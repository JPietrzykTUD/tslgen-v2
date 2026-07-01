"""Render C++ value-test plans."""

from __future__ import annotations

from tslc.compiler_assets import RenderAssets
from tslc.value_tests._render_cpp_dispatch import CPP_VALUE_TEST_RENDERER, render_cpp_case
from tslc.value_tests.model import ValueTestProfilePlan

CPP_VALUE_TEST_SUPPORT = CPP_VALUE_TEST_RENDERER.backend_support()


def render_cpp_values_runner(
    profile: ValueTestProfilePlan, assets: RenderAssets
) -> str:
    functions = [render_cpp_case(case) for case in profile.cases]
    body = "\n\n".join(functions)
    call_lines = "\n".join(f"  failures += {case.function_name}();" for case in profile.cases)
    support_includes = "".join(
        f'#include "{header}"\n' for header in profile.support_headers
    )
    return assets.fill(
        "cpp_value_tests.cpp.tmpl",
        support_includes=support_includes,
        body=body,
        call_lines=call_lines,
    )


__all__ = ["CPP_VALUE_TEST_SUPPORT", "render_cpp_values_runner"]
