"""Pipeline orchestration for the clean restart generator."""

from tslgen.pipeline.generated_primitive_pipeline import (
    ParsedTinyGeneratedProjectResult,
    SelectedLoweredFunction,
    build_parsed_tiny_generated_project_artifacts,
)
from tslgen.pipeline.real_scalar_pipeline import (
    RealScalarEmitReturnGeneratedProjectResult,
    RealScalarEmitReturnSelection,
    build_real_scalar_emit_return_generated_project_artifacts,
)

__all__ = [
    "ParsedTinyGeneratedProjectResult",
    "RealScalarEmitReturnGeneratedProjectResult",
    "RealScalarEmitReturnSelection",
    "SelectedLoweredFunction",
    "build_parsed_tiny_generated_project_artifacts",
    "build_real_scalar_emit_return_generated_project_artifacts",
]
