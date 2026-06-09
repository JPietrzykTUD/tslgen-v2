"""Compiler orchestration: sources -> ... -> generated per-profile project.

Pure up to the optional write/verify steps. For each machine profile, selects the
implementations reachable in that profile (one specialization per reachable
`(extension, type)`), lowers each, groups by primitive, and renders per-profile
headers/modules with a top-level dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslc.backend.translation import BackendTranslation
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import load_machine_profiles
from tslc.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.output.artifacts import ArtifactSet
from tslc.render.project import ProfileRender, RenderedProject, render_project
from tslc.select.selector import Selector
from tslc.sources import SourceLoader

_DEFAULT_BACKENDS = ("cpp", "rust")
_TYPE_ORDER = {
    tag: index
    for index, tag in enumerate(
        ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64")
    )
}


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...]
    profiles: tuple[str, ...]
    type_tags: tuple[str, ...]
    backends: tuple[str, ...] = _DEFAULT_BACKENDS


@dataclass(frozen=True, slots=True)
class CoverageEntry:
    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str


@dataclass(frozen=True, slots=True)
class SkippedEntry:
    """A selected slot whose body could not be lowered yet (recorded, not failed)."""

    profile: str
    backend: str
    primitive: str
    extension: str
    type_tag: str
    reason: str


@dataclass(frozen=True, slots=True)
class GenerationResult:
    artifacts: ArtifactSet
    rendered: RenderedProject | None
    diagnostics: tuple[Diagnostic, ...]
    coverage: tuple[CoverageEntry, ...]
    skipped: tuple[SkippedEntry, ...] = ()


def generate(request: GenerationRequest) -> GenerationResult:
    diagnostics: list[Diagnostic] = []

    load_result = SourceLoader().load(request.source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    from tslc.syntax.parser import TslParser

    parse_result = TslParser().parse(load_result.documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return _empty(diagnostics)

    catalog_result = CatalogBuilder().build(parse_result)
    diagnostics.extend(catalog_result.diagnostics)
    if catalog_result.catalog is None or has_errors(diagnostics):
        return _empty(diagnostics)
    catalog = catalog_result.catalog
    machine_profiles = load_machine_profiles(request.machine_profiles_path)

    selector = Selector()
    lowerer = Lowerer()
    type_tags = _sorted_type_tags(request.type_tags)
    coverage: list[CoverageEntry] = []
    skipped: list[SkippedEntry] = []
    profile_renders: list[ProfileRender] = []

    for profile_name in sorted(request.profiles):
        profile = machine_profiles.get(profile_name)
        if profile is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-UNKNOWN-PROFILE",
                    message=f"no machine profile named {profile_name!r}",
                )
            )
            continue

        # backend -> primitive -> [specialization]
        grouped: dict[str, dict[str, list[LoweredSpecialization]]] = {
            backend: {} for backend in request.backends
        }
        for primitive in sorted(request.primitives):
            selection = selector.select_profile(catalog, profile, primitive, type_tags)
            diagnostics.extend(selection.diagnostics)
            for slot in selection.selected:
                for backend in request.backends:
                    translation = BackendTranslation(catalog=catalog, backend_id=backend)
                    lowered = lowerer.lower(slot, catalog, translation)
                    # Real diagnostics (warnings/errors) bubble up; a not-yet-lowerable
                    # body is an "info" skip -> recorded as a coverage gap, not noise.
                    diagnostics.extend(d for d in lowered.diagnostics if d.severity != "info")
                    if lowered.specialization is None:
                        reason = next(
                            (d.message for d in lowered.diagnostics), "unsupported body"
                        )
                        skipped.append(
                            SkippedEntry(
                                profile=profile_name,
                                backend=backend,
                                primitive=primitive,
                                extension=slot.extension.name,
                                type_tag=slot.type_tag,
                                reason=reason,
                            )
                        )
                        continue
                    grouped[backend].setdefault(primitive, []).append(lowered.specialization)
                    coverage.append(
                        CoverageEntry(
                            profile=profile_name,
                            backend=backend,
                            primitive=primitive,
                            extension=slot.extension.name,
                            type_tag=slot.type_tag,
                        )
                    )

        profile_renders.append(
            ProfileRender(
                profile=profile,
                cpp=_finalize(grouped.get("cpp", {})),
                rust=_finalize(grouped.get("rust", {})),
            )
        )

    rendered = (
        render_project(tuple(profile_renders), request.backends)
        if profile_renders
        else None
    )
    artifacts = rendered.artifacts if rendered is not None else ArtifactSet.create(())
    return GenerationResult(
        artifacts=artifacts,
        rendered=rendered,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=tuple(sorted(coverage, key=_coverage_key)),
        skipped=tuple(sorted(skipped, key=_skipped_key)),
    )


def _finalize(
    by_primitive: dict[str, list[LoweredSpecialization]],
) -> dict[str, tuple[LoweredSpecialization, ...]]:
    return {
        name: tuple(sorted(specs, key=_spec_key)) for name, specs in by_primitive.items()
    }


def _spec_key(spec: LoweredSpecialization) -> tuple[int, str, str]:
    return (_TYPE_ORDER.get(spec.type_tag, 99), spec.type_tag, spec.extension_name)


def _sorted_type_tags(type_tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(type_tags, key=lambda tag: (_TYPE_ORDER.get(tag, 99), tag)))


def _coverage_key(entry: CoverageEntry) -> tuple[str, str, str, str, int, str]:
    return (
        entry.profile,
        entry.primitive,
        entry.backend,
        entry.extension,
        _TYPE_ORDER.get(entry.type_tag, 99),
        entry.type_tag,
    )


def _skipped_key(entry: SkippedEntry) -> tuple[str, str, str, str, int, str]:
    return (
        entry.profile,
        entry.primitive,
        entry.backend,
        entry.extension,
        _TYPE_ORDER.get(entry.type_tag, 99),
        entry.type_tag,
    )


def _empty(diagnostics: list[Diagnostic]) -> GenerationResult:
    return GenerationResult(
        artifacts=ArtifactSet.create(()),
        rendered=None,
        diagnostics=sort_diagnostics(diagnostics),
        coverage=(),
    )
