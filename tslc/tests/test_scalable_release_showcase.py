"""Release showcase for one vector-length-agnostic filter/gather/transform binary."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import shutil
import subprocess

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
            f"{profile_name} showcase needs {compiler_name}, {runner_name}, and {sysroot}"
        )
    profile = machine_profiles[profile_name]
    assert profile.runner is not None
    assert len(profile.runner.executions) == 3

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
