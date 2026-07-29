"""Small public API facade."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from tslc.backend.registry import registered_backend_ids
from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)
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
from tslc.pipeline import (
    BackendProfileScope,
    GenerationMode,
    GenerationRequest,
    GenerationResult,
    generate,
)
from tslc.sources import expand_source_paths
from tslc.project_render import ProjectRenderConfig

_ARITH_TYPE_TAGS = DEFAULT_SCALAR_TYPE_TAGS


def generate_project(
    source_paths: Iterable[Path | str],
    *,
    machine_profiles_path: Path | str,
    primitives: Iterable[str] | None = None,
    profiles: Iterable[str] | None = None,
    backend_profiles: Mapping[str, Iterable[str]] | None = None,
    type_tags: Iterable[str] = _ARITH_TYPE_TAGS,
    extensions: Iterable[str] | None = None,
    backends: Iterable[str] | None = None,
    generation_mode: GenerationMode = "partial",
    test_harness: bool = False,
    value_test_warnings: bool = False,
    value_test_fuzz: bool = False,
    render_artifacts: bool = True,
    rust_package: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG,
) -> GenerationResult:
    """Run the full compiler pipeline and return in-memory artifacts.

    ``source_paths`` entries may be ``.tsl`` files or directories; directories
    are expanded to every ``.tsl`` file beneath them (the catalog needs the
    extension/type/language definitions alongside the primitive files).
    ``profiles`` names machine feature-profiles from ``machine_profiles_path``.
    ``profiles=None`` means every loaded machine profile.
    ``backend_profiles`` optionally restricts individual requested backends within
    that global profile set; omitted backends retain every requested profile.
    ``primitives=None`` means every primitive in the loaded catalog.
    """

    request = GenerationRequest(
        source_paths=expand_source_paths(source_paths),
        machine_profiles_path=Path(machine_profiles_path),
        primitives=tuple(primitives) if primitives is not None else None,
        profiles=tuple(profiles) if profiles is not None else None,
        type_tags=tuple(type_tags),
        extensions=tuple(extensions) if extensions is not None else None,
        backends=(
            tuple(backends) if backends is not None else registered_backend_ids()
        ),
        backend_profile_scopes=tuple(
            BackendProfileScope(
                backend_id=backend_id,
                profiles=tuple(sorted(set(profile_names))),
            )
            for backend_id, profile_names in sorted(
                (backend_profiles or {}).items()
            )
        ),
        mode=generation_mode,
        test_harness=test_harness,
        value_test_warnings=value_test_warnings,
        value_test_fuzz=value_test_fuzz,
        render_artifacts=render_artifacts,
        render_config=ProjectRenderConfig(rust_package=rust_package),
    )
    return generate(request)


def _expand_sources(source_paths: Iterable[Path | str]) -> tuple[Path, ...]:
    """Compatibility wrapper for older internal callers."""

    return expand_source_paths(source_paths)


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
    tool_paths: Mapping[str, str] | None = None,
    run_value_tests: bool = False,
    run_quality_checks: bool = False,
) -> BuildVerificationReport:
    return verify_generated_project(
        Path(output_root),
        verify,
        config=BuildVerifierConfig.create(
            toolchains=toolchains,
            runner_paths=runner_paths,
            tool_paths=tool_paths,
            run_value_tests=run_value_tests,
            run_quality_checks=run_quality_checks,
        ),
    )
