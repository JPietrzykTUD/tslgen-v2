from pathlib import Path

from tslgen.analysis.selection import (
    SelectedImplementation,
    Target,
    TargetAttribute,
)
from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Implementation,
    ImplementationBody,
    LowerableDirective,
    Primitive,
    PrimitiveAttribute,
    RawStringToken,
)
from tslgen.lowering import (
    LoweredGenerationControlBranch,
    LoweredGenerationValue,
    Lowerer,
)

_SOURCE = Path("m186.tsl")
_BASE_SIZE = "type::size_bytes(type<generation>(base::in))"
_BASE_SIGNED = "type::is_signed(type<generation>(base::in))"
_IS_SI32 = "type::is_same(type<generation>(base::in), scalar::si32)"
_IS_UI32 = "type::is_same(type<generation>(base::in), scalar::ui32)"


def test_m186_lowers_bare_boolean_generation_predicates() -> None:
    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                _IS_SI32,
                true_tokens=_tokens("same_path();", line=5),
                false_tokens=_tokens("other_path();", line=8),
            ),
            type_tag="si32",
        ),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition == LoweredGenerationValue(
        kind="type.is_same",
        value=True,
        source_text=_IS_SI32,
        source=_location(4, 7),
    )
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=_tokens("same_path();", line=5),
        source=_location(5, 9),
    )


def test_m186_lowers_boolean_operators_with_precedence_and_parentheses() -> None:
    true_without_grouping = f"{_IS_UI32} || {_IS_SI32} && {_BASE_SIGNED}"
    false_with_grouping = f"({_IS_UI32} || {_IS_SI32}) && {_BASE_SIGNED}"

    ungrouped = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                true_without_grouping,
                true_tokens=_tokens("selected_path();", line=5),
                false_tokens=_tokens("fallback_path();", line=8),
            ),
            type_tag="ui32",
        ),
    )
    grouped = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                false_with_grouping,
                true_tokens=_tokens("selected_path();", line=5),
                false_tokens=_tokens("fallback_path();", line=8),
            ),
            type_tag="ui32",
        ),
    )

    assert ungrouped.diagnostics == ()
    assert grouped.diagnostics == ()
    assert ungrouped.region is not None
    assert grouped.region is not None
    assert ungrouped.region.condition == LoweredGenerationValue(
        kind="generation.boolean_condition",
        value=True,
        source_text=true_without_grouping,
        source=_location(4, 7),
    )
    assert grouped.region.condition == LoweredGenerationValue(
        kind="generation.boolean_condition",
        value=False,
        source_text=false_with_grouping,
        source=_location(4, 7),
    )
    assert ungrouped.region.selected_branch == LoweredGenerationControlBranch(
        tokens=_tokens("selected_path();", line=5),
        source=_location(5, 9),
    )
    assert grouped.region.selected_branch == LoweredGenerationControlBranch(
        tokens=_tokens("fallback_path();", line=8),
        source=_location(8, 9),
    )


def test_m186_lowers_not_and_primitive_attribute_conditions() -> None:
    condition = "!primitive::attribute(aligned)"
    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                condition,
                true_tokens=_tokens("unaligned_path();", line=5),
                false_tokens=_tokens("aligned_path();", line=8),
            ),
            attributes=(
                PrimitiveAttribute(
                    key="aligned",
                    value="false",
                    declared_value="*",
                    source=_location(1, 16),
                ),
            ),
        ),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition == LoweredGenerationValue(
        kind="generation.boolean_condition",
        value=True,
        source_text=condition,
        source=_location(4, 7),
    )
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=_tokens("unaligned_path();", line=5),
        source=_location(5, 9),
    )


def test_m186_lowers_bare_integer_generation_expression_comparisons() -> None:
    condition = (
        f"{_BASE_SIZE} == 4 && "
        f"arith<generation>::mul({_BASE_SIZE}, 8) == 32"
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                condition,
                true_tokens=_tokens("four_byte_path();", line=5),
                false_tokens=_tokens("other_path();", line=8),
            ),
            type_tag="ui32",
        ),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition == LoweredGenerationValue(
        kind="generation.boolean_condition",
        value=True,
        source_text=condition,
        source=_location(4, 7),
    )
    assert result.region.selected_branch == LoweredGenerationControlBranch(
        tokens=_tokens("four_byte_path();", line=5),
        source=_location(5, 9),
    )


def test_m186_preserves_value_query_integer_comparisons() -> None:
    condition = (
        "value<generation>(arith<generation>::mul("
        "type::size_bytes(type<generation>(base::in)), 8)) >= 32"
    )

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                condition,
                true_tokens=_tokens("wide_path();", line=5),
                false_tokens=_tokens("narrow_path();", line=8),
            ),
            type_tag="ui32",
        ),
    )

    assert result.diagnostics == ()
    assert result.region is not None
    assert result.region.condition == LoweredGenerationValue(
        kind="generation.integer_comparison",
        value=True,
        source_text=condition,
        source=_location(4, 7),
    )


