from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import ArtifactDescriptor, ArtifactPlan

from .declarations import RustFunctionDeclaration, plan_rust_production_declarations


RUST_BACKEND_ID = "rust"
SUPPORTED_RUST_ARTIFACT_KINDS = frozenset({"generated"})


@dataclass(frozen=True, slots=True)
class RustRenderJob:
    descriptor: ArtifactDescriptor
    candidates: tuple[ImplementationCandidate, ...]
    declarations: tuple[RustFunctionDeclaration, ...] = ()
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda candidate: candidate.key))
        object.__setattr__(self, "candidates", candidates)
        declarations = tuple(sorted(self.declarations, key=lambda item: item.key))
        object.__setattr__(self, "declarations", declarations)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.descriptor.logical_path.as_posix(),
            self.descriptor.kind,
            tuple(candidate.key for candidate in self.candidates),
            tuple(declaration.key for declaration in self.declarations),
        )


@dataclass(frozen=True, slots=True)
class RustRenderPlan:
    source_plan: ArtifactPlan
    jobs: tuple[RustRenderJob, ...]
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        jobs = tuple(sorted(self.jobs, key=lambda job: job.key))
        object.__setattr__(self, "jobs", jobs)


def plan_rust_render_jobs(
    plan: ArtifactPlan,
    selection: CandidateSelection,
) -> Result[RustRenderPlan]:
    diagnostics: list[Diagnostic] = []
    if plan.backend_id != RUST_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-RUST-RENDER-BACKEND",
                f"Rust renderer cannot render artifact plan for backend "
                f"{plan.backend_id!r}",
            )
        )

    jobs: list[RustRenderJob] = []
    for descriptor in plan.descriptors:
        diagnostics.extend(_descriptor_diagnostics(descriptor))
        candidates = _descriptor_candidates(descriptor, selection, diagnostics)
        diagnostics.extend(_candidate_diagnostics(candidates))
        declarations: tuple[RustFunctionDeclaration, ...] = ()
        if not has_errors(diagnostics):
            declaration_result = plan_rust_production_declarations(candidates)
            diagnostics.extend(declaration_result.diagnostics)
            if declaration_result.is_ok:
                declarations = declaration_result.unwrap()
        if not has_errors(diagnostics):
            jobs.append(
                RustRenderJob(
                    descriptor=descriptor,
                    candidates=candidates,
                    declarations=declarations,
                    metadata=FrozenMap(
                        {
                            "candidate_count": len(candidates),
                            "declaration_count": len(declarations),
                            "required_flags": _required_flag_names(candidates),
                            "target_extensions": _target_extension_names(candidates),
                        }
                    ),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        RustRenderPlan(
            source_plan=plan,
            jobs=tuple(jobs),
            metadata=FrozenMap(
                {
                    "backend_id": RUST_BACKEND_ID,
                    "candidate_count": sum(len(job.candidates) for job in jobs),
                    "declaration_count": sum(
                        len(job.declarations) for job in jobs
                    ),
                    "required_flags": _required_flag_names(
                        candidate
                        for job in jobs
                        for candidate in job.candidates
                    ),
                    "target_extensions": _target_extension_names(
                        candidate
                        for job in jobs
                        for candidate in job.candidates
                    ),
                }
            ),
        ),
        diagnostics=ordered,
    )


def _descriptor_diagnostics(
    descriptor: ArtifactDescriptor,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if descriptor.backend_id != RUST_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-RUST-RENDER-BACKEND",
                f"Rust renderer cannot render descriptor for backend "
                f"{descriptor.backend_id!r}",
            )
        )
    if descriptor.kind not in SUPPORTED_RUST_ARTIFACT_KINDS:
        diagnostics.append(
            Diagnostic.error(
                "TSL-RUST-RENDER-UNSUPPORTED-ARTIFACT",
                f"Rust renderer does not support artifact kind {descriptor.kind!r}",
            )
        )
    return tuple(diagnostics)


def _descriptor_candidates(
    descriptor: ArtifactDescriptor,
    selection: CandidateSelection,
    diagnostics: list[Diagnostic],
) -> tuple[ImplementationCandidate, ...]:
    candidates: list[ImplementationCandidate] = []
    for candidate_id in descriptor.candidate_ids:
        candidate = selection.candidates_by_id.get(candidate_id)
        if candidate is None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-RUST-RENDER-MISSING-CANDIDATE",
                    f"Rust render descriptor {descriptor.logical_path.as_posix()!r} "
                    f"references unknown candidate {candidate_id!r}",
                )
            )
            continue
        candidates.append(candidate)
    return tuple(candidates)


def _candidate_diagnostics(
    candidates: tuple[ImplementationCandidate, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for candidate in candidates:
        if candidate.backend not in (None, RUST_BACKEND_ID):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-RUST-RENDER-CANDIDATE-BACKEND",
                    f"Rust renderer received candidate {candidate.candidate_id!r} "
                    f"selected for backend {candidate.backend!r}",
                )
            )
        body = candidate.implementation.body
        if body.kind != "tsil" or body.text is None:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-RUST-RENDER-CANDIDATE-BODY",
                    f"Rust renderer supports only string TSIL payloads in this "
                    f"slice; candidate {candidate.candidate_id!r} has "
                    f"{body.kind!r}",
                )
            )
    return tuple(diagnostics)


def _required_flag_names(
    candidates: Iterable[ImplementationCandidate],
) -> tuple[str, ...]:
    names = {
        flag.name
        for candidate in candidates
        for flag in candidate.required_flags
    }
    return tuple(sorted(names))


def _target_extension_names(
    candidates: Iterable[ImplementationCandidate],
) -> tuple[str, ...]:
    return tuple(sorted({candidate.target_extension for candidate in candidates}))
