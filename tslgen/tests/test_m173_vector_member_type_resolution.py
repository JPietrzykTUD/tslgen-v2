from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    Extension,
    ExtensionCatalog,
    ExtensionTypePolicy,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    NamedPrimitiveReference,
    Primitive,
    PrimitiveCall,
    PrimitiveCallArgument,
    PrimitiveCallSelector,
    TypeTag,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    LoweredScalarTypeIdentity,
    LoweredVectorMemberType,
    PrimitiveCallSelectorPayload,
    build_selected_implementation_lowering_context,
    build_selected_type_environment,
)
from tslgen.lowering.primitive_calls import PrimitiveCallResolver
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.lowering.vector_member_types import resolve_vector_member_scalar_type
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_m173_resolves_lane_bitmask_members_to_exact_unsigned_scalar() -> None:
    catalog = _catalog_from_documents()
    source = _location(4, 7)

    mask = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="mask",
            extension="avx2",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )
    underlying = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="mask_underlying",
            extension="avx2",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )
    imask = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="avx2",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )

    assert mask == LoweredScalarTypeIdentity(type_tag=TypeTag("ui8"))
    assert underlying == LoweredScalarTypeIdentity(type_tag=TypeTag("ui8"))
    assert imask == LoweredScalarTypeIdentity(type_tag=TypeTag("ui8"))


def test_m173_matches_maskvec_style_alias_through_resolved_member_type(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_extension="avx2",
        current_type_tag="si32",
        alias_name="LocalAlias",
        alias_expression=(
            "type<generation>(vector::transform("
            "type<generation>(vector::mask_underlying_t)))"
        ),
        extra_primitives=(_primitive_source("convert", "avx2", "ui8"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.diagnostics == ()
    assert result.match is not None
    assert result.match.selected.primitive.name == "convert"
    assert result.match.selected.target.extension == "avx2"
    assert result.match.selected.target.type_tag == "ui8"


def test_m173_native_predicate_member_policy_is_not_scalar_selector(
    tmp_path: Path,
) -> None:
    catalog = _catalog_from_documents()
    source = _location(4, 7)

    resolved = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="mask",
            extension="avx512",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )

    assert isinstance(resolved, Diagnostic)
    _assert_direct_diagnostic(
        resolved,
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        source,
    )
    assert "native_predicate_by_lanes" in resolved.message

    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_extension="avx512",
        current_type_tag="si32",
        alias_name="PredicateAlias",
        alias_expression=(
            "type<generation>(vector::transform("
            "type<generation>(vector::mask)))"
        ),
        extra_primitives=(_primitive_source("convert", "avx512", "ui16"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 22),
    )
    assert "native_predicate_by_lanes" in result.diagnostics[0].message


def test_m173_backend_member_type_reference_is_not_scalar_selector(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_extension="avx2",
        current_type_tag="si32",
        alias_name="BackendMemberAlias",
        alias_expression=(
            "type<generation>(vector::transform("
            "type<backend>(vector::mask_underlying_t)))"
        ),
        extra_primitives=(_primitive_source("convert", "avx2", "ui8"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 22),
    )


def test_m173_reports_missing_extension_metadata() -> None:
    source = _location(4, 7)
    result = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="missing",
            type_tag=TypeTag("si32"),
        ),
        catalog=Catalog(primitives=()),
        source=source,
    )

    assert isinstance(result, Diagnostic)
    _assert_direct_diagnostic(
        result,
        "TSL-LOWER-MISSING-VECTOR-MEMBER-TYPE-METADATA",
        source,
    )
    assert "known extension 'missing'" in result.message


def test_m173_reports_unsupported_policy_and_non_mask_member() -> None:
    catalog = _catalog_from_documents()
    scalar_source = _location(4, 7)
    register_source = _location(5, 7)

    scalar_imask = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="scalar",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=scalar_source,
    )
    register = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="register",
            extension="avx2",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=register_source,
    )

    assert isinstance(scalar_imask, Diagnostic)
    _assert_direct_diagnostic(
        scalar_imask,
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        scalar_source,
    )
    assert "unsigned_scalar" in scalar_imask.message
    assert isinstance(register, Diagnostic)
    _assert_direct_diagnostic(
        register,
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        register_source,
    )
    assert "not a scalar mask member" in register.message


def test_m173_reports_unsupported_unmapped_lane_bitmask_width() -> None:
    catalog = _catalog_with_large_lane_bitmask_extension()
    source = _location(4, 7)

    result = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="large_bitmask",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )

    assert isinstance(result, Diagnostic)
    _assert_direct_diagnostic(
        result,
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        source,
    )
    assert "exactly 128 bits" in result.message


