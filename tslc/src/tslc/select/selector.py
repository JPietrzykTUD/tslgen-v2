"""Resolve which implementation bodies a machine profile emits.

For a profile, a primitive, and a concrete type, every *extension* reachable in
the profile yields its own specialization slot (the extension is part of the
`simd<type, ext>` key, so there is no cross-extension ambiguity). Within one
`(extension, type)` slot the body is chosen by the confirmed order:

    1. most specific type-group (fewest members)
    2. tie -> most hardware flags (most specialized)
    3. tie -> first occurrence (source order)

An implementation is usable only if its `required_flags` are known and are a
subset of the profile's feature set.
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
        primitive = catalog.primitive(primitive_name, unmasked=True)
        if primitive is None:
            return ProfileSelectionResult(
                selected=(),
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                        message=f"no unmasked primitive named {primitive_name!r}",
                    ),
                ),
            )

        # Extensions that are real catalog extensions (skip bracketed multi-selectors).
        extension_names = sorted(
            {
                implementation.extension
                for implementation in primitive.implementations
                if implementation.extension in catalog.extensions
            }
        )

        selected: list[SelectedImplementation] = []
        for type_tag in type_tags:
            for extension_name in extension_names:
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

    def _best_body(
        self,
        catalog: Catalog,
        profile: MachineProfile,
        primitive: Primitive,
        extension_name: str,
        type_tag: str,
    ) -> Implementation | None:
        candidates = [
            implementation
            for implementation in primitive.implementations
            if implementation.extension == extension_name
            and implementation.required_flags is not None
            and implementation.required_flags <= profile.features
            and catalog.type_group_contains(implementation.type_group, type_tag)
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda impl: (
                catalog.type_group_specificity(impl.type_group),
                -len(impl.required_flags or frozenset()),
                impl.source_order,
            ),
        )
