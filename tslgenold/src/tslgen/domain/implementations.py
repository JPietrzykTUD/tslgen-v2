from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, cast

from tslgen.core.diagnostics import Diagnostic, SourceSpan, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.ordering import stable_sort_key
from tslgen.core.result import Result
from tslgen.domain.primitives import PrimitiveDeclaration
from tslgen.domain.values import CatalogMap, CatalogValue


type ImplementationSelectorKind = Literal["extension", "type_group"]
type ImplementationBodyClassification = Literal[
    "tsil",
    "intrinsic",
    "backend_specific",
    "opaque",
]
type ImplementationExtensionFilter = Callable[[ImplementationSelector], bool]
type ImplementationTypeFilter = Callable[
    [ImplementationSelector, ImplementationSelector],
    bool,
]


@dataclass(frozen=True, slots=True)
class ImplementationSelector:
    kind: ImplementationSelectorKind
    raw: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.raw:
            raise ValueError("implementation selector raw value must be non-empty")
        object.__setattr__(self, "names", tuple(self.names))

    @property
    def key(self) -> tuple[str, str, tuple[str, ...]]:
        return (self.kind, self.raw, self.names)


@dataclass(frozen=True, slots=True)
class ImplementationBody:
    kind: str
    payload: CatalogValue
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("implementation body kind must be non-empty")

    @property
    def classification(self) -> ImplementationBodyClassification:
        if self.kind == "tsil":
            return "tsil"
        if self.kind in {"intrin", "intrinsic", "intrin_compose"}:
            return "intrinsic"
        if self.kind in {"c", "c17", "cpp", "rust"}:
            return "backend_specific"
        return "opaque"

    @property
    def text(self) -> str | None:
        return self.payload if isinstance(self.payload, str) else None

    @property
    def has_payload(self) -> bool:
        return self.payload is not None


@dataclass(frozen=True, slots=True)
class ImplementationSpec:
    extension_selector: ImplementationSelector
    type_selector: ImplementationSelector
    body: ImplementationBody
    source_span: SourceSpan
    requires_value: CatalogValue | None = None
    fields: CatalogMap = field(default_factory=FrozenMap.empty)
    extra_fields: CatalogMap = field(default_factory=FrozenMap.empty)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.extension_selector.key,
            self.type_selector.key,
            self.body.kind,
            self.body.text or "",
            stable_sort_key(self.extra_fields),
        )


@dataclass(frozen=True, slots=True)
class ImplementationSpecSet:
    primitive: PrimitiveDeclaration
    specs: tuple[ImplementationSpec, ...]
    specs_by_selector: FrozenMap[tuple[str, str], ImplementationSpec] = field(
        init=False
    )

    def __post_init__(self) -> None:
        specs = tuple(sorted(self.specs, key=lambda spec: spec.key))
        object.__setattr__(self, "specs", specs)
        object.__setattr__(
            self,
            "specs_by_selector",
            FrozenMap(
                (
                    (
                        spec.extension_selector.raw,
                        spec.type_selector.raw,
                    ),
                    spec,
                )
                for spec in specs
            ),
        )


def implementation_specs_from_primitive(
    primitive: PrimitiveDeclaration,
    *,
    include_extension_selector: ImplementationExtensionFilter | None = None,
    include_type_selector: ImplementationTypeFilter | None = None,
) -> Result[ImplementationSpecSet]:
    impls_value = primitive.fields.get("impls")
    if impls_value is None:
        return Result.ok(ImplementationSpecSet(primitive=primitive, specs=()))

    impls = _as_map(impls_value)
    if impls is None:
        return Result.failure(
            (
                _shape_diagnostic(
                    primitive,
                    "implementation block",
                    "impls",
                ),
            )
        )

    diagnostics: list[Diagnostic] = []
    specs: list[ImplementationSpec] = []
    for extension_selector_text, extension_value in impls.items():
        extension_selector = ImplementationSelector(
            kind="extension",
            raw=extension_selector_text,
            names=_selector_items(extension_selector_text),
        )
        if (
            include_extension_selector is not None
            and not include_extension_selector(extension_selector)
        ):
            continue

        type_map = _as_map(extension_value)
        if type_map is None:
            diagnostics.append(
                _shape_diagnostic(
                    primitive,
                    "implementation extension selector",
                    extension_selector_text,
                )
            )
            continue

        for type_selector_text, implementation_value in type_map.items():
            type_selector = ImplementationSelector(
                kind="type_group",
                raw=type_selector_text,
                names=_selector_items(type_selector_text),
            )
            if (
                include_type_selector is not None
                and not include_type_selector(extension_selector, type_selector)
            ):
                continue

            implementation_map = _as_map(implementation_value)
            if implementation_map is None:
                diagnostics.append(
                    _type_selector_shape_diagnostic(
                        primitive,
                        implementation_value,
                        type_selector_text,
                    )
                )
                continue
            spec = _implementation_spec(
                primitive=primitive,
                extension_selector=extension_selector,
                type_selector=type_selector,
                implementation_map=implementation_map,
            )
            diagnostics.extend(spec.diagnostics)
            if spec.is_ok:
                specs.append(spec.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        ImplementationSpecSet(primitive=primitive, specs=tuple(specs)),
        diagnostics=ordered,
    )


