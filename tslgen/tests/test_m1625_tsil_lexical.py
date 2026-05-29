from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import LowerableDirective, RawStringToken
from tslgen.lowering.type_syntax import TypeCall, TypeQuery, parse_type_syntax
from tslgen.pipeline._tsil_directives import classify_tsil_directive_line
from tslgen.pipeline._tsil_primitive_calls import classify_tsil_primitive_call_tokens
from tslgen.syntax.ast import ParsedRawStringLine
from tslgen.syntax.tsil_lexical import (
    ANGLE_DELIMITER,
    BRACE_DELIMITER,
    BRACKET_DELIMITER,
    PAREN_DELIMITER,
    find_top_level_char,
    matching_close,
    raw_brace_depth_after,
    split_top_level_parts,
)


def test_m1625_matching_close_handles_nested_delimiters() -> None:
    text = "emit_return(call<primitive=add>(left, helper(right)));"

    close_index = matching_close(text, len("emit_return"), PAREN_DELIMITER)

    assert close_index == text.rindex(")")
    assert matching_close(text, len("emit_return") + 1, PAREN_DELIMITER) is None
    braced = "{ inner { body(); } }"
    assert matching_close(braced, 0, BRACE_DELIMITER) == len(braced) - 1


def test_m1625_split_top_level_parts_preserves_trimmed_offsets() -> None:
    payload = (
        "left, call<primitive=set_zero[Vec]>(), "
        "type<generation>(base::signed_of(type<generation>(base::in)))"
    )

    parts = split_top_level_parts(
        payload,
        delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER, ANGLE_DELIMITER),
        allow_empty_payload=False,
    )

    assert parts is not None
    assert tuple(part.text for part in parts) == (
        "left",
        "call<primitive=set_zero[Vec]>()",
        "type<generation>(base::signed_of(type<generation>(base::in)))",
    )
    assert parts[1].start == payload.index("call")
    assert parts[2].start == payload.index("type<generation>")


def test_m1625_split_top_level_parts_rejects_malformed_balance() -> None:
    assert split_top_level_parts("left,, right") is None
    assert split_top_level_parts("left, helper(right") is None
    assert (
        split_top_level_parts(
            "left, Vec<si32], right",
            delimiters=(PAREN_DELIMITER, BRACKET_DELIMITER, ANGLE_DELIMITER),
        )
        is None
    )


def test_m1625_find_top_level_char_respects_nested_selector_payload() -> None:
    selector = "@self[type<backend>(vector::as_extension(scalar))]>"

    assert (
        find_top_level_char(
            selector,
            ">",
            start=0,
            delimiters=(BRACKET_DELIMITER,),
        )
        == len(selector) - 1
    )
    assert (
        find_top_level_char(
            "@self] >",
            ">",
            start=0,
            delimiters=(BRACKET_DELIMITER,),
        )
        is None
    )


def test_m1625_raw_brace_depth_can_preserve_m162_top_level_clamping() -> None:
    assert raw_brace_depth_after(0, "{ nested { body(); }") == 1
    assert raw_brace_depth_after(0, "} loose close", clamp_underflow=True) == 0


def test_m1625_directive_classification_keeps_nested_generation_payload() -> None:
    source = SourceLocation(Path("fixture.tsl"), 7, 5)
    line = ParsedRawStringLine(
        text=(
            "if<generation>(value<generation>(type::is_same("
            "type<generation>(base::in), si32))) { body(); }"
        ),
        source=source,
    )

    tokens = classify_tsil_directive_line(line)

    assert tokens is not None
    assert isinstance(tokens[0], LowerableDirective)
    assert tokens[0].name == "if"
    assert tokens[0].arguments == (
        "generation",
        (
            "value<generation>(type::is_same("
            "type<generation>(base::in), si32))"
        ),
    )
    assert tuple(token.text for token in tokens[1:]) == (" {", " body(); ", "}")


def test_m1625_primitive_call_classifier_keeps_nested_argument_boundaries() -> None:
    source = SourceLocation(Path("fixture.tsl"), 9, 3)
    text = (
        "prefix call<primitive=mov[Vec] attrs[mask=pass_through]>"
        "(call<primitive=set_zero[Vec]>(), left) suffix"
    )

    tokens = classify_tsil_primitive_call_tokens(
        (RawStringToken(text=text, source=source),)
    )

    assert len(tokens) == 3
    call = tokens[1]
    assert isinstance(call, LowerableDirective)
    assert call.arguments == (
        "primitive",
        "mov[Vec] attrs[mask=pass_through]",
        "call<primitive=set_zero[Vec]>(), left",
    )
    assert call.primitive_call is not None
    assert tuple(argument.text for argument in call.primitive_call.arguments) == (
        "call<primitive=set_zero[Vec]>()",
        "left",
    )


def test_m1625_type_syntax_uses_shared_nested_call_splitting() -> None:
    parsed = parse_type_syntax(
        "value<generation>(arith<generation>::mul("
        "type::size_bytes(type<generation>(base::in)), 8))"
    )

    assert isinstance(parsed, TypeQuery)
    assert isinstance(parsed.expression, TypeCall)
    assert parsed.expression.name == "arith<generation>::mul"
    assert tuple(argument.source_text for argument in parsed.expression.arguments) == (
        "type::size_bytes(type<generation>(base::in))",
        "8",
    )
