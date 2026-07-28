"""Typed configuration for complete generated-project rendering."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)


@dataclass(frozen=True, slots=True)
class ProjectRenderConfig:
    rust_package: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG


DEFAULT_PROJECT_RENDER_CONFIG = ProjectRenderConfig()


__all__ = (
    "DEFAULT_PROJECT_RENDER_CONFIG",
    "ProjectRenderConfig",
)
