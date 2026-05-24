from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import sys


@dataclass(frozen=True, slots=True)
class QuarantinedPath:
    path: str
    reason: str
    future_milestone: str


@dataclass(frozen=True, slots=True)
class ValidationCommand:
    name: str
    argv: tuple[str, ...]
    description: str
    env: tuple[tuple[str, str], ...] = ()

    def command_text(self) -> str:
        env_prefix = tuple(f"{key}={shlex.quote(value)}" for key, value in self.env)
        return " ".join((*env_prefix, *(shlex.quote(part) for part in self.argv)))


@dataclass(frozen=True, slots=True)
class ValidationProfile:
    name: str
    accepted_source_paths: tuple[str, ...]
    accepted_test_paths: tuple[str, ...]
    quarantined_paths: tuple[QuarantinedPath, ...]
    commands: tuple[ValidationCommand, ...]

    def command_by_name(self, name: str) -> ValidationCommand:
        for command in self.commands:
            if command.name == name:
                return command
        raise KeyError(name)


ACCEPTED_SOURCE_PATHS = (
    "tslgen/src/tslgen/__main__.py",
    "tslgen/src/tslgen/api.py",
    "tslgen/src/tslgen/cli.py",
    "tslgen/src/tslgen/analysis",
    "tslgen/src/tslgen/backends",
    "tslgen/src/tslgen/config",
    "tslgen/src/tslgen/core/__init__.py",
    "tslgen/src/tslgen/core/diagnostics.py",
    "tslgen/src/tslgen/core/frozen_map.py",
    "tslgen/src/tslgen/core/ordering.py",
    "tslgen/src/tslgen/core/result.py",
    "tslgen/src/tslgen/domain",
    "tslgen/src/tslgen/io",
    "tslgen/src/tslgen/lowering",
    "tslgen/src/tslgen/rendering",
    "tslgen/src/tslgen/reporting",
    "tslgen/src/tslgen/syntax",
    "tslgen/src/tslgen/testgen",
    "tslgen/src/tslgen/tooling",
    "tslgen/src/tslgen/validation",
)

ACCEPTED_TEST_PATHS = ("tslgen/tests/unit",)

QUARANTINED_PATHS = (
    QuarantinedPath(
        path="tslgen/src/tslgen/frontend",
        reason=(
            "pre-redesign parser sketch that imports old IR/context objects; "
            "the accepted parser boundary is tslgen.syntax"
        ),
        future_milestone="future exploratory-code cleanup",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/ir",
        reason=(
            "early primitive/signature sketch coupled to frontend/utils rather "
            "than the accepted domain, candidate, and lowering models"
        ),
        future_milestone="future IR/lowering milestone",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/middle_end",
        reason=(
            "legacy-shaped rewrite/filter sketch with unstable "
            "tslgen.src.tslgen imports and incomplete TSIL semantics"
        ),
        future_milestone="future lowering/backend rendering cleanup",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/utils",
        reason="helpers used by quarantined sketches, not accepted pipeline code",
        future_milestone="future exploratory-code cleanup",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/core/context.py",
        reason="early generation-context sketch that imports quarantined IR objects",
        future_milestone="future configuration/pipeline cleanup",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/core/passes.py",
        reason="syntactically incomplete early pass sketch",
        future_milestone="future exploratory-code cleanup",
    ),
    QuarantinedPath(
        path="tslgen/src/tslgen/core/types.py",
        reason="early type sketch used by quarantined IR/middle-end code",
        future_milestone="future type/lowering cleanup",
    ),
    QuarantinedPath(
        path="tslgen/tests/backend",
        reason="pre-redesign backend sketch tests outside accepted unit baseline",
        future_milestone="future backend rendering cleanup",
    ),
    QuarantinedPath(
        path="tslgen/tests/test_timing.py",
        reason="pre-redesign timing sketch outside accepted unit baseline",
        future_milestone="future performance/tooling milestone",
    ),
    QuarantinedPath(
        path="frozen",
        reason="legacy evidence only; not a runtime or validation target",
        future_milestone="none",
    ),
    QuarantinedPath(
        path="tsldata",
        reason=(
            "read-only corpus fixtures for accepted tests; not a Python lint/type "
            "target"
        ),
        future_milestone="future corpus normalization if needed",
    ),
)


