from pathlib import Path

from tslgen.core.diagnostics import SourceLocation
from tslgen.domain.catalog import LowerableDirective, RawStringToken
from tslgen.lowering._source_islands import (
    OpaqueTokenBuffer,
    RawStringRunBuffer,
    matching_delimiter_close,
    source_at_offset,
    source_text_from_raw_tokens,
)


def test_m178_matching_delimiter_close_is_quote_and_escape_aware() -> None:
    text = 'call("not ) close", nested("escaped \\" ) still quoted"), value)'

    assert matching_delimiter_close(text, text.index("("), "(", ")") == len(text) - 1

    angle_text = 'intrin_compose<name, suffix=value<backend>("x>y")>(data)'

    assert matching_delimiter_close(angle_text, len("intrin_compose"), "<", ">") == (
        angle_text.rindex(">(")
    )


def test_m178_source_at_offset_preserves_one_based_line_columns() -> None:
    source = _location(line=10, column=4)
    text = "ab\ncd"

    assert source_at_offset(source, text, 0) == _location(line=10, column=4)
    assert source_at_offset(source, text, 2) == _location(line=10, column=6)
    assert source_at_offset(source, text, 3) == _location(line=11, column=1)
    assert source_at_offset(source, text, len(text)) == _location(
        line=11,
        column=3,
    )


def test_m178_raw_string_run_join_keeps_per_character_source_mapping() -> None:
    first = _raw("aa", line=2, column=5)
    second = _raw("b\nc", line=10, column=3)

    source_text = source_text_from_raw_tokens((first, second))

    assert source_text.text == "aab\nc"
    assert source_text.source == first.source
    assert source_text.source_at(0) == _location(line=2, column=5)
    assert source_text.source_at(1) == _location(line=2, column=6)
    assert source_text.source_at(2) == _location(line=10, column=3)
    assert source_text.source_at(3) == _location(line=10, column=4)
    assert source_text.source_at(4) == _location(line=11, column=1)
    assert source_text.span(2, 5).text == "b\nc"
    assert source_text.span(2, 5).source == _location(line=10, column=3)


def test_m178_run_and_opaque_buffers_preserve_token_identity_and_order() -> None:
    first = _raw("prefix ", line=1, column=1)
    second = _raw("request", line=2, column=7)
    directive = LowerableDirective(
        name="var",
        arguments=("infer", "tmp, hidden"),
        source=_location(line=3, column=11),
    )

    raw_buffer = RawStringRunBuffer()
    raw_buffer.append(first)
    raw_buffer.append(second)
    raw_run = raw_buffer.take()

    assert raw_run is not None
    assert raw_run.tokens == (first, second)
    assert raw_run.source_text.text == "prefix request"
    assert raw_buffer.take() is None

    opaque_buffer = OpaqueTokenBuffer()
    opaque_buffer.append(first)
    opaque_buffer.append(directive)
    opaque_span = opaque_buffer.take()

    assert opaque_span is not None
    assert opaque_span.tokens == (first, directive)
    assert opaque_span.source == first.source
    assert opaque_buffer.take() is None


def _raw(
    text: str,
    *,
    line: int = 1,
    column: int = 1,
) -> RawStringToken:
    return RawStringToken(text=text, source=_location(line=line, column=column))


def _location(line: int = 1, column: int = 1) -> SourceLocation:
    return SourceLocation(Path("fixture.tsl"), line, column)