def test_m173_requires_explicit_non_runtime_lane_metadata() -> None:
    catalog = _catalog_with_runtime_lanes(None)
    source = _location(4, 7)

    result = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="unknown_runtime_bitmask",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )

    assert isinstance(result, Diagnostic)
    _assert_direct_diagnostic(
        result,
        "TSL-LOWER-MISSING-VECTOR-MEMBER-TYPE-METADATA",
        source,
    )
    assert "explicit non-runtime fixed vector lanes" in result.message


def test_m173_rejects_same_as_mask_type_policy_cycle() -> None:
    catalog = _catalog_with_same_as_mask_cycle()
    source = _location(4, 7)

    result = resolve_vector_member_scalar_type(
        LoweredVectorMemberType(
            member="imask",
            extension="cycle_bitmask",
            type_tag=TypeTag("si32"),
        ),
        catalog=catalog,
        source=source,
    )

    assert isinstance(result, Diagnostic)
    _assert_direct_diagnostic(
        result,
        "TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        source,
    )
    assert "refers back to itself" in result.message


def test_m173_preserves_scalar_mask_member_selector_diagnostic(
    tmp_path: Path,
) -> None:
    catalog, selected, payload = _selected_payload(
        tmp_path,
        current_extension="scalar",
        current_type_tag="si32",
        alias_name="StillOpaque",
        alias_expression=(
            "type<generation>(vector::transform("
            "type<generation>(vector::mask_underlying_t)))"
        ),
        extra_primitives=(_primitive_source("convert", "scalar", "ui8"),),
    )

    result = _match_target(catalog, selected, payload)

    assert result.match is None
    _assert_single_diagnostic(
        result.diagnostics,
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL-SELECTOR",
        SourceLocation(_single_primitive_call(selected).source.path, 5, 22),
    )
    assert "unsigned_scalar" in result.diagnostics[0].message


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
    base_catalog: Catalog | None = None,
    current_extension: str,
    current_type_tag: str,
    alias_name: str,
    alias_expression: str,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation, PrimitiveCallSelectorPayload]:
    catalog, selected = _selected_current(
        tmp_path,
        base_catalog=base_catalog,
        current_extension=current_extension,
        current_type_tag=current_type_tag,
        alias_name=alias_name,
        alias_expression=alias_expression,
        extra_primitives=extra_primitives,
    )
    return catalog, selected, _lower_payload_for_call(catalog, selected)


def _lower_payload_for_call(
    catalog: Catalog,
    selected: SelectedImplementation,
) -> PrimitiveCallSelectorPayload:
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
    return result.payload


def _selected_current(
    tmp_path: Path,
    *,
    base_catalog: Catalog | None = None,
    current_extension: str,
    current_type_tag: str,
    alias_name: str,
    alias_expression: str,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation]:
    source_path = tmp_path / "m173_current.tsl"
    current = _primitive(
        "add",
        current_extension,
        current_type_tag,
        body=_body_with_alias_call(source_path, alias_name, alias_expression),
    )
    target_primitives = tuple(
        _primitive_from_source(tmp_path, index, primitive_source)
        for index, primitive_source in enumerate(extra_primitives)
    )
    if base_catalog is None:
        base_catalog = _catalog_from_documents()
    catalog = Catalog(
        primitives=(current, *target_primitives),
        type_groups=base_catalog.type_groups,
        extensions=base_catalog.extensions,
    )

    target = Target(
        backend="cpp",
        primitive_name="add",
        extension=current_extension,
        type_tag=current_type_tag,
    )
    selection = Selector().select(catalog, target)
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1
    return catalog, selection.selected[0]


def _primitive_source(
    name: str,
    extension: str,
    type_tag: str,
    *,
    body_payload: str | None = None,
) -> str:
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
            f"  implementation {extension} {type_tag}:",
            *body_lines,
        )
    )


def _primitive_from_source(
    tmp_path: Path,
    index: int,
    source_text: str,
) -> Primitive:
    source_path = tmp_path / f"m173_target_{index}.tsl"
    lines = source_text.splitlines()
    header = lines[0]
    implementation = lines[1]
    name = header.split(" ", 1)[1].split("(", 1)[0]
    extension, type_tag = implementation.removeprefix("  implementation ").removesuffix(
        ":"
    ).split(" ")
    return _primitive(name, extension, type_tag, body=_empty_body(source_path))


