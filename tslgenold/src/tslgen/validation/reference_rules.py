from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.primitives import PrimitiveDeclaration
from tslgen.domain.values import CatalogMap, CatalogValue
from tslgen.validation.catalog_validator import ValidatedCatalog
from tslgen.validation.extension_rules import validate_extension_references


@dataclass(frozen=True, slots=True)
class ReferenceValidatedCatalog:
    catalog: Catalog
    validated_catalog: ValidatedCatalog | None = None


def validate_references(
    target: Catalog | ValidatedCatalog,
) -> Result[ReferenceValidatedCatalog]:
    validated_catalog: ValidatedCatalog | None
    if isinstance(target, ValidatedCatalog):
        catalog = target.catalog
        validated_catalog = target
    else:
        catalog = target
        validated_catalog = None

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_validate_type_group_members(catalog))
    diagnostics.extend(_validate_lane_set_types(catalog))
    diagnostics.extend(validate_extension_references(catalog))
    diagnostics.extend(_validate_primitive_references(catalog))
    if validated_catalog is not None:
        diagnostics.extend(_validate_validated_template_references(validated_catalog))

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        ReferenceValidatedCatalog(
            catalog=catalog,
            validated_catalog=validated_catalog,
        ),
        diagnostics=ordered,
    )


def _validate_type_group_members(catalog: Catalog) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for type_group in catalog.type_groups:
        for reference in type_group.members:
            if reference not in catalog.type_groups_by_name:
                diagnostics.append(
                    _unknown_reference_diagnostic(
                        code="TSL-REF-UNKNOWN-TYPE-GROUP",
                        owner_kind="type group",
                        owner_name=type_group.name,
                        field_name="types",
                        target_kind="type group",
                        reference=reference,
                        location=type_group.source_span.location,
                    )
                )
    return tuple(diagnostics)


def _validate_lane_set_types(catalog: Catalog) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for lane_set in catalog.lane_sets:
        for reference in lane_set.type_names:
            if reference not in catalog.type_groups_by_name:
                diagnostics.append(
                    _unknown_reference_diagnostic(
                        code="TSL-REF-UNKNOWN-TYPE-GROUP",
                        owner_kind="lane set",
                        owner_name=lane_set.name,
                        field_name="types",
                        target_kind="type group",
                        reference=reference,
                        location=lane_set.source_span.location,
                    )
                )
    return tuple(diagnostics)


def _validate_primitive_references(catalog: Catalog) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for primitive in catalog.primitives:
        diagnostics.extend(_validate_primitive_tests(primitive, catalog))
        diagnostics.extend(_validate_primitive_impls(primitive, catalog))
    return tuple(diagnostics)


def _validate_primitive_tests(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    tests = primitive.fields.get("tests")
    if not isinstance(tests, tuple):
        return ()

    diagnostics: list[Diagnostic] = []
    for test_value in tests:
        test_map = _as_map(test_value)
        if test_map is None:
            continue
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "type",
                primitive,
                catalog.type_groups_by_name,
                code="TSL-REF-UNKNOWN-TYPE-GROUP",
                target_kind="type group",
            )
        )
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "to_type",
                primitive,
                catalog.type_groups_by_name,
                code="TSL-REF-UNKNOWN-TYPE-GROUP",
                target_kind="type group",
            )
        )
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "lane_set",
                primitive,
                catalog.lane_sets_by_name,
                code="TSL-REF-UNKNOWN-LANE-SET",
                target_kind="lane set",
            )
        )
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "extension",
                primitive,
                catalog.extensions_by_name,
                code="TSL-REF-UNKNOWN-EXTENSION",
                target_kind="extension",
            )
        )
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "to_extension",
                primitive,
                catalog.extensions_by_name,
                code="TSL-REF-UNKNOWN-EXTENSION",
                target_kind="extension",
            )
        )
        diagnostics.extend(
            _validate_string_field(
                test_map,
                "template",
                primitive,
                catalog.templates_by_name,
                code="TSL-REF-UNKNOWN-TEMPLATE",
                target_kind="template",
            )
        )
    return tuple(diagnostics)


def _validate_primitive_impls(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
) -> tuple[Diagnostic, ...]:
    impls = _as_map(primitive.fields.get("impls"))
    if impls is None:
        return ()

    diagnostics: list[Diagnostic] = []
    for extension_selector, extension_value in impls.items():
        extension_names = _selector_items(extension_selector)
        for extension_name in extension_names:
            if extension_name not in catalog.extensions_by_name:
                diagnostics.append(
                    _primitive_unknown_reference_diagnostic(
                        code="TSL-REF-UNKNOWN-EXTENSION",
                        primitive=primitive,
                        field_name="impls",
                        target_kind="extension",
                        reference=extension_name,
                    )
                )

        type_map = _as_map(extension_value)
        if type_map is None:
            continue
        for type_selector, implementation_value in type_map.items():
            for type_group_name in _selector_items(type_selector):
                if type_group_name not in catalog.type_groups_by_name:
                    diagnostics.append(
                        _primitive_unknown_reference_diagnostic(
                            code="TSL-REF-UNKNOWN-TYPE-GROUP",
                            primitive=primitive,
                            field_name="impls",
                            target_kind="type group",
                            reference=type_group_name,
                        )
                    )

            implementation_map = _as_map(implementation_value)
            if implementation_map is None:
                continue
            requires = _as_map(implementation_map.get("requires"))
            if requires is None:
                continue
            diagnostics.extend(
                _validate_requires_map(
                    primitive,
                    catalog,
                    extension_names,
                    requires,
                )
            )
    return tuple(diagnostics)


