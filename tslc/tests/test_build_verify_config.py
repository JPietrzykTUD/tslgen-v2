"""Build verifier toolchain configuration behavior."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from tslc.output.verify import (
    BuildCommand,
    BuildCommandResult,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
    VerifyProject,
    run_subprocess_build_command,
    verify_generated_project,
)


def test_cpp_verifier_accepts_explicit_compiler(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(cpp_compiler="/usr/bin/c++"),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == ["preflight", "configure", "build"]
    assert seen[0].argv[0] == "/usr/bin/c++"
    assert _env(seen[1])["CXX"] == "/usr/bin/c++"
    assert _env(seen[2])["CXX"] == "/usr/bin/c++"


def test_cpp_verifier_skips_after_failed_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CXX", "zig c++")
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(
            command=command,
            returncode=1,
            stderr="unable to create compiler cache file",
        )

    report = verify_generated_project(tmp_path, project, runner)

    assert report.diagnostics == ()
    assert len(seen) == 1
    assert seen[0].step == "preflight"
    assert report.skipped
    assert "C++ compiler preflight failed" in report.skipped[0]


def test_cpp_verifier_skips_missing_explicit_compiler(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(cpp_compiler="/definitely/missing/c++"),
    )

    assert report.diagnostics == ()
    assert seen == []
    assert report.skipped == ("cpp: C++ compiler /definitely/missing/c++ not found",)


def test_rust_verifier_accepts_explicit_compiler(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(rust_compiler=sys.executable),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == ["preflight", "test"]
    assert seen[0].argv[0] == sys.executable
    assert _env(seen[1])["RUSTC"] == sys.executable
    assert "--target-dir" in seen[1].argv
    assert str(tmp_path / "rust" / "target" / "scalar") in seen[1].argv


def test_rust_verifier_skips_after_failed_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("RUSTC", sys.executable)
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(
            command=command,
            returncode=1,
            stderr="rust compiler cannot produce binaries",
        )

    report = verify_generated_project(tmp_path, project, runner)

    assert report.diagnostics == ()
    assert len(seen) == 1
    assert seen[0].step == "preflight"
    assert report.skipped
    assert "Rust compiler preflight failed" in report.skipped[0]


def test_rust_verifier_skips_missing_explicit_compiler(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(rust_compiler="/definitely/missing/rustc"),
    )

    assert report.diagnostics == ()
    assert seen == []
    assert report.skipped == ("rust: Rust compiler /definitely/missing/rustc not found",)


def test_subprocess_runner_closes_command_stdin(tmp_path: Path) -> None:
    command = BuildCommand(
        backend_id="rust",
        profile_name="unit",
        step="stdin",
        argv=(
            sys.executable,
            "-c",
            "import sys; data = sys.stdin.read(); print('empty' if data == '' else 'nonempty')",
        ),
        cwd=tmp_path,
    )

    result = run_subprocess_build_command(command)

    assert result.returncode == 0
    assert result.stdout.strip() == "empty"


def test_subprocess_runner_defaults_zig_cache_under_command_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ZIG_LOCAL_CACHE_DIR", "/shared/zig-local")
    monkeypatch.setenv("ZIG_GLOBAL_CACHE_DIR", "/shared/zig-global")
    command = BuildCommand(
        backend_id="cpp",
        profile_name="unit",
        step="env",
        argv=(
            sys.executable,
            "-c",
            "import os; print(os.environ['ZIG_LOCAL_CACHE_DIR']); print(os.environ['ZIG_GLOBAL_CACHE_DIR'])",
        ),
        cwd=tmp_path,
    )

    result = run_subprocess_build_command(command)

    assert result.returncode == 0
    local_cache, global_cache = result.stdout.splitlines()
    expected_root = Path(tempfile.gettempdir()) / "tslc-zig-cache"
    assert local_cache != "/shared/zig-local"
    assert global_cache != "/shared/zig-global"
    assert Path(local_cache).is_dir()
    assert Path(global_cache).is_dir()
    assert Path(local_cache).is_relative_to(expected_root)
    assert Path(global_cache).is_relative_to(expected_root)
    assert Path(local_cache).name == "local"
    assert Path(global_cache).name == "global"


def test_cpp_value_test_run_can_be_wrapped_with_sde(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        sde="hsw",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(
            cpp_compiler="/usr/bin/c++",
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "preflight",
        "clean",
        "configure",
        "build",
        "build-values",
        "test",
    ]
    assert seen[-2].argv[0] == "cmake"
    assert seen[-1].argv[:3] == (sys.executable, "-hsw", "--")
    assert seen[-1].argv[3] == "ctest"


def test_sde_cpp_value_tests_pin_default_compiler_over_ambient_cxx(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CXX", "zig c++")
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="sse2",
                        file_stem="sse2",
                        sde="mrm",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen[:3]] == ["preflight", "clean", "configure"]
    assert seen[0].argv[0] == "c++"
    assert _env(seen[1])["CXX"] == "c++"
    assert _env(seen[2])["CXX"] == "c++"


def test_sde_value_tests_skip_non_generic_profiles_without_sde_alias(
    tmp_path: Path,
) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="neon",
                        file_stem="neon",
                        family="aarch64",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == (
        "cpp: profile neon has no SDE chip alias; value-test verification skipped",
    )
    assert seen == []


def test_rust_value_tests_run_built_binaries_through_sde(tmp_path: Path) -> None:
    executable = str(tmp_path / "rust" / "target" / "debug" / "deps" / "values")
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        rust_target_features=("+avx2",),
                        sde="hsw",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "build-tests":
            stdout = "\n".join(
                (
                    json.dumps(
                        {
                            "reason": "compiler-artifact",
                            "executable": executable,
                        }
                    ),
                    "non-json cargo noise",
                )
            )
            return BuildCommandResult(command=command, returncode=0, stdout=stdout)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(
            rust_compiler=sys.executable,
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == ["preflight", "build-tests", "test"]
    assert "--no-run" in seen[1].argv
    assert "--message-format=json" in seen[1].argv
    assert "--target-dir" in seen[1].argv
    assert str(tmp_path / "rust" / "target" / "avx2") in seen[1].argv
    assert seen[1].argv[0] == "cargo"
    assert seen[2].argv == (sys.executable, "-hsw", "--", executable)


def test_rust_sde_value_tests_diagnose_missing_test_binaries(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(VerifyProfile(profile_name="avx2", file_stem="avx2", sde="hsw"),),
            ),
        )
    )

    def runner(command: BuildCommand) -> BuildCommandResult:
        return BuildCommandResult(command=command, returncode=0, stdout="{}")

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=BuildVerifierConfig.create(
            rust_compiler=sys.executable,
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-NO-RUST-TEST-BINARIES"
    ]


def test_explicit_sde_path_must_exist(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(VerifyProfile(profile_name="avx2", file_stem="avx2", sde="hsw"),),
            ),
        )
    )

    report = verify_generated_project(
        tmp_path,
        project,
        config=BuildVerifierConfig.create(
            rust_compiler=sys.executable,
            run_value_tests=True,
            sde_path="/definitely/missing/sde",
        ),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-SDE-MISSING"
    ]


def _env(command: BuildCommand) -> dict[str, str]:
    return {item.key: item.value for item in command.env}
