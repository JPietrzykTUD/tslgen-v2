"""Typed Rust artifact emitter for tiny lowered functions."""

from dataclasses import dataclass

from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata
from tslgen.lowering import (
    LoweredBinaryOperationExpression,
    LoweredFunction,
    LoweredUnaryOperationExpression,
)
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor
from tslgen.lowering.unary_operations import UnaryOperationDescriptor


@dataclass(frozen=True, slots=True)
class _ScalarTypeSpelling:
    tag: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _BinaryOperatorSpelling:
    operation_id: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _UnaryOperatorSpelling:
    operation_id: str
    spelling: str


_SCALAR_TYPE_SPELLINGS: tuple[_ScalarTypeSpelling, ...] = (
    _ScalarTypeSpelling(tag="si32", spelling="i32"),
    _ScalarTypeSpelling(tag="ui32", spelling="u32"),
    _ScalarTypeSpelling(tag="f32", spelling="f32"),
    _ScalarTypeSpelling(tag="f64", spelling="f64"),
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
    _UnaryOperatorSpelling(operation_id="bit_not", spelling="!"),
    _UnaryOperatorSpelling(operation_id="neg", spelling="-"),
)


class RustBackend:
    backend_id = "rust"

    def emit(self, function: LoweredFunction) -> BackendEmitResult:
        signature = function.signature
        scalar_spelling = _scalar_type_spelling(signature.scalar_type)
        if scalar_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            "Rust emitter has no spelling for scalar type "
                            f"{signature.scalar_type.tag!r}"
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
            scalar_spelling,
            return_expression,
        )
        return BackendEmitResult(
            artifact=Artifact(
                logical_path=f"src/{signature.name}.rs",
                content=content,
                media_type="text/x-rust",
                metadata=(
                    ArtifactMetadata("backend", "rust"),
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
                        "Rust emitter has no operator spelling for operation "
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
                message="Rust emitter supports only lowered binary and unary expressions",
                location=function.source,
            )

        operator_spelling = _unary_operator_spelling(expression.operation)
        if operator_spelling is None:
            return Diagnostic(
                severity="error",
                code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                message=(
                    "Rust emitter has no operator spelling for operation "
                    f"{expression.operation.operation_id!r}"
                ),
                location=function.source,
            )
        return f"{operator_spelling}{expression.value.parameter_name}"

    def _render_function(
        self,
        function: LoweredFunction,
        scalar_spelling: str,
        return_expression: str,
    ) -> str:
        signature = function.signature
        parameters = ", ".join(
            f"{parameter.name}: {scalar_spelling}" for parameter in signature.parameters
        )
        return (
            f"pub fn {signature.name}"
            f"({parameters})"
            f" -> {scalar_spelling} {{\n"
            f"    {return_expression}\n"
            "}\n"
        )


def _scalar_type_spelling(descriptor: ScalarTypeDescriptor) -> str | None:
    for spelling in _SCALAR_TYPE_SPELLINGS:
        if spelling.tag == descriptor.tag:
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
