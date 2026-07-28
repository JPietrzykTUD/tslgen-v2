"""Build verifier toolchain configuration behavior."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import tslc.output.verify as verify_module
import tslc.output._verify_common as verify_common
from tslc.backend.cpp_capability import create_cpp_verify_driver
from tslc.backend.rust_capability import create_rust_verify_driver
from tslc.output.verify import (
    BuildCommand,
    BuildCommandEnvironment,
    BuildCommandResult,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyCompileFailure,
    VerifyProfile,
    VerifyProject,
    VerifyRunner,
    run_subprocess_build_command,
    verify_generated_project,
)
from tslc.output._verify_cpp import _prepare_cpp_backend
from tslc.output._verify_cpp_config import effective_cpp_compiler
from tslc.output._verify_runners import runner_prefix
from tslc.output._verify_rust_config import effective_rust_compiler
from tslc.output.verify_drivers import BackendPreparation, VerifyBackendDriver
from tslc.output.verify_model import BackendToolchain

_ONEAPI_CPP_TOOL = "/opt/intel/oneapi/compiler/2025.0/bin/icpx"
_WASI_CPP_TOOL = "/opt/wasi-sdk/bin/clang++"


def _config(
    *,
    cpp_compiler: str | None = None,
    rust_compiler: str | None = None,
    rust_target: str | None = None,
    run_value_tests: bool = False,
    sde_path: str | None = None,
    qemu_aarch64_path: str | None = None,
    wasmtime_path: str | None = None,
    cpp_linker: str | None = None,
    rust_clippy_path: str | None = None,
    run_quality_checks: bool = False,
    tool_paths: dict[str, str] | None = None,
) -> BuildVerifierConfig:
    toolchains = {
        backend_id: BackendToolchain.create(compiler=compiler)
        for backend_id, compiler in (
            ("cpp", cpp_compiler),
            ("rust", rust_compiler),
        )
        if (
            compiler is not None
            or (backend_id == "cpp" and cpp_linker is not None)
            or (backend_id == "rust" and rust_target is not None)
        )
    }
    if cpp_linker is not None:
        toolchains["cpp"] = BackendToolchain.create(
            compiler=cpp_compiler,
            linker=cpp_linker,
        )
    if rust_target is not None:
        toolchains["rust"] = BackendToolchain.create(
            compiler=rust_compiler,
            target=rust_target,
        )
    runner_paths = {
        kind: path
        for kind, path in (
            ("sde", sde_path),
            ("qemu-aarch64", qemu_aarch64_path),
            ("wasmtime", wasmtime_path),
        )
        if path is not None
    }
    configured_tools = dict(tool_paths or {})
    if rust_clippy_path is not None:
        configured_tools["rust-clippy"] = rust_clippy_path
    return BuildVerifierConfig.create(
        toolchains=toolchains,
        runner_paths=runner_paths,
        tool_paths=configured_tools,
        run_value_tests=run_value_tests,
        run_quality_checks=run_quality_checks,
    )


def _mixed_rust_host_discovery_project() -> VerifyProject:
    return VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(profile_name="scalar", file_stem="scalar"),
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        target_features=("+avx2",),
                    ),
                ),
            ),
        )
    )


def test_backend_capabilities_use_public_verify_driver_surface() -> None:
    cpp_driver = create_cpp_verify_driver()
    rust_driver = create_rust_verify_driver()

    assert isinstance(cpp_driver, VerifyBackendDriver)
    assert isinstance(rust_driver, VerifyBackendDriver)
    assert cpp_driver.backend_id == "cpp"
    assert rust_driver.backend_id == "rust"
    assert cpp_driver.prepare_backend.__module__ != verify_module.__name__
    assert rust_driver.command_groups.__module__ != verify_module.__name__
    assert not hasattr(verify_module, "cpp_verify_driver")
    assert not hasattr(verify_module, "rust_verify_driver")


def test_verifier_configuration_has_focused_module_ownership() -> None:
    assert effective_cpp_compiler.__module__ == "tslc.output._verify_cpp_config"
    assert effective_rust_compiler.__module__ == "tslc.output._verify_rust_config"
    assert runner_prefix.__module__ == "tslc.output._verify_runners"
    assert not hasattr(verify_common, "effective_cpp_compiler")
    assert not hasattr(verify_common, "effective_rust_compiler")
    assert not hasattr(verify_common, "runner_prefix")


def test_subprocess_verifier_uses_local_runtime_cache_dirs(tmp_path: Path) -> None:
    command = BuildCommand(
        backend_id="cpp",
        profile_name="wasm32_simd128",
        step="test",
        argv=("ctest", "--test-dir", "build"),
        cwd=tmp_path,
    )

    env = verify_module._subprocess_env(command)

    assert env is not None
    assert env["WASMTIME_HOME"] == str(tmp_path / ".tslctmp" / "runtime" / "wasmtime-home")
    assert env["XDG_CACHE_HOME"] == str(tmp_path / ".tslctmp" / "runtime" / "xdg-cache")

    overridden = BuildCommand(
        backend_id="cpp",
        profile_name="wasm32_simd128",
        step="test",
        argv=("ctest", "--test-dir", "build"),
        cwd=tmp_path,
        env=(BuildCommandEnvironment("XDG_CACHE_HOME", "/custom/cache"),),
    )
    overridden_env = verify_module._subprocess_env(overridden)
    assert overridden_env is not None
    assert overridden_env["XDG_CACHE_HOME"] == "/custom/cache"


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
        config=_config(cpp_compiler="/usr/bin/c++", cpp_linker="/usr/bin/ld"),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == ["preflight", "configure", "build"]
    assert [result.command.step for result in report.commands] == [
        "preflight",
        "configure",
        "build",
    ]
    assert seen[0].argv[0] == "/usr/bin/c++"
    assert "-DCMAKE_LINKER=/usr/bin/ld" in seen[1].argv
    assert _env(seen[1])["CXX"] == "/usr/bin/c++"
    assert _env(seen[2])["CXX"] == "/usr/bin/c++"


def test_expected_compile_failure_requires_nonzero_status_and_exact_marker(
    tmp_path: Path,
) -> None:
    marker = "TSL_ARITH_INTEGER_IMMEDIATE_ZERO"
    profile = VerifyProfile(
        profile_name="scalar",
        file_stem="scalar",
        compile_failures=(VerifyCompileFailure("negative_case", marker),),
    )
    project = VerifyProject(
        backends=(VerifyBackend("cpp", "cpp", (profile,)),)
    )

    def report_for(returncode: int, stderr: str):
        def runner(command: BuildCommand) -> BuildCommandResult:
            if command.step == "compile-failure":
                return BuildCommandResult(command, returncode, stderr=stderr)
            return BuildCommandResult(command, 0)

        return verify_generated_project(
            tmp_path,
            project,
            runner,
            config=_config(cpp_compiler="/usr/bin/c++"),
        )

    accepted = report_for(1, f"static assertion failed: {marker}")
    wrong_failure = report_for(1, "unrelated syntax error")
    unexpected_success = report_for(0, "")

    assert accepted.diagnostics == ()
    assert accepted.commands[-1].matches_expectation
    assert accepted.commands[-1].command.argv[-1] == "negative_case"
    assert [item.code for item in wrong_failure.diagnostics] == [
        "TSL-BUILD-VERIFY-EXPECTED-COMPILE-FAILURE"
    ]
    assert [item.code for item in unexpected_success.diagnostics] == [
        "TSL-BUILD-VERIFY-EXPECTED-COMPILE-FAILURE"
    ]


def test_cpp_prepare_backend_returns_frozen_preparation(tmp_path: Path) -> None:
    backend = VerifyBackend(
        backend_id="cpp",
        root_path="cpp",
        profiles=(VerifyProfile(profile_name="scalar", file_stem="scalar"),),
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    prep = _prepare_cpp_backend(
        tmp_path,
        backend,
        _config(cpp_compiler="/usr/bin/c++"),
        runner,
    )

    assert isinstance(prep, BackendPreparation)
    assert prep.backend is not None
    assert [profile.profile_name for profile in prep.backend.profiles] == ["scalar"]
    assert [result.command.step for result in prep.commands] == ["preflight"]
    assert prep.diagnostics == ()
    assert prep.skipped == ()


def test_native_cpp_verifier_uses_host_compiler_over_ambient_zig(
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
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(tmp_path, project, runner)

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == ["preflight", "configure", "build"]
    assert seen[0].argv[0] == "c++"
    assert _env(seen[1])["CXX"] == "c++"
    assert _env(seen[2])["CXX"] == "c++"


def test_cpp_verifier_skips_after_failed_preflight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CXX", sys.executable)
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
        config=_config(cpp_compiler="/definitely/missing/c++"),
    )

    assert report.diagnostics == ()
    assert seen == []
    assert report.skipped == (
        "cpp: profile scalar C++ compiler /definitely/missing/c++ not found",
    )


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
        config=_config(
            rust_compiler=sys.executable,
            rust_clippy_path=sys.executable,
            run_quality_checks=True,
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == [
        "preflight",
        "check-warnings",
        "rustdoc",
        "clippy",
        "test",
    ]
    assert seen[0].argv[0] == sys.executable
    warning_gate, rustdoc_gate, clippy_gate, test = seen[1:]
    assert warning_gate.argv[:2] == ("cargo", "check")
    assert "--all-targets" in warning_gate.argv
    warning_flags = _env(warning_gate)["RUSTFLAGS"]
    assert "-Dwarnings" in warning_flags
    assert "-Dinvalid-value" in warning_flags
    assert "-Dprivate-interfaces" in warning_flags
    assert "-Dprivate-bounds" in warning_flags
    assert rustdoc_gate.argv[:2] == ("cargo", "doc")
    assert "--no-deps" in rustdoc_gate.argv
    rustdoc_flags = _env(rustdoc_gate)["RUSTDOCFLAGS"]
    assert "-Dwarnings" in rustdoc_flags
    assert "-Drustdoc::broken-intra-doc-links" in rustdoc_flags
    assert "-Drustdoc::bare-urls" in rustdoc_flags
    assert clippy_gate.argv[:2] == (sys.executable, "clippy")
    clippy_separator = clippy_gate.argv.index("--")
    assert clippy_gate.argv[clippy_separator + 1 :] == (
        "-Awarnings",
        "-Dclippy::correctness",
        "-Dclippy::suspicious",
    )
    assert _env(test)["RUSTC"] == sys.executable
    assert "--target-dir" in test.argv
    assert str(tmp_path / "rust" / "target" / "scalar") in test.argv


def test_rust_verifier_reports_missing_optional_clippy_and_runs_other_gates(
    tmp_path: Path,
) -> None:
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
        config=_config(
            rust_compiler=sys.executable,
            rust_clippy_path="/definitely/missing/cargo-clippy",
            run_quality_checks=True,
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == (
        "rust: optional Clippy component /definitely/missing/cargo-clippy not found",
    )
    assert [command.step for command in seen] == [
        "preflight",
        "check-warnings",
        "rustdoc",
        "test",
    ]


def test_rust_warning_gates_report_independent_failures(tmp_path: Path) -> None:
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
            returncode=(
                1
                if command.step in {"check-warnings", "rustdoc", "clippy"}
                else 0
            ),
            stderr=f"{command.step} gate failure",
        )

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            rust_compiler=sys.executable,
            rust_clippy_path=sys.executable,
            run_quality_checks=True,
        ),
    )

    assert [command.step for command in seen] == [
        "preflight",
        "check-warnings",
        "rustdoc",
        "clippy",
        "test",
    ]
    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-COMMAND-FAILED",
        "TSL-BUILD-VERIFY-COMMAND-FAILED",
        "TSL-BUILD-VERIFY-COMMAND-FAILED",
    ]
    assert all(
        gate in diagnostic.message
        for gate, diagnostic in zip(
            ("check-warnings", "rustdoc", "clippy"), report.diagnostics
        )
    )


def test_rust_compile_failures_use_isolated_unpublished_manifests(tmp_path: Path) -> None:
    marker = "TSL_ARITH_INTEGER_IMMEDIATE_ZERO"
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="zen5",
                        file_stem="zen5",
                        compile_failures=(
                            VerifyCompileFailure("negative_zero", marker),
                            VerifyCompileFailure("negative_narrowed_zero", marker),
                        ),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "compile-failure":
            return BuildCommandResult(command, 1, stderr=marker)
        return BuildCommandResult(command, 0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(rust_compiler=sys.executable),
    )

    assert report.diagnostics == ()
    compile_failures = [
        command for command in seen if command.step == "compile-failure"
    ]
    assert [
        command.argv[command.argv.index("--manifest-path") + 1]
        for command in compile_failures
    ] == [
        str(tmp_path / "rust/verify/negative_zero/Cargo.toml"),
        str(tmp_path / "rust/verify/negative_narrowed_zero/Cargo.toml"),
    ]
    assert all("--features" not in command.argv for command in compile_failures)
    assert all("--example" not in command.argv for command in compile_failures)


def test_rust_build_verifier_cross_target_does_not_run_test_binary(
    tmp_path: Path,
) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="neon",
                        file_stem="neon",
                        family="aarch64",
                        target_features=("+neon",),
                        target="aarch64-unknown-linux-musl",
                        linker="rust-lld",
                        runner=VerifyRunner(kind="qemu-aarch64", profile="cortex-a76"),
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
        config=_config(
            rust_compiler=sys.executable,
            rust_clippy_path=sys.executable,
            run_quality_checks=True,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "preflight",
        "target-preflight",
        "check-warnings",
        "rustdoc",
        "clippy",
        "build-tests",
    ]
    assert "--target" in seen[1].argv
    assert "aarch64-unknown-linux-musl" in seen[1].argv
    assert "linker=rust-lld" in seen[1].argv
    build_tests = next(command for command in seen if command.step == "build-tests")
    assert "--target" in build_tests.argv
    assert "aarch64-unknown-linux-musl" in build_tests.argv
    assert "--no-run" in build_tests.argv
    assert "--message-format=json" not in build_tests.argv
    env = _env(build_tests)
    assert env["CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER"] == "rust-lld"
    assert (
        env["CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUSTFLAGS"]
        == "-C target-feature=+neon"
    )
    assert env["RUSTDOCFLAGS"] == "-C target-feature=+neon"
    warning_gate = next(
        command for command in seen if command.step == "check-warnings"
    )
    warning_flags = _env(warning_gate)[
        "CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_RUSTFLAGS"
    ]
    assert warning_flags.startswith("-C target-feature=+neon ")
    assert "-Dwarnings" in warning_flags


def test_rust_target_preflight_failure_skips_only_that_profile(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(profile_name="scalar", file_stem="scalar"),
                    VerifyProfile(
                        profile_name="wasm32_simd128",
                        file_stem="wasm32_simd128",
                        family="wasm32",
                        target_features=("+simd128",),
                        target="wasm32-wasip1",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "target-preflight":
            return BuildCommandResult(
                command=command,
                returncode=1,
                stderr="can't find crate for `std`",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(rust_compiler=sys.executable),
    )

    assert report.diagnostics == ()
    assert len(report.skipped) == 1
    assert report.skipped[0].startswith(
        "rust: profile wasm32_simd128 target preflight failed with exit code 1"
    )
    assert [command.step for command in seen] == [
        "preflight",
        "target-preflight",
        "test",
    ]
    assert [command.profile_name for command in seen if command.step == "test"] == [
        "scalar"
    ]


def test_rust_host_target_query_failure_skips_only_dependent_profiles(
    tmp_path: Path,
) -> None:
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "host-target":
            return BuildCommandResult(
                command=command,
                returncode=1,
                stderr="toolchain metadata unavailable",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        _mixed_rust_host_discovery_project(),
        runner,
        config=_config(rust_compiler=sys.executable),
    )

    assert report.diagnostics == ()
    assert report.skipped == (
        "rust: profile avx2 requires host-target discovery; Rust host-target "
        f"query failed with exit code 1: {sys.executable} -vV: "
        "toolchain metadata unavailable",
    )
    assert [command.step for command in seen] == [
        "preflight",
        "host-target",
        "test",
    ]
    assert seen[-1].profile_name == "scalar"


def test_rust_malformed_host_target_skips_only_dependent_profiles(
    tmp_path: Path,
) -> None:
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "host-target":
            return BuildCommandResult(
                command=command,
                returncode=0,
                stdout="rustc 1.89.0\nrelease: 1.89.0\n",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        _mixed_rust_host_discovery_project(),
        runner,
        config=_config(rust_compiler=sys.executable),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-RUST-HOST-TARGET"
    ]
    assert report.skipped == (
        "rust: profile avx2 requires host-target discovery; Rust compiler "
        "verbose version output did not contain a valid `host: <target>` line",
    )
    assert [command.step for command in seen] == [
        "preflight",
        "host-target",
        "test",
    ]
    assert seen[-1].profile_name == "scalar"


def test_rust_explicit_target_bypasses_host_discovery(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        target_features=("+avx2",),
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
        config=_config(
            rust_compiler=sys.executable,
            rust_target="x86_64-unknown-linux-gnu",
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen] == [
        "preflight",
        "target-preflight",
        "build-tests",
    ]
    assert all(command.step != "host-target" for command in seen)
    target_preflight, cargo_build = seen[1:]
    assert target_preflight.argv[
        target_preflight.argv.index("--target") + 1
    ] == "x86_64-unknown-linux-gnu"
    assert cargo_build.argv[cargo_build.argv.index("--target") + 1] == (
        "x86_64-unknown-linux-gnu"
    )
    environment = _env(cargo_build)
    assert environment[
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS"
    ] == "-C target-feature=+avx2"
    assert "RUSTFLAGS" not in environment


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
        config=_config(rust_compiler="/definitely/missing/rustc"),
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


def test_subprocess_runner_installs_rustc_stdin_guard_for_cargo(tmp_path: Path) -> None:
    cargo = tmp_path / "cargo"
    cargo.write_text(
        "\n".join(
            (
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "print(os.environ['RUSTC_WRAPPER'])",
                "print(repr(sys.stdin.read()))",
                "",
            )
        ),
        encoding="utf-8",
    )
    cargo.chmod(0o755)
    command = BuildCommand(
        backend_id="rust",
        profile_name="unit",
        step="cargo",
        argv=(str(cargo),),
        cwd=tmp_path,
    )

    result = run_subprocess_build_command(command)

    assert result.returncode == 0
    wrapper_path, stdin = result.stdout.splitlines()
    wrapper = Path(wrapper_path)
    assert wrapper.is_file()
    assert os.access(wrapper, os.X_OK)
    assert "fn main()" in wrapper.read_text(encoding="utf-8")
    assert stdin == repr("")


def test_subprocess_runner_replaces_invalid_output_bytes(tmp_path: Path) -> None:
    command = BuildCommand(
        backend_id="rust",
        profile_name="unit",
        step="invalid-output",
        argv=(
            sys.executable,
            "-c",
            "import sys; sys.stdout.buffer.write(b'valid\\n\\xb7\\n')",
        ),
        cwd=tmp_path,
    )

    result = run_subprocess_build_command(command)

    assert result.returncode == 0
    assert result.stdout == "valid\n\ufffd\n"


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
    expected_root = tmp_path / ".tslctmp" / "zig-cache"
    assert local_cache != "/shared/zig-local"
    assert global_cache != "/shared/zig-global"
    assert Path(local_cache).is_dir()
    assert Path(global_cache).is_dir()
    assert Path(local_cache).is_relative_to(expected_root)
    assert Path(global_cache).is_relative_to(expected_root)
    assert Path(local_cache).name == "local"
    assert Path(global_cache).name == "global"


def test_cpp_value_test_run_configures_sde_as_test_launcher(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        runner=VerifyRunner(kind="sde", profile="hsw"),
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
        config=_config(
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
    configure = seen[2].argv
    assert f"-DTSL_TEST_LAUNCHER={sys.executable};-hsw;--" in configure
    assert seen[-2].argv[0] == "cmake"
    assert seen[-1].argv[0] == "ctest"


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
                        runner=VerifyRunner(kind="sde", profile="mrm"),
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
        config=_config(
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen[:3]] == ["preflight", "clean", "configure"]
    assert seen[0].argv[0] == "c++"
    assert _env(seen[1])["CXX"] == "c++"
    assert _env(seen[2])["CXX"] == "c++"


def test_sde_runner_does_not_override_oneapi_cpp_default_compiler(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="cascadelake_oneapi",
                        file_stem="cascadelake_oneapi",
                        family="x86",
                        compile_modes=frozenset({"oneapi_fpga"}),
                        runner=VerifyRunner(kind="sde", profile="clx"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []
    oneapi_compiler = _ONEAPI_CPP_TOOL
    real_which = shutil.which

    def fake_which(executable: str) -> str | None:
        if executable == oneapi_compiler:
            return executable
        return real_which(executable)

    monkeypatch.setattr(shutil, "which", fake_which)

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            run_value_tests=True,
            sde_path=sys.executable,
            tool_paths={"oneapi-cpp": oneapi_compiler},
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen[:3]] == ["preflight", "clean", "configure"]
    assert seen[0].argv[0] == oneapi_compiler
    assert _env(seen[1])["CXX"] == oneapi_compiler
    assert _env(seen[2])["CXX"] == oneapi_compiler


def test_runner_value_tests_skip_non_generic_profiles_without_matching_runner(
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
                        runner=VerifyRunner(kind="qemu-aarch64", profile="cortex-a76"),
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
        config=_config(run_value_tests=True),
    )

    assert report.diagnostics == ()
    assert report.skipped == (
        "cpp: profile neon requires qemu-aarch64, but that runner is not "
        "configured; value-test verification skipped",
    )
    assert seen == []


def test_cpp_qemu_value_tests_configure_cmake_cross_emulator(
    tmp_path: Path,
    monkeypatch,
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
                        flags=("-march=armv8-a+simd",),
                        target="aarch64-linux-gnu",
                        runner=VerifyRunner(kind="qemu-aarch64", profile="cortex-a76"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []
    real_which = shutil.which

    def fake_which(executable: str) -> str | None:
        if executable == "aarch64-linux-gnu-g++":
            return executable
        return real_which(executable)

    monkeypatch.setattr(shutil, "which", fake_which)

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            run_value_tests=True,
            qemu_aarch64_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "target-preflight",
        "clean",
        "configure",
        "build",
        "build-values",
        "test",
    ]
    assert seen[0].argv[0] == "aarch64-linux-gnu-g++"
    assert "--target=aarch64-linux-gnu" not in seen[0].argv
    configure = seen[2].argv
    assert "-DCMAKE_CXX_COMPILER_TARGET=aarch64-linux-gnu" not in configure
    emulator = _configure_arg(configure, "-DCMAKE_CROSSCOMPILING_EMULATOR=")
    assert emulator is not None
    assert emulator.startswith(f"-DCMAKE_CROSSCOMPILING_EMULATOR={sys.executable};")
    assert emulator.endswith(";-cpu;cortex-a76")
    assert seen[-1].argv[0] == "ctest"


def test_cpp_qemu_value_tests_fall_back_to_clang_target_when_cross_gpp_missing(
    tmp_path: Path,
    monkeypatch,
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
                        flags=("-march=armv8-a+simd",),
                        target="aarch64-linux-gnu",
                        runner=VerifyRunner(kind="qemu-aarch64", profile="cortex-a76"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []
    real_which = shutil.which

    def fake_which(executable: str) -> str | None:
        if executable == "aarch64-linux-gnu-g++":
            return None
        return real_which(executable)

    monkeypatch.setattr(shutil, "which", fake_which)

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            run_value_tests=True,
            qemu_aarch64_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen[:3]] == [
        "target-preflight",
        "clean",
        "configure",
    ]
    assert seen[0].argv[0] == "clang++"
    assert "--target=aarch64-linux-gnu" in seen[0].argv
    assert "-DCMAKE_CXX_COMPILER_TARGET=aarch64-linux-gnu" in seen[2].argv


def test_cpp_wasm_value_tests_configure_wasi_and_wasmtime(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="wasm32_simd128",
                        file_stem="wasm32_simd128",
                        family="wasm32",
                        flags=("-msimd128",),
                        target="wasm32-wasip1",
                        runner=VerifyRunner(kind="wasmtime", profile="default"),
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
        config=_config(
            cpp_compiler=sys.executable,
            run_value_tests=True,
            wasmtime_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "target-preflight",
        "clean",
        "configure",
        "build",
        "build-values",
        "test",
    ]
    assert seen[0].argv[0] == sys.executable
    assert "--target=wasm32-wasip1" in seen[0].argv
    assert "-msimd128" in seen[0].argv
    configure = seen[2].argv
    assert "-DCMAKE_SYSTEM_NAME=WASI" in configure
    assert "-DCMAKE_SYSTEM_PROCESSOR=wasm32" in configure
    assert "-DCMAKE_CXX_COMPILER_TARGET=wasm32-wasip1" in configure
    assert f"-DTSL_TEST_LAUNCHER={sys.executable}" in configure
    assert seen[-1].argv[0] == "ctest"


def test_cpp_wasm_default_compiler_uses_configured_wasi_tool_or_clang() -> None:
    project = VerifyBackend(
        backend_id="cpp",
        root_path="cpp",
        profiles=(
            VerifyProfile(
                profile_name="wasm32_simd128",
                file_stem="wasm32_simd128",
                target="wasm32-wasip1",
            ),
        ),
    )
    configured = _config(tool_paths={"wasi-cpp": _WASI_CPP_TOOL})

    assert effective_cpp_compiler(configured, project) == (_WASI_CPP_TOOL,)
    assert effective_cpp_compiler(
        configured,
        project,
        project.profiles[0],
    ) == (_WASI_CPP_TOOL,)
    assert effective_cpp_compiler(_config(), project) == ("clang++",)


def test_cpp_oneapi_default_compiler_uses_configured_tool_or_icpx() -> None:
    project = VerifyBackend(
        backend_id="cpp",
        root_path="cpp",
        profiles=(
            VerifyProfile(
                profile_name="cascadelake_oneapi",
                file_stem="cascadelake_oneapi",
                compile_modes=frozenset({"oneapi_fpga"}),
            ),
        ),
    )
    configured = _config(tool_paths={"oneapi-cpp": _ONEAPI_CPP_TOOL})

    assert effective_cpp_compiler(configured, project) == (_ONEAPI_CPP_TOOL,)
    assert effective_cpp_compiler(
        configured,
        project,
        project.profiles[0],
    ) == (_ONEAPI_CPP_TOOL,)
    assert effective_cpp_compiler(_config(), project) == ("icpx",)
    assert effective_cpp_compiler(
        _config(),
        project,
        project.profiles[0],
    ) == ("icpx",)


def test_sde_runner_does_not_override_wasm_cpp_default_compiler(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="wasm32_simd128",
                        file_stem="wasm32_simd128",
                        family="wasm32",
                        flags=("-msimd128",),
                        target="wasm32-wasip1",
                        runner=VerifyRunner(kind="wasmtime", profile="default"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []
    real_which = shutil.which

    def fake_which(executable: str) -> str | None:
        if executable == _WASI_CPP_TOOL:
            return executable
        return real_which(executable)

    monkeypatch.setattr(shutil, "which", fake_which)

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            run_value_tests=True,
            sde_path=sys.executable,
            wasmtime_path=sys.executable,
            tool_paths={"wasi-cpp": _WASI_CPP_TOOL},
        ),
    )

    assert report.diagnostics == ()
    assert report.skipped == ()
    assert [command.step for command in seen[:3]] == [
        "target-preflight",
        "clean",
        "configure",
    ]
    assert seen[0].argv[0] == _WASI_CPP_TOOL
    assert "--target=wasm32-wasip1" in seen[0].argv
    assert "-msimd128" in seen[0].argv
    assert _env(seen[0])["CXX"] == _WASI_CPP_TOOL
    assert _env(seen[1])["CXX"] == _WASI_CPP_TOOL


def test_cpp_default_compiler_is_profile_scoped_for_mixed_native_and_wasm(
    monkeypatch,
) -> None:
    monkeypatch.delenv("CXX", raising=False)
    config = _config(tool_paths={"wasi-cpp": _WASI_CPP_TOOL})
    backend = VerifyBackend(
        backend_id="cpp",
        root_path="cpp",
        profiles=(
            VerifyProfile(profile_name="scalar", file_stem="scalar"),
            VerifyProfile(
                profile_name="wasm32_simd128",
                file_stem="wasm32_simd128",
                family="wasm32",
                target="wasm32-wasip1",
            ),
        ),
    )
    scalar, wasm = backend.profiles

    assert effective_cpp_compiler(config, backend, scalar) == ("c++",)
    assert effective_cpp_compiler(config, backend, wasm) == (_WASI_CPP_TOOL,)


def test_cpp_target_preflight_failure_skips_only_that_profile(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="cpp",
                root_path="cpp",
                profiles=(
                    VerifyProfile(
                        profile_name="scalar",
                        file_stem="scalar",
                    ),
                    VerifyProfile(
                        profile_name="neon",
                        file_stem="neon",
                        family="aarch64",
                        target="aarch64-linux-gnu",
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "target-preflight":
            return BuildCommandResult(
                command=command,
                returncode=1,
                stderr="fatal error: 'array' file not found",
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(tmp_path, project, runner)

    assert report.diagnostics == ()
    assert len(report.skipped) == 1
    assert report.skipped[0].startswith(
        "cpp: profile neon target preflight failed with exit code 1"
    )
    assert [command.profile_name for command in seen if command.step == "configure"] == [
        "scalar"
    ]


def test_rust_qemu_value_tests_use_target_and_run_binaries(tmp_path: Path) -> None:
    executable = str(tmp_path / "rust" / "target" / "aarch64" / "deps" / "values")
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="neon",
                        file_stem="neon",
                        family="aarch64",
                        target_features=("+neon",),
                        target="aarch64-unknown-linux-musl",
                        linker="rust-lld",
                        runner=VerifyRunner(kind="qemu-aarch64", profile="cortex-a76"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "build-tests":
            return BuildCommandResult(
                command=command,
                returncode=0,
                stdout=json.dumps(
                    {"reason": "compiler-artifact", "executable": executable}
                ),
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            rust_compiler=sys.executable,
            run_value_tests=True,
            qemu_aarch64_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "preflight",
        "target-preflight",
        "build-tests",
        "test",
    ]
    assert "--target" in seen[1].argv
    assert "aarch64-unknown-linux-musl" in seen[1].argv
    assert "linker=rust-lld" in seen[1].argv
    build_tests = next(command for command in seen if command.step == "build-tests")
    assert "--target" in build_tests.argv
    assert "aarch64-unknown-linux-musl" in build_tests.argv
    env = _env(build_tests)
    assert env["CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER"] == "rust-lld"
    run_test = seen[-1]
    assert run_test.argv[0] == sys.executable
    assert run_test.argv[-3:] == ("-cpu", "cortex-a76", executable)


def test_rust_wasm_value_tests_use_wasmtime_runner(tmp_path: Path) -> None:
    executable = str(tmp_path / "rust" / "target" / "wasm32" / "deps" / "values.wasm")
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="wasm32_simd128",
                        file_stem="wasm32_simd128",
                        family="wasm32",
                        target_features=("+simd128",),
                        target="wasm32-wasip1",
                        runner=VerifyRunner(kind="wasmtime", profile="default"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "build-tests":
            return BuildCommandResult(
                command=command,
                returncode=0,
                stdout=json.dumps(
                    {"reason": "compiler-artifact", "executable": executable}
                ),
            )
        return BuildCommandResult(command=command, returncode=0)

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
            rust_compiler=sys.executable,
            run_value_tests=True,
            wasmtime_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "preflight",
        "target-preflight",
        "build-tests",
        "test",
    ]
    assert "--target" in seen[1].argv
    assert "wasm32-wasip1" in seen[1].argv
    build_tests = next(command for command in seen if command.step == "build-tests")
    assert "--target" in build_tests.argv
    assert "wasm32-wasip1" in build_tests.argv
    assert "--message-format=json" in build_tests.argv
    assert _env(build_tests)["CARGO_TARGET_WASM32_WASIP1_RUSTFLAGS"] == (
        "-C target-feature=+simd128 --cfg tsl_value_tests"
    )
    assert seen[-1].argv == (sys.executable, executable)


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
                        target_features=("+avx2",),
                        runner=VerifyRunner(kind="sde", profile="hsw"),
                    ),
                ),
            ),
        )
    )
    seen: list[BuildCommand] = []

    def runner(command: BuildCommand) -> BuildCommandResult:
        seen.append(command)
        if command.step == "host-target":
            return BuildCommandResult(
                command=command,
                returncode=0,
                stdout="host: x86_64-unknown-linux-gnu\n",
            )
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
        config=_config(
            rust_compiler=sys.executable,
            run_value_tests=True,
            sde_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == [
        "preflight",
        "host-target",
        "target-preflight",
        "build-tests",
        "test",
    ]
    build_tests = next(command for command in seen if command.step == "build-tests")
    assert "--no-run" in build_tests.argv
    assert "--message-format=json" in build_tests.argv
    assert "--target-dir" in build_tests.argv
    assert str(tmp_path / "rust" / "target" / "avx2") in build_tests.argv
    assert build_tests.argv[0] == "cargo"
    assert "--target" in build_tests.argv
    assert "x86_64-unknown-linux-gnu" in build_tests.argv
    assert _env(build_tests)[
        "CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_RUSTFLAGS"
    ] == "-C target-feature=+avx2 --cfg tsl_value_tests"
    assert "RUSTFLAGS" not in _env(build_tests)
    assert seen[-1].argv == (sys.executable, "-hsw", "--", executable)


def test_rust_sde_value_tests_diagnose_missing_test_binaries(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        runner=VerifyRunner(kind="sde", profile="hsw"),
                    ),
                ),
            ),
        )
    )

    def runner(command: BuildCommand) -> BuildCommandResult:
        return BuildCommandResult(command=command, returncode=0, stdout="{}")

    report = verify_generated_project(
        tmp_path,
        project,
        runner,
        config=_config(
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
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        runner=VerifyRunner(kind="sde", profile="hsw"),
                    ),
                ),
            ),
        )
    )

    report = verify_generated_project(
        tmp_path,
        project,
        config=_config(
            rust_compiler=sys.executable,
            run_value_tests=True,
            sde_path="/definitely/missing/sde",
        ),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-RUNNER-MISSING"
    ]


def test_explicit_wasmtime_path_must_exist(tmp_path: Path) -> None:
    project = VerifyProject(
        backends=(
            VerifyBackend(
                backend_id="rust",
                root_path="rust",
                profiles=(
                    VerifyProfile(
                        profile_name="wasm32_simd128",
                        file_stem="wasm32_simd128",
                        runner=VerifyRunner(kind="wasmtime", profile="default"),
                    ),
                ),
            ),
        )
    )

    report = verify_generated_project(
        tmp_path,
        project,
        config=_config(
            rust_compiler=sys.executable,
            run_value_tests=True,
            wasmtime_path="/definitely/missing/wasmtime",
        ),
    )

    assert [diagnostic.code for diagnostic in report.diagnostics] == [
        "TSL-BUILD-VERIFY-RUNNER-MISSING"
    ]
    assert "wasmtime" in report.diagnostics[0].message


def _env(command: BuildCommand) -> dict[str, str]:
    return {item.key: item.value for item in command.env}


def _configure_arg(argv: tuple[str, ...], prefix: str) -> str | None:
    return next((arg for arg in argv if arg.startswith(prefix)), None)
