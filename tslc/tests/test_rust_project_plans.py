"""Trusted-plan boundary tests for Rust project artifact rendering."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable

import pytest

from tslc.api import generate_project
from tslc.backend import (
    rust_api_planner,
    rust_capability,
    rust_dispatch,
    rust_policy_selection,
    rust_static_selection,
    rust_validation,
)
from tslc.backend.rust_policy_manifest import load_rust_policy_manifest
from tslc.compiler_assets import RenderAssets
from tslc.diagnostics import has_errors
from tslc.render.rust_benchmark_layout import plan_rust_benchmark_layout
from tslc.render.rust_policy_consumption import (
    EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
)
from tslc.render.rust_project import _rust_artifacts

RUST_POLICY_MANIFEST = load_rust_policy_manifest()


def test_artifact_pass_plans_once_and_renderer_consumes_frozen_plans(
    data_root: Path,
    machine_profiles_path: Path,
    render_assets: RenderAssets,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    planner_names = (
        "plan_rust_policy_selection",
        "plan_rust_static_selection",
        "plan_rust_facade",
        "plan_rust_dispatch",
        "plan_rust_policy_consumption",
        "plan_rust_policy_consumption_render",
        "plan_rust_benchmark_layout",
    )
    originals: dict[str, Callable[..., object]] = {
        name: getattr(rust_capability, name) for name in planner_names
    }
    counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()

    for name, original in originals.items():
        def counted(
            *args: object,
            _name: str = name,
            _original: Callable[..., object] = original,
            **kwargs: object,
        ) -> object:
            counts[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(rust_capability, name, counted)

    for name in ("plan_rust_static_selection", "validate_rust_facade"):
        original = getattr(rust_validation, name)

        def counted_validation(
            *args: object,
            _name: str = name,
            _original: Callable[..., object] = original,
            **kwargs: object,
        ) -> object:
            validation_counts[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(rust_validation, name, counted_validation)

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["scalar"],
        backends=["rust"],
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert counts == Counter({name: 1 for name in planner_names})
    assert validation_counts == Counter(
        {
            "plan_rust_static_selection": 1,
            "validate_rust_facade": 1,
        }
    )

    profiles = result.emitted_profiles
    selection = rust_policy_selection.plan_rust_policy_selection(
        profiles, RUST_POLICY_MANIFEST
    )
    static = rust_static_selection.plan_rust_static_selection(profiles)
    facade = rust_api_planner.plan_rust_facade(profiles, static)
    dispatch = rust_dispatch.plan_rust_dispatch(
        profiles,
        static,
        facade,
    )
    benchmark_layout = plan_rust_benchmark_layout(
        tuple(profile.profile.name for profile in profiles)
    )

    def fail_if_replanned(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("trusted Rust rendering must not replan")

    monkeypatch.setattr(
        rust_api_planner,
        "plan_rust_facade",
        fail_if_replanned,
    )
    monkeypatch.setattr(
        rust_dispatch,
        "plan_rust_dispatch",
        fail_if_replanned,
    )
    first = _rust_artifacts(
        profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=selection,
        static_selection_plan=static,
        facade_plan=facade,
        dispatch_plan=dispatch,
        consumption_plan=EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
        benchmark_layout_plan=benchmark_layout,
    )
    second = _rust_artifacts(
        profiles,
        render_assets,
        media_type="text/rust",
        selection_plan=selection,
        static_selection_plan=static,
        facade_plan=facade,
        dispatch_plan=dispatch,
        consumption_plan=EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN,
        benchmark_layout_plan=benchmark_layout,
    )

    assert first == second

def test_trusted_rust_project_renderer_has_one_production_caller() -> None:
    source_root = Path(__file__).parents[1] / "src" / "tslc"
    callers = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*.py")
        if "_rust_artifacts(" in path.read_text(encoding="utf-8")
    }
    renderer_source = (
        source_root / "render" / "rust_project.py"
    ).read_text(encoding="utf-8")

    assert callers == {
        "backend/rust_capability.py",
        "render/rust_project.py",
    }
    assert "plan_rust_facade" not in renderer_source
    assert "plan_rust_dispatch" not in renderer_source
    assert "validate_rust_" not in renderer_source
