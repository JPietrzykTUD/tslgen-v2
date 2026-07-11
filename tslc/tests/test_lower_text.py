"""Shared TSIL lowering text helpers."""

from __future__ import annotations

from tslc.ir.scan import scan
from tslc.ir.region_syntax import split_arg_groups
from tslc.ir.text import split_selector_terms


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
