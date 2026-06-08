"""C++ backend: render lowered functions as inline definitions."""

from __future__ import annotations

from tslc.lower.lowerer import LoweredFunction


class CppBackend:
    backend_id = "cpp"

    def render_function(self, function: LoweredFunction) -> str:
        parameters = ", ".join(
            f"{parameter.type_spelling} {parameter.name}"
            for parameter in function.parameters
        )
        return (
            f"inline {function.result_type} {function.name}({parameters}) {{\n"
            f"  {function.body_text}\n"
            f"}}"
        )
