"""Rust backend: render lowered functions as ``pub fn`` definitions.

Return framing and any required ``unsafe`` wrapping already live in
``function.body_text`` (decided during lowering via the backend translation), so
this emitter only places the function shape around it.
"""

from __future__ import annotations

from tslc.lower.lowerer import LoweredFunction


class RustBackend:
    backend_id = "rust"

    def render_function(self, function: LoweredFunction) -> str:
        parameters = ", ".join(
            f"{parameter.name}: {parameter.type_spelling}"
            for parameter in function.parameters
        )
        return (
            f"pub fn {function.name}({parameters}) -> {function.result_type} {{\n"
            f"    {function.body_text}\n"
            f"}}"
        )
