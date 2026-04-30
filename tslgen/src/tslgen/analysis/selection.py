from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from typing import Literal

from tslgen.analysis.expansion import PrimitiveVariant, expand_variants
from tslgen.analysis.requirements import (
    FeatureFlag,
    FlagCatalog,
    RequirementConstraint,
    build_flag_catalog,
)
from tslgen.core.diagnostics import Diagnostic, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.values import CatalogMap, CatalogValue
from tslgen.validation.reference_rules import ReferenceValidatedCatalog


type SelectorKind = Literal["extension", "type_group"]


@dataclass(frozen=True, slots=True)
class SelectionRequest:
    backend: str | None = None
    primitive_names: tuple[str, ...] = ()
    template_names: tuple[str, ...] = ()
    extension_names: tuple[str, ...] = ()
    cpu_flags: tuple[str, ...] = ()
    include_support_extensions: bool = True
    forced_support_extensions: tuple[str, ...] = ("scalar", "generic")

    def __post_init__(self) -> None:
        object.__setattr__(self, "primitive_names", tuple(self.primitive_names))
        object.__setattr__(self, "template_names", tuple(self.template_names))
        object.__setattr__(self, "extension_names", tuple(self.extension_names))
        object.__setattr__(self, "cpu_flags", tuple(self.cpu_flags))
        object.__setattr__(
            self,
            "forced_support_extensions",
            tuple(self.forced_support_extensions),
        )


@dataclass(frozen=True, slots=True)
class SelectorPlan:
    kind: SelectorKind
    raw: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.raw:
            raise ValueError("selector raw value must be non-empty")
        object.__setattr__(self, "names", tuple(self.names))


@dataclass(frozen=True, slots=True)
class VariantImplementationPlan:
    variant_id: str
    extension_selector: SelectorPlan
    type_selector: SelectorPlan
    requirements: tuple[RequirementConstraint, ...]

    def __post_init__(self) -> None:
        requirements = tuple(
            sorted(self.requirements, key=lambda requirement: requirement.key)
        )
        object.__setattr__(self, "requirements", requirements)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.variant_id,
            self.extension_selector.names,
            self.type_selector.names,
            tuple(requirement.key for requirement in self.requirements),
        )


@dataclass(frozen=True, slots=True)
class SelectionPlan:
    request: SelectionRequest
    variants: tuple[PrimitiveVariant, ...]
    allowed_extensions: tuple[str, ...]
    normalized_cpu_flags: tuple[FeatureFlag, ...]
    implementation_plans: tuple[VariantImplementationPlan, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "variants",
            tuple(self.variants),
        )
        object.__setattr__(self, "allowed_extensions", tuple(self.allowed_extensions))
        object.__setattr__(
            self,
            "normalized_cpu_flags",
            tuple(sorted(self.normalized_cpu_flags, key=lambda flag: flag.name)),
        )
        object.__setattr__(
            self,
            "implementation_plans",
            tuple(
                sorted(
                    self.implementation_plans,
                    key=lambda implementation: implementation.key,
                )
            ),
        )


def plan_selection(
    reference_catalog: ReferenceValidatedCatalog,
    request: SelectionRequest,
) -> Result[SelectionPlan]:
    catalog = reference_catalog.catalog
    diagnostics: list[Diagnostic] = []

    flag_catalog_result = build_flag_catalog(catalog)
    diagnostics.extend(flag_catalog_result.diagnostics)
    if not flag_catalog_result.is_ok:
        return Result.failure(diagnostics)
    flag_catalog = flag_catalog_result.unwrap()

    cpu_flags = flag_catalog.normalize_all(request.cpu_flags)
    diagnostics.extend(cpu_flags.diagnostics)
    normalized_cpu_flags = cpu_flags.unwrap() if cpu_flags.is_ok else ()

    allowed_extensions = _allowed_extensions(
        catalog,
        request,
        flag_catalog,
        normalized_cpu_flags,
    )
    diagnostics.extend(allowed_extensions.diagnostics)

    variants_result = expand_variants(reference_catalog)
    diagnostics.extend(variants_result.diagnostics)
    if not variants_result.is_ok:
        return Result.failure(diagnostics)

    variants = _filter_variants(
        variants_result.unwrap().variants,
        request,
        catalog,
        diagnostics,
    )
    implementation_plans: list[VariantImplementationPlan] = []
    if allowed_extensions.is_ok:
        for variant in variants:
            planned = _implementation_plans_for_variant(
                variant,
                catalog,
                flag_catalog,
                frozenset(allowed_extensions.unwrap()),
            )
            diagnostics.extend(planned.diagnostics)
            if planned.is_ok:
                implementation_plans.extend(planned.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        SelectionPlan(
            request=request,
            variants=variants,
            allowed_extensions=allowed_extensions.unwrap(),
            normalized_cpu_flags=normalized_cpu_flags,
            implementation_plans=tuple(implementation_plans),
        ),
        diagnostics=ordered,
    )


