from hashlib import sha256
from pathlib import Path

import pytest

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.domain.catalog import Catalog, LowerableDirective, PrimitiveCall
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    LoweredPrimitiveCallExpression,
    Lowerer,
    PrimitiveCallClosureLoweringPackage,
)
from tslgen.lowering.primitive_calls import PrimitiveCallResolver
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser

ROOT = Path(__file__).resolve().parents[2]
TYPES_TSL = ROOT / "tsldata" / "detail" / "types.tsl"
EXTENSIONS_TSL = ROOT / "tsldata" / "extensions" / "extension.tsl"


def test_primitive_call_expression_lowers_recognized_call_token(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "call<primitive=sub[Vec]>(right, left)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = PrimitiveCallResolver(catalog).lower_expression(
        selected,
        _single_body_call(selected),
    )

    assert result.diagnostics == ()
    assert result.expression is not None
    assert _expression_target_name(result.expression) == "sub"
    assert _expression_binding_summary(result.expression) == (
        ("left", "right"),
        ("right", "left"),
    )


def test_emit_return_primitive_call_consumes_reusable_expression(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left, right));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.diagnostics == ()
    assert result.function is not None
    expression = result.function.body.return_statement.expression
    assert isinstance(expression, LoweredPrimitiveCallExpression)
    assert _expression_target_name(expression) == "sub"
    assert _expression_binding_summary(expression) == (
        ("left", "left"),
        ("right", "right"),
    )


def test_emit_return_primitive_call_preserves_raw_argument_text(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        (
            "emit_return(call<primitive=sub[Vec]>("
            "right, call<primitive=neg[Vec]>(value)));"
        ),
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.diagnostics == ()
    assert result.function is not None
    expression = result.function.body.return_statement.expression
    assert isinstance(expression, LoweredPrimitiveCallExpression)
    assert _expression_binding_summary(expression) == (
        ("left", "right"),
        ("right", "call<primitive=neg[Vec]>(value)"),
    )


def test_closure_package_includes_root_function_with_emit_return_call(
    tmp_path: Path,
) -> None:
    package = _selected_package(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left, right));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    assert package.diagnostics == ()
    assert _lowered_function_names(package) == ("add", "sub")
    root_expression = package.lowered_functions.functions[0].body.return_statement.expression
    assert isinstance(root_expression, LoweredPrimitiveCallExpression)
    assert _expression_target_name(root_expression) == "sub"


def test_emit_return_primitive_call_reports_reference_diagnostics(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "emit_return(call<primitive=missing[Vec]>(left, right));",
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-SELECT-UNKNOWN-PRIMITIVE",
    ]


def test_emit_return_primitive_call_reports_argument_count_diagnostics(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "emit_return(call<primitive=sub[Vec]>(left));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-PRIMITIVE-CALL-ARGUMENT-COUNT-MISMATCH",
    ]


def test_standalone_call_body_stays_outside_expression_consumer(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "call<primitive=sub[Vec]>(left, right)",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
    ]


@pytest.mark.parametrize(
    ("body_payload", "expected_code"),
    (
        (
            "var<infer>(result, call<primitive=sub[Vec]>(left, right))",
            "TSL-LOWER-UNSUPPORTED-BODY",
        ),
        (
            "let<value>(result, call<primitive=sub[Vec]>(left, right))",
            "TSL-LOWER-UNSUPPORTED-BODY",
        ),
        (
            "result = call<primitive=sub[Vec]>(left, right);",
            "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
        ),
        (
            "loop<size>(i, call<primitive=sub[Vec]>(left, right), lanes) {",
            "TSL-LOWER-UNSUPPORTED-BODY",
        ),
        (
            "if<runtime>(call<primitive=sub[Vec]>(left, right)) {",
            "TSL-LOWER-UNSUPPORTED-BODY",
        ),
    ),
)
def test_unselected_context_payload_calls_stay_outside_expression_consumer(
    tmp_path: Path,
    body_payload: str,
    expected_code: str,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        body_payload,
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [expected_code]


def test_mixed_emit_return_payload_stays_unsupported(
    tmp_path: Path,
) -> None:
    catalog, selected = _selected_root(
        tmp_path,
        "emit_return(prefix call<primitive=sub[Vec]>(left, right));",
        extra_primitives=(_primitive_source("sub", "sub"),),
    )

    result = Lowerer().lower(selected, catalog=catalog)

    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION",
    ]


def _selected_package(
    tmp_path: Path,
    root_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> PrimitiveCallClosureLoweringPackage:
    catalog, selected = _selected_root(
        tmp_path,
        root_payload,
        extra_primitives=extra_primitives,
    )
    return Lowerer().lower_primitive_call_closure_lowering_package(
        selected,
        catalog=catalog,
    )


def _selected_root(
    tmp_path: Path,
    root_payload: str,
    *,
    extra_primitives: tuple[str, ...] = (),
) -> tuple[Catalog, SelectedImplementation]:
    root_source = _source_document(
        tmp_path,
        "current_add.tsl",
        _primitive_source("add", "add", body_payload=root_payload),
    )
    documents = [
        _document(TYPES_TSL),
        _document(EXTENSIONS_TSL),
        root_source,
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
    return catalog_result.catalog, selection.selected[0]


def _primitive_source(
    name: str,
    operation: str,
    *,
    body_payload: str | None = None,
) -> str:
    if body_payload is None:
        body_lines = (f"    body {operation}(left, right)",)
    else:
        body_lines = (
            '    tsil """',
            *(f"      {line}" for line in body_payload.splitlines()),
            '    """',
        )
    return "\n".join(
        (
            f"prim<v:=(v,v)> {name}(left, right):",
            "  implementation scalar si32:",
            *body_lines,
        )
    )


def _single_body_call(selected: SelectedImplementation) -> PrimitiveCall:
    for token in selected.implementation.body.tokens:
        if isinstance(token, LowerableDirective) and token.primitive_call is not None:
            return token.primitive_call
    raise AssertionError("expected one primitive call token")


def _expression_target_name(expression: LoweredPrimitiveCallExpression) -> str:
    return expression.reference.target_match.selected.primitive.name


def _expression_binding_summary(
    expression: LoweredPrimitiveCallExpression,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (binding.parameter_name, binding.argument.text)
        for binding in expression.reference.bindings
    )


def _lowered_function_names(
    package: PrimitiveCallClosureLoweringPackage,
) -> tuple[str, ...]:
    return tuple(
        function.signature.primitive_name
        for function in package.lowered_functions.functions
    )


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
