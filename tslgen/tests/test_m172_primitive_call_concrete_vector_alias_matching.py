from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import (
    SelectedImplementation,
    Selector,
    Target,
    TargetReturnTypeBaseBinding,
    TargetSpecializationBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, LowerableDirective, TypeTag
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    PrimitiveCallSelectorPayload,
    build_selected_implementation_lowering_context,
    build_selected_type_environment,
)
from tslgen.lowering.primitive_calls import PrimitiveCallResolver
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_m172_matches_arbitrary_vector_transform_alias(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
            (
                "let<type>(ChunkAlias, type<generation>(vector::transform_extension(scalar::f64)))",
                "call<primitive=convert[ChunkAlias]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("convert", type_tag="f64"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "convert"
    assert result.match.selected.target.extension == "scalar"
    assert result.match.selected.target.type_tag == "f64"


def test_m172_matches_alias_with_backend_scalar_base(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
            (
                "let<type>(BackendAlias, type<generation>(vector::transform_extension(type<backend>(scalar::f64))))",
                "call<primitive=convert[BackendAlias]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("convert", type_tag="f64"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.target.type_tag == "f64"


def test_m172_matches_alias_with_resolved_unsigned_transform(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
            (
                "let<type>(UnsignedAlias, type<generation>(vector::transform_extension(type<generation>(base::unsigned_of(type<generation>(base::in))))))",
                "call<primitive=convert[UnsignedAlias]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("convert", type_tag="ui32"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.target.type_tag == "ui32"


def test_m172_preserves_alias_plus_return_binding_decoration(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_return_binding=("base", "CallerResult"),
        call_payload="\n".join(
            (
                "let<type>(NarrowAlias, type<generation>(vector::transform_extension(scalar::ui32)))",
                "call<primitive=convert[NarrowAlias, CallerResult]>(left, right)",
            )
        ),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="CallerResult",
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(
            _primitive_source(
                "convert",
                type_tag="ui32",
                return_binding=("base", "TargetResult"),
            ),
        ),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert payload.selected_return_binding_names == (None, "CallerResult")
    assert result.match.selected.target.type_tag == "ui32"
    assert result.match.selected.target.specialization_bindings == (
        TargetReturnTypeBaseBinding(
            name="TargetResult",
            type_tag=TypeTag("f64"),
        ),
    )


def test_m172_preserves_existing_vec_and_as_extension_matching(
    tmp_path: Path,
) -> None:
    catalog, selected, first_payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
                (
                    "call<primitive=same[Vec]>(left, right)",
                    "call<primitive=widen[type<backend>(vector::as_extension(scalar, scalar::f64))]>(left, right)",
                )
            ),
        extra_primitives=(
            _primitive_source("same"),
            _primitive_source("widen", type_tag="f64"),
        ),
        call_index=0,
    )
    second_payload = _lower_payload_for_call(catalog, selected, call_index=1)

    first = _match_target(catalog, selected, first_payload)
    second = _match_target(catalog, selected, second_payload)

    assert first.diagnostics == ()
    assert first.match is not None
    assert first.match.selected.primitive.name == "same"
    assert first.match.selected.target.type_tag == "si32"
    assert second.diagnostics == ()
    assert second.match is not None
    assert second.match.selected.primitive.name == "widen"
    assert second.match.selected.target.type_tag == "f64"


def test_m172_rejects_raw_symbol_vector_selector(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[UnknownAlias]>(left, right)",
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 30),
    )
    assert "selector symbol 'UnknownAlias'" in result.diagnostics[0].message


def test_m172_rejects_literal_vector_selector(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[3]>(left, right)",
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 30),
    )
    assert "selector literal '3'" in result.diagnostics[0].message


def test_m172_rejects_catalog_extension_vector_selector(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="call<primitive=convert[avx2]>(left, right)",
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 4, 30),
    )
    assert "extension operand 'avx2'" in result.diagnostics[0].message


def test_m172_rejects_unresolved_specialization_alias(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
            (
                "let<type>(UnresolvedAlias, type<generation>(vector::transform_extension(ToBase)))",
                "call<primitive=convert[UnresolvedAlias]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 22),
    )
    assert "LoweredVectorTransformType" in result.diagnostics[0].message


def test_m172_rejects_mask_member_alias(tmp_path: Path) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        call_payload="\n".join(
            (
                "let<type>(MaskAlias, type<generation>(vector::transform(type<generation>(vector::mask_underlying_t))))",
                "call<primitive=convert[MaskAlias]>(left, right)",
            )
        ),
        extra_primitives=(_primitive_source("convert"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 22),
    )
    assert "LoweredVectorTransformType" in result.diagnostics[0].message


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
    call_index: int = 0,
) -> tuple[Catalog, SelectedImplementation, PrimitiveCallSelectorPayload]:
    catalog, selected = _selected_current(
        tmp_path,
        call_payload=call_payload,
        current_return_binding=current_return_binding,
        specialization_bindings=specialization_bindings,
        extra_primitives=extra_primitives,
    )
    return catalog, selected, _lower_payload_for_call(
        catalog,
        selected,
        call_index=call_index,
    )


def _lower_payload_for_call(
    catalog: Catalog,
    selected: SelectedImplementation,
    *,
    call_index: int,
) -> PrimitiveCallSelectorPayload:
    calls = _primitive_calls(selected)
    call = calls[call_index]
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
    return result.payload


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
        "m172_current.tsl",
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
                f"m172_target_{index}.tsl",
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
    extension: str = "scalar",
    type_tag: str = "si32",
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
            f"  implementation {extension} {type_tag}:",
            *body_lines,
        )
    )


def _single_primitive_call(selected: SelectedImplementation):
    calls = _primitive_calls(selected)
    assert len(calls) == 1
    return calls[0]


def _primitive_calls(selected: SelectedImplementation):
    calls = tuple(
        token.primitive_call
        for token in selected.implementation.body.tokens
        if isinstance(token, LowerableDirective) and token.primitive_call is not None
    )
    assert all(call is not None for call in calls)
    return calls


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
