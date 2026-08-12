"""Typed C++ profile auto-detection extension-point tests."""

from __future__ import annotations

from tslc.backend.cpp_detection import (
    CppProfileAutoGate,
    CppProfileAutoGateRegistry,
    CppProfileDetectionCandidate,
    CppProfileDetectionStrategy,
    CppProfileDetectionStrategyRegistry,
    cpp_profile_detection_candidates,
    cpp_profile_detection_plan,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.target_families import (
    BackendProfileFamily,
    ProfileFamilyCapability,
)
from tslc.render.cpp_build import _cpp_profile_auto_modes


def test_fake_detection_strategy_is_added_without_renderer_changes() -> None:
    seen: list[str] = []

    def source_builder(profile, guards):  # noqa: ANN001
        seen.append(profile.name)
        assert guards == ()
        return "int main() { return 42; }"

    registry = CppProfileDetectionStrategyRegistry(
        (CppProfileDetectionStrategy("future_probe", source_builder),)
    )
    family = ProfileFamilyCapability(
        "future-family",
        backends={
            "cpp": BackendProfileFamily(detection="future_probe"),
        },
    )
    profile = MachineProfile(
        "future-profile",
        family.name,
        frozenset({"future_feature"}),
        {},
    )
    emitted = EmittedProfile(
        profile,
        {"cpp": {}},
        profile_family=family,
        immediate_split_names=frozenset(),
    )

    candidates = cpp_profile_detection_candidates(
        (emitted,), strategy_registry=registry
    )

    assert seen == ["future-profile"]
    assert candidates == (
        CppProfileDetectionCandidate(
            profile_name="future-profile",
            auto_gate_id=None,
            has_features=True,
            source="int main() { return 42; }",
        ),
    )


def test_fake_second_auto_gate_renders_from_registry_facts() -> None:
    gate = CppProfileAutoGate(
        gate_id="future_accelerator",
        mode_name="auto-future-accelerator",
        helper_function="_tsl_detect_future_accelerator",
        helper_asset="future_accelerator.cmake",
    )
    registry = CppProfileAutoGateRegistry((gate,))
    profile = MachineProfile(
        "future-profile",
        "future-family",
        frozenset({"future_feature"}),
        {},
        auto_detect_gate=gate.gate_id,
    )

    plan = cpp_profile_detection_plan(
        (profile,),
        candidates=(
            CppProfileDetectionCandidate(
                profile_name=profile.name,
                auto_gate_id=gate.gate_id,
                has_features=True,
                source="int main() { return 0; }",
            ),
        ),
        gate_registry=registry,
    )
    rendered = _cpp_profile_auto_modes(plan)

    assert plan.auto_choices == ("auto-future-accelerator",)
    assert plan.helper_assets == ("future_accelerator.cmake",)
    assert "_tsl_detect_future_accelerator(" in rendered
    assert "future_accelerator auto-detection failed" in rendered
    assert "_tsl_detect_profile_gate" not in rendered
