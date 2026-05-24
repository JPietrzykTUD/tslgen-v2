"""Target selection for the M107 clean restart slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, Implementation, Primitive


@dataclass(frozen=True, slots=True)
class Target:
    backend: str
    primitive_name: str
    extension: str
    type_tag: str

    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.backend, self.primitive_name, self.extension, self.type_tag)


@dataclass(frozen=True, slots=True)
class SelectedImplementation:
    target: Target
    primitive: Primitive
    implementation: Implementation


@dataclass(frozen=True, slots=True)
class SelectionResult:
    selected: tuple[SelectedImplementation, ...]
    diagnostics: tuple[Diagnostic, ...]


class Selector:
    """Select implementation objects for explicit target requests."""

    def select(self, catalog: Catalog, target: Target) -> SelectionResult:
        diagnostics: list[Diagnostic] = []
        if target.backend not in ("cpp", "rust"):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SELECT-UNSUPPORTED-BACKEND",
                    message=(
                        f"backend {target.backend!r} is unsupported; "
                        "expected one of: cpp, rust"
                    ),
                )
            )
            return SelectionResult(selected=(), diagnostics=tuple(diagnostics))

        primitive = self._find_primitive(catalog, target.primitive_name)
        if primitive is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                    message=f"primitive {target.primitive_name!r} is not in the catalog",
                )
            )
            return SelectionResult(selected=(), diagnostics=tuple(diagnostics))

        implementation = self._find_implementation(primitive, target)
        if implementation is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SELECT-NO-IMPLEMENTATION",
                    message=(
                        f"primitive {primitive.name!r} has no implementation for "
                        f"extension {target.extension!r} and type {target.type_tag!r}"
                    ),
                    location=self._primitive_location(primitive),
                )
            )
            return SelectionResult(selected=(), diagnostics=tuple(diagnostics))

        return SelectionResult(
            selected=(
                SelectedImplementation(
                    target=target,
                    primitive=primitive,
                    implementation=implementation,
                ),
            ),
            diagnostics=(),
        )

    def _find_primitive(self, catalog: Catalog, name: str) -> Primitive | None:
        for primitive in catalog.primitives:
            if primitive.name == name:
                return primitive
        return None

    def _find_implementation(
        self,
        primitive: Primitive,
        target: Target,
    ) -> Implementation | None:
        for implementation in primitive.implementations:
            if (
                implementation.extension == target.extension
                and implementation.type_tag == target.type_tag
            ):
                return implementation
        return None

    def _primitive_location(self, primitive: Primitive) -> SourceLocation:
        return primitive.source
