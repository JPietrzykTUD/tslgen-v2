"""Shared TSIL region descriptor registry.

This module owns lexical facts about TSIL keyword regions. It deliberately does
not import lowering or validation code: scanner, catalog validation, and lowering
registries consume these descriptors from their own layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

RegionBodyShape = Literal["call", "if_block", "loop_block", "switch_block"]


@dataclass(frozen=True, slots=True)
class TsilRegionDescriptor:
    keyword: str
    purpose: str
    accepted_forms: tuple[str, ...]
    body_shape: RegionBodyShape = "call"
    shell_validator: str | None = None


DEFAULT_TSIL_REGION_DESCRIPTORS: tuple[TsilRegionDescriptor, ...] = (
    TsilRegionDescriptor(
        "intrin",
        "Invoke a target intrinsic.",
        (
            "intrin<name>(args)",
            "intrin<base, build>(args)",
            "intrin<base, build[modifier=value, ...]>(args)",
        ),
        shell_validator="intrin_selector",
    ),
    TsilRegionDescriptor(
        "helper",
        "Invoke a compiler-owned helper.",
        (
            "helper<name>(args)",
            "helper<name, template_arg, ...>(args)",
        ),
        shell_validator="helper_selector",
    ),
    TsilRegionDescriptor(
        "op",
        "Render a backend-specific operator.",
        ("op<name>(arg0, arg1, ...)",),
    ),
    TsilRegionDescriptor(
        "var",
        "Declare local storage.",
        (
            "var<infer>(name, value)",
            "var<const_infer>(name, value)",
            "var<typed>(type, name, value)",
            "var<const_typed>(type, name, value)",
            "var<runtime_array>(element_type, name, count)",
            "var<init_register>(name)",
            "var<const_init_register>(name)",
        ),
        shell_validator="var_selector",
    ),
    TsilRegionDescriptor(
        "let",
        "Bind a lowering-time type alias.",
        ("let<type>(Name, type_expression)",),
        shell_validator="let_type",
    ),
    TsilRegionDescriptor(
        "mask",
        "Construct or update a mask.",
        (
            "mask<lane_true>()",
            "mask<lane_false>()",
            "mask<none>()",
            "mask<all>()",
            "mask<test>(mask, index)",
            "mask<test, imask>(imask, index)",
            "mask<set>(mask, index)",
            "mask<clear>(mask, index)",
            "mask<set_to>(mask, index, value)",
        ),
        shell_validator="mask_selector",
    ),
    TsilRegionDescriptor(
        "mem",
        "Perform raw byte-memory operations.",
        (
            "mem<copy>(dst, src, count)",
            "mem<set>(ptr, value, count)",
            "mem<alloc>(count)",
            "mem<alloc_aligned>(count, align)",
            "mem<free>(ptr)",
        ),
    ),
    TsilRegionDescriptor(
        "lanes",
        "Read a generation-known lane-list element.",
        ("lanes<at>(lane_list_param, index)",),
    ),
    TsilRegionDescriptor(
        "array",
        "Update backend-owned array storage.",
        ("array<set>(array, index, value)",),
        shell_validator="array_set",
    ),
    TsilRegionDescriptor(
        "io",
        "Format vector output.",
        ("io<format>(out, array, modifier)",),
    ),
    TsilRegionDescriptor(
        "cast",
        "Render a backend-specific cast.",
        (
            "cast<variant>(type_expression, expr)",
            "cast<reinterpret, type=ptr>(type_expression, expr)",
            "cast<reinterpret, type=const_ptr>(type_expression, expr)",
        ),
        shell_validator="cast_selector",
    ),
    TsilRegionDescriptor(
        "call",
        "Invoke a generated primitive wrapper.",
        (
            "call<primitive=name>(args)",
            "call<primitive=name[VecOrTypeArgs], attrs[key=value, ...]>(args)",
            "call<primitive=@self[...], attrs[key=value, ...]>(args)",
        ),
        shell_validator="call_selector",
    ),
    TsilRegionDescriptor(
        "if",
        "Select or emit a branch.",
        (
            "if(condition) { then_body } else { else_body }",
            "if<generation>(condition) { then_body } else<generation> { else_body }",
            "if<compile>(condition) { then_body } else<compile> { else_body }",
        ),
        body_shape="if_block",
    ),
    TsilRegionDescriptor(
        "select_expr",
        "Render an expression conditional.",
        ("select_expr(condition, if_true, if_false)",),
        shell_validator="select_expr",
    ),
    TsilRegionDescriptor(
        "assume_aligned",
        "Apply an alignment hint.",
        ("assume_aligned<alignment_expression>(ptr)",),
    ),
    TsilRegionDescriptor(
        "loop",
        "Emit or expand a loop.",
        (
            "loop<backend>(var, start, end, step) { body }",
            "loop<backend, unroll>(var, start, end, step) { body }",
            "loop<generation>(var, start, end, step) { body }",
            "loop<generation, scoped>(var, start, end, step) { body }",
        ),
        body_shape="loop_block",
    ),
    TsilRegionDescriptor(
        "switch",
        "Emit compile-time selection.",
        (
            "switch<compile>(selector) { label => { body } _ => { fallback_body } }",
        ),
        body_shape="switch_block",
    ),
    TsilRegionDescriptor(
        "type",
        "Splice a resolved type.",
        ("type(query)",),
        shell_validator="no_selector",
    ),
    TsilRegionDescriptor(
        "value",
        "Splice a resolved value.",
        ("value(query)",),
        shell_validator="no_selector",
    ),
    TsilRegionDescriptor(
        "complete",
        "Return the primitive result.",
        ("complete(expr)",),
    ),
)

TSIL_REGION_BY_KEYWORD = MappingProxyType(
    {descriptor.keyword: descriptor for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS}
)
TSIL_REGION_KEYWORDS: frozenset[str] = frozenset(TSIL_REGION_BY_KEYWORD)


def region_body_shape(keyword: str) -> RegionBodyShape:
    descriptor = TSIL_REGION_BY_KEYWORD.get(keyword)
    return descriptor.body_shape if descriptor is not None else "call"


def region_shell_validator(keyword: str) -> str | None:
    descriptor = TSIL_REGION_BY_KEYWORD.get(keyword)
    return descriptor.shell_validator if descriptor is not None else None


__all__ = [
    "DEFAULT_TSIL_REGION_DESCRIPTORS",
    "RegionBodyShape",
    "TSIL_REGION_BY_KEYWORD",
    "TSIL_REGION_KEYWORDS",
    "TsilRegionDescriptor",
    "region_body_shape",
    "region_shell_validator",
]
