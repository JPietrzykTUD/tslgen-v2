"""Input loading boundary for the generation pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.model import Catalog
from tslc.catalog.validation import validate_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.compiler_assets import (
    RenderAssets,
    load_default_render_assets,
    load_default_tsl_grammar,
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


@dataclass(frozen=True, slots=True)
class _PipelineInputs:
    catalog: Catalog
    machine_profiles: Mapping[str, MachineProfile]
    render_assets: RenderAssets
    split_names: frozenset[str]
    imm_split_names: frozenset[str]
    test_harness: HarnessPrimitiveNames


def _load_inputs(request: _InputRequest) -> tuple[_PipelineInputs | None, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    load_result = SourceLoader().load(request.source_paths)
    diagnostics.extend(load_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics

    from tslc.syntax.parser import TslParser

    parse_result = TslParser(load_default_tsl_grammar()).parse(load_result.documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return None, diagnostics

    catalog_result = CatalogBuilder().build(parse_result)
    diagnostics.extend(catalog_result.diagnostics)
    if catalog_result.catalog is None or has_errors(diagnostics):
        return None, diagnostics
    catalog = catalog_result.catalog
    diagnostics.extend(
        validate_catalog(
            catalog,
            parse_result,
            required_backends=request.backends,
            supported_backends=registered_backend_ids(),
        )
    )
    if has_errors(diagnostics):
        return None, diagnostics
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
            render_assets=load_default_render_assets(),
            split_names=split_names,
            imm_split_names=imm_split_names,
            test_harness=test_harness,
        ),
        diagnostics,
    )
