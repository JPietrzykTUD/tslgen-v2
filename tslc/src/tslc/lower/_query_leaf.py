"""Leaf resolution for source-level query identifiers."""

from __future__ import annotations

import re

from tslc.catalog.scalar_types import is_type_tag
from tslc.lower._query_model import QueryValue, TextValue, TypeValue
from tslc.lower.context import LoweringSession, SimdTypeParameterValue

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def resolve_query_leaf(head: str, context: LoweringSession) -> QueryValue | None:
    generation_int = context.scope.resolve_generation_int(head)
    if generation_int is not None:
        return TextValue(str(generation_int))

    target_type_symbol = context.scope.resolve_target_type_symbol(head)
    if target_type_symbol is not None:
        return TypeValue(target_type_symbol)

    extension_symbol = context.scope.resolve_extension_symbol(head)
    if extension_symbol is not None:
        return TextValue(extension_symbol)

    type_symbol = context.scope.resolve_type_symbol(head)
    if type_symbol is not None:
        return TypeValue(type_symbol)

    vector_alias = context.scope.resolve_vector_alias(head)
    if vector_alias is not None:
        return vector_alias

    type_alias = context.scope.resolve_type_alias(head)
    if type_alias is not None:
        return TextValue(type_alias)

    if head in getattr(context.env, "simd_type_param_names", frozenset()):
        return SimdTypeParameterValue(head)

    if is_type_tag(head):
        return TypeValue(head)

    if head.startswith("scalar::"):
        scalar_tag = head[len("scalar::") :]
        if is_type_tag(scalar_tag):
            return TypeValue(scalar_tag)
        backend = getattr(context.env, "backend", None)
        types = getattr(backend, "types", None)
        if types is None:
            return TextValue(scalar_tag)
        spelling = types.scalar_spelling(scalar_tag)
        return TextValue(spelling) if spelling is not None else None

    if head.startswith("x86::"):
        backend = getattr(context.env, "backend", None)
        templates = getattr(backend, "templates", None)
        if templates is None:
            return None
        key = f"value_{head[len('x86::') :]}"
        spelling = templates.template(key)
        return TextValue(spelling) if spelling is not None else None

    if len(head) >= 2 and head[0] == '"' == head[-1]:
        return TextValue(head[1:-1])

    if _IDENTIFIER.match(head):
        return TextValue(head)
    return None
