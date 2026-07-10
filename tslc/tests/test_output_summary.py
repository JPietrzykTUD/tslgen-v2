from __future__ import annotations

from pathlib import Path

from tslc.output.summary import (
    append_markdown_summary,
    render_value_test_markdown_summary,
)
from tslc.output.verify_model import (
    BuildCommand,
    BuildCommandResult,
    BuildVerificationReport,
)
from tslc.value_tests.model import (
    ValueTestCasePlan,
    ValueTestInvocation,
    ValueTestProfilePlan,
    ValueTestProjectPlan,
)


def test_value_test_summary_counts_profile_case_and_command_results(tmp_path: Path) -> None:
    plan = ValueTestProjectPlan(
        profiles=(
            ValueTestProfilePlan(
                "cpp",
                "avx2",
                (
                    _case("add", "test_add_compiles"),
                    _case("sub", "test_sub_compiles"),
                ),
            ),
            ValueTestProfilePlan(
                "rust",
                "wasm32_simd128",
                (_case("add", "test_add_compiles"),),
            ),
        )
    )
    report = BuildVerificationReport(
        commands=(
            _result(tmp_path, "cpp", "avx2", "configure", 0),
            _result(tmp_path, "cpp", "avx2", "build-values", 0),
            _result(tmp_path, "cpp", "avx2", "test", 0),
            _result(tmp_path, "rust", "wasm32_simd128", "build-tests", 0),
            _result(tmp_path, "rust", "wasm32_simd128", "test", 1),
        ),
        diagnostics=(),
    )

    markdown = render_value_test_markdown_summary(
        plan,
        report,
        run_value_tests=True,
    )

    assert "| Backend | Profile | Planned primitive names |" in markdown
    assert (
        "| cpp | avx2 | 2 | 2 | 2 | 0 | 1/1 | 3/3 | passed |"
        in markdown
    )
    assert (
        "| rust | wasm32_simd128 | 1 | 1 | 0 | 1 | 0/1 | 1/2 | failed |"
        in markdown
    )


def test_value_test_summary_matches_source_profile_to_rendered_command_slug(
    tmp_path: Path,
) -> None:
    plan = ValueTestProjectPlan(
        profiles=(
            ValueTestProfilePlan(
                "cpp",
                "wasm32-simd128",
                (_case("add", "test_add_compiles"),),
            ),
        )
    )
    report = BuildVerificationReport(
        commands=(
            _result(tmp_path, "cpp", "wasm32_simd128", "configure", 0),
            _result(tmp_path, "cpp", "wasm32_simd128", "build-values", 0),
            _result(tmp_path, "cpp", "wasm32_simd128", "test", 0),
        ),
        diagnostics=(),
    )

    markdown = render_value_test_markdown_summary(
        plan,
        report,
        run_value_tests=True,
    )

    assert (
        "| cpp | wasm32-simd128 | 1 | 1 | 1 | 0 | 1/1 | 3/3 | passed |"
        in markdown
    )
    assert "| cpp | wasm32_simd128 |" not in markdown


def test_value_test_summary_marks_planned_cases_blocked_when_profile_is_skipped(
    tmp_path: Path,
) -> None:
    plan = ValueTestProjectPlan(
        profiles=(ValueTestProfilePlan("cpp", "sve", (_case("add", "test_add"),)),)
    )
    report = BuildVerificationReport(
        commands=(),
        diagnostics=(),
        skipped=("cpp: profile sve skipped | no runner",),
    )

    markdown = render_value_test_markdown_summary(
        plan,
        report,
        run_value_tests=True,
    )

    assert "| cpp | sve | 1 | 1 | 0 | 1 | 0/0 | 0/0 | skipped |" in markdown
    assert "> [!WARNING]" in markdown
    assert "1 verification skip reported" in markdown
    assert "#### Skipped Verification Notes (1)" in markdown
    assert "- cpp: profile sve skipped \\| no runner" in markdown


def test_append_markdown_summary_creates_parent_and_appends(tmp_path: Path) -> None:
    summary_path = tmp_path / "nested" / "summary.md"

    append_markdown_summary(summary_path, "### One\n")
    append_markdown_summary(summary_path, "### Two\n")

    assert summary_path.read_text(encoding="utf-8") == "### One\n\n### Two\n"


def _case(call_name: str, function_name: str) -> ValueTestCasePlan:
    return ValueTestCasePlan(
        kind="compile_only",
        function_name=function_name,
        case_name="compile",
        call_name=call_name,
        type_tag="si32",
        base_spelling="std::int32_t",
        lanes=4,
        invocation=ValueTestInvocation(result_kind="v"),
    )


def _result(
    cwd: Path,
    backend_id: str,
    profile_name: str,
    step: str,
    returncode: int,
) -> BuildCommandResult:
    command = BuildCommand(
        backend_id=backend_id,
        profile_name=profile_name,
        step=step,
        argv=(step,),
        cwd=cwd,
    )
    return BuildCommandResult(command=command, returncode=returncode)
