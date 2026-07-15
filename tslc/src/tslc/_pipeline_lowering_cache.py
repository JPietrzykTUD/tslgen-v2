"""Generation-session reuse of immutable lowering results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tslc.backend.translation import BackendDialect
from tslc.catalog.model import Catalog
from tslc.catalog.target_families import ExtensionFamilyCapability
from tslc.ir.segments import Segment
from tslc.lower.lowerer import Lowerer, LoweringResult
from tslc.select.selector import SelectedImplementation, SimdTypeBaseBinding

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class _LoweringCacheKey:
    """Every selected fact that can affect one lowering result.

    Catalog-owned objects use session-local identities. This distinguishes exact
    promoted objects without hashing their mapping fields or exposing process object
    IDs. The local integers are used only for cache lookup, never for output ordering.
    """

    backend_id: str
    primitive_identity: int
    implementation_identity: int
    extension_identity: int
    type_tag: str
    required_features: frozenset[str]
    to_target: str | None
    concrete_lanes: int | None
    simd_type_base_bindings: tuple[SimdTypeBaseBinding, ...]
    fixed_fallback_extension_identity: int | None
    extension_family_capability: ExtensionFamilyCapability


@dataclass(frozen=True, slots=True)
class _LoweringCacheInfo:
    hits: int
    misses: int
    size: int


class _SessionIdentityTable:
    """Assign stable local integers to exact objects retained by one catalog."""

    def __init__(self) -> None:
        self._identities: dict[int, tuple[object, int]] = {}

    def identity(self, value: object) -> int:
        marker = id(value)
        current = self._identities.get(marker)
        if current is not None:
            stored, identity = current
            if stored is not value:
                raise AssertionError("live catalog objects reused a process identity")
            return identity
        identity = len(self._identities)
        self._identities[marker] = (value, identity)
        return identity


class _LoweringCache:
    """Lower exact selected slots once within a generation session."""

    def __init__(
        self,
        lowerer: Lowerer,
        catalog: Catalog,
        dialects: Mapping[str, BackendDialect],
    ) -> None:
        self._lowerer = lowerer
        self._catalog = catalog
        self._dialects = dialects
        self._identities = _SessionIdentityTable()
        self._results: dict[_LoweringCacheKey, LoweringResult] = {}
        self._hits = 0
        self._misses = 0

    def lower(
        self,
        selected: SelectedImplementation,
        backend_id: str,
        *,
        body_segments: tuple[Segment, ...],
    ) -> LoweringResult:
        key = self._key(selected, backend_id)
        cached = self._results.get(key)
        if cached is not None:
            self._hits += 1
            return cached
        self._misses += 1
        result = self._lowerer.lower(
            selected,
            self._catalog,
            self._dialects[backend_id],
            body_segments=body_segments,
        )
        self._results[key] = result
        return result

    def info(self) -> _LoweringCacheInfo:
        return _LoweringCacheInfo(self._hits, self._misses, len(self._results))

    def _key(
        self, selected: SelectedImplementation, backend_id: str
    ) -> _LoweringCacheKey:
        return _LoweringCacheKey(
            backend_id=backend_id,
            primitive_identity=self._identities.identity(selected.primitive),
            implementation_identity=self._identities.identity(
                selected.implementation
            ),
            extension_identity=self._identities.identity(selected.extension),
            type_tag=selected.type_tag,
            required_features=selected.required_features,
            to_target=selected.to_target,
            concrete_lanes=selected.concrete_lanes,
            simd_type_base_bindings=selected.simd_type_base_bindings,
            fixed_fallback_extension_identity=(
                None
                if selected.fixed_fallback_extension is None
                else self._identities.identity(selected.fixed_fallback_extension)
            ),
            extension_family_capability=selected.extension_family_capability,
        )


__all__ = ("_LoweringCache", "_LoweringCacheInfo", "_LoweringCacheKey")