def _implementation_spec(
    *,
    primitive: PrimitiveDeclaration,
    extension_selector: ImplementationSelector,
    type_selector: ImplementationSelector,
    implementation_map: CatalogMap,
) -> Result[ImplementationSpec]:
    if "implementation" not in implementation_map and _has_nested_selector_shape(
        implementation_map
    ):
        return Result.failure(
            (
                _shape_diagnostic(
                    primitive,
                    "nested implementation selector",
                    f"{extension_selector.raw}/{type_selector.raw}",
                ),
            )
        )

    body = _implementation_body(primitive, implementation_map)
    if not body.is_ok:
        return Result.failure(body.diagnostics)
    return Result.ok(
        ImplementationSpec(
            extension_selector=extension_selector,
            type_selector=type_selector,
            body=body.unwrap(),
            source_span=primitive.source_span,
            requires_value=implementation_map.get("requires"),
            fields=implementation_map,
            extra_fields=_extra_fields(implementation_map),
        )
    )


def _implementation_body(
    primitive: PrimitiveDeclaration,
    implementation_map: CatalogMap,
) -> Result[ImplementationBody]:
    body_value = implementation_map.get("implementation")
    if body_value is None:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-IMPLEMENTATION-SPEC-BODY-MISSING",
                    f"primitive {primitive.name!r} implementation is missing "
                    "an 'implementation' body",
                    location=primitive.source_span.location,
                ),
            )
        )

    body_map = _as_map(body_value)
    if body_map is None or len(body_map) == 0:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-IMPLEMENTATION-SPEC-BODY-SHAPE",
                    f"primitive {primitive.name!r} implementation body must be "
                    "a non-empty field map",
                    location=primitive.source_span.location,
                ),
            )
        )
    if len(body_map) > 1:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-IMPLEMENTATION-SPEC-BODY-AMBIGUOUS",
                    f"primitive {primitive.name!r} implementation body has "
                    "multiple payload fields",
                    location=primitive.source_span.location,
                ),
            )
        )

    kind, payload = next(iter(body_map.items()))
    return Result.ok(
        ImplementationBody(
            kind=kind,
            payload=payload,
            source_span=primitive.source_span,
        )
    )


def _extra_fields(implementation_map: CatalogMap) -> CatalogMap:
    return FrozenMap(
        (name, value)
        for name, value in implementation_map.items()
        if name not in {"implementation", "requires"}
    )


def _has_nested_selector_shape(implementation_map: CatalogMap) -> bool:
    return any(
        field_name != "requires" and isinstance(value, FrozenMap)
        for field_name, value in implementation_map.items()
    )


def _type_selector_shape_diagnostic(
    primitive: PrimitiveDeclaration,
    value: CatalogValue,
    selector: str,
) -> Diagnostic:
    if isinstance(value, tuple):
        return Diagnostic.error(
            "TSL-IMPLEMENTATION-SPEC-LIST-VARIANTS",
            f"primitive {primitive.name!r} has list-backed implementation "
            f"variants for selector {selector!r}; variant policy is unresolved",
            location=primitive.source_span.location,
        )
    return _shape_diagnostic(primitive, "implementation type selector", selector)


def _shape_diagnostic(
    primitive: PrimitiveDeclaration,
    context: str,
    selector: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-IMPLEMENTATION-SPEC-SHAPE",
        f"primitive {primitive.name!r} has unsupported {context} shape for "
        f"selector {selector!r}",
        location=primitive.source_span.location,
    )


def _selector_items(selector: str) -> tuple[str, ...]:
    stripped = selector.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return ()
        raw_items = tuple(item.strip() for item in inner.split(",") if item.strip())
    else:
        raw_items = (stripped,)
    return tuple(_selector_base_name(item) for item in raw_items)


def _selector_base_name(selector_item: str) -> str:
    if "<" in selector_item and selector_item.endswith(">"):
        return selector_item.split("<", 1)[0]
    return selector_item


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return cast(CatalogMap, value)
    return None
