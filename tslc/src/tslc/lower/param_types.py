"""Lower typed catalog parameter-type rules into backend spellings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.catalog.model import ParamTypeExpression
from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.lower.body_rendering import ExpressionRenderer
from tslc.lower.context import LoweringSession
from tslc.lower.region_handlers import RegionLowerer
from tslc.select.selector import SelectedImplementation
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.target_text import render_text

if TYPE_CHECKING:
    from tslc.lower.lowerer import LoweredSpecialization


def effective_param_types(spec: LoweredSpecialization) -> tuple[str, ...]:
    """Return per-position overload identities after typed overrides."""

    identity_tokens = spec.param_identity_tokens or tuple(
        DEFAULT_SUPPORT_POLICY.overload_identity_token(
            kind,
            register_is_base=spec.register_is_base,
        )
        for kind in spec.param_kinds
    )
    return tuple(
        override if override is not None else identity
        for identity, override in zip(
            identity_tokens, spec.effective_param_type_overrides
        )
    )


def param_type_overrides(
    selected: SelectedImplementation,
    parameters: tuple[str, ...],
    context: LoweringSession,
    region_lowerers: tuple[RegionLowerer, ...],
) -> tuple[str | None, ...]:
    """Render unconditional typed ``param_types`` rules for one selection."""

    primitive = selected.primitive
    overrides: list[str | None] = []
    renderer = ExpressionRenderer(context, selected, region_lowerers)
    for parameter_name in parameters:
        rule = next(
            (
                rule
                for rule in primitive.param_type_rules
                if rule.parameter_name == parameter_name
                and rule.attribute_name is None
            ),
            None,
        )
        if rule is None:
            overrides.append(None)
            continue
        text = _render_param_type_expr(
            rule.type_expr, context, renderer, rule.source
        )
        if not text:
            context.effects.skip(
                "TSL-LOWER-UNSUPPORTED-PARAM-TYPE",
                f"could not resolve param_types default for {parameter_name!r}",
                source=rule.source,
            )
            overrides.append(None)
            continue
        overrides.append(text)
    return tuple(overrides)


def _render_param_type_expr(
    type_expr: ParamTypeExpression,
    context: LoweringSession,
    renderer: ExpressionRenderer,
    source: SourceSpan | None,
) -> str:
    value = render_text(
        renderer.render(scan(type_expr.pointee_expr, source=source))
    ).strip()
    if not value:
        return ""
    rendered = context.env.backend.syntax.render_param_type(
        value,
        is_pointer=True,
        is_const=type_expr.pointer_kind == "const",
    )
    return render_text(rendered).strip()


__all__ = ("effective_param_types", "param_type_overrides")
