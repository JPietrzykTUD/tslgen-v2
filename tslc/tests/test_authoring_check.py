"""Public authoring checks, overlays, caching, and ranged output."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from tslc.authoring import (
    ParsedDocumentCache,
    SourceOverlay,
    apply_overlays,
    check_catalog,
)
from tslc.diagnostics import (
    Diagnostic,
    RelatedLocation,
    SourceSpan,
    format_diagnostic,
    format_diagnostics_json,
)
from tslc.sources import SourceDocument


def _document(path: Path, text: str) -> SourceDocument:
    return SourceDocument(
        path=path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def test_parsed_document_cache_reuses_unchanged_documents(tmp_path: Path) -> None:
    first = _document(tmp_path / "a.tsl", 'description "a"\n')
    second = _document(tmp_path / "b.tsl", 'description "b"\n')
    cache = ParsedDocumentCache()

    parsed = cache.parse((second, first))
    assert parsed.diagnostics == ()
    assert cache.last_reparsed == (first.path.resolve(), second.path.resolve())

    cache.parse((first, second))
    assert cache.last_reparsed == ()

    changed = _document(first.path, 'description "changed"\n')
    cache.parse((changed, second))
    assert cache.last_reparsed == (first.path.resolve(),)


def test_parsed_document_cache_retains_failed_parse(tmp_path: Path) -> None:
    malformed = _document(tmp_path / "bad.tsl", "not valid !!!\n")
    cache = ParsedDocumentCache()

    first = cache.parse((malformed,))
    second = cache.parse((malformed,))

    assert first.diagnostics
    assert second.diagnostics == first.diagnostics
    assert cache.last_reparsed == ()


def test_undecodable_string_escape_reaches_authoring_as_a_diagnostic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad_escape.tsl"
    path.write_text(
        'extension broken:\n  extension_name "bad \\x escape"\n  family "x86"\n',
        encoding="utf-8",
    )

    result = check_catalog((path,))

    assert "TSL-OUTER-PARSE-BAD-STRING" in [d.code for d in result.diagnostics]


def test_overlays_replace_disk_text_without_writing(tmp_path: Path) -> None:
    path = tmp_path / "value.tsl"
    path.write_text('description "disk"\n', encoding="utf-8")
    disk = _document(path, path.read_text(encoding="utf-8"))

    documents, diagnostics = apply_overlays(
        (disk,), (SourceOverlay(path.parent / "." / path.name, 'description "memory"\n', 4),)
    )

    assert diagnostics == ()
    assert documents[0].text == 'description "memory"\n'
    assert path.read_text(encoding="utf-8") == 'description "disk"\n'


def test_duplicate_normalized_overlays_are_diagnosed(tmp_path: Path) -> None:
    path = tmp_path / "value.tsl"
    _, diagnostics = apply_overlays(
        (),
        (
            SourceOverlay(path, "one"),
            SourceOverlay(path.parent / "." / path.name, "two"),
        ),
    )

    assert [item.code for item in diagnostics] == ["TSL-AUTHORING-DUPLICATE-PATH"]


def test_diagnostic_json_uses_zero_based_full_ranges(tmp_path: Path) -> None:
    source = SourceSpan(tmp_path / "a.tsl", 2, 3, 2, 8)
    related = SourceSpan(tmp_path / "b.tsl", 4, 2, 4, 5)
    diagnostic = Diagnostic(
        "error",
        "TSL-TEST",
        "bad value",
        span=source,
        related=(RelatedLocation("declared here", related),),
        help="choose a known value",
    )

    payload = json.loads(format_diagnostics_json((diagnostic,)))

    assert payload["schema_version"] == 1
    assert payload["diagnostics"][0]["range"] == {
        "start": {"line": 1, "character": 2},
        "end": {"line": 1, "character": 7},
    }
    assert payload["diagnostics"][0]["related"][0]["range"]["start"] == {
        "line": 3,
        "character": 1,
    }
    assert "help: choose a known value" in format_diagnostic(diagnostic)


def test_catalog_index_contains_typed_call_references(data_root: Path) -> None:
    result = check_catalog((data_root,))

    assert result.catalog is not None
    assert result.index is not None
    assert result.index.primitive_definitions["add"]
    assert any(result.index.primitive_references.values())
    assert result.index.extension_definitions["avx2"]
    assert result.index.type_group_definitions["arith"]
