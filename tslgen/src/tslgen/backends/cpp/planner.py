from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
from tslgen.io.artifacts import ArtifactDescriptor, ArtifactPlan


CPP_BACKEND_ID = "cpp"
SUPPORTED_CPP_ARTIFACT_KINDS = frozenset({"generated"})


@dataclass(frozen=True, slots=True)
class CppRenderJob:
    descriptor: ArtifactDescriptor
    candidates: tuple[ImplementationCandidate, ...]
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda candidate: candidate.key))
        object.__setattr__(self, "candidates", candidates)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.descriptor.logical_path.as_posix(),
            self.descriptor.kind,
            tuple(candidate.key for candidate in self.candidates),
        )


@dataclass(frozen=True, slots=True)
class CppRenderPlan:
    source_plan: ArtifactPlan
    jobs: tuple[CppRenderJob, ...]
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        jobs = tuple(sorted(self.jobs, key=lambda job: job.key))
        object.__setattr__(self, "jobs", jobs)


def plan_cpp_render_jobs(
    plan: ArtifactPlan,
    selection: CandidateSelection,
) -> Result[CppRenderPlan]:
    diagnostics: list[Diagnostic] = []
    if plan.backend_id != CPP_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-BACKEND",
                f"C++ renderer cannot render artifact plan for backend "
                f"{plan.backend_id!r}",
            )
        )

    jobs: list[CppRenderJob] = []
    for descriptor in plan.descriptors:
        diagnostics.extend(_descriptor_diagnostics(descriptor))
        candidates = _descriptor_candidates(descriptor, selection, diagnostics)
        diagnostics.extend(_candidate_diagnostics(candidates))
        if not has_errors(diagnostics):
            jobs.append(
                CppRenderJob(
                    descriptor=descriptor,
                    candidates=candidates,
                    metadata=FrozenMap(
                        {
                            "candidate_count": len(candidates),
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
        CppRenderPlan(
            source_plan=plan,
            jobs=tuple(jobs),
            metadata=FrozenMap(
                {
                    "backend_id": CPP_BACKEND_ID,
                    "candidate_count": sum(len(job.candidates) for job in jobs),
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
    if descriptor.backend_id != CPP_BACKEND_ID:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-BACKEND",
                f"C++ renderer cannot render descriptor for backend "
                f"{descriptor.backend_id!r}",
            )
        )
    if descriptor.kind not in SUPPORTED_CPP_ARTIFACT_KINDS:
        diagnostics.append(
            Diagnostic.error(
                "TSL-CPP-RENDER-UNSUPPORTED-ARTIFACT",
                f"C++ renderer does not support artifact kind {descriptor.kind!r}",
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
                    "TSL-CPP-RENDER-MISSING-CANDIDATE",
                    f"C++ render descriptor {descriptor.logical_path.as_posix()!r} "
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
        if candidate.backend not in (None, CPP_BACKEND_ID):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-CPP-RENDER-CANDIDATE-BACKEND",
                    f"C++ renderer received candidate {candidate.candidate_id!r} "
                    f"selected for backend {candidate.backend!r}",
                )
            )
        body = candidate.implementation.body
        if body.kind != "tsil" or not isinstance(body.payload, str):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-CPP-RENDER-CANDIDATE-BODY",
                    f"C++ renderer supports only string TSIL payloads in this "
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
