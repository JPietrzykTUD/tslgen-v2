from __future__ import annotations

from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.backends import (
    BackendIntrinsicImmediateGenericParameterReference,
    translate_backend_intrinsic_modifier_field,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    Implementation,
    ImplementationBody,
    Primitive,
    PrimitiveGenericParameter,
    PrimitiveGenericParameterKind,
)
from tslgen.domain.signatures import (
    PrimitiveSignature,
    SignatureTermKind,
    parse_primitive_signature,
    signature_parameter_terms,
)
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    BackendIntrinsicComposeHandoffRequest,
    BackendIntrinsicHandoffRequestSegment,
    BackendIntrinsicModifierField,
    BackendIntrinsicModifierSymbolOperand,
    LoweredSelectedGenericImmediateParameter,
    LoweredSelectedSignatureImmediateParameter,
    Lowerer,
    discover_backend_intrinsic_requests_in_text,
)
from tslgen.lowering._source_islands import matching_delimiter_close
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.ast import (
    PARSED_TSIL_BODY_ENVELOPE,
    ParsedDocument,
    ParsedGenericParameter,
    ParsedImplementation,
    ParsedImplementationBody,
    ParsedPrimitive,
    ParsedRawStringLine,
)
from tslgen.syntax.parser import TslParser

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_m210_generic_parameter_values_are_dataclasses_and_enums() -> None:
    assert is_dataclass(PrimitiveGenericParameter)
    assert issubclass(PrimitiveGenericParameterKind, Enum)
    assert PrimitiveGenericParameterKind.INT.value == "int"
    assert PrimitiveGenericParameterKind.BOOL.value == "bool"
    assert PrimitiveGenericParameterKind.SIMD_TYPE.value == "simd_type"


def test_m210_catalog_promotes_observed_generic_param_forms(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "generic_params.tsl",
        """prim<v:=(v,v)> fixture(left, right):
  generic_params:
    PreserveSign:
      kind bool
      default true
    IndicesType {kind simd_type}
    N {kind int, default 1}
    Index {kind int, default 0}
  implementation scalar si32:
    body fixture(left, right)
""",
    )

    parse_result = TslParser().parse((source,))
    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert parse_result.diagnostics == ()
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None
    primitive = catalog_result.catalog.primitives[0]
    assert tuple(
        (parameter.name, parameter.kind, parameter.default)
        for parameter in primitive.generic_parameters
    ) == (
        ("PreserveSign", PrimitiveGenericParameterKind.BOOL, True),
        ("IndicesType", PrimitiveGenericParameterKind.SIMD_TYPE, None),
        ("N", PrimitiveGenericParameterKind.INT, 1),
        ("Index", PrimitiveGenericParameterKind.INT, 0),
    )


def test_m210_selected_context_exposes_generic_params() -> None:
    generic = _generic("Index", PrimitiveGenericParameterKind.INT, 0)
    selected = _selected(
        signature_text="s:=v[idx]",
        parameter_names=("a",),
        generic_parameters=(generic,),
    )

    context = Lowerer().context_for(selected)

    assert context.generic_parameters == (generic,)
    assert context.parameter_names == ("a",)


def test_m210_lowers_and_translates_indexed_generic_immediate_parameter() -> None:
    generic = _generic("Index", PrimitiveGenericParameterKind.INT, 0)
    request = _single_compose_request(
        "intrin_compose<vgetq_lane suffix=si32 immediate(1)=Index>(a, Index)",
        _selected(
            signature_text="s:=v[idx]",
            parameter_names=("a",),
            generic_parameters=(generic,),
        ),
    )
    field = _immediate_field(request)

    immediate = field.value
    assert isinstance(immediate, LoweredSelectedGenericImmediateParameter)
    assert immediate.argument_index == 1
    assert immediate.parameter is generic
    assert immediate.source_text == "Index"

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.field is field
    assert result.modifier.value == BackendIntrinsicImmediateGenericParameterReference(
        argument_index=1,
        parameter=generic,
        source_text="Index",
        source=immediate.source,
    )


