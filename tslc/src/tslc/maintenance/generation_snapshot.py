"""Capture and compare deterministic generation snapshots.

This maintenance command records generated files together with the semantic
facts that are not sufficiently proved by artifact digests alone.  Snapshot
comparison deliberately ignores compiler provenance while requiring identical
source, profile, grammar, and render-asset inputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

from tslc.api import _ARITH_TYPE_TAGS, generate_project, write_artifacts
from tslc.maintenance._generation_snapshot_semantics import (
    serialize_artifact,
    serialize_generation_semantics,
)
from tslc.diagnostics import has_errors
from tslc.pipeline import GenerationMode, GenerationResult

_SNAPSHOT_VERSION = 1
_SNAPSHOT_FILE = "snapshot.json"
_GENERATED_DIR = "generated"


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_DATA_ROOT = _REPO_ROOT / "tsldata"
_PROFILES_PATH = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
_GRAMMAR_PATH = _REPO_ROOT / "tslc" / "src" / "tslc" / "syntax" / "grammar" / "tsl_data.lark"
_ASSETS_ROOT = _REPO_ROOT / "tslc" / "src" / "tslc" / "backend" / "assets"
_COMPILER_ROOT = _REPO_ROOT / "tslc" / "src" / "tslc"
_SCRATCH_ROOT = _REPO_ROOT / "tslctmp"


@dataclass(frozen=True, slots=True)
class SnapshotCase:
    name: str
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    type_tags: tuple[str, ...]
    backends: tuple[str, ...] = ("cpp", "rust")
    generation_mode: GenerationMode = "partial"
    test_harness: bool = False
    value_test_warnings: bool = False
    value_test_fuzz: bool = False
    render_artifacts: bool = True


_ALL_PROFILE_SHAPES = (
    "add",
    "load",
    "store",
    "cast",
    "gather",
    "shift_left",
    "equal",
    "hadd",
    "to_integral",
    "from_array",
    "to_array",
    "allocate",
    "deallocate",
)

SNAPSHOT_CASES: dict[str, SnapshotCase] = {
    case.name: case
    for case in (
        SnapshotCase("full", None, None, _ARITH_TYPE_TAGS),
        SnapshotCase(
            "profile-diverse",
            None,
            ("scalar", "avx2", "sve128", "wasm32-simd128"),
            _ARITH_TYPE_TAGS,
        ),
        SnapshotCase(
            "lowering-reuse",
            None,
            ("skylake", "cascadelake"),
            _ARITH_TYPE_TAGS,
        ),
        SnapshotCase(
            "all-profiles-shapes",
            _ALL_PROFILE_SHAPES,
            None,
            ("si32", "f32"),
        ),
        SnapshotCase(
            "focused",
            ("add",),
            ("avx2",),
            ("si32",),
            backends=("cpp",),
        ),
    )
}


@dataclass(frozen=True, slots=True)
class SnapshotComparison:
    differences: tuple[str, ...]

    @property
    def matches(self) -> bool:
        return not self.differences


class SnapshotError(RuntimeError):
    """An explicit snapshot capture or comparison failure."""


def capture(case: SnapshotCase, output_root: Path, *, replace: bool = False) -> Path:
    """Generate and write one repository-local snapshot case."""

    root = _prepare_output_root(output_root, replace=replace)
    result = generate_project(
        [_DATA_ROOT],
        machine_profiles_path=_PROFILES_PATH,
        primitives=case.primitives,
        profiles=case.profiles,
        type_tags=case.type_tags,
        backends=case.backends,
        generation_mode=case.generation_mode,
        test_harness=case.test_harness,
        value_test_warnings=case.value_test_warnings,
        value_test_fuzz=case.value_test_fuzz,
        render_artifacts=case.render_artifacts,
    )
    generated_root = root / _GENERATED_DIR
    report = write_artifacts(result.artifacts, generated_root, mode="manifest-clean")
    if has_errors(report.diagnostics):
        messages = "; ".join(
            f"{diagnostic.code}: {diagnostic.message}" for diagnostic in report.diagnostics
        )
        raise SnapshotError(f"could not write generated snapshot tree: {messages}")

    document = build_snapshot_document(case, result, generated_root)
    snapshot_path = root / _SNAPSHOT_FILE
    snapshot_path.write_text(serialize_snapshot(document), encoding="utf-8")
    return snapshot_path


def build_snapshot_document(
    case: SnapshotCase,
    result: GenerationResult,
    generated_root: Path,
) -> dict[str, object]:
    """Build the canonical JSON boundary using explicit domain serializers."""

    input_manifest = _input_manifest()
    return {
        "version": _SNAPSHOT_VERSION,
        "case": case.name,
        "request": _serialize_request(case),
        "input_manifest": input_manifest,
        "input_manifest_digest": _records_digest(input_manifest),
        "compiler_provenance": _compiler_provenance(),
        "artifacts": [serialize_artifact(artifact) for artifact in result.artifacts.artifacts],
        "generated_files": _file_manifest(generated_root),
        "semantics": serialize_generation_semantics(result, _REPO_ROOT),
    }


def serialize_snapshot(document: dict[str, object]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def compare_snapshot_directories(baseline: Path, candidate: Path) -> SnapshotComparison:
    baseline_document = _load_document(baseline / _SNAPSHOT_FILE)
    candidate_document = _load_document(candidate / _SNAPSHOT_FILE)
    differences = list(compare_snapshot_documents(baseline_document, candidate_document))
    if differences and (
        differences[0].startswith("request")
        or differences[0].startswith("input_manifest")
    ):
        return SnapshotComparison(tuple(differences))

    baseline_files = _file_manifest(baseline / _GENERATED_DIR)
    candidate_files = _file_manifest(candidate / _GENERATED_DIR)
    file_difference = _first_difference(baseline_files, candidate_files, "generated_tree")
    if file_difference is not None:
        differences.append(file_difference)
    return SnapshotComparison(tuple(differences))


def compare_snapshot_documents(
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> tuple[str, ...]:
    """Compare normalized records, checking frozen inputs before outputs."""

    for key in ("version", "case", "request"):
        difference = _first_difference(baseline.get(key), candidate.get(key), key)
        if difference is not None:
            return (difference,)
    for key in ("input_manifest", "input_manifest_digest"):
        difference = _first_difference(baseline.get(key), candidate.get(key), key)
        if difference is not None:
            return (difference,)

    differences: list[str] = []
    for key in ("semantics", "artifacts", "generated_files"):
        difference = _first_difference(baseline.get(key), candidate.get(key), key)
        if difference is not None:
            differences.append(difference)
    return tuple(differences)


def _serialize_request(case: SnapshotCase) -> dict[str, object]:
    return {
        "source_paths": ("tsldata",),
        "machine_profiles_path": "supplementary/buildsystem/machine_profiles.json",
        "primitives": case.primitives,
        "profiles": case.profiles,
        "type_tags": case.type_tags,
        "backends": case.backends,
        "generation_mode": case.generation_mode,
        "test_harness": case.test_harness,
        "value_test_warnings": case.value_test_warnings,
        "value_test_fuzz": case.value_test_fuzz,
        "render_artifacts": case.render_artifacts,
    }


def _input_manifest() -> list[dict[str, object]]:
    paths = [
        *sorted(_DATA_ROOT.rglob("*.tsl"), key=lambda item: item.as_posix()),
        _PROFILES_PATH,
        _GRAMMAR_PATH,
        *sorted(
            (path for path in _ASSETS_ROOT.iterdir() if path.is_file()),
            key=lambda item: item.as_posix(),
        ),
    ]
    return [_file_record(path) for path in paths]


def input_manifest_digest() -> str:
    """Return the frozen-input identity shared by snapshots and benchmarks."""

    return _records_digest(_input_manifest())


def _compiler_provenance() -> dict[str, object]:
    records = [
        _file_record(path)
        for path in sorted(_COMPILER_ROOT.rglob("*.py"), key=lambda item: item.as_posix())
    ]
    return {"python_file_count": len(records), "python_files_digest": _records_digest(records)}


def _file_manifest(root: Path) -> list[dict[str, object]]:
    if not root.is_dir():
        return []
    records: list[dict[str, object]] = []
    for path in sorted((item for item in root.rglob("*") if item.is_file())):
        content = path.read_bytes()
        records.append(
            {
                "logical_path": path.relative_to(root).as_posix(),
                "sha256": sha256(content).hexdigest(),
                "byte_count": len(content),
            }
        )
    return records


def _file_record(path: Path) -> dict[str, object]:
    content = path.read_bytes()
    return {
        "logical_path": _relative_path(path),
        "sha256": sha256(content).hexdigest(),
        "byte_count": len(content),
    }


def _records_digest(records: list[dict[str, object]]) -> str:
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _prepare_output_root(output_root: Path, *, replace: bool) -> Path:
    root = output_root.resolve()
    try:
        root.relative_to(_SCRATCH_ROOT.resolve())
    except ValueError as exc:
        raise SnapshotError(f"snapshot output must be under {_SCRATCH_ROOT}") from exc
    if root == _SCRATCH_ROOT.resolve():
        raise SnapshotError("snapshot output must be a child of tslctmp")
    if root.exists():
        if not replace:
            raise SnapshotError(f"snapshot output already exists: {root}")
        if root.is_symlink():
            raise SnapshotError(f"refusing to replace symlink snapshot root: {root}")
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _load_document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"could not read snapshot {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SnapshotError(f"snapshot {path} must contain a JSON object")
    return value


def _first_difference(baseline: object, candidate: object, path: str) -> str | None:
    if type(baseline) is not type(candidate):
        return f"{path}: type {type(baseline).__name__} != {type(candidate).__name__}"
    if isinstance(baseline, dict) and isinstance(candidate, dict):
        keys = sorted(set(baseline) | set(candidate))
        for key in keys:
            if key not in baseline:
                return f"{path}.{key}: added"
            if key not in candidate:
                return f"{path}.{key}: removed"
            difference = _first_difference(baseline[key], candidate[key], f"{path}.{key}")
            if difference is not None:
                return difference
        return None
    if isinstance(baseline, list) and isinstance(candidate, list):
        if len(baseline) != len(candidate):
            return f"{path}: length {len(baseline)} != {len(candidate)}"
        for index, (before, after) in enumerate(zip(baseline, candidate, strict=True)):
            difference = _first_difference(before, after, f"{path}[{index}]")
            if difference is not None:
                return difference
        return None
    if baseline != candidate:
        return f"{path}: {baseline!r} != {candidate!r}"
    return None


def _capture_command(args: argparse.Namespace) -> int:
    case = SNAPSHOT_CASES[args.case]
    try:
        path = capture(case, Path(args.output), replace=args.replace)
    except SnapshotError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


def _compare_command(args: argparse.Namespace) -> int:
    try:
        comparison = compare_snapshot_directories(Path(args.baseline), Path(args.candidate))
    except SnapshotError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if comparison.matches:
        print("snapshots match")
        return 0
    for difference in comparison.differences:
        print(f"DIFF: {difference}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture", help="capture one generation case")
    capture_parser.add_argument("--case", choices=sorted(SNAPSHOT_CASES), required=True)
    capture_parser.add_argument("--output", required=True)
    capture_parser.add_argument("--replace", action="store_true")
    capture_parser.set_defaults(handler=_capture_command)
    compare_parser = subparsers.add_parser("compare", help="compare two snapshot directories")
    compare_parser.add_argument("--baseline", required=True)
    compare_parser.add_argument("--candidate", required=True)
    compare_parser.set_defaults(handler=_compare_command)
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "SNAPSHOT_CASES",
    "SnapshotCase",
    "SnapshotComparison",
    "SnapshotError",
    "build_snapshot_document",
    "capture",
    "compare_snapshot_directories",
    "compare_snapshot_documents",
    "input_manifest_digest",
    "main",
    "serialize_snapshot",
)
