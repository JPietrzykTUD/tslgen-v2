"""Typed C++ profile auto-detection extension-point tests."""

from __future__ import annotations

from tslc.backend.cpp_detection import (
    CppProfileAutoGate,
    CppProfileAutoGateRegistry,
    cpp_profile_detection_plan,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.catalog.machine_profiles import MachineProfile
from tslc.render.cpp_build import _cpp_profile_auto_modes


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
    emitted = EmittedProfile(
        profile=profile,
        specializations_by_backend={"cpp": {}},
        extensions={},
        immediate_split_names=frozenset(),
    )

    plan = cpp_profile_detection_plan((profile,), gate_registry=registry)
    rendered = _cpp_profile_auto_modes((emitted,), plan)

    assert plan.auto_choices == ("auto-future-accelerator",)
    assert plan.helper_assets == ("future_accelerator.cmake",)
    assert "_tsl_detect_future_accelerator(" in rendered
    assert "future_accelerator auto-detection failed" in rendered
    assert "_tsl_detect_profile_gate" not in rendered
