from __future__ import annotations

from dataclasses import dataclass

from tslgen.analysis.candidates import CandidateSelection
from tslgen.core.result import Result
from tslgen.io.artifacts import ArtifactPlan, ArtifactSet

from .planner import RUST_BACKEND_ID, plan_rust_render_jobs
from .renderer import render_rust_plan


@dataclass(frozen=True, slots=True)
class RustBackend:
    backend_id: str = RUST_BACKEND_ID

    def render(
        self,
        plan: ArtifactPlan,
        selection: CandidateSelection,
    ) -> Result[ArtifactSet]:
        planned = plan_rust_render_jobs(plan, selection)
        if not planned.is_ok:
            return Result.failure(planned.diagnostics)
        return render_rust_plan(planned.unwrap())
