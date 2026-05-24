"""Typed Rust artifact emitter for tiny lowered binary functions."""

from dataclasses import dataclass

from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata
from tslgen.lowering import LoweredFunction
from tslgen.lowering.binary_operations import BinaryOperationDescriptor
from tslgen.lowering.scalar_types import ScalarTypeDescriptor


@dataclass(frozen=True, slots=True)
class _ScalarTypeSpelling:
    tag: str
    spelling: str


@dataclass(frozen=True, slots=True)
class _BinaryOperatorSpelling:
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

        return_statement = function.body.return_statement
        expression = return_statement.expression
        operator_spelling = _binary_operator_spelling(expression.operation)
        if operator_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                        message=(
                            "Rust emitter has no operator spelling for operation "
                            f"{expression.operation.operation_id!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        content = self._render_binary_function(
            function,
            scalar_spelling,
            operator_spelling,
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

    def _render_binary_function(
        self,
        function: LoweredFunction,
        scalar_spelling: str,
        operator_spelling: str,
    ) -> str:
        signature = function.signature
        expression = function.body.return_statement.expression
        left = expression.left.parameter_name
        right = expression.right.parameter_name
        parameters = ", ".join(
            f"{parameter.name}: {scalar_spelling}" for parameter in signature.parameters
        )
        return (
            f"pub fn {signature.name}"
            f"({parameters})"
            f" -> {scalar_spelling} {{\n"
            f"    {left} {operator_spelling} {right}\n"
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
