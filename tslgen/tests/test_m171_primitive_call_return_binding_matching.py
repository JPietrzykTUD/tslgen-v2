from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import (
    SelectedImplementation,
    Selector,
    Target,
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, ExtensionName, LowerableDirective, TypeTag
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    PrimitiveCallSelectorPayload,
    build_selected_implementation_lowering_context,
    build_selected_type_environment,
)
from tslgen.lowering.primitive_calls import (
    PrimitiveCallDependencyCollector,
    PrimitiveCallResolver,
)
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_m171_maps_arbitrary_caller_base_binding_to_target_declaration(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_return_binding=("base", "CallerResult"),
        call_payload="call<primitive=convert[Vec, CallerResult]>(left, right)",
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="CallerResult",
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(
            _primitive_source(
                "convert",
                return_binding=("base", "TargetResult"),
            ),
        ),
    )

    first = _match_target(catalog, selected, payload)
    second = _match_target(catalog, selected, payload)

    assert first.diagnostics == ()
    assert first.match is not None
    assert payload.selected_return_binding_names == (None, "CallerResult")
    assert first.match.selected.primitive.name == "convert"
    assert first.match.selected.target.specialization_bindings == (
        TargetReturnTypeBaseBinding(
            name="TargetResult",
            type_tag=TypeTag("f64"),
        ),
    )
    assert first.match.selected.target.sort_key() == second.match.selected.target.sort_key()


