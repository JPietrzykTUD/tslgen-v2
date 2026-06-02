"""Rendering boundaries for generated artifacts."""

from tslgen.rendering.generated_project import (
    GeneratedProjectRenderResult,
    build_generated_project_render_model,
    render_generated_project_skeleton,
)
from tslgen.rendering.primitive_templates import (
    CPP_PRIMITIVE_TEMPLATE_PATH,
    RUST_PRIMITIVE_TEMPLATE_PATH,
    PrimitiveTemplateRenderContext,
    PrimitiveTemplateRenderResult,
    cpp_primitive_template_context,
    render_primitive_templates,
    rust_primitive_template_context,
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
    "CPP_PRIMITIVE_TEMPLATE_PATH",
    "ProjectSkeletonRenderContext",
    "PrimitiveTemplateRenderContext",
    "PrimitiveTemplateRenderResult",
    "RUST_PRIMITIVE_TEMPLATE_PATH",
    "SupplementaryRenderResult",
    "SupplementaryStaticAsset",
    "SupplementaryTemplateAsset",
    "build_generated_project_render_model",
    "cpp_project_skeleton_assets",
    "cpp_primitive_template_context",
    "render_primitive_templates",
    "render_generated_project_skeleton",
    "render_supplementary_assets",
    "rust_primitive_template_context",
    "rust_project_skeleton_assets",
]
