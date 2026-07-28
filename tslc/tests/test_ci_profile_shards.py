"""GitHub Actions generated-profile shard coverage."""

from __future__ import annotations

from collections import Counter
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_RUST_COEXISTENCE_NAME = "rust-x86-coexistence"
_RUST_COEXISTENCE_PROFILES = ("sse", "sse2", "sse3", "avx", "avx2", "knl")


def test_generated_profile_shards_preserve_exhaustive_and_coexistence_lanes(
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
    coexistence_shards = [
        shard for shard in shards if shard.get("purpose") == "coexistence"
    ]
    assert coexistence_shards == [
        {
            "backend": "rust",
            "name": _RUST_COEXISTENCE_NAME,
            "profiles": ",".join(_RUST_COEXISTENCE_PROFILES),
            "purpose": "coexistence",
        }
    ]
    exhaustive_shards = [
        shard for shard in shards if shard.get("purpose") != "coexistence"
    ]
    assert all("purpose" not in shard for shard in exhaustive_shards)
    shard_profiles = {
        shard["name"]: tuple(profile for profile in shard["profiles"].split(",") if profile)
        for shard in exhaustive_shards
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

    assert {shard["backend"] for shard in exhaustive_shards} == {"cpp", "rust"}
    for backend in ("cpp", "rust"):
        backend_shards = {
            name: profiles
            for name, profiles in shard_profiles.items()
            if name.startswith(f"{backend}-")
        }
        emitted_profiles = [
            profile for profiles in backend_shards.values() for profile in profiles
        ]
        oneapi_shard_profiles = {
            profile
            for name, profiles in backend_shards.items()
            if "-oneapi-fpga-" in name
            for profile in profiles
        }
        assert sorted(emitted_profiles) == sorted(all_profiles)
        assert len(emitted_profiles) == len(set(emitted_profiles))
        assert f"{backend}-x86-oneapi-fpga-0" in backend_shards
        assert oneapi_shard_profiles == oneapi_profiles
        assert all(
            not (set(profiles) & oneapi_profiles)
            for name, profiles in backend_shards.items()
            if "-oneapi-fpga-" not in name
        )
        if backend == "rust":
            assert all(len(profiles) == 1 for profiles in backend_shards.values())
        else:
            assert all(len(profiles) <= 6 for profiles in backend_shards.values())

    assert {
        name: profiles
        for name, profiles in shard_profiles.items()
        if name.startswith("cpp-")
    } == _expected_exhaustive_shards(source, backend="cpp", chunk_size=6)
    assert {
        name: profiles
        for name, profiles in shard_profiles.items()
        if name.startswith("rust-")
    } == _expected_exhaustive_shards(source, backend="rust", chunk_size=1)

    rust_profile_counts = Counter(
        profile
        for shard in shards
        if shard["backend"] == "rust"
        for profile in shard["profiles"].split(",")
        if profile
    )
    assert rust_profile_counts == Counter(
        {
            profile: 2 if profile in _RUST_COEXISTENCE_PROFILES else 1
            for profile in all_profiles
        }
    )


def _expected_exhaustive_shards(
    source: dict[str, list[dict[str, object]]],
    *,
    backend: str,
    chunk_size: int,
) -> dict[str, tuple[str, ...]]:
    expected: dict[str, tuple[str, ...]] = {}
    for family, profiles in source.items():
        groups: list[tuple[str, list[dict[str, object]]]] = [
            (
                family,
                [profile for profile in profiles if not profile.get("auto_detect_gate")],
            )
        ]
        gates = sorted(
            {
                str(profile["auto_detect_gate"])
                for profile in profiles
                if profile.get("auto_detect_gate")
            }
        )
        groups.extend(
            (
                f"{family}-{gate.replace('_', '-')}",
                [
                    profile
                    for profile in profiles
                    if profile.get("auto_detect_gate") == gate
                ],
            )
            for gate in gates
        )
        for group_name, group_profiles in groups:
            names = tuple(str(profile["name"]) for profile in group_profiles)
            for index, start in enumerate(range(0, len(names), chunk_size)):
                expected[f"{backend}-{group_name}-{index}"] = names[
                    start : start + chunk_size
                ]
    return expected
