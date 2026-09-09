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
    value_test_job = values.split("\n  generated-value-tests:\n", 1)[1].split(
        "\n  generated-", 1
    )[0]

    assert "Generated build and values" in values
    assert "./dev.sh test" in value_test_job
    assert "./dev.sh build" not in value_test_job
    assert "Generated Clang overlay build and values" in values
    assert "Generated benchmarks (x86 policy and ARM smoke)" in values
    assert not Path(".github/workflows/generated-build.yml").exists()
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "actions/workflows/generated-build.yml" not in readme
    assert "actions/workflows/docs.yml" not in readme


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


def test_atomic_release_workflow_is_the_only_publication_owner() -> None:
    release = _workflow("release.yml")
    assert "gh release create" in release
    assert "gh release upload" in release
    assert "contents: write" in release
    assert "environment: release" in release
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        if path.name == "release.yml":
            continue
        workflow = path.read_text(encoding="utf-8")
        assert "gh release create" not in workflow
        assert "gh release upload" not in workflow
        assert "contents: write" not in workflow


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
