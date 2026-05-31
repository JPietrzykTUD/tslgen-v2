"""Supplementary static asset and template rendering boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata, ArtifactSet


@dataclass(frozen=True, slots=True)
class ProjectSkeletonRenderContext:
    backend_id: str
    project_name: str
    artifact_path: str
    helper_files: tuple[str, ...] = ()

    def format_values(self) -> dict[str, str]:
        helper_files = tuple(sorted(self.helper_files))
        if helper_files:
            helper_manifest = "\n".join(f"# helper: {path}" for path in helper_files)
        else:
            helper_manifest = "# helper: none"
        return {
            "backend_id": self.backend_id,
            "project_name": self.project_name,
            "artifact_path": self.artifact_path,
            "helper_manifest": helper_manifest,
        }


@dataclass(frozen=True, slots=True)
class SupplementaryStaticAsset:
    source_path: str
    logical_path: str
    media_type: str = "text/plain"
    metadata: tuple[ArtifactMetadata, ...] = ()


@dataclass(frozen=True, slots=True)
class SupplementaryTemplateAsset:
    source_path: str
    logical_path: str
    context: ProjectSkeletonRenderContext
    media_type: str = "text/plain"
    metadata: tuple[ArtifactMetadata, ...] = ()


SupplementaryAsset = SupplementaryStaticAsset | SupplementaryTemplateAsset


@dataclass(frozen=True, slots=True)
class SupplementaryRenderResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...]


_SEMANTIC_TEMPLATE_FIELDS = frozenset(
    {
        "backend_feature",
        "dependency",
        "extension",
        "extension_id",
        "fallback",
        "feature",
        "feature_gate",
        "intrinsic",
        "intrinsic_name",
        "primitive",
        "primitive_name",
        "selector",
        "source",
        "source_payload",
        "template",
        "tsil",
        "type",
        "type_tag",
    }
)


def render_supplementary_assets(
    asset_root: Path,
    assets: tuple[SupplementaryAsset, ...],
) -> SupplementaryRenderResult:
    """Copy/render supplementary assets into an in-memory artifact set."""

    artifacts: list[Artifact] = []
    diagnostics: list[Diagnostic] = []
    root = asset_root.resolve()

    for asset in sorted(assets, key=lambda item: item.logical_path):
        if isinstance(asset, SupplementaryStaticAsset):
            artifact, asset_diagnostics = _copy_static_asset(root, asset)
        else:
            artifact, asset_diagnostics = _render_template_asset(root, asset)
        diagnostics.extend(asset_diagnostics)
        if artifact is not None:
            artifacts.append(artifact)

    return SupplementaryRenderResult(
        artifacts=ArtifactSet.create(tuple(artifacts)),
        diagnostics=tuple(sorted(diagnostics, key=_diagnostic_sort_key)),
    )


def cpp_project_skeleton_assets(
    context: ProjectSkeletonRenderContext,
) -> tuple[SupplementaryAsset, ...]:
    metadata = (ArtifactMetadata("backend", context.backend_id),)
    return (
        SupplementaryStaticAsset(
            source_path="buildsystem/cpp/static/tsl_project.marker",
            logical_path="share/tsl/cpp_skeleton.txt",
            metadata=metadata,
        ),
        SupplementaryTemplateAsset(
            source_path="buildsystem/cpp/templates/CMakeLists.txt.in",
            logical_path="CMakeLists.txt",
            context=context,
            media_type="text/x-cmake",
            metadata=metadata,
        ),
        SupplementaryStaticAsset(
            source_path="helpers/cpp/skeleton.hpp",
            logical_path="include/tsl/support/skeleton.hpp",
            media_type="text/x-c++hdr",
            metadata=metadata,
        ),
    )


def rust_project_skeleton_assets(
    context: ProjectSkeletonRenderContext,
) -> tuple[SupplementaryAsset, ...]:
    metadata = (ArtifactMetadata("backend", context.backend_id),)
    return (
        SupplementaryTemplateAsset(
            source_path="buildsystem/rust/templates/Cargo.toml.in",
            logical_path="Cargo.toml",
            context=context,
            metadata=metadata,
        ),
        SupplementaryStaticAsset(
            source_path="buildsystem/rust/static/tsl_project.marker",
            logical_path="share/tsl/rust_skeleton.txt",
            metadata=metadata,
        ),
        SupplementaryStaticAsset(
            source_path="helpers/rust/skeleton.rs",
            logical_path="src/support/skeleton.rs",
            media_type="text/x-rust",
            metadata=metadata,
        ),
    )


def _copy_static_asset(
    root: Path,
    asset: SupplementaryStaticAsset,
) -> tuple[Artifact | None, tuple[Diagnostic, ...]]:
    source = root / asset.source_path
    if not source.is_file():
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-SUPPLEMENTARY-MISSING-STATIC-ASSET",
                    message=(
                        "missing supplementary static asset "
                        f"{asset.source_path!r}"
                    ),
                ),
            ),
        )
    return (
        Artifact(
            logical_path=asset.logical_path,
            content=source.read_text(encoding="utf-8"),
            media_type=asset.media_type,
            metadata=asset.metadata,
        ),
        (),
    )


def _render_template_asset(
    root: Path,
    asset: SupplementaryTemplateAsset,
) -> tuple[Artifact | None, tuple[Diagnostic, ...]]:
    source = root / asset.source_path
    if not source.is_file():
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-SUPPLEMENTARY-MISSING-TEMPLATE-ASSET",
                    message=(
                        "missing supplementary template asset "
                        f"{asset.source_path!r}"
                    ),
                ),
            ),
        )

    template_text = source.read_text(encoding="utf-8")
    values = asset.context.format_values()
    diagnostics = _template_field_diagnostics(template_text, values, asset)
    if diagnostics:
        return None, diagnostics

    return (
        Artifact(
            logical_path=asset.logical_path,
            content=template_text.format_map(values),
            media_type=asset.media_type,
            metadata=asset.metadata,
        ),
        (),
    )


def _template_field_diagnostics(
    template_text: str,
    values: dict[str, str],
    asset: SupplementaryTemplateAsset,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for _, field_name, _, _ in Formatter().parse(template_text):
        if field_name is None:
            continue
        root_name = field_name.split(".", maxsplit=1)[0].split("[", maxsplit=1)[0]
        if root_name in _SEMANTIC_TEMPLATE_FIELDS:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SUPPLEMENTARY-TEMPLATE-SEMANTIC-FIELD",
                    message=(
                        "supplementary template "
                        f"{asset.source_path!r} references semantic field "
                        f"{root_name!r}"
                    ),
                )
            )
            continue
        if root_name != field_name:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SUPPLEMENTARY-TEMPLATE-UNSUPPORTED-FIELD-SHAPE",
                    message=(
                        "supplementary template "
                        f"{asset.source_path!r} uses unsupported field shape "
                        f"{field_name!r}"
                    ),
                )
            )
            continue
        if root_name not in values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SUPPLEMENTARY-TEMPLATE-UNKNOWN-FIELD",
                    message=(
                        "supplementary template "
                        f"{asset.source_path!r} references unknown field "
                        f"{root_name!r}"
                    ),
                )
            )
    return tuple(sorted(diagnostics, key=_diagnostic_sort_key))


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str]:
    return diagnostic.code, diagnostic.message
