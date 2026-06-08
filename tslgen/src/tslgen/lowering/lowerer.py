"""Selected-implementation lowering for the exact tiny clean operation bodies."""

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    BodyToken,
    Catalog,
    LowerableDirective,
    LowerableOperationFragment,
    NamedPrimitiveReference,
    RawStringToken,
)
from tslgen.lowering.binary_operations import (
    BinaryOperationDescriptor,
    lookup_binary_operation_descriptor,
    supported_binary_operation_ids,
)
from tslgen.lowering.comparison_operations import (
    ComparisonOperationDescriptor,
    lookup_comparison_operation_descriptor,
    supported_comparison_operation_ids,
)
from tslgen.lowering.model import (
    INPUT_SCALAR_RESULT_TYPE,
    SCALAR_COMPARISON_RESULT_TYPE,
    BackendControlDirectiveDiscoveryLoweringResult,
    BackendIntrinsicDiscovery,
    BackendIntrinsicDiscoveryLoweringResult,
    BackendIntrinsicHandoffLoweringResult,
    BackendTypeQueryDiscoveryLoweringResult,
    BackendTypeQueryDiscovery,
    BackendTypeQueryHandoffLoweringResult,
    SourceOperationDiscovery,
    SourceOperationDiscoveryLoweringResult,
    SourceOperationHandoffLoweringResult,
    BackendValueQueryDiscoveryLoweringResult,
    BackendValueQueryDiscovery,
    BackendValueQueryHandoffLoweringResult,
    MaskLaneConstantDiscoveryLoweringResult,
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredPrimitiveCallExpression,
    LoweredReturnStatement,
    LoweredResultType,
    LoweredUnaryOperationExpression,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    BackendTypeQueryLoweringResult,
    GenerationLoopDiscoveryLoweringResult,
    GenerationVariableDeclarationDiscoveryLoweringResult,
    GenerationControlRegionLoweringResult,
    GenerationLoopRegionLoweringResult,
    GenerationValueQueryLoweringResult,
    PrimitiveCallClosureLoweringPackage,
    PrimitiveCallExpressionLoweringResult,
    TypeExpressionLoweringResult,
    build_selected_implementation_lowering_context,
)
from tslgen.lowering.backend_control import discover_backend_control_directives
from tslgen.lowering.backend_intrinsic_handoff import lower_backend_intrinsic_discovery
from tslgen.lowering.backend_intrinsics import discover_backend_intrinsic_requests
from tslgen.lowering.backend_output_source_islands import (
    BackendOutputDiscoveryLoweringResult,
    discover_backend_output_requests,
)
from tslgen.lowering.backend_type_queries import discover_backend_type_queries
from tslgen.lowering.backend_type_queries import lower_backend_type_query_discovery
from tslgen.lowering.backend_value_queries import discover_backend_value_queries
from tslgen.lowering.backend_value_queries import lower_backend_value_query_discovery
from tslgen.lowering.mask_lane_constants import discover_mask_lane_constant_requests
from tslgen.lowering.mask_keywords import discover_mask_keyword_requests
from tslgen.lowering.mask_keywords import MaskKeywordDiscoveryLoweringResult
from tslgen.lowering.source_operation_handoff import lower_source_operation_discovery
from tslgen.lowering.source_operations import discover_source_operation_requests
from tslgen.lowering.generation_control import lower_generation_control_region
from tslgen.lowering.generation_loops import (
    discover_generation_loop_regions,
    lower_generation_loop_region,
)
from tslgen.lowering.generation_variables import (
    discover_generation_variable_declarations,
)
from tslgen.lowering.generation_values import (
    lower_generation_expression,
    lower_generation_value_query,
)
from tslgen.lowering.operation_type_compatibility import (
    binary_operation_supports_scalar_type,
    supported_scalar_type_tags_for_binary_operation,
    supported_scalar_type_tags_for_unary_operation,
    unary_operation_supports_scalar_type,
)
from tslgen.lowering.scalar_types import (
    ScalarTypeDescriptor,
    lookup_scalar_type_descriptor,
    supported_scalar_type_tags,
)
from tslgen.lowering.type_queries import (
    build_selected_type_environment,
    lower_backend_type_query,
    lower_generation_type_query,
    lower_type_expression,
)
from tslgen.lowering.primitive_calls import (
    PrimitiveCallDependencyCollector,
    PrimitiveCallResolver,
    unsupported_primitive_call_diagnostics_from_body_tokens,
    unsupported_primitive_call_diagnostics_from_payload_tokens,
)
from tslgen.lowering.source_body_fragments import (
    compatibility_body_token_result_from_fragment_sequence,
)
from tslgen.lowering.unary_operations import (
    UnaryOperationDescriptor,
    lookup_unary_operation_descriptor,
    supported_unary_operation_ids,
)
from tslgen.syntax.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    SourceBodyFragmentSequence,
)
from tslgen.syntax.source_body_regions import SourceBodyKeyword

