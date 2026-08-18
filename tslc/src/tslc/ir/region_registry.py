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
TsilSelectorTermKind = Literal["value", "named", "bag"]
TsilDynamicValueSource = Literal["cast", "helper", "operator", "primitive"]


@dataclass(frozen=True, slots=True)
class TsilSelectorOptionDescriptor:
    """One named option inside a TSIL selector option bag."""

    name: str
    values: tuple[str, ...] = ()
    open_value: bool = False
    insert_text: str | None = None


@dataclass(frozen=True, slots=True)
class TsilSelectorTermDescriptor:
    """One comma-separated term in a TSIL region selector shell."""

    kind: TsilSelectorTermKind
    name: str | None = None
    values: tuple[str, ...] = ()
    dynamic_values: TsilDynamicValueSource | None = None
    open_value: bool = False
    options: tuple[TsilSelectorOptionDescriptor, ...] = ()
    allow_bare: bool = False


@dataclass(frozen=True, slots=True)
class TsilRegionAuthoringDescriptor:
    """Closed, syntax-only selector forms exposed to authoring tools.

    An empty form represents a region without a ``<...>`` selector. Open
    values are recorded so completion can stop safely instead of guessing a
    target-language or query identifier.
    """

    selector_forms: tuple[tuple[TsilSelectorTermDescriptor, ...], ...]


@dataclass(frozen=True, slots=True)
class TsilRegionDescriptor:
    keyword: str
    purpose: str
    accepted_forms: tuple[str, ...]
    authoring: TsilRegionAuthoringDescriptor
    body_shape: RegionBodyShape = "call"
    shell_validator: str | None = None


def _value(
    *values: str,
    dynamic_values: TsilDynamicValueSource | None = None,
    open_value: bool = False,
) -> TsilSelectorTermDescriptor:
    return TsilSelectorTermDescriptor(
        "value",
        values=values,
        dynamic_values=dynamic_values,
        open_value=open_value,
    )


def _named(
    name: str,
    *values: str,
    dynamic_values: TsilDynamicValueSource | None = None,
    open_value: bool = False,
) -> TsilSelectorTermDescriptor:
    return TsilSelectorTermDescriptor(
        "named",
        name=name,
        values=values,
        dynamic_values=dynamic_values,
        open_value=open_value,
    )


def _bag(
    name: str,
    *options: TsilSelectorOptionDescriptor,
    allow_bare: bool = False,
) -> TsilSelectorTermDescriptor:
    return TsilSelectorTermDescriptor(
        "bag",
        name=name,
        options=options,
        allow_bare=allow_bare,
    )


def _authoring(
    *forms: tuple[TsilSelectorTermDescriptor, ...],
) -> TsilRegionAuthoringDescriptor:
    return TsilRegionAuthoringDescriptor(forms)


_OPEN_VALUE = _value(open_value=True)
_BUILD_BAG = _bag(
    "build",
    TsilSelectorOptionDescriptor("prefix", open_value=True),
    TsilSelectorOptionDescriptor("infix", open_value=True),
    TsilSelectorOptionDescriptor("infix_sep", open_value=True),
    TsilSelectorOptionDescriptor("suffix", open_value=True),
    TsilSelectorOptionDescriptor("post", open_value=True),
    TsilSelectorOptionDescriptor(
        "immediate",
        open_value=True,
        insert_text="immediate(${1})=",
    ),
    allow_bare=True,
)
_CALL_ATTRS_BAG = _bag(
    "attrs",
    TsilSelectorOptionDescriptor("aligned", ("false", "true")),
    TsilSelectorOptionDescriptor("mask", ("zero", "pass_through")),
)
_CAST_TYPE = _named("type", "value", "ptr", "const_ptr")


