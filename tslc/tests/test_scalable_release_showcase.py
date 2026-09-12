"""Release showcase for one vector-length-agnostic filter/gather/transform binary."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import subprocess
import tarfile

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.catalog.machine_profiles import MachineProfile
from tslc.diagnostics import has_errors


pytestmark = pytest.mark.generated_build

_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "release"
    / "scalable_filter_gather_transform.cpp"
)
_PRIMITIVES = (
    "add",
    "compress_store",
    "gather",
    "greater_than",
    "load",
    "mask_false",
    "mask_population_count",
    "mul",
    "set1",
    "set_mask_lane",
    "store",
)
_TOOLS = {
    "sve": (
        "aarch64-linux-gnu-g++",
        "qemu-aarch64",
        Path("/usr/aarch64-linux-gnu"),
    ),
    "rvv": (
        "riscv64-linux-gnu-g++",
        "qemu-riscv64",
        Path("/usr/riscv64-linux-gnu"),
    ),
}


@pytest.mark.parametrize("profile_name", ("sve", "rvv"))
def test_scalable_filter_gather_transform_matches_oracle_at_three_vector_lengths(
    profile_name: str,
    data_root: Path,
    machine_profiles_path: Path,
    machine_profiles: Mapping[str, MachineProfile],
    tmp_path: Path,
) -> None:
    compiler_name, runner_name, sysroot = _TOOLS[profile_name]
    compiler = shutil.which(compiler_name)
    runner_path = shutil.which(runner_name)
    if compiler is None or runner_path is None or not sysroot.is_dir():
        pytest.skip(
            f"{profile_name} showcase needs {compiler_name}, {runner_name}, "
            f"and {sysroot}"
        )
    profile = machine_profiles[profile_name]
    assert profile.runner is not None
    assert len(profile.runner.executions) == 3

    release_archive = os.environ.get("TSL_RELEASE_ARCHIVE")
    if release_archive:
        generated = _extract_release_bundle(
            Path(release_archive), profile_name=profile_name, destination=tmp_path
        )
    else:
        result = generate_project(
            [data_root],
            machine_profiles_path=machine_profiles_path,
            primitives=_PRIMITIVES,
            profiles=(profile_name,),
            type_tags=("si32",),
            backends=("cpp",),
        )
        assert not has_errors(result.diagnostics), result.diagnostics
        generated = tmp_path / "generated"
        report = write_artifacts(result.artifacts, generated)
        assert not has_errors(report.diagnostics), report.diagnostics

    binary = tmp_path / f"scalable-showcase-{profile_name}"
    compiled = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fwrapv",
            *profile.flags_for_backend("cpp"),
            f"-DTSL_PROFILE_{profile_name.upper()}",
            "-I",
            str(generated / "cpp" / "include"),
            str(_FIXTURE),
            "-o",
            str(binary),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stderr

    observations: list[dict[str, int]] = []
    for execution in profile.runner.executions:
        assert execution.vector_bits is not None
        executed = subprocess.run(
            (
                runner_path,
                "-L",
                str(sysroot),
                "-cpu",
                execution.profile,
                *execution.args,
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert executed.returncode == 0, (
            f"{profile_name}/{execution.name} showcase failed: "
            f"stdout={executed.stdout!r} stderr={executed.stderr!r}"
        )
        payload = json.loads(executed.stdout)
        expected_lanes = execution.vector_bits // 32
        assert payload["runtime_lanes"] == expected_lanes
        assert payload["input_count"] == expected_lanes * 3 + 2
        assert payload["selected"] == expected_lanes * 2 + 1
        assert payload["tail"] == 1
        assert payload["output_digest"] != 0
        observations.append(payload)

    assert len({item["runtime_lanes"] for item in observations}) == 3


def _extract_release_bundle(
    archive_path: Path, *, profile_name: str, destination: Path
) -> Path:
    assert archive_path.is_file(), f"release archive does not exist: {archive_path}"
    bundle_id = f"cpp-{profile_name}"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members}
        assert len(roots) == 1, "release archive must contain exactly one root"
        archive_root = next(iter(roots))
        manifest_name = f"{archive_root}/.tsl-release-bundles.json"
        manifest_members = [
            member for member in members if member.name == manifest_name
        ]
        assert len(manifest_members) == 1
        manifest_handle = archive.extractfile(manifest_members[0])
        assert manifest_handle is not None
        manifest = json.load(manifest_handle)
        records = [item for item in manifest["bundles"] if item["id"] == bundle_id]
        assert len(records) == 1
        record = records[0]
        assert record["backend"] == "cpp"
        assert record["profiles"] == [profile_name]
        assert record["generated_scope"] == [profile_name]
        relative = PurePosixPath(record["path"])
        assert relative == PurePosixPath("bundles") / bundle_id
        bundle_prefix = PurePosixPath(archive_root) / relative
        selected = [
            member
            for member in members
            if PurePosixPath(member.name) == bundle_prefix
            or bundle_prefix in PurePosixPath(member.name).parents
        ]
        assert selected, f"release archive has no {bundle_id} members"
        assert all(member.isdir() or member.isfile() for member in selected)
        inner_name = f"{bundle_prefix.as_posix()}/.tslc-manifest.json"
        inner_members = [member for member in selected if member.name == inner_name]
        assert len(inner_members) == 1
        inner_handle = archive.extractfile(inner_members[0])
        assert inner_handle is not None
        assert sha256(inner_handle.read()).hexdigest() == record[
            "artifact_manifest_sha256"
        ]
        archive.extractall(destination, members=selected, filter="data")
    generated = destination / bundle_prefix
    assert (generated / "cpp" / "CMakeLists.txt").is_file()
    public_api = json.loads(
        (generated / "cpp" / "public-api.json").read_text(encoding="utf-8")
    )
    assert public_api["backend"] == "cpp"
    assert public_api["scope"] == [profile_name]
    return generated
