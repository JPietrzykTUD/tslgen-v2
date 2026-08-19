#!/usr/bin/env python3
"""Classify changed repository paths into conservative GitHub Actions scopes."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
# Bump ci-image-revision when intentionally refreshing mutable upstream image
# inputs (base distributions, stable toolchains, or remote installers).
CI_IMAGE_INPUTS = (
    Path(".devcontainer/Dockerfile"),
    Path(".devcontainer/ci-image-revision"),
    Path(".devcontainer/download_sde.py"),
    Path("requirements.txt"),
)


@dataclass(frozen=True, slots=True)
class CiScope:
    python_tests: bool = False
    python_full: bool = False
    python_type_check: bool = False
    pivot: bool = False
    coverage: bool = False
    editor_tests: bool = False
    editor_runtime: bool = False
    generated_profiles: bool = False
    clang_overlay: bool = False
    benchmarks: bool = False
    package: bool = False
    docs: bool = False
    changed_python_tests: tuple[str, ...] = ()

    @classmethod
    def full(cls) -> "CiScope":
        return cls(
            python_tests=True,
            python_full=True,
            python_type_check=True,
            pivot=True,
            coverage=True,
            editor_tests=True,
            editor_runtime=True,
            generated_profiles=True,
            clang_overlay=True,
            benchmarks=True,
            package=True,
            docs=True,
        )


def classify_paths(paths: tuple[str, ...]) -> CiScope:
    changed = tuple(sorted({_normalize_path(path) for path in paths if path.strip()}))
    if not changed or any(_is_unclassified(path) for path in changed):
        return CiScope.full()

    shared_ci = _any_path(changed, prefixes=(".github/",))
    compiler = _any_path(
        changed,
        prefixes=("tslc/src/", "tsldata/"),
        exact=("tslc/pyproject.toml", "tslc.toml", "dev.sh", "requirements.txt"),
    )
    profiles = _any_path(changed, prefixes=("supplementary/buildsystem/",))
    changed_python_tests = tuple(
        path
        for path in changed
        if path.startswith("tslc/tests/test_") and path.endswith(".py")
    )
    test_support = (
        any(
            path.startswith("tslc/tests/") and path not in changed_python_tests
            for path in changed
        )
        or "pytest.ini" in changed
    )

    python_full = shared_ci or compiler or profiles or test_support
    python_tests = python_full or bool(changed_python_tests)
    python_type_check = shared_ci or _any_path(
        changed,
        prefixes=("tslc/src/",),
        exact=("tslc/pyproject.toml", "requirements.txt"),
    )

    generated_infrastructure = _any_path(
        changed,
        prefixes=(".devcontainer/", "supplementary/ci/"),
        exact=("compose.yaml",),
    )
    generated_profiles = (
        shared_ci or compiler or profiles or generated_infrastructure
    )
    clang_overlay = generated_profiles or _any_path(
        changed,
        exact=(
            "tslc/tests/test_build_verify.py",
            "tslc/tests/test_value_tests.py",
        ),
    )
    benchmarks = generated_profiles or _any_path(
        changed,
        exact=(
            "tslc/tests/test_benchmark_variants.py",
            "tslc/tests/test_rust_benchmark_rendering.py",
            "tslc/tests/test_rust_policy_consumption.py",
        ),
    )

    pivot = shared_ci or compiler or profiles or _any_path(
        changed,
        prefixes=("tools/pivot/",),
    )
    coverage = shared_ci or compiler or profiles or _any_path(
        changed,
        prefixes=("coverage/",),
    )
    editor_tests = shared_ci or compiler or _any_path(
        changed,
        prefixes=("editors/vscode-tsl/",),
        exact=(
            "tslc/tests/test_authoring_check.py",
        ),
        globs=("tslc/tests/test_lsp_*.py",),
    )
    editor_runtime = shared_ci or compiler or _any_path(
        changed,
        prefixes=("editors/vscode-tsl/",),
    )

    package_inputs = _any_path(
        changed,
        prefixes=("examples/",),
        exact=(
            "LICENSE",
            "NOTICE",
        ),
    )
    docs_inputs = _any_path(
        changed,
        prefixes=("docReact/", "docs/", "supplementary/docs/"),
        exact=(
            "README.md",
            "tslc/README.md",
            "tslc/DESCRIPTION.md",
        ),
    )
    package = generated_profiles or package_inputs
    docs = generated_profiles or docs_inputs

    return CiScope(
        python_tests=python_tests,
        python_full=python_full,
        python_type_check=python_type_check,
        pivot=pivot,
        coverage=coverage,
        editor_tests=editor_tests,
        editor_runtime=editor_runtime,
        generated_profiles=generated_profiles,
        clang_overlay=clang_overlay,
        benchmarks=benchmarks,
        package=package,
        docs=docs,
        changed_python_tests=changed_python_tests,
    )


def ci_image_reference(repository: str, root: Path = REPO_ROOT) -> str:
    normalized_repository = repository.strip().lower()
    if not normalized_repository or "/" not in normalized_repository:
        raise ValueError("repository must use OWNER/NAME form")
    digest = hashlib.sha256()
    for relative in CI_IMAGE_INPUTS:
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"ghcr.io/{normalized_repository}-tslc-ci:env-{digest.hexdigest()[:24]}"


def changed_paths(event: str, base: str, head: str) -> tuple[str, ...] | None:
    if event in {"merge_group", "workflow_dispatch"}:
        return None
    if not base or not head or set(base) == {"0"}:
        return None
    separator = "..." if event == "pull_request" else ".."
    try:
        completed = subprocess.run(
            (
                "git",
                "diff",
                "--name-only",
                "-z",
                "--diff-filter=ACMRTUXB",
                f"{base}{separator}{head}",
            ),
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"warning: unable to compute CI path scope ({exc}); running all gates",
            file=sys.stderr,
        )
        return None
    return tuple(
        path.decode("utf-8")
        for path in completed.stdout.split(b"\0")
        if path
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--ref-type", default="")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    paths = (
        None
        if args.ref_type == "tag"
        else changed_paths(args.event, args.base, args.head)
    )
    scope = CiScope.full() if paths is None else classify_paths(paths)
    payload = _scope_payload(scope, ci_image_reference(args.repository))
    if args.github_output:
        _write_github_outputs(Path(args.github_output), payload)
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


def _scope_payload(scope: CiScope, image: str) -> dict[str, object]:
    payload: dict[str, object] = asdict(scope)
    payload["changed_python_tests"] = list(scope.changed_python_tests)
    payload["ci_image"] = image
    return payload


def _write_github_outputs(path: Path, payload: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for key, value in payload.items():
            if isinstance(value, (list, dict)):
                rendered = json.dumps(value, separators=(",", ":"))
            elif isinstance(value, bool):
                rendered = str(value).lower()
            else:
                rendered = str(value)
            handle.write(f"{key}={rendered}\n")


def _normalize_path(path: str) -> str:
    return PurePosixPath(path.strip().replace("\\", "/")).as_posix()


def _any_path(
    paths: tuple[str, ...],
    *,
    prefixes: tuple[str, ...] = (),
    exact: tuple[str, ...] = (),
    globs: tuple[str, ...] = (),
) -> bool:
    return any(
        path in exact
        or path.startswith(prefixes)
        or any(PurePosixPath(path).match(pattern) for pattern in globs)
        for path in paths
    )


def _is_unclassified(path: str) -> bool:
    known_prefixes = (
        ".agents/",
        ".claude/",
        ".codex/",
        ".devcontainer/",
        ".github/",
        ".vscode/",
        "coverage/",
        "docReact/",
        "docs/",
        "editors/vscode-tsl/",
        "examples/",
        "research/",
        "supplementary/buildsystem/",
        "supplementary/ci/",
        "supplementary/docs/",
        "test-sort/",
        "todo/",
        "tools/pivot/",
        "tslc/src/",
        "tslc/tests/",
        "tslc/tslctmp/",
        "tsldata/",
    )
    known_root_files = {
        ".claudeignore",
        ".gitattributes",
        ".gitignore",
        "AGENTS.md",
        "CHARTER.md",
        "CLAUDE.md",
        "LICENSE",
        "NOTICE",
        "PLANS.md",
        "README.md",
        "compose.yaml",
        "dev.sh",
        "pytest.ini",
        "requirements.txt",
        "tslc.toml",
        "tslc/.gitignore",
        "tslc/AGENTS.md",
        "tslc/CHARTER.md",
        "tslc/CLAUDE.md",
        "tslc/DESCRIPTION.md",
        "tslc/LICENSE",
        "tslc/NOTICE",
        "tslc/README.md",
        "tslc/pyproject.toml",
    }
    return path not in known_root_files and not path.startswith(known_prefixes)


if __name__ == "__main__":
    raise SystemExit(main())
