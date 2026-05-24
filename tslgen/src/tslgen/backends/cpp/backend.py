"""Typed C++ artifact emitter for the tiny lowered add function."""

from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata
from tslgen.lowering import LoweredFunction


class CppBackend:
    backend_id = "cpp"

    def emit(self, function: LoweredFunction) -> BackendEmitResult:
        if function.scalar_type_tag != "si32":
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            f"C++ emitter supports only type 'si32' in M107; "
                            f"got {function.scalar_type_tag!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        content = self._render_add_function(function)
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

    def _render_add_function(self, function: LoweredFunction) -> str:
        left = function.expression.left.parameter_name
        right = function.expression.right.parameter_name
        return (
            "#pragma once\n"
            "\n"
            "#include <cstdint>\n"
            "\n"
            "namespace tsl {\n"
            "\n"
            f"inline std::int32_t {function.name}"
            f"(std::int32_t {left}, std::int32_t {right}) {{\n"
            f"  return {left} + {right};\n"
            "}\n"
            "\n"
            "}  // namespace tsl\n"
        )
