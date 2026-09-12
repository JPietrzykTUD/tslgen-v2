"""ABI/codegen evidence for the C++ checked-value return convention."""

from __future__ import annotations

from pathlib import Path
import platform
import re
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.generated_build

_FIXTURE = Path(__file__).parent / "fixtures" / "checked_api" / "abi_probe.cpp"


def _function(assembly: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)}:.*?^\s*\.size\s+{re.escape(name)}\b",
        assembly,
    )
    assert match is not None, f"assembly has no function body for {name}"
    return match.group(0).lower()


@pytest.mark.parametrize("compiler_name", ("g++", "clang++"))
def test_sysv_vector_return_abi_and_optimized_call_site(
    compiler_name: str,
    tmp_path: Path,
) -> None:
    if platform.machine().lower() not in ("x86_64", "amd64"):
        pytest.skip("the maintained assembly assertions describe x86-64 System V")
    compiler = shutil.which(compiler_name)
    if compiler is None:
        pytest.skip(f"{compiler_name} is not available")
    assembly_path = tmp_path / f"{compiler_name.replace('+', 'p')}.s"
    completed = subprocess.run(
        (
            compiler,
            "-std=c++17",
            "-O3",
            "-mavx2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-S",
            "-masm=intel",
            str(_FIXTURE),
            "-o",
            str(assembly_path),
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assembly = assembly_path.read_text(encoding="utf-8")

    raw = _function(assembly, "raw_return")
    checked = _function(assembly, "checked_return")
    aggregate = _function(assembly, "aggregate_return")
    status_output = _function(assembly, "status_with_value_output")
    consumed = _function(assembly, "consume_checked_inline")

    assert "ymm0" in raw and "ret" in raw
    assert "ymm0" in checked and "ret" in checked
    assert re.search(r"byte ptr\s+\[rdi(?:\s*\+\s*0)?\]", checked)
    assert not re.search(r"ymmword ptr\s+\[rdi", checked)

    assert re.search(r"ymmword ptr\s+(?:32)?\[rdi", aggregate)
    assert re.search(r"\bmov\s+rax,\s*rdi\b", aggregate)
    assert re.search(r"ymmword ptr\s+\[rdi", status_output)
    assert re.search(r"\b(?:xor\s+eax,\s*eax|mov\s+eax,\s*0)\b", status_output)

    assert "ret" in consumed
    assert not re.search(r"\[(?:r|e)sp(?:\s*[+\-])?", consumed)


def test_msvc_probe_compiles_when_available(tmp_path: Path) -> None:
    if platform.system() != "Windows":
        pytest.skip("MSVC is only probed on a native Windows runner")
    compiler = shutil.which("cl.exe") or shutil.which("cl")
    if compiler is None:
        pytest.skip("MSVC cl.exe is not available")
    assembly_path = tmp_path / "abi_probe.asm"
    completed = subprocess.run(
        (
            compiler,
            "/nologo",
            "/std:c++17",
            "/O2",
            "/W4",
            "/WX",
            "/arch:AVX2",
            "/FAs",
            "/c",
            str(_FIXTURE),
            f"/Fo{tmp_path / 'abi_probe.obj'}",
            f"/Fa{assembly_path}",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assembly = assembly_path.read_text(encoding="utf-8", errors="replace").lower()
    for function_name in (
        "raw_return",
        "checked_return",
        "aggregate_return",
        "status_with_value_output",
        "consume_checked_inline",
    ):
        assert re.search(rf"\b{function_name}\s+proc\b", assembly)
    assert "ymm0" in assembly
    assert "ymmword ptr" in assembly