def _validate_requires_map(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
    extension_names: tuple[str, ...],
    requires: CatalogMap,
) -> tuple[Diagnostic, ...]:
    if len(extension_names) > 1:
        return _validate_extension_keyed_requires(primitive, catalog, requires)
    return _validate_type_group_keyed_requires(primitive, catalog, requires)


def _validate_extension_keyed_requires(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
    requires: CatalogMap,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for extension_selector, value in requires.items():
        if not _selector_contains(extension_selector, catalog.extensions_by_name):
            continue
        diagnostics.extend(
            _validate_selector_references(
                extension_selector,
                catalog.extensions_by_name,
                code="TSL-REF-UNKNOWN-EXTENSION",
                primitive=primitive,
                field_name="requires",
                target_kind="extension",
            )
        )
        nested_requires = _as_map(value)
        if nested_requires is not None:
            diagnostics.extend(
                _validate_type_group_keyed_requires(
                    primitive,
                    catalog,
                    nested_requires,
                )
            )
    return tuple(diagnostics)


def _validate_type_group_keyed_requires(
    primitive: PrimitiveDeclaration,
    catalog: Catalog,
    requires: CatalogMap,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for type_selector, value in requires.items():
        if _selector_contains(type_selector, catalog.extensions_by_name):
            diagnostics.extend(
                _validate_selector_references(
                    type_selector,
                    catalog.extensions_by_name,
                    code="TSL-REF-UNKNOWN-EXTENSION",
                    primitive=primitive,
                    field_name="requires",
                    target_kind="extension",
                )
            )
            nested_requires = _as_map(value)
            if nested_requires is not None:
                diagnostics.extend(
                    _validate_type_group_keyed_requires(
                        primitive,
                        catalog,
                        nested_requires,
                    )
                )
            continue
        if not _selector_contains(type_selector, catalog.type_groups_by_name):
            continue
        diagnostics.extend(
            _validate_selector_references(
                type_selector,
                catalog.type_groups_by_name,
                code="TSL-REF-UNKNOWN-TYPE-GROUP",
                primitive=primitive,
                field_name="requires",
                target_kind="type group",
            )
        )
    return tuple(diagnostics)


def _validate_validated_template_references(
    validated_catalog: ValidatedCatalog,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    catalog = validated_catalog.catalog
    for primitive in validated_catalog.primitives:
        if primitive.template_name not in catalog.templates_by_name:
            diagnostics.append(
                _primitive_unknown_reference_diagnostic(
                    code="TSL-REF-UNKNOWN-TEMPLATE",
                    primitive=primitive.declaration,
                    field_name="template",
                    target_kind="template",
                    reference=primitive.template_name,
                )
            )
    return tuple(diagnostics)


def _validate_string_field(
    value_map: CatalogMap,
    field_name: str,
    primitive: PrimitiveDeclaration,
    known_names: Container[str],
    *,
    code: str,
    target_kind: str,
) -> tuple[Diagnostic, ...]:
    reference = value_map.get(field_name)
    if not isinstance(reference, str) or reference in known_names:
        return ()
    return (
        _primitive_unknown_reference_diagnostic(
            code=code,
            primitive=primitive,
            field_name=field_name,
            target_kind=target_kind,
            reference=reference,
        ),
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


def _selector_contains(selector: str, known_names: Container[str]) -> bool:
    return any(item in known_names for item in _selector_items(selector))


def _validate_selector_references(
    selector: str,
    known_names: Container[str],
    *,
    code: str,
    primitive: PrimitiveDeclaration,
    field_name: str,
    target_kind: str,
) -> tuple[Diagnostic, ...]:
    return tuple(
        _primitive_unknown_reference_diagnostic(
            code=code,
            primitive=primitive,
            field_name=field_name,
            target_kind=target_kind,
            reference=item,
        )
        for item in _selector_items(selector)
        if item not in known_names
    )


def _selector_base_name(selector_item: str) -> str:
    if "<" in selector_item and selector_item.endswith(">"):
        return selector_item.split("<", 1)[0]
    return selector_item


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return value
    return None


def _primitive_unknown_reference_diagnostic(
    *,
    code: str,
    primitive: PrimitiveDeclaration,
    field_name: str,
    target_kind: str,
    reference: str,
) -> Diagnostic:
    return _unknown_reference_diagnostic(
        code=code,
        owner_kind="primitive",
        owner_name=primitive.name,
        field_name=field_name,
        target_kind=target_kind,
        reference=reference,
        location=primitive.source_span.location,
    )


def _unknown_reference_diagnostic(
    *,
    code: str,
    owner_kind: str,
    owner_name: str,
    field_name: str,
    target_kind: str,
    reference: str,
    location: SourceLocation,
) -> Diagnostic:
    return Diagnostic.error(
        code,
        f"{owner_kind} {owner_name!r} field {field_name!r} references unknown "
        f"{target_kind} {reference!r}",
        location=location,
    )