def test_m186_reports_malformed_and_unsupported_condition_text() -> None:
    lowerer = Lowerer()

    trailing_operator = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                f"{_IS_SI32} &&",
                true_tokens=_tokens("true_path();", line=5),
                false_tokens=_tokens("false_path();", line=8),
            ),
        ),
    )
    missing_group_close = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                f"({_IS_SI32} || {_IS_UI32}",
                true_tokens=_tokens("true_path();", line=5),
                false_tokens=_tokens("false_path();", line=8),
            ),
        ),
    )
    raw_arithmetic = lowerer.lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                f"{_BASE_SIZE} + 1",
                true_tokens=_tokens("true_path();", line=5),
                false_tokens=_tokens("false_path();", line=8),
            ),
        ),
    )

    assert [diagnostic.code for diagnostic in trailing_operator.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.code for diagnostic in missing_group_close.diagnostics] == [
        "TSL-LOWER-MALFORMED-GENERATION-CONTROL-CONDITION",
    ]
    assert [diagnostic.code for diagnostic in raw_arithmetic.diagnostics] == [
        "TSL-LOWER-UNSUPPORTED-GENERATION-CONTROL-CONDITION",
    ]
    assert "raw arithmetic operator text" in raw_arithmetic.diagnostics[0].message


def test_m186_reports_later_operand_diagnostics_without_short_circuiting() -> None:
    condition = f"{_IS_SI32} || arith<generation>::div(8, 0) == 1"

    result = Lowerer().lower_generation_control_region(
        _selected_implementation(
            body=_generation_if_body(
                condition,
                true_tokens=_tokens("true_path();", line=5),
                false_tokens=_tokens("false_path();", line=8),
            ),
            type_tag="si32",
        ),
    )

    assert result.region is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "TSL-LOWER-ZERO-DIVISOR-GENERATION-ARITHMETIC",
    ]


def test_m186_condition_lowering_is_deterministic() -> None:
    condition = f"!({_IS_UI32} || {_BASE_SIZE} != 4)"
    body = _generation_if_body(
        condition,
        true_tokens=_tokens("true_path();", line=5),
        false_tokens=_tokens("false_path();", line=8),
    )
    malformed_body = _generation_if_body(
        f"{_BASE_SIZE} == 4 == 4",
        true_tokens=_tokens("true_path();", line=5),
        false_tokens=_tokens("false_path();", line=8),
    )
    lowerer = Lowerer()

    first_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body, type_tag="si32"),
    )
    second_region = lowerer.lower_generation_control_region(
        _selected_implementation(body=body, type_tag="si32"),
    )
    first_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed_body, type_tag="ui32"),
    )
    second_diagnostics = lowerer.lower_generation_control_region(
        _selected_implementation(body=malformed_body, type_tag="ui32"),
    )

    assert first_region == second_region
    assert first_diagnostics == second_diagnostics


def _selected_implementation(
    *,
    body: ImplementationBody,
    backend: str = "cpp",
    extension: str = "scalar",
    type_tag: str = "si32",
    attributes: tuple[PrimitiveAttribute, ...] = (),
) -> SelectedImplementation:
    implementation = Implementation(
        extension=extension,
        type_tag=type_tag,
        body=body,
        source=_location(2, 3),
    )
    primitive = Primitive(
        name="add",
        signature="v:=(v,v)",
        parameters=("left", "right"),
        template="binary",
        implementations=(implementation,),
        source=_location(1, 1),
        attributes=attributes,
    )
    return SelectedImplementation(
        target=Target(
            backend=backend,
            primitive_name="add",
            extension=extension,
            type_tag=type_tag,
            attributes=tuple(
                TargetAttribute(key=attribute.key, value=attribute.value)
                for attribute in attributes
            ),
        ),
        primitive=primitive,
        implementation=implementation,
    )


def _generation_if_body(
    condition: str,
    *,
    true_tokens: tuple[BodyToken, ...],
    false_tokens: tuple[BodyToken, ...],
) -> ImplementationBody:
    if_text = f"if<generation>({condition})"
    return ImplementationBody(
        tokens=(
            LowerableDirective(
                name="if",
                arguments=("generation", condition),
                source=_location(4, 7),
            ),
            RawStringToken(
                text=" {",
                source=_location(4, 7 + len(if_text)),
            ),
            *true_tokens,
            RawStringToken(text="} ", source=_location(7, 7)),
            LowerableDirective(
                name="else",
                arguments=("generation",),
                source=_location(7, 9),
            ),
            RawStringToken(text=" {", source=_location(7, 25)),
            *false_tokens,
            RawStringToken(text="}", source=_location(10, 7)),
        ),
        source=_location(3, 5),
    )


def _tokens(text: str, *, line: int) -> tuple[RawStringToken, ...]:
    return (RawStringToken(text=text, source=_location(line, 9)),)


def _location(line: int, column: int) -> SourceLocation:
    return SourceLocation(path=_SOURCE, line=line, column=column)
