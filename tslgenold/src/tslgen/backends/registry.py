from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from tslgen.analysis.candidates import CandidateSelection
from tslgen.core.diagnostics import Diagnostic
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.io.artifacts import ArtifactPlan, ArtifactSet

from .base import BackendRenderer
from .cpp.backend import CppBackend
from .rust.backend import RustBackend


@dataclass(frozen=True, slots=True)
class BackendRegistry:
    renderers: tuple[BackendRenderer, ...]
    renderers_by_id: FrozenMap[str, BackendRenderer] = field(init=False)

    def __post_init__(self) -> None:
        renderers = tuple(sorted(self.renderers, key=lambda renderer: renderer.backend_id))
        backend_ids = [renderer.backend_id for renderer in renderers]
        duplicate_ids = tuple(
            sorted(
                backend_id
                for backend_id in set(backend_ids)
                if backend_ids.count(backend_id) > 1
            )
        )
        if duplicate_ids:
            joined = ", ".join(repr(backend_id) for backend_id in duplicate_ids)
            raise ValueError(f"duplicate backend renderer id(s): {joined}")
        object.__setattr__(self, "renderers", renderers)
        object.__setattr__(
            self,
            "renderers_by_id",
            FrozenMap((renderer.backend_id, renderer) for renderer in renderers),
        )

    @property
    def backend_ids(self) -> tuple[str, ...]:
        return tuple(renderer.backend_id for renderer in self.renderers)

    def render(
        self,
        backend_id: str,
        plan: ArtifactPlan,
        selection: CandidateSelection,
    ) -> Result[ArtifactSet]:
        renderer = self.renderers_by_id.get(backend_id)
        if renderer is None:
            return Result.failure(
                (
                    Diagnostic.error(
                        "TSL-BACKEND-RENDERER-UNKNOWN",
                        f"no renderer is registered for backend {backend_id!r}; "
                        f"known backends: {_known_backend_text(self.backend_ids)}",
                    ),
                )
            )
        return renderer.render(plan, selection)


def default_backend_registry() -> BackendRegistry:
    renderers = (
        cast(BackendRenderer, CppBackend()),
        cast(BackendRenderer, RustBackend()),
    )
    return BackendRegistry(renderers)


def _known_backend_text(backend_ids: tuple[str, ...]) -> str:
    if not backend_ids:
        return "none"
    return ", ".join(repr(backend_id) for backend_id in backend_ids)
