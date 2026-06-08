"""The scanner segments bodies into raw text and recursive keyword regions."""

from __future__ import annotations

from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region


def test_raw_text_passes_through() -> None:
    segments = scan("emit_return(left + right);")
    assert isinstance(segments[0], Region)
    assert segments[0].keyword == "emit_return"
    assert segments[0].body == (RawText("left + right"),)
    assert segments[1] == RawText(";")


def test_intrin_compose_selector_is_raw_and_args_recurse() -> None:
    segments = scan("emit_return(intrin_compose<add>(left, right));")
    emit = segments[0]
    assert isinstance(emit, Region)
    compose = emit.body[0]
    assert isinstance(compose, Region)
    assert compose.keyword == "intrin_compose"
    assert compose.selector_text == "add"
    assert compose.body == (RawText("left, right"),)


def test_nested_modifier_selector_kept_verbatim() -> None:
    body = (
        "emit_return(intrin_compose<add, "
        "suffix=value<backend>(intrin::suffix(type<generation>(base::in)))>(left, right));"
    )
    compose = scan(body)[0].body[0]
    assert isinstance(compose, Region)
    # The whole selector (including nested value<...>/type<...>) is preserved as text;
    # the lowerer parses modifiers, the scanner does not.
    assert compose.selector_text.startswith("add, suffix=value<backend>(")
    assert "type<generation>(base::in)" in compose.selector_text


def test_keyword_inside_identifier_is_not_matched() -> None:
    segments = scan("my_call_value = 1;")
    assert segments == (RawText("my_call_value = 1;"),)


def test_keyword_inside_string_is_not_matched() -> None:
    segments = scan('a = "call<primitive=x>(y)";')
    assert segments == (RawText('a = "call<primitive=x>(y)";'),)
