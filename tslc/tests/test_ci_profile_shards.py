"""GitHub Actions generated-profile shard coverage."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

_RUST_COEXISTENCE_NAME = "rust-release-coexistence"
_RELEASE_POLICY_PATH = Path("supplementary/release/tsl-v1-policy.json")
_RELEASE_POLICY = json.loads(_RELEASE_POLICY_PATH.read_text(encoding="utf-8"))
_RUST_COEXISTENCE_PROFILES = tuple(
    _RELEASE_POLICY["backend_profiles"]["rust"]["profiles"]
)
_RUST_RELEASE_QUALITY_CHUNK_SIZE = 4
_ROOT_CONFIG = tomllib.loads(Path("tslc.toml").read_text(encoding="utf-8"))
_REFERENCE_GENERATOR = (
    "bash .github/scripts/generate_release_reference_project.sh"
)
_BUNDLE_GENERATOR = "python .github/scripts/build_release_bundles.py"


def test_project_default_rust_scope_matches_release_coexistence_policy() -> None:
    assert tuple(_ROOT_CONFIG["tslc"]["backend_profiles"]["rust"]) == (
        _RUST_COEXISTENCE_PROFILES
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
            "--slurpfile",
            "release_policy",
            str(_RELEASE_POLICY_PATH),
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
    rust_release_quality_shards = [
        shard for shard in shards if shard.get("purpose") == "release-quality"
    ]
    expected_quality_profiles = [
        _RUST_COEXISTENCE_PROFILES[index : index + _RUST_RELEASE_QUALITY_CHUNK_SIZE]
        for index in range(
            0,
            len(_RUST_COEXISTENCE_PROFILES),
            _RUST_RELEASE_QUALITY_CHUNK_SIZE,
        )
    ]
    assert [shard["name"] for shard in rust_release_quality_shards] == [
        f"rust-release-quality-{index}"
        for index in range(len(expected_quality_profiles))
    ]
    assert all(
        shard["backend"] == "rust"
        and len(shard["profiles"].split(","))
        <= _RUST_RELEASE_QUALITY_CHUNK_SIZE
        for shard in rust_release_quality_shards
    )
    assert [
        tuple(shard["profiles"].split(","))
        for shard in rust_release_quality_shards
    ] == expected_quality_profiles
    exhaustive_shards = [
        shard for shard in shards if "purpose" not in shard
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
            profile: 3 if profile in _RUST_COEXISTENCE_PROFILES else 1
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
    sve_profiles = {"sve", "sve128", "sve256", "sve512"}
    assert not any(
        sve_profiles & set(shard["profiles"].split(","))
        for shard in exhaustive_shards
        if shard["backend"] == "rust"
    )

    values_workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    assert 'quality_args+=(--quality)' in values_workflow
    assert 'TSLC_QEMU_RISCV64="/usr/bin/qemu-riscv64"' in values_workflow
    assert "vlen=256,elen=64" not in values_workflow
    assert "timeout --signal=KILL 60s /usr/bin/qemu-riscv64" not in values_workflow
    rvv = next(
        profile
        for family_profiles in source.values()
        for profile in family_profiles
        if profile["name"] == "rvv"
    )
    assert [
        rvv["runner"]["vector_bits"],
        *(variant["vector_bits"] for variant in rvv["runner"]["variants"]),
    ] == [128, 256, 512]


def test_rust_release_quality_runs_msrv_and_current_stable() -> None:
    workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    section = workflow.split("  generated-rust-release-quality:\n", 1)[1].split(
        "\n  generated-", 1
    )[0]
    dockerfile = Path(".devcontainer/Dockerfile").read_text(encoding="utf-8")

    assert "rust_release_quality_shards:" in workflow
    assert 'select(.purpose != "release-quality")' in workflow
    assert 'select(.purpose == "release-quality")' in workflow
    assert (
        "profile_shard: "
        "${{ fromJson(needs['profile-shards'].outputs.rust_release_quality_shards) }}"
        in section
    )
    assert "name: stable" in section
    assert "name: 1.89.0" in section
    assert 'RUSTUP_TOOLCHAIN="${{ matrix.toolchain.name }}"' in section
    assert (
        'TSLC_RUST_RELEASE_PROFILES="${{ matrix.profile_shard.profiles }}"'
        in section
    )
    assert '--profiles "${TSLC_RUST_RELEASE_PROFILES}"' in section
    assert "--quality" in section
    assert "./dev.sh test" in section
    assert "ARG RUST_MSRV=1.89.0" in dockerfile
    assert 'rustup toolchain install "${RUST_MSRV}"' in dockerfile
    msrv_targets = dockerfile.split(
        'rustup target add --toolchain "${RUST_MSRV}"', 1
    )[1].split(";", 1)[0]
    assert "aarch64-unknown-linux-musl" in msrv_targets
    assert "wasm32-wasip1" in msrv_targets


def test_scalable_showcase_is_a_required_generated_profile_gate() -> None:
    workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    section = workflow.split("  generated-scalable-showcase:\n", 1)[1].split(
        "\n  generated-", 1
    )[0]
    required = workflow.split("  required-generated:\n", 1)[1]

    assert "needs.scope.outputs.generated_profiles == 'true'" in section
    assert "tslc/tests/test_scalable_release_showcase.py" in section
    assert "tslc/tests/test_rvv_downstream_consumer.py" in section
    assert "--run-generated-builds" in section
    assert "generated-scalable-showcase" in required
    assert "needs['generated-scalable-showcase'].result" in required


def test_clang_and_msvc_quality_matrices_cover_non_oneapi_x86_profiles(
    machine_profiles_path: Path,
) -> None:
    jq = shutil.which("jq")
    if jq is None:
        pytest.skip("jq is required to exercise the GitHub Actions profile shard script")
    completed = subprocess.run(
        (
            jq,
            "-c",
            "--slurpfile",
            "release_policy",
            str(_RELEASE_POLICY_PATH),
            "-f",
            ".github/scripts/profile_shards.jq",
            str(machine_profiles_path),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    shards = json.loads(completed.stdout)
    quality_shards = [
        shard
        for shard in shards
        if shard["backend"] == "cpp"
        and shard["name"].startswith("cpp-x86-")
        and "oneapi-fpga" not in shard["name"]
    ]
    matrix_profiles = {
        profile
        for shard in quality_shards
        for profile in shard["profiles"].split(",")
    }
    source = json.loads(machine_profiles_path.read_text(encoding="utf-8"))
    expected = {
        profile["name"]
        for profile in source["x86"]
        if profile.get("backend_compiler_roles", {}).get("cpp") is None
        and _supports_backend(profile, "cpp")
    }
    assert matrix_profiles == expected

    workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    assert 'x86_quality_shards="$(' in workflow
    assert 'and ((.name | contains("oneapi-fpga")) | not)' in workflow
    for job, runner, compiler in (
        ("generated-msvc-quality", "windows-2022", "cl.exe"),
        ("generated-clang-quality", "ubuntu-latest", "/usr/bin/clang++-21"),
    ):
        section = workflow.split(f"  {job}:\n", 1)[1].split("\n  generated-", 1)[0]
        assert f"runs-on: {runner}" in section
        assert "fromJson(needs['profile-shards'].outputs.x86_quality_shards)" in section
        assert f"--compiler cpp={compiler}" in section
        assert "--quality" in section


def test_package_and_docs_generate_contract_owned_reference_and_bundles() -> None:
    helper = Path(".github/scripts/generate_release_reference_project.sh").read_text(
        encoding="utf-8"
    )
    assert "python -m tslc release contract --format json" in helper
    assert helper.count("./dev.sh generate") == 1
    assert '--backend-profiles "cpp=$cpp_profiles"' in helper
    assert '--backend-profiles "rust=$rust_profiles"' in helper
    assert '--profiles "$all_profiles"' in helper
    assert "--backends cpp,rust" in helper

    values_workflow = Path(".github/workflows/generated-values.yml").read_text(
        encoding="utf-8"
    )
    assert "--slurpfile release_policy supplementary/release/tsl-v1-policy.json" in (
        values_workflow
    )

    package_workflow = Path(".github/workflows/generated-package.yml").read_text(
        encoding="utf-8"
    )
    assert _REFERENCE_GENERATOR in package_workflow
    assert package_workflow.count(_REFERENCE_GENERATOR) == 1
    assert _BUNDLE_GENERATOR in package_workflow
    assert package_workflow.count(_BUNDLE_GENERATOR) == 1
    assert not Path(".github/workflows/docs.yml").exists()
    assert "./dev.sh generate --backends cpp,rust" not in package_workflow
    assert "./dev.sh document" not in package_workflow
    assert "python -m tslc.maintenance.documentation" in package_workflow
    assert "tsl-generated-reference-${{ github.sha }}" in package_workflow
    docs_extract_step = package_workflow.split("      - name: Extract generated package\n", 1)[
        1
    ].split("\n      - name:", 1)[0]
    assert "--strip-components=1" in docs_extract_step

    consumer_verifier = Path(
        "supplementary/ci/verify_generated_consumers.sh"
    ).read_text(encoding="utf-8")
    assert 'default-features = false, features = ["scalar"]' not in consumer_verifier
    for profile in ("scalar", "avx2", "sve", "rvv"):
        assert f"build_cpp_consumer {profile}" in consumer_verifier
    assert "  wasm32-simd128 \\\n" in consumer_verifier
    assert "load_checked<Vec, false>" in consumer_verifier
    assert "store_checked<Vec, false>" in consumer_verifier
    assert "supplementary/docs/site/checked_api_example.cpp" in consumer_verifier
    assert "tsl_cpp_documented_checked_example" in consumer_verifier
    assert "package_paths_before" in consumer_verifier
    assert "package_paths_after" in consumer_verifier
    assert "tsl-v1-package-probe.txt" in consumer_verifier

    archive_verifier = Path(
        "supplementary/ci/verify_release_archive_consumers.sh"
    ).read_text(encoding="utf-8")
    assert "tar -xzf" in archive_verifier
    assert '"$archive_root/bundles/cpp-scalar"' in archive_verifier
    assert '"$archive_root/bundles/rust-release"' in archive_verifier
    assert ".tsl-release-bundles.json" in archive_verifier
    assert "archive_cpp_consumer" in archive_verifier
    assert "cargo new" in archive_verifier
    assert 'cargo run --quiet --locked' in archive_verifier
    assert "Consume the packaged archive from clean projects" in package_workflow
    assert "verify_release_archive_consumers.sh" in package_workflow
    assert "Run the scalable showcase from packaged target bundles" in package_workflow
    assert "TSL_RELEASE_ARCHIVE" in Path(
        "tslc/tests/test_scalable_release_showcase.py"
    ).read_text(encoding="utf-8")
    assert '-e TSLC_RELEASE_ARCHIVE="tslctmp/artifacts/tsl-generated-${GITHUB_SHA}.tar.gz"' in (
        package_workflow
    )
    assert '"${TSLC_RELEASE_ARCHIVE}"' in package_workflow


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
