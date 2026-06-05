from __future__ import annotations

from dataclasses import is_dataclass
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from tslgen.io.sources import SourceDocument
from tslgen.lowering.corpus_completion import (
    CorpusLoweringCharacterization,
    CorpusLoweringFamilyCount,
    CorpusLoweringRepresentative,
    CorpusLoweringStatus,
    characterize_primitive_corpus_lowering,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TSLDATA_PRIMITIVES = _REPO_ROOT / "tsldata" / "primitives"
_HELPER_SOURCE = (
    _REPO_ROOT / "tslgen" / "src" / "tslgen" / "lowering" / "corpus_completion.py"
)

_EXPECTED_OBSERVED_COUNTS = {
    "array_type": ("accepted_handoff", 21),
    "assume_aligned": ("accepted_handoff", 20),
    "call<primitive>": ("accepted_lowering", 1796),
    "cast<bitcast>": ("accepted_handoff", 12),
    "cast<reinterpret>": ("accepted_handoff", 360),
    "cast<saturating>": ("accepted_handoff", 1),
    "cast<static>": ("accepted_handoff", 710),
    "else<compile>": ("accepted_handoff", 24),
    "else<generation>": ("accepted_lowering", 45),
    "emit_return": ("accepted_lowering", 1585),
    "generic::length": ("accepted_lowering", 75),
    "generic::runtime_length": ("accepted_lowering", 2),
    "if<compile>": ("accepted_handoff", 43),
    "if<generation>": ("accepted_lowering", 109),
    "intrin": ("accepted_handoff", 727),
    "intrin_compose": ("accepted_handoff", 627),
    "io<endl>": ("accepted_handoff", 2),
    "io<write>": ("accepted_handoff", 2),
    "io<write_base>": ("accepted_handoff", 8),
    "io<write_bin>": ("accepted_handoff", 2),
    "let<type>": ("accepted_lowering", 382),
    "loop<range>": ("accepted_lowering", 214),
    "loop<unroll>": ("accepted_lowering", 77),
    "mask<set:1>": ("accepted_handoff", 14),
    "mask<set>": ("accepted_handoff", 4),
    "mask<test>": ("accepted_handoff", 33),
    "mask<zero>": ("accepted_handoff", 20),
    "mask::lane::all_false": ("accepted_lowering", 12),
    "mask::lane::all_true": ("accepted_lowering", 30),
    "mem<alloc>": ("accepted_handoff", 1),
    "mem<alloc_aligned>": ("accepted_handoff", 1),
    "mem<copy>": ("accepted_handoff", 22),
    "mem<free>": ("accepted_handoff", 1),
    "pack": ("accepted_handoff", 1),
    "switch<compile>": ("accepted_handoff", 45),
    "type<backend>": ("accepted_handoff", 212),
    "type<generation>": ("accepted_lowering", 1783),
    "value<backend>": ("accepted_handoff", 336),
    "value<generation>": ("accepted_lowering", 597),
    "var<const_infer>": ("accepted_handoff", 595),
    "var<infer>": ("accepted_handoff", 179),
    "var<init_register>": ("accepted_handoff", 33),
    "var<typed>": ("accepted_handoff", 24),
}

_EXPECTED_RECURSIVE_COUNTS = {
    "call<primitive>": ("accepted_lowering", 1796),
    "else<generation>": ("accepted_lowering", 45),
    "emit_return": ("accepted_lowering", 1585),
    "if<generation>": ("accepted_lowering", 109),
    "intrin_compose": ("accepted_handoff", 627),
    "loop<range>": ("accepted_lowering", 214),
    "switch<compile>": ("accepted_handoff", 45),
}


def test_m242_public_values_are_frozen_slotted_dataclasses() -> None:
    classes = (
        CorpusLoweringCharacterization,
        CorpusLoweringFamilyCount,
        CorpusLoweringRepresentative,
    )

    for value_type in classes:
        assert is_dataclass(value_type)
        assert value_type.__dataclass_params__.frozen
        assert "__dict__" not in value_type.__slots__


def test_m242_real_primitive_corpus_lowering_gate_passes() -> None:
    result = _characterization()

    assert result.primitive_file_count == 30
    assert result.parsed_document_count == 30
    assert result.primitive_count == 140
    assert result.body_envelope_count == 1331
    assert result.diagnostics == ()
    assert result.unsupported_generation_relevant == ()
    assert result.is_complete_for_backend_rendering


def test_m242_observed_generation_relevant_families_are_classified() -> None:
    result = _characterization()

    assert _counts(result.observed_families) == _EXPECTED_OBSERVED_COUNTS
    assert _counts(result.validated_families) == _EXPECTED_OBSERVED_COUNTS
    assert {
        "emit_return",
        "intrin",
        "intrin_compose",
        "call<primitive>",
        "type<generation>",
        "type<backend>",
        "value<generation>",
        "value<backend>",
        "let<type>",
        "if<generation>",
        "else<generation>",
        "if<compile>",
        "else<compile>",
        "loop<range>",
        "loop<unroll>",
        "switch<compile>",
        "cast<static>",
        "cast<reinterpret>",
        "cast<bitcast>",
        "cast<saturating>",
        "mem<copy>",
        "io<write>",
        "mask<zero>",
        "mask::lane::all_true",
        "array_type",
        "assume_aligned",
        "pack",
        "generic::length",
    } <= set(_counts(result.observed_families))


def test_m242_recursive_keyword_lowering_covers_nested_real_intrin_compose() -> None:
    result = _characterization()

    assert _counts(result.recursive_keyword_families) == _EXPECTED_RECURSIVE_COUNTS
    assert _count_for(result.recursive_keyword_families, "intrin_compose") == (
        _count_for(result.observed_families, "intrin_compose")
    )
    assert _count_for(result.recursive_keyword_families, "call<primitive>") == (
        _count_for(result.observed_families, "call<primitive>")
    )

    representative = _representative(result, "intrin_compose")
    assert representative.source.path == (
        _TSLDATA_PRIMITIVES / "arithmetic" / "complex.tsl"
    ).resolve()
    assert representative.source.line == 47
    assert representative.source.column == 29
    assert representative.source_text == "intrin_compose<mul>(factor1, factor2)"


def test_m242_representatives_carry_real_source_provenance() -> None:
    result = _characterization()

    expected = {
        "emit_return": (
            "arithmetic/complex.tsl",
            28,
            17,
            "emit_return(details::arith_mul(factor1, factor2))",
        ),
        "call<primitive>": (
            "arithmetic/complex.tsl",
            39,
            27,
            "call<primitive=@self[type<backend>(vector::as_extension(scalar))]>"
            "(factor1[i], factor2[i])",
        ),
        "type<generation>": (
            "arithmetic/complex.tsl",
            58,
            54,
            "type<generation>(base::signed_of(type<generation>(base::in)))",
        ),
        "value<backend>": (
            "arithmetic/complex.tsl",
            58,
            24,
            "value<backend>(intrin::suffix(type<generation>"
            "(base::signed_of(type<generation>(base::in)))))",
        ),
        "cast<static>": (
            "arithmetic/complex.tsl",
            678,
            54,
            "cast<static>(type<generation>(base::in), factor)",
        ),
    }

    for family, (relative_path, line, column, source_text) in expected.items():
        representative = _representative(result, family)
        assert representative.source.path == (_TSLDATA_PRIMITIVES / relative_path).resolve()
        assert representative.source.line == line
        assert representative.source.column == column
        assert representative.source_text == source_text
        assert representative.status is not CorpusLoweringStatus.UNSUPPORTED_GENERATION_RELEVANT


def test_m242_corpus_gate_does_not_reopen_backend_or_legacy_boundaries() -> None:
    source = _HELPER_SOURCE.read_text(encoding="utf-8")

    forbidden_snippets = (
        "tslgen.rendering",
        "tslgen.backends",
        "ArtifactWriter",
        "BuildVerifier",
        "from frozen",
        "import frozen",
        "tslgenold",
        "EmitReturnIntrin",
        "ReturnPayloadIntrin",
    )

    assert not any(snippet in source for snippet in forbidden_snippets)


@lru_cache(maxsize=1)
def _characterization() -> CorpusLoweringCharacterization:
    return characterize_primitive_corpus_lowering(_all_primitive_documents())


def _all_primitive_documents() -> tuple[SourceDocument, ...]:
    return tuple(
        _source_document(path) for path in sorted(_TSLDATA_PRIMITIVES.rglob("*.tsl"))
    )


def _source_document(path: Path) -> SourceDocument:
    text = path.read_text(encoding="utf-8")
    return SourceDocument(
        path=path.resolve(),
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind="tsl",
    )


def _counts(
    counts: tuple[CorpusLoweringFamilyCount, ...],
) -> dict[str, tuple[str, int]]:
    return {item.family: (item.status.value, item.count) for item in counts}


def _count_for(counts: tuple[CorpusLoweringFamilyCount, ...], family: str) -> int:
    return next(item.count for item in counts if item.family == family)


def _representative(
    result: CorpusLoweringCharacterization,
    family: str,
) -> CorpusLoweringRepresentative:
    return next(item for item in result.representatives if item.family == family)
