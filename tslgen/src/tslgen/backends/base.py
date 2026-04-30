from __future__ import annotations

from typing import Protocol

from tslgen.analysis.candidates import CandidateSelection
from tslgen.core.result import Result
from tslgen.io.artifacts import ArtifactPlan, ArtifactSet


class BackendRenderer(Protocol):
    backend_id: str

    def render(
        self,
        plan: ArtifactPlan,
        selection: CandidateSelection,
    ) -> Result[ArtifactSet]:
        """Render artifacts for an already planned backend slice."""
