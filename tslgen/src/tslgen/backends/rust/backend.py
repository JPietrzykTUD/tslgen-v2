"""Typed Rust artifact emitter for the tiny lowered add function."""

from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.io.artifacts import Artifact, ArtifactMetadata
from tslgen.lowering import LoweredFunction


class RustBackend:
    backend_id = "rust"

    def emit(self, function: LoweredFunction) -> BackendEmitResult:
        if function.scalar_type_tag != "si32":
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            f"Rust emitter supports only type 'si32' in M107; "
                            f"got {function.scalar_type_tag!r}"
                        ),
                        location=function.source,
                    ),
                ),
            )

        content = self._render_add_function(function)
        return BackendEmitResult(
            artifact=Artifact(
                logical_path=f"src/{function.name}.rs",
                content=content,
                media_type="text/x-rust",
                metadata=(
                    ArtifactMetadata("backend", "rust"),
                    ArtifactMetadata("primitive", function.primitive_name),
                ),
            ),
            diagnostics=(),
        )

    def _render_add_function(self, function: LoweredFunction) -> str:
        left = function.expression.left.parameter_name
        right = function.expression.right.parameter_name
        return (
            f"pub fn {function.name}({left}: i32, {right}: i32) -> i32 {{\n"
            f"    {left} + {right}\n"
            "}\n"
        )
