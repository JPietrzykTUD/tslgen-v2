from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path, PurePosixPath

from tslgen.config.model import SourceConfig
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.core.result import Result


class SourceKind(StrEnum):
    TSL = "tsl"
    PRIMITIVE = "primitive"
    EXTENSION = "extension"
    TYPE_GROUPS = "type_groups"
    LANE_SETS = "lane_sets"
    FLAGS = "flags"
    TEMPLATES = "templates"
    LANGUAGE_TYPES = "language_types"
    TRANSLATION = "translation"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    path: Path
    logical_path: PurePosixPath
    text: str
    digest: str
    kind: SourceKind

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "logical_path", PurePosixPath(self.logical_path))
        if not self.digest:
            raise ValueError("source document digest must be non-empty")


@dataclass(frozen=True, slots=True)
class SourceSet:
    documents: tuple[SourceDocument, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "documents",
            tuple(
                sorted(
                    self.documents,
                    key=lambda document: document.logical_path.as_posix(),
                )
            ),
        )

    def __iter__(self) -> Iterator[SourceDocument]:
        return iter(self.documents)

    def __len__(self) -> int:
        return len(self.documents)


@dataclass(frozen=True, slots=True)
class _SourceCandidate:
    path: Path
    standard_root: Path | None = None


def load_sources(config: SourceConfig) -> Result[SourceSet]:
    candidates, diagnostics = _collect_candidates(config)
    if diagnostics:
        return Result.failure(diagnostics)

    documents: list[SourceDocument] = []
    seen: dict[str, SourceDocument] = {}
    for candidate in candidates:
        loaded = _read_document(candidate)
        if isinstance(loaded, Diagnostic):
            diagnostics.append(loaded)
            continue
        document = loaded
        duplicate = seen.get(document.logical_path.as_posix())
        if duplicate is not None:
            diagnostics.append(_duplicate_source_diagnostic(document.path, duplicate.path))
            continue
        seen[document.logical_path.as_posix()] = document
        documents.append(document)

    if diagnostics:
        return Result.failure(diagnostics)
    return Result.ok(SourceSet(tuple(documents)))


def _collect_candidates(config: SourceConfig) -> tuple[list[_SourceCandidate], list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    candidates: list[_SourceCandidate] = []
    standard_root = config.standard_library_root.resolve(strict=False)

    if config.include_standard_library:
        if not standard_root.is_dir():
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SRC-STANDARD-DIR-MISSING",
                    f"standard source directory does not exist: {standard_root}",
                    location=_file_location(standard_root),
                )
            )
        else:
            candidates.extend(
                _SourceCandidate(path=path.resolve(), standard_root=standard_root)
                for path in _sorted_tsl_files(standard_root, config.allowed_extensions)
            )

    for input_path in config.explicit_paths:
        path = input_path.resolve(strict=False)
        if not path.exists():
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SRC-MISSING",
                    f"source path does not exist: {path}",
                    location=_file_location(path),
                )
            )
            continue
        if path.is_dir():
            candidates.extend(
                _SourceCandidate(path=child.resolve(), standard_root=_root_for(path, standard_root))
                for child in _sorted_tsl_files(path, config.allowed_extensions)
            )
            continue
        if path.suffix.casefold() not in config.allowed_extensions:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SRC-UNSUPPORTED-EXTENSION",
                    f"unsupported source extension {path.suffix!r} for {path}",
                    location=_file_location(path),
                )
            )
            continue
        candidates.append(_SourceCandidate(path=path.resolve(), standard_root=_root_for(path, standard_root)))

    candidates.sort(key=lambda candidate: _logical_path(candidate.path, candidate.standard_root).as_posix())
    return candidates, diagnostics


def _sorted_tsl_files(root: Path, allowed_extensions: tuple[str, ...]) -> tuple[Path, ...]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in allowed_extensions
    ]
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def _read_document(candidate: _SourceCandidate) -> SourceDocument | Diagnostic:
    try:
        text = candidate.path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        return Diagnostic.error(
            "TSL-SRC-DECODE-FAILED",
            f"source file is not valid UTF-8: {candidate.path}: {error}",
            location=_file_location(candidate.path),
        )
    except OSError as error:
        return Diagnostic.error(
            "TSL-SRC-READ-FAILED",
            f"could not read source file {candidate.path}: {error}",
            location=_file_location(candidate.path),
        )

    logical_path = _logical_path(candidate.path, candidate.standard_root)
    return SourceDocument(
        path=candidate.path,
        logical_path=logical_path,
        text=text,
        digest=sha256(text.encode("utf-8")).hexdigest(),
        kind=_classify_source(logical_path),
    )


def _root_for(path: Path, standard_root: Path) -> Path | None:
    try:
        path.resolve().relative_to(standard_root)
    except ValueError:
        return None
    return standard_root


def _logical_path(path: Path, standard_root: Path | None) -> PurePosixPath:
    if standard_root is not None:
        try:
            return PurePosixPath(path.relative_to(standard_root).as_posix())
        except ValueError:
            pass
    return PurePosixPath(path.as_posix())


def _classify_source(logical_path: PurePosixPath) -> SourceKind:
    parts = logical_path.parts
    if len(parts) >= 2 and parts[0] == "primitives":
        return SourceKind.PRIMITIVE
    if parts == ("extensions", "extension.tsl"):
        return SourceKind.EXTENSION
    if parts == ("detail", "types.tsl"):
        return SourceKind.TYPE_GROUPS
    if parts == ("detail", "lane_sets.tsl"):
        return SourceKind.LANE_SETS
    if parts == ("detail", "flags.tsl"):
        return SourceKind.FLAGS
    if parts == ("detail", "templates.tsl"):
        return SourceKind.TEMPLATES
    if len(parts) == 4 and parts[:3] == ("detail", "lang", "types"):
        return SourceKind.LANGUAGE_TYPES
    if len(parts) == 3 and parts[:2] == ("detail", "lang") and parts[2].startswith("translate_"):
        return SourceKind.TRANSLATION
    return SourceKind.TSL


def _duplicate_source_diagnostic(path: Path, original_path: Path) -> Diagnostic:
    return Diagnostic.error(
        "TSL-SRC-DUPLICATE",
        f"duplicate source path {path}; first loaded from {original_path}",
        location=_file_location(path),
    )


def _file_location(path: Path) -> SourceLocation:
    return SourceLocation(path=path, line=1, column=1)
