"""Filesystem writer for generated artifact values."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactSet

ArtifactWriteStatus = Literal["written"]


@dataclass(frozen=True, slots=True)
class ArtifactWriteRecord:
    logical_path: str
    written_path: Path
    digest: str
    bytes_written: int
    status: ArtifactWriteStatus = "written"


@dataclass(frozen=True, slots=True)
class ArtifactWriteReport:
    output_root: Path
    written: tuple[ArtifactWriteRecord, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _PlannedArtifact:
    artifact: Artifact
    relative_parts: tuple[str, ...]
    target_path: Path


class ArtifactWriter:
    """Write an existing artifact set under a caller-provided root."""

    def write(
        self,
        artifacts: ArtifactSet,
        output_root: Path | str,
    ) -> ArtifactWriteReport:
        root = Path(output_root).resolve()
        planned, diagnostics = _plan_writes(artifacts, root)
        if diagnostics:
            return ArtifactWriteReport(
                output_root=root,
                written=(),
                diagnostics=diagnostics,
            )

        root_diagnostic = _ensure_root(root)
        if root_diagnostic is not None:
            return ArtifactWriteReport(
                output_root=root,
                written=(),
                diagnostics=(root_diagnostic,),
            )

        written: list[ArtifactWriteRecord] = []
        write_diagnostics: list[Diagnostic] = []
        for item in planned:
            try:
                item.target_path.parent.mkdir(parents=True, exist_ok=True)
                item.target_path.write_text(item.artifact.content, encoding="utf-8")
            except OSError as exc:
                write_diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-WRITE-FILESYSTEM-ERROR",
                        message=(
                            f"could not write artifact {item.artifact.logical_path!r} "
                            f"to {item.target_path}: {exc}"
                        ),
                    )
                )
                continue

            written.append(
                ArtifactWriteRecord(
                    logical_path=item.artifact.logical_path,
                    written_path=item.target_path,
                    digest=item.artifact.digest,
                    bytes_written=len(item.artifact.content.encode("utf-8")),
                )
            )

        return ArtifactWriteReport(
            output_root=root,
            written=tuple(sorted(written, key=lambda item: item.logical_path)),
            diagnostics=_sort_diagnostics(write_diagnostics),
        )


def write_artifacts(
    artifacts: ArtifactSet,
    output_root: Path | str,
) -> ArtifactWriteReport:
    """Write generated artifact values under an explicit output root."""

    return ArtifactWriter().write(artifacts, output_root)


def _plan_writes(
    artifacts: ArtifactSet,
    output_root: Path,
) -> tuple[tuple[_PlannedArtifact, ...], tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    planned: list[_PlannedArtifact] = []

    if output_root.exists() and not output_root.is_dir():
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-WRITE-OUTPUT-ROOT-NOT-DIRECTORY",
                message=f"output root {output_root} exists but is not a directory",
            )
        )

    logical_path_counts: dict[str, int] = {}
    for artifact in artifacts.artifacts:
        logical_path_counts[artifact.logical_path] = (
            logical_path_counts.get(artifact.logical_path, 0) + 1
        )

    for logical_path in sorted(logical_path_counts):
        if logical_path_counts[logical_path] > 1:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-WRITE-DUPLICATE-LOGICAL-PATH",
                    message=(
                        f"artifact logical path {logical_path!r} "
                        "appears more than once"
                    ),
                )
            )

    for artifact in sorted(artifacts.artifacts, key=lambda item: item.logical_path):
        path_diagnostic = _logical_path_diagnostic(artifact.logical_path)
        if path_diagnostic is not None:
            diagnostics.append(path_diagnostic)
            continue

        relative_parts = PurePosixPath(artifact.logical_path).parts
        target_path = output_root.joinpath(*relative_parts)
        planned.append(
            _PlannedArtifact(
                artifact=artifact,
                relative_parts=relative_parts,
                target_path=target_path,
            )
        )

    diagnostics.extend(_duplicate_target_diagnostics(planned))
    diagnostics.extend(_planned_collision_diagnostics(planned))
    diagnostics.extend(_existing_collision_diagnostics(planned, output_root))
    return tuple(planned), _sort_diagnostics(diagnostics)


def _logical_path_diagnostic(logical_path: str) -> Diagnostic | None:
    posix_path = PurePosixPath(logical_path)
    windows_path = PureWindowsPath(logical_path)
    if not posix_path.parts:
        return Diagnostic(
            severity="error",
            code="TSL-WRITE-EMPTY-LOGICAL-PATH",
            message="artifact logical path must not be empty",
        )

    if posix_path.is_absolute() or windows_path.is_absolute():
        return Diagnostic(
            severity="error",
            code="TSL-WRITE-ABSOLUTE-LOGICAL-PATH",
            message=f"artifact logical path {logical_path!r} must be relative",
        )

    if ".." in posix_path.parts or ".." in windows_path.parts:
        return Diagnostic(
            severity="error",
            code="TSL-WRITE-PARENT-ESCAPE",
            message=f"artifact logical path {logical_path!r} must not contain '..'",
        )

    return None


def _duplicate_target_diagnostics(
    planned: list[_PlannedArtifact],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    first_logical_path_by_target: dict[tuple[str, ...], str] = {}
    for item in planned:
        first_logical_path = first_logical_path_by_target.get(item.relative_parts)
        if first_logical_path is None:
            first_logical_path_by_target[item.relative_parts] = item.artifact.logical_path
            continue
        if first_logical_path == item.artifact.logical_path:
            continue
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-WRITE-DUPLICATE-TARGET-PATH",
                message=(
                    f"artifact logical path {item.artifact.logical_path!r} resolves to "
                    f"the same target as {first_logical_path!r}"
                ),
            )
        )
    return tuple(diagnostics)


def _planned_collision_diagnostics(
    planned: list[_PlannedArtifact],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    unique_items = {
        item.relative_parts: item.artifact.logical_path
        for item in sorted(planned, key=lambda value: value.artifact.logical_path)
    }
    sorted_items = sorted(unique_items.items())
    for index, (left_parts, left_logical_path) in enumerate(sorted_items):
        for right_parts, right_logical_path in sorted_items[index + 1 :]:
            if _is_prefix(left_parts, right_parts):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-WRITE-DIRECTORY-FILE-COLLISION",
                        message=(
                            f"artifact logical path {left_logical_path!r} collides "
                            f"with descendant path {right_logical_path!r}"
                        ),
                    )
                )
            if _is_prefix(right_parts, left_parts):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-WRITE-DIRECTORY-FILE-COLLISION",
                        message=(
                            f"artifact logical path {right_logical_path!r} collides "
                            f"with descendant path {left_logical_path!r}"
                        ),
                    )
                )
    return tuple(diagnostics)


def _existing_collision_diagnostics(
    planned: list[_PlannedArtifact],
    output_root: Path,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for item in planned:
        target_path = item.target_path
        resolved_target = target_path.resolve(strict=False)
        if not _is_relative_to(resolved_target, output_root):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-WRITE-TARGET-ESCAPES-OUTPUT-ROOT",
                    message=(
                        f"artifact logical path {item.artifact.logical_path!r} "
                        f"resolves outside output root {output_root}"
                    ),
                )
            )

        if target_path.exists() and target_path.is_dir():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-WRITE-DIRECTORY-FILE-COLLISION",
                    message=(
                        f"artifact logical path {item.artifact.logical_path!r} "
                        f"targets existing directory {target_path}"
                    ),
                )
            )

        for index in range(1, len(item.relative_parts)):
            parent = output_root.joinpath(*item.relative_parts[:index])
            if parent.exists() and not parent.is_dir():
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-WRITE-DIRECTORY-FILE-COLLISION",
                        message=(
                            f"artifact logical path {item.artifact.logical_path!r} "
                            f"requires directory {parent}, but a file exists there"
                        ),
                    )
                )
    return tuple(diagnostics)


def _ensure_root(output_root: Path) -> Diagnostic | None:
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return Diagnostic(
            severity="error",
            code="TSL-WRITE-FILESYSTEM-ERROR",
            message=f"could not create output root {output_root}: {exc}",
        )
    return None


def _is_prefix(prefix: tuple[str, ...], value: tuple[str, ...]) -> bool:
    return len(prefix) < len(value) and value[: len(prefix)] == prefix


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
