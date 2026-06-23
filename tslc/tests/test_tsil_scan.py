"""The scanner segments bodies into raw text and recursive keyword regions."""

from __future__ import annotations

from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.ir.segments import RawText, Region


def test_raw_text_passes_through() -> None:
    segments = scan("emit_return(left + right);")
    assert isinstance(segments[0], Region)
    assert segments[0].keyword == "emit_return"
    assert segments[0].body == (RawText("left + right"),)
    assert segments[0].has_statement_terminator
    assert len(segments) == 1


def test_intrin_compose_selector_is_raw_and_args_recurse() -> None:
    segments = scan("emit_return(intrin_compose<add>(left, right));")
    emit = segments[0]
    assert isinstance(emit, Region)
    assert emit.has_statement_terminator
    compose = emit.body[0]
    assert isinstance(compose, Region)
    assert compose.keyword == "intrin_compose"
    assert compose.selector_text == "add"
    assert compose.body == (RawText("left, right"),)
    assert not compose.has_statement_terminator


def test_expression_statement_consumes_source_terminator() -> None:
    segments = scan("call<primitive=store>(ptr, value);")

    assert len(segments) == 1
    call = segments[0]
    assert isinstance(call, Region)
    assert call.keyword == "call"
    assert call.has_statement_terminator


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


def test_scan_carries_nested_source_spans() -> None:
    body = "  emit_return(\n    intrin_compose<add>(left, right)\n  );"
    source = SourceSpan(Path("body.tsl"), 10, 5, 12, 7)

    segments = scan(body, source=source)
    assert segments[0] == RawText(
        "  ",
        source=SourceSpan(Path("body.tsl"), 10, 5, 10, 7),
    )
    emit = segments[1]
    assert isinstance(emit, Region)
    assert emit.source == SourceSpan(Path("body.tsl"), 10, 7, 12, 4)
    assert emit.has_statement_terminator

    compose = next(segment for segment in emit.body if isinstance(segment, Region))
    assert compose.keyword == "intrin_compose"
    assert compose.source == SourceSpan(Path("body.tsl"), 11, 5, 11, 37)


def _joined(segments) -> str:
    return "".join(
        s.full_text if isinstance(s, Region) else s.text for s in segments
    ).strip()


def test_if_generation_captures_branch_blocks() -> None:
    body = "if<generation>(type::is_same(type<generation>(base::in), ui8)) { a = 1; } else<generation> { a = 2; }"
    region = scan(body)[0]
    assert isinstance(region, Region)
    assert region.keyword == "if"
    assert region.selector_text == "generation"
    # condition is the (...) payload; the {...} blocks are captured separately
    assert "type::is_same" in _joined(region.body)
    assert _joined(region.block) == "a = 1;"
    assert region.else_block is not None and _joined(region.else_block) == "a = 2;"


def test_if_generation_without_else() -> None:
    region = scan("if<generation>(cond) { x = 1; }")[0]
    assert isinstance(region, Region) and region.keyword == "if"
    assert _joined(region.block) == "x = 1;"
    assert region.else_block is None


def test_if_generation_else_if_chain_nests() -> None:
    body = "if<generation>(a) { x = 1; } else<generation> { if<generation>(b) { x = 2; } else<generation> { x = 3; } }"
    region = scan(body)[0]
    assert region.keyword == "if"
    assert _joined(region.block) == "x = 1;"
    # the else branch is a block containing the nested if (which renders recursively)
    assert region.else_block is not None
    nested = next(s for s in region.else_block if isinstance(s, Region) and s.keyword == "if")
    assert _joined(nested.block) == "x = 2;"
    assert nested.else_block is not None and _joined(nested.else_block) == "x = 3;"


def test_if_generation_bare_else_if_is_single_region() -> None:
    # the brace-less `else<gen> if<gen>...` form yields a one-element else_block.
    region = scan("if<generation>(a) { x = 1; } else<generation> if<generation>(b) { x = 2; }")[0]
    assert region.else_block is not None and len(region.else_block) == 1
    nested = region.else_block[0]
    assert isinstance(nested, Region) and nested.keyword == "if"
    assert _joined(nested.block) == "x = 2;"
