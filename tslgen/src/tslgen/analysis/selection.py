"""Target selection for the M107 clean restart slice."""

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, Implementation, Primitive


@dataclass(frozen=True, slots=True)
class TargetAttribute:
    key: str
    value: str
    key_argument: str | None = None


@dataclass(frozen=True, slots=True)
class Target:
    backend: str
    primitive_name: str
    extension: str
    type_tag: str
    attributes: tuple[TargetAttribute, ...] = ()

    def sort_key(
        self,
    ) -> tuple[str, str, str, str, tuple[tuple[str, str, str], ...]]:
        return (
            self.backend,
            self.primitive_name,
            self.extension,
            self.type_tag,
            _target_attribute_sort_key(self.attributes),
        )


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

        primitive_variants = self._find_primitives(catalog, target.primitive_name)
        if not primitive_variants:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SELECT-UNKNOWN-PRIMITIVE",
                    message=f"primitive {target.primitive_name!r} is not in the catalog",
                )
            )
            return SelectionResult(selected=(), diagnostics=tuple(diagnostics))

        primitive = self._find_attribute_variant(primitive_variants, target)
        if primitive is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-SELECT-NO-ATTRIBUTE-VARIANT",
                    message=(
                        f"primitive {target.primitive_name!r} has no concrete "
                        "attribute variant matching requested attributes "
                        f"{_format_target_attributes(target.attributes)}; "
                        "available concrete variants are: "
                        f"{_format_available_attribute_variants(primitive_variants)}"
                    ),
                    location=self._primitive_location(primitive_variants[0]),
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

    def _find_primitives(self, catalog: Catalog, name: str) -> tuple[Primitive, ...]:
        primitives: list[Primitive] = []
        for primitive in catalog.primitives:
            if primitive.name == name:
                primitives.append(primitive)
        return tuple(primitives)

    def _find_attribute_variant(
        self,
        primitives: tuple[Primitive, ...],
        target: Target,
    ) -> Primitive | None:
        target_key = _target_attribute_key(target.attributes)
        for primitive in primitives:
            if _primitive_attribute_key(primitive) == target_key:
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


def _target_attribute_key(
    attributes: tuple[TargetAttribute, ...],
) -> tuple[tuple[str, str | None, str], ...]:
    return tuple(
        sorted(
            (
                (attribute.key, attribute.key_argument, attribute.value)
                for attribute in attributes
            ),
            key=_attribute_sort_key,
        )
    )


def _target_attribute_sort_key(
    attributes: tuple[TargetAttribute, ...],
) -> tuple[tuple[str, str, str], ...]:
    return _attribute_key_sort_key(_target_attribute_key(attributes))


def _primitive_attribute_key(
    primitive: Primitive,
) -> tuple[tuple[str, str | None, str], ...]:
    return tuple(
        sorted(
            (
                (attribute.key, attribute.key_argument, attribute.value)
                for attribute in primitive.attributes
            ),
            key=_attribute_sort_key,
        )
    )


def _format_target_attributes(
    attributes: tuple[TargetAttribute, ...],
) -> str:
    return _format_attribute_key(_target_attribute_key(attributes))


def _format_available_attribute_variants(
    primitives: tuple[Primitive, ...],
) -> str:
    keys = sorted(
        {_primitive_attribute_key(primitive) for primitive in primitives},
        key=_attribute_key_sort_key,
    )
    return ", ".join(_format_attribute_key(key) for key in keys)


def _format_attribute_key(
    key: tuple[tuple[str, str | None, str], ...],
) -> str:
    if not key:
        return "<empty>"
    return "[" + ", ".join(_format_attribute(attribute) for attribute in key) + "]"


def _format_attribute(attribute: tuple[str, str | None, str]) -> str:
    key, key_argument, value = attribute
    if key_argument is None:
        return f"{key}={value}"
    return f"{key}({key_argument})={value}"


def _attribute_key_sort_key(
    key: tuple[tuple[str, str | None, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    return tuple(_attribute_sort_key(attribute) for attribute in key)


def _attribute_sort_key(attribute: tuple[str, str | None, str]) -> tuple[str, str, str]:
    key, key_argument, value = attribute
    return (key, key_argument or "", value)