_SUPPORTED_BINARY_TEMPLATE = "binary"
_SUPPORTED_UNARY_TEMPLATE = "unary"
_SUPPORTED_COMPARISON_TEMPLATE = "compare"
_SUPPORTED_EXTENSION = "scalar"
_SUPPORTED_BINARY_PARAMETERS = ("left", "right")
_SUPPORTED_UNARY_PARAMETERS = ("value",)
_SUPPORTED_COMPARISON_PARAMETERS = ("left", "right")
_SUPPORTED_EXACT_PRIMITIVE_CALL_TARGET = "add"
_SUPPORTED_EXACT_PRIMITIVE_CALL_PAYLOAD = "left, right"


@dataclass(frozen=True, slots=True)
class LoweringResult:
    function: LoweredFunction | None
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class LoweringStageResult:
    lowered_functions: LoweredFunctionSet
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True, slots=True)
class _SelectedBodyTokenView:
    tokens: tuple[BodyToken, ...]
    source: SourceLocation
    diagnostics: tuple[Diagnostic, ...]


class Lowerer:
    """Lower only the selected scalar operation implementation shapes."""

    def context_for(
        self,
        selected: SelectedImplementation,
    ) -> SelectedImplementationLoweringContext:
        return build_selected_implementation_lowering_context(selected)

    def type_environment_for(
        self,
        selected: SelectedImplementation,
    ) -> SelectedTypeEnvironment:
        context = self.context_for(selected)
        return build_selected_type_environment(context)

    def lower_type_expression(
        self,
        selected: SelectedImplementation,
        expression: str,
        source: SourceLocation,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> TypeExpressionLoweringResult:
        context = self.context_for(selected)
        return lower_type_expression(
            context,
            expression,
            source,
            environment=environment,
        )

    def lower_backend_type_query(
        self,
        selected: SelectedImplementation,
        query: str,
        source: SourceLocation,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> BackendTypeQueryLoweringResult:
        context = self.context_for(selected)
        return lower_backend_type_query(
            context,
            query,
            source,
            environment=environment,
        )

    def lower_generation_type_query(
        self,
        selected: SelectedImplementation,
        query: str,
        source: SourceLocation,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> TypeExpressionLoweringResult:
        context = self.context_for(selected)
        return lower_generation_type_query(
            context,
            query,
            source,
            environment=environment,
        )

    def lower_generation_value_query(
        self,
        selected: SelectedImplementation,
        query: str,
        source: SourceLocation,
        *,
        catalog: Catalog | None = None,
        environment: SelectedTypeEnvironment | None = None,
    ) -> GenerationValueQueryLoweringResult:
        context = self.context_for(selected)
        return lower_generation_value_query(
            context,
            query,
            source,
            catalog=catalog,
            environment=environment,
        )

    def lower_generation_expression(
        self,
        selected: SelectedImplementation,
        expression: str,
        source: SourceLocation,
        *,
        catalog: Catalog | None = None,
        environment: SelectedTypeEnvironment | None = None,
    ) -> GenerationValueQueryLoweringResult:
        context = self.context_for(selected)
        return lower_generation_expression(
            context,
            expression,
            source,
            catalog=catalog,
            environment=environment,
        )

    def lower_generation_control_region(
        self,
        selected: SelectedImplementation,
        *,
        catalog: Catalog | None = None,
        environment: SelectedTypeEnvironment | None = None,
    ) -> GenerationControlRegionLoweringResult:
        context = self.context_for(selected)
        return lower_generation_control_region(
            context,
            catalog=catalog,
            environment=environment,
        )

    def lower_generation_loop_region(
        self,
        selected: SelectedImplementation,
        *,
        catalog: Catalog | None = None,
        environment: SelectedTypeEnvironment | None = None,
    ) -> GenerationLoopRegionLoweringResult:
        context = self.context_for(selected)
        return lower_generation_loop_region(
            context,
            catalog=catalog,
            environment=environment,
        )

    def discover_generation_loop_regions(
        self,
        selected: SelectedImplementation,
        *,
        catalog: Catalog | None = None,
        environment: SelectedTypeEnvironment | None = None,
    ) -> GenerationLoopDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_generation_loop_regions(
            context,
            catalog=catalog,
            environment=environment,
        )

    def discover_generation_variable_declarations(
        self,
        selected: SelectedImplementation,
    ) -> GenerationVariableDeclarationDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_generation_variable_declarations(context)

    def discover_backend_value_queries(
        self,
        selected: SelectedImplementation,
    ) -> BackendValueQueryDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_backend_value_queries(context)

    def lower_backend_value_query_discovery(
        self,
        selected: SelectedImplementation,
        discovery: BackendValueQueryDiscovery,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> BackendValueQueryHandoffLoweringResult:
        context = self.context_for(selected)
        return lower_backend_value_query_discovery(
            context,
            discovery,
            environment=environment,
        )

    def discover_backend_type_queries(
        self,
        selected: SelectedImplementation,
    ) -> BackendTypeQueryDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_backend_type_queries(context)

    def lower_backend_type_query_discovery(
        self,
        selected: SelectedImplementation,
        discovery: BackendTypeQueryDiscovery,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> BackendTypeQueryHandoffLoweringResult:
        context = self.context_for(selected)
        return lower_backend_type_query_discovery(
            context,
            discovery,
            environment=environment,
        )

    def discover_mask_lane_constant_requests(
        self,
        selected: SelectedImplementation,
    ) -> MaskLaneConstantDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_mask_lane_constant_requests(context)

    def discover_mask_keyword_requests(
        self,
        selected: SelectedImplementation,
    ) -> MaskKeywordDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_mask_keyword_requests(context)

    def discover_backend_control_directives(
        self,
        selected: SelectedImplementation,
    ) -> BackendControlDirectiveDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_backend_control_directives(context)

    def discover_backend_intrinsic_requests(
        self,
        selected: SelectedImplementation,
    ) -> BackendIntrinsicDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_backend_intrinsic_requests(context)

    def discover_backend_output_requests(
        self,
        selected: SelectedImplementation,
    ) -> BackendOutputDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_backend_output_requests(context)

    def lower_backend_intrinsic_discovery(
        self,
        selected: SelectedImplementation,
        discovery: BackendIntrinsicDiscovery,
        *,
        environment: SelectedTypeEnvironment | None = None,
    ) -> BackendIntrinsicHandoffLoweringResult:
        context = self.context_for(selected)
        return lower_backend_intrinsic_discovery(
            context,
            discovery,
            environment=environment,
        )

    def discover_source_operation_requests(
        self,
        selected: SelectedImplementation,
    ) -> SourceOperationDiscoveryLoweringResult:
        context = self.context_for(selected)
        return discover_source_operation_requests(context)

    def lower_source_operation_discovery(
        self,
        selected: SelectedImplementation,
        discovery: SourceOperationDiscovery,
    ) -> SourceOperationHandoffLoweringResult:
        context = self.context_for(selected)
        return lower_source_operation_discovery(context, discovery)

    def lower_primitive_call_closure_lowering_package(
        self,
        root: SelectedImplementation,
        *,
        catalog: Catalog,
    ) -> PrimitiveCallClosureLoweringPackage:
        closure = PrimitiveCallDependencyCollector(catalog).dependency_closure(root)
        lowering_result = self.lower_all(
            closure.selected,
            catalog=catalog,
        )
        return PrimitiveCallClosureLoweringPackage(
            closure=closure,
            lowered_functions=lowering_result.lowered_functions,
            diagnostics=closure.diagnostics + lowering_result.diagnostics,
        )

    def lower_all(
        self,
        selected: Iterable[SelectedImplementation],
        *,
        catalog: Catalog | None = None,
    ) -> LoweringStageResult:
        functions: list[LoweredFunction] = []
        diagnostics: list[Diagnostic] = []

        for item in selected:
            result = self.lower(item, catalog=catalog)
            diagnostics.extend(result.diagnostics)
            if result.function is not None:
                functions.append(result.function)

        return LoweringStageResult(
            lowered_functions=LoweredFunctionSet(tuple(functions)),
            diagnostics=tuple(diagnostics),
        )

    def lower(
        self,
        selected: SelectedImplementation,
        *,
        catalog: Catalog | None = None,
    ) -> LoweringResult:
        if _is_generation_control_region_candidate(selected):
            context = self.context_for(selected)
            branch_result = lower_generation_control_region(
                context,
                catalog=catalog,
            )
            if branch_result.region is None:
                return LoweringResult(
                    function=None,
                    diagnostics=branch_result.diagnostics,
                )
            branch_body_view = _SelectedBodyTokenView(
                tokens=branch_result.region.selected_branch.tokens,
                source=branch_result.region.selected_branch.source,
                diagnostics=(),
            )
            return self._lower_direct_body_view(
                selected,
                branch_body_view,
                catalog=catalog,
            )

        return self._lower_direct_body(selected, catalog=catalog)

    def _lower_direct_body(
        self,
        selected: SelectedImplementation,
        *,
        catalog: Catalog | None = None,
    ) -> LoweringResult:
        body_view = _selected_body_token_view(selected)
        return self._lower_direct_body_view(
            selected,
            body_view,
            catalog=catalog,
        )

    def _lower_direct_body_view(
        self,
        selected: SelectedImplementation,
        body_view: _SelectedBodyTokenView,
        *,
        catalog: Catalog | None = None,
    ) -> LoweringResult:
        context = self.context_for(selected)
        scalar_type = lookup_scalar_type_descriptor(context.type_tag)
        if body_view.diagnostics:
            return LoweringResult(function=None, diagnostics=body_view.diagnostics)

        fragment = _operation_fragment_from_selected_body(selected, body_view)
        call_expression_result = (
            _primitive_call_expression_result_from_return_payload(
                selected,
                body_view,
                catalog,
            )
        )
        if context.template == _SUPPORTED_COMPARISON_TEMPLATE:
            operation = lookup_comparison_operation_descriptor(context.primitive_name)
            if fragment is None and call_expression_result is not None:
                diagnostics = (
                    _unsupported_comparison_capability_diagnostics(
                        selected,
                        scalar_type,
                        operation,
                    )
                    + call_expression_result.diagnostics
                )
                if (
                    diagnostics
                    or scalar_type is None
                    or operation is None
                    or call_expression_result.expression is None
                ):
                    return LoweringResult(function=None, diagnostics=diagnostics)
                return LoweringResult(
                    function=_lower_function_with_expression(
                        context,
                        scalar_type,
                        call_expression_result.expression,
                        result_type=SCALAR_COMPARISON_RESULT_TYPE,
                    ),
                    diagnostics=(),
                )
            diagnostics = tuple(
                _unsupported_comparison_diagnostics(
                    selected,
                    body_view,
                    fragment,
                    scalar_type,
                    operation,
                    catalog,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)
            return LoweringResult(
                function=_lower_comparison_function(
                    context,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        if context.template == _SUPPORTED_UNARY_TEMPLATE:
            operation = lookup_unary_operation_descriptor(context.primitive_name)
            if fragment is None and call_expression_result is not None:
                diagnostics = (
                    _unsupported_unary_capability_diagnostics(
                        selected,
                        scalar_type,
                        operation,
                    )
                    + call_expression_result.diagnostics
                )
                if (
                    diagnostics
                    or scalar_type is None
                    or operation is None
                    or call_expression_result.expression is None
                ):
                    return LoweringResult(function=None, diagnostics=diagnostics)

                return LoweringResult(
                    function=_lower_function_with_expression(
                        context,
                        scalar_type,
                        call_expression_result.expression,
                    ),
                    diagnostics=(),
                )
            diagnostics = tuple(
                _unsupported_unary_diagnostics(
                    selected,
                    body_view,
                    fragment,
                    scalar_type,
                    operation,
                    catalog,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)

            return LoweringResult(
                function=_lower_unary_function(
                    context,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        if context.template == _SUPPORTED_BINARY_TEMPLATE:
            operation = lookup_binary_operation_descriptor(context.primitive_name)
            if fragment is None and call_expression_result is not None:
                diagnostics = (
                    _unsupported_binary_capability_diagnostics(
                        selected,
                        scalar_type,
                        operation,
                    )
                    + call_expression_result.diagnostics
                )
                if (
                    diagnostics
                    or scalar_type is None
                    or operation is None
                    or call_expression_result.expression is None
                ):
                    return LoweringResult(function=None, diagnostics=diagnostics)
                return LoweringResult(
                    function=_lower_function_with_expression(
                        context,
                        scalar_type,
                        call_expression_result.expression,
                    ),
                    diagnostics=(),
                )
            diagnostics = tuple(
                _unsupported_binary_diagnostics(
                    selected,
                    body_view,
                    fragment,
                    scalar_type,
                    operation,
                    catalog,
                )
            )
            if (
                diagnostics
                or scalar_type is None
                or operation is None
                or fragment is None
            ):
                return LoweringResult(function=None, diagnostics=diagnostics)
            return LoweringResult(
                function=_lower_binary_function(
                    context,
                    fragment,
                    scalar_type,
                    operation,
                ),
                diagnostics=(),
            )

        diagnostics = (
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {context.primitive_name!r} uses template "
                    f"{context.template!r}; expected one of: "
                    f"{_SUPPORTED_BINARY_TEMPLATE}, {_SUPPORTED_UNARY_TEMPLATE}, "
                    f"{_SUPPORTED_COMPARISON_TEMPLATE}"
                ),
                location=context.primitive_source,
            )
        )
        return LoweringResult(function=None, diagnostics=diagnostics)


def _unsupported_binary_diagnostics(
    selected: SelectedImplementation,
    body: _SelectedBodyTokenView,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: BinaryOperationDescriptor | None,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    diagnostics = list(
        _unsupported_binary_capability_diagnostics(
            selected,
            scalar_type,
            operation,
        )
    )

    if fragment is None:
        directive = _emit_return_directive_from_body_view(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := (
            unsupported_primitive_call_diagnostics_from_body_tokens(
                body.tokens,
                selected=selected,
                catalog=catalog,
            )
        ):
            diagnostics.extend(primitive_call_diagnostics)
        else:
            diagnostics.append(
                _unsupported_body_shape_diagnostic(
                    body,
                    _SUPPORTED_BINARY_PARAMETERS,
                    selected.primitive.name,
                )
            )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_BINARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(left, right)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_binary_capability_diagnostics(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor | None,
    operation: BinaryOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if operation is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION",
                message=(
                    f"operation {selected.primitive.name!r} cannot be lowered; "
                    "expected one of: "
                    f"{', '.join(supported_binary_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_BINARY_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_BINARY_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_BINARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_BINARY_PARAMETERS!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.implementation.extension != _SUPPORTED_EXTENSION:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-EXTENSION",
                message=(
                    f"implementation extension "
                    f"{selected.implementation.extension!r} cannot be lowered by "
                    f"the tiny clean lowerer; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if scalar_type is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    "cannot be lowered; expected one of: "
                    f"{', '.join(supported_scalar_type_tags())}"
                ),
                location=selected.implementation.source,
            )
        )

    if (
        operation is not None
        and scalar_type is not None
        and not binary_operation_supports_scalar_type(operation, scalar_type)
    ):
        supported_type_tags = supported_scalar_type_tags_for_binary_operation(operation)
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION-TYPE",
                message=(
                    f"operation {operation.operation_id!r} cannot be lowered for "
                    f"scalar type {scalar_type.tag!r}; expected one of: "
                    f"{', '.join(supported_type_tags)}"
                ),
                location=selected.implementation.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_comparison_diagnostics(
    selected: SelectedImplementation,
    body: _SelectedBodyTokenView,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: ComparisonOperationDescriptor | None,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    diagnostics = list(
        _unsupported_comparison_capability_diagnostics(
            selected,
            scalar_type,
            operation,
        )
    )

    if fragment is None:
        directive = _emit_return_directive_from_body_view(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := (
            unsupported_primitive_call_diagnostics_from_body_tokens(
                body.tokens,
                selected=selected,
                catalog=catalog,
            )
        ):
            diagnostics.extend(primitive_call_diagnostics)
        else:
            diagnostics.append(
                _unsupported_body_shape_diagnostic(
                    body,
                    _SUPPORTED_COMPARISON_PARAMETERS,
                    selected.primitive.name,
                )
            )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_COMPARISON_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(left, right)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_comparison_capability_diagnostics(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor | None,
    operation: ComparisonOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if operation is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION",
                message=(
                    f"operation {selected.primitive.name!r} cannot be lowered; "
                    "expected one of: "
                    f"{', '.join(supported_comparison_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_COMPARISON_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_COMPARISON_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_COMPARISON_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_COMPARISON_PARAMETERS!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.implementation.extension != _SUPPORTED_EXTENSION:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-EXTENSION",
                message=(
                    f"implementation extension "
                    f"{selected.implementation.extension!r} cannot be lowered by "
                    f"the tiny clean lowerer; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if scalar_type is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    "cannot be lowered; expected one of: "
                    f"{', '.join(supported_scalar_type_tags())}"
                ),
                location=selected.implementation.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_unary_diagnostics(
    selected: SelectedImplementation,
    body: _SelectedBodyTokenView,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: UnaryOperationDescriptor | None,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    diagnostics = list(
        _unsupported_unary_capability_diagnostics(
            selected,
            scalar_type,
            operation,
        )
    )

    if fragment is None:
        directive = _emit_return_directive_from_body_view(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := (
            unsupported_primitive_call_diagnostics_from_body_tokens(
                body.tokens,
                selected=selected,
                catalog=catalog,
            )
        ):
            diagnostics.extend(primitive_call_diagnostics)
        else:
            diagnostics.append(
                _unsupported_body_shape_diagnostic(
                    body,
                    _SUPPORTED_UNARY_PARAMETERS,
                    selected.primitive.name,
                )
            )
    elif (
        operation is not None
        and fragment.operation != operation.source_body_operation
    ):
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-OPERATION-MISMATCH",
                message=(
                    f"primitive operation {selected.primitive.name!r} expects "
                    f"body operation {operation.source_body_operation!r}; got "
                    f"{fragment.operation!r}"
                ),
                location=fragment.source,
            )
        )

    if fragment is not None and fragment.arguments != _SUPPORTED_UNARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-BODY",
                message=(
                    "implementation body cannot be lowered; expected exactly "
                    f"'{fragment.operation}(value)'"
                ),
                location=fragment.source,
            )
        )

    return tuple(diagnostics)


def _unsupported_unary_capability_diagnostics(
    selected: SelectedImplementation,
    scalar_type: ScalarTypeDescriptor | None,
    operation: UnaryOperationDescriptor | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if operation is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION",
                message=(
                    f"operation {selected.primitive.name!r} cannot be lowered; "
                    "expected one of: "
                    f"{', '.join(supported_unary_operation_ids())}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.template != _SUPPORTED_UNARY_TEMPLATE:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TEMPLATE",
                message=(
                    f"primitive {selected.primitive.name!r} uses template "
                    f"{selected.primitive.template!r}; expected "
                    f"{_SUPPORTED_UNARY_TEMPLATE!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.primitive.parameters != _SUPPORTED_UNARY_PARAMETERS:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-PARAMETERS",
                message=(
                    f"primitive {selected.primitive.name!r} uses parameters "
                    f"{selected.primitive.parameters!r}; expected exactly "
                    f"{_SUPPORTED_UNARY_PARAMETERS!r}"
                ),
                location=selected.primitive.source,
            )
        )

    if selected.implementation.extension != _SUPPORTED_EXTENSION:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-EXTENSION",
                message=(
                    f"implementation extension "
                    f"{selected.implementation.extension!r} cannot be lowered by "
                    f"the tiny clean lowerer; expected {_SUPPORTED_EXTENSION!r}"
                ),
                location=selected.implementation.source,
            )
        )

    if scalar_type is None:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-TYPE",
                message=(
                    f"implementation type {selected.implementation.type_tag!r} "
                    "cannot be lowered; expected one of: "
                    f"{', '.join(supported_scalar_type_tags())}"
                ),
                location=selected.implementation.source,
            )
        )

    if (
        operation is not None
        and scalar_type is not None
        and not unary_operation_supports_scalar_type(operation, scalar_type)
    ):
        supported_type_tags = supported_scalar_type_tags_for_unary_operation(operation)
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="TSL-LOWER-UNSUPPORTED-OPERATION-TYPE",
                message=(
                    f"operation {operation.operation_id!r} cannot be lowered for "
                    f"scalar type {scalar_type.tag!r}; expected one of: "
                    f"{', '.join(supported_type_tags)}"
                ),
                location=selected.implementation.source,
            )
        )

    return tuple(diagnostics)


def _is_generation_control_region_candidate(selected: SelectedImplementation) -> bool:
    fragments = selected.implementation.source_body_fragments
    if fragments is not None:
        fragment = _first_non_whitespace_fragment(fragments)
        return (
            isinstance(fragment, KeywordRegionFragment)
            and fragment.keyword is SourceBodyKeyword.IF
            and fragment.source_region.selector is not None
            and fragment.source_region.selector.payload_span.text.strip()
            == "generation"
        )

    tokens = selected.implementation.body.tokens
    if not tokens:
        return False
    token = tokens[0]
    return (
        isinstance(token, LowerableDirective)
        and token.name == "if"
        and len(token.arguments) == 2
        and token.arguments[0] == "generation"
    )


def _first_non_whitespace_fragment(
    fragments: SourceBodyFragmentSequence,
):
    for fragment in fragments.fragments:
        if isinstance(fragment, RawSourceFragment) and fragment.span.text.strip() == "":
            continue
        return fragment
    return None


def _selected_body_token_view(
    selected: SelectedImplementation,
) -> _SelectedBodyTokenView:
    body = selected.implementation.body
    fragments = selected.implementation.source_body_fragments
    if fragments is not None:
        result = compatibility_body_token_result_from_fragment_sequence(fragments)
        tokens = _trim_direct_body_boundary_tokens(tuple(result.tokens))
        return _SelectedBodyTokenView(
            tokens=tokens,
            source=body.source,
            diagnostics=result.diagnostics,
        )

    return _body_token_view(body.tokens, body.source)


def _body_token_view(
    tokens: tuple[BodyToken, ...],
    source: SourceLocation,
) -> _SelectedBodyTokenView:
    return _SelectedBodyTokenView(
        tokens=tokens,
        source=source,
        diagnostics=(),
    )


def _trim_direct_body_boundary_tokens(
    tokens: tuple[BodyToken, ...],
) -> tuple[BodyToken, ...]:
    start = 0
    end = len(tokens)
    while start < end and _is_direct_body_boundary_token(tokens[start]):
        start += 1
    while end > start and _is_direct_body_boundary_token(tokens[end - 1]):
        end -= 1
    return tokens[start:end]


def _is_direct_body_boundary_token(token: BodyToken) -> bool:
    return isinstance(token, RawStringToken) and token.text.strip() in {"", ";"}


def _operation_fragment_from_selected_body(
    selected: SelectedImplementation,
    body: _SelectedBodyTokenView,
) -> LowerableOperationFragment | None:
    fragment = _operation_fragment_from_token_sequence(selected, body.tokens)
    if fragment is not None:
        return fragment
    directive = _emit_return_directive_from_body_view(body)
    if directive is None:
        return None
    return _operation_fragment_from_token_sequence(selected, directive.payload_tokens)


def _operation_fragment_from_token_sequence(
    selected: SelectedImplementation,
    tokens: Iterable[object],
) -> LowerableOperationFragment | None:
    token_sequence = tuple(tokens)
    if len(token_sequence) != 1:
        return None
    segment = token_sequence[0]
    if isinstance(segment, LowerableOperationFragment):
        return segment
    if isinstance(segment, LowerableDirective):
        return _exact_add_primitive_call_fragment_from_directive(selected, segment)
    return None


def _exact_add_primitive_call_fragment_from_directive(
    selected: SelectedImplementation,
    directive: LowerableDirective,
) -> LowerableOperationFragment | None:
    if selected.primitive.name != "add":
        return None
    if selected.primitive.template != _SUPPORTED_BINARY_TEMPLATE:
        return None
    if directive.name != "call":
        return None
    if not _is_exact_add_primitive_call_directive(directive):
        return None

    return LowerableOperationFragment(
        operation="add",
        arguments=_SUPPORTED_BINARY_PARAMETERS,
        source=directive.source,
    )


def _is_exact_add_primitive_call_directive(
    directive: LowerableDirective,
) -> bool:
    primitive_call = directive.primitive_call
    if primitive_call is None:
        return directive.arguments == (
            "primitive",
            _SUPPORTED_EXACT_PRIMITIVE_CALL_TARGET,
            _SUPPORTED_EXACT_PRIMITIVE_CALL_PAYLOAD,
        )

    selector = primitive_call.selector
    if not isinstance(selector.target, NamedPrimitiveReference):
        return False
    argument_texts = tuple(argument.text for argument in primitive_call.arguments)
    return (
        selector.target.name == _SUPPORTED_EXACT_PRIMITIVE_CALL_TARGET
        and selector.specialization is None
        and selector.attrs is None
        and primitive_call.payload == _SUPPORTED_EXACT_PRIMITIVE_CALL_PAYLOAD
        and argument_texts == _SUPPORTED_BINARY_PARAMETERS
    )


def _primitive_call_expression_result_from_return_payload(
    selected: SelectedImplementation,
    body: _SelectedBodyTokenView,
    catalog: Catalog | None,
) -> PrimitiveCallExpressionLoweringResult | None:
    if catalog is None:
        return None

    directive = _emit_return_directive_from_body_view(body)
    if directive is None or len(directive.payload_tokens) != 1:
        return None

    payload_token = directive.payload_tokens[0]
    if not isinstance(payload_token, LowerableDirective):
        return None
    if payload_token.name != "call" or payload_token.primitive_call is None:
        return None

    return PrimitiveCallResolver(catalog).lower_expression(
        selected,
        payload_token.primitive_call,
    )


def _emit_return_directive_from_body_view(
    body: _SelectedBodyTokenView,
) -> LowerableDirective | None:
    if len(body.tokens) != 1:
        return None
    segment = body.tokens[0]
    if not isinstance(segment, LowerableDirective):
        return None
    if segment.name != "emit_return":
        return None
    return segment


def _unsupported_emit_return_diagnostics(
    directive: LowerableDirective,
    *,
    selected: SelectedImplementation,
    catalog: Catalog | None,
) -> tuple[Diagnostic, ...]:
    primitive_call_diagnostics = unsupported_primitive_call_diagnostics_from_payload_tokens(
        directive.payload_tokens,
        selected=selected,
        catalog=catalog,
    )
    if primitive_call_diagnostics:
        return primitive_call_diagnostics
    return (_unsupported_return_expression_diagnostic(directive),)


def _unsupported_return_expression_diagnostic(
    directive: LowerableDirective,
) -> Diagnostic:
    payload = directive.arguments[0] if directive.arguments else ""
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-RETURN-EXPRESSION",
        message=(
            "emit_return directive payload cannot be lowered yet; "
            f"payload remains opaque: {payload!r}"
        ),
        location=directive.source,
    )


def _unsupported_body_shape_diagnostic(
    body: _SelectedBodyTokenView,
    expected_arguments: tuple[str, ...],
    operation_id: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-BODY",
        message=(
            "implementation body cannot be lowered; expected exactly one "
            "lowerable operation token "
            f"'{operation_id}({', '.join(expected_arguments)})'"
        ),
        location=body.source,
    )


def _lower_binary_function(
    context: SelectedImplementationLoweringContext,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: BinaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(context, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredBinaryOperationExpression(
                    operation=operation,
                    left=LoweredParameterRef(fragment.arguments[0]),
                    right=LoweredParameterRef(fragment.arguments[1]),
                ),
                source=fragment.source,
            ),
        ),
        source=context.implementation_source,
    )


def _lower_comparison_function(
    context: SelectedImplementationLoweringContext,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: ComparisonOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(
            context,
            scalar_type,
            result_type=SCALAR_COMPARISON_RESULT_TYPE,
        ),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredComparisonOperationExpression(
                    operation=operation,
                    left=LoweredParameterRef(fragment.arguments[0]),
                    right=LoweredParameterRef(fragment.arguments[1]),
                ),
                source=fragment.source,
            ),
        ),
        source=context.implementation_source,
    )


def _lower_unary_function(
    context: SelectedImplementationLoweringContext,
    fragment: LowerableOperationFragment,
    scalar_type: ScalarTypeDescriptor,
    operation: UnaryOperationDescriptor,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(context, scalar_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=LoweredUnaryOperationExpression(
                    operation=operation,
                    value=LoweredParameterRef(fragment.arguments[0]),
                ),
                source=fragment.source,
            ),
        ),
        source=context.implementation_source,
    )


def _lower_function_with_expression(
    context: SelectedImplementationLoweringContext,
    scalar_type: ScalarTypeDescriptor,
    expression: LoweredPrimitiveCallExpression,
    *,
    result_type: LoweredResultType = INPUT_SCALAR_RESULT_TYPE,
) -> LoweredFunction:
    return LoweredFunction(
        signature=_signature(context, scalar_type, result_type=result_type),
        body=LoweredFunctionBody(
            return_statement=LoweredReturnStatement(
                expression=expression,
                source=expression.reference.source,
            ),
        ),
        source=context.implementation_source,
    )


def _signature(
    context: SelectedImplementationLoweringContext,
    scalar_type: ScalarTypeDescriptor,
    *,
    result_type: LoweredResultType = INPUT_SCALAR_RESULT_TYPE,
) -> LoweredFunctionSignature:
    return LoweredFunctionSignature(
        name=_function_name(context),
        primitive_name=context.primitive_name,
        parameters=tuple(
            LoweredParameter(name=name) for name in context.parameter_names
        ),
        scalar_type=scalar_type,
        result_type=result_type,
        signature_shape=context.signature_model,
    )


def _function_name(context: SelectedImplementationLoweringContext) -> str:
    return (
        f"{context.primitive_name}_"
        f"{context.extension}_"
        f"{context.type_tag}"
    )
