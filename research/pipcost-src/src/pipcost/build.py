"""Local CMake build and correctness verification."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, cast

from pipcost.host import compiler_record
from pipcost.records import digest_file, digest_json, digest_tree, read_json, write_json
from pipcost.tsl_project import GenerationEvidence, load_generation
from pipcost.workspace import WorkspacePaths


@dataclass(frozen=True, slots=True)
class BuildEvidence:
    build_id: str
    build_root: Path
    executable: Path
    test_executable: Path
    manifest: dict[str, Any]


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{detail}"
        )
    return completed


def _build_identity(
    paths: WorkspacePaths,
    generation: GenerationEvidence,
    compiler: str,
    simd_lanes: int,
) -> tuple[str, dict[str, object]]:
    compiler_info = compiler_record(compiler)
    if not compiler_info["available"]:
        raise RuntimeError(f"C++ compiler is unavailable: {compiler}")
    cpp_digest, cpp_files = digest_tree(paths.prototype_root / "cpp")
    identity = {
        "schema_version": 1,
        "generation_id": generation.generation_id,
        "generation_manifest_digest": generation.manifest[
            "artifact_manifest_digest"
        ],
        "compiler": compiler_info,
        "simd_lanes": simd_lanes,
        "cpp_source_digest": cpp_digest,
        "cpp_files": cpp_files,
        "build_type": "Release",
    }
    return f"build-{digest_json(identity)[:16]}", identity


def build_benchmark(
    paths: WorkspacePaths,
    *,
    profile: str,
    simd_lanes: int,
    compiler: str,
    tsl_ref: str,
) -> BuildEvidence:
    generation = load_generation(
        paths, profile=profile, simd_lanes=simd_lanes, tsl_ref=tsl_ref
    )
    build_id, identity = _build_identity(
        paths, generation, compiler, simd_lanes
    )
    build_root = paths.output_path("build", build_id)
    build_root.mkdir(parents=True, exist_ok=True)
    compiler_path = str(identity["compiler"]["executable"])  # type: ignore[index]
    configure = [
        shutil.which("cmake") or "cmake",
        "-S",
        str(paths.prototype_root / "cpp"),
        "-B",
        str(build_root),
        f"-DTSL_GENERATED_CPP_DIR={generation.cpp_root}",
        f"-DTSL_PROFILE={profile}",
        f"-DPIPCOST_SIMD_LANES={simd_lanes}",
        f"-DCMAKE_CXX_COMPILER={compiler_path}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    ]
    configured = _run(configure, cwd=paths.root)
    build_command = [
        shutil.which("cmake") or "cmake",
        "--build",
        str(build_root),
        "--target",
        "pipcost-bench",
        "pipcost-kernel-tests",
        "--parallel",
    ]
    built = _run(build_command, cwd=paths.root)
    executable = build_root / "pipcost-bench"
    test_executable = build_root / "pipcost-kernel-tests"
    if not executable.is_file() or not test_executable.is_file():
        raise RuntimeError("CMake build completed without expected PIPCost binaries")

    compile_commands_path = build_root / "compile_commands.json"
    compile_commands = (
        read_json(compile_commands_path)
        if compile_commands_path.is_file()
        else []
    )
    link_path = build_root / "CMakeFiles" / "pipcost-bench.dir" / "link.txt"
    effective_link_command = (
        link_path.read_text(encoding="utf-8").strip()
        if link_path.is_file()
        else None
    )
    manifest: dict[str, Any] = {
        **identity,
        "build_id": build_id,
        "profile": profile,
        "configure_command": configure,
        "build_command": build_command,
        "configure_stdout": configured.stdout,
        "configure_stderr": configured.stderr,
        "build_stdout": built.stdout,
        "build_stderr": built.stderr,
        "compile_commands": compile_commands,
        "effective_link_command": effective_link_command,
        "executable": str(executable),
        "executable_sha256": digest_file(executable),
        "test_executable": str(test_executable),
        "test_executable_sha256": digest_file(test_executable),
    }
    write_json(build_root / "build.json", manifest)
    return BuildEvidence(
        build_id=build_id,
        build_root=build_root,
        executable=executable,
        test_executable=test_executable,
        manifest=manifest,
    )


def load_build(
    paths: WorkspacePaths,
    *,
    profile: str,
    simd_lanes: int,
    compiler: str,
    tsl_ref: str,
) -> BuildEvidence:
    generation = load_generation(
        paths, profile=profile, simd_lanes=simd_lanes, tsl_ref=tsl_ref
    )
    build_id, _ = _build_identity(paths, generation, compiler, simd_lanes)
    build_root = paths.output_path("build", build_id)
    manifest_path = build_root / "build.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"build evidence does not exist: {manifest_path}")
    manifest = read_json(manifest_path)
    executable = Path(manifest["executable"])
    test_executable = Path(manifest["test_executable"])
    if (
        not executable.is_file()
        or digest_file(executable) != manifest["executable_sha256"]
    ):
        raise RuntimeError("benchmark executable is missing or differs from build evidence")
    return BuildEvidence(
        build_id=build_id,
        build_root=build_root,
        executable=executable,
        test_executable=test_executable,
        manifest=manifest,
    )


def list_plans(build: BuildEvidence) -> dict[str, Any]:
    completed = _run(
        [str(build.executable), "--list-plans", "--format", "json"],
        cwd=build.build_root,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def _function_body(disassembly: str, function: str) -> str:
    header = re.compile(
        rf"^[0-9a-f]+ <pipcost::{re.escape(function)}\(.*\)>:$"
    )
    next_header = re.compile(r"^[0-9a-f]+ <.*>:$")
    lines = disassembly.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if header.match(line)),
        None,
    )
    if start is None:
        raise RuntimeError(f"disassembly has no {function} function")
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if next_header.match(lines[index])
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _vectorization_evidence(disassembly: str) -> dict[str, object]:
    registers = re.compile(r"%([xyz]mm[0-9]+)")
    autovec = sorted(
        set(registers.findall(_function_body(disassembly, "scalar_autovec")))
    )
    disabled = sorted(
        set(registers.findall(_function_body(disassembly, "scalar_no_vector")))
    )
    passed = bool(autovec) and not disabled
    return {
        "status": "pass" if passed else "fail",
        "criterion": (
            "compiler-enabled scalar uses SIMD registers and the identical "
            "no-vector source uses none"
        ),
        "scalar_autovec_vector_registers": autovec,
        "scalar_no_vector_vector_registers": disabled,
    }


def _disassembly_control(build: BuildEvidence) -> dict[str, object]:
    executable = shutil.which("objdump")
    if executable is None:
        raise RuntimeError(
            "objdump is required to validate the scalar vectorization controls"
        )
    completed = _run(
        [executable, "-d", "-C", str(build.executable)],
        cwd=build.build_root,
    )
    path = build.build_root / "pipcost-bench.disassembly.txt"
    path.write_text(completed.stdout, encoding="utf-8")
    vectorization = _vectorization_evidence(completed.stdout)
    if vectorization["status"] != "pass":
        raise RuntimeError(
            "scalar autovectorization control failed disassembly validation"
        )
    return {
        "status": "captured",
        "path": str(path),
        "sha256": digest_file(path),
        "scalar_vectorization_control": vectorization,
    }


def check_build(
    build: BuildEvidence,
    *,
    validate_vectorization: bool = False,
) -> dict[str, Any]:
    ctest = _run(
        [
            shutil.which("ctest") or "ctest",
            "--test-dir",
            str(build.build_root),
            "--output-on-failure",
        ],
        cwd=build.build_root,
    )
    self_test = _run(
        [str(build.executable), "--self-test"],
        cwd=build.build_root,
    )
    result: dict[str, Any] = {
        "schema_version": 1,
        "build_id": build.build_id,
        "ctest": {
            "command": [
                shutil.which("ctest") or "ctest",
                "--test-dir",
                str(build.build_root),
                "--output-on-failure",
            ],
            "stdout": ctest.stdout,
        },
        "self_test": json.loads(self_test.stdout),
        "plans": list_plans(build)["plans"],
    }
    if validate_vectorization:
        result["disassembly"] = _disassembly_control(build)
    return result
