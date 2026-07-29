"""Focused generation-session lowering-cache contracts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

from tslc._pipeline_inputs import _load_inputs
from tslc._pipeline_lowering_cache import _LoweringCache
from tslc.backend.translation import BackendDialect
from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic
from tslc.ir.segments import Segment
from tslc.lower.lowerer import Lowerer, LoweringResult
from tslc.pipeline import (
    BackendProfileScope,
    GenerationRequest,
    _GenerationSession,
    _lowering_skipped_entry,
)
from tslc.select.selector import SelectedImplementation, SimdTypeBaseBinding


class _CountingLowerer(Lowerer):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def lower(
        self,
        selected: SelectedImplementation,
        catalog: Catalog,
        backend: BackendDialect,
        *,
        body_segments: tuple[Segment, ...] | None = None,
    ) -> LoweringResult:
        del selected, catalog, backend, body_segments
        self.calls += 1
        return LoweringResult(
            specialization=None,
            diagnostics=(
                Diagnostic(
                    severity="info",
                    code="TSL-LOWER-CACHE-TEST",
                    message=f"lowering call {self.calls}",
                ),
            ),
        )


def _selected(catalog: Catalog) -> SelectedImplementation:
    primitive = catalog.primitive("add")
    assert primitive is not None
    implementation = next(
        item for item in primitive.implementations if item.extension == "avx2"
    )
    extension = catalog.extensions["avx2"]
    return SelectedImplementation(
        primitive=primitive,
        implementation=implementation,
        extension=extension,
        type_tag="si32",
        extension_family_capability=catalog.target_families.extension_family(
            extension.family
        ),
    )


def test_lowering_cache_reuses_exact_result_and_separates_every_key_axis(
    catalog: Catalog,
) -> None:
    lowerer = _CountingLowerer()
    dialects = cast(
        dict[str, BackendDialect],
        {"cpp": object(), "rust": object()},
    )
    cache = _LoweringCache(lowerer, catalog, dialects)
    selected = _selected(catalog)

    first = cache.lower(selected, "cpp", body_segments=())
    repeated = cache.lower(selected, "cpp", body_segments=())

    assert repeated is first
    assert lowerer.calls == 1

    changed_axes = (
        replace(selected, primitive=replace(selected.primitive)),
        replace(selected, implementation=replace(selected.implementation)),
        replace(selected, extension=replace(selected.extension)),
        replace(selected, type_tag="ui32"),
        replace(selected, required_features=frozenset({"unit_feature"})),
        replace(selected, to_target="ui32"),
        replace(selected, concrete_lanes=7),
        replace(
            selected,
            simd_type_base_bindings=(SimdTypeBaseBinding("Indices", "ui32"),),
        ),
        replace(
            selected,
            fixed_fallback_extension=catalog.extensions["scalar"],
        ),
        replace(
            selected,
            extension_family_capability=replace(
                selected.extension_family_capability,
                index_vector_register=(
                    not selected.extension_family_capability.index_vector_register
                ),
            ),
        ),
    )
    for changed in changed_axes:
        cache.lower(changed, "cpp", body_segments=())
    cache.lower(selected, "rust", body_segments=())

    info = cache.info()
    assert info.hits == 1
    assert info.misses == 1 + len(changed_axes) + 1
    assert info.size == info.misses
    assert lowerer.calls == info.misses


def test_cached_skip_result_stays_profile_scoped(catalog: Catalog) -> None:
    lowerer = _CountingLowerer()
    cache = _LoweringCache(
        lowerer,
        catalog,
        cast(dict[str, BackendDialect], {"cpp": object()}),
    )
    selected = _selected(catalog)
    lowered = cache.lower(selected, "cpp", body_segments=())
    assert cache.lower(selected, "cpp", body_segments=()) is lowered

    skylake = _lowering_skipped_entry(
        "skylake", "cpp", "add", selected, lowered
    )
    cascadelake = _lowering_skipped_entry(
        "cascadelake", "cpp", "add", selected, lowered
    )

    assert skylake.profile == "skylake"
    assert cascadelake.profile == "cascadelake"
    assert skylake.diagnostics is cascadelake.diagnostics
    assert lowerer.calls == 1


def test_equivalent_profiles_reuse_lowering_but_keep_profile_metadata(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    request = GenerationRequest(
        source_paths=tuple(sorted(data_root.rglob("*.tsl"))),
        machine_profiles_path=machine_profiles_path,
        primitives=("add",),
        profiles=("skylake", "cascadelake"),
        type_tags=("si32",),
        backends=("cpp",),
        render_artifacts=False,
    )
    inputs, diagnostics = _load_inputs(request)
    assert inputs is not None
    session = _GenerationSession(request, inputs, diagnostics)

    result = session.run()

    assert result.diagnostics == ()
    info = session.lowering_cache.info()
    assert info.hits == info.misses
    assert info.hits > 0
    profiles = tuple(item.profile for item in session.emitted_profiles)
    assert tuple(profile.name for profile in profiles) == (
        "cascadelake",
        "skylake",
    )
    assert profiles[0].features != profiles[1].features
    assert profiles[0] is not profiles[1]


def test_backend_profile_scope_limits_only_the_named_backend(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    request = GenerationRequest(
        source_paths=tuple(sorted(data_root.rglob("*.tsl"))),
        machine_profiles_path=machine_profiles_path,
        primitives=("add",),
        profiles=("skylake", "cascadelake"),
        type_tags=("si32",),
        backends=("cpp", "rust"),
        backend_profile_scopes=(
            BackendProfileScope("rust", ("skylake",)),
        ),
        render_artifacts=False,
    )
    inputs, diagnostics = _load_inputs(request)
    assert inputs is not None
    session = _GenerationSession(request, inputs, diagnostics)

    result = session.run()

    assert result.diagnostics == ()
    profiles = {
        profile.profile.name: profile
        for profile in result.emitted_profiles
    }
    assert set(profiles) == {"cascadelake", "skylake"}
    assert profiles["cascadelake"].supports_backend("cpp")
    assert not profiles["cascadelake"].supports_backend("rust")
    assert profiles["skylake"].supports_backend("cpp")
    assert profiles["skylake"].supports_backend("rust")
    assert {entry.backend for entry in result.coverage} == {"cpp", "rust"}
