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
_DISTRIBUTABLE_GENERATOR = (
    "bash .github/scripts/generate_distributable_project.sh"
)


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
        supported_profiles = [
            profile["name"]
            for family_profiles in source.values()
            for profile in family_profiles
            if _supports_backend(profile, backend)
        ]
        oneapi_shard_profiles = {
            profile
            for name, profiles in backend_shards.items()
            if "-oneapi-fpga-" in name
            for profile in profiles
        }
        assert sorted(emitted_profiles) == sorted(supported_profiles)
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
            assert all(
                len(profiles)
                <= (3 if name.startswith("cpp-x86-oneapi-fpga-") else 6)
                for name, profiles in backend_shards.items()
            )

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
    rust_supported_profiles = [
        profile["name"]
        for family_profiles in source.values()
        for profile in family_profiles
        if _supports_backend(profile, "rust")
    ]
    assert rust_profile_counts == Counter(
        {
            profile: 2 if profile in _RUST_COEXISTENCE_PROFILES else 1
            for profile in rust_supported_profiles
        }
    )

    assert [
        shard for shard in exhaustive_shards if "rvv" in shard["profiles"].split(",")
    ] == [
        {
            "backend": "cpp",
            "name": "cpp-riscv-0",
            "profiles": "rvv",
        }
    ]

    values_workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    assert 'TSLC_QEMU_RISCV64="/usr/bin/qemu-riscv64"' in values_workflow
    assert "vlen=256,elen=64" in values_workflow
    assert "timeout --signal=KILL 60s /usr/bin/qemu-riscv64" in values_workflow


def test_package_and_docs_generate_a_supported_distributable_profile_set() -> None:
    helper = Path(".github/scripts/generate_distributable_project.sh").read_text(
        encoding="utf-8"
    )
    assert "-f .github/scripts/profile_shards.jq" in helper
    assert '.purpose == "coexistence"' in helper
    assert helper.count("./dev.sh generate") == 1
    assert '--backend-profiles "rust=$rust_profiles"' in helper
    assert "--backends cpp,rust" in helper

    package_workflow = Path(".github/workflows/generated-package.yml").read_text(
        encoding="utf-8"
    )
    assert _DISTRIBUTABLE_GENERATOR in package_workflow
    assert package_workflow.count(_DISTRIBUTABLE_GENERATOR) == 1
    assert not Path(".github/workflows/docs.yml").exists()
    assert "./dev.sh generate --backends cpp,rust" not in package_workflow
    assert "./dev.sh document" not in package_workflow
    assert "python -m tslc.maintenance.documentation" in package_workflow
    assert "Download generated package" in package_workflow

    consumer_verifier = Path(
        "supplementary/ci/verify_generated_consumers.sh"
    ).read_text(encoding="utf-8")
    assert 'default-features = false, features = ["scalar"]' not in consumer_verifier


def test_rust_examples_use_static_profile_selection_api() -> None:
    manifest = Path("examples/rust/Cargo.toml").read_text(encoding="utf-8")
    assert 'features = ["scalar"]' not in manifest

    examples = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path("examples/rust/src/bin").glob("*.rs"))
    )
    assert "dataparallel::native()" not in examples
    assert "BlendImpl" not in examples
    assert "SelectImpl" in examples

    readme = Path("examples/rust/README.md").read_text(encoding="utf-8")
    assert "profile-named Cargo features are no longer part of the API" in readme
    assert "dataparallel::native()" not in readme
    assert "BlendImpl" not in readme


def _supports_backend(profile: dict[str, object], backend: str) -> bool:
    supported = profile.get("supported_backends", ["cpp", "rust"])
    assert isinstance(supported, list)
    return backend in supported


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
                [
                    profile
                    for profile in profiles
                    if not profile.get("auto_detect_gate")
                    and _supports_backend(profile, backend)
                ],
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
                    and _supports_backend(profile, backend)
                ],
            )
            for gate in gates
        )
        for group_name, group_profiles in groups:
            names = tuple(str(profile["name"]) for profile in group_profiles)
            effective_chunk_size = (
                3
                if backend == "cpp" and group_name.endswith("-oneapi-fpga")
                else chunk_size
            )
            for index, start in enumerate(range(0, len(names), effective_chunk_size)):
                expected[f"{backend}-{group_name}-{index}"] = names[
                    start : start + effective_chunk_size
                ]
    return expected
