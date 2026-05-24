"""Typed Rust artifact emitter for the M107 fixture shape."""

from tslgen.analysis.selection import SelectedImplementation
from tslgen.backends.base import BackendEmitResult
from tslgen.core.diagnostics import Diagnostic
from tslgen.domain.catalog import BinaryAddBody
from tslgen.io.artifacts import Artifact, ArtifactMetadata


class RustBackend:
    backend_id = "rust"

    def emit(self, selected: SelectedImplementation) -> BackendEmitResult:
        if selected.target.backend != self.backend_id:
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-MISMATCH",
                        message=(
                            f"Rust emitter received target backend "
                            f"{selected.target.backend!r}"
                        ),
                        location=selected.implementation.source,
                    ),
                ),
            )

        if selected.target.type_tag != "si32":
            return BackendEmitResult(
                artifact=None,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TSL-BACKEND-UNSUPPORTED-TYPE",
                        message=(
                            f"Rust emitter supports only type 'si32' in M107; "
                            f"got {selected.target.type_tag!r}"
                        ),
                        location=selected.implementation.source,
                    ),
                ),
            )

        body = selected.implementation.body
        content = self._render_add_function(selected, body)
        function_name = _function_name(selected)
        return BackendEmitResult(
            artifact=Artifact(
                logical_path=f"src/{function_name}.rs",
                content=content,
                media_type="text/x-rust",
                metadata=(
                    ArtifactMetadata("backend", "rust"),
                    ArtifactMetadata("primitive", selected.primitive.name),
                ),
            ),
            diagnostics=(),
        )

    def _render_add_function(
        self,
        selected: SelectedImplementation,
        body: BinaryAddBody,
    ) -> str:
        function_name = _function_name(selected)
        left = body.left_parameter
        right = body.right_parameter
        return (
            f"pub fn {function_name}({left}: i32, {right}: i32) -> i32 {{\n"
            f"    {left} + {right}\n"
            "}\n"
        )


def _function_name(selected: SelectedImplementation) -> str:
    return (
        f"{selected.primitive.name}_"
        f"{selected.target.extension}_"
        f"{selected.target.type_tag}"
    )
