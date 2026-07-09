"""Markdown summaries for generated-project verification."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from tslc.output.verify_model import BuildCommandResult, BuildVerificationReport
from tslc.render._common import slug
from tslc.value_tests.model import ValueTestProfilePlan, ValueTestProjectPlan


_TOOLCHAIN_PROFILE = "_toolchain"


@dataclass(frozen=True, slots=True)
class ProfileValueTestSummary:
    backend_id: str
    profile_name: str
    planned_primitive_names: int
    planned_cases: int
    passed_cases: int
    failed_or_blocked_cases: int
    passed_test_commands: int
    total_test_commands: int
    passed_verify_commands: int
    total_verify_commands: int
    status: str


def append_markdown_summary(path: str | Path, markdown: str) -> None:
    """Append a Markdown summary to ``path``, creating parent directories."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = target.exists() and target.stat().st_size > 0
    with target.open("a", encoding="utf-8") as handle:
        if needs_separator:
            handle.write("\n")
        handle.write(markdown.rstrip())
        handle.write("\n")


def render_value_test_markdown_summary(
    test_plan: ValueTestProjectPlan | None,
    verify_report: BuildVerificationReport | None,
    *,
    run_value_tests: bool,
    title: str = "Generated value-test summary",
) -> str:
    """Render a GitHub-flavored Markdown value-test verification summary."""

    rows = value_test_profile_summaries(
        test_plan, verify_report, run_value_tests=run_value_tests
    )
    lines = [
        f"### {_escape_markdown_cell(title)}",
        "",
        (
            "Case pass/fail counts are assigned at profile test-command granularity; "
            "the generated runner currently reports one command result per profile."
        ),
        "",
        "| Backend | Profile | Planned primitive names | Planned cases | Passed cases | "
        "Failed/blocked cases | Test cmds | Verify cmds | Status |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    if rows:
        lines.extend(_summary_row(row) for row in rows)
    else:
        lines.append("| - | - | 0 | 0 | 0 | 0 | 0/0 | 0/0 | no profiles |")

    if verify_report is not None and verify_report.skipped:
        count = len(verify_report.skipped)
        suffix = "" if count == 1 else "s"
        lines.extend(
            [
                "",
                "> [!WARNING]",
                (
                    f"> {count} verification skip{suffix} reported. "
                    "A generated value-test run with skips is incomplete."
                ),
                "",
                f"#### Skipped Verification Notes ({count})",
                "",
            ]
        )
        lines.extend(f"- {_escape_markdown_text(note)}" for note in verify_report.skipped)

    return "\n".join(lines) + "\n"


def value_test_profile_summaries(
    test_plan: ValueTestProjectPlan | None,
    verify_report: BuildVerificationReport | None,
    *,
    run_value_tests: bool,
) -> tuple[ProfileValueTestSummary, ...]:
    """Summarize planned value tests joined to rendered verifier commands.

    Value-test plans use source profile names, while generated verifier commands
    use render-safe profile identifiers. Joining through the render slug keeps
    the summary aligned with the commands that actually ran.
    """

    profiles = {
        (profile.backend_id, slug(profile.profile_name)): profile
        for profile in (test_plan.profiles if test_plan is not None else ())
    }
    commands = _commands_by_profile(verify_report)
    keys = sorted(set(profiles) | set(commands))
    return tuple(
        _profile_summary(
            key[0],
            _display_profile_name(key[1], profiles.get(key)),
            profiles.get(key),
            tuple(commands.get(key, ())),
            run_value_tests=run_value_tests,
        )
        for key in keys
    )


def _display_profile_name(
    normalized_profile_name: str,
    profile: ValueTestProfilePlan | None,
) -> str:
    if profile is None:
        return normalized_profile_name
    return profile.profile_name


def _commands_by_profile(
    verify_report: BuildVerificationReport | None,
) -> dict[tuple[str, str], list[BuildCommandResult]]:
    commands: dict[tuple[str, str], list[BuildCommandResult]] = defaultdict(list)
    if verify_report is None:
        return commands
    for result in verify_report.commands:
        command = result.command
        if command.profile_name == _TOOLCHAIN_PROFILE:
            continue
        commands[(command.backend_id, command.profile_name)].append(result)
    return commands


def _profile_summary(
    backend_id: str,
    profile_name: str,
    profile: ValueTestProfilePlan | None,
    commands: tuple[BuildCommandResult, ...],
    *,
    run_value_tests: bool,
) -> ProfileValueTestSummary:
    cases = profile.cases if profile is not None else ()
    planned_cases = len(cases)
    planned_primitive_names = len({case.call_name for case in cases})
    test_commands = tuple(result for result in commands if result.command.step == "test")
    passed_test_commands = _passed_commands(test_commands)
    passed_verify_commands = _passed_commands(commands)
    has_failed_verify_command = passed_verify_commands != len(commands)

    status = _profile_status(
        planned_cases=planned_cases,
        commands=commands,
        test_commands=test_commands,
        run_value_tests=run_value_tests,
        has_failed_verify_command=has_failed_verify_command,
    )
    passed_cases = (
        planned_cases
        if run_value_tests
        and planned_cases > 0
        and status == "passed"
        else 0
    )
    failed_or_blocked_cases = (
        planned_cases
        if run_value_tests
        and planned_cases > 0
        and status != "passed"
        else 0
    )
    return ProfileValueTestSummary(
        backend_id=backend_id,
        profile_name=profile_name,
        planned_primitive_names=planned_primitive_names,
        planned_cases=planned_cases,
        passed_cases=passed_cases,
        failed_or_blocked_cases=failed_or_blocked_cases,
        passed_test_commands=passed_test_commands,
        total_test_commands=len(test_commands),
        passed_verify_commands=passed_verify_commands,
        total_verify_commands=len(commands),
        status=status,
    )


def _profile_status(
    *,
    planned_cases: int,
    commands: tuple[BuildCommandResult, ...],
    test_commands: tuple[BuildCommandResult, ...],
    run_value_tests: bool,
    has_failed_verify_command: bool,
) -> str:
    if has_failed_verify_command:
        return "failed"
    if not run_value_tests:
        return "build-only" if commands else "skipped"
    if planned_cases == 0:
        return "passed" if commands else "skipped"
    if not commands:
        return "skipped"
    if not test_commands:
        return "not run"
    if _passed_commands(test_commands) == len(test_commands):
        return "passed"
    return "failed"


def _passed_commands(commands: tuple[BuildCommandResult, ...]) -> int:
    return sum(1 for result in commands if result.returncode == 0)


def _summary_row(row: ProfileValueTestSummary) -> str:
    return (
        f"| {_escape_markdown_cell(row.backend_id)} "
        f"| {_escape_markdown_cell(row.profile_name)} "
        f"| {row.planned_primitive_names} "
        f"| {row.planned_cases} "
        f"| {row.passed_cases} "
        f"| {row.failed_or_blocked_cases} "
        f"| {row.passed_test_commands}/{row.total_test_commands} "
        f"| {row.passed_verify_commands}/{row.total_verify_commands} "
        f"| {_escape_markdown_cell(row.status)} |"
    )


def _escape_markdown_cell(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def _escape_markdown_text(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


__all__ = [
    "ProfileValueTestSummary",
    "append_markdown_summary",
    "render_value_test_markdown_summary",
    "value_test_profile_summaries",
]
