"""Build verifier toolchain configuration behavior."""

from __future__ import annotations

import sys
from pathlib import Path

from tslc.output.verify import (
    BuildCommand,
    BuildCommandResult,
    BuildVerifierConfig,
    VerifyBackend,
    VerifyProfile,
    VerifyProject,
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


def _env(command: BuildCommand) -> dict[str, str]:
    return {item.key: item.value for item in command.env}
