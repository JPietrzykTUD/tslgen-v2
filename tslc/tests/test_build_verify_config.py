"""Build verifier toolchain configuration behavior."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import tslc.output.verify as verify_module
from tslc.backend.cpp_capability import create_cpp_verify_driver
from tslc.backend.rust_capability import create_rust_verify_driver
from tslc.output.verify import (
    BuildCommand,
    BuildCommandResult,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyEmulator,
    VerifyProfile,
    VerifyProject,
    run_subprocess_build_command,
    verify_generated_project,
)
from tslc.output.verify_drivers import VerifyBackendDriver


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
                        rust_target_features=("+neon",),
                        rust_target="aarch64-unknown-linux-musl",
                        rust_linker="rust-lld",
                        emulator=VerifyEmulator(kind="qemu-aarch64", profile="cortex-a76"),
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
        config=BuildVerifierConfig.create(rust_compiler=sys.executable),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == ["preflight", "build-tests"]
    assert "--target" in seen[1].argv
    assert "aarch64-unknown-linux-musl" in seen[1].argv
    assert "--no-run" in seen[1].argv
    assert "--message-format=json" not in seen[1].argv
    env = _env(seen[1])
    assert env["CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER"] == "rust-lld"


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
                        emulator=VerifyEmulator(kind="sde", profile="hsw"),
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
                        emulator=VerifyEmulator(kind="sde", profile="mrm"),
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


def test_emulator_value_tests_skip_non_generic_profiles_without_matching_runner(
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
                        emulator=VerifyEmulator(kind="qemu-aarch64", profile="cortex-a76"),
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
        "cpp: profile neon requires qemu-aarch64, but that emulator is not "
        "configured; value-test verification skipped",
    )
    assert seen == []


def test_cpp_qemu_value_tests_configure_cmake_cross_emulator(tmp_path: Path) -> None:
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
                        cpp_flags=("-march=armv8-a+simd",),
                        cpp_target="aarch64-linux-gnu",
                        emulator=VerifyEmulator(kind="qemu-aarch64", profile="cortex-a76"),
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
    assert seen[0].argv[0] == "clang++"
    assert "--target=aarch64-linux-gnu" in seen[0].argv
    configure = seen[2].argv
    assert "-DCMAKE_CXX_COMPILER_TARGET=aarch64-linux-gnu" in configure
    assert (
        f"-DCMAKE_CROSSCOMPILING_EMULATOR={sys.executable};-cpu;cortex-a76"
        in configure
    )
    assert seen[-1].argv[0] == "ctest"


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
                        cpp_target="aarch64-linux-gnu",
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
                        rust_target_features=("+neon",),
                        rust_target="aarch64-unknown-linux-musl",
                        rust_linker="rust-lld",
                        emulator=VerifyEmulator(kind="qemu-aarch64", profile="cortex-a76"),
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
        config=BuildVerifierConfig.create(
            rust_compiler=sys.executable,
            run_value_tests=True,
            qemu_aarch64_path=sys.executable,
        ),
    )

    assert report.diagnostics == ()
    assert [command.step for command in seen] == ["preflight", "build-tests", "test"]
    assert "--target" in seen[1].argv
    assert "aarch64-unknown-linux-musl" in seen[1].argv
    env = _env(seen[1])
    assert env["CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER"] == "rust-lld"
    assert seen[2].argv == (sys.executable, "-cpu", "cortex-a76", executable)


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
                        emulator=VerifyEmulator(kind="sde", profile="hsw"),
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
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        emulator=VerifyEmulator(kind="sde", profile="hsw"),
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
                profiles=(
                    VerifyProfile(
                        profile_name="avx2",
                        file_stem="avx2",
                        emulator=VerifyEmulator(kind="sde", profile="hsw"),
                    ),
                ),
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
        "TSL-BUILD-VERIFY-EMULATOR-MISSING"
    ]


def _env(command: BuildCommand) -> dict[str, str]:
    return {item.key: item.value for item in command.env}
