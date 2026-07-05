"""Resolve source-owned pointer parameter layout rules for value tests."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import Primitive, TestCase
from tslc.catalog.scalar_types import signed_of, unsigned_of
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import base_spelling


@dataclass(frozen=True, slots=True)
class ParamLayout:
    """Concrete scalar storage selected from a `param_types:` rule."""

    type_expr: str
    type_tag: str
    base_spelling: str


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
        type_tag = scalar_type_tag_from_expr(rule.type_expr, case.type_tag)
        if type_tag is None:
            return None
        spelling = base_spelling(specs, type_tag)
        if spelling is None:
            return None
        return ParamLayout(
            type_expr=rule.type_expr,
            type_tag=type_tag,
            base_spelling=spelling,
        )
    return None


def scalar_type_tag_from_expr(type_expr: str, input_type_tag: str) -> str | None:
    """Resolve the scalar subset of `param_types` expressions used by value tests."""

    normalized = "".join(type_expr.split())
    if "base::unsigned_of" in normalized and "base::in" in normalized:
        return unsigned_of(input_type_tag)
    if "base::signed_of" in normalized and "base::in" in normalized:
        return signed_of(input_type_tag)
    if "base::in" in normalized:
        return input_type_tag
    return None


__all__ = ("ParamLayout", "resolve_param_layout", "scalar_type_tag_from_expr")
