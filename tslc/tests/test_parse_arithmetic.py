"""The parser recovers primitive signatures and TSIL body envelopes."""

from __future__ import annotations

from pathlib import Path

from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser


def _parse(path: Path):
    documents = SourceLoader().load((path,))
    assert documents.diagnostics == ()
    result = TslParser().parse(documents.documents)
    assert result.diagnostics == ()
    return result.documents[0]


def test_parses_unmasked_add_signature(fundamental_path: Path) -> None:
    document = _parse(fundamental_path)
    add = next(
        primitive
        for primitive in document.primitives
        if primitive.name == "add" and not primitive.attributes
    )
    assert add.signature == "v:=(v,v)"
    assert add.parameters == ("left", "right")


def test_body_envelopes_carry_selector_paths(fundamental_path: Path) -> None:
    document = _parse(fundamental_path)
    add = next(
        primitive
        for primitive in document.primitives
        if primitive.name == "add" and not primitive.attributes
    )
    by_path = {env.selector_path: env.payload_text for env in add.body_envelopes}
    assert by_path[("scalar", "arith")].strip() == "emit_return(op<add>(left, right));"
    avx2_int = by_path[("avx2", "?i?")]
    assert "intrin<add, build[" in avx2_int
    assert "suffix=value<backend>(intrin::suffix(" in avx2_int
    assert by_path[("avx2", "f?")].strip() == "emit_return(intrin<add, build>(left, right));"
