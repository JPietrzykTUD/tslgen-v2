"""Authoring-only projections for closed primitive semantic fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tslc.catalog.arithmetic import (
    arithmetic_guarantee_values,
    arithmetic_operand_role_values,
    arithmetic_operation_values,
)
from tslc.catalog.conversion import (
    conversion_kind_values,
    lane_count_relation_values,
    numeric_conversion_mode_values,
)
from tslc.catalog.memory import (
    memory_access_values,
    memory_addressing_values,
    memory_indexed_lane_extent_values,
)
from tslc.catalog.preconditions import precondition_values
from tslc.catalog.scalar_types import KNOWN_SCALAR_TYPE_TAGS
from tslc.catalog.semantics import operand_role_values, primitive_operation_values
from tslc.catalog.shift import shift_count_rule_values, shift_lane_rule_values
from tslc.syntax.access import child
from tslc.syntax.ast import (
    ParsedPrimitiveDeclaration,
    ParsedTslField,
    ParsedTslListValue,
    ParsedTslScalarValue,
)

if TYPE_CHECKING:
    from tslc.catalog_index_model import SymbolKind


SemanticTokenKind = Literal[
    "function",
    "class",
    "type",
    "keyword",
    "property",
    "parameter",
    "typeParameter",
    "enumMember",
    "namespace",
]
SemanticFieldShape = Literal[
    "enum-scalar",
    "enum-list",
    "parameter-bindings",
    "type-list",
]
BindingSymbolKind = Literal["arithmetic-operand", "semantic-operand"]
DynamicCompletionSource = Literal["primitive-parameters"]
CompletionValues = Callable[[], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class SemanticFieldProjection:
    """Presentation metadata for one parsed primitive semantic field."""

    path: tuple[str, ...]
    value_shape: SemanticFieldShape
    symbol_kind: SymbolKind | None
    semantic_token_kind: SemanticTokenKind
    completion_values: CompletionValues
    field_detail: str
    value_detail: str
    binding_symbol_kind: BindingSymbolKind | None = None
    dynamic_value_source: DynamicCompletionSource | None = None
    child_field_detail: str | None = None

    def __post_init__(self) -> None:
        if len(self.path) < 2 or self.path[0] != "primitive":
            raise ValueError("semantic authoring paths must start below 'primitive'")
        if not self.field_detail or not self.value_detail:
            raise ValueError("semantic authoring details must not be empty")
        if self.value_shape == "parameter-bindings":
            if (
                self.symbol_kind is None
                or self.binding_symbol_kind is None
                or self.dynamic_value_source != "primitive-parameters"
                or not self.child_field_detail
            ):
                raise ValueError(
                    "parameter-binding projections require key/value symbol kinds "
                    "and primitive-parameter completion metadata"
                )
        elif (
            self.binding_symbol_kind is not None
            or self.dynamic_value_source is not None
            or self.child_field_detail is not None
        ):
            raise ValueError(
                "only parameter-binding projections may declare binding metadata"
            )
        elif self.value_shape != "type-list" and self.symbol_kind is None:
            raise ValueError("semantic enum projections require a symbol kind")


def _scalar_type_values() -> tuple[str, ...]:
    return tuple(sorted(KNOWN_SCALAR_TYPE_TAGS))


SEMANTIC_FIELD_PROJECTIONS: tuple[SemanticFieldProjection, ...] = (
    SemanticFieldProjection(
        ("primitive", "operation"),
        "enum-scalar",
        "primitive-operation",
        "enumMember",
        primitive_operation_values,
        "primitive field",
        "primitive operation",
    ),
    SemanticFieldProjection(
        ("primitive", "operand_roles"),
        "parameter-bindings",
        "operand-role",
        "enumMember",
        operand_role_values,
        "primitive field",
        "primitive parameter",
        binding_symbol_kind="semantic-operand",
        dynamic_value_source="primitive-parameters",
        child_field_detail="primitive operand role",
    ),
    SemanticFieldProjection(
        ("primitive", "preconditions"),
        "enum-list",
        "precondition",
        "enumMember",
        precondition_values,
        "primitive field",
        "primitive precondition",
    ),
    SemanticFieldProjection(
        ("primitive", "arithmetic", "operations"),
        "enum-list",
        "arithmetic-operation",
        "enumMember",
        arithmetic_operation_values,
        "arithmetic contract field",
        "arithmetic operation",
    ),
    SemanticFieldProjection(
        ("primitive", "arithmetic", "operand_roles"),
        "parameter-bindings",
        "arithmetic-role",
        "enumMember",
        arithmetic_operand_role_values,
        "arithmetic contract field",
        "primitive parameter",
        binding_symbol_kind="arithmetic-operand",
        dynamic_value_source="primitive-parameters",
        child_field_detail="arithmetic operand role",
    ),
    SemanticFieldProjection(
        ("primitive", "arithmetic", "guarantees"),
        "enum-list",
        "arithmetic-guarantee",
        "enumMember",
        arithmetic_guarantee_values,
        "arithmetic contract field",
        "arithmetic guarantee",
    ),
    SemanticFieldProjection(
        ("primitive", "memory", "access"),
        "enum-scalar",
        "memory-access",
        "enumMember",
        memory_access_values,
        "memory contract field",
        "memory access",
    ),
    SemanticFieldProjection(
        ("primitive", "memory", "addressing"),
        "enum-scalar",
        "memory-addressing",
        "enumMember",
        memory_addressing_values,
        "memory contract field",
        "memory addressing",
    ),
    SemanticFieldProjection(
        ("primitive", "memory", "indexed_lanes"),
        "enum-scalar",
        "memory-indexed-lane-extent",
        "enumMember",
        memory_indexed_lane_extent_values,
        "memory contract field",
        "indexed memory lane extent",
    ),
    SemanticFieldProjection(
        ("primitive", "conversion", "kind"),
        "enum-scalar",
        "conversion-kind",
        "enumMember",
        conversion_kind_values,
        "conversion contract field",
        "conversion kind",
    ),
    SemanticFieldProjection(
        ("primitive", "conversion", "lane_count"),
        "enum-scalar",
        "lane-count-relation",
        "enumMember",
        lane_count_relation_values,
        "conversion contract field",
        "conversion lane-count relation",
    ),
    SemanticFieldProjection(
        ("primitive", "conversion", "numeric_mode"),
        "enum-scalar",
        "numeric-conversion-mode",
        "enumMember",
        numeric_conversion_mode_values,
        "conversion contract field",
        "numeric conversion mode",
    ),
    SemanticFieldProjection(
        ("primitive", "shift", "count_rule"),
        "enum-scalar",
        "shift-count-rule",
        "enumMember",
        shift_count_rule_values,
        "shift contract field",
        "shift count rule",
    ),
    SemanticFieldProjection(
        ("primitive", "shift", "lane_rule"),
        "enum-scalar",
        "shift-lane-rule",
        "enumMember",
        shift_lane_rule_values,
        "shift contract field",
        "shift lane rule",
    ),
    SemanticFieldProjection(
        ("primitive", "shift", "scalar_count_types"),
        "type-list",
        None,
        "type",
        _scalar_type_values,
        "shift contract field",
        "shift scalar count type",
    ),
)


def semantic_field_projections() -> tuple[SemanticFieldProjection, ...]:
    """Return the active immutable projection inventory."""

    return SEMANTIC_FIELD_PROJECTIONS


def semantic_field_projection(
    path: tuple[str, ...],
) -> SemanticFieldProjection | None:
    return next(
        (item for item in semantic_field_projections() if item.path == path),
        None,
    )


def semantic_child_fields(path: tuple[str, ...]) -> tuple[str, ...]:
    """Return closed field names immediately below one semantic source path."""

    exact = semantic_field_projection(path)
    if exact is not None and exact.value_shape == "parameter-bindings":
        return exact.completion_values()
    return tuple(
        sorted(
            {
                item.path[len(path)]
                for item in semantic_field_projections()
                if len(item.path) > len(path) and item.path[: len(path)] == path
            }
        )
    )


def semantic_child_detail(path: tuple[str, ...]) -> str | None:
    exact = semantic_field_projection(path)
    if exact is not None and exact.value_shape == "parameter-bindings":
        return exact.child_field_detail
    details = {
        item.field_detail
        for item in semantic_field_projections()
        if len(item.path) == len(path) + 1 and item.path[: len(path)] == path
    }
    return next(iter(details)) if len(details) == 1 else None


def semantic_value_projection(
    block_path: tuple[str, ...],
    field_name: str,
) -> SemanticFieldProjection | None:
    direct = semantic_field_projection((*block_path, field_name))
    if direct is not None:
        return direct
    container = semantic_field_projection(block_path)
    if (
        container is not None
        and container.value_shape == "parameter-bindings"
        and field_name in container.completion_values()
    ):
        return container
    return None


def semantic_projection_fields(
    primitive: ParsedPrimitiveDeclaration,
) -> tuple[tuple[SemanticFieldProjection, ParsedTslField], ...]:
    """Pair active descriptors with matching parsed fields in source order."""

    projected: list[tuple[SemanticFieldProjection, ParsedTslField]] = []
    for descriptor in semantic_field_projections():
        fields = tuple(
            parsed.field for parsed in primitive.fields_by_name(descriptor.path[1])
        )
        for member_name in descriptor.path[2:]:
            fields = tuple(
                member
                for field in fields
                if (member := child(field, member_name)) is not None
            )
        projected.extend((descriptor, field) for field in fields)
    return tuple(projected)


def semantic_scalar_values(
    descriptor: SemanticFieldProjection,
    field: ParsedTslField,
) -> tuple[ParsedTslScalarValue, ...]:
    if descriptor.value_shape == "enum-scalar":
        return (field.value,) if isinstance(field.value, ParsedTslScalarValue) else ()
    if descriptor.value_shape in {"enum-list", "type-list"} and isinstance(
        field.value, ParsedTslListValue
    ):
        return tuple(
            item for item in field.value.items if isinstance(item, ParsedTslScalarValue)
        )
    return ()


__all__ = (
    "BindingSymbolKind",
    "DynamicCompletionSource",
    "SEMANTIC_FIELD_PROJECTIONS",
    "SemanticFieldProjection",
    "SemanticFieldShape",
    "SemanticTokenKind",
    "semantic_child_detail",
    "semantic_child_fields",
    "semantic_field_projection",
    "semantic_field_projections",
    "semantic_projection_fields",
    "semantic_scalar_values",
    "semantic_value_projection",
)