def _allowed_extensions(
    catalog: Catalog,
    request: SelectionRequest,
    flag_catalog: FlagCatalog,
    normalized_cpu_flags: tuple[FeatureFlag, ...],
) -> Result[tuple[str, ...]]:
    diagnostics: list[Diagnostic] = []
    allowed: set[str] = set()
    if request.extension_names:
        for extension_name in request.extension_names:
            if extension_name not in catalog.extensions_by_name:
                diagnostics.append(
                    Diagnostic.error(
                        "TSL-SELECT-UNKNOWN-EXTENSION",
                        f"selection request references unknown extension "
                        f"{extension_name!r}",
                    )
                )
            else:
                allowed.add(extension_name)
    else:
        cpu_flag_names = frozenset(flag.name for flag in normalized_cpu_flags)
        for extension in catalog.extensions:
            if extension.fields.get("autodetect") is not True:
                continue
            required_flags_value = extension.fields.get("lscpu_flags")
            required_flags = _string_tuple(required_flags_value)
            normalized = flag_catalog.normalize_all(
                required_flags,
                location=extension.source_span.location,
            )
            diagnostics.extend(normalized.diagnostics)
            if normalized.is_ok and _flag_names(normalized.unwrap()) <= cpu_flag_names:
                allowed.add(extension.name)

    if request.include_support_extensions:
        for extension_name in request.forced_support_extensions:
            if extension_name in catalog.extensions_by_name:
                allowed.add(extension_name)
            else:
                diagnostics.append(
                    Diagnostic.error(
                        "TSL-SELECT-UNKNOWN-EXTENSION",
                        f"forced support extension {extension_name!r} is not defined",
                    )
                )

    ordered = _catalog_extension_order(catalog, allowed)
    if has_errors(diagnostics):
        return Result.failure(diagnostics)
    return Result.ok(ordered, diagnostics=diagnostics)


def _filter_variants(
    variants: tuple[PrimitiveVariant, ...],
    request: SelectionRequest,
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> tuple[PrimitiveVariant, ...]:
    requested_primitives = frozenset(request.primitive_names)
    requested_templates = frozenset(request.template_names)
    for primitive_name in sorted(requested_primitives):
        if not catalog.primitive_declarations(primitive_name):
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SELECT-UNKNOWN-PRIMITIVE",
                    f"selection request references unknown primitive {primitive_name!r}",
                )
            )
    for template_name in sorted(requested_templates):
        if template_name not in catalog.templates_by_name:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-SELECT-UNKNOWN-TEMPLATE",
                    f"selection request references unknown template {template_name!r}",
                )
            )

    return tuple(
        variant
        for variant in variants
        if (not requested_primitives or variant.primitive_name in requested_primitives)
        and (not requested_templates or variant.template_name in requested_templates)
    )


def _implementation_plans_for_variant(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    allowed_extensions: frozenset[str],
) -> Result[tuple[VariantImplementationPlan, ...]]:
    impls = _as_map(variant.source.declaration.fields.get("impls"))
    if impls is None:
        return Result.ok(())

    diagnostics: list[Diagnostic] = []
    plans: list[VariantImplementationPlan] = []
    for extension_selector_text, extension_value in impls.items():
        extension_names = _selector_items(extension_selector_text)
        if not (set(extension_names) & allowed_extensions):
            continue
        type_map = _as_map(extension_value)
        if type_map is None:
            diagnostics.append(
                _shape_diagnostic(
                    variant,
                    "implementation extension selector",
                    extension_selector_text,
                )
            )
            continue
        extension_selector = SelectorPlan(
            kind="extension",
            raw=extension_selector_text,
            names=extension_names,
        )
        for type_selector_text, implementation_value in type_map.items():
            implementation_map = _as_map(implementation_value)
            if implementation_map is None:
                diagnostics.append(
                    _shape_diagnostic(
                        variant,
                        "implementation type selector",
                        type_selector_text,
                    )
                )
                continue
            requirements = _requirements_for_implementation(
                variant,
                catalog,
                flag_catalog,
                extension_names,
                _selector_items(type_selector_text),
                implementation_map.get("requires"),
            )
            diagnostics.extend(requirements.diagnostics)
            if not requirements.is_ok:
                continue
            plans.append(
                VariantImplementationPlan(
                    variant_id=variant.variant_id,
                    extension_selector=extension_selector,
                    type_selector=SelectorPlan(
                        kind="type_group",
                        raw=type_selector_text,
                        names=_selector_items(type_selector_text),
                    ),
                    requirements=requirements.unwrap(),
                )
            )

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(plans), diagnostics=ordered)


