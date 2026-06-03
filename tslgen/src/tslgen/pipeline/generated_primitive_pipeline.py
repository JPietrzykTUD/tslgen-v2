"""Tiny parsed-source to generated primitive project pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tslgen.analysis.selection import SelectedImplementation, Selector, Target
from tslgen.core.diagnostics import Diagnostic, has_errors
from tslgen.domain.catalog import Catalog
from tslgen.domain.generated_project import (
    GeneratedProfileSet,
    GeneratedProjectRenderModel,
)
from tslgen.domain.machine_profiles import MachineFeatureProfileCatalog
from tslgen.io.artifacts import ArtifactSet
from tslgen.io.sources import SourceDocument
from tslgen.lowering import (
    INPUT_SCALAR_RESULT_TYPE,
    LoweredBinaryOperationExpression,
    LoweredFunction,
    LoweredFunctionSet,
    LoweredParameterRef,
    LoweredResultType,
    Lowerer,
)
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.pipeline.catalog_builder import CatalogBuilder
from tslgen.pipeline.generated_profiles import select_generated_profiles
from tslgen.rendering import (
    PrimitiveArtifactLogicalPath,
    PrimitiveBackendId,
    PrimitiveProfileName,
    PrimitiveRenderPlan,
    PrimitiveRenderPlanPrimitiveId,
    PrimitiveRenderPlanRecord,
    PrimitiveRenderPlanSource,
    PrimitiveRenderSortKey,
    RenderedIncludeLine,
    RenderedNamespaceText,
    RenderedPrimitiveDefinitionText,
    adapt_primitive_render_plans,
    build_generated_project_render_model,
    compose_generated_primitive_project_artifacts,
    render_generated_project_skeleton,
    render_primitive_templates,
    scalar_profile_replacement_policy,
)
from tslgen.syntax.parser import TslParser


@dataclass(frozen=True, slots=True)
class SelectedLoweredFunction:
    selected: SelectedImplementation
    function: LoweredFunction


@dataclass(frozen=True, slots=True)
class ParsedTinyGeneratedProjectResult:
    artifacts: ArtifactSet
    diagnostics: tuple[Diagnostic, ...]
    model: GeneratedProjectRenderModel | None = None
    catalog: Catalog | None = None
    selected: tuple[SelectedImplementation, ...] = ()
    lowered_functions: LoweredFunctionSet = LoweredFunctionSet(())
    render_plans: tuple[PrimitiveRenderPlan, ...] = ()


@dataclass(frozen=True, slots=True)
class _ScalarTypeSpellingRule:
    backend_id: str
    type_tag: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _BinaryOperationSpellingRule:
    backend_id: str
    operation_id: str
    spelling: str


_SUPPORTED_PROFILE = "scalar"
_CPP_SCALAR_PROFILE_PATH = "cpp/include/profiles/scalar.hpp"
_RUST_SCALAR_PROFILE_PATH = "rust/src/profiles/scalar.rs"

_SCALAR_TYPE_SPELLINGS: tuple[_ScalarTypeSpellingRule, ...] = (
    _ScalarTypeSpellingRule("cpp", "si32", "std::int32_t"),
    _ScalarTypeSpellingRule("rust", "si32", "i32"),
)

_BINARY_OPERATION_SPELLINGS: tuple[_BinaryOperationSpellingRule, ...] = (
    _BinaryOperationSpellingRule("cpp", "add", "+"),
    _BinaryOperationSpellingRule("rust", "add", "+"),
)


def build_parsed_tiny_generated_project_artifacts(
    *,
    supplementary_root: Path,
    source_documents: tuple[SourceDocument, ...],
    targets: tuple[Target, ...],
    machine_profiles: MachineFeatureProfileCatalog,
    requested_profiles: tuple[str, ...] | None = None,
) -> ParsedTinyGeneratedProjectResult:
    diagnostics: list[Diagnostic] = []

    profile_selection = select_generated_profiles(machine_profiles, requested_profiles)
    diagnostics.extend(profile_selection.diagnostics)
    if profile_selection.profile_set is not None:
        diagnostics.extend(
            _unsupported_profile_diagnostics(profile_selection.profile_set)
        )
    if has_errors(diagnostics) or profile_selection.profile_set is None:
        return _result(diagnostics)

    model_result = build_generated_project_render_model(profile_selection.profile_set)
    diagnostics.extend(model_result.diagnostics)
    if has_errors(diagnostics) or model_result.model is None:
        return _result(diagnostics)
    model = model_result.model

    parse_result = TslParser().parse(source_documents)
    diagnostics.extend(parse_result.diagnostics)
    if has_errors(diagnostics):
        return _result(diagnostics, model=model)

    catalog_result = CatalogBuilder().build(parse_result.documents)
    diagnostics.extend(catalog_result.diagnostics)
    if has_errors(diagnostics) or catalog_result.catalog is None:
        return _result(diagnostics, model=model)
    catalog = catalog_result.catalog

    selected_functions, selection_lowering_diagnostics = _select_and_lower(
        catalog,
        targets,
    )
    diagnostics.extend(selection_lowering_diagnostics)
    if has_errors(diagnostics):
        return _result(
            diagnostics,
            model=model,
            catalog=catalog,
            selected=tuple(item.selected for item in selected_functions),
            lowered_functions=LoweredFunctionSet(
                tuple(item.function for item in selected_functions)
            ),
        )

    plans, plan_diagnostics = _render_plans_from_lowered_functions(
        selected_functions,
    )
    diagnostics.extend(plan_diagnostics)
    if has_errors(diagnostics):
        return _result(
            diagnostics,
            model=model,
            catalog=catalog,
            selected=tuple(item.selected for item in selected_functions),
            lowered_functions=LoweredFunctionSet(
                tuple(item.function for item in selected_functions)
            ),
        )

    plan_result = adapt_primitive_render_plans(plans)
    diagnostics.extend(plan_result.diagnostics)
    if has_errors(diagnostics):
        return _result(
            diagnostics,
            model=model,
            catalog=catalog,
            selected=tuple(item.selected for item in selected_functions),
            lowered_functions=LoweredFunctionSet(
                tuple(item.function for item in selected_functions)
            ),
            render_plans=plans,
        )

    primitive_render = render_primitive_templates(
        supplementary_root,
        plan_result.contexts,
    )
    diagnostics.extend(primitive_render.diagnostics)
    if has_errors(diagnostics):
        return _result(
            diagnostics,
            model=model,
            catalog=catalog,
            selected=tuple(item.selected for item in selected_functions),
            lowered_functions=LoweredFunctionSet(
                tuple(item.function for item in selected_functions)
            ),
            render_plans=plans,
        )

    skeleton_render = render_generated_project_skeleton(supplementary_root, model)
    diagnostics.extend(skeleton_render.diagnostics)
    if has_errors(diagnostics):
        return _result(
            diagnostics,
            model=model,
            catalog=catalog,
            selected=tuple(item.selected for item in selected_functions),
            lowered_functions=LoweredFunctionSet(
                tuple(item.function for item in selected_functions)
            ),
            render_plans=plans,
        )

    composition = compose_generated_primitive_project_artifacts(
        skeleton_render.artifacts,
        primitive_render.artifacts,
        scalar_profile_replacement_policy(),
    )
    diagnostics.extend(composition.diagnostics)
    return ParsedTinyGeneratedProjectResult(
        artifacts=(
            composition.artifacts
            if not has_errors(diagnostics)
            else ArtifactSet.create(())
        ),
        diagnostics=tuple(diagnostics),
        model=model,
        catalog=catalog,
        selected=tuple(item.selected for item in selected_functions),
        lowered_functions=LoweredFunctionSet(
            tuple(item.function for item in selected_functions)
        ),
        render_plans=plans,
    )


def _select_and_lower(
    catalog: Catalog,
    targets: tuple[Target, ...],
) -> tuple[tuple[SelectedLoweredFunction, ...], tuple[Diagnostic, ...]]:
    selector = Selector()
    lowerer = Lowerer()
    selected_functions: list[SelectedLoweredFunction] = []
    diagnostics: list[Diagnostic] = []

    for target in sorted(targets, key=lambda item: item.sort_key()):
        selection = selector.select(catalog, target)
        diagnostics.extend(selection.diagnostics)
        if has_errors(selection.diagnostics):
            continue
        for selected in selection.selected:
            lowering = lowerer.lower(selected, catalog=catalog)
            diagnostics.extend(lowering.diagnostics)
            if lowering.function is not None:
                selected_functions.append(
                    SelectedLoweredFunction(
                        selected=selected,
                        function=lowering.function,
                    )
                )

    return tuple(selected_functions), tuple(diagnostics)


def _render_plans_from_lowered_functions(
    functions: tuple[SelectedLoweredFunction, ...],
) -> tuple[tuple[PrimitiveRenderPlan, ...], tuple[Diagnostic, ...]]:
    plans: list[PrimitiveRenderPlan] = []
    diagnostics: list[Diagnostic] = []
    for item in functions:
        plan, plan_diagnostics = _render_plan_from_lowered_function(item)
        diagnostics.extend(plan_diagnostics)
        if plan is not None:
            plans.append(plan)
    return tuple(plans), tuple(sorted(diagnostics, key=_diagnostic_sort_key))


def _render_plan_from_lowered_function(
    item: SelectedLoweredFunction,
) -> tuple[PrimitiveRenderPlan | None, tuple[Diagnostic, ...]]:
    backend_id = item.selected.target.backend
    function = item.function
    definition, diagnostics = _render_function_definition(backend_id, function)
    if diagnostics or definition is None:
        return None, diagnostics

    primitive_id = _primitive_id(function)
    record = PrimitiveRenderPlanRecord(
        primitive_id=PrimitiveRenderPlanPrimitiveId(primitive_id),
        presentation_sort_key=PrimitiveRenderSortKey(primitive_id),
        definitions=(RenderedPrimitiveDefinitionText(definition),),
        source=PrimitiveRenderPlanSource(str(function.source.path)),
    )

    if backend_id == "cpp":
        return (
            PrimitiveRenderPlan(
                backend_id=PrimitiveBackendId("cpp"),
                profile_name=PrimitiveProfileName(_SUPPORTED_PROFILE),
                logical_path=PrimitiveArtifactLogicalPath(_CPP_SCALAR_PROFILE_PATH),
                includes=(RenderedIncludeLine("#include <cstdint>"),),
                namespace_open=RenderedNamespaceText("namespace tsl {"),
                namespace_close=RenderedNamespaceText("}  // namespace tsl"),
                primitives=(record,),
                source=PrimitiveRenderPlanSource(str(function.source.path)),
            ),
            (),
        )
    if backend_id == "rust":
        return (
            PrimitiveRenderPlan(
                backend_id=PrimitiveBackendId("rust"),
                profile_name=PrimitiveProfileName(_SUPPORTED_PROFILE),
                logical_path=PrimitiveArtifactLogicalPath(_RUST_SCALAR_PROFILE_PATH),
                primitives=(record,),
                source=PrimitiveRenderPlanSource(str(function.source.path)),
            ),
            (),
        )
    return (
        None,
        (
            Diagnostic(
                severity="error",
                code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-BACKEND",
                message=(
                    f"parsed generated primitive bridge does not support "
                    f"backend {backend_id!r}"
                ),
                location=function.source,
            ),
        ),
    )


def _render_function_definition(
    backend_id: str,
    function: LoweredFunction,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    signature = function.signature
    scalar_type = _scalar_type_spelling(backend_id, signature.scalar_type)
    if scalar_type is None:
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-TYPE",
                    message=(
                        f"parsed generated primitive bridge has no {backend_id!r} "
                        f"spelling for scalar type {signature.scalar_type.tag!r}"
                    ),
                    location=function.source,
                ),
            ),
        )
    result_type = _result_type_spelling(signature.result_type, scalar_type)
    if result_type is None:
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-RESULT-TYPE",
                    message=(
                        "parsed generated primitive bridge has no "
                        f"{backend_id!r} spelling for result type "
                        f"{signature.result_type.result_id!r}"
                    ),
                    location=function.source,
                ),
            ),
        )
    expression, expression_diagnostics = _render_return_expression(
        backend_id,
        function,
    )
    if expression_diagnostics or expression is None:
        return None, expression_diagnostics

    if backend_id == "cpp":
        parameters = ", ".join(
            f"{scalar_type} {parameter.name}" for parameter in signature.parameters
        )
        return (
            "\n".join(
                (
                    f'inline constexpr const char* active_profile = "{_SUPPORTED_PROFILE}";',
                    'inline constexpr const char* active_profile_family = "generic";',
                    f"inline {result_type} {signature.name}({parameters}) {{",
                    f"  return {expression};",
                    "}",
                )
            ),
            (),
        )
    if backend_id == "rust":
        parameters = ", ".join(
            f"{parameter.name}: {scalar_type}" for parameter in signature.parameters
        )
        return (
            "\n".join(
                (
                    f'pub const ACTIVE_PROFILE: &str = "{_SUPPORTED_PROFILE}";',
                    'pub const ACTIVE_PROFILE_FAMILY: &str = "generic";',
                    f"pub fn {signature.name}({parameters}) -> {result_type} {{",
                    f"    {expression}",
                    "}",
                )
            ),
            (),
        )
    return (
        None,
        (
            Diagnostic(
                severity="error",
                code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-BACKEND",
                message=(
                    f"parsed generated primitive bridge does not support "
                    f"backend {backend_id!r}"
                ),
                location=function.source,
            ),
        ),
    )


def _render_return_expression(
    backend_id: str,
    function: LoweredFunction,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    expression = function.body.return_statement.expression
    if not isinstance(expression, LoweredBinaryOperationExpression):
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-EXPRESSION",
                    message=(
                        "parsed generated primitive bridge supports only the "
                        "accepted tiny lowered binary expression slice"
                    ),
                    location=function.body.return_statement.source,
                ),
            ),
        )
    operator_spelling = _binary_operation_spelling(backend_id, expression.operation)
    if operator_spelling is None:
        return (
            None,
            (
                Diagnostic(
                    severity="error",
                    code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-OPERATION",
                    message=(
                        f"parsed generated primitive bridge has no {backend_id!r} "
                        f"spelling for binary operation "
                        f"{expression.operation.operation_id!r}"
                    ),
                    location=function.body.return_statement.source,
                ),
            ),
        )
    return (
        f"{_parameter_name(expression.left)} "
        f"{operator_spelling} "
        f"{_parameter_name(expression.right)}",
        (),
    )


def _parameter_name(parameter: LoweredParameterRef) -> str:
    return parameter.parameter_name


def _scalar_type_spelling(
    backend_id: str,
    descriptor: ScalarTypeDescriptor,
) -> str | None:
    for rule in _SCALAR_TYPE_SPELLINGS:
        if rule.backend_id == backend_id and rule.type_tag == descriptor.tag:
            return rule.spelling
    return None


def _result_type_spelling(
    descriptor: LoweredResultType,
    scalar_spelling: str,
) -> str | None:
    if descriptor.result_id == INPUT_SCALAR_RESULT_TYPE.result_id:
        return scalar_spelling
    return None


def _binary_operation_spelling(
    backend_id: str,
    descriptor: BinaryOperationDescriptor,
) -> str | None:
    for rule in _BINARY_OPERATION_SPELLINGS:
        if (
            rule.backend_id == backend_id
            and rule.operation_id == descriptor.operation_id
        ):
            return rule.spelling
    return None


def _primitive_id(function: LoweredFunction) -> str:
    return (
        f"{function.signature.primitive_name}."
        f"{function.signature.scalar_type.tag}."
        f"{function.signature.name}"
    )


def _unsupported_profile_diagnostics(
    profile_set: GeneratedProfileSet,
) -> tuple[Diagnostic, ...]:
    profiles = profile_set.profiles
    if len(profiles) == 1 and str(profiles[0].name) == _SUPPORTED_PROFILE:
        return ()
    return (
        Diagnostic(
            severity="error",
            code="TSL-PARSED-GENERATED-PRIMITIVE-UNSUPPORTED-PROFILE-SET",
            message=(
                "M224 parsed generated primitive bridge supports only the "
                "single scalar generated profile"
            ),
        ),
    )


def _result(
    diagnostics: list[Diagnostic],
    *,
    model: GeneratedProjectRenderModel | None = None,
    catalog: Catalog | None = None,
    selected: tuple[SelectedImplementation, ...] = (),
    lowered_functions: LoweredFunctionSet = LoweredFunctionSet(()),
    render_plans: tuple[PrimitiveRenderPlan, ...] = (),
) -> ParsedTinyGeneratedProjectResult:
    return ParsedTinyGeneratedProjectResult(
        artifacts=ArtifactSet.create(()),
        diagnostics=tuple(diagnostics),
        model=model,
        catalog=catalog,
        selected=selected,
        lowered_functions=lowered_functions,
        render_plans=render_plans,
    )


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str]:
    return (diagnostic.code, diagnostic.message)
