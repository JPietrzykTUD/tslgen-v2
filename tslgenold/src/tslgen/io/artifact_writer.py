from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result
from tslgen.io.artifacts import Artifact, ArtifactSet
from tslgen.io.write_report import (
    ArtifactWriteOptions,
    ArtifactWritePlan,
    ArtifactWriteRecord,
    ArtifactWriteReport,
    ArtifactWriteStatus,
)


def plan_artifact_writes(
    artifacts: ArtifactSet | Iterable[Artifact],
    options: ArtifactWriteOptions,
) -> ArtifactWritePlan:
    output_root = _resolved_output_root(options.output_root)
    artifact_tuple = _artifact_tuple(artifacts)
    records: list[ArtifactWriteRecord] = []
    diagnostics: list[Diagnostic] = []

    root_conflict = _root_conflict(output_root)
    if root_conflict is not None and not artifact_tuple:
        diagnostics.append(root_conflict)

    duplicate_targets: set[Path] = set()
    if root_conflict is None:
        resolved_targets = _resolved_targets(artifact_tuple, output_root)
        duplicate_targets = _duplicate_targets(resolved_targets)
    else:
        resolved_targets = ()

    for artifact in artifact_tuple:
        resolved = _resolve_record_target(output_root, artifact.logical_path)
        if resolved is None:
            unsafe = _unsafe_path_diagnostic(output_root, artifact.logical_path)
            records.append(_failed_record(artifact, output_root, unsafe))
            continue
        target_path = resolved

        if root_conflict is not None:
            records.append(_failed_record(artifact, target_path, root_conflict))
            continue
        if target_path in duplicate_targets:
            records.append(
                _failed_record(
                    artifact,
                    target_path,
                    _duplicate_target_diagnostic(target_path),
                )
            )
            continue

        conflict = _target_conflict_diagnostic(output_root, target_path)
        if conflict is not None:
            records.append(_failed_record(artifact, target_path, conflict))
            continue

        status: ArtifactWriteStatus = (
            "skipped_unchanged"
            if options.skip_unchanged and _target_matches_digest(target_path, artifact)
            else "would_write"
        )
        records.append(_record(artifact, target_path, status))

    return ArtifactWritePlan(
        output_root=output_root,
        dry_run=options.dry_run,
        skip_unchanged=options.skip_unchanged,
        records=tuple(records),
        report_diagnostics=tuple(diagnostics),
    )


def write_artifacts(
    artifacts: ArtifactSet | Iterable[Artifact],
    options: ArtifactWriteOptions,
) -> ArtifactWriteReport:
    plan = plan_artifact_writes(artifacts, options)
    if options.dry_run:
        return ArtifactWriteReport(
            output_root=plan.output_root,
            dry_run=plan.dry_run,
            skip_unchanged=plan.skip_unchanged,
            records=plan.records,
            report_diagnostics=plan.report_diagnostics,
        )
    if not plan.is_ok:
        return ArtifactWriteReport(
            output_root=plan.output_root,
            dry_run=plan.dry_run,
            skip_unchanged=plan.skip_unchanged,
            records=_abort_pending_records(plan.records),
            report_diagnostics=plan.report_diagnostics,
        )

    records: list[ArtifactWriteRecord] = []
    artifact_by_path = {
        artifact.logical_path.as_posix(): artifact
        for artifact in _artifact_tuple(artifacts)
    }
    for record in plan.records:
        if record.status != "would_write":
            records.append(record)
            continue

        artifact = artifact_by_path[record.logical_path.as_posix()]
        written = _write_record(record, artifact)
        records.append(written)

    return ArtifactWriteReport(
        output_root=plan.output_root,
        dry_run=plan.dry_run,
        skip_unchanged=plan.skip_unchanged,
        records=tuple(records),
    )


def resolve_artifact_target(
    output_root: Path,
    logical_path: PurePosixPath,
) -> Result[Path]:
    root = _resolved_output_root(output_root)
    target = _resolve_record_target(root, logical_path)
    if target is None:
        return Result.failure((_unsafe_path_diagnostic(root, logical_path),))
    return Result.ok(target)


def _artifact_tuple(artifacts: ArtifactSet | Iterable[Artifact]) -> tuple[Artifact, ...]:
    if isinstance(artifacts, ArtifactSet):
        return artifacts.artifacts
    return tuple(sorted(tuple(artifacts), key=lambda artifact: artifact.key))


def _resolved_output_root(output_root: Path) -> Path:
    return Path(output_root).resolve(strict=False)


def _resolved_targets(
    artifacts: tuple[Artifact, ...],
    output_root: Path,
) -> tuple[Path, ...]:
    targets: list[Path] = []
    for artifact in artifacts:
        target = _resolve_record_target(output_root, artifact.logical_path)
        if target is not None:
            targets.append(target)
    return tuple(targets)


