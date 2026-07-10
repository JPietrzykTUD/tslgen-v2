"""The scanner segments bodies into raw text and recursive keyword regions."""

from __future__ import annotations

from pathlib import Path

from tslc.catalog.validation.body_validation import _SHELL_VALIDATORS
from tslc.diagnostics import SourceSpan
from tslc.ir.region_registry import (
    DEFAULT_TSIL_REGION_DESCRIPTORS,
    TSIL_REGION_KEYWORDS,
    region_shell_validator,
)
from tslc.ir.scan import KEYWORDS, scan
from tslc.ir.segments import RawText, Region
from tslc.lower.region_handlers.registry import (
    DEFAULT_REGION_LOWERERS,
    REGION_LOWERING_REGISTRATIONS,
)


def test_region_descriptor_registry_drives_scanning_and_lowering() -> None:
    descriptor_keywords = tuple(
        descriptor.keyword for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS
    )
    lowerer_keywords = {lowerer.keyword for lowerer in DEFAULT_REGION_LOWERERS}
    registration_keywords = {
        registration.keyword for registration in REGION_LOWERING_REGISTRATIONS
    }

    assert len(descriptor_keywords) == len(set(descriptor_keywords))
    assert len(REGION_LOWERING_REGISTRATIONS) == len(registration_keywords)
    assert KEYWORDS == TSIL_REGION_KEYWORDS
    assert registration_keywords == TSIL_REGION_KEYWORDS
    assert lowerer_keywords == TSIL_REGION_KEYWORDS
    assert region_shell_validator("call") == "call_selector"
    assert region_shell_validator("mask") == "mask_selector"
    assert region_shell_validator("var") == "var_selector"
    assert region_shell_validator("type") == "no_selector"
    assert region_shell_validator("value") == "no_selector"
    assert region_shell_validator("complete") is None
    declared_validators = {
        descriptor.shell_validator
        for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS
        if descriptor.shell_validator is not None
    }
    assert declared_validators <= frozenset(_SHELL_VALIDATORS)


def test_raw_text_passes_through() -> None:
    segments = scan("complete(left + right);")
    assert isinstance(segments[0], Region)
    assert segments[0].keyword == "complete"
    assert segments[0].body == (RawText("left + right"),)
    assert segments[0].has_statement_terminator
    assert len(segments) == 1


def test_intrin_build_selector_is_raw_and_args_recurse() -> None:
    segments = scan("complete(intrin<add, build>(left, right));")
    emit = segments[0]
    assert isinstance(emit, Region)
    assert emit.has_statement_terminator
    intrinsic = emit.body[0]
    assert isinstance(intrinsic, Region)
    assert intrinsic.keyword == "intrin"
    assert intrinsic.selector_text == "add, build"
    assert intrinsic.body == (RawText("left, right"),)
    assert not intrinsic.has_statement_terminator


def test_select_expr_arguments_recurse() -> None:
    segments = scan(
        "complete(select_expr("
        "a == b, cast<static>(si32, 1), call<primitive=zero[Vec]>()"
        "));"
    )
    emit = segments[0]
    assert isinstance(emit, Region)
    select = emit.body[0]
    assert isinstance(select, Region)
    assert select.keyword == "select_expr"
    assert select.selector_text == ""
    assert any(
        isinstance(segment, Region) and segment.keyword == "cast"
        for segment in select.body
    )
    assert any(
        isinstance(segment, Region) and segment.keyword == "call"
        for segment in select.body
    )


def test_removed_pack_keyword_stays_raw_text() -> None:
    segments = scan("complete(pack<first>(value));")

    complete = segments[0]
    assert isinstance(complete, Region)
    assert "pack" not in TSIL_REGION_KEYWORDS
    assert complete.body == (RawText("pack<first>(value)"),)


def test_expression_statement_consumes_source_terminator() -> None:
    segments = scan("call<primitive=store>(ptr, value);")

    assert len(segments) == 1
    call = segments[0]
    assert isinstance(call, Region)
    assert call.keyword == "call"
    assert call.has_statement_terminator


def test_nested_modifier_selector_kept_verbatim() -> None:
    body = (
        "complete(intrin<add, build["
        "suffix=base::signed_of(base::in)]>(left, right));"
    )
    intrinsic = scan(body)[0].body[0]
    assert isinstance(intrinsic, Region)
    # The whole selector (including nested generation-time queries) is preserved as text;
    # the lowerer parses modifiers, the scanner does not.
    assert intrinsic.keyword == "intrin"
    assert intrinsic.selector_text.startswith("add, build[suffix=base::signed_of(")
    assert "base::in" in intrinsic.selector_text


def test_keyword_inside_identifier_is_not_matched() -> None:
    segments = scan("my_call_value = 1;")
    assert segments == (RawText("my_call_value = 1;"),)


def test_keyword_inside_string_is_not_matched() -> None:
    segments = scan('a = "call<primitive=x>(y)";')
    assert segments == (RawText('a = "call<primitive=x>(y)";'),)


def test_scan_carries_nested_source_spans() -> None:
    body = "  complete(\n    intrin<add, build>(left, right)\n  );"
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

    intrinsic = next(segment for segment in emit.body if isinstance(segment, Region))
    assert intrinsic.keyword == "intrin"
    assert intrinsic.source == SourceSpan(Path("body.tsl"), 11, 5, 11, 36)


def _joined(segments) -> str:
    return "".join(
        s.full_text if isinstance(s, Region) else s.text for s in segments
    ).strip()


def test_if_generation_captures_branch_blocks() -> None:
    body = "if<generation>(type::is_same(type(base::in), ui8)) { a = 1; } else<generation> { a = 2; }"
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


def test_backend_loop_unroll_selector_captures_block() -> None:
    region = scan("loop<backend, unroll>(i, 0, 4, 1) { x = i; }")[0]
    assert isinstance(region, Region)
    assert region.keyword == "loop"
    assert region.selector_text == "backend, unroll"
    assert _joined(region.body) == "i, 0, 4, 1"
    assert _joined(region.block) == "x = i;"


def test_loop_without_block_keeps_optional_block_absent() -> None:
    region = scan("loop<backend>(i, 0, 4, 1)")[0]
    assert isinstance(region, Region)
    assert region.keyword == "loop"
    assert region.block is None


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
