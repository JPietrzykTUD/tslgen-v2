"""Small public API facade."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tslc.output.artifacts import ArtifactSet
from tslc.output.verify import (
    BuildVerificationReport,
    VerifyProject,
    verify_generated_project,
)
from tslc.output.writer import ArtifactWriteReport, ArtifactWriter
from tslc.pipeline import GenerationRequest, GenerationResult, generate

_ARITH_TYPE_TAGS = (
    "si8",
    "si16",
    "si32",
    "si64",
    "ui8",
    "ui16",
    "ui32",
    "ui64",
    "f32",
    "f64",
)


def generate_project(
    source_paths: Iterable[Path | str],
    *,
    machine_profiles_path: Path | str,
    primitives: Iterable[str],
    profiles: Iterable[str],
    type_tags: Iterable[str] = _ARITH_TYPE_TAGS,
    backends: Iterable[str] = ("cpp", "rust"),
) -> GenerationResult:
    """Run the full compiler pipeline and return in-memory artifacts.

    ``source_paths`` entries may be ``.tsl`` files or directories; directories
    are expanded to every ``.tsl`` file beneath them (the catalog needs the
    extension/type/language definitions alongside the primitive files).
    ``profiles`` names machine feature-profiles from ``machine_profiles_path``.
    """

    request = GenerationRequest(
        source_paths=_expand_sources(source_paths),
        machine_profiles_path=Path(machine_profiles_path),
        primitives=tuple(primitives),
        profiles=tuple(profiles),
        type_tags=tuple(type_tags),
        backends=tuple(backends),
    )
    return generate(request)


def _expand_sources(source_paths: Iterable[Path | str]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    for entry in source_paths:
        path = Path(entry)
        if path.is_dir():
            expanded.extend(sorted(path.rglob("*.tsl"), key=lambda item: item.as_posix()))
        else:
            expanded.append(path)
    # de-duplicate while keeping deterministic order
    seen: set[str] = set()
    unique: list[Path] = []
    for path in sorted(expanded, key=lambda item: item.as_posix()):
        key = path.as_posix()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def write_artifacts(
    artifacts: ArtifactSet,
    output_root: Path | str,
    mode: str = "manifest-clean",
) -> ArtifactWriteReport:
    return ArtifactWriter().write(artifacts, output_root, mode)  # type: ignore[arg-type]


def verify_project(
    output_root: Path | str,
    verify: VerifyProject,
) -> BuildVerificationReport:
    return verify_generated_project(Path(output_root), verify)
