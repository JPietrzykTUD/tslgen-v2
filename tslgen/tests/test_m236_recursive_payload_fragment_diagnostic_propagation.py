from __future__ import annotations

from dataclasses import is_dataclass
from hashlib import sha256
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.lowering.source_body_fragments import (
    PayloadTokenFragmentSequenceResult,
    lower_source_body_fragments,
    payload_token_result_from_fragment_sequence,
)
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.syntax.parser import TslParser
from tslgen.syntax.source_body_regions import SourceBodyText


def test_m236_payload_token_result_is_frozen_slotted_dataclass() -> None:
    assert is_dataclass(PayloadTokenFragmentSequenceResult)
    assert PayloadTokenFragmentSequenceResult.__dataclass_params__.frozen
    assert "__dict__" not in PayloadTokenFragmentSequenceResult.__slots__


def test_m236_payload_token_result_carries_call_fragment_diagnostics() -> None:
    result = _lower("emit_return(call<target=sub>(left, right));")
    emit_return = result.sequence.keyword_fragments[0]
    assert emit_return.payload_fragments is not None

    payload_result = payload_token_result_from_fragment_sequence(
        emit_return.payload_fragments,
    )

    assert result.diagnostics == ()
    assert [diagnostic.code for diagnostic in payload_result.diagnostics] == [
        "TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED"
    ]
    assert "expected selector to start with 'primitive='" in (
        payload_result.diagnostics[0].message
    )
    assert payload_result.diagnostics[0].location is not None
    assert payload_result.diagnostics[0].location.path == Path("fixture.tsl")


def test_m236_catalog_surfaces_malformed_emit_return_call_payload(
    tmp_path: Path,
) -> None:
    source = _source_document(
        tmp_path,
        "current_add.tsl",
        "\n".join(
            (
                "prim<v:=(v,v)> add(left, right):",
                "  implementation scalar si32:",
                '    tsil """',
                "      emit_return(call<target=sub>(left, right));",
                '    """',
            )
        ),
    )
    parse_result = TslParser().parse((source,))
    assert parse_result.diagnostics == ()

    catalog_result = CatalogBuilder().build(parse_result.documents)

    assert catalog_result.catalog is None
    assert [diagnostic.code for diagnostic in catalog_result.diagnostics] == [
        "TSL-LOWER-PRIMITIVE-CALL-FRAGMENT-MALFORMED"
    ]
    diagnostic = catalog_result.diagnostics[0]
    assert diagnostic.location is not None
    assert diagnostic.location.path == source.path
    assert "expected selector to start with 'primitive='" in diagnostic.message


def _lower(text: str):
    return lower_source_body_fragments(
        SourceBodyText(
            path=Path("fixture.tsl"),
            line=1,
            column=1,
            text=text,
        )
    )


def _source_document(tmp_path: Path, name: str, text: str) -> SourceDocument:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )
