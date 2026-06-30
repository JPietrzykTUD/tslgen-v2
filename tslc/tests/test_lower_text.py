"""Shared TSIL lowering text helpers."""

from __future__ import annotations

from tslc.lower._text import split_selector_terms


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
