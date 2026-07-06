"""Tests for the `explain` diagnostic tool (maintenance/explain.py)."""

from __future__ import annotations

from pathlib import Path

from tslc.maintenance.explain import _decisive_tiebreak, explain
from tslc.select.selector import RankedCandidate, Selector


def _candidate(
    *, distance: int = 0, specificity: int = 1, flag_count: int = 0, source_order: int = 0
) -> RankedCandidate:
    return RankedCandidate(
        implementation=None,  # type: ignore[arg-type]  # not read by _decisive_tiebreak
        required_features=frozenset(),
        distance=distance,
        specificity=specificity,
        flag_count=flag_count,
        source_order=source_order,
    )


def _explain(data_root: Path, machine_profiles_path: Path, **kwargs) -> str:
    return explain(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        **kwargs,
    )


def test_compiling_slot_shows_intrinsic_and_verdict(
    data_root: Path, machine_profiles_path: Path
) -> None:
    report = _explain(
        data_root,
        machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="avx2",
    )
    assert "VERDICT: COMPILES" in report
    assert "_mm256_add_epi32" in report  # the resolved intrinsic name
    assert "avx2:?i?" in report  # the winning body's extension:type-group
    # the float body is a rejected on-chain candidate, with the reason
    assert "f?" in report and "does not contain si32" in report


def test_segment_tree_names_the_regions(
    data_root: Path, machine_profiles_path: Path
) -> None:
    report = _explain(
        data_root,
        machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="avx2",
    )
    assert "BODY  (TSIL segment tree)" in report
    assert "region complete(...)" in report
    assert "region intrin<add, build[suffix=base::signed_of(base::in)]>(...)" in report


def test_not_selected_reports_the_missing_flag(
    data_root: Path, machine_profiles_path: Path
) -> None:
    # avx512 is a candidate extension on an avx2 profile, but its body needs avx512f.
    report = _explain(
        data_root,
        machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="avx512",
    )
    assert "NOT selected" in report
    assert "missing: avx512f" in report


def test_dependency_closure_marks_emitted_callee(
    data_root: Path, machine_profiles_path: Path
) -> None:
    # The portable `generic` add lowers to a per-lane loop that calls scalar add.
    report = _explain(
        data_root,
        machine_profiles_path,
        primitive="add",
        profile="avx2",
        type_tag="si32",
        backend="cpp",
        extension="generic",
    )
    assert "call<…> callees" in report
    assert "add <scalar, si32>" in report
    assert "✓" in report  # the callee is emitted in the closure


def test_unknown_profile_is_reported(
    data_root: Path, machine_profiles_path: Path
) -> None:
    report = _explain(
        data_root,
        machine_profiles_path,
        primitive="add",
        profile="does-not-exist",
        type_tag="si32",
        backend="cpp",
    )
    assert "no machine profile named 'does-not-exist'" in report


def test_evaluate_candidates_ranks_winner_and_records_rejection(
    data_root: Path, machine_profiles_path: Path
) -> None:
    from tslc.catalog.builder import CatalogBuilder
    from tslc.catalog.machine_profiles import load_machine_profiles
    from tslc.compiler_assets import load_default_tsl_grammar
    from tslc.sources import SourceLoader
    from tslc.syntax.parser import TslParser

    sources = sorted(data_root.rglob("*.tsl"))
    documents = SourceLoader().load(tuple(sources))
    parse_result = TslParser(load_default_tsl_grammar()).parse(documents.documents)
    catalog = CatalogBuilder().build(parse_result).catalog
    assert catalog is not None
    profile = load_machine_profiles(machine_profiles_path)["avx2"]
    primitive = catalog.primitive("add")
    assert primitive is not None

    evaluation = Selector().evaluate_candidates(
        catalog, profile, primitive, "avx2", "si32", None
    )
    assert len(evaluation.ranked) == 1
    winner = evaluation.ranked[0]
    assert winner.implementation.extension == "avx2"
    assert winner.implementation.type_group == "?i?"
    assert winner.required_features == frozenset({"avx", "avx2"})
    # the float body could not serve si32 and is recorded as rejected
    rejected_groups = {r.implementation.type_group for r in evaluation.rejected}
    assert "f?" in rejected_groups


def test_decisive_tiebreak_names_the_first_differing_key() -> None:
    # distance dominates everything else
    winner = _candidate(distance=0, specificity=10, flag_count=0, source_order=9)
    runner = _candidate(distance=1, specificity=1, flag_count=5, source_order=0)
    assert "won on distance" in _decisive_tiebreak(winner, runner)

    # tie on distance -> specificity decides (fewer members wins)
    winner = _candidate(distance=0, specificity=1, flag_count=0)
    runner = _candidate(distance=0, specificity=8, flag_count=0)
    assert "won on specificity" in _decisive_tiebreak(winner, runner)

    # tie on distance + specificity -> more required target features wins
    winner = _candidate(distance=0, specificity=8, flag_count=3)
    runner = _candidate(distance=0, specificity=8, flag_count=1)
    message = _decisive_tiebreak(winner, runner)
    assert "won on flag_count" in message and "3 > 1" in message

    # all principled keys tie -> only source order, which is arbitrary
    winner = _candidate(distance=0, specificity=8, flag_count=1, source_order=2)
    runner = _candidate(distance=0, specificity=8, flag_count=1, source_order=7)
    assert "won on source_order" in _decisive_tiebreak(winner, runner)