def _requirements_for_implementation(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    extension_context: tuple[str, ...],
    type_context: tuple[str, ...],
    requires_value: CatalogValue | None,
) -> Result[tuple[RequirementConstraint, ...]]:
    if requires_value is None:
        return Result.ok(())
    if isinstance(requires_value, tuple):
        return _flags_requirement(
            variant,
            flag_catalog,
            requires_value,
            extension_context=extension_context,
            type_context=type_context,
            selector_path=("requires",),
        )

    requires = _as_map(requires_value)
    if requires is None:
        return Result.failure(
            (
                _shape_diagnostic(variant, "requires", "requires"),
            )
        )

    if len(extension_context) > 1:
        return _extension_keyed_requirements(
            variant,
            catalog,
            flag_catalog,
            requires,
            extension_context=extension_context,
            type_context=type_context,
        )
    return _mixed_requirements(
        variant,
        catalog,
        flag_catalog,
        requires,
        extension_context=extension_context,
        type_context=type_context,
    )


def _extension_keyed_requirements(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    requires: CatalogMap,
    *,
    extension_context: tuple[str, ...],
    type_context: tuple[str, ...],
) -> Result[tuple[RequirementConstraint, ...]]:
    diagnostics: list[Diagnostic] = []
    constraints: list[RequirementConstraint] = []
    known_key_seen = any(
        _selector_contains(selector, catalog.extensions_by_name)
        for selector in requires
    )
    for extension_selector, value in requires.items():
        if not _selector_contains(extension_selector, catalog.extensions_by_name):
            if not known_key_seen:
                diagnostics.append(
                    _unknown_selector_diagnostic(
                        variant,
                        code="TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
                        selector_kind="extension",
                        selector=extension_selector,
                    )
                )
            continue
        diagnostics.extend(
            _unknown_selector_items(
                variant,
                extension_selector,
                catalog.extensions_by_name,
                code="TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
                selector_kind="extension",
            )
        )
        extension_names = tuple(
            item
            for item in _selector_items(extension_selector)
            if item in catalog.extensions_by_name
        )
        nested = _as_map(value)
        if nested is None:
            flags = _flags_requirement(
                variant,
                flag_catalog,
                value,
                extension_context=extension_names,
                type_context=type_context,
                selector_path=("requires", extension_selector),
            )
            diagnostics.extend(flags.diagnostics)
            if flags.is_ok:
                constraints.extend(flags.unwrap())
            continue
        nested_constraints = _type_keyed_requirements(
            variant,
            catalog,
            flag_catalog,
            nested,
            extension_context=extension_names,
            type_context=type_context,
        )
        diagnostics.extend(nested_constraints.diagnostics)
        if nested_constraints.is_ok:
            constraints.extend(nested_constraints.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(constraints), diagnostics=ordered)


def _mixed_requirements(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    requires: CatalogMap,
    *,
    extension_context: tuple[str, ...],
    type_context: tuple[str, ...],
) -> Result[tuple[RequirementConstraint, ...]]:
    diagnostics: list[Diagnostic] = []
    constraints: list[RequirementConstraint] = []
    for selector, value in requires.items():
        if _selector_contains(selector, catalog.extensions_by_name):
            diagnostics.extend(
                _unknown_selector_items(
                    variant,
                    selector,
                    catalog.extensions_by_name,
                    code="TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
                    selector_kind="extension",
                )
            )
            extension_names = tuple(
                item
                for item in _selector_items(selector)
                if item in catalog.extensions_by_name
            )
            nested = _as_map(value)
            if nested is None:
                flags = _flags_requirement(
                    variant,
                    flag_catalog,
                    value,
                    extension_context=extension_names,
                    type_context=type_context,
                    selector_path=("requires", selector),
                )
                diagnostics.extend(flags.diagnostics)
                if flags.is_ok:
                    constraints.extend(flags.unwrap())
            else:
                nested_constraints = _type_keyed_requirements(
                    variant,
                    catalog,
                    flag_catalog,
                    nested,
                    extension_context=extension_names,
                    type_context=type_context,
                )
                diagnostics.extend(nested_constraints.diagnostics)
                if nested_constraints.is_ok:
                    constraints.extend(nested_constraints.unwrap())
            continue
        if _selector_contains(selector, catalog.type_groups_by_name):
            type_constraints = _type_selector_requirement(
                variant,
                catalog,
                flag_catalog,
                selector,
                value,
                extension_context=extension_context,
                fallback_type_context=type_context,
            )
            diagnostics.extend(type_constraints.diagnostics)
            if type_constraints.is_ok:
                constraints.extend(type_constraints.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(constraints), diagnostics=ordered)


