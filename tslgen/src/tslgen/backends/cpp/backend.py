"""Typed C++ artifact emitter for tiny lowered binary functions."""

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
    _ScalarTypeSpelling(tag="si32", spelling="std::int32_t"),
    _ScalarTypeSpelling(tag="ui32", spelling="std::uint32_t"),
    _ScalarTypeSpelling(tag="f32", spelling="float"),
    _ScalarTypeSpelling(tag="f64", spelling="double"),
)

_BINARY_OPERATOR_SPELLINGS: tuple[_BinaryOperatorSpelling, ...] = (
    _BinaryOperatorSpelling(operation_id="add", spelling="+"),
    _BinaryOperatorSpelling(operation_id="sub", spelling="-"),
    _BinaryOperatorSpelling(operation_id="mul", spelling="*"),
)


class CppBackend:
    backend_id = "cpp"

    def emit(self, function: LoweredFunction) -> BackendEmitResult:
        scalar_spelling = _scalar_type_spelling(function.scalar_type)
        if scalar_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            "C++ emitter has no spelling for scalar type "
                            f"{function.scalar_type.tag!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        operator_spelling = _binary_operator_spelling(function.expression.operation)
        if operator_spelling is None:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-OPERATION",
                        message=(
                            "C++ emitter has no operator spelling for operation "
                            f"{function.expression.operation.operation_id!r}"
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
                logical_path=f"include/tsl/{function.name}.hpp",
                content=content,
                media_type="text/x-c++hdr",
                metadata=(
                    ArtifactMetadata("backend", "cpp"),
                    ArtifactMetadata("primitive", function.primitive_name),
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
        left = function.expression.left.parameter_name
        right = function.expression.right.parameter_name
        return (
            "#pragma once\n"
            "\n"
            "#include <cstdint>\n"
            "\n"
            "namespace tsl {\n"
            "\n"
            f"inline {scalar_spelling} {function.name}"
            f"({scalar_spelling} {left}, {scalar_spelling} {right}) {{\n"
            f"  return {left} {operator_spelling} {right};\n"
            "}\n"
            "\n"
            "}  // namespace tsl\n"
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
