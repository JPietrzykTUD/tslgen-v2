"""Choose an implementation for a concrete target.

Selection matches a target's ``(extension, type_tag)`` against the primitive's
implementation selector paths, expanding type groups. Extension fallback chains
(e.g. ``avx2_vl -> avx2``) are a documented future extension point; the first
slice uses direct extension matches only.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Catalog, Extension, Implementation, Primitive
from tslc.diagnostics import Diagnostic, sort_diagnostics
from tslc.select.target import Target


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    target: Target
    primitive: Primitive
    implementation: Implementation
    extension: Extension


@dataclass(frozen=True, slots=True)
class SelectionResult:
    selected: SelectedImplementation | None
    diagnostics: tuple[Diagnostic, ...]


class Selector:
    def select(self, catalog: Catalog, target: Target) -> SelectionResult:
        diagnostics: list[Diagnostic] = []

        primitive = catalog.primitive(target.primitive_name, unmasked=True)
        if primitive is None:
            return _error(
                "TSL-SELECT-UNKNOWN-PRIMITIVE",
                f"no unmasked primitive named {target.primitive_name!r}",
            )

        extension = catalog.extensions.get(target.extension)
        if extension is None:
            return _error(
                "TSL-SELECT-UNKNOWN-EXTENSION",
                f"no extension named {target.extension!r}",
            )

        matches = [
            implementation
            for implementation in primitive.implementations
            if implementation.extension == target.extension
            and catalog.type_group_contains(implementation.type_group, target.type_tag)
        ]
        if not matches:
            return _error(
                "TSL-SELECT-NO-IMPLEMENTATION",
                (
                    f"primitive {target.primitive_name!r} has no implementation for "
                    f"extension {target.extension!r} and type {target.type_tag!r}"
                ),
            )
        if len(matches) > 1:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="TSL-SELECT-AMBIGUOUS-IMPLEMENTATION",
                    message=(
                        f"primitive {target.primitive_name!r} has {len(matches)} "
                        f"implementations matching {target.extension!r}/{target.type_tag!r}; "
                        "using the first in source order"
                    ),
                )
            )

        selected = SelectedImplementation(
            target=target,
            primitive=primitive,
            implementation=matches[0],
            extension=extension,
        )
        return SelectionResult(selected=selected, diagnostics=sort_diagnostics(diagnostics))


def _error(code: str, message: str) -> SelectionResult:
    return SelectionResult(
        selected=None,
        diagnostics=(Diagnostic(severity="error", code=code, message=message),),
    )