def _primitive(
    name: str,
    extension: str,
    type_tag: str,
    *,
    body: ImplementationBody,
) -> Primitive:
    source = SourceLocation(Path(f"{name}.tsl"), 1, 1)
    return Primitive(
        name=name,
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template=name,
        implementations=(
            Implementation(
                extension=extension,
                type_tag=type_tag,
                body=body,
                source=source,
            ),
        ),
        source=source,
    )


def _body_with_alias_call(
    source_path: Path,
    alias_name: str,
    alias_expression: str,
) -> ImplementationBody:
    let_source = SourceLocation(source_path, 4, 7)
    call_source = SourceLocation(source_path, 5, 7)
    selector_source = SourceLocation(source_path, 5, 22)
    selector_text = f"convert[{alias_name}]"
    call = PrimitiveCall(
        selector=PrimitiveCallSelector(
            target=NamedPrimitiveReference(name="convert", source=selector_source),
            specialization=alias_name,
            attrs=None,
            source_text=selector_text,
            source=selector_source,
        ),
        payload="left, right",
        source=call_source,
        arguments=(
            PrimitiveCallArgument(text="left", source=SourceLocation(source_path, 5, 46)),
            PrimitiveCallArgument(
                text="right",
                source=SourceLocation(source_path, 5, 52),
            ),
        ),
    )
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="let",
                arguments=("type", f"{alias_name}, {alias_expression}"),
                source=let_source,
            ),
            LowerableDirective(
                name="call",
                arguments=("primitive",),
                source=call_source,
                primitive_call=call,
            ),
        ),
        source=SourceLocation(source_path, 3, 5),
    )


def _empty_body(source_path: Path) -> ImplementationBody:
    return ImplementationBody(tokens=(), source=SourceLocation(source_path, 3, 5))


def _catalog_from_documents() -> Catalog:
    parse_result = TslParser().parse((_document(TYPES_TSL), _document(EXTENSIONS_TSL)))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    return catalog_result.catalog


def _catalog_with_large_lane_bitmask_extension() -> Catalog:
    catalog = _catalog_from_documents()
    avx2 = catalog.extensions.get("avx2")
    assert avx2 is not None
    return _catalog_with_extension(
        catalog,
        replace(
            avx2,
            name="large_bitmask",
            extension_name="large_bitmask",
            vector_bits=4096,
            runtime_lanes=False,
            size_parameter=None,
        ),
    )


def _catalog_with_runtime_lanes(runtime_lanes: bool | None) -> Catalog:
    catalog = _catalog_from_documents()
    avx2 = catalog.extensions.get("avx2")
    assert avx2 is not None
    return _catalog_with_extension(
        catalog,
        replace(
            avx2,
            name="unknown_runtime_bitmask",
            extension_name="unknown_runtime_bitmask",
            vector_bits=1024,
            runtime_lanes=runtime_lanes,
            size_parameter=None,
        ),
    )


def _catalog_with_same_as_mask_cycle() -> Catalog:
    catalog = _catalog_from_documents()
    avx2 = catalog.extensions.get("avx2")
    assert avx2 is not None
    policy = ExtensionTypePolicy(
        kind="same_as_mask_type",
        source=_location(9, 3),
    )
    return _catalog_with_extension(
        catalog,
        replace(
            avx2,
            name="cycle_bitmask",
            extension_name="cycle_bitmask",
            vector_bits=1024,
            runtime_lanes=False,
            size_parameter=None,
            mask_type_policy=policy,
            integral_mask_type_policy=policy,
        ),
    )


def _catalog_with_extension(catalog: Catalog, extension: Extension) -> Catalog:
    return Catalog(
        primitives=catalog.primitives,
        type_groups=catalog.type_groups,
        extensions=ExtensionCatalog(
            extensions=(
                *tuple(
                    item
                    for item in catalog.extensions.extensions
                    if item.name != extension.name
                ),
                extension,
            ),
        ),
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
    _assert_direct_diagnostic(diagnostics[0], code, location)


def _assert_direct_diagnostic(
    diagnostic: Diagnostic,
    code: str,
    location: SourceLocation,
) -> None:
    assert diagnostic.code == code
    assert diagnostic.severity == "error"
    assert diagnostic.location == location


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(Path("m173.tsl"), line, column)


def _document(path: Path) -> SourceDocument:
    resolved = path.resolve()
    text = resolved.read_text(encoding="utf-8")
    return SourceDocument(
        path=resolved,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
