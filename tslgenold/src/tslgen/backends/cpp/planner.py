from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.values import CatalogValue
from tslgen.domain.backends import BackendMetadataBoundary
from tslgen.domain.extensions import Extension
from tslgen.io.artifacts import ArtifactDescriptor, ArtifactPlan
from tslgen.lowering import LoweringPlan

from .bodies import CppFunctionDefinition, plan_cpp_production_definitions
from .declarations import CppFunctionDeclaration, plan_cpp_production_declarations
from .layout import (
    CPP_NATIVE_HEADER_LAYOUT,
    cpp_layout_diagnostics,
    cpp_layout_name,
)
from .scalar_binary import (
    CppScalarBinarySlice,
    cpp_native_header_no_lowering_diagnostic,
    plan_cpp_scalar_binary_slice,
)
from .translation import CppNativeTranslationPlan, translate_cpp_native_intrinsic_calls


CPP_BACKEND_ID = "cpp"
SUPPORTED_CPP_ARTIFACT_KINDS = frozenset({"generated"})


@dataclass(frozen=True, slots=True)
class CppRenderJob:
    descriptor: ArtifactDescriptor
    candidates: tuple[ImplementationCandidate, ...]
    declarations: tuple[CppFunctionDeclaration, ...] = ()
    definitions: tuple[CppFunctionDefinition, ...] = ()
    scalar_binary_slice: CppScalarBinarySlice | None = None
    metadata: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda candidate: candidate.key))
        object.__setattr__(self, "candidates", candidates)
        declarations = tuple(sorted(self.declarations, key=lambda item: item.key))
        object.__setattr__(self, "declarations", declarations)
        definitions = tuple(sorted(self.definitions, key=lambda item: item.key))
        object.__setattr__(self, "definitions", definitions)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.descriptor.logical_path.as_posix(),
            self.descriptor.kind,
            tuple(candidate.key for candidate in self.candidates),
            tuple(declaration.key for declaration in self.declarations),
            tuple(definition.key for definition in self.definitions),
            self.scalar_binary_slice.key if self.scalar_binary_slice is not None else (),
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
    lowering_plan: LoweringPlan | None = None,
    metadata_boundary: BackendMetadataBoundary | None = None,
    extensions: tuple[Extension, ...] = (),
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
        layout_name = cpp_layout_name(descriptor)
        candidates = _descriptor_candidates(descriptor, selection, diagnostics)
        diagnostics.extend(
            _candidate_diagnostics(
                candidates,
                require_tsil_body=layout_name != CPP_NATIVE_HEADER_LAYOUT,
            )
        )
        declarations: tuple[CppFunctionDeclaration, ...] = ()
        definitions: tuple[CppFunctionDefinition, ...] = ()
        scalar_binary_slice: CppScalarBinarySlice | None = None
        native_translation_plan: CppNativeTranslationPlan | None = None
        if not has_errors(diagnostics) and layout_name != CPP_NATIVE_HEADER_LAYOUT:
            declaration_result = plan_cpp_production_declarations(candidates)
            diagnostics.extend(declaration_result.diagnostics)
            if declaration_result.is_ok:
                declarations = declaration_result.unwrap()
        if (
            not has_errors(diagnostics)
            and layout_name != CPP_NATIVE_HEADER_LAYOUT
            and lowering_plan is not None
        ):
            definition_result = plan_cpp_production_definitions(
                declarations,
                lowering_plan,
            )
            diagnostics.extend(definition_result.diagnostics)
            if definition_result.is_ok:
                definitions = definition_result.unwrap()
        if (
            not has_errors(diagnostics)
            and layout_name == CPP_NATIVE_HEADER_LAYOUT
            and lowering_plan is None
        ):
            diagnostics.extend(
                diagnostic
                for candidate in candidates
                for diagnostic in (cpp_native_header_no_lowering_diagnostic(candidate),)
                if diagnostic is not None
            )
        if (
            not has_errors(diagnostics)
            and layout_name == CPP_NATIVE_HEADER_LAYOUT
            and lowering_plan is not None
        ):
            translation_result = translate_cpp_native_intrinsic_calls(
                candidates,
                lowering_plan,
                metadata_boundary=metadata_boundary,
                extensions=extensions,
            )
            diagnostics.extend(translation_result.diagnostics)
            if translation_result.is_ok:
                native_translation_plan = translation_result.unwrap()
        if (
            not has_errors(diagnostics)
            and layout_name == CPP_NATIVE_HEADER_LAYOUT
            and lowering_plan is not None
        ):
            scalar_result = plan_cpp_scalar_binary_slice(
                candidates,
                lowering_plan,
                native_translation_plan,
            )
            diagnostics.extend(scalar_result.diagnostics)
            if scalar_result.is_ok:
                scalar_binary_slice = scalar_result.unwrap()
        if not has_errors(diagnostics):
            metadata: dict[str, CatalogValue] = {
                "candidate_count": len(candidates),
                "definition_count": len(definitions),
                "required_flags": _required_flag_names(candidates),
                "target_extensions": _target_extension_names(candidates),
            }
            if layout_name is not None:
                metadata["cpp_layout"] = layout_name
            if scalar_binary_slice is not None:
                metadata["scalar_specialization_count"] = len(
                    scalar_binary_slice.specializations
                )
                metadata["native_specialization_count"] = len(
                    scalar_binary_slice.native_specializations
                )
            jobs.append(
                CppRenderJob(
                    descriptor=descriptor,
                    candidates=candidates,
                    declarations=declarations,
                    definitions=definitions,
                    scalar_binary_slice=scalar_binary_slice,
                    metadata=FrozenMap(metadata),
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
                    "definition_count": sum(len(job.definitions) for job in jobs),
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
    diagnostics.extend(cpp_layout_diagnostics(descriptor))
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
    *,
    require_tsil_body: bool = True,
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
        if not require_tsil_body:
            continue
        body = candidate.implementation.body
        if body.kind != "tsil" or body.text is None:
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
