"""Resolve source-owned pointer parameter layout rules for value tests."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Primitive, TestCase
from tslc.catalog.param_types import resolve_param_type_scalar_tag
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import base_spelling


@dataclass(frozen=True, slots=True)
class ParamLayout:
    """Concrete scalar storage selected from a `param_types:` rule."""

    type_expr: str
    type_tag: str
    base_spelling: str


@dataclass(frozen=True, slots=True)
class ParamLayoutResolution:
    layout: ParamLayout | None = None
    reason: str | None = None


def resolve_param_layout(
    primitive: Primitive,
    parameter_name: str,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ParamLayout | None:
    """Resolve a pointer parameter's storage layout for one authored test case.

    This is deliberately narrow: the public wrapper ABI still sees an abstract
    `ptr`, while value-test planning consumes source-owned layout rules when it
    needs a concrete buffer type.
    """

    return resolve_param_layout_checked(primitive, parameter_name, case, specs).layout


def resolve_param_layout_checked(
    primitive: Primitive,
    parameter_name: str,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ParamLayoutResolution:
    attrs = dict(specs[0].axis) if specs else {}
    attrs.update(case.attrs)
    for rule in primitive.param_type_rules:
        if rule.parameter_name != parameter_name:
            continue
        if (
            rule.attribute_name is not None
            and attrs.get(rule.attribute_name) != rule.attribute_value
        ):
            continue
        resolved = resolve_param_type_scalar_tag(rule.type_expr, case.type_tag)
        if resolved.type_tag is None:
            return ParamLayoutResolution(reason=resolved.reason)
        type_tag = resolved.type_tag
        spelling = base_spelling(specs, type_tag)
        if spelling is None:
            return ParamLayoutResolution(
                reason=(
                    f"param_types layout expression {rule.type_expr!r} resolved to "
                    f"type tag {type_tag!r}, but this backend has no scalar spelling for it"
                )
            )
        return ParamLayoutResolution(
            layout=ParamLayout(
                type_expr=rule.type_expr,
                type_tag=type_tag,
                base_spelling=spelling,
            )
        )
    return ParamLayoutResolution(
        reason=(
            f"no param_types layout rule for pointer parameter {parameter_name!r} "
            f"under attrs {_attrs_label(attrs)}"
        )
    )


def scalar_type_tag_from_expr(type_expr: str, input_type_tag: str) -> str | None:
    """Resolve the scalar subset of `param_types` expressions used by value tests."""

    return resolve_param_type_scalar_tag(type_expr, input_type_tag).type_tag


def unsupported_param_layout_reason(
    primitive: Primitive,
    parameter_name: str,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> str | None:
    return resolve_param_layout_checked(primitive, parameter_name, case, specs).reason


def _attrs_label(attrs: dict[str, str]) -> str:
    if not attrs:
        return "{}"
    return "{" + ", ".join(f"{key}={attrs[key]}" for key in sorted(attrs)) + "}"


__all__ = (
    "ParamLayout",
    "ParamLayoutResolution",
    "resolve_param_layout",
    "resolve_param_layout_checked",
    "scalar_type_tag_from_expr",
    "unsupported_param_layout_reason",
)
