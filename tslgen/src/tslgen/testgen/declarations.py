from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from tslgen.core.diagnostics import Diagnostic, SourceLocation, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.ordering import stable_sort_key
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.primitives import PrimitiveDeclaration
from tslgen.domain.values import CatalogMap, CatalogValue


_KNOWN_TEST_FIELDS = frozenset(
    {
        "attrs",
        "case",
        "extension",
        "lane_set",
        "lanes",
        "test_name",
        "to_extension",
        "to_type",
        "type",
    }
)


@dataclass(frozen=True, slots=True)
class ProductionTestCase:
    inputs: tuple[CatalogValue, ...]
    expected: CatalogValue
    fields: CatalogMap = field(default_factory=FrozenMap.empty)

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))


@dataclass(frozen=True, slots=True)
class ProductionTestDeclaration:
    primitive_name: str
    test_name: str
    type_tag: str
    case: ProductionTestCase
    lane_set_name: str | None = None
    lanes: int | None = None
    extension_name: str | None = None
    to_type_tag: str | None = None
    to_extension_name: str | None = None
    attributes: CatalogMap = field(default_factory=FrozenMap.empty)
    extra_fields: CatalogMap = field(default_factory=FrozenMap.empty)
    source_location: SourceLocation | None = None

    def __post_init__(self) -> None:
        if not self.primitive_name:
            raise ValueError("test declaration primitive name must be non-empty")
        if not self.test_name:
            raise ValueError("test declaration name must be non-empty")
        if not self.type_tag:
            raise ValueError("test declaration type tag must be non-empty")
        if self.lanes is not None and self.lanes < 1:
            raise ValueError("test declaration lanes must be positive")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.primitive_name,
            self.test_name,
            self.extension_name or "",
            self.type_tag,
            self.to_type_tag or "",
            self.lane_set_name or "",
            self.lanes or 0,
            tuple(
                (key, stable_sort_key(value))
                for key, value in self.attributes.items()
            ),
            tuple(
                (key, stable_sort_key(value))
                for key, value in self.extra_fields.items()
            ),
        )


