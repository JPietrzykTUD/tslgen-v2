"""C++ build verifier driver."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tslc.diagnostics import Diagnostic
from tslc.output._verify_common import (
    cmake_cross_emulator,
    configured_emulator_kinds,
    cpp_environment,
    cpp_target,
    effective_cpp_compiler,
    emulator_prefix,
    missing_executable,
)
from tslc.output.verify_drivers import VerifyBackendDriver
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandResult,
    BuildCommandRunner,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
)


def create_cpp_verify_driver() -> VerifyBackendDriver:
    return VerifyBackendDriver(
        backend_id="cpp",
        required_tools=("cmake",),
        prepare_backend=_prepare_cpp_backend,
        command_groups=_cpp_command_groups,
        after_successful_command=_after_noop_command,
    )


def _prepare_cpp_backend(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
    results: list[BuildCommandResult],
    diagnostics: list[Diagnostic],
    skipped: list[str],
) -> VerifyBackend | None:
    compiler = effective_cpp_compiler(config, backend)
    missing_compiler = missing_executable(compiler[0])
    if missing_compiler is not None:
        skipped.append(f"cpp: C++ compiler {missing_compiler} not found")
        return None
    preflight = _cpp_preflight_command(root, backend, compiler)
    if isinstance(preflight, Diagnostic):
        diagnostics.append(preflight)
        return None
    result = runner(preflight)
    results.append(result)
    if result.returncode != 0:
        skipped.append(_cpp_preflight_skip(result))
        return None
    target_profiles: list[VerifyProfile] = []
    for profile in backend.profiles:
        target_preflight = _cpp_target_preflight_command(
            root,
            backend,
            profile,
            config,
            compiler,
        )
        if target_preflight is None:
            target_profiles.append(profile)
            continue
        if isinstance(target_preflight, Diagnostic):
            diagnostics.append(target_preflight)
            continue
        result = runner(target_preflight)
        results.append(result)
        if result.returncode != 0:
            skipped.append(_cpp_target_preflight_skip(result))
            continue
        target_profiles.append(profile)
    return VerifyBackend(
        backend_id=backend.backend_id,
        root_path=backend.root_path,
        profiles=tuple(target_profiles),
    )


def _after_noop_command(
    result: BuildCommandResult,
    profiles_by_name: Mapping[str, VerifyProfile],
    config: BuildVerifierConfig,
    runner: BuildCommandRunner,
    results: list[BuildCommandResult],
    diagnostics: list[Diagnostic],
) -> None:
    del result, profiles_by_name, config, runner, results, diagnostics


def _cpp_command_groups(
    root: Path,
    backend: VerifyBackend,
    config: BuildVerifierConfig,
) -> tuple[tuple[BuildCommand, ...], ...]:
    project_root = root / backend.root_path
    env = cpp_environment(config, backend)
    groups: list[tuple[BuildCommand, ...]] = []
    for profile in backend.profiles:
        build_dir = project_root / "build" / profile.file_stem
        configure_args = _cpp_configure_args(project_root, build_dir, profile, config)
        commands: list[BuildCommand] = []
        if config.run_value_tests and configured_emulator_kinds(config):
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="clean",
                    argv=("cmake", "-E", "rm", "-rf", str(build_dir)),
                    cwd=root,
                    env=env,
                )
            )
        commands.extend(
            [
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="configure",
                    argv=configure_args,
                    cwd=root,
                    env=env,
                ),
                # Build only the substrate-compile target by default; the heavy
                # value-test binary is built (and run) only when value testing is
                # requested, so the standard gate keeps its single-target cost.
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="build",
                    argv=("cmake", "--build", str(build_dir), "--target", "tsl_smoke"),
                    cwd=root,
                    env=env,
                ),
            ]
        )
        if config.run_value_tests:
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="build-values",
                    argv=("cmake", "--build", str(build_dir), "--target", "tsl_values"),
                    cwd=root,
                    env=env,
                    severity_on_failure="warning",
                )
            )
            commands.append(
                BuildCommand(
                    backend_id="cpp",
                    profile_name=profile.profile_name,
                    step="test",
                    argv=(
                        "ctest",
                        "--test-dir",
                        str(build_dir),
                        "--output-on-failure",
                    ),
                    cwd=root,
                    env=env,
                    severity_on_failure="warning",
                )
            )
        groups.append(tuple(commands))
    return tuple(groups)


def _cpp_configure_args(
    project_root: Path,
    build_dir: Path,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    args = [
        "cmake",
        "-S",
        str(project_root),
        "-B",
        str(build_dir),
        f"-DTSL_PROFILE={profile.profile_name}",
    ]
    target = cpp_target(profile, config)
    if target is not None:
        args.extend(
            (
                "-DCMAKE_SYSTEM_NAME=Linux",
                "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
                "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
                f"-DCMAKE_CXX_COMPILER_TARGET={target}",
            )
        )
    cross_emulator = cmake_cross_emulator(profile, config)
    if cross_emulator:
        args.append(f"-DCMAKE_CROSSCOMPILING_EMULATOR={';'.join(cross_emulator)}")
    test_launcher = _cmake_test_launcher(profile, config)
    if test_launcher:
        args.append(f"-DTSL_TEST_LAUNCHER={';'.join(test_launcher)}")
    return tuple(args)


def _cmake_test_launcher(
    profile: VerifyProfile,
    config: BuildVerifierConfig,
) -> tuple[str, ...]:
    if profile.emulator is None or profile.emulator.kind != "sde":
        return ()
    return emulator_prefix(profile, config)


def _cpp_preflight_command(
    root: Path,
    backend: VerifyBackend,
    compiler: tuple[str, ...],
) -> BuildCommand | Diagnostic:
    project_root = root / backend.root_path
    preflight_dir = project_root / "build" / "_compiler_preflight"
    source_path = preflight_dir / "tslc_compiler_check.cpp"
    object_path = preflight_dir / "tslc_compiler_check.o"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text("int main() { return 0; }\n", encoding="utf-8")
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=f"could not write C++ compiler preflight source under {preflight_dir}: {exc}",
        )

    return BuildCommand(
        backend_id="cpp",
        profile_name="_toolchain",
        step="preflight",
        argv=(
            *compiler,
            "-x",
            "c++",
            "-std=c++17",
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ),
        cwd=root,
    )


def _cpp_target_preflight_command(
    root: Path,
    backend: VerifyBackend,
    profile: VerifyProfile,
    config: BuildVerifierConfig,
    compiler: tuple[str, ...],
) -> BuildCommand | Diagnostic | None:
    target = cpp_target(profile, config)
    if target is None:
        return None

    project_root = root / backend.root_path
    preflight_dir = project_root / "build" / "_compiler_preflight" / profile.file_stem
    source_path = preflight_dir / "tslc_target_check.cpp"
    object_path = preflight_dir / "tslc_target_check.o"
    try:
        preflight_dir.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "\n".join(
                (
                    "#include <array>",
                    "#if defined(__aarch64__)",
                    "#include <arm_neon.h>",
                    "#endif",
                    "int main() { std::array<int, 1> value{}; return value[0]; }",
                    "",
                )
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-BUILD-VERIFY-PREFLIGHT-ERROR",
            message=(
                "could not write C++ target preflight source for profile "
                f"{profile.profile_name} under {preflight_dir}: {exc}"
            ),
        )

    return BuildCommand(
        backend_id="cpp",
        profile_name=profile.profile_name,
        step="target-preflight",
        argv=(
            *compiler,
            f"--target={target}",
            "-x",
            "c++",
            "-std=c++17",
            *profile.cpp_flags,
            "-c",
            str(source_path),
            "-o",
            str(object_path),
        ),
        cwd=root,
        env=cpp_environment(config, backend),
    )


def _cpp_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        "cpp: C++ compiler preflight failed with exit code "
        f"{result.returncode}: {command_text}{suffix}"
    )


def _cpp_target_preflight_skip(result: BuildCommandResult) -> str:
    command_text = " ".join(result.command.argv)
    detail = result.stderr.strip() or result.stdout.strip()
    suffix = f": {detail}" if detail else ""
    return (
        f"cpp: profile {result.command.profile_name} target preflight failed "
        f"with exit code {result.returncode}: {command_text}{suffix}"
    )