DEFAULT_TSIL_REGION_DESCRIPTORS: tuple[TsilRegionDescriptor, ...] = (
    TsilRegionDescriptor(
        "intrin",
        "Invoke a target intrinsic.",
        (
            "intrin<name>(args)",
            "intrin<base, build>(args)",
            "intrin<base, build[modifier=value, ...]>(args)",
        ),
        _authoring(
            (_OPEN_VALUE,),
            (_OPEN_VALUE, _BUILD_BAG),
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
        _authoring(
            (_value(dynamic_values="helper"),),
            (_value(dynamic_values="helper"), _OPEN_VALUE),
        ),
        shell_validator="helper_selector",
    ),
    TsilRegionDescriptor(
        "op",
        "Render a backend-specific operator.",
        ("op<name>(arg0, arg1, ...)",),
        _authoring((_value(dynamic_values="operator"),)),
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
        _authoring(
            *(
                (_value(selector),)
                for selector in (
                    "infer",
                    "const_infer",
                    "typed",
                    "const_typed",
                    "runtime_array",
                    "init_register",
                    "const_init_register",
                )
            )
        ),
        shell_validator="var_selector",
    ),
    TsilRegionDescriptor(
        "let",
        "Bind a lowering-time type alias.",
        ("let<type>(Name, type_expression)",),
        _authoring((_value("type"),)),
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
        _authoring(
            (_value("lane_true"),),
            (_value("lane_false"),),
            (_value("none"),),
            (_value("all"),),
            (_value("test"),),
            (_value("test"), _value("imask")),
            (_value("set"),),
            (_value("clear"),),
            (_value("set_to"),),
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
        _authoring(
            *(
                (_value(selector),)
                for selector in ("copy", "set", "alloc", "alloc_aligned", "free")
            )
        ),
    ),
    TsilRegionDescriptor(
        "lanes",
        "Read a generation-known lane-list element.",
        ("lanes<at>(lane_list_param, index)",),
        _authoring((_value("at"),)),
    ),
    TsilRegionDescriptor(
        "array",
        "Update backend-owned array storage.",
        ("array<set>(array, index, value)",),
        _authoring((_value("set"),)),
        shell_validator="array_set",
    ),
    TsilRegionDescriptor(
        "io",
        "Format vector output.",
        ("io<format>(out, array, modifier)",),
        _authoring((_value("format"),)),
    ),
    TsilRegionDescriptor(
        "address",
        "Take a typed address or mutable borrow.",
        (
            "address<of>(expr)",
            "address<borrow_mut>(expr)",
        ),
        _authoring(
            (_value("of"),),
            (_value("borrow_mut"),),
        ),
        shell_validator="address_selector",
    ),
    TsilRegionDescriptor(
        "cast",
        "Render a backend-specific cast.",
        (
            "cast<variant>(type_expression, expr)",
            "cast<reinterpret, type=ptr>(type_expression, expr)",
            "cast<reinterpret, type=const_ptr>(type_expression, expr)",
        ),
        _authoring(
            (_value(dynamic_values="cast"),),
            (_value(dynamic_values="cast"), _CAST_TYPE),
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
        _authoring(
            (_named("primitive", dynamic_values="primitive"),),
            (
                _named("primitive", dynamic_values="primitive"),
                _CALL_ATTRS_BAG,
            ),
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
        _authoring((), (_value("generation"),), (_value("compile"),)),
        body_shape="if_block",
    ),
    TsilRegionDescriptor(
        "select_expr",
        "Render an expression conditional.",
        ("select_expr(condition, if_true, if_false)",),
        _authoring(()),
        shell_validator="select_expr",
    ),
    TsilRegionDescriptor(
        "assume_aligned",
        "Apply an alignment hint.",
        ("assume_aligned<alignment_expression>(ptr)",),
        _authoring((_OPEN_VALUE,)),
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
        _authoring(
            (_value("backend"),),
            (_value("backend"), _value("unroll")),
            (_value("generation"),),
            (_value("generation"), _value("scoped")),
        ),
        body_shape="loop_block",
    ),
    TsilRegionDescriptor(
        "switch",
        "Emit compile-time selection.",
        (
            "switch<compile>(selector) { label => { body } _ => { fallback_body } }",
        ),
        _authoring((_value("compile"),)),
        body_shape="switch_block",
    ),
    TsilRegionDescriptor(
        "type",
        "Splice a resolved type.",
        ("type(query)",),
        _authoring(()),
        shell_validator="no_selector",
    ),
    TsilRegionDescriptor(
        "value",
        "Splice a resolved value.",
        ("value(query)",),
        _authoring(()),
        shell_validator="no_selector",
    ),
    TsilRegionDescriptor(
        "complete",
        "Return the primitive result.",
        ("complete(expr)",),
        _authoring(()),
    ),
)


def validate_region_authoring_descriptors(
    descriptors: tuple[TsilRegionDescriptor, ...],
) -> None:
    for descriptor in descriptors:
        if not isinstance(descriptor.authoring, TsilRegionAuthoringDescriptor):
            raise ValueError(
                f"TSIL region {descriptor.keyword!r} is missing authoring metadata"
            )
        if not descriptor.authoring.selector_forms:
            raise ValueError(
                f"TSIL region {descriptor.keyword!r} has no authoring selector forms"
            )


validate_region_authoring_descriptors(DEFAULT_TSIL_REGION_DESCRIPTORS)

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
    "TsilDynamicValueSource",
    "TsilRegionAuthoringDescriptor",
    "TsilRegionDescriptor",
    "TsilSelectorOptionDescriptor",
    "TsilSelectorTermDescriptor",
    "TsilSelectorTermKind",
    "region_body_shape",
    "region_shell_validator",
    "validate_region_authoring_descriptors",
]
