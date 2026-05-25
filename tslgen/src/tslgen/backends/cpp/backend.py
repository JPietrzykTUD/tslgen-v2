"""Typed C++ artifact emitter for tiny lowered functions."""

from dataclasses import dataclass

from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata
from tslgen.lowering import (
    INPUT_SCALAR_RESULT_TYPE,
    LoweredBinaryOperationExpression,
    LoweredComparisonOperationExpression,
    LoweredFunction,
    LoweredResultType,
    LoweredUnaryOperationExpression,
)
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.comparison_operations import ComparisonOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor


@dataclass(frozen=True, slots=True)
class _ScalarTypeSpelling:
    tag: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _ResultTypeSpelling:
    result_id: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _BinaryOperatorSpelling:
    operation_id: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _UnaryOperatorSpelling:
    operation_id: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _ComparisonOperatorSpelling:
    operation_id: str
    spelling: str


_SCALAR_TYPE_SPELLINGS: tuple[_ScalarTypeSpelling, ...] = (
    _ScalarTypeSpelling(tag="si32", spelling="std::int32_t"),
    _ScalarTypeSpelling(tag="ui32", spelling="std::uint32_t"),
    _ScalarTypeSpelling(tag="f32", spelling="float"),
    _ScalarTypeSpelling(tag="f64", spelling="double"),
)

_RESULT_TYPE_SPELLINGS: tuple[_ResultTypeSpelling, ...] = (
    _ResultTypeSpelling(result_id="scalar_comparison", spelling="bool"),
)

_BINARY_OPERATOR_SPELLINGS: tuple[_BinaryOperatorSpelling, ...] = (
    _BinaryOperatorSpelling(operation_id="add", spelling="+"),
    _BinaryOperatorSpelling(operation_id="sub", spelling="-"),
    _BinaryOperatorSpelling(operation_id="mul", spelling="*"),
    _BinaryOperatorSpelling(operation_id="div", spelling="/"),
    _BinaryOperatorSpelling(operation_id="mod", spelling="%"),
    _BinaryOperatorSpelling(operation_id="bit_and", spelling="&"),
    _BinaryOperatorSpelling(operation_id="bit_or", spelling="|"),
    _BinaryOperatorSpelling(operation_id="bit_xor", spelling="^"),
    _BinaryOperatorSpelling(operation_id="shift_left", spelling="<<"),
    _BinaryOperatorSpelling(operation_id="shift_right", spelling=">>"),
)

_UNARY_OPERATOR_SPELLINGS: tuple[_UnaryOperatorSpelling, ...] = (
    _UnaryOperatorSpelling(operation_id="bit_not", spelling="~"),
    _UnaryOperatorSpelling(operation_id="neg", spelling="-"),
)

_COMPARISON_OPERATOR_SPELLINGS: tuple[_ComparisonOperatorSpelling, ...] = (
    _ComparisonOperatorSpelling(operation_id="equal", spelling="=="),
    _ComparisonOperatorSpelling(operation_id="nequal", spelling="!="),
    _ComparisonOperatorSpelling(operation_id="less_than", spelling="<"),
    _ComparisonOperatorSpelling(operation_id="greater_than", spelling=">"),
    _ComparisonOperatorSpelling(operation_id="less_than_or_equal", spelling="<="),
    _ComparisonOperatorSpelling(operation_id="greater_than_or_equal", spelling=">="),
)


