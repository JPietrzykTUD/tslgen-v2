"""Small public API facade."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from tslc.backend.registry import registered_backend_ids
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.output.artifacts import ArtifactSet
from tslc.output.verify import (
    BuildVerificationReport,
    BuildVerifierConfig,
    VerifyProject,
    verify_generated_project,
)
from tslc.output.verify_model import BackendToolchain
from tslc.output.writer import ArtifactWriteMode, ArtifactWriteReport, ArtifactWriter
from tslc.pipeline import GenerationMode, GenerationRequest, GenerationResult, generate

_ARITH_TYPE_TAGS = DEFAULT_SCALAR_TYPE_TAGS


def generate_project(
    source_paths: Iterable[Path | str],
    *,
    machine_profiles_path: Path | str,
    primitives: Iterable[str] | None = None,
    profiles: Iterable[str] | None = None,
    type_tags: Iterable[str] = _ARITH_TYPE_TAGS,
    backends: Iterable[str] = registered_backend_ids(),
    generation_mode: GenerationMode = "partial",
    test_harness: bool = False,
    value_test_warnings: bool = False,
    value_test_fuzz: bool = False,
    render_artifacts: bool = True,
) -> GenerationResult:
    """Run the full compiler pipeline and return in-memory artifacts.

    ``source_paths`` entries may be ``.tsl`` files or directories; directories
    are expanded to every ``.tsl`` file beneath them (the catalog needs the
    extension/type/language definitions alongside the primitive files).
    ``profiles`` names machine feature-profiles from ``machine_profiles_path``.
    ``profiles=None`` means every loaded machine profile.
    ``primitives=None`` means every primitive in the loaded catalog.
    """

    request = GenerationRequest(
        source_paths=_expand_sources(source_paths),
        machine_profiles_path=Path(machine_profiles_path),
        primitives=tuple(primitives) if primitives is not None else None,
        profiles=tuple(profiles) if profiles is not None else None,
        type_tags=tuple(type_tags),
        backends=tuple(backends),
        mode=generation_mode,
        test_harness=test_harness,
        value_test_warnings=value_test_warnings,
        value_test_fuzz=value_test_fuzz,
        render_artifacts=render_artifacts,
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
    mode: ArtifactWriteMode = "manifest-clean",
) -> ArtifactWriteReport:
    return ArtifactWriter().write(artifacts, output_root, mode)


def verify_project(
    output_root: Path | str,
    verify: VerifyProject,
    *,
    toolchains: Mapping[str, BackendToolchain] | None = None,
    runner_paths: Mapping[str, str] | None = None,
    run_value_tests: bool = False,
) -> BuildVerificationReport:
    return verify_generated_project(
        Path(output_root),
        verify,
        config=BuildVerifierConfig.create(
            toolchains=toolchains,
            runner_paths=runner_paths,
            run_value_tests=run_value_tests,
        ),
    )