def normalize_test_declarations(
    catalog: Catalog,
) -> Result[tuple[ProductionTestDeclaration, ...]]:
    diagnostics: list[Diagnostic] = []
    declarations: list[ProductionTestDeclaration] = []
    known_type_tags = _known_type_tags(catalog)

    for primitive in catalog.primitives:
        tests_value = primitive.fields.get("tests")
        if tests_value is None:
            continue
        if not isinstance(tests_value, tuple):
            diagnostics.append(
                _shape_diagnostic(primitive, "'tests' must be a list of maps")
            )
            continue

        for test_value in tests_value:
            declaration = _normalize_test_value(
                primitive,
                test_value,
                catalog,
                known_type_tags,
            )
            diagnostics.extend(declaration.diagnostics)
            if declaration.is_ok:
                declarations.append(declaration.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if any(diagnostic.is_error for diagnostic in ordered):
        return Result.failure(ordered)
    return Result.ok(tuple(sorted(declarations, key=lambda item: item.key)), ordered)


def _normalize_test_value(
    primitive: PrimitiveDeclaration,
    test_value: CatalogValue,
    catalog: Catalog,
    known_type_tags: frozenset[str],
) -> Result[ProductionTestDeclaration]:
    diagnostics: list[Diagnostic] = []
    test_map = _as_map(test_value)
    if test_map is None:
        return Result.failure(
            (_shape_diagnostic(primitive, "test entries must be maps"),)
        )

    name = _required_string(primitive, test_map, "test_name", diagnostics)
    type_tag = _required_string(primitive, test_map, "type", diagnostics)
    case = _test_case(primitive, test_map.get("case"))
    diagnostics.extend(case.diagnostics)

    extension_name = _optional_string(primitive, test_map, "extension", diagnostics)
    to_type_tag = _optional_string(primitive, test_map, "to_type", diagnostics)
    to_extension_name = _optional_string(
        primitive,
        test_map,
        "to_extension",
        diagnostics,
    )
    lane_set_name = _optional_string(primitive, test_map, "lane_set", diagnostics)
    lanes = _optional_positive_int(primitive, test_map, "lanes", diagnostics)
    attributes = _attributes(primitive, test_map.get("attrs"))
    diagnostics.extend(attributes.diagnostics)

    if type_tag is not None and type_tag not in known_type_tags:
        diagnostics.append(
            _reference_diagnostic(
                primitive,
                f"test type {type_tag!r} is not a known concrete type tag",
            )
        )
    if to_type_tag is not None and to_type_tag not in known_type_tags:
        diagnostics.append(
            _reference_diagnostic(
                primitive,
                f"test to_type {to_type_tag!r} is not a known concrete type tag",
            )
        )
    if lane_set_name is not None and lane_set_name not in catalog.lane_sets_by_name:
        diagnostics.append(
            _reference_diagnostic(
                primitive,
                f"test lane_set {lane_set_name!r} is not defined",
            )
        )
    if (
        extension_name is not None
        and extension_name not in catalog.extensions_by_name
    ):
        diagnostics.append(
            _reference_diagnostic(
                primitive,
                f"test extension {extension_name!r} is not defined",
            )
        )
    if (
        to_extension_name is not None
        and to_extension_name not in catalog.extensions_by_name
    ):
        diagnostics.append(
            _reference_diagnostic(
                primitive,
                f"test to_extension {to_extension_name!r} is not defined",
            )
        )

    ordered = sort_diagnostics(diagnostics)
    if any(diagnostic.is_error for diagnostic in ordered):
        return Result.failure(ordered)

    if name is None or type_tag is None or not case.is_ok or not attributes.is_ok:
        return Result.failure(ordered)

    return Result.ok(
        ProductionTestDeclaration(
            primitive_name=primitive.name,
            test_name=name,
            type_tag=type_tag,
            case=case.unwrap(),
            lane_set_name=lane_set_name,
            lanes=lanes,
            extension_name=extension_name,
            to_type_tag=to_type_tag,
            to_extension_name=to_extension_name,
            attributes=attributes.unwrap(),
            extra_fields=FrozenMap(
                (key, value)
                for key, value in test_map.items()
                if key not in _KNOWN_TEST_FIELDS
            ),
            source_location=primitive.source_span.location,
        ),
        ordered,
    )


def _test_case(
    primitive: PrimitiveDeclaration,
    value: CatalogValue | None,
) -> Result[ProductionTestCase]:
    case_map = _as_map(value)
    if case_map is None:
        return Result.failure(
            (_missing_diagnostic(primitive, "test case must be a map"),)
        )
    diagnostics: list[Diagnostic] = []
    inputs_value = case_map.get("inputs")
    if not isinstance(inputs_value, tuple):
        diagnostics.append(
            _shape_diagnostic(primitive, "test case inputs must be a list")
        )
    if "expected" not in case_map:
        diagnostics.append(
            _missing_diagnostic(primitive, "test case is missing 'expected'")
        )

    ordered = sort_diagnostics(diagnostics)
    if any(diagnostic.is_error for diagnostic in ordered):
        return Result.failure(ordered)

    return Result.ok(
        ProductionTestCase(
            inputs=cast(tuple[CatalogValue, ...], inputs_value),
            expected=case_map["expected"],
            fields=case_map,
        ),
        ordered,
    )


def _attributes(
    primitive: PrimitiveDeclaration,
    value: CatalogValue | None,
) -> Result[CatalogMap]:
    if value is None:
        return Result.ok(FrozenMap.empty())
    attributes = _as_map(value)
    if attributes is None:
        return Result.failure(
            (_shape_diagnostic(primitive, "test attrs must be a key/value map"),)
        )
    return Result.ok(attributes)


def _required_string(
    primitive: PrimitiveDeclaration,
    test_map: CatalogMap,
    field_name: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    value = test_map.get(field_name)
    if isinstance(value, str) and value:
        return value
    if value is None:
        diagnostics.append(
            _missing_diagnostic(primitive, f"test entry is missing {field_name!r}")
        )
    else:
        diagnostics.append(
            _shape_diagnostic(primitive, f"test field {field_name!r} must be a string")
        )
    return None


def _optional_string(
    primitive: PrimitiveDeclaration,
    test_map: CatalogMap,
    field_name: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    value = test_map.get(field_name)
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    diagnostics.append(
        _shape_diagnostic(primitive, f"test field {field_name!r} must be a string")
    )
    return None


def _optional_positive_int(
    primitive: PrimitiveDeclaration,
    test_map: CatalogMap,
    field_name: str,
    diagnostics: list[Diagnostic],
) -> int | None:
    value = test_map.get(field_name)
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    diagnostics.append(
        _shape_diagnostic(
            primitive,
            f"test field {field_name!r} must be a positive integer",
        )
    )
    return None


def _known_type_tags(catalog: Catalog) -> frozenset[str]:
    known: set[str] = set()

    def add_members(type_group_name: str, stack: tuple[str, ...]) -> None:
        if type_group_name in stack:
            return
        type_group = catalog.type_groups_by_name.get(type_group_name)
        if type_group is None:
            return
        next_stack = (*stack, type_group_name)
        for member in type_group.members:
            if member == type_group_name:
                known.add(member)
            elif member in catalog.type_groups_by_name:
                add_members(member, next_stack)
            else:
                known.add(member)

    for group in catalog.type_groups:
        add_members(group.name, ())
    return frozenset(known)


def _as_map(value: CatalogValue | None) -> CatalogMap | None:
    if isinstance(value, FrozenMap):
        return cast(CatalogMap, value)
    return None


def _shape_diagnostic(primitive: PrimitiveDeclaration, message: str) -> Diagnostic:
    return Diagnostic.error(
        "TSL-TEST-DECL-SHAPE",
        f"primitive {primitive.name!r} has unsupported test declaration shape: "
        f"{message}",
        location=primitive.source_span.location,
    )


def _missing_diagnostic(primitive: PrimitiveDeclaration, message: str) -> Diagnostic:
    return Diagnostic.error(
        "TSL-TEST-DECL-MISSING",
        f"primitive {primitive.name!r} has incomplete test declaration: {message}",
        location=primitive.source_span.location,
    )


def _reference_diagnostic(primitive: PrimitiveDeclaration, message: str) -> Diagnostic:
    return Diagnostic.error(
        "TSL-TEST-DECL-REFERENCE",
        f"primitive {primitive.name!r} has unresolved test declaration reference: "
        f"{message}",
        location=primitive.source_span.location,
    )
