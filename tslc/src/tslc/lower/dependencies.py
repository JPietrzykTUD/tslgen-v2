"""Semantic dependencies discovered from lowered TSIL primitive calls.

The pipeline needs to know which primitive specializations a lowered body calls
so it can keep reachable callees and prune dangling callers. The call-region
lowerer records these source identities while rendering the branch that will
actually be emitted; this module owns only the typed identity and its focused
resolution helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import RESULT_DIM_VECTOR
from tslc.ir.region_syntax import ParsedCallSelector
from tslc.lower.context import LoweringSession, VectorValue
from tslc.lower.queries import QueryEvaluator, TypeValue


@dataclass(frozen=True, slots=True)
class VectorIdentity:
    base_tag: str
    extension_isa: str


@dataclass(frozen=True, slots=True)
class CallDependency:
    primitive: str
    mask_policy: str | None
    source: VectorIdentity
    target: VectorIdentity | None = None


@dataclass(frozen=True, slots=True)
class CallDependencyOrigin:
    """One lowered call edge plus its authored implementation origin."""

    dependency: CallDependency
    origin: str


def resolve_lowered_call_dependency(
    selector: ParsedCallSelector,
    context: LoweringSession,
    evaluator: QueryEvaluator,
    *,
    mask_policy: str | None,
) -> CallDependency:
    """Resolve one successfully lowered ``call`` to source vector identities."""

    current = VectorIdentity(context.env.type_tag, context.env.extension.isa_name)
    callee = (
        context.env.current_primitive
        if selector.primitive_ref == "@self"
        else selector.primitive_ref.lstrip("@")
    )
    entries = selector.type_args
    source = (
        resolve_lowered_call_vector(entries[0], context, evaluator)
        if entries
        else None
    ) or current
    target = None
    if _lowered_callee_has_target_axis(context, callee):
        target = next(
            (
                resolved
                for entry in entries[1:]
                if (
                    resolved := resolve_lowered_call_vector(
                        entry,
                        context,
                        evaluator,
                        relative_to=source,
                    )
                )
                is not None
            ),
            None,
        )
    return CallDependency(callee, mask_policy, source, target)


def dependency_sort_key(
    dependency: CallDependency,
) -> tuple[str, str, str, str, str, str]:
    return (
        dependency.primitive,
        dependency.mask_policy or "",
        dependency.source.extension_isa,
        dependency.source.base_tag,
        dependency.target.extension_isa if dependency.target is not None else "",
        dependency.target.base_tag if dependency.target is not None else "",
    )


def origin_sort_key(
    origin: CallDependencyOrigin,
) -> tuple[str, str, str, str, str, str, str]:
    return (*dependency_sort_key(origin.dependency), origin.origin)


def resolve_lowered_call_vector(
    expression: str,
    context: LoweringSession,
    evaluator: QueryEvaluator,
    *,
    relative_to: VectorIdentity | None = None,
) -> VectorIdentity | None:
    """Resolve one call-vector expression using representation-change rules.

    Explicit vectors are absolute. A bare extension target inherits the source
    vector's base, while a bare base target inherits its extension. Rendering
    and dependency closure share this resolver so those identities cannot
    drift apart.
    """

    expression = expression.strip()
    if expression == "Vec":
        return VectorIdentity(context.env.type_tag, context.env.extension.isa_name)
    if expression.startswith("Vec<") and expression.endswith(">"):
        base = _resolve_lowered_type(
            expression[len("Vec<") : -1], context, evaluator
        )
        return (
            VectorIdentity(base, context.env.extension.isa_name)
            if base is not None
            else None
        )
    if expression in context.env.simd_type_param_names:
        base = context.env.simd_type_param_base_bindings.get(expression)
        if base is not None:
            return VectorIdentity(
                base,
                (
                    relative_to.extension_isa
                    if relative_to is not None
                    else context.env.extension.isa_name
                ),
            )

    vector = context.scope.resolve_vector_alias(expression)
    if vector is not None:
        return VectorIdentity(vector.base_tag, vector.extension_isa)
    extension = _resolve_lowered_extension_isa(expression, context)
    if extension is not None:
        return VectorIdentity(
            relative_to.base_tag if relative_to is not None else context.env.type_tag,
            extension,
        )

    value = evaluator.evaluate(expression, context)
    if isinstance(value, VectorValue):
        return VectorIdentity(value.base_tag, value.extension_isa)
    if isinstance(value, TypeValue):
        return VectorIdentity(
            value.type_tag,
            (
                relative_to.extension_isa
                if relative_to is not None
                else context.env.extension.isa_name
            ),
        )
    return None


def _resolve_lowered_type(
    expression: str,
    context: LoweringSession,
    evaluator: QueryEvaluator,
) -> str | None:
    expression = expression.strip()
    bound = context.scope.resolve_type_symbol(expression)
    if bound is not None:
        return bound
    value = evaluator.evaluate(expression, context)
    return value.type_tag if isinstance(value, TypeValue) else None


def _resolve_lowered_extension_isa(
    expression: str,
    context: LoweringSession,
) -> str | None:
    name = expression.strip()
    bound = context.scope.resolve_extension_symbol(name)
    if bound is not None:
        name = bound
    extension = context.env.catalog.extensions.get(name)
    if extension is not None:
        return extension.isa_name
    return next(
        (
            extension.isa_name
            for extension in context.env.catalog.extensions.values()
            if extension.isa_name == name
        ),
        None,
    )


def _lowered_callee_has_target_axis(
    context: LoweringSession,
    callee: str,
) -> bool:
    return any(
        primitive.result_target is not None
        and primitive.result_target[0] != RESULT_DIM_VECTOR
        for primitive in context.env.catalog.primitives_named(callee, unmasked=False)
    )


__all__ = (
    "CallDependency",
    "CallDependencyOrigin",
    "VectorIdentity",
    "dependency_sort_key",
    "origin_sort_key",
    "resolve_lowered_call_vector",
    "resolve_lowered_call_dependency",
)
