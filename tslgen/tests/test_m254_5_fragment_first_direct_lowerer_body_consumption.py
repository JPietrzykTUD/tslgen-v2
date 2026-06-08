from __future__ import annotations

from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Target
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    LowerableOperationFragment,
    Primitive,
)
from tslgen.lowering import (
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredUnaryOperationExpression,
    Lowerer,
)
from tslgen.syntax.source_body_fragments import (
    SourceBodyFragmentSequence,
    fragment_source_body_text,
)
from tslgen.syntax.source_body_regions import SourceBodyText


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "tslgen" / "src" / "tslgen"


def test_m254_5_fragment_backed_emit_return_add_call_lowers_with_empty_tokens() -> None:
    selected = _selected_with_fragment_text(
        "add",
        "binary",
        ("left", "right"),
        "emit_return(call<primitive=add>(left, right));",
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.body.tokens == ()
    assert result.diagnostics == ()
    assert result.function is not None
    expression = result.function.body.return_statement.expression
    assert isinstance(expression, LoweredBinaryOperationExpression)
    assert expression.operation.operation_id == "add"


def test_m254_5_fragment_backed_unsupported_return_expression_diagnostic() -> None:
    selected = _selected_with_fragment_text(
        "add",
        "binary",
        ("left", "right"),
        "emit_return(left);",
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.body.tokens == ()
    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION",
    ]
    assert "left" in result.diagnostics[0].message
    assert result.diagnostics[0].location == _location()


def test_m254_5_fragment_backed_primitive_call_diagnostic() -> None:
    selected = _selected_with_fragment_text(
        "add",
        "binary",
        ("left", "right"),
        "emit_return(call<primitive=sub>(left, right));",
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.body.tokens == ()
    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
    ]
    assert "target name is 'sub'" in result.diagnostics[0].message


def test_m254_5_fragment_backed_plain_body_keeps_unsupported_body_boundary() -> None:
    selected = _selected_with_fragment_text(
        "add",
        "binary",
        ("left", "right"),
        "plain_target_language();",
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.body.tokens == ()
    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-BODY",
    ]
    assert "expected exactly one lowerable operation token" in result.diagnostics[0].message
    assert result.diagnostics[0].location == _location()


def test_m254_5_token_only_operation_fallback_remains_available() -> None:
    unary = Lowerer().lower(
        _selected_with_tokens(
            "neg",
            "unary",
            ("value",),
            (
                LowerableOperationFragment(
                    operation="neg",
                    arguments=("value",),
                    source=_location(),
                ),
            ),
        )
    )
    comparison = Lowerer().lower(
        _selected_with_tokens(
            "equal",
            "compare",
            ("left", "right"),
            (
                LowerableOperationFragment(
                    operation="equal",
                    arguments=("left", "right"),
                    source=_location(),
                ),
            ),
        )
    )

    assert unary.diagnostics == ()
    assert unary.function is not None
    assert isinstance(
        unary.function.body.return_statement.expression,
        LoweredUnaryOperationExpression,
    )
    assert comparison.diagnostics == ()
    assert comparison.function is not None
    assert isinstance(
        comparison.function.body.return_statement.expression,
        LoweredComparisonOperationExpression,
    )


def test_m254_5_token_only_primitive_call_diagnostic_fallback_remains_available() -> None:
    selected = _selected_with_tokens(
        "add",
        "binary",
        ("left", "right"),
        (
            LowerableDirective(
                name="call",
                arguments=("primitive", "sub", "left, right"),
                source=_location(),
            ),
        ),
    )

    result = Lowerer().lower(selected)

    assert selected.implementation.source_body_fragments is None
    assert result.function is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL",
    ]
    assert "selector remains opaque: 'sub'" in result.diagnostics[0].message


def test_m254_5_direct_lowerer_guardrails() -> None:
    lowerer_text = (SRC / "lowering" / "lowerer.py").read_text(encoding="utf-8")
    primitive_calls_text = (
        SRC / "lowering" / "primitive_calls.py"
    ).read_text(encoding="utf-8")
    module_text = "\n".join((lowerer_text, primitive_calls_text))

    assert "_SelectedBodyTokenView" in lowerer_text
    assert "compatibility_body_token_result_from_fragment_sequence" in lowerer_text
    assert "unsupported_primitive_call_diagnostics_from_body_tokens" in lowerer_text
    assert "unsupported_primitive_call_diagnostics(\n            body" not in lowerer_text

    forbidden = (
        "emit_return +",
        "call +",
        "real_scalar_pipeline",
        "real_avx2_pipeline",
        "SourceBodyLexicalRegionScanner(",
        "frozen.",
        "tslgenold",
    )
    assert not any(text in module_text for text in forbidden)


def _selected_with_fragment_text(
    primitive_name: str,
    template: str,
    parameters: tuple[str, ...],
    text: str,
) -> SelectedImplementation:
    result = fragment_source_body_text(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=1,
            column=1,
            text=text,
        )
    )
    assert result.diagnostics == ()
    return _selected_with_fragments(
        primitive_name,
        template,
        parameters,
        result.sequence,
    )


def _selected_with_fragments(
    primitive_name: str,
    template: str,
    parameters: tuple[str, ...],
    sequence: SourceBodyFragmentSequence,
) -> SelectedImplementation:
    source = sequence.source_text.source_at(0)
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=ImplementationBody(tokens=(), source=source),
        source=source,
        source_body_fragments=sequence,
    )
    return _selected_with_implementation(
        primitive_name,
        template,
        parameters,
        implementation,
    )


def _selected_with_tokens(
    primitive_name: str,
    template: str,
    parameters: tuple[str, ...],
    tokens: tuple[BodyToken, ...],
) -> SelectedImplementation:
    source = _location()
    implementation = Implementation(
        extension="scalar",
        type_tag="si32",
        body=ImplementationBody(tokens=tokens, source=source),
        source=source,
    )
    return _selected_with_implementation(
        primitive_name,
        template,
        parameters,
        implementation,
    )


def _selected_with_implementation(
    primitive_name: str,
    template: str,
    parameters: tuple[str, ...],
    implementation: Implementation,
) -> SelectedImplementation:
    primitive = Primitive(
        name=primitive_name,
        signature="fixture",
        parameters=parameters,
        template=template,
        implementations=(implementation,),
        source=implementation.source,
    )
    return SelectedImplementation(
        target=Target(
            backend="cpp",
            primitive_name=primitive_name,
            extension=implementation.extension,
            type_tag=implementation.type_tag,
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
