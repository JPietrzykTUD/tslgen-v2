from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import Catalog, LowerableDirective, PrimitiveCall
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    Lowerer,
    PrimitiveCallArgumentBinding,
    PrimitiveCallSelectorPayload,
    PrimitiveCallTargetMatch,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_argument_binding_binds_self_call_positionally(tmp_path: Path) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=@self[Vec]>(right, left)",
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert result.reference.target_match is match
    assert result.reference.primitive_call is call
    assert _bound_pairs(result.reference.bindings) == (
        ("left", "right"),
        ("right", "left"),
    )


def test_argument_binding_uses_matched_named_primitive_parameters(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub[Vec]>(rhs, lhs)",
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )
    # The current parser admits only the tiny left/right clean header shape.
    # M146 is a lowering boundary, so prove the typed target drives binding.
    renamed_primitive = replace(
        match.selected.primitive,
        parameters=("minuend", "subtrahend"),
    )
    match = replace(
        match,
        selected=replace(match.selected, primitive=renamed_primitive),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert result.reference.target_match.selected.primitive.name == "sub"
    assert _bound_pairs(result.reference.bindings) == (
        ("minuend", "rhs"),
        ("subtrahend", "lhs"),
    )


def test_argument_binding_binds_naked_named_call_as_current_vector(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub>(rhs, lhs)",
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert _bound_pairs(result.reference.bindings) == (
        ("left", "rhs"),
        ("right", "lhs"),
    )


def test_argument_binding_preserves_attrs_only_call_arguments(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub attrs[mask=zero]>(value, value)",
        extra_primitives=(
            _primitive_source("sub", "sub", attributes="[mask=zero]"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert _bound_pairs(result.reference.bindings) == (
        ("left", "value"),
        ("right", "value"),
    )


def test_argument_binding_preserves_specialization_plus_attrs_arguments(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=load[Vec] attrs[aligned=false]>(ptr[i], mask)",
        extra_primitives=(
            _primitive_source("load", "add", attributes="[aligned=*]"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert _bound_pairs(result.reference.bindings) == (
        ("left", "ptr[i]"),
        ("right", "mask"),
    )


def test_argument_binding_keeps_nested_call_argument_raw(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        (
            "call<primitive=sub[Vec]>("
            "call<primitive=neg[Vec]>(value), left)"
        ),
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.diagnostics == ()
    assert result.reference is not None
    assert _bound_pairs(result.reference.bindings) == (
        ("left", "call<primitive=neg[Vec]>(value)"),
        ("right", "left"),
    )


def test_argument_binding_reports_too_few_arguments(tmp_path: Path) -> None:
    catalog, source, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub[Vec]>(left)",
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.reference is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH"
    assert diagnostic.location == call.source
    assert diagnostic.location == SourceLocation(source, 4, 7)
    assert "expects 2 argument(s)" in diagnostic.message
    assert "got 1 argument(s)" in diagnostic.message


def test_argument_binding_reports_too_many_arguments(tmp_path: Path) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right, carry)",
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.reference is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH"
    assert diagnostic.location == call.source
    assert "expects 2 argument(s)" in diagnostic.message
    assert "got 3 argument(s)" in diagnostic.message


def test_argument_binding_reports_no_arguments_for_required_parameters(
    tmp_path: Path,
) -> None:
    catalog, _, selected, call, payload, match = _selected_match(
        tmp_path,
        "call<primitive=sub[Vec]>()",
        extra_primitives=(
            _primitive_source("sub", "sub"),
        ),
    )

    result = Lowerer().lower_primitive_call_argument_bindings(
        call,
        match,
    )

    assert result.reference is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH"
    assert diagnostic.location == call.source
    assert "expects 2 argument(s)" in diagnostic.message
    assert "got 0 argument(s)" in diagnostic.message


def _selected_match(
    tmp_path: Path,
    call_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[
    Catalog,
    Path,
    SelectedImplementation,
    PrimitiveCall,
    PrimitiveCallSelectorPayload,
    PrimitiveCallTargetMatch,
]:
    current_source = _source_document(
        tmp_path,
        "current_add.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                *(f"      {line}" for line in call_payload.splitlines()),
                '    """',
            )
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
                f"target_{index}.tsl",
                primitive_source,
            )
        )

    parse_result = TslParser().parse(tuple(documents))
    assert parse_result.diagnostics == ()
    catalog_result = CatalogBuilder().build(parse_result.documents)
    assert catalog_result.diagnostics == ()
    assert catalog_result.catalog is not None

    selection = Selector().select(
        catalog_result.catalog,
        Target(
            backend="cpp",
            primitive_name="add",
            extension="scalar",
            type_tag="si32",
        ),
    )
    assert selection.diagnostics == ()
    assert len(selection.selected) == 1
    selected = selection.selected[0]

    call = _single_primitive_call(selected)
    payload_result = Lowerer().lower_primitive_call_selector_payload(
        selected,
        call,
        catalog=catalog_result.catalog,
    )
    assert payload_result.diagnostics == ()
    assert payload_result.payload is not None

    match_result = Lowerer().lower_primitive_call_target_match(
        selected,
        payload_result.payload,
        catalog=catalog_result.catalog,
    )
    assert match_result.diagnostics == ()
    assert match_result.match is not None

    return (
        catalog_result.catalog,
        current_source.path,
        selected,
        call,
        payload_result.payload,
        match_result.match,
    )


def _primitive_source(
    name: str,
    operation: str,
    *,
    attributes: str = "",
) -> str:
    return "\n".join(
        (
            f"prim<v:=(v,v)>{attributes} {name}(left, right):",
            "  implementation scalar si32:",
            f"    body {operation}(left, right)",
        )
    )


def _bound_pairs(
    bindings: tuple[PrimitiveCallArgumentBinding, ...],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (binding.parameter_name, binding.argument.text) for binding in bindings
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
