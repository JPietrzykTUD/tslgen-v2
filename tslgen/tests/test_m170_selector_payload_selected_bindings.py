from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import (
    SelectedImplementation,
    Selector,
    Target,
    TargetReturnTypeBaseBinding,
    TargetReturnTypeExtensionBinding,
    TargetSpecializationBinding,
    TargetVectorTypeBinding,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    ExtensionName,
    LowerableDirective,
    PrimitiveCall,
    TypeTag,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    BackendTypeSpellingRequest,
    CurrentVector,
    ExtensionOperand,
    LoweredBackendTypeReference,
    LoweredCurrentScalarType,
    LoweredScalarTypeIdentity,
    LoweredVectorAsExtensionType,
    PrimitiveCallSelectorPayload,
    SelectorSymbol,
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


def test_m170_selector_payload_lowers_arbitrary_base_binding_name(
    tmp_path: Path,
) -> None:
    source, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  return_type:
    base: ResultBase
  implementation scalar si32:
    tsil "call<primitive=@self[ResultBase]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetReturnTypeBaseBinding(
                name="ResultBase",
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        LoweredScalarTypeIdentity(type_tag=TypeTag("f64")),
    )
    assert result.payload.selected_return_binding_names == ("ResultBase",)
    assert result.payload.source == SourceLocation(source, 5, 26)


def test_m170_selector_payload_lowers_arbitrary_extension_binding_name(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  return_type:
    extension: TargetExtension
  implementation scalar si32:
    tsil "call<primitive=@self[TargetExtension]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="TargetExtension",
                extension=ExtensionName("avx2"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        ExtensionOperand(
            name=ExtensionName("avx2"),
            source=SourceLocation(_single_primitive_call(selected).source.path, 5, 32),
        ),
    )
    assert result.payload.selected_return_binding_names == ("TargetExtension",)


def test_m170_selector_payload_lowers_explicit_vector_type_binding(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[ToType]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="ToType",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("f64")),
    )
    assert result.payload.selected_return_binding_names == (None,)


def test_m170_unbound_arbitrary_selector_symbol_stays_raw(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[PreserveSign]>(left, right)"
""".strip(),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        SelectorSymbol(
            name="PreserveSign",
            source=SourceLocation(_single_primitive_call(selected).source.path, 3, 32),
        ),
    )
    assert result.payload.selected_return_binding_names == (None,)


def test_m170_declared_extension_without_selected_fact_is_not_raw_extension(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  return_type:
    extension: sse
  implementation scalar si32:
    tsil "call<primitive=@self[sse]>(left, right)"
""".strip(),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.payload is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNBOUND-SELECTED-SPECIALIZATION-BINDING",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 32),
    )


def test_m170_selector_payload_preserves_malformed_binding_diagnostic(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[Vec]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="Bad Name",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.payload is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-MALFORMED-SELECTED-SPECIALIZATION-BINDING",
        SourceLocation(_single_primitive_call(selected).source.path, 1, 1),
    )


