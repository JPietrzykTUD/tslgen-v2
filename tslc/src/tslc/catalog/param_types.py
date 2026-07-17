"""Source-owned ``param_types`` expression and condition-key grammar.

``param_types`` entries are authored as TSIL-ish type expressions, with an
optional C-like pointer suffix because the source corpus is C-family today. This
module owns that source syntax — the type expressions, the ``default`` /
``if attribute=value`` rule-condition keys, and the related generic-parameter
base-width constraint keys — so catalog promotion, schema validation, lowering,
and value-test planning share one grammar instead of drifting copies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tslc.catalog.scalar_types import signed_of, unsigned_of

_PARAM_TYPE_CONDITION_RE = re.compile(r"^if\s+([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_]+)$")
_BASE_WIDTH_CONSTRAINT_RE = re.compile(
    r"^width\(self::base\)\s*(>=|>|==)\s*width\(base::in\)$"
)


@dataclass(frozen=True, slots=True)
class ParamTypeExpression:
    value_expr: str
    pointer_const: bool | None = None

    @property
    def is_pointer(self) -> bool:
        return self.pointer_const is not None


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


def parse_base_width_constraint(text: str) -> str | None:
    """The relation of a ``width(self::base) <op> width(base::in)`` constraint key.

    Returns ``">="``, ``">"``, or ``"=="``; ``None`` when the key is not a
    base-width constraint.
    """

    match = _BASE_WIDTH_CONSTRAINT_RE.fullmatch(text)
    return None if match is None else match.group(1)


def parse_param_type_expression(type_expr: str) -> ParamTypeExpression:
    """Parse the source-level pointer shell around a ``param_types`` expression."""

    pointer = _split_c_like_pointer_type(type_expr)
    if pointer is None:
        return ParamTypeExpression(type_expr.strip())
    value_expr, is_const = pointer
    return ParamTypeExpression(value_expr, pointer_const=is_const)


def resolve_param_type_scalar_tag(
    type_expr: str,
    input_type_tag: str,
) -> ParamTypeScalarResolution:
    """Resolve the scalar-layout subset used by generated value tests."""

    parsed = parse_param_type_expression(type_expr)
    query = _unwrap_type_call(parsed.value_expr)
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


def _unsupported_scalar_layout(type_expr: str) -> ParamTypeScalarResolution:
    return ParamTypeScalarResolution(
        reason=(
            f"unsupported param_types layout expression {type_expr!r}; value tests "
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


def _split_c_like_pointer_type(type_expr: str) -> tuple[str, bool] | None:
    text = type_expr.strip()
    if not text.endswith("*"):
        return None
    base = text[:-1].rstrip()
    is_const = False
    if base.endswith("const"):
        is_const = True
        base = base[: -len("const")].rstrip()
    if not base:
        return None
    return base, is_const


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
    "ParamTypeExpression",
    "ParamTypeScalarResolution",
    "parse_base_width_constraint",
    "parse_param_type_condition",
    "parse_param_type_expression",
    "resolve_param_type_scalar_tag",
    "unquote_key",
)
