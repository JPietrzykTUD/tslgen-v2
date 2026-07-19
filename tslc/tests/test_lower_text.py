"""Shared TSIL lowering text helpers."""

from __future__ import annotations

from tslc.ir.scan import scan
from tslc.ir.region_syntax import (
    ConditionAnd,
    ConditionLeaf,
    ConditionOr,
    GenericParamReference,
    LoopSelector,
    parse_condition,
    parse_generic_param_reference,
    parse_loop_selector,
    split_arg_groups,
)
from tslc.ir.text import split_selector_terms
from tslc.lower.raw_text import render_raw_text
from tslc.target_text import render_text


def test_raw_target_text_is_verbatim() -> None:
    source = '// Alias\n"Alias" + \'Alias\' + \'a + Alias'

    assert render_text(render_raw_text(source)) == source


def test_split_selector_terms_keeps_build_modifiers_together() -> None:
    assert split_selector_terms(
        'add, build[suffix=base::signed_of(base::in), immediate(2)=1]'
    ) == [
        "add",
        "build[suffix=base::signed_of(base::in), immediate(2)=1]",
    ]


def test_split_selector_terms_does_not_split_top_level_whitespace() -> None:
    assert split_selector_terms("foo build post=mask") == ["foo build post=mask"]


def test_split_selector_terms_respects_strings_and_nested_selectors() -> None:
    assert split_selector_terms(
        'foo, build[suffix=intrin::suffix("x,y"), '
        "infix=vector::as_base(base::in)]"
    ) == [
        "foo",
        'build[suffix=intrin::suffix("x,y"), infix=vector::as_base(base::in)]',
    ]


def test_split_arg_groups_respects_strings_and_nested_regions() -> None:
    region = scan(
        'select_expr(flag, helper<format>("x,y"), call<primitive=foo>(a, b))'
    )[0]

    assert len(split_arg_groups(region.body)) == 3


def test_split_arg_groups_does_not_treat_comparison_as_closing_angle() -> None:
    region = scan(
        "select_expr("
        "cast<static>(ShiftT, shift) >= cast<static>(ShiftT, value(type::size_bits(base::in))), "
        "cast<static>(ShiftT, 0), "
        "data << cast<static>(ShiftT, shift)"
        ")"
    )[0]

    assert len(split_arg_groups(region.body)) == 3


def test_parse_condition_builds_or_of_ands_with_opaque_leaves() -> None:
    term = parse_condition(
        "( value(type::is_signed(vector::imask)) ) && (!PreserveSign)"
        " || is_same(base::in, si64)"
    )

    assert term == ConditionOr(
        (
            ConditionAnd(
                (
                    ConditionLeaf("value(type::is_signed(vector::imask))"),
                    ConditionLeaf("!PreserveSign"),
                )
            ),
            ConditionLeaf("is_same(base::in, si64)"),
        )
    )


def test_parse_condition_strips_only_whole_expression_parens() -> None:
    assert parse_condition("(( a ))") == ConditionLeaf("a")
    assert parse_condition("( a ) && b") == ConditionAnd(
        (ConditionLeaf("a"), ConditionLeaf("b"))
    )
    # an operator inside a nested call is not a split point
    assert parse_condition('f("x || y", a)') == ConditionLeaf('f("x || y", a)')


def test_parse_generic_param_reference_accepts_only_exact_forms() -> None:
    names = ("PreserveSign",)

    assert parse_generic_param_reference("PreserveSign", names) == (
        GenericParamReference(name="PreserveSign", negated=False)
    )
    assert parse_generic_param_reference(" !PreserveSign ", names) == (
        GenericParamReference(name="PreserveSign", negated=True)
    )
    # mentioning a declared name is not referencing it
    assert parse_generic_param_reference("foo(PreserveSign)", names) is None
    assert parse_generic_param_reference("PreserveSign.bar", names) is None
    assert parse_generic_param_reference("! PreserveSign", names) is None
    assert parse_generic_param_reference("Other", names) is None


def test_parse_loop_selector_tokenizes_variant_and_modifiers_once() -> None:
    assert parse_loop_selector(" generation ,   scoped ") == LoopSelector(
        variant="generation", modifiers=("scoped",)
    )
    assert parse_loop_selector("backend, unroll") == LoopSelector(
        variant="backend", modifiers=("unroll",)
    )
    assert parse_loop_selector("generation") == LoopSelector(variant="generation")
    assert parse_loop_selector("   ") == LoopSelector(variant="")
