"""Focused unit evidence for typed Rust policy-selection planning."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tslc.api import generate_project
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_policy_selection import (
    plan_rust_policy_selection,
    rust_policy_selection_reason,
)
from tslc.diagnostics import has_errors


@pytest.fixture(scope="module")
def rust_selection_result(data_root: Path, machine_profiles_path: Path):
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


def test_plan_has_exact_supported_and_report_only_keys(rust_selection_result) -> None:
    plan = plan_rust_policy_selection(rust_selection_result.emitted_profiles)
    profile = plan.profile("sse2")
    assert profile is not None
    assert [selection.key.primitive_name for selection in profile.selections] == [
        "mul"
    ]

    selection = profile.selections[0]
    assert selection.candidate_ids == ("default", "generic_fallback")
    assert selection.selected_candidate == "default"

    report = rust_selection_result.rendered.benchmarks.profile("rust", "sse2")
    assert report is not None
    report_keys = {
        candidate_set.key.primitive_name: candidate_set.key
        for candidate_set in report.candidate_sets
    }
    coverage = {entry.key.primitive_name: entry for entry in profile.coverage}
    assert coverage.keys() == report_keys.keys()
    assert selection.key == report_keys["mul"]
    assert coverage["mul"].status == "supported"
    for primitive_name in ("shift_left", "shift_right"):
        assert coverage[primitive_name].key == report_keys[primitive_name]
        assert coverage[primitive_name].status == "report_only"
        assert "overloaded" in coverage[primitive_name].reason


def test_forced_override_is_validated_and_immutable(rust_selection_result) -> None:
    default = plan_rust_policy_selection(rust_selection_result.emitted_profiles)
    profile = default.profile("sse2")
    assert profile is not None
    selected = profile.selections[0]

    forced = default.with_forced_selection(selected.key, "generic_fallback")
    forced_profile = forced.profile("sse2")
    assert forced_profile is not None
    assert profile.selections[0].selected_candidate == "default"
    assert forced_profile.selections[0].selected_candidate == "generic_fallback"
    assert forced_profile.coverage == profile.coverage

    with pytest.raises(ValueError, match="candidate 'missing' is unavailable"):
        default.with_forced_selection(selected.key, "missing")
    report_only = next(
        entry for entry in profile.coverage if entry.status == "report_only"
    )
    with pytest.raises(ValueError, match="is report-only: overloaded"):
        default.with_forced_selection(report_only.key, "generic_fallback")
    with pytest.raises(ValueError, match="key is not present"):
        default.with_forced_selection(
            replace(selected.key, primitive_name="missing"),
            "default",
        )


def test_selection_gate_is_exact_and_deterministic(rust_selection_result) -> None:
    emitted = rust_selection_result.emitted_profiles[0]
    source = _variant_spec(emitted, "mul")
    renamed = replace(
        source,
        primitive_name="structural_probe",
        source_primitive_name="structural_probe",
    )
    profile = _profile_with(emitted, {"structural_probe": (renamed,)})

    first = plan_rust_policy_selection((profile,))
    second = plan_rust_policy_selection((profile,))
    planned = first.profile("sse2")

    assert first == second
    assert planned is not None
    assert planned.selections == ()
    assert len(planned.coverage) == 1
    assert planned.coverage[0].status == "report_only"
    assert "proven sse2 mul pilot" in planned.coverage[0].reason


def test_duplicate_key_coverage_is_fail_closed_and_order_independent(
    rust_selection_result,
) -> None:
    emitted = rust_selection_result.emitted_profiles[0]
    source = _variant_spec(emitted, "mul")
    alternate = replace(
        source,
        variant_bodies=(
            replace(source.variant_bodies[0], name="alternate"),
        ),
    )
    forward = _profile_with(emitted, {"mul": (source, alternate)})
    reverse = _profile_with(emitted, {"mul": (alternate, source)})

    planned = plan_rust_policy_selection((forward,)).profile("sse2")
    reversed_plan = plan_rust_policy_selection((reverse,)).profile("sse2")

    assert planned is not None
    assert planned == reversed_plan
    assert planned.selections == ()
    assert len(planned.coverage) == 1
    assert planned.coverage[0].status == "report_only"
    assert "same Rust policy key" in planned.coverage[0].reason
    assert planned.coverage[0].candidate_ids == (
        "default",
        "alternate",
        "generic_fallback",
    )


def test_backend_query_owns_deferred_shape_classification(
    rust_selection_result,
) -> None:
    plan = plan_rust_policy_selection(rust_selection_result.emitted_profiles)
    profile = plan.profile("sse2")
    assert profile is not None
    selection = profile.selections[0]
    key = selection.key
    spec = selection.specialization

    assert rust_policy_selection_reason(key, spec) is None
    assert "fixed-width" in rust_policy_selection_reason(
        replace(key, lanes=None), spec
    )
    assert "header-group" in rust_policy_selection_reason(
        replace(key, header_group="optional"), spec
    )
    assert "overloaded" in rust_policy_selection_reason(
        replace(key, overload_parameter_positions=(1,)), spec
    )
    assert "masked" in rust_policy_selection_reason(
        key, replace(spec, mask_policy="zero")
    )
    assert "axis" in rust_policy_selection_reason(
        replace(key, axis=(("aligned", "false"),)),
        replace(spec, axis=(("aligned", "false"),)),
    )
    assert "immediate" in rust_policy_selection_reason(
        key, replace(spec, immediate=("amount", "u32"))
    )
    assert "const-generic" in rust_policy_selection_reason(
        key, replace(spec, generic_params=(("N", "usize", "1"),))
    )
    assert "parameter type overrides" in rust_policy_selection_reason(
        key, replace(spec, param_type_overrides=("u32", None))
    )
    assert "proven sse2 mul pilot" in rust_policy_selection_reason(
        replace(key, primitive_name="renamed"),
        replace(spec, primitive_name="renamed"),
    )


def _variant_spec(profile: EmittedProfile, primitive_name: str):
    return next(
        spec
        for spec in profile.specializations("rust")[primitive_name]
        if spec.variant_bodies
    )


def _profile_with(source: EmittedProfile, by_primitive) -> EmittedProfile:
    return EmittedProfile(
        profile=source.profile,
        specializations_by_backend={"rust": by_primitive},
        extensions=source.extensions,
        profile_family=source.profile_family,
        immediate_split_names=frozenset(),
    )
