from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipcost.config import ExperimentConfig


ROOT = Path(__file__).resolve().parents[3]


def test_smoke_config_is_valid_and_versioned() -> None:
    config = ExperimentConfig.load(
        ROOT / "research" / "pipcost-src" / "configs" / "smoke.json"
    )
    assert config.schema_version == 2
    assert config.tsl_ref == "v0.2.7"
    assert config.profile == "avx2"
    assert config.digest
    assert "batch_native_mask" in config.studies[0].candidate_plans
    assert "fused_mask" in config.studies[0].reference_plans
    assert "scalar_autovec" in config.studies[0].reference_plans


def test_unknown_config_key_is_rejected(tmp_path: Path) -> None:
    source = ROOT / "research" / "pipcost-src" / "configs" / "smoke.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["surprise"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown config keys"):
        ExperimentConfig.load(path)


def test_invalid_batch_value_is_rejected(tmp_path: Path) -> None:
    source = ROOT / "research" / "pipcost-src" / "configs" / "smoke.json"
    value = json.loads(source.read_text(encoding="utf-8"))
    value["studies"][0]["batch_rows"] = [0]
    path = tmp_path / "bad-batch.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="batch_rows"):
        ExperimentConfig.load(path)


@pytest.mark.parametrize(
    ("name", "profile", "lanes"),
    [
        ("pilot-representation-sse2.json", "sse2", 4),
        ("pilot-representation.json", "avx2", 8),
        ("pilot-representation-skylake.json", "skylake", 16),
        ("pilot-batch.json", "avx2", 8),
        ("held-out.json", "avx2", 8),
    ],
)
def test_research_configs_pin_stable_tsl_and_valid_widths(
    name: str,
    profile: str,
    lanes: int,
) -> None:
    config = ExperimentConfig.load(
        ROOT / "research" / "pipcost-src" / "configs" / name
    )
    assert config.tsl_ref == "v0.2.7"
    assert config.profile == profile
    assert config.simd_lanes == lanes
    assert all(study.candidate_plans for study in config.studies)
    assert all(
        set(study.candidate_plans).isdisjoint(study.reference_plans)
        for study in config.studies
    )
