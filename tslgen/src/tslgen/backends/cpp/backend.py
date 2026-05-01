from __future__ import annotations

from dataclasses import dataclass

from tslgen.analysis.candidates import CandidateSelection
from tslgen.core.result import Result
from tslgen.domain.backends import BackendMetadataBoundary
from tslgen.domain.extensions import Extension
from tslgen.io.artifacts import ArtifactPlan, ArtifactSet
from tslgen.lowering import LoweringPlan

from .planner import CPP_BACKEND_ID, plan_cpp_render_jobs
from .renderer import render_cpp_plan


@dataclass(frozen=True, slots=True)
class CppBackend:
    backend_id: str = CPP_BACKEND_ID

    def render(
        self,
        plan: ArtifactPlan,
        selection: CandidateSelection,
        lowering_plan: LoweringPlan | None = None,
        metadata_boundary: BackendMetadataBoundary | None = None,
        extensions: tuple[Extension, ...] = (),
    ) -> Result[ArtifactSet]:
        planned = plan_cpp_render_jobs(
            plan,
            selection,
            lowering_plan,
            metadata_boundary,
            extensions,
        )
        if not planned.is_ok:
            return Result.failure(planned.diagnostics)
        return render_cpp_plan(planned.unwrap())
