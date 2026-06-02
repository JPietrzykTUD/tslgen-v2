"""Primitive render plan assembly over already-decided presentation values."""

from __future__ import annotations

from dataclasses import dataclass

from tslgen.core.diagnostics import Diagnostic
from tslgen.rendering.primitive_render_model import (
    BackendPrimitiveRenderModel,
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveBodyValue,
    PrimitiveDeclarationValue,
    PrimitiveDefinitionValue,
    PrimitiveImportValue,
    PrimitiveIncludeValue,
    PrimitiveModuleValue,
    PrimitiveNamespaceValue,
    PrimitiveProfileName,
    PrimitiveRenderRecord,
    PrimitiveRenderSortKey,
    adapt_primitive_render_models,
)
from tslgen.rendering.primitive_templates import PrimitiveTemplateRenderContext


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlanText:
    text: str

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlanPrimitiveId(PrimitiveRenderPlanText):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlanSource(PrimitiveRenderPlanText):
    pass


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlanRecord:
    primitive_id: PrimitiveRenderPlanPrimitiveId
    presentation_sort_key: PrimitiveRenderSortKey
    declarations: tuple[PrimitiveDeclarationValue, ...] = ()
    definitions: tuple[PrimitiveDefinitionValue, ...] = ()
    body_text: PrimitiveBodyValue | None = None
    source: PrimitiveRenderPlanSource | None = None


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlan:
    backend_id: PrimitiveBackendId
    profile_name: PrimitiveProfileName
    logical_path: PrimitiveArtifactLogicalPath
    primitives: tuple[PrimitiveRenderPlanRecord, ...] = ()
    includes: tuple[PrimitiveIncludeValue, ...] = ()
    imports: tuple[PrimitiveImportValue, ...] = ()
    namespace_open: PrimitiveNamespaceValue | None = None
    namespace_close: PrimitiveNamespaceValue | None = None
    module_open: PrimitiveModuleValue | None = None
    module_close: PrimitiveModuleValue | None = None
    source: PrimitiveRenderPlanSource | None = None


@dataclass(frozen=True, slots=True)
class PrimitiveRenderPlanAdaptationResult:
    plans: tuple[PrimitiveRenderPlan, ...] = ()
    models: tuple[BackendPrimitiveRenderModel, ...] = ()
    contexts: tuple[PrimitiveTemplateRenderContext, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


def adapt_primitive_render_plans(
    plans: tuple[PrimitiveRenderPlan, ...],
) -> PrimitiveRenderPlanAdaptationResult:
    diagnostics = list(_plan_diagnostics(plans))
    if diagnostics:
        return PrimitiveRenderPlanAdaptationResult(
            diagnostics=_sort_diagnostics(diagnostics),
        )

    ordered_plans = tuple(
        sorted(
            plans,
            key=lambda item: (
                item.logical_path.text,
                item.backend_id.text,
                item.profile_name.text,
            ),
        )
    )
    models = tuple(_plan_to_model(plan) for plan in ordered_plans)
    adaptation = adapt_primitive_render_models(models, primitive_order="supplied")
    if adaptation.diagnostics:
        return PrimitiveRenderPlanAdaptationResult(
            diagnostics=adaptation.diagnostics,
        )
    return PrimitiveRenderPlanAdaptationResult(
        plans=ordered_plans,
        models=models,
        contexts=adaptation.contexts,
    )


def _plan_to_model(plan: PrimitiveRenderPlan) -> BackendPrimitiveRenderModel:
    return BackendPrimitiveRenderModel(
        backend_id=plan.backend_id,
        logical_path=plan.logical_path,
        profile_name=plan.profile_name,
        includes=plan.includes,
        imports=plan.imports,
        namespace_open=plan.namespace_open,
        namespace_close=plan.namespace_close,
        module_open=plan.module_open,
        module_close=plan.module_close,
        primitives=tuple(
            PrimitiveRenderRecord(
                sort_key=record.presentation_sort_key,
                declarations=record.declarations,
                definitions=record.definitions,
                body_text=record.body_text,
            )
            for record in plan.primitives
        ),
    )


def _plan_diagnostics(plans: tuple[PrimitiveRenderPlan, ...]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_plan_keys: set[tuple[str, str, str]] = set()

    for plan in plans:
        plan_key = (
            plan.backend_id.text,
            plan.profile_name.text,
            plan.logical_path.text,
        )
        if plan_key in seen_plan_keys:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-RENDER-PLAN-DUPLICATE-PLAN",
                    message=(
                        "duplicate primitive render plan for backend "
                        f"{plan.backend_id.text!r}, profile "
                        f"{plan.profile_name.text!r}, artifact "
                        f"{plan.logical_path.text!r}"
                    ),
                )
            )
        seen_plan_keys.add(plan_key)

        backend_id = plan.backend_id.text
        if backend_id not in {"cpp", "rust"}:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-RENDER-PLAN-UNKNOWN-BACKEND",
                    message=f"unsupported primitive render plan backend {backend_id!r}",
                )
            )
            continue

        diagnostics.extend(_duplicate_record_diagnostics(plan))
        diagnostics.extend(_wrong_backend_field_diagnostics(plan))

    return _sort_diagnostics(diagnostics)


def _duplicate_record_diagnostics(
    plan: PrimitiveRenderPlan,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_primitive_ids: set[str] = set()
    for record in plan.primitives:
        primitive_id = record.primitive_id.text
        if primitive_id in seen_primitive_ids:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-RENDER-PLAN-DUPLICATE-PRIMITIVE",
                    message=(
                        "duplicate primitive render record "
                        f"{primitive_id!r} in backend {plan.backend_id.text!r}, "
                        f"profile {plan.profile_name.text!r}, artifact "
                        f"{plan.logical_path.text!r}"
                    ),
                )
            )
        seen_primitive_ids.add(primitive_id)
    return tuple(diagnostics)


def _wrong_backend_field_diagnostics(
    plan: PrimitiveRenderPlan,
) -> tuple[Diagnostic, ...]:
    if plan.backend_id.text == "cpp":
        return _unexpected_fields(
            plan,
            field_names=("imports", "module_open", "module_close"),
        )
    return _unexpected_fields(
        plan,
        field_names=("includes", "namespace_open", "namespace_close"),
    )


def _unexpected_fields(
    plan: PrimitiveRenderPlan,
    *,
    field_names: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for field_name in field_names:
        if getattr(plan, field_name):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PRIMITIVE-RENDER-PLAN-WRONG-BACKEND-FIELD",
                    message=(
                        f"primitive render plan backend {plan.backend_id.text!r} "
                        f"does not consume field {field_name!r}"
                    ),
                )
            )
    return tuple(diagnostics)


def _sort_diagnostics(diagnostics: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    return tuple(sorted(diagnostics, key=lambda item: (item.code, item.message)))
