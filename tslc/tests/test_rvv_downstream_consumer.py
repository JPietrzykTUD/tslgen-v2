"""Generated RVV downstream consumer with scalar-oracle checks."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from tslc.api import generate_project, write_artifacts
from tslc.diagnostics import has_errors


pytestmark = pytest.mark.generated_build

_FIXTURE = (
    Path(__file__).parent / "fixtures" / "release" / "rvv_downstream_consumer.cpp"
)


def test_rvv_downstream_consumer_matches_scalar_oracle_at_multiple_vlens(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    compiler = shutil.which("riscv64-linux-gnu-g++")
    qemu = shutil.which("qemu-riscv64")
    sysroot = Path("/usr/riscv64-linux-gnu")
    if compiler is None or qemu is None or not sysroot.is_dir():
        pytest.skip("RISC-V GNU cross compiler, QEMU, and sysroot are required")

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=("add", "extract_value_at", "load", "mul", "store"),
        profiles=("rvv",),
        type_tags=("si32",),
        backends=("cpp",),
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    report = write_artifacts(result.artifacts, tmp_path / "generated")
    assert not has_errors(report.diagnostics), report.diagnostics

    binary = tmp_path / "rvv-downstream-consumer"
    compiled = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-fwrapv",
            "-march=rv64imafdcv",
            "-mabi=lp64d",
            "-mrvv-vector-bits=scalable",
            "-DTSL_PROFILE_RVV",
            "-I",
            str(tmp_path / "generated" / "cpp" / "include"),
            str(_FIXTURE),
            "-o",
            str(binary),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stderr

    for vlen in (128, 256):
        executed = subprocess.run(
            (
                qemu,
                "-L",
                str(sysroot),
                "-cpu",
                f"max,v=true,vext_spec=v1.0,vlen={vlen},elen=64",
                str(binary),
            ),
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert executed.returncode == 0, (
            f"RVV downstream consumer failed at VLEN={vlen}: "
            f"stdout={executed.stdout!r} stderr={executed.stderr!r}"
        )