def test_m171_maps_arbitrary_caller_extension_binding_to_target_declaration(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_return_binding=("extension", "CallerExtension"),
        call_payload="call<primitive=route[Vec, CallerExtension]>(left, right)",
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="CallerExtension",
                extension=ExtensionName("avx2"),
            ),
        ),
        extra_primitives=(
            _primitive_source(
                "route",
                return_binding=("extension", "TargetExtension"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert payload.selected_return_binding_names == (None, "CallerExtension")
    assert result.match.selected.primitive.name == "route"
    assert result.match.selected.target.specialization_bindings == (
        TargetReturnTypeExtensionBinding(
            name="TargetExtension",
            extension=ExtensionName("avx2"),
        ),
    )


def test_m171_preserves_existing_single_vector_selector_matching(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[Vec]>(left, right)",
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "convert"
    assert result.match.selected.target.specialization_bindings == ()


def test_m171_keeps_raw_unbound_selector_symbols_unsupported(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[Vec, PreserveSign]>(left, right)",
        extra_primitives=(
            _primitive_source(
                "convert",
                return_binding=("base", "TargetResult"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 22),
    )
    assert "PreserveSign" in result.diagnostics[0].message


def test_m171_reports_return_binding_without_target_declaration(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_return_binding=("base", "CallerResult"),
        call_payload="call<primitive=convert[Vec, CallerResult]>(left, right)",
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="CallerResult",
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 6, 22),
    )
    assert "no primitive-local return_type declaration" in result.diagnostics[0].message


def test_m171_reports_wrong_binding_kind_for_target_declaration(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_return_binding=("base", "CallerResult"),
        call_payload="call<primitive=convert[Vec, CallerResult]>(left, right)",
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="CallerResult",
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(
            _primitive_source(
                "convert",
                return_binding=("extension", "TargetExtension"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 6, 22),
    )
    assert "expected return_type.extension" in result.diagnostics[0].message
    assert "got return_type.base" in result.diagnostics[0].message


def test_m171_rejects_raw_scalar_type_expression_as_return_binding(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[Vec, scalar::f64]>(left, right)",
        extra_primitives=(
            _primitive_source(
                "convert",
                return_binding=("base", "TargetResult"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert payload.selected_return_binding_names == (None, None)
    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 22),
    )
    assert "selected return-type binding" in result.diagnostics[0].message
    assert "LoweredScalarTypeIdentity" in result.diagnostics[0].message


def test_m171_rejects_raw_known_extension_as_return_binding(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=route[Vec, avx2]>(left, right)",
        extra_primitives=(
            _primitive_source(
                "route",
                return_binding=("extension", "TargetExtension"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert payload.selected_return_binding_names == (None, None)
    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 22),
    )
    assert "selected return-type binding" in result.diagnostics[0].message
    assert "extension operand 'avx2'" in result.diagnostics[0].message


def test_m171_reference_inventory_preserves_decorated_target_binding(
    tmp_path: Path,
) -> None:
    catalog, selected, _ = _selected_payload(
        tmp_path,
        current_return_binding=("base", "CallerResult"),
        call_payload="call<primitive=convert[Vec, CallerResult]>(left, right)",
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="CallerResult",
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(
            _primitive_source(
                "convert",
                return_binding=("base", "TargetResult"),
            ),
        ),
    )

    inventory = PrimitiveCallDependencyCollector(catalog).reference_inventory(selected)

    assert inventory.diagnostics == ()
    assert len(inventory.references) == 1
    assert inventory.references[0].target_match.selected.target.specialization_bindings == (
        TargetReturnTypeBaseBinding(
            name="TargetResult",
            type_tag=TypeTag("f64"),
        ),
    )


def _match_target(
    catalog: Catalog,
    selected: SelectedImplementation,
    payload: PrimitiveCallSelectorPayload,
):
    return PrimitiveCallResolver(catalog).match_target(
        build_selected_implementation_lowering_context(selected),
        payload,
    )


def _selected_payload(
    tmp_path: Path,
    *,
    call_payload: str,
    current_return_binding: tuple[str, str] | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation, PrimitiveCallSelectorPayload]:
    catalog, selected = _selected_current(
        tmp_path,
        call_payload=call_payload,
        current_return_binding=current_return_binding,
        specialization_bindings=specialization_bindings,
        extra_primitives=extra_primitives,
    )
    call = _single_primitive_call(selected)
    context = build_selected_implementation_lowering_context(selected)
    environment = build_selected_type_environment(context)
    result = lower_primitive_call_selector_payload(
        context,
        catalog,
        call,
        environment,
    )

    assert result.diagnostics == ()
    assert result.payload is not None
    return catalog, selected, result.payload


def _selected_current(
    tmp_path: Path,
    *,
    call_payload: str,
    current_return_binding: tuple[str, str] | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation]:
    current_source = _source_document(
        tmp_path,
        "m171_current.tsl",
        _primitive_source(
            "add",
            return_binding=current_return_binding,
            body_payload=call_payload,
        ),
    )
    documents = [
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        current_source,
    ]
    for index, primitive_source in enumerate(extra_primitives):
        documents.append(
            _source_document(
                tmp_path,
                f"m171_target_{index}.tsl",
                primitive_source,
            )
        )

    parse_result = TslParser().parse(tuple(documents))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None

    target = Target(
        backend="cpp",
        primitive_name="add",
        extension="scalar",
        type_tag="si32",
        specialization_bindings=specialization_bindings,
    )
    selection = Selector().select(catalog_result.catalog, target)
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1
    return catalog_result.catalog, selection.selected[0]


def _primitive_source(
    name: str,
    *,
    return_binding: tuple[str, str] | None = None,
    body_payload: str | None = None,
) -> str:
    return_type_lines: tuple[str, ...] = ()
    if return_binding is not None:
        kind, binding_name = return_binding
        return_type_lines = (
            "  return_type:",
            f"    {kind}: {binding_name}",
        )

    if body_payload is None:
        body_lines = ("    body add(left, right)",)
    else:
        body_lines = (
            '    tsil """',
            *(f"      {line}" for line in body_payload.splitlines()),
            '    """',
        )

    return "\n".join(
        (
            f"prim<v:=(v,v)> {name}(left, right):",
            *return_type_lines,
            "  implementation scalar si32:",
            *body_lines,
        )
    )


def _single_primitive_call(selected: SelectedImplementation):
    calls = tuple(
        token.primitive_call
        for token in selected.implementation.body.tokens
        if isinstance(token, LowerableDirective) and token.primitive_call is not None
    )
    assert len(calls) == 1
    assert calls[0] is not None
    return calls[0]


def _assert_single_diagnostic(
    diagnostics: tuple[Diagnostic, ...],
    code: str,
    location: SourceLocation,
) -> None:
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.code == code
    assert diagnostic.severity == "error"
    assert diagnostic.location == location


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return _document(path)
