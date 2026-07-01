"""The parser recovers primitive signatures and TSIL body envelopes."""

from __future__ import annotations

from pathlib import Path

from tslc.sources import SourceDocument, SourceLoader
from tslc.syntax.parser import TslParser


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
