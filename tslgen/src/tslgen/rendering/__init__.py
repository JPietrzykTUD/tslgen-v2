"""Rendering boundaries for generated artifacts."""

from tslgen.rendering.generated_project import (
    GeneratedProjectRenderResult,
    build_generated_project_render_model,
    render_generated_project_skeleton,
)
from tslgen.rendering.supplementary import (
    ProjectSkeletonRenderContext,
    SupplementaryRenderResult,
    SupplementaryStaticAsset,
    SupplementaryTemplateAsset,
    cpp_project_skeleton_assets,
    render_supplementary_assets,
    rust_project_skeleton_assets,
)

__all__ = [
    "GeneratedProjectRenderResult",
    "ProjectSkeletonRenderContext",
    "SupplementaryRenderResult",
    "SupplementaryStaticAsset",
    "SupplementaryTemplateAsset",
    "build_generated_project_render_model",
    "cpp_project_skeleton_assets",
    "render_generated_project_skeleton",
    "render_supplementary_assets",
    "rust_project_skeleton_assets",
]
