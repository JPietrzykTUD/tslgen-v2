from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap


type ArtifactWriteStatus = Literal[
    "would_write",
    "written",
    "skipped_unchanged",
    "failed",
]


@dataclass(frozen=True, slots=True)
class ArtifactWriteOptions:
    output_root: Path
    dry_run: bool = False
    skip_unchanged: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_root", Path(self.output_root))


@dataclass(frozen=True, slots=True)
class ArtifactWriteRecord:
    logical_path: PurePosixPath
    target_path: Path
    status: ArtifactWriteStatus
    digest: str
    content_size: int
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        path = PurePosixPath(self.logical_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("write record logical path must be relative and safe")
        if not self.digest:
            raise ValueError("write record digest must be non-empty")
        if self.content_size < 0:
            raise ValueError("write record content size must not be negative")
        object.__setattr__(self, "logical_path", path)
        object.__setattr__(self, "target_path", Path(self.target_path))
        object.__setattr__(self, "diagnostics", sort_diagnostics(self.diagnostics))

    @property
    def key(self) -> tuple[str, str]:
        return (
            self.logical_path.as_posix(),
            self.target_path.as_posix(),
        )


@dataclass(frozen=True, slots=True)
class ArtifactWritePlan:
    output_root: Path
    dry_run: bool
    skip_unchanged: bool
    records: tuple[ArtifactWriteRecord, ...]
    report_diagnostics: tuple[Diagnostic, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = field(init=False)

    def __post_init__(self) -> None:
        records = tuple(sorted(self.records, key=lambda record: record.key))
        report_diagnostics = sort_diagnostics(self.report_diagnostics)
        diagnostics = sort_diagnostics(
            (
                *report_diagnostics,
                *(item for record in records for item in record.diagnostics),
            )
        )
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "report_diagnostics", report_diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def is_ok(self) -> bool:
        return not has_errors(self.diagnostics)


@dataclass(frozen=True, slots=True)
class ArtifactWriteReport:
    output_root: Path
    dry_run: bool
    skip_unchanged: bool
    records: tuple[ArtifactWriteRecord, ...]
    report_diagnostics: tuple[Diagnostic, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = field(init=False)

    def __post_init__(self) -> None:
        records = tuple(sorted(self.records, key=lambda record: record.key))
        report_diagnostics = sort_diagnostics(self.report_diagnostics)
        diagnostics = sort_diagnostics(
            (
                *report_diagnostics,
                *(item for record in records for item in record.diagnostics),
            )
        )
        object.__setattr__(self, "output_root", Path(self.output_root))
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "report_diagnostics", report_diagnostics)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def is_ok(self) -> bool:
        return not has_errors(self.diagnostics)

    @property
    def written_paths(self) -> tuple[str, ...]:
        return self._paths_with_status("written")

    @property
    def skipped_paths(self) -> tuple[str, ...]:
        return self._paths_with_status("skipped_unchanged")

    @property
    def would_write_paths(self) -> tuple[str, ...]:
        return self._paths_with_status("would_write")

    @property
    def failed_paths(self) -> tuple[str, ...]:
        return self._paths_with_status("failed")

    @property
    def digest_map(self) -> FrozenMap[str, str]:
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for record in self.records:
            path = record.logical_path.as_posix()
            if record.status == "failed" or path in seen:
                continue
            seen.add(path)
            pairs.append((path, record.digest))
        return FrozenMap(pairs)

    def _paths_with_status(self, status: ArtifactWriteStatus) -> tuple[str, ...]:
        return tuple(
            record.logical_path.as_posix()
            for record in self.records
            if record.status == status
        )
