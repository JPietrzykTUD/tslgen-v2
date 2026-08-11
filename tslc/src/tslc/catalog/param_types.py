"""Source-owned ``param_types`` expression and condition-key grammar.

``param_types`` entries are authored as target-neutral ``ptr(...)`` or
``cptr(...)`` wrappers around TSIL type expressions. This module owns that
source syntax — the type expressions, the ``default`` /
``if attribute=value`` rule-condition keys, and the related generic-parameter
base-width constraint keys — so catalog promotion, schema validation, lowering,
and value-test planning share one grammar instead of drifting copies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast, get_args

from tslc.catalog.model import BaseWidthRelation, ParamTypeExpression
from tslc.catalog.scalar_types import signed_of, unsigned_of

_PARAM_TYPE_CONDITION_RE = re.compile(r"^if\s+([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_]+)$")
# Allowed relations come from the typed vocabulary; longest-first so ">=" wins over ">".
BASE_WIDTH_RELATIONS: tuple[str, ...] = tuple(
    sorted(get_args(BaseWidthRelation), key=len, reverse=True)
)
_BASE_WIDTH_CONSTRAINT_RE = re.compile(
    r"^width\(self::base\)\s*("
    + "|".join(re.escape(relation) for relation in BASE_WIDTH_RELATIONS)
    + r")\s*width\(base::in\)$"
)
# The same key shape with *any* relation token, so validation can distinguish a
# base-width constraint with an unknown relation from an unrelated unknown field.
_BASE_WIDTH_SHAPE_RE = re.compile(
    r"^width\(self::base\)\s*(\S+?)\s*width\(base::in\)$"
)


@dataclass(frozen=True, slots=True)
class ParamTypeScalarResolution:
    type_tag: str | None = None
    reason: str | None = None


def unquote_key(text: str) -> str:
    """A parse-tree field key with its surrounding quotes removed, if quoted."""

    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1]
    return text


def parse_param_type_condition(text: str) -> tuple[str | None, str | None] | None:
    """Parse a ``param_types`` rule-condition key (a possibly quoted field key).

    Returns ``(None, None)`` for the unconditional ``default`` rule,
    ``(attribute, value)`` for an ``if attribute=value`` condition, and ``None``
    when the key matches neither form. Promotion drops rejected keys and schema
    validation diagnoses them, both through this one parser.
    """

    condition = unquote_key(text)
    if condition == "default":
        return (None, None)
    match = _PARAM_TYPE_CONDITION_RE.fullmatch(condition)
    if match is None:
        return None
    return match.group(1), match.group(2)


def parse_base_width_constraint(text: str) -> BaseWidthRelation | None:
    """The relation of a ``width(self::base) <op> width(base::in)`` constraint key.

    Returns ``">="``, ``">"``, or ``"=="``; ``None`` when the key is not a
    base-width constraint with a known relation.
    """

    match = _BASE_WIDTH_CONSTRAINT_RE.fullmatch(text)
    # The regex alternation is derived from BaseWidthRelation, so the group is a member.
    return None if match is None else cast(BaseWidthRelation, match.group(1))


def base_width_relation_text(text: str) -> str | None:
    """The raw relation token of a base-width-*shaped* constraint key, known or not.

    Validation uses this to diagnose a mistyped relation (``<``, ``=>``) with a
    clear message instead of reporting the whole key as an unknown field.
    """

    match = _BASE_WIDTH_SHAPE_RE.fullmatch(text)
    return None if match is None else match.group(1)


def parse_param_type_expression(type_expr: str) -> ParamTypeExpression | None:
    """Parse an exact target-neutral pointer wrapper."""

    head_arg = _split_head_arg(type_expr)
    if head_arg is None:
        return None
    head, pointee = head_arg
    if not pointee:
        return None
    if head == "ptr":
        return ParamTypeExpression("mutable", pointee)
    if head == "cptr":
        return ParamTypeExpression("const", pointee)
    return None


def resolve_param_type_scalar_tag(
    type_expr: ParamTypeExpression,
    input_type_tag: str,
) -> ParamTypeScalarResolution:
    """Resolve the scalar-layout subset used by generated value tests."""

    query = _unwrap_type_call(type_expr.pointee_expr)
    if query is None:
        return _unsupported_scalar_layout(type_expr)
    resolved = _resolve_scalar_query(query, input_type_tag)
    if resolved is None:
        return _unsupported_scalar_layout(type_expr)
    return ParamTypeScalarResolution(type_tag=resolved)


def _resolve_scalar_query(query: str, input_type_tag: str) -> str | None:
    query = query.strip()
    if query == "base::in":
        return input_type_tag
    head_arg = _split_head_arg(query)
    if head_arg is None:
        return None
    head, arg = head_arg
    inner = _unwrap_type_call(arg)
    if inner != "base::in":
        return None
    if head == "base::unsigned_of":
        return unsigned_of(input_type_tag)
    if head == "base::signed_of":
        return signed_of(input_type_tag)
    return None


def _unsupported_scalar_layout(
    type_expr: ParamTypeExpression,
) -> ParamTypeScalarResolution:
    return ParamTypeScalarResolution(
        reason=(
            "unsupported param_types layout expression "
            f"{type_expr.source_text!r}; value tests "
            "support type(base::in), type(base::unsigned_of(type(base::in))), "
            "and type(base::signed_of(type(base::in)))"
        )
    )


def _unwrap_type_call(text: str) -> str | None:
    head_arg = _split_head_arg(text)
    if head_arg is None:
        return None
    head, arg = head_arg
    return arg.strip() if head == "type" else None


def uses_c_like_pointer_syntax(type_expr: str) -> bool:
    """Whether a rejected expression uses the retired target-language shell."""

    return type_expr.strip().endswith("*")


def _split_head_arg(text: str) -> tuple[str, str] | None:
    text = text.strip()
    open_index = text.find("(")
    if open_index == -1 or not text.endswith(")"):
        return None
    depth = 0
    for index, char in enumerate(text[open_index:], start=open_index):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                if index != len(text) - 1:
                    return None
                return text[:open_index].strip(), text[open_index + 1 : index].strip()
    return None


__all__ = (
    "BASE_WIDTH_RELATIONS",
    "ParamTypeExpression",
    "ParamTypeScalarResolution",
    "base_width_relation_text",
    "parse_base_width_constraint",
    "parse_param_type_condition",
    "parse_param_type_expression",
    "resolve_param_type_scalar_tag",
    "unquote_key",
    "uses_c_like_pointer_syntax",
)