def test_m210_generic_immediate_name_is_not_hardcoded_to_index() -> None:
    generic = _generic("Lane", PrimitiveGenericParameterKind.INT, 2)
    request = _single_compose_request(
        "intrin_compose<vgetq_lane immediate(1)=Lane>(a, Lane)",
        _selected(
            signature_text="s:=v[idx]",
            parameter_names=("a",),
            generic_parameters=(generic,),
        ),
    )
    field = _immediate_field(request)

    assert isinstance(field.value, LoweredSelectedGenericImmediateParameter)
    assert field.value.parameter.name == "Lane"

    result = translate_backend_intrinsic_modifier_field(field, "rust")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicImmediateGenericParameterReference(
        argument_index=1,
        parameter=generic,
        source_text="Lane",
        source=field.value.source,
    )


def test_m210_backend_consumes_lowered_generic_immediate_without_context() -> None:
    generic = _generic("Index", PrimitiveGenericParameterKind.INT, 0)
    operand = LoweredSelectedGenericImmediateParameter(
        argument_index=1,
        parameter=generic,
        source_text="Index",
        source=_location(1, 31),
    )
    field = _immediate_modifier_field(value=operand, immediate_index=None)

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.diagnostics == ()
    assert result.modifier is not None
    assert result.modifier.value == BackendIntrinsicImmediateGenericParameterReference(
        argument_index=1,
        parameter=generic,
        source_text="Index",
        source=operand.source,
    )


def test_m210_array_tsl_indexed_generic_immediate_occurrence_is_accepted() -> None:
    path = _REPO_ROOT / "tsldata" / "primitives" / "load_store" / "array.tsl"
    text = path.read_text(encoding="utf-8")
    generic = _generic(
        "Index",
        PrimitiveGenericParameterKind.INT,
        0,
        source=SourceLocation(path, 171, 5),
    )
    selected = _selected(
        signature_text="s:=v[idx]",
        parameter_names=("a",),
        generic_parameters=(generic,),
    )

    snippets = tuple(
        (snippet, source)
        for snippet, source in _intrin_compose_snippets(path, text)
        if "immediate(1)=Index" in snippet
    )

    assert len(snippets) == 1
    request = _single_compose_request(snippets[0][0], selected, source=snippets[0][1])
    field = _immediate_field(request)

    assert isinstance(field.value, LoweredSelectedGenericImmediateParameter)
    assert field.value.parameter.name == "Index"
    translation = translate_backend_intrinsic_modifier_field(field, "cpp")
    assert translation.diagnostics == ()
    assert translation.modifier is not None
    assert isinstance(
        translation.modifier.value,
        BackendIntrinsicImmediateGenericParameterReference,
    )


@pytest.mark.parametrize(
    ("generic_specs", "signature_text", "symbol"),
    (
        ((), "s:=v[idx]", "Index"),
        (
            (("Index", PrimitiveGenericParameterKind.BOOL, True),),
            "s:=v[idx]",
            "Index",
        ),
        (
            (("IndicesType", PrimitiveGenericParameterKind.SIMD_TYPE, None),),
            "s:=v[idx]",
            "IndicesType",
        ),
        (
            (("N", PrimitiveGenericParameterKind.INT, 1),),
            "v:=(ptr,vidx,sImm)",
            "N",
        ),
    ),
)
def test_m210_non_matching_generic_immediate_symbols_remain_unsupported(
    generic_specs: tuple[tuple[str, PrimitiveGenericParameterKind, int | bool | None], ...],
    signature_text: str,
    symbol: str,
) -> None:
    generic_parameters = tuple(
        _generic(name, kind, default) for name, kind, default in generic_specs
    )
    parameter_names = (
        ("a",)
        if signature_text == "s:=v[idx]"
        else ("base_ptr", "index", "scale")
    )
    request = _single_compose_request(
        f"intrin_compose<vgetq_lane immediate(1)={symbol}>(a, {symbol})",
        _selected(
            signature_text=signature_text,
            parameter_names=parameter_names,
            generic_parameters=generic_parameters,
        ),
    )
    field = _immediate_field(request)

    assert isinstance(field.value, BackendIntrinsicModifierSymbolOperand)
    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
    )


