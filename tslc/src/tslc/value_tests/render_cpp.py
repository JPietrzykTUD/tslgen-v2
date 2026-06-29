"""Render C++ value-test plans."""

from __future__ import annotations

from tslc.value_tests._render_cpp_dispatch import CPP_VALUE_TEST_RENDERER, render_cpp_case
from tslc.value_tests.model import ValueTestProfilePlan

CPP_VALUE_TEST_SUPPORT = CPP_VALUE_TEST_RENDERER.backend_support()


def render_cpp_values_runner(profile: ValueTestProfilePlan) -> str:
    functions = [render_cpp_case(case) for case in profile.cases]
    body = "\n\n".join(functions)
    call_lines = "\n".join(f"  failures += {case.function_name}();" for case in profile.cases)
    support_includes = "".join(
        f'#include "{header}"\n' for header in profile.support_headers
    )
    return (
        "#include <tsl.hpp>\n"
        '#include "tsl_test_core.hpp"\n'
        f"{support_includes}"
        "#include <cmath>\n"
        "#include <cstddef>\n"
        "#include <cstdint>\n"
        "#include <cstdio>\n\n"
        "#include <cstdlib>\n"
        "#include <string>\n"
        "#include <vector>\n\n"
        "namespace {\n\n"
        f"{body}\n\n"
        "}  // namespace\n\n"
        "int main() {\n"
        "  int failures = 0;\n"
        f"{call_lines}\n"
        "  if (failures != 0) {\n"
        '    std::fprintf(stderr, "%d lane failure(s)\\n", failures);\n'
        "    return 1;\n"
        "  }\n"
        "  return 0;\n"
        "}\n"
    )


__all__ = ["CPP_VALUE_TEST_SUPPORT", "render_cpp_values_runner"]