def _type_keyed_requirements(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    requires: CatalogMap,
    *,
    extension_context: tuple[str, ...],
    type_context: tuple[str, ...],
) -> Result[tuple[RequirementConstraint, ...]]:
    diagnostics: list[Diagnostic] = []
    constraints: list[RequirementConstraint] = []
    for selector, value in requires.items():
        if not _selector_contains(selector, catalog.type_groups_by_name):
            continue
        type_constraints = _type_selector_requirement(
            variant,
            catalog,
            flag_catalog,
            selector,
            value,
            extension_context=extension_context,
            fallback_type_context=type_context,
        )
        diagnostics.extend(type_constraints.diagnostics)
        if type_constraints.is_ok:
            constraints.extend(type_constraints.unwrap())
    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(constraints), diagnostics=ordered)


def _type_selector_requirement(
    variant: PrimitiveVariant,
    catalog: Catalog,
    flag_catalog: FlagCatalog,
    selector: str,
    value: CatalogValue,
    *,
    extension_context: tuple[str, ...],
    fallback_type_context: tuple[str, ...],
) -> Result[tuple[RequirementConstraint, ...]]:
    diagnostics = list(
        _unknown_selector_items(
            variant,
            selector,
            catalog.type_groups_by_name,
            code="TSL-PLAN-REQUIRES-UNKNOWN-TYPE-SELECTOR",
            selector_kind="type group",
        )
    )
    type_names = tuple(
        item for item in _selector_items(selector) if item in catalog.type_groups_by_name
    )
    flags = _flags_requirement(
        variant,
        flag_catalog,
        value,
        extension_context=extension_context,
        type_context=type_names or fallback_type_context,
        selector_path=("requires", selector),
    )
    diagnostics.extend(flags.diagnostics)
    if has_errors(diagnostics):
        return Result.failure(diagnostics)
    return flags


def _flags_requirement(
    variant: PrimitiveVariant,
    flag_catalog: FlagCatalog,
    value: CatalogValue,
    *,
    extension_context: tuple[str, ...],
    type_context: tuple[str, ...],
    selector_path: tuple[str, ...],
) -> Result[tuple[RequirementConstraint, ...]]:
    if not isinstance(value, tuple):
        return Result.failure((_shape_diagnostic(variant, "requires flags", "requires"),))

    flag_names: list[str] = []
    diagnostics: list[Diagnostic] = []
    for item in value:
        if isinstance(item, str):
            flag_names.append(item)
        else:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-PLAN-REQUIRES-SHAPE",
                    "requires flag lists must contain only string feature flags",
                    location=variant.source.declaration.source_span.location,
                )
            )
    normalized = flag_catalog.normalize_all(
        flag_names,
        location=variant.source.declaration.source_span.location,
    )
    diagnostics.extend(normalized.diagnostics)
    if has_errors(diagnostics):
        return Result.failure(diagnostics)
    return Result.ok(
        (
            RequirementConstraint(
                extension_names=extension_context,
                type_group_names=type_context,
                required_flags=normalized.unwrap(),
                selector_path=selector_path,
            ),
        ),
        diagnostics=diagnostics,
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


def _selector_contains(selector: str, known_names: Container[str]) -> bool:
    return any(item in known_names for item in _selector_items(selector))


def _unknown_selector_items(
    variant: PrimitiveVariant,
    selector: str,
    known_names: Container[str],
    *,
    code: str,
    selector_kind: str,
) -> tuple[Diagnostic, ...]:
    return tuple(
        _unknown_selector_diagnostic(
            variant,
            code=code,
            selector_kind=selector_kind,
            selector=item,
        )
        for item in _selector_items(selector)
        if item not in known_names
    )


def _unknown_selector_diagnostic(
    variant: PrimitiveVariant,
    *,
    code: str,
    selector_kind: str,
    selector: str,
) -> Diagnostic:
    return Diagnostic.error(
        code,
        f"primitive {variant.primitive_name!r} has unknown {selector_kind} "
        f"selector {selector!r} in requires",
        location=variant.source.declaration.source_span.location,
    )


def _shape_diagnostic(
    variant: PrimitiveVariant,
    context: str,
    selector: str,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-PLAN-IMPLEMENTATION-SHAPE",
        f"primitive {variant.primitive_name!r} has unsupported {context} "
        f"shape for selector {selector!r}",
        location=variant.source.declaration.source_span.location,
    )


def _catalog_extension_order(catalog: Catalog, extension_names: set[str]) -> tuple[str, ...]:
    return tuple(
        extension.name for extension in catalog.extensions if extension.name in extension_names
    )


def _flag_names(flags: tuple[FeatureFlag, ...]) -> frozenset[str]:
    return frozenset(flag.name for flag in flags)


def _string_tuple(value: CatalogValue | None) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return value
    return None
