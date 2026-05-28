"""Selected-implementation lowering for the exact tiny clean operation bodies."""

from collections.abc import Iterable
from dataclasses import dataclass

from tslgen.analysis.selection import SelectedImplementation
from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import (
    Catalog,
    ImplementationBody,
    LowerableDirective,
    LowerableOperationFragment,
    NamedPrimitiveReference,
    PrimitiveCall,
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
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredFunction,
    LoweredFunctionBody,
    LoweredFunctionSet,
    LoweredFunctionSignature,
    LoweredParameter,
    LoweredParameterRef,
    LoweredReturnStatement,
    LoweredResultType,
    LoweredUnaryOperationExpression,
    SelectedImplementationLoweringContext,
    SelectedTypeEnvironment,
    BackendTypeQueryLoweringResult,
    PrimitiveCallArgumentBindingResult,
    PrimitiveCallSelectorPayloadLoweringResult,
    PrimitiveCallSelectorPayload,
    PrimitiveCallTargetMatch,
    PrimitiveCallTargetMatchingResult,
    TypeExpressionLoweringResult,
    build_selected_implementation_lowering_context,
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
from tslgen.lowering.primitive_call_diagnostics import (
    unsupported_primitive_call_diagnostics,
    unsupported_primitive_call_diagnostics_from_payload_tokens,
)
from tslgen.lowering.primitive_call_arguments import (
    lower_primitive_call_argument_bindings,
)
from tslgen.lowering.primitive_call_targets import lower_primitive_call_target_match
from tslgen.lowering.selector_payload import lower_primitive_call_selector_payload
from tslgen.lowering.unary_operations import (
    UnaryOperationDescriptor,
    lookup_unary_operation_descriptor,
    supported_unary_operation_ids,
)

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

    def lower_primitive_call_selector_payload(
        self,
        selected: SelectedImplementation,
        primitive_call: PrimitiveCall,
        *,
        catalog: Catalog,
        environment: SelectedTypeEnvironment | None = None,
    ) -> PrimitiveCallSelectorPayloadLoweringResult:
        context = self.context_for(selected)
        selected_environment = (
            environment
            if environment is not None
            else build_selected_type_environment(context)
        )
        return lower_primitive_call_selector_payload(
            context,
            catalog,
            primitive_call,
            selected_environment,
        )

    def lower_primitive_call_target_match(
        self,
        selected: SelectedImplementation,
        selector_payload: PrimitiveCallSelectorPayload,
        *,
        catalog: Catalog,
    ) -> PrimitiveCallTargetMatchingResult:
        return lower_primitive_call_target_match(
            self.context_for(selected),
            catalog,
            selector_payload,
        )

    def lower_primitive_call_argument_bindings(
        self,
        selected: SelectedImplementation,
        primitive_call: PrimitiveCall,
        selector_payload: PrimitiveCallSelectorPayload,
        target_match: PrimitiveCallTargetMatch,
        *,
        catalog: Catalog,
    ) -> PrimitiveCallArgumentBindingResult:
        _ = (selected, selector_payload, catalog)
        return lower_primitive_call_argument_bindings(
            primitive_call,
            target_match,
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
        context = self.context_for(selected)
        scalar_type = lookup_scalar_type_descriptor(context.type_tag)
        body = context.implementation.body
        fragment = _operation_fragment_from_selected_body(selected, body)
        if context.template == _SUPPORTED_COMPARISON_TEMPLATE:
            operation = lookup_comparison_operation_descriptor(context.primitive_name)
            diagnostics = tuple(
                _unsupported_comparison_diagnostics(
                    selected,
                    body,
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
            diagnostics = tuple(
                _unsupported_unary_diagnostics(
                    selected,
                    body,
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
            diagnostics = tuple(
                _unsupported_binary_diagnostics(
                    selected,
                    body,
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
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: BinaryOperationDescriptor | None,
    catalog: Catalog | None,
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

    if fragment is None:
        directive = _emit_return_directive_from_body(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := unsupported_primitive_call_diagnostics(
            body,
            selected=selected,
            catalog=catalog,
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


def _unsupported_comparison_diagnostics(
    selected: SelectedImplementation,
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: ComparisonOperationDescriptor | None,
    catalog: Catalog | None,
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

    if fragment is None:
        directive = _emit_return_directive_from_body(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := unsupported_primitive_call_diagnostics(
            body,
            selected=selected,
            catalog=catalog,
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


def _unsupported_unary_diagnostics(
    selected: SelectedImplementation,
    body: ImplementationBody,
    fragment: LowerableOperationFragment | None,
    scalar_type: ScalarTypeDescriptor | None,
    operation: UnaryOperationDescriptor | None,
    catalog: Catalog | None,
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

    if fragment is None:
        directive = _emit_return_directive_from_body(body)
        if directive is not None:
            diagnostics.extend(
                _unsupported_emit_return_diagnostics(
                    directive,
                    selected=selected,
                    catalog=catalog,
                )
            )
        elif primitive_call_diagnostics := unsupported_primitive_call_diagnostics(
            body,
            selected=selected,
            catalog=catalog,
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


def _operation_fragment_from_selected_body(
    selected: SelectedImplementation,
    body: ImplementationBody,
) -> LowerableOperationFragment | None:
    fragment = _operation_fragment_from_body(body)
    if fragment is not None:
        return fragment
    return _exact_add_primitive_call_fragment_from_body(selected, body)


def _operation_fragment_from_body(
    body: ImplementationBody,
) -> LowerableOperationFragment | None:
    if len(body.tokens) != 1:
        return None
    segment = body.tokens[0]
    if not isinstance(segment, LowerableOperationFragment):
        return None
    return segment


def _exact_add_primitive_call_fragment_from_body(
    selected: SelectedImplementation,
    body: ImplementationBody,
) -> LowerableOperationFragment | None:
    if len(body.tokens) != 1:
        return None

    segment = body.tokens[0]
    if not isinstance(segment, LowerableDirective):
        return None

    if segment.name == "emit_return":
        if len(segment.payload_tokens) != 1:
            return None
        payload_token = segment.payload_tokens[0]
        if not isinstance(payload_token, LowerableDirective):
            return None
        return _exact_add_primitive_call_fragment_from_directive(
            selected,
            payload_token,
        )

    return _exact_add_primitive_call_fragment_from_directive(selected, segment)


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


def _emit_return_directive_from_body(
    body: ImplementationBody,
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
    body: ImplementationBody,
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
    )


def _function_name(context: SelectedImplementationLoweringContext) -> str:
    return (
        f"{context.primitive_name}_"
        f"{context.extension}_"
        f"{context.type_tag}"
    )