def test_m170_selector_payload_preserves_duplicate_binding_diagnostic(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil "call<primitive=@self[Vec]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="ToType",
                extension=ExtensionName("sse"),
                type_tag=TypeTag("f32"),
            ),
            TargetVectorTypeBinding(
                name="ToType",
                extension=ExtensionName("avx2"),
                type_tag=TypeTag("f64"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.payload is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-DUPLICATE-SELECTED-SPECIALIZATION-BINDING",
        SourceLocation(_single_primitive_call(selected).source.path, 1, 1),
    )


def test_m170_selector_payload_preserves_mismatched_binding_diagnostic(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  return_type:
    base: ResultBase
  implementation scalar si32:
    tsil "call<primitive=@self[Vec]>(left, right)"
""".strip(),
        specialization_bindings=(
            TargetReturnTypeExtensionBinding(
                name="ResultBase",
                extension=ExtensionName("avx2"),
            ),
        ),
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.payload is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-SELECTED-SPECIALIZATION-BINDING-MISMATCH",
        SourceLocation(_single_primitive_call(selected).source.path, 1, 1),
    )


def test_m170_selector_payload_preserves_alias_keyword_and_prefix_behavior(
    tmp_path: Path,
) -> None:
    _, catalog, selected = _selected_call(
        tmp_path,
        """
prim<v:=(v,v)> add(left, right):
  implementation scalar si32:
    tsil \"\"\"
      let<type>(Alias, Vec)
      call<primitive=@self[Alias, Vec, type<backend>(vector::as_extension(scalar))]>(left, right)
    \"\"\"
""".strip(),
        selected_extension="avx2",
    )

    result = _lower_selector_payload(selected, _single_primitive_call(selected), catalog)

    assert result.diagnostics == ()
    assert result.payload is not None
    assert result.payload.specializations == (
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("si32")),
        CurrentVector(extension=ExtensionName("avx2"), type_tag=TypeTag("si32")),
        LoweredBackendTypeReference(
            request=BackendTypeSpellingRequest(
                backend="cpp",
                value=LoweredVectorAsExtensionType(
                    base_type=LoweredCurrentScalarType(type_tag=TypeTag("si32")),
                    extension=ExtensionName("scalar"),
                ),
                source_text="type<backend>(vector::as_extension(scalar))",
                source=SourceLocation(_single_primitive_call(selected).source.path, 5, 40),
            )
        ),
    )


def test_m170_target_matching_consumes_vector_binding_through_existing_path(
    tmp_path: Path,
) -> None:
    catalog, _, selected, payload = _selected_payload(
        tmp_path,
        "call<primitive=sub[ToType]>(left, right)",
        specialization_bindings=(
            TargetVectorTypeBinding(
                name="ToType",
                extension=ExtensionName("scalar"),
                type_tag=TypeTag("f64"),
            ),
        ),
        extra_primitives=(
            _primitive_source("sub", "sub", type_tag="f64"),
        ),
    )

    result = PrimitiveCallResolver(catalog).match_target(
        build_selected_implementation_lowering_context(selected),
        payload,
    )

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "sub"
    assert result.match.selected.target.extension == "scalar"
    assert result.match.selected.target.type_tag == "f64"


def _lower_selector_payload(
    selected: SelectedImplementation,
    call: PrimitiveCall,
    catalog: Catalog,
):
    context = build_selected_implementation_lowering_context(selected)
    environment = build_selected_type_environment(context)
    return lower_primitive_call_selector_payload(
        context,
        catalog,
        call,
        environment,
    )


def _selected_payload(
    tmp_path: Path,
    call_payload: str,
    *,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, Path, SelectedImplementation, PrimitiveCallSelectorPayload]:
    source, catalog, selected = _selected_call(
        tmp_path,
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                *(f"      {line}" for line in call_payload.splitlines()),
                '    """',
            )
        ),
        specialization_bindings=specialization_bindings,
        extra_primitives=extra_primitives,
    )
    payload_result = _lower_selector_payload(
        selected,
        _single_primitive_call(selected),
        catalog,
    )
    assert payload_result.diagnostics == ()
    assert payload_result.payload is not None
    return catalog, source, selected, payload_result.payload


def _selected_call(
    tmp_path: Path,
    primitive_source_text: str,
    *,
    selected_extension: str | None = None,
    specialization_bindings: tuple[TargetSpecializationBinding, ...] = (),
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Path, Catalog, SelectedImplementation]:
    source = _source_document(tmp_path, "m170_current.tsl", primitive_source_text)
    documents = [
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        source,
    ]
    for index, primitive_source in enumerate(extra_primitives):
        documents.append(
            _source_document(
                tmp_path,
                f"m170_target_{index}.tsl",
                primitive_source,
            )
        )

    parse_result = TslParser().parse(tuple(documents))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None

    primitive = catalog_result.catalog.primitives[-1 - len(extra_primitives)]
    implementation = primitive.implementations[0]
    if selected_extension is not None:
        implementation = replace(implementation, extension=selected_extension)

    target = Target(
        backend="cpp",
        primitive_name=primitive.name,
        extension=implementation.extension,
        type_tag=implementation.type_tag,
        specialization_bindings=specialization_bindings,
    )
    if selected_extension is None:
        selection = Selector().select(catalog_result.catalog, target)
        assert selection.diagnostics == ()
        assert len(selection.selected) == 1
        selected = selection.selected[0]
    else:
        selected = SelectedImplementation(
            target=target,
            primitive=primitive,
            implementation=implementation,
        )
    return source.path, catalog_result.catalog, selected


def _primitive_source(
    name: str,
    operation: str,
    *,
    extension: str = "scalar",
    type_tag: str = "si32",
) -> str:
    return "\n".join(
        (
            f"prim<v:=(v,v)> {name}(left, right):",
            f"  implementation {extension} {type_tag}:",
            f"    body {operation}(left, right)",
        )
    )


def _single_primitive_call(selected: SelectedImplementation) -> PrimitiveCall:
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
