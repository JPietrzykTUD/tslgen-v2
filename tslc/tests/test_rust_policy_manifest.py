"""Strict packaged-evidence tests for Rust policy configuration."""

from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tslc.backend.rust_policy_manifest import (
    load_rust_policy_manifest,
    parse_rust_policy_manifest,
)


def _packaged_data() -> dict[str, object]:
    text = (
        files("tslc.backend")
        .joinpath("policy_assets", "rust_policy.json")
        .read_text(encoding="utf-8")
    )
    value = json.loads(text)
    assert isinstance(value, dict)
    return value


def test_packaged_manifest_loads_once_through_injectable_reader() -> None:
    calls = 0
    text = json.dumps(_packaged_data())

    def read_text() -> str:
        nonlocal calls
        calls += 1
        return text

    loaded = load_rust_policy_manifest(read_text)

    assert calls == 1
    assert loaded == load_rust_policy_manifest()


def test_importing_rust_backend_does_not_read_policy_asset() -> None:
    source_root = Path(__file__).parents[1] / "src"
    script = """
import importlib.resources

def reject_eager_read(*args, **kwargs):
    raise AssertionError("Rust policy asset was read during backend import")

importlib.resources.files = reject_eager_read
import tslc.backend.rust_capability
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source_root)

    completed = subprocess.run(
        (sys.executable, "-c", script),
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda data: data.update({"version": 99}),
            "unsupported Rust policy manifest version",
        ),
        (
            lambda data: data.update({"unknown": True}),
            "unknown fields: unknown",
        ),
        (
            lambda data: data["benchmark_admissions"][0].update(
                {"scenario_family": "invented"}
            ),
            "unknown value 'invented'",
        ),
        (
            lambda data: data["selection_pilots"][0].update({"lanes": True}),
            "lanes must be an integer",
        ),
    ),
)
def test_manifest_rejects_unknown_or_mistyped_evidence(
    mutate,
    message: str,
) -> None:
    data = _packaged_data()
    mutate(data)

    with pytest.raises(ValueError, match=message):
        parse_rust_policy_manifest(json.dumps(data))


def test_manifest_rejects_duplicate_admissions_and_ambiguous_pilots() -> None:
    admissions = _packaged_data()
    admission = deepcopy(admissions["benchmark_admissions"][0])
    admissions["benchmark_admissions"].append(admission)
    with pytest.raises(ValueError, match="duplicate.*benchmark admissions"):
        parse_rust_policy_manifest(json.dumps(admissions))

    pilots = _packaged_data()
    duplicate = deepcopy(pilots["selection_pilots"][0])
    duplicate["pilot_id"] = "ambiguous_copy"
    pilots["selection_pilots"].append(duplicate)
    with pytest.raises(ValueError, match="ambiguous Rust policy pilots"):
        parse_rust_policy_manifest(json.dumps(pilots))
