"""Repository CI workflow contracts."""

from __future__ import annotations

from pathlib import Path
import subprocess


_PR_WORKFLOWS = (
    "coverage-ratchet.yml",
    "editor.yml",
    "generated-values.yml",
    "python.yml",
)
_IMAGE_WORKFLOWS = (
    "generated-package.yml",
    "generated-values.yml",
)


def test_pr_workflows_cover_merge_queue_and_use_shared_scope() -> None:
    for name in _PR_WORKFLOWS:
        workflow = _workflow(name)
        assert "  merge_group:\n" in workflow
        assert "uses: ./.github/workflows/ci-scope.yml" in workflow


def test_generated_workflows_reuse_content_addressed_images() -> None:
    for name in _IMAGE_WORKFLOWS:
        workflow = _workflow(name)
        assert "needs.scope.outputs.ci_image" in workflow
        assert 'reuse-existing: "true"' in workflow
        assert "-tslc-ci:${GITHUB_SHA}" not in workflow


def test_generated_values_subsume_the_profile_build_matrix() -> None:
    values = _workflow("generated-values.yml")

    assert "Generated build and values" in values
    assert "./dev.sh test" in values
    assert "./dev.sh build" not in values
    assert "Generated Clang overlay build and values" in values
    assert "Generated benchmarks (x86 policy and ARM smoke)" in values
    assert not Path(".github/workflows/generated-build.yml").exists()


def test_python_shard_paths_are_not_interpolated_as_shell_code() -> None:
    workflow = _workflow("python.yml")

    assert "matrix.python_test_shard.paths_json" in workflow
    assert "json.loads(os.environ" in workflow
    assert "python -m pytest -q ${{" not in workflow


def test_required_jobs_check_out_the_shared_result_checker() -> None:
    for name in _PR_WORKFLOWS:
        workflow = _workflow(name)
        required_job = workflow[workflow.index("\n  required-") :]
        checkout = required_job.index("uses: actions/checkout@v5")
        checker = required_job.index(
            "bash .github/scripts/require_ci_results.sh"
        )
        assert checkout < checker


def test_required_result_checker_enforces_selected_jobs() -> None:
    script = ".github/scripts/require_ci_results.sh"
    subprocess.run(
        ("bash", script, "selected", "true", "success", "omitted", "false", "skipped"),
        check=True,
    )
    failed = subprocess.run(
        ("bash", script, "selected", "true", "skipped"),
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1
    assert "expected success, got skipped" in failed.stdout


def _workflow(name: str) -> str:
    return Path(".github/workflows", name).read_text(encoding="utf-8")