def test_m210_raw_backend_symbol_index_remains_unsupported() -> None:
    field = _immediate_modifier_field(
        value=BackendIntrinsicModifierSymbolOperand(
            text="Index",
            source=_location(1, 31),
        ),
        immediate_index=1,
    )

    result = translate_backend_intrinsic_modifier_field(field, "cpp")

    assert result.modifier is None
    assert _codes(result.diagnostics) == (
        "TSL-BACKEND-INTRINSIC-MODIFIER-UNSUPPORTED-IMMEDIATE",
    )


def test_m210_preserves_m208_signature_parameter_immediate_path() -> None:
    generic = _generic("index", PrimitiveGenericParameterKind.INT, 0)
    request = _single_compose_request(
        "intrin_compose<extracti128 immediate(1)=index>(data, index)",
        _selected(
            signature_text="v:=(v,sImm)",
            parameter_names=("data", "index"),
            generic_parameters=(generic,),
        ),
    )
    field = _immediate_field(request)

    assert isinstance(field.value, LoweredSelectedSignatureImmediateParameter)
    assert field.value.parameter.name == "index"
    assert field.value.parameter.term.kind is SignatureTermKind.SCALAR_IMMEDIATE


def test_m210_catalog_rejects_unsupported_generic_kind() -> None:
    catalog_result = CatalogBuilder().build(
        (
            _parsed_with_generic_params(
                (ParsedGenericParameter("Index", "float", "0", _location(2, 5)),)
            ),
        )
    )

    assert catalog_result.catalog is None
    assert _codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-UNSUPPORTED-GENERIC-PARAMETER-KIND",
    )


@pytest.mark.parametrize(
    ("name", "kind", "default"),
    (
        ("Index", "int", "zero"),
        ("PreserveSign", "bool", "maybe"),
        ("IndicesType", "simd_type", "Vec"),
    ),
)
def test_m210_catalog_rejects_unsupported_generic_defaults(
    name: str,
    kind: str,
    default: str,
) -> None:
    parsed = ParsedGenericParameter(name, kind, default, _location(2, 5))
    catalog_result = CatalogBuilder().build((_parsed_with_generic_params((parsed,)),))

    assert catalog_result.catalog is None
    assert _codes(catalog_result.diagnostics) == (
        "TSL-CATALOG-UNSUPPORTED-GENERIC-PARAMETER-DEFAULT",
    )


def test_m210_parser_reports_malformed_generic_param_shape(tmp_path: Path) -> None:
    source = _source_document(
        tmp_path,
        "bad_generic_params.tsl",
        """prim<v:=(v,v)> fixture(left, right):
  generic_params:
    Index {kind int default 0}
  implementation scalar si32:
    body fixture(left, right)
""",
    )

    parse_result = TslParser().parse((source,))

    assert parse_result.documents == ()
    assert _codes(parse_result.diagnostics) == (
        "TSL-PARSE-UNSUPPORTED-GENERIC-PARAMETER",
    )


def _selected(
    *,
    signature_text: str,
    parameter_names: tuple[str, ...],
    generic_parameters: tuple[PrimitiveGenericParameter, ...] = (),
) -> SelectedImplementation:
    source = _location()
    signature = _signature(signature_text)
    bindings = signature_parameter_terms(signature, parameter_names, source)
    assert bindings.diagnostics == ()
    implementation = Implementation(
        extension="neon",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
    )
    primitive = Primitive(
        name="fixture",
        signature=signature.source_text,
        parameters=parameter_names,
        template="unknown",
        implementations=(implementation,),
        source=source,
        signature_model=signature,
        parameter_signature_terms=bindings.bindings,
        generic_parameters=generic_parameters,
    )
    target = Target(
        backend="cpp",
        primitive_name="fixture",
        extension="neon",
        type_tag="si32",
    )
    return SelectedImplementation(
        target=target,
        primitive=primitive,
        implementation=implementation,
    )


def _signature(text: str) -> PrimitiveSignature:
    result = parse_primitive_signature(text, _location())
    assert result.diagnostics == ()
    assert result.signature is not None
    return result.signature


