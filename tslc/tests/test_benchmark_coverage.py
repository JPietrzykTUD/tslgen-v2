"""Full-corpus benchmark coverage audit and deterministic shape inventory."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tslc.api import generate_project
from tslc.backend.rust_policy_consumption import (
    plan_rust_policy_coverage,
)
from tslc.backend.rust_policy_selection import plan_rust_policy_selection
from tslc.benchmark.model import BenchmarkProjectPlan
from tslc.catalog.model import Catalog
from tslc.diagnostics import has_errors
from tslc.maintenance import benchmark_coverage as benchmark_coverage_module
from tslc.maintenance.benchmark_coverage import (
    audit_benchmark_coverage,
    benchmark_issue_baseline,
    compute_benchmark_coverage_audit,
    deserialize_rust_benchmark_baseline,
    deserialize_issue_baseline,
    diff_benchmark_issues,
    diff_rust_benchmark_coverage,
    main as benchmark_coverage_main,
    render_benchmark_shape_inventory,
    rust_benchmark_coverage_baseline,
    serialize_rust_benchmark_baseline,
    serialize_issue_baseline,
)
from tslc.maintenance.rust_benchmark_evidence import RustBenchmarkEvidence
from tslc.pipeline import SkippedEntry


@pytest.fixture(scope="module")
def focused_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["scalar", "sse2", "avx2"],
        type_tags=["si8"],
        backends=["cpp"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


@pytest.fixture(scope="module")
def focused_rust_benchmark_result(data_root: Path, machine_profiles_path: Path):
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["mul"],
        profiles=["sse2"],
        type_tags=["si8"],
        backends=["rust"],
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    return result


def _rust_audit(catalog: Catalog, result, *, plan=None):
    assert result.rendered is not None
    benchmarks = result.rendered.benchmarks if plan is None else plan
    policy_coverage = plan_rust_policy_coverage(
        benchmarks,
        plan_rust_policy_selection(result.emitted_profiles),
    )
    return audit_benchmark_coverage(
        catalog,
        benchmarks,
        backend_id="rust",
        primitive_names=("mul",),
        selection_coverage=result.coverage,
        selection_skips=result.skipped,
        emitted_profiles=result.emitted_profiles,
        rust_policy_coverage=policy_coverage,
    )


def test_audit_accounts_for_every_selected_variant_slot(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    assert audit.complete
    assert audit.selected_slots > 0
    assert audit.candidate_sets >= audit.selected_slots
    variant_shapes = [entry for entry in audit.shapes if entry.variant_declarations]
    assert variant_shapes
    assert all(entry.status == "benchmarked" for entry in variant_shapes)


def test_audit_rejects_a_selected_slot_without_a_workload(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    focused_benchmark_plan = focused_benchmark_result.rendered.benchmarks
    first, *rest = focused_benchmark_plan.coverage
    broken = replace(
        focused_benchmark_plan,
        coverage=(
            replace(
                first,
                status="unsupported",
                reason="focused unsupported-shape sentinel",
            ),
            *rest,
        ),
    )

    audit = audit_benchmark_coverage(
        catalog,
        broken,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    assert not audit.complete
    assert any(
        issue.kind == "coverage-gap"
        and "unsupported-shape sentinel" in issue.detail
        for issue in audit.issues
    )


def test_issue_baseline_is_deterministic_and_ignores_reason_wording(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    focused_benchmark_plan = focused_benchmark_result.rendered.benchmarks
    first, *rest = focused_benchmark_plan.coverage
    broken = replace(
        focused_benchmark_plan,
        coverage=(
            replace(first, status="unsupported", reason="baseline sentinel"),
            *rest,
        ),
    )
    audit = audit_benchmark_coverage(
        catalog,
        broken,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )
    assert len(audit.issues) == 1
    baseline = benchmark_issue_baseline(audit.issues)

    rendered = serialize_issue_baseline(baseline)
    loaded = deserialize_issue_baseline(rendered)

    assert loaded == baseline
    assert serialize_issue_baseline(loaded) == rendered
    reworded = (replace(audit.issues[0], detail="different explanation"),)
    unchanged = diff_benchmark_issues(loaded, reworded)
    assert unchanged.new_issues == ()
    assert unchanged.resolved_issues == ()

    added = replace(audit.issues[0], kind="candidate-without-coverage")
    regressed = diff_benchmark_issues(loaded, (*reworded, added))
    assert regressed.new_issues == (added,)
    assert regressed.resolved_issues == ()


def test_audit_rejects_a_lowered_variant_slot_missing_from_the_planner(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    selected = next(
        entry for entry in focused_benchmark_result.coverage if entry.variant_names
    )
    unplanned = replace(selected, extension="unplanned_extension")

    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=(*focused_benchmark_result.coverage, unplanned),
        selection_skips=focused_benchmark_result.skipped,
    )

    assert any(
        issue.kind == "selected-slot-missing-planner"
        and issue.slot is not None
        and issue.slot.extension_name == "unplanned_extension"
        for issue in audit.issues
    )


def test_audit_keeps_variant_lowering_skips_in_the_funnel(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    assert focused_benchmark_result.rendered is not None
    selected = next(
        entry for entry in focused_benchmark_result.coverage if entry.variant_names
    )
    remaining = tuple(
        entry for entry in focused_benchmark_result.coverage if entry is not selected
    )
    skipped = SkippedEntry(
        profile=selected.profile,
        backend=selected.backend,
        primitive=selected.primitive,
        extension=selected.extension,
        type_tag=selected.type_tag,
        reason="focused lowering-skip sentinel",
        source_primitive_name=selected.source_primitive_name,
        result_kind=selected.result_kind,
        param_kinds=selected.param_kinds,
        mask_policy=selected.mask_policy,
        axis=selected.axis,
        variant_names=selected.variant_names,
    )

    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=remaining,
        selection_skips=(*focused_benchmark_result.skipped, skipped),
    )

    assert any(
        issue.kind == "selected-slot-skipped"
        and "lowering-skip sentinel" in issue.detail
        for issue in audit.issues
    )


def test_shape_inventory_is_deterministic_and_marks_default_only_shapes(
    catalog: Catalog,
    focused_benchmark_result,
) -> None:
    # The focused plan intentionally leaves other variant declarations inactive;
    # rendering must still inventory all source shapes and distinguish default-only
    # shapes from genuine variant coverage gaps.
    assert focused_benchmark_result.rendered is not None
    audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )

    first = render_benchmark_shape_inventory(audit)
    second = render_benchmark_shape_inventory(audit)

    assert first == second
    assert "## Signature shapes" in first
    assert "## Special cases" in first
    assert "not applicable" in first
    assert "inactive-authored-shape" in first
    special_cases = {entry.name: entry for entry in audit.special_cases}
    sized = special_cases["sized-vector implementation"]
    assert sized.variant_declarations == 0
    assert sized.status == "not applicable"

    for name in (
        "scalable-vector implementation",
        "opt-in compiler header implementation",
    ):
        assert special_cases[name].variant_declarations > 0
        assert special_cases[name].status == "gap"


def test_rust_audit_keeps_report_and_policy_eligibility_separate(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    audit = _rust_audit(catalog, focused_rust_benchmark_result)

    assert audit.backend_id == "rust"
    assert audit.candidate_sets == 1
    assert audit.policy_supported_reports == 1
    assert audit.policy_report_only_reports == 0
    assert audit.rust_evidence is not None
    assert len(audit.rust_evidence.profiles) == 1
    assert len(audit.rust_evidence.candidates) == 3
    assert [policy.status for policy in audit.rust_evidence.policies] == [
        "supported",
        "report_only",
        "report_only",
    ]
    rendered = render_benchmark_shape_inventory(audit)
    assert "Policy mapped" in rendered
    assert "Report-only" in rendered


def test_rust_issue_baseline_preserves_equal_slot_memberships(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    plan = focused_rust_benchmark_result.rendered.benchmarks
    first = next(
        entry for entry in plan.coverage if entry.source_primitive_name == "mul"
    )
    duplicated_gap = replace(
        first,
        status="unsupported",
        reason="exact-membership sentinel",
    )
    broken = replace(
        plan,
        coverage=(duplicated_gap, duplicated_gap, *plan.coverage),
    )

    audit = _rust_audit(catalog, focused_rust_benchmark_result, plan=broken)
    sentinels = tuple(
        issue for issue in audit.issues if "exact-membership sentinel" in issue.detail
    )

    assert len(sentinels) == 2
    assert [issue.slot.membership for issue in sentinels if issue.slot is not None] == [
        0,
        1,
    ]
    assert all(
        issue.slot is not None and issue.slot.specialization_hash == first.slot_hash
        for issue in sentinels
    )
    baseline = rust_benchmark_coverage_baseline(audit)
    assert len(baseline.issues) == len(audit.issues)

    changed_coverage = list(broken.coverage)
    changed_coverage[1] = replace(
        changed_coverage[1], slot_hash="3" * 64
    )
    changed = _rust_audit(
        catalog,
        focused_rust_benchmark_result,
        plan=replace(broken, coverage=tuple(changed_coverage)),
    )
    assert diff_rust_benchmark_coverage(baseline, changed).issue_diff.new_issues


def test_rust_gap_membership_is_stable_per_exact_slot_hash(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    result = focused_rust_benchmark_result
    plan = result.rendered.benchmarks
    first = next(
        entry for entry in plan.coverage if entry.source_primitive_name == "mul"
    )
    gap_a = replace(
        first,
        slot_hash="6" * 64,
        status="unsupported",
        reason="first distinct exact slot",
    )
    gap_b = replace(
        first,
        slot_hash="7" * 64,
        status="unsupported",
        reason="second distinct exact slot",
    )
    broken = replace(plan, coverage=(gap_a, gap_b, *plan.coverage))
    baseline = rust_benchmark_coverage_baseline(_rust_audit(catalog, result, plan=broken))

    changed = _rust_audit(
        catalog,
        result,
        plan=replace(plan, coverage=(gap_b, *plan.coverage)),
    )
    diff = diff_rust_benchmark_coverage(baseline, changed).issue_diff

    assert not diff.new_issues
    assert any(
        issue.kind == "coverage-gap"
        and issue.slot is not None
        and issue.slot.specialization_hash == gap_a.slot_hash
        for issue in diff.resolved_issues
    )
    assert not any(
        issue.kind == "coverage-gap"
        and issue.slot is not None
        and issue.slot.specialization_hash == gap_b.slot_hash
        for issue in diff.resolved_issues
    )


def test_rust_audit_detects_planner_slot_identity_drift(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    result = focused_rust_benchmark_result
    plan = result.rendered.benchmarks
    selection = plan_rust_policy_selection(result.emitted_profiles)
    policy_coverage = plan_rust_policy_coverage(plan, selection)
    baseline_audit = _rust_audit(catalog, result)
    baseline = rust_benchmark_coverage_baseline(baseline_audit)

    planner_index = next(
        index
        for index, entry in enumerate(plan.coverage)
        if entry.source_primitive_name == "mul"
    )
    changed_planner = list(plan.coverage)
    changed_planner[planner_index] = replace(
        changed_planner[planner_index],
        primitive_name="foreign_emitted_name",
        slot_hash="4" * 64,
    )
    planner_audit = audit_benchmark_coverage(
        catalog,
        replace(plan, coverage=tuple(changed_planner)),
        backend_id="rust",
        primitive_names=("mul",),
        selection_coverage=result.coverage,
        selection_skips=result.skipped,
        emitted_profiles=result.emitted_profiles,
        rust_policy_coverage=policy_coverage,
    )
    assert diff_rust_benchmark_coverage(
        baseline, planner_audit
    ).issue_diff.new_issues

    changed_planner[planner_index] = replace(
        plan.coverage[planner_index], slot_hash="5" * 64
    )
    hash_audit = audit_benchmark_coverage(
        catalog,
        replace(plan, coverage=tuple(changed_planner)),
        backend_id="rust",
        primitive_names=("mul",),
        selection_coverage=result.coverage,
        selection_skips=result.skipped,
        emitted_profiles=result.emitted_profiles,
        rust_policy_coverage=policy_coverage,
    )
    assert {
        issue.kind for issue in diff_rust_benchmark_coverage(
            baseline, hash_audit
        ).issue_diff.new_issues
    } == {
        "candidate-without-coverage",
        "emitted-without-candidates",
        "planner-slot-without-selection",
        "selected-slot-missing-planner",
    }


def test_rust_audit_rejects_duplicate_emitted_planner_membership(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    result = focused_rust_benchmark_result
    plan = result.rendered.benchmarks
    emitted = next(
        entry
        for entry in plan.coverage
        if entry.source_primitive_name == "mul" and entry.status == "emitted"
    )

    audit = _rust_audit(
        catalog,
        result,
        plan=replace(plan, coverage=(emitted, *plan.coverage)),
    )

    extras = tuple(
        issue
        for issue in audit.issues
        if issue.kind == "planner-slot-without-selection"
        and issue.slot is not None
        and issue.slot.specialization_hash == emitted.slot_hash
    )
    assert len(extras) == 1


def test_rust_policy_gap_issue_baseline_round_trips(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    result = focused_rust_benchmark_result
    plan = result.rendered.benchmarks
    selections = plan_rust_policy_selection(result.emitted_profiles)
    supported_key = next(
        selection.key
        for profile in selections.profiles
        for selection in profile.selections
    )
    broken_profiles = tuple(
        replace(
            profile,
            candidate_sets=tuple(
                candidate
                for candidate in profile.candidate_sets
                if candidate.key != supported_key
            ),
            manifest_hash="8" * 64,
        )
        if profile.profile_name == supported_key.profile_name
        else profile
        for profile in plan.profiles
    )
    broken = replace(plan, profiles=broken_profiles)
    policy_coverage = plan_rust_policy_coverage(broken, selections)

    audit = audit_benchmark_coverage(
        catalog,
        broken,
        backend_id="rust",
        primitive_names=("mul",),
        selection_coverage=result.coverage,
        selection_skips=result.skipped,
        emitted_profiles=result.emitted_profiles,
        rust_policy_coverage=policy_coverage,
    )
    gaps = tuple(
        issue
        for issue in audit.issues
        if issue.kind == "policy-supported-without-report"
    )
    assert len(gaps) == 1
    assert gaps[0].slot is not None
    assert gaps[0].slot.primitive_name == supported_key.primitive_name

    baseline = rust_benchmark_coverage_baseline(audit)
    rendered = serialize_rust_benchmark_baseline(baseline)
    assert deserialize_rust_benchmark_baseline(rendered) == baseline


def test_rust_baseline_round_trips_and_rejects_exact_evidence_drift(
    catalog: Catalog,
    focused_rust_benchmark_result,
) -> None:
    audit = _rust_audit(catalog, focused_rust_benchmark_result)
    baseline = rust_benchmark_coverage_baseline(audit)
    rendered = serialize_rust_benchmark_baseline(baseline)

    assert deserialize_rust_benchmark_baseline(rendered) == baseline
    assert serialize_rust_benchmark_baseline(
        deserialize_rust_benchmark_baseline(rendered)
    ) == rendered

    evidence = baseline.evidence
    changed_profile = replace(
        evidence,
        profiles=(
            replace(evidence.profiles[0], manifest_hash="0" * 64),
            *evidence.profiles[1:],
        ),
    )
    assert diff_rust_benchmark_coverage(
        baseline, replace(audit, rust_evidence=changed_profile)
    ).evidence_changed

    policy_index = next(
        index
        for index, policy in enumerate(evidence.policies)
        if policy.status == "report_only"
    )
    policy = evidence.policies[policy_index]
    candidate_index = next(
        index
        for index, candidate in enumerate(evidence.candidates)
        if candidate.stable_id == policy.stable_id
    )
    candidate = evidence.candidates[candidate_index]

    changed_hashes = (
        candidate.candidates[0],
        (candidate.candidates[1][0], "1" * 64),
    )
    candidates = list(evidence.candidates)
    policies = list(evidence.policies)
    candidates[candidate_index] = replace(candidate, candidates=changed_hashes)
    policies[policy_index] = replace(policy, candidates=changed_hashes)
    changed_body = RustBenchmarkEvidence(
        evidence.profiles, tuple(candidates), tuple(policies)
    )
    assert diff_rust_benchmark_coverage(
        baseline, replace(audit, rust_evidence=changed_body)
    ).evidence_changed

    changed_ids = (
        candidate.candidates[0],
        ("renamed_candidate", candidate.candidates[1][1]),
    )
    candidates[candidate_index] = replace(candidate, candidates=changed_ids)
    policies[policy_index] = replace(policy, candidates=changed_ids)
    changed_candidate = RustBenchmarkEvidence(
        evidence.profiles, tuple(candidates), tuple(policies)
    )
    assert diff_rust_benchmark_coverage(
        baseline, replace(audit, rust_evidence=changed_candidate)
    ).evidence_changed

    candidates[candidate_index] = candidate
    policies[policy_index] = replace(
        policy,
        status="supported",
        mappings=tuple((candidate_id, "2" * 64) for candidate_id, _ in policy.candidates),
    )
    changed_policy = RustBenchmarkEvidence(
        evidence.profiles, tuple(candidates), tuple(policies)
    )
    assert diff_rust_benchmark_coverage(
        baseline, replace(audit, rust_evidence=changed_policy)
    ).evidence_changed


def test_cpp_and_rust_baseline_formats_are_backend_separated(
    catalog: Catalog,
    focused_benchmark_result,
    focused_rust_benchmark_result,
) -> None:
    cpp_audit = audit_benchmark_coverage(
        catalog,
        focused_benchmark_result.rendered.benchmarks,
        primitive_names=("mul",),
        selection_coverage=focused_benchmark_result.coverage,
        selection_skips=focused_benchmark_result.skipped,
    )
    rust_audit = _rust_audit(catalog, focused_rust_benchmark_result)

    cpp_text = serialize_issue_baseline(benchmark_issue_baseline(cpp_audit.issues))
    rust_text = serialize_rust_benchmark_baseline(
        rust_benchmark_coverage_baseline(rust_audit)
    )
    with pytest.raises(ValueError, match="Rust benchmark baseline"):
        deserialize_rust_benchmark_baseline(cpp_text)
    with pytest.raises(ValueError, match="benchmark baseline version"):
        deserialize_issue_baseline(rust_text)

    cpp_payload = json.loads(cpp_text)
    cpp_payload["version"] = True
    with pytest.raises(ValueError, match="benchmark baseline version"):
        deserialize_issue_baseline(json.dumps(cpp_payload))
    cpp_payload["version"] = 1
    cpp_payload["issues"] = [
        ["policy-supported-without-report", ["mul", "v", ["v", "v"], None], None]
    ]
    with pytest.raises(ValueError, match="unknown benchmark issue kind"):
        deserialize_issue_baseline(json.dumps(cpp_payload))

    rust_payload = json.loads(rust_text)
    rust_payload["version"] = True
    with pytest.raises(ValueError, match="Rust benchmark baseline"):
        deserialize_rust_benchmark_baseline(json.dumps(rust_payload))
    rust_payload["version"] = 1
    rust_payload["profiles"][0][1] = "not-a-sha256"
    with pytest.raises(ValueError, match="profile evidence"):
        deserialize_rust_benchmark_baseline(json.dumps(rust_payload))
    rust_payload = json.loads(rust_text)
    rust_payload["issues"] = [
        [
            "coverage-gap",
            ["mul", "v", ["v", "v"], None],
            ["cpp", "sse2", "sse", "si8", [], ["generic_fallback"], "mul", 0, "a" * 64],
        ]
    ]
    with pytest.raises(ValueError, match="slot backend must be 'rust'"):
        deserialize_rust_benchmark_baseline(json.dumps(rust_payload))

    rust_payload["issues"] = [
        [
            "coverage-gap",
            ["mul", "v", ["v", "v"], None],
            [
                "rust",
                "sse2",
                "sse",
                "si8",
                [],
                ["generic_fallback"],
                "mul",
                0,
                "not-a-sha256",
            ],
        ]
    ]
    with pytest.raises(ValueError, match="canonical SHA-256"):
        deserialize_rust_benchmark_baseline(json.dumps(rust_payload))


def test_benchmark_cli_rejects_an_unowned_backend_before_writing(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    inventory = tmp_path / "inventory.md"

    with pytest.raises(SystemExit, match="2"):
        benchmark_coverage_main(
            [
                "--backend",
                "future-backend",
                "--baseline",
                str(baseline),
                "--inventory",
                str(inventory),
                "--update",
            ]
        )

    assert not baseline.exists()
    assert not inventory.exists()


def test_rust_benchmark_audit_generates_unordered_profiles_independently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    catalog = SimpleNamespace(target_families=object())
    eligible_profile = SimpleNamespace(
        supports_backend=lambda backend_id: backend_id == "rust"
    )
    ineligible_profile = SimpleNamespace(
        supports_backend=lambda backend_id: backend_id == "cpp"
    )
    monkeypatch.setattr(
        benchmark_coverage_module,
        "_load_catalog",
        lambda _sources, _backend_id: (catalog, ()),
    )
    monkeypatch.setattr(
        benchmark_coverage_module,
        "load_machine_profiles_checked",
        lambda _path, _families: SimpleNamespace(
            profiles={
                "cpp-only": ineligible_profile,
                "left": eligible_profile,
                "right": eligible_profile,
            },
            diagnostics=(),
        ),
    )

    generated_groups: list[tuple[str, ...] | None] = []

    def fake_generate_project(_sources, **kwargs):
        group = kwargs["profiles"]
        generated_groups.append(group)
        assert group is not None and len(group) == 1
        profile_name = group[0]
        return SimpleNamespace(
            diagnostics=(),
            rendered=SimpleNamespace(
                benchmarks=BenchmarkProjectPlan(
                    profiles=(profile_name,),
                    coverage=(f"benchmark-{profile_name}",),
                )
            ),
            coverage=(f"selection-{profile_name}",),
            skipped=(f"skip-{profile_name}",),
            emitted_profiles=(
                SimpleNamespace(profile=SimpleNamespace(name=profile_name)),
            ),
        )

    monkeypatch.setattr(
        benchmark_coverage_module,
        "generate_project",
        fake_generate_project,
    )
    policy_inputs: dict[str, object] = {}

    def fake_policy_selection(emitted_profiles):
        policy_inputs["emitted"] = emitted_profiles
        return "selection"

    def fake_policy_coverage(benchmarks, selection):
        policy_inputs["benchmarks"] = benchmarks
        policy_inputs["selection"] = selection
        return "coverage"

    monkeypatch.setattr(
        benchmark_coverage_module,
        "plan_rust_policy_selection",
        fake_policy_selection,
    )
    monkeypatch.setattr(
        benchmark_coverage_module,
        "plan_rust_policy_coverage",
        fake_policy_coverage,
    )
    audit_inputs: dict[str, object] = {}
    sentinel = object()

    def fake_audit(_catalog, benchmarks, **kwargs):
        audit_inputs["benchmarks"] = benchmarks
        audit_inputs.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        benchmark_coverage_module,
        "audit_benchmark_coverage",
        fake_audit,
    )

    audit, errors = compute_benchmark_coverage_audit(
        sources=tmp_path,
        machine_profiles=tmp_path / "profiles.json",
        profiles=None,
        types=("si8",),
        backend_id="rust",
    )

    assert errors == ()
    assert audit is sentinel
    assert generated_groups == [("left",), ("right",)]
    merged = audit_inputs["benchmarks"]
    assert isinstance(merged, BenchmarkProjectPlan)
    assert merged.profiles == ("left", "right")
    assert merged.coverage == ("benchmark-left", "benchmark-right")
    assert audit_inputs["selection_coverage"] == (
        "selection-left",
        "selection-right",
    )
    assert audit_inputs["selection_skips"] == ("skip-left", "skip-right")
    emitted = audit_inputs["emitted_profiles"]
    assert tuple(item.profile.name for item in emitted) == ("left", "right")
    assert policy_inputs["selection"] == "selection"
    assert policy_inputs["benchmarks"] is merged


def test_rust_benchmark_audit_rejects_explicit_backend_ineligible_profile(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    catalog = SimpleNamespace(target_families=object())
    ineligible_profile = SimpleNamespace(
        supports_backend=lambda backend_id: backend_id == "cpp"
    )
    monkeypatch.setattr(
        benchmark_coverage_module,
        "_load_catalog",
        lambda _sources, _backend_id: (catalog, ()),
    )
    monkeypatch.setattr(
        benchmark_coverage_module,
        "load_machine_profiles_checked",
        lambda _path, _families: SimpleNamespace(
            profiles={"cpp-only": ineligible_profile},
            diagnostics=(),
        ),
    )

    audit, errors = compute_benchmark_coverage_audit(
        sources=tmp_path,
        machine_profiles=tmp_path / "profiles.json",
        profiles=("cpp-only",),
        types=("si8",),
        backend_id="rust",
    )

    assert audit is None
    assert errors == ("machine profile(s) cpp-only do not support backend 'rust'",)