def redesign_validation_profile() -> ValidationProfile:
    python = sys.executable
    mypy_env = (("MYPYPATH", "tslgen/src:tslgen/tests/unit"),)
    checked_paths = (*ACCEPTED_SOURCE_PATHS, *ACCEPTED_TEST_PATHS)
    commands = (
        ValidationCommand(
            name="current-corpus-probes",
            argv=(
                python,
                "-m",
                "pytest",
                "tslgen/tests/unit/test_tsl_parser.py::"
                "TslParserTests::test_all_current_tsldata_files_parse",
                "tslgen/tests/unit/test_implementation_specs.py::"
                "ImplementationSpecTests::"
                "test_scalar_blend_selection_ignores_unselected_current_corpus_shapes",
                "tslgen/tests/unit/test_validation_baseline.py::"
                "ValidationBaselineTests::"
                "test_public_entry_points_do_not_import_quarantined_modules",
            ),
            description=(
                "Run corpus smoke probes, including the selector-aware blend "
                "regression required by Milestone 21."
            ),
        ),
        ValidationCommand(
            name="unit-discovery",
            argv=(python, "-m", "unittest", "discover", "tslgen/tests/unit"),
            description="Run the accepted redesigned unit-test discovery surface.",
        ),
        ValidationCommand(
            name="compileall",
            argv=(python, "-m", "compileall", "-q", *checked_paths),
            description="Compile accepted redesigned modules and tests only.",
        ),
        ValidationCommand(
            name="ruff",
            argv=("ruff", "check", *checked_paths),
            description="Lint accepted redesigned modules and tests only.",
        ),
        ValidationCommand(
            name="mypy",
            argv=("mypy", "--explicit-package-bases", *checked_paths),
            env=mypy_env,
            description="Type-check accepted redesigned modules and tests only.",
        ),
        ValidationCommand(
            name="diff-check",
            argv=("git", "diff", "--check"),
            description="Reject whitespace errors in the working diff.",
        ),
    )
    return ValidationProfile(
        name="redesign-baseline",
        accepted_source_paths=ACCEPTED_SOURCE_PATHS,
        accepted_test_paths=ACCEPTED_TEST_PATHS,
        quarantined_paths=QUARANTINED_PATHS,
        commands=commands,
    )


def run_validation_profile(
    profile: ValidationProfile,
    *,
    repo_root: Path,
    command_names: Sequence[str] = (),
) -> int:
    commands = _commands_for_names(profile, command_names)
    for command in commands:
        print(f"==> {command.name}: {command.command_text()}", flush=True)
        env = os.environ.copy()
        env.update(dict(command.env))
        completed = subprocess.run(command.argv, cwd=repo_root, env=env, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


def _commands_for_names(
    profile: ValidationProfile,
    command_names: Sequence[str],
) -> tuple[ValidationCommand, ...]:
    selected_names = tuple(command_names)
    if not selected_names:
        return profile.commands
    commands_by_name = {command.name: command for command in profile.commands}
    unknown_names = tuple(name for name in selected_names if name not in commands_by_name)
    if unknown_names:
        raise ValueError(_unknown_command_message(profile, unknown_names))
    return tuple(commands_by_name[name] for name in selected_names)


def _unknown_command_message(
    profile: ValidationProfile,
    command_names: tuple[str, ...],
) -> str:
    available = ", ".join(command.name for command in profile.commands)
    unknown = ", ".join(command_names)
    return f"unknown validation command(s): {unknown}; available: {available}"


def format_profile(profile: ValidationProfile) -> str:
    lines = [f"Validation profile: {profile.name}", "", "Accepted source paths:"]
    lines.extend(f"- {path}" for path in profile.accepted_source_paths)
    lines.append("")
    lines.append("Accepted test paths:")
    lines.extend(f"- {path}" for path in profile.accepted_test_paths)
    lines.append("")
    lines.append("Quarantined paths:")
    lines.extend(
        f"- {entry.path}: {entry.reason} ({entry.future_milestone})"
        for entry in profile.quarantined_paths
    )
    lines.append("")
    lines.append("Commands:")
    lines.extend(
        f"- {command.name}: {command.command_text()}"
        for command in profile.commands
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the redesigned-code validation baseline."
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the validation profile without running commands",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=None,
        metavar="NAME",
        help="run only the named validation command; may be repeated",
    )
    args = parser.parse_args(argv)
    profile = redesign_validation_profile()
    if args.list:
        print(format_profile(profile))
        return 0
    repo_root = Path(__file__).resolve().parents[4]
    command_names = tuple(args.only or ())
    try:
        return run_validation_profile(
            profile,
            repo_root=repo_root,
            command_names=command_names,
        )
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