def _generic(
    name: str,
    kind: PrimitiveGenericParameterKind,
    default: int | bool | None,
    *,
    source: SourceLocation | None = None,
) -> PrimitiveGenericParameter:
    return PrimitiveGenericParameter(
        name=name,
        kind=kind,
        default=default,
        source=source or _location(),
    )


def _single_compose_request(
    text: str,
    selected: SelectedImplementation,
    *,
    source: SourceLocation | None = None,
) -> BackendIntrinsicComposeHandoffRequest:
    lowerer = Lowerer()
    discovery = discover_backend_intrinsic_requests_in_text(
        text,
        source or _location(),
    )
    assert discovery.diagnostics == ()
    assert discovery.discovery is not None
    environment = lowerer.type_environment_for(selected)
    result = lowerer.lower_backend_intrinsic_discovery(
        selected,
        discovery.discovery,
        environment=environment,
    )
    assert result.diagnostics == ()
    assert result.handoff is not None
    assert len(result.handoff.segments) == 1
    segment = result.handoff.segments[0]
    assert isinstance(segment, BackendIntrinsicHandoffRequestSegment)
    assert isinstance(segment.request, BackendIntrinsicComposeHandoffRequest)
    return segment.request


def _immediate_field(
    request: BackendIntrinsicComposeHandoffRequest,
) -> BackendIntrinsicModifierField:
    matches = tuple(field for field in request.modifiers if field.name == "immediate")
    assert len(matches) == 1
    return matches[0]


def _immediate_modifier_field(
    *,
    value,
    immediate_index: int | None,
) -> BackendIntrinsicModifierField:
    key_index = "missing" if immediate_index is None else str(immediate_index)
    return BackendIntrinsicModifierField(
        name="immediate",
        key_text=f"immediate({key_index})",
        value=value,
        source_text=f"immediate({key_index})=value",
        source=_location(1, 1),
        key_source=_location(1, 1),
        value_source=_location(1, 31),
        immediate_index=immediate_index,
        immediate_index_text=None if immediate_index is None else str(immediate_index),
    )


def _parsed_with_generic_params(
    generic_parameters: tuple[ParsedGenericParameter, ...],
) -> ParsedDocument:
    return ParsedDocument(
        path="fixture.tsl",
        primitives=(
            ParsedPrimitive(
                name="fixture",
                signature="v:=(v,v)",
                parameters=("left", "right"),
                implementations=(
                    ParsedImplementation(
                        extension="scalar",
                        type_tag="si32",
                        body=ParsedImplementationBody(
                            lines=(
                                ParsedRawStringLine(
                                    text="emit_return(left);",
                                    source=_location(3, 5),
                                ),
                            ),
                            source=_location(3, 5),
                            envelope=PARSED_TSIL_BODY_ENVELOPE,
                        ),
                        source=_location(2, 3),
                    ),
                ),
                source=_location(),
                generic_parameters=generic_parameters,
            ),
        ),
    )


def _intrin_compose_snippets(
    path: Path,
    text: str,
) -> tuple[tuple[str, SourceLocation], ...]:
    snippets: list[tuple[str, SourceLocation]] = []
    position = 0
    head = "intrin_compose"
    while True:
        start = text.find(f"{head}<", position)
        if start == -1:
            break

        angle_open = start + len(head)
        angle_close = matching_delimiter_close(text, angle_open, "<", ">")
        if angle_close is None:
            position = start + 1
            continue

        args_open = _skip_whitespace(text, angle_close + 1)
        if args_open >= len(text) or text[args_open] != "(":
            position = start + 1
            continue

        args_close = matching_delimiter_close(text, args_open, "(", ")")
        if args_close is None:
            position = start + 1
            continue

        snippets.append((text[start : args_close + 1], _source_at(path, text, start)))
        position = start + 1

    return tuple(snippets)


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    return SourceDocument(
        path=tmp_path / name,
        text=text,
        digest="fixture",
        kind="tsl",
    )


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _source_at(path: Path, text: str, offset: int) -> SourceLocation:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    column = len(prefix.rsplit("\n", 1)[-1]) + 1
    return SourceLocation(path, line, column)


def _codes(diagnostics) -> tuple[str, ...]:
    return tuple(diagnostic.code for diagnostic in diagnostics)


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
