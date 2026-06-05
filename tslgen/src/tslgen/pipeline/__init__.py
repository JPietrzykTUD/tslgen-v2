"""Pipeline orchestration for the clean restart generator."""

from tslgen.pipeline.generated_primitive_pipeline import (
    ParsedTinyGeneratedProjectResult,
    SelectedLoweredFunction,
    build_parsed_tiny_generated_project_artifacts,
)
from tslgen.pipeline.primitive_project_pipeline import (
    SelectedPrimitiveProjectResult,
    SelectedPrimitiveBodyRenderEntry,
    SelectedPrimitiveBodyRenderSelection,
    build_primitive_project_artifacts_from_selected_body,
    build_primitive_project_artifacts_from_selected_bodies,
)

__all__ = [
    "ParsedTinyGeneratedProjectResult",
    "SelectedPrimitiveProjectResult",
    "SelectedPrimitiveBodyRenderEntry",
    "SelectedPrimitiveBodyRenderSelection",
    "SelectedLoweredFunction",
    "build_parsed_tiny_generated_project_artifacts",
    "build_primitive_project_artifacts_from_selected_body",
    "build_primitive_project_artifacts_from_selected_bodies",
]
