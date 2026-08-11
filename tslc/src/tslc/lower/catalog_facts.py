"""Catalog-wide facts cached by concrete specialization lowering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    RESULT_DIM_VECTOR,
)
from tslc.catalog.signatures import parse_signature
from tslc.ir.region_syntax import parse_call_selector
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment
from tslc.support_policy import DEFAULT_SUPPORT_POLICY, SupportPolicy
from tslc.support_policy_views import immediate_split_names, policy_split_names


@dataclass(frozen=True, slots=True)
class LowererCatalogFacts:
    primitive_axes: MappingProxyType[str, tuple[str, ...]]
    primitive_arg_generics: MappingProxyType[str, int]
    primitive_caller_unsafe: MappingProxyType[str, bool]
    primitive_borrowed_arg_positions: MappingProxyType[str, tuple[int, ...]]
    primitive_type_param_bounds: MappingProxyType[
        tuple[str, str, int], tuple[str, ...]
    ]
    policy_split_names: frozenset[str]
    immediate_split_names: frozenset[str]

    @classmethod
    def build(
        cls,
        catalog: Catalog,
        support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
    ) -> LowererCatalogFacts:
        return cls(
            primitive_axes=MappingProxyType(_primitive_axes(catalog)),
            primitive_arg_generics=MappingProxyType(
                _primitive_arg_generics(catalog, support)
            ),
            primitive_caller_unsafe=MappingProxyType(
                _primitive_caller_unsafe(catalog, support)
            ),
            primitive_borrowed_arg_positions=MappingProxyType(
                _primitive_borrowed_arg_positions(catalog, support)
            ),
            primitive_type_param_bounds=MappingProxyType(
                _primitive_type_param_bounds(catalog)
            ),
            policy_split_names=policy_split_names(catalog, support),
            immediate_split_names=immediate_split_names(catalog, support),
        )


def type_param_bounds(
    body: str | tuple[Segment, ...],
    type_param_name: str,
    forwarded_bounds: Mapping[tuple[str, str, int], tuple[str, ...]] | None = None,
    forwarded_extension: str | None = None,
) -> tuple[str, ...]:
    """Derive primitive bounds from typed call regions, including forwarding."""

    segments = scan(body) if isinstance(body, str) else body
    return tuple(
        sorted(
            _type_param_bound_names(
                segments,
                type_param_name,
                forwarded_bounds or {},
                forwarded_extension,
            )
        )
    )


def _type_param_bound_names(
    segments: tuple[Segment, ...] | None,
    type_param_name: str,
    forwarded_bounds: Mapping[tuple[str, str, int], tuple[str, ...]],
    forwarded_extension: str | None,
) -> frozenset[str]:
    if segments is None:
        return frozenset()
    names: set[str] = set()
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        if segment.keyword == "call":
            parsed = parse_call_selector(segment.selector_text)
            if (
                parsed is not None
                and not parsed.primitive_ref.startswith("@")
                and parsed.type_args
                and parsed.type_args[0].strip() == type_param_name
            ):
                names.add(parsed.primitive_ref)
            if parsed is not None and not parsed.primitive_ref.startswith("@"):
                for index, argument in enumerate(parsed.type_args[1:]):
                    if argument.strip() == type_param_name:
                        names.update(
                            forwarded_bounds.get(
                                (
                                    forwarded_extension or "",
                                    parsed.primitive_ref,
                                    index,
                                ),
                                (),
                            )
                        )
        for child in segment.child_sequences():
            names.update(
                _type_param_bound_names(
                    child,
                    type_param_name,
                    forwarded_bounds,
                    forwarded_extension,
                )
            )
    return frozenset(names)


def _primitive_type_param_bounds(
    catalog: Catalog,
) -> dict[tuple[str, str, int], tuple[str, ...]]:
    direct: dict[tuple[str, str, int], set[str]] = {}
    for primitive in catalog.primitives:
        extra_offset = (
            1
            if primitive.result_target is not None
            and primitive.result_target[0] != RESULT_DIM_VECTOR
            else 0
        )
        type_params = tuple(
            param for param in primitive.generic_params if param.kind == "simd_type"
        )
        for index, param in enumerate(type_params):
            for implementation in primitive.implementations:
                key = (
                    implementation.extension,
                    primitive.name,
                    extra_offset + index,
                )
                bounds = direct.setdefault(key, set())
                bodies = (
                    implementation.body_text,
                    *(variant.body_text for variant in implementation.variants),
                )
                for body in bodies:
                    bounds.update(type_param_bounds(body, param.name))

    collected: dict[tuple[str, str, int], set[str]] = {}
    for extension_name in catalog.extensions:
        chain = catalog.extension_chain(extension_name)
        for (implementation_extension, primitive_name, index), bounds in direct.items():
            if implementation_extension not in chain:
                continue
            collected.setdefault(
                (extension_name, primitive_name, index),
                set(),
            ).update(bounds)
    return {
        key: tuple(sorted(bounds))
        for key, bounds in sorted(collected.items())
    }


def _primitive_axes(catalog: Catalog) -> dict[str, tuple[str, ...]]:
    return {
        primitive.name: tuple(
            sorted(
                key
                for key in primitive.attributes
                if key in BOOLEAN_WILDCARD_ATTRIBUTES
            )
        )
        for primitive in catalog.primitives
    }


def _primitive_arg_generics(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> dict[str, int]:
    by_name: dict[str, list[tuple[str, ...]]] = {}
    policy_names = policy_split_names(catalog, support)
    immediate_names = immediate_split_names(catalog, support)
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is None:
            continue
        name = primitive.name
        mask_policy = primitive.attributes.get("mask")
        if mask_policy is not None and name in policy_names:
            name = f"{name}{support.mask_suffix(mask_policy)}"
        if primitive.name in immediate_names and support.has_immediate_operand(shape):
            name = f"{name}_imm"
        by_name.setdefault(name, []).append(shape.param_kinds)
    counts: dict[str, int] = {}
    for name, kinds in by_name.items():
        arity = len(kinds[0])
        same = [item for item in kinds if len(item) == arity]
        counts[name] = sum(
            1 for index in range(arity) if len({item[index] for item in same}) > 1
        )
    return counts


def _primitive_caller_unsafe(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> dict[str, bool]:
    values: dict[str, bool] = {}
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        inferred = shape is not None and support.requires_unsafe_frame(shape)
        authored = any(
            implementation.safety.caller_unsafe
            for implementation in primitive.implementations
        )
        values[primitive.name] = values.get(primitive.name, False) or inferred or authored
    return values


def _primitive_borrowed_arg_positions(
    catalog: Catalog,
    support: SupportPolicy = DEFAULT_SUPPORT_POLICY,
) -> dict[str, tuple[int, ...]]:
    positions_by_name: dict[str, set[int]] = {}
    for primitive in catalog.primitives:
        shape = parse_signature(primitive.signature)
        if shape is None:
            continue
        for index, kind in enumerate(shape.param_kinds):
            if support.is_borrowed_parameter_kind(kind):
                positions_by_name.setdefault(primitive.name, set()).add(index)
    return {
        name: tuple(sorted(positions))
        for name, positions in sorted(positions_by_name.items())
    }


__all__ = ("LowererCatalogFacts", "type_param_bounds")