def _duplicate_targets(resolved_targets: tuple[Path, ...]) -> set[Path]:
    counts: dict[Path, int] = {}
    for target_path in resolved_targets:
        counts[target_path] = counts.get(target_path, 0) + 1
    return {target_path for target_path, count in counts.items() if count > 1}


def _resolve_record_target(
    output_root: Path,
    logical_path: PurePosixPath,
) -> Path | None:
    path = PurePosixPath(logical_path)
    if path.is_absolute() or ".." in path.parts:
        return None
    target_path = output_root.joinpath(*path.parts).resolve(strict=False)
    try:
        target_path.relative_to(output_root)
    except ValueError:
        return None
    return target_path


def _root_conflict(output_root: Path) -> Diagnostic | None:
    if output_root.exists() and not output_root.is_dir():
        return Diagnostic.error(
            "TSL-ARTIFACT-WRITE-ROOT-CONFLICT",
            f"artifact output root {output_root.as_posix()!r} exists but is not "
            "a directory",
            location=_location(output_root),
        )
    return None


def _target_conflict_diagnostic(
    output_root: Path,
    target_path: Path,
) -> Diagnostic | None:
    if target_path.exists() and target_path.is_dir():
        return Diagnostic.error(
            "TSL-ARTIFACT-WRITE-TARGET-CONFLICT",
            f"artifact target {target_path.as_posix()!r} is a directory",
            location=_location(target_path),
        )

    parent = target_path.parent
    while parent != output_root and parent != parent.parent:
        if parent.exists() and not parent.is_dir():
            return Diagnostic.error(
                "TSL-ARTIFACT-WRITE-TARGET-CONFLICT",
                f"artifact target parent {parent.as_posix()!r} exists but is "
                "not a directory",
                location=_location(parent),
            )
        parent = parent.parent
    return None


def _target_matches_digest(target_path: Path, artifact: Artifact) -> bool:
    if not target_path.exists() or not target_path.is_file():
        return False
    try:
        current = target_path.read_bytes()
    except OSError:
        return False
    return hashlib.sha256(current).hexdigest() == artifact.content_digest


def _write_record(
    record: ArtifactWriteRecord,
    artifact: Artifact,
) -> ArtifactWriteRecord:
    try:
        record.target_path.parent.mkdir(parents=True, exist_ok=True)
        record.target_path.write_bytes(artifact.content.encode("utf-8"))
    except OSError as exc:
        return _failed_record(
            artifact,
            record.target_path,
            Diagnostic.error(
                "TSL-ARTIFACT-WRITE-IO",
                f"failed to write artifact {record.logical_path.as_posix()!r}: {exc}",
                location=_location(record.target_path),
            ),
        )
    return _record(artifact, record.target_path, "written")


def _abort_pending_records(
    records: tuple[ArtifactWriteRecord, ...],
) -> tuple[ArtifactWriteRecord, ...]:
    return tuple(
        _aborted_record(record) if record.status == "would_write" else record
        for record in records
    )


def _aborted_record(record: ArtifactWriteRecord) -> ArtifactWriteRecord:
    diagnostic = Diagnostic.error(
        "TSL-ARTIFACT-WRITE-ABORTED",
        f"artifact {record.logical_path.as_posix()!r} was not written because "
        "the write plan has errors",
        location=_location(record.target_path),
    )
    return ArtifactWriteRecord(
        logical_path=record.logical_path,
        target_path=record.target_path,
        status="failed",
        digest=record.digest,
        content_size=record.content_size,
        diagnostics=(*record.diagnostics, diagnostic),
    )


def _record(
    artifact: Artifact,
    target_path: Path,
    status: ArtifactWriteStatus,
    *,
    diagnostics: tuple[Diagnostic, ...] = (),
) -> ArtifactWriteRecord:
    return ArtifactWriteRecord(
        logical_path=artifact.logical_path,
        target_path=target_path,
        status=status,
        digest=artifact.content_digest,
        content_size=len(artifact.content.encode("utf-8")),
        diagnostics=diagnostics,
    )


def _failed_record(
    artifact: Artifact,
    target_path: Path,
    diagnostic: Diagnostic,
) -> ArtifactWriteRecord:
    return _record(artifact, target_path, "failed", diagnostics=(diagnostic,))


def _unsafe_path_diagnostic(
    output_root: Path,
    logical_path: PurePosixPath,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-ARTIFACT-WRITE-UNSAFE-PATH",
        f"artifact logical path {logical_path.as_posix()!r} cannot be resolved "
        f"safely under output root {output_root.as_posix()!r}",
        location=_location(output_root),
    )


def _duplicate_target_diagnostic(target_path: Path) -> Diagnostic:
    return Diagnostic.error(
        "TSL-ARTIFACT-WRITE-DUPLICATE-TARGET",
        f"multiple artifacts resolve to output target {target_path.as_posix()!r}",
        location=_location(target_path),
    )


def _location(path: Path) -> SourceLocation:
    return SourceLocation(path=path, line=1, column=1)
