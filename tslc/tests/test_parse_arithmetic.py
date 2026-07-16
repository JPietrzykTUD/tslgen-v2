"""The parser recovers primitive signatures and TSIL body envelopes."""

from __future__ import annotations

from pathlib import Path

from tslc.sources import SourceDocument, SourceLoader
from tslc.syntax.parser import TslParser, _line_column, _line_starts


def _linear_line_column(text: str, offset: int) -> tuple[int, int]:
    line = 1
    column = 1
    for character in text[:offset]:
        if character == "\n":
            line += 1
            column = 1
        else:
            column += 1
    return line, column


def test_binary_line_lookup_matches_linear_oracle_at_every_offset() -> None:
    for text in ("", "one line", "one\ntwo", "one\ntwo\n", "αβ\nγδ\n"):
        starts = _line_starts(text)
        for offset in range(len(text) + 1):
            assert _line_column(starts, offset) == _linear_line_column(text, offset)


def _parse(path: Path, grammar: str):
    documents = SourceLoader().load((path,))
    assert documents.diagnostics == ()
    result = TslParser(grammar).parse(documents.documents)
    assert result.diagnostics == ()
    return result.documents[0]


def test_parses_unmasked_add_signature(fundamental_path: Path, tsl_grammar: str) -> None:
    document = _parse(fundamental_path, tsl_grammar)
    add = next(
        primitive
        for primitive in document.primitives
        if primitive.name == "add" and not primitive.attributes
    )
    assert add.signature == "v:=(v,v)"
    assert add.parameters == ("left", "right")


def test_body_envelopes_carry_selector_paths(
    fundamental_path: Path, tsl_grammar: str
) -> None:
    document = _parse(fundamental_path, tsl_grammar)
    add = next(
        primitive
        for primitive in document.primitives
        if primitive.name == "add" and not primitive.attributes
    )
    by_path = {env.selector_path: env.payload_text for env in add.body_envelopes}
    assert by_path[("scalar", "arith")].strip() == "complete(op<add>(left, right));"
    avx2_int = by_path[("avx2", "?i?")]
    assert "intrin<add, build[" in avx2_int
    assert "suffix=base::signed_of(base::in)" in avx2_int
    assert by_path[("avx2", "f?")].strip() == "complete(intrin<add, build>(left, right));"


def test_inline_tsil_body_envelope_uses_decoded_string_payload(
    tmp_path: Path, tsl_grammar: str
) -> None:
    path = tmp_path / "escaped.tsl"
    text = (
        'prim<v:=v> escaped(data):\n'
        '  impls:\n'
        '    scalar:\n'
        '      arith:\n'
        '        implementation:\n'
        '          tsil "complete(intrin<foo, build[infix_sep=\\"\\"]>(data));"\n'
    )
    document = SourceDocument(path=path, text=text, digest="", kind="tsl")

    result = TslParser(tsl_grammar).parse((document,))

    assert result.diagnostics == ()
    envelope = result.documents[0].primitives[0].body_envelopes[0]
    assert envelope.payload_text == 'complete(intrin<foo, build[infix_sep=""]>(data));'
    assert envelope.payload_source.text == 'complete(intrin<foo, build[infix_sep=\\"\\"]>(data));'


def test_undecodable_string_escape_is_a_located_diagnostic(
    tmp_path: Path, tsl_grammar: str
) -> None:
    path = tmp_path / "bad_escape.tsl"
    text = 'extension broken:\n  extension_name "bad \\x escape"\n'
    document = SourceDocument(path=path, text=text, digest="", kind="tsl")

    result = TslParser(tsl_grammar).parse((document,))

    assert result.documents == ()
    (diagnostic,) = result.diagnostics
    assert diagnostic.severity == "error"
    assert diagnostic.code == "TSL-OUTER-PARSE-BAD-STRING"
    assert diagnostic.span is not None
    assert diagnostic.span.path == path
    assert diagnostic.span.line == 2
    assert diagnostic.span.column == text.splitlines()[1].index('"') + 1


def test_undecodable_string_in_one_document_keeps_other_documents_parsed(
    tmp_path: Path, tsl_grammar: str
) -> None:
    bad_path = tmp_path / "a_bad.tsl"
    good_path = tmp_path / "b_good.tsl"
    bad = SourceDocument(
        path=bad_path,
        text='extension broken:\n  extension_name "bad \\x escape"\n',
        digest="",
        kind="tsl",
    )
    good = SourceDocument(
        path=good_path,
        text='extension fine:\n  extension_name "fine"\n',
        digest="",
        kind="tsl",
    )

    result = TslParser(tsl_grammar).parse((bad, good))

    assert [doc.path for doc in result.documents] == [good_path]
    assert [d.code for d in result.diagnostics] == ["TSL-OUTER-PARSE-BAD-STRING"]
