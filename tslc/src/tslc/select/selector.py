"""Resolve which implementation bodies a machine profile emits.

For a profile, a primitive, and a concrete type, every *extension* reachable in
the profile yields its own specialization slot (the extension is part of the
`simd<type, ext>` key, so there is no cross-extension ambiguity). Within one
`(extension, type)` slot the body is chosen by the confirmed order:

    1. most specific type-group (fewest members)
    2. tie -> most hardware flags (most specialized)
    3. tie -> first occurrence (source order)

An implementation body is usable only if the `requires` clause that applies to the
type has its flags ⊆ the profile's feature set. A *derived* extension (`avx2_vl`
inherits `avx2`) is only active when its `lscpu_flags ⊆ features`, and then
supersedes its base; a base extension's bodies self-gate via `requires`.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension, Implementation, Primitive
from tslc.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    primitive: Primitive
    implementation: Implementation
    extension: Extension
    type_tag: str


@dataclass(frozen=True, slots=True)
class ProfileSelectionResult:
    selected: tuple[SelectedImplementation, ...]
    diagnostics: tuple[Diagnostic, ...]


class Selector:
    def select_profile(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive_name: str,
        type_tags: tuple[str, ...],
    ) -> ProfileSelectionResult:
        # Prefer the unmasked variant; fall back to a masked-only primitive (like
        # `blend`, which exists solely as `[mask=pass_through]`). Names that also have
        # an unmasked variant still resolve unmasked — explicit masked requests for
        # those are a separate concern.
        primitive = catalog.primitive(primitive_name, unmasked=True) or catalog.primitive(
            primitive_name, unmasked=False
        )
        if primitive is None:
            return ProfileSelectionResult(
                selected=(),
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                        message=f"no primitive named {primitive_name!r}",
                    ),
                ),
            )

        selected: list[SelectedImplementation] = []
        for extension_name in self._emit_extensions(catalog, profile):
            for type_tag in type_tags:
                best = self._best_body(
                    catalog, profile, primitive, extension_name, type_tag
                )
                if best is not None:
                    selected.append(
                        SelectedImplementation(
                            primitive=primitive,
                            implementation=best,
                            extension=catalog.extensions[extension_name],
                            type_tag=type_tag,
                        )
                    )
        return ProfileSelectionResult(selected=tuple(selected), diagnostics=())

    def _emit_extensions(self, catalog: Catalog, profile: MachineProfile) -> list[str]:
        """Extensions to emit for a profile.

        A *base* extension (no `inherits`) is always a candidate; its individual
        bodies self-gate via their `requires` (e.g. avx2's 256-bit *float* add needs
        only `avx`, so it appears on an avx-only profile while its 256-bit *integer*
        add does not). A *derived* extension (e.g. `avx2_vl`, which `inherits avx2`)
        is a candidate only when genuinely active — its `lscpu_flags ⊆ features` —
        and then it *supersedes* its base (avx512vl profiles use `_vl`, not the base).
        Candidates with no usable body for any type drop out later in `_best_body`.
        """

        active_derived = [
            name
            for name, ext in catalog.extensions.items()
            if ext.inherits is not None and ext.lscpu_flags <= profile.features
        ]
        superseded = {catalog.extensions[name].inherits for name in active_derived}

        emit: list[str] = []
        for name, ext in catalog.extensions.items():
            if name in superseded:
                continue
            if ext.inherits is not None and not (ext.lscpu_flags <= profile.features):
                continue  # inactive derived extension
            emit.append(name)
        return sorted(emit)

    def _best_body(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
    ) -> Implementation | None:
        # Gather candidates from the extension and the ancestors it inherits from
        # (e.g. avx2_vl borrows avx2's body where it has none of its own).
        chain = catalog.extension_chain(extension_name)
        distance = {name: index for index, name in enumerate(chain)}
        candidates: list[tuple[Implementation, frozenset[str]]] = []
        for implementation in primitive.implementations:
            if implementation.extension not in distance:
                continue
            if not catalog.type_group_contains(implementation.type_group, type_tag):
                continue
            flags = _applicable_flags(catalog, implementation, type_tag)
            if flags is None or not (flags <= profile.features):
                continue
            candidates.append((implementation, flags))
        if not candidates:
            return None
        best, _ = min(
            candidates,
            key=lambda item: (
                distance[item[0].extension],  # own extension before inherited (a)
                catalog.type_group_specificity(item[0].type_group),  # most specific (b)
                -len(item[1]),  # most hardware flags
                item[0].source_order,  # first occurrence
            ),
        )
        return best
        # (a) before (b): when a derived extension is active and supersedes its base
        # (e.g. avx2_vl over avx2 on an avx512vl profile), the derived ext's OWN body
        # wins even if a base body is more type-specific — so avx512vl comparisons use
        # the `_vl` native-mask body, not the base's lane-bitmask `si?` body. Within a
        # single extension distance ties, so specificity still decides there.


def _applicable_flags(
    catalog: Catalog, implementation: Implementation, type_tag: str
) -> frozenset[str] | None:
    """The requirement-clause flags that apply to ``type_tag`` (None if none apply)."""

    if not implementation.requirements:
        return frozenset()
    for clause in implementation.requirements:
        if clause.extension is not None and clause.extension != implementation.extension:
            continue  # this clause is scoped to a different extension
        if clause.type_group is None or catalog.type_group_contains(
            clause.type_group, type_tag
        ):
            return clause.flags
    return None
