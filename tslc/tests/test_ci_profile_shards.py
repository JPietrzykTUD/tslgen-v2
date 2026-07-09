"""GitHub Actions generated-profile shard coverage."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_generated_profile_shards_expose_oneapi_fpga_lane(
    machine_profiles_path: Path,
) -> None:
    jq = shutil.which("jq")
    if jq is None:
        pytest.skip("jq is required to exercise the GitHub Actions profile shard script")

    completed = subprocess.run(
        (
            jq,
            "-c",
            "-f",
            ".github/scripts/profile_shards.jq",
            str(machine_profiles_path),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    shards = json.loads(completed.stdout)
    shard_profiles = {
        shard["name"]: tuple(profile for profile in shard["profiles"].split(",") if profile)
        for shard in shards
    }

    with machine_profiles_path.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    all_profiles = [
        profile["name"]
        for family_profiles in source.values()
        for profile in family_profiles
    ]
    oneapi_profiles = {
        profile["name"]
        for family_profiles in source.values()
        for profile in family_profiles
        if profile.get("auto_detect_gate") == "oneapi_fpga"
    }

    emitted_profiles = [
        profile for profiles in shard_profiles.values() for profile in profiles
    ]
    oneapi_shard_profiles = {
        profile
        for name, profiles in shard_profiles.items()
        if "-oneapi-fpga-" in name
        for profile in profiles
    }
    assert sorted(emitted_profiles) == sorted(all_profiles)
    assert len(emitted_profiles) == len(set(emitted_profiles))
    assert "x86-oneapi-fpga-0" in shard_profiles
    assert oneapi_shard_profiles == oneapi_profiles
    assert all(
        not (set(profiles) & oneapi_profiles)
        for name, profiles in shard_profiles.items()
        if "-oneapi-fpga-" not in name
    )
