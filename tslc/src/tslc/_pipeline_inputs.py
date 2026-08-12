"""Input loading boundary for the generation pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol

from tslc.authoring import check_documents
from tslc.backend.capability import (
    BackendPolicyInputs,
    EMPTY_BACKEND_POLICY_INPUTS,
)
from tslc.backend.registry import load_backend_policy_inputs
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.compiler_assets import (
    RenderAssets,
    load_default_render_assets,
)
from tslc.diagnostics import Diagnostic, has_errors
from tslc.sources import SourceLoader
from tslc.support_policy_views import immediate_split_names, policy_split_names
from tslc.value_tests import HarnessPrimitiveNames, discover_harness_primitives


class _InputRequest(Protocol):
    @property
    def source_paths(self) -> tuple[Path, ...]: ...

    @property
    def machine_profiles_path(self) -> Path: ...

    @property
    def backends(self) -> tuple[str, ...]: ...

    @property
    def test_harness(self) -> bool: ...

    @property
    def render_artifacts(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class CatalogInputs:
    """Validated authoring inputs before profile selection or rendering."""

    catalog: Catalog
    source_digest: str


@dataclass(frozen=True, slots=True)
class _PipelineInputs:
    catalog: Catalog
    machine_profiles: Mapping[str, MachineProfile]
    render_assets: RenderAssets | None
    policy_inputs: BackendPolicyInputs
    split_names: frozenset[str]
    imm_split_names: frozenset[str]
    test_harness: HarnessPrimitiveNames
    input_digest: str


def _load_inputs(request: _InputRequest) -> tuple[_PipelineInputs | None, list[Diagnostic]]:
    catalog_inputs, diagnostics = load_catalog_inputs(
        request.source_paths,
        required_backends=request.backends,
    )
    if catalog_inputs is None:
        return None, diagnostics
    catalog = catalog_inputs.catalog
    split_names = policy_split_names(catalog)
    imm_split_names = immediate_split_names(catalog)
    test_harness = discover_harness_primitives(catalog)
    if request.test_harness:
        diagnostics.extend(test_harness.diagnostics)
    profile_result = load_machine_profiles_checked(
        request.machine_profiles_path,
        catalog.target_families,
    )
    diagnostics.extend(profile_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics
    return (
        _PipelineInputs(
            catalog=catalog,
            machine_profiles=profile_result.profiles,
            render_assets=(
                load_default_render_assets() if request.render_artifacts else None
            ),
            policy_inputs=(
                load_backend_policy_inputs(request.backends)
                if request.render_artifacts
                else EMPTY_BACKEND_POLICY_INPUTS
            ),
            split_names=split_names,
            imm_split_names=imm_split_names,
            test_harness=test_harness,
            input_digest=_combine_input_digests(
                catalog_inputs.source_digest,
                profile_result.digest,
            ),
        ),
        diagnostics,
    )


def load_catalog_inputs(
    source_paths: tuple[Path, ...],
    *,
    required_backends: tuple[str, ...],
) -> tuple[CatalogInputs | None, list[Diagnostic]]:
    """Load, parse, promote, and validate a complete TSL corpus."""

    diagnostics: list[Diagnostic] = []
    load_result = SourceLoader().load(source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics

    checked = check_documents(
        load_result.documents,
        required_backends=required_backends,
    )
    diagnostics.extend(checked.diagnostics)
    if checked.catalog is None or has_errors(diagnostics):
        return None, diagnostics
    digest = sha256()
    for document in load_result.documents:
        digest.update(document.path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(document.digest.encode("ascii"))
        digest.update(b"\0")
    return CatalogInputs(checked.catalog, digest.hexdigest()), diagnostics


def _combine_input_digests(source_digest: str, profile_digest: str | None) -> str:
    digest = sha256()
    digest.update(f"sources:{source_digest}\n".encode("ascii"))
    digest.update(f"profiles:{profile_digest or 'unavailable'}\n".encode("ascii"))
    return digest.hexdigest()


__all__ = ("CatalogInputs", "load_catalog_inputs")
