"""Rust build verifier driver."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections.abc import Mapping

from tslc.diagnostics import Diagnostic, Severity
from tslc.output._verify_common import command_failure_diagnostic, missing_executable
from tslc.output._verify_runners import runner_prefix
from tslc.output._verify_rust_config import (
    effective_rust_compiler,
    rust_environment,
    rust_linker,
    rust_target,
    rust_target_args,
)
from tslc.output.verify_drivers import (
    BackendPreparation,
    CommandFollowUp,
    VerifyBackendDriver,
)
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandEnvironment,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
)
_RUST_WARNING_FLAGS = (
    "-Dwarnings",
    "-Dinvalid-value",
    "-Dprivate-interfaces",
    "-Dprivate-bounds",
)
_RUSTDOC_WARNING_FLAGS = (
    "-Dwarnings",
    "-Drustdoc::broken-intra-doc-links",
    "-Drustdoc::bare-urls",
)
_CLIPPY_WARNING_FLAGS = (
    "-Awarnings",
    "-Dclippy::correctness",
    "-Dclippy::suspicious",
)


def create_rust_verify_driver() -> VerifyBackendDriver:
    return VerifyBackendDriver(
        backend_id="rust",
        required_tools=("cargo",),
        prepare_backend=_prepare_rust_backend,
        command_groups=_rust_command_groups,
        after_successful_command=_after_rust_command,
        prepare_command_environment=_prepare_rust_command_environment,
    )


def _prepare_rust_command_environment(
    command: BuildCommand, environment: dict[str, str]
) -> None:
    if not command.argv or Path(command.argv[0]).name != "cargo":
        return
    wrapper = _rustc_stdin_guard(command.cwd)
    previous_wrapper = environment.get("RUSTC_WRAPPER")
    if previous_wrapper and Path(previous_wrapper).resolve() != wrapper:
        environment["TSLC_RUSTC_WRAPPER_NEXT"] = previous_wrapper
    else:
        environment.pop("TSLC_RUSTC_WRAPPER_NEXT", None)
    environment["RUSTC_WRAPPER"] = str(wrapper)


def _rustc_stdin_guard(command_root: Path) -> Path:
    wrapper = command_root.resolve() / ".tslctmp" / "rust" / "rustc-stdin-guard.py"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    script = _rustc_stdin_guard_script()
    if not wrapper.exists() or wrapper.read_text(encoding="utf-8") != script:
        wrapper.write_text(script, encoding="utf-8")
        wrapper.chmod(0o755)
    return wrapper


def _rustc_stdin_guard_script() -> str:
    return "\n".join(
        (
            f"#!{sys.executable}",
            "from __future__ import annotations",
            "",
            "import os",
            "import subprocess",
            "import sys",
            "",
            "",
            "def main() -> int:",
            "    if len(sys.argv) < 2:",
            "        return 1",
            "    rustc_args = sys.argv[2:]",
            "    delegate = os.environ.get('TSLC_RUSTC_WRAPPER_NEXT')",
            "    if delegate:",
            "        argv = (delegate, *sys.argv[1:])",
            "    else:",
            "        argv = tuple(sys.argv[1:])",
            "    stdin_payload = (",
            "        b'fn main() {}\\n'",
            "        if _is_cargo_target_info_probe(rustc_args)",
            "        else None",
            "    )",
            "    completed = subprocess.run(",
            "        argv,",
            "        input=stdin_payload,",
            "        check=False,",
            "        pass_fds=_jobserver_fds(),",
            "    )",
            "    return completed.returncode",
            "",
            "",
            "def _is_cargo_target_info_probe(args: list[str]) -> bool:",
            "    return (",
            "        '-' in args",
            "        and '--crate-name' in args",
            "        and '___' in args",
            "        and '--print=file-names' in args",
            "        and '--print=cfg' in args",
            "    )",
            "",
            "",
            "def _jobserver_fds() -> tuple[int, ...]:",
            "    fds: set[int] = set()",
            "    for token in os.environ.get('CARGO_MAKEFLAGS', '').split():",
            "        if token.startswith('--jobserver-auth='):",
            "            _add_fds(fds, token.removeprefix('--jobserver-auth='))",
            "        elif token.startswith('--jobserver-fds='):",
            "            _add_fds(fds, token.removeprefix('--jobserver-fds='))",
            "    return tuple(sorted(fds))",
            "",
            "",
            "def _add_fds(fds: set[int], value: str) -> None:",
            "    for part in value.split(','):",
            "        try:",
            "            fd = int(part)",
            "            os.fstat(fd)",
            "        except (OSError, ValueError):",
            "            continue",
            "        fds.add(fd)",
            "",
            "",
            "if __name__ == '__main__':",
            "    raise SystemExit(main())",
            "",
        )
    )


def _prepare_rust_backend(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
) -> BackendPreparation:
    results: list[BuildCommandResult] = []
    diagnostics: list[Diagnostic] = []
    skipped: list[str] = []
    compiler = effective_rust_compiler(config)
    missing_compiler = missing_executable(compiler)
    if missing_compiler is not None:
        skipped.append(f"rust: Rust compiler {missing_compiler} not found")
        return BackendPreparation(backend=None, skipped=tuple(skipped))
    preflight = _rust_preflight_command(root, backend, compiler)
    if isinstance(preflight, Diagnostic):
        diagnostics.append(preflight)
        return BackendPreparation(backend=None, diagnostics=tuple(diagnostics))
    result = runner(preflight)
    results.append(result)
    if result.returncode != 0:
        skipped.append(_rust_preflight_skip(result))
        return BackendPreparation(
            backend=None,
            commands=tuple(results),
            skipped=tuple(skipped),
        )
    if config.run_quality_checks:
        clippy = _rust_clippy_executable(config)
        if missing_executable(clippy) is not None:
            skipped.append(f"rust: optional Clippy component {clippy} not found")
    target_profiles: list[VerifyProfile] = []
    for profile in backend.profiles:
        target = rust_target(profile, config)
        if target is None:
            target_profiles.append(profile)
            continue
        target_preflight = _rust_target_preflight_command(
            root,
            backend,
            profile,
            config,
            compiler,
        )
        if isinstance(target_preflight, Diagnostic):
            diagnostics.append(target_preflight)
            continue
        result = runner(target_preflight)
        results.append(result)
        if result.returncode != 0:
            skipped.append(_rust_target_preflight_skip(result))
            continue
        target_profiles.append(profile)
    return BackendPreparation(
        backend=VerifyBackend(
            backend_id=backend.backend_id,
            root_path=backend.root_path,
            profiles=tuple(target_profiles),
        ),
        commands=tuple(results),
        diagnostics=tuple(diagnostics),
        skipped=tuple(skipped),
    )


def _after_rust_command(
    result: BuildCommandResult,
    profiles_by_name: Mapping[str, VerifyProfile],
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
) -> CommandFollowUp:
    if result.command.step != "build-tests":
        return CommandFollowUp()
    profile = profiles_by_name[result.command.profile_name]
    followups, followup_diagnostics = _rust_emulated_test_commands(
        result,
        profile,
        config,
    )
    results: list[BuildCommandResult] = []
    diagnostics: list[Diagnostic] = list(followup_diagnostics)
    for followup in followups:
        followup_result = runner(followup)
        results.append(followup_result)
        if followup_result.returncode != 0:
            diagnostics.append(command_failure_diagnostic(followup_result))
            break
    return CommandFollowUp(
        commands=tuple(results),
        diagnostics=tuple(diagnostics),
    )


def _rust_command_groups(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    manifest = project_root / "Cargo.toml"
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        target_dir = project_root / "target" / profile.file_stem
        cargo_profile_args = (
            "--manifest-path",
            str(manifest),
            "--no-default-features",
            *rust_target_args(profile, config),
            "--target-dir",
            str(target_dir),
        )
        if config.run_quality_checks:
            groups.append(
                (
                    BuildCommand(
                        backend_id="rust",
                        profile_name=profile.profile_name,
                        step="check-warnings",
                        argv=("cargo", "check", *cargo_profile_args, "--all-targets"),
                        cwd=root,
                        env=_rust_lint_environment(
                            profile,
                            config,
                            key="RUSTFLAGS",
                            flags=_RUST_WARNING_FLAGS,
                        ),
                    ),
                )
            )
            groups.append(
                (
                    BuildCommand(
                        backend_id="rust",
                        profile_name=profile.profile_name,
                        step="rustdoc",
                        argv=("cargo", "doc", *cargo_profile_args, "--no-deps"),
                        cwd=root,
                        env=_rust_lint_environment(
                            profile,
                            config,
                            key="RUSTDOCFLAGS",
                            flags=_RUSTDOC_WARNING_FLAGS,
                        ),
                    ),
                )
            )
            clippy = _rust_clippy_executable(config)
            if missing_executable(clippy) is None:
                groups.append(
                    (
                        BuildCommand(
                            backend_id="rust",
                            profile_name=profile.profile_name,
                            step="clippy",
                            argv=(
                                clippy,
                                "clippy",
                                *cargo_profile_args,
                                "--all-targets",
                                "--",
                                *_CLIPPY_WARNING_FLAGS,
                            ),
                            cwd=root,
                            env=rust_environment(profile, config),
                        ),
                    )
                )
        # Build verification still uses `cargo test` so generated test targets
        # compile. Cross-target builds cannot execute those binaries natively, so
        # they use --no-run unless value-test mode has a runner follow-up.
        severity: Severity = "error"
        step = "test"
        extra_args: tuple[str, ...] = ()
        if not config.run_value_tests and rust_target(profile, config) is not None:
            step = "build-tests"
            extra_args = ("--no-run",)
        if config.run_value_tests:
            # Value testing adds a verifier-owned cfg (so `cargo test`
            # compiles+runs the generated value tests); without it
            # `tests/values.rs` is cfg'd empty. A value-mode failure is reported as a warning
            # (report-then-promote), like the C++ ctest step.
            severity = "warning"
            if runner_prefix(profile, config):
                step = "build-tests"
                extra_args = ("--no-run", "--message-format=json")
        commands = [
            BuildCommand(
                backend_id="rust",
                profile_name=profile.profile_name,
                step=step,
                argv=(
                    "cargo",
                    "test",
                    "--manifest-path",
                    str(manifest),
                    "--no-default-features",
                    *rust_target_args(profile, config),
                    "--target-dir",
                    str(target_dir),
                    *extra_args,
                ),
                cwd=root,
                env=(
                    _rust_environment_with_cfg(profile, config, "tsl_value_tests")
                    if config.run_value_tests
                    else rust_environment(profile, config)
                ),
                severity_on_failure=severity,
            )
        ]
        commands.extend(
            BuildCommand(
                backend_id="rust",
                profile_name=profile.profile_name,
                step="compile-failure",
                argv=(
                    "cargo",
                    "build",
                    "--manifest-path",
                    str(
                        project_root
                        / "verify"
                        / failure.target_name
                        / "Cargo.toml"
                    ),
                    *rust_target_args(profile, config),
                    "--target-dir",
                    str(target_dir),
                ),
                cwd=root,
                env=rust_environment(profile, config),
                expected_failure_marker=failure.marker,
            )
            for failure in profile.compile_failures
        )
        groups.append(tuple(commands))
    return tuple(groups)


def _rust_environment_with_cfg(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
    cfg: str,
) -> tuple[BuildCommandEnvironment, ...]:
    environment = list(rust_environment(profile, config))
    cfg_flag = f"--cfg {cfg}"
    for index, item in enumerate(environment):
        if item.key == "RUSTFLAGS":
            environment[index] = BuildCommandEnvironment(
                key="RUSTFLAGS",
                value=f"{item.value} {cfg_flag}",
            )
            break
    else:
        environment.append(BuildCommandEnvironment(key="RUSTFLAGS", value=cfg_flag))
    return tuple(environment)


def _rust_clippy_executable(config: BuildVerifierConfig) -> str:
    return config.tool_path("rust-clippy") or "cargo-clippy"


def _rust_lint_environment(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
    *,
    key: str,
    flags: tuple[str, ...],
) -> tuple[BuildCommandEnvironment, ...]:
    environment = list(rust_environment(profile, config))
    suffix = " ".join(flags)
    for index, item in enumerate(environment):
        if item.key != key:
            continue
        environment[index] = BuildCommandEnvironment(
            key=key,
            value=f"{item.value} {suffix}",
        )
        break
    else:
        environment.append(BuildCommandEnvironment(key=key, value=suffix))
    return tuple(environment)


def _rust_emulated_test_commands(
    result: BuildCommandResult,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], tuple[Diagnostic, ...]]:
    prefix = runner_prefix(profile, config)
    if not prefix:
        return (), ()

    executables = _rust_test_executables(result.stdout)
    if not executables:
        return (
            (),
            (
                Diagnostic(
                    severity=result.command.severity_on_failure,
                    code="TSL-BUILD-VERIFY-NO-RUST-TEST-BINARIES",
                    message=(
                        f"rust profile {profile.profile_name} value-test build produced "
                        "no runnable test binaries"
                    ),
                ),
            ),
        )

    return (
        tuple(
            BuildCommand(
                backend_id="rust",
                profile_name=profile.profile_name,
                step="test",
                argv=(*prefix, executable),
                cwd=result.command.cwd,
                severity_on_failure=result.command.severity_on_failure,
            )
            for executable in executables
        ),
        (),
    )


def _rust_test_executables(stdout: str) -> tuple[str, ...]:
    executables: list[str] = []
    seen: set[str] = set()
    for line in stdout.splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("reason") != "compiler-artifact":
            continue
        executable = data.get("executable")
        if not isinstance(executable, str) or not executable:
            continue
        if executable not in seen:
            seen.add(executable)
            executables.append(executable)
    return tuple(executables)


def _rust_preflight_command(
    root: Path,
    backend: VerifyBackend,
    compiler: str,
) -> BuildCommand | Diagnostic:
    project_root = root / backend.root_path
    preflight_dir = project_root / "target" / "_compiler_preflight"
    source_path = preflight_dir / "tslc_compiler_check.rs"
    binary_path = preflight_dir / "tslc_compiler_check"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text("fn main() {}\n", encoding="utf-8")
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=f"could not write Rust compiler preflight source under {preflight_dir}: {exc}",
        )

    return BuildCommand(
        backend_id="rust",
        profile_name="_toolchain",
        step="preflight",
        argv=(
            compiler,
            "--edition=2021",
            str(source_path),
            "-o",
            str(binary_path),
        ),
        cwd=root,
    )


def _rust_target_preflight_command(
    root: Path,
    backend: VerifyBackend,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
    compiler: str,
) -> BuildCommand | Diagnostic:
    target = rust_target(profile, config)
    if target is None:
        raise ValueError("rust target preflight requires a concrete target")

    project_root = root / backend.root_path
    preflight_dir = project_root / "target" / "_compiler_preflight" / profile.file_stem
    source_path = preflight_dir / "tslc_target_check.rs"
    binary_path = preflight_dir / "tslc_target_check"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text("fn main() {}\n", encoding="utf-8")
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=(
                "could not write Rust target preflight source for profile "
                f"{profile.profile_name} under {preflight_dir}: {exc}"
            ),
        )

    return BuildCommand(
        backend_id="rust",
        profile_name=profile.profile_name,
        step="target-preflight",
        argv=(
            compiler,
            "--edition=2021",
            "--target",
            target,
            *_rust_linker_args(profile, config),
            str(source_path),
            "-o",
            str(binary_path),
        ),
        cwd=root,
        env=rust_environment(profile, config),
    )


def _rust_linker_args(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    linker = rust_linker(profile, config)
    return ("-C", f"linker={linker}") if linker is not None else ()


def _rust_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        "rust: Rust compiler preflight failed with exit code "
        f"{result.returncode}: {command_text}{suffix}"
    )


def _rust_target_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        f"rust: profile {result.command.profile_name} target preflight failed "
        f"with exit code {result.returncode}: {command_text}{suffix}"
    )
