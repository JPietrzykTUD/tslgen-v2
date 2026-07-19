"""Typed specialization inventory calculation and command behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Implementation, Primitive
from tslc.catalog.target_families import (
    ProfileFamilyCapability,
    TargetFamilyCatalog,
)
from tslc.maintenance import coverage_inventory
from tslc.maintenance.build_verified import (
    BUILD_VERIFIED_PRIMITIVE_SETS,
    build_verified_primitives,
)
from tslc.maintenance.coverage_inventory_report import (
    CoverageInventory,
    build_coverage_inventory,
)
from tslc.maintenance.coverage_inventory_render import (
    render_json,
    render_markdown,
    render_text,
)
from tslc.output.artifacts import ArtifactSet
from tslc.pipeline import CoverageEntry, GenerationResult, SkippedEntry


def _primitive(name: str) -> Primitive:
    return Primitive(
        name=name,
        signature="v:=(v,v)",
        parameters=("left", "right"),
        attribute_keys=(),
        implementations=(
            Implementation(
                selector_path=("sse", "si32"),
                extension="sse",
                type_group="si32",
                body_text="complete(left);",
            ),
        ),
    )


def _result() -> GenerationResult:
    coverage = (
        CoverageEntry("unit", "cpp", "add", "sse", "si32"),
        CoverageEntry("unit", "cpp", "add", "sse", "f32"),
        CoverageEntry("unit", "cpp", "sub", "sse", "si32"),
        CoverageEntry("unit", "rust", "add", "sse", "si32"),
        CoverageEntry("unit", "rust", "sub", "sse", "si32"),
        CoverageEntry("cpp_only", "cpp", "add", "sse", "si32"),
    )
    skipped = (
        SkippedEntry(
            "unit",
            "rust",
            "add",
            "sse",
            "f32",
            "not lowered",
        ),
        SkippedEntry(
            "unit",
            "rust",
            "sub",
            "sse",
            "f64",
            "intentionally deferred",
            status="policy_deferred",
        ),
    )
    return GenerationResult(
        artifacts=ArtifactSet.create(()),
        rendered=None,
        diagnostics=(),
        coverage=coverage,
        skipped=skipped,
    )


def _inventory() -> CoverageInventory:
    catalog = Catalog(
        primitives=(_primitive("add"), _primitive("sub")),
        type_groups={},
        extensions={},
        type_spellings={},
        translations={},
        target_families=TargetFamilyCatalog(
            profile_families={
                "generic": ProfileFamilyCapability("generic", sort_order=0),
                "x86": ProfileFamilyCapability("x86", sort_order=10),
                "aarch64": ProfileFamilyCapability("aarch64", sort_order=20),
            }
        ),
    )
    return build_coverage_inventory(
        catalog,
        _result(),
        machine_profiles=(
            MachineProfile("unit", "x86", frozenset({"sse", "sse2", "avx"}), {}),
            MachineProfile("cpp_only", "generic", frozenset({"NOSIMD-INVALID"}), {}),
            MachineProfile("x86_b", "x86", frozenset({"sse"}), {}),
            MachineProfile("x86_a", "x86", frozenset({"sse"}), {}),
            MachineProfile("arm", "aarch64", frozenset({"neon"}), {}),
        ),
        backends=("cpp", "rust"),
        type_tags=("si32", "f32", "f64"),
        verified_primitives=frozenset({"add"}),
    )


def test_inventory_uses_one_shared_candidate_denominator_per_profile() -> None:
    inventory = _inventory()

    assert inventory.primitive_count == 2
    assert inventory.implementation_count == 2
    assert inventory.emitted_specializations == 6
    assert inventory.average_specializations_per_primitive == 3.0
    assert inventory.aggregate_coverage_percent == pytest.approx(100.0 * 6 / 7)
    assert inventory.mean_primitive_coverage_percent == 90.0
    assert inventory.coverage_gaps == 1
    assert inventory.policy_deferred == 1
    assert inventory.backend_parity is False

    assert tuple(
        (profile.architecture, profile.target_feature_count, profile.profile)
        for profile in inventory.profile_inventory
    ) == (
        ("generic", 1, "cpp_only"),
        ("x86", 1, "x86_a"),
        ("x86", 1, "x86_b"),
        ("x86", 3, "unit"),
        ("aarch64", 1, "arm"),
    )

    by_profile = {profile.profile: profile for profile in inventory.profile_inventory}
    unit = by_profile["unit"]
    cpp, rust = unit.backends
    assert unit.shared_candidates == 3
    assert (cpp.emitted, cpp.shared_candidates, cpp.coverage_percent) == (3, 3, 100.0)
    assert rust.emitted == 2
    assert rust.shared_candidates == 3
    assert rust.coverage_percent == pytest.approx(100.0 * 2 / 3)
    assert rust.lowering_success_percent == pytest.approx(100.0 * 2 / 3)

    cpp_only = by_profile["cpp_only"]
    assert cpp_only.backends[0].coverage_percent == 100.0
    assert cpp_only.backends[1].coverage_percent is None


def test_inventory_renderers_explain_counts_and_emit_stable_json() -> None:
    inventory = _inventory()

    text = render_text(inventory)
    assert "Emitted specializations: 6" in text
    assert "2 / 3 (66.7% shared; 66.7% local)" in text
    assert "—" in text

    markdown = render_markdown(inventory)
    assert "Generated by `tslc coverage inventory --format markdown`." in markdown
    assert "## Profile/backend specialization availability" in markdown
    assert (
        "| `x86` | `unit` | 3 | 3 / 3 (100.0% shared; 100.0% local) | "
        "2 / 3 (66.7% shared; 66.7% local) |"
    ) in markdown

    payload = json.loads(render_json(inventory))
    assert payload["corpus"]["primitives"] == 2
    assert payload["corpus"]["source_primitive_declarations"] == 2
    assert payload["corpus"]["catalog_primitive_variants"] == 2
    assert payload["specializations"]["emitted"] == 6
    profiles = {profile["profile"]: profile for profile in payload["profiles"]}
    assert profiles["cpp_only"]["architecture"] == "generic"
    assert profiles["unit"]["backends"][1]["coverage_percent"] == pytest.approx(
        100.0 * 2 / 3
    )
    assert profiles["cpp_only"]["backends"][1]["coverage_percent"] is None


def test_inventory_command_is_read_only_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "inventory.md"
    monkeypatch.setattr(
        coverage_inventory,
        "collect_inventory",
        lambda **kwargs: (_inventory(), ()),
    )

    status = coverage_inventory.main(
        [
            "--sources",
            str(tmp_path),
            "--machine-profiles",
            str(tmp_path / "profiles.json"),
            "--profiles",
            "unit,cpp_only",
            "--backends",
            "cpp,rust",
        ]
    )

    assert status == 0
    assert "TSLC coverage inventory" in capsys.readouterr().out
    assert not output.exists()


def test_inventory_update_and_check_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "inventory.md"
    monkeypatch.setattr(
        coverage_inventory,
        "collect_inventory",
        lambda **kwargs: (_inventory(), ()),
    )

    assert coverage_inventory.main(["--update", "--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == render_markdown(
        _inventory(), tracked=True
    )
    capsys.readouterr()

    assert coverage_inventory.main(["--check", "--output", str(output)]) == 0
    assert "coverage inventory is current" in capsys.readouterr().out


def test_inventory_rejects_output_without_a_write_or_check_mode(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc:
        coverage_inventory.main(["--output", str(tmp_path / "inventory.md")])

    assert exc.value.code == 2


def test_build_verified_evidence_is_typed_and_consumed_by_the_inventory() -> None:
    """The inventory's verified column comes from the shared typed constant,
    not from sniffing test-source syntax."""

    assert BUILD_VERIFIED_PRIMITIVE_SETS, "typed build evidence must not be empty"
    for test_name, names in BUILD_VERIFIED_PRIMITIVE_SETS.items():
        assert names, f"{test_name} claims build verification without primitives"
        assert all(isinstance(name, str) and name for name in names), test_name
        assert len(set(names)) == len(names), f"{test_name} repeats primitives"

    union = build_verified_primitives()
    assert union == frozenset(
        name for names in BUILD_VERIFIED_PRIMITIVE_SETS.values() for name in names
    )
    assert "add" in union and "load" in union

    # Every entry is keyed by the generated-build test that consumes it, and
    # that test looks its own entry up by name, so the constant cannot drift
    # from what the gate compiles.
    build_test_source = (
        Path(__file__).with_name("test_build_verify.py").read_text(encoding="utf-8")
    )
    for test_name in BUILD_VERIFIED_PRIMITIVE_SETS:
        assert f"def {test_name}(" in build_test_source, (
            f"{test_name} is not a generated-build test"
        )
        assert f'_build_verified("{test_name}")' in build_test_source, (
            f"{test_name} does not consume its build-verified entry"
        )

    # collect_inventory wires the same evidence into the report.
    assert coverage_inventory.build_verified_primitives is build_verified_primitives