class CppBackend:
    backend_id = "cpp"

    def emit(self, function: LoweredFunction) -> BackendEmitResult:
        signature = function.signature
        parameter_spelling = _scalar_type_spelling(signature.scalar_type)
        if parameter_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            "C++ emitter has no spelling for scalar type "
                            f"{signature.scalar_type.tag!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        return_type_spelling = _result_type_spelling(
            signature.result_type,
            parameter_spelling,
        )
        if return_type_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-RESULT-TYPE",
                        message=(
                            "C++ emitter has no spelling for result type "
                            f"{signature.result_type.result_id!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        return_expression = self._render_return_expression(function)
        if isinstance(return_expression, Diagnostic):
            return BackendEmitResult(
                artifact=None,
                diagnostics=(return_expression,),
            )

        content = self._render_function(
            function,
            parameter_spelling,
            return_type_spelling,
            return_expression,
        )
        return BackendEmitResult(
            artifact=Artifact(
                logical_path=f"include/tsl/{signature.name}.hpp",
                content=content,
                media_type="text/x-c++hdr",
                metadata=(
                    ArtifactMetadata("backend", "cpp"),
                    ArtifactMetadata("primitive", signature.primitive_name),
                ),
            ),
            diagnostics=(),
        )

    def _render_return_expression(
        self,
        function: LoweredFunction,
    ) -> str | Diagnostic:
        expression = function.body.return_statement.expression
        if isinstance(expression, LoweredBinaryOperationExpression):
            operator_spelling = _binary_operator_spelling(expression.operation)
            if operator_spelling is None:
                return Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                    message=(
                        "C++ emitter has no operator spelling for operation "
                        f"{expression.operation.operation_id!r}"
                    ),
                    location=function.source,
                )
            return (
                f"{expression.left.parameter_name} "
                f"{operator_spelling} "
                f"{expression.right.parameter_name}"
            )

        if isinstance(expression, LoweredComparisonOperationExpression):
            operator_spelling = _comparison_operator_spelling(expression.operation)
            if operator_spelling is None:
                return Diagnostic(
                    severity="error",
                    code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                    message=(
                        "C++ emitter has no operator spelling for operation "
                        f"{expression.operation.operation_id!r}"
                    ),
                    location=function.source,
                )
            return (
                f"{expression.left.parameter_name} "
                f"{operator_spelling} "
                f"{expression.right.parameter_name}"
            )

        if not isinstance(expression, LoweredUnaryOperationExpression):
            return Diagnostic(
                severity="error",
                code="TSL-BACKEND-UNSUPPORTED-EXPRESSION",
                message=(
                    "C++ emitter supports only lowered binary, unary, and "
                    "comparison expressions"
                ),
                location=function.source,
            )

        operator_spelling = _unary_operator_spelling(expression.operation)
        if operator_spelling is None:
            return Diagnostic(
                severity="error",
                code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                message=(
                    "C++ emitter has no operator spelling for operation "
                    f"{expression.operation.operation_id!r}"
                ),
                location=function.source,
            )
        return f"{operator_spelling}{expression.value.parameter_name}"

    def _render_function(
        self,
        function: LoweredFunction,
        parameter_spelling: str,
        return_type_spelling: str,
        return_expression: str,
    ) -> str:
        signature = function.signature
        parameters = ", ".join(
            f"{parameter_spelling} {parameter.name}"
            for parameter in signature.parameters
        )
        return (
            "#pragma once\n"
            "\n"
            "#include <cstdint>\n"
            "\n"
            "namespace tsl {\n"
            "\n"
            f"inline {return_type_spelling} {signature.name}"
            f"({parameters}) {{\n"
            f"  return {return_expression};\n"
            "}\n"
            "\n"
            "}  // namespace tsl\n"
        )


def _scalar_type_spelling(descriptor: ScalarTypeDescriptor) -> str | None:
    for spelling in _SCALAR_TYPE_SPELLINGS:
        if spelling.tag == descriptor.tag:
            return spelling.spelling
    return None


def _result_type_spelling(
    descriptor: LoweredResultType,
    scalar_spelling: str,
) -> str | None:
    if descriptor.result_id == INPUT_SCALAR_RESULT_TYPE.result_id:
        return scalar_spelling
    for spelling in _RESULT_TYPE_SPELLINGS:
        if spelling.result_id == descriptor.result_id:
            return spelling.spelling
    return None


def _binary_operator_spelling(
    descriptor: BinaryOperationDescriptor,
) -> str | None:
    for spelling in _BINARY_OPERATOR_SPELLINGS:
        if spelling.operation_id == descriptor.operation_id:
            return spelling.spelling
    return None


def _unary_operator_spelling(
    descriptor: UnaryOperationDescriptor,
) -> str | None:
    for spelling in _UNARY_OPERATOR_SPELLINGS:
        if spelling.operation_id == descriptor.operation_id:
            return spelling.spelling
    return None


def _comparison_operator_spelling(
    descriptor: ComparisonOperationDescriptor,
) -> str | None:
    for spelling in _COMPARISON_OPERATOR_SPELLINGS:
        if spelling.operation_id == descriptor.operation_id:
            return spelling.spelling
    return None
