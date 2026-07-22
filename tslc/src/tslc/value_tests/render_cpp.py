"""Render C++ value-test plans."""

from __future__ import annotations

from tslc.compiler_assets import RenderAssets
from tslc.value_tests._render_cpp_dispatch import CPP_VALUE_TEST_RENDERER, render_cpp_case
from tslc.value_tests.case_plan import ValueTestCasePlan
from tslc.value_tests.model import ValueTestProfilePlan

CPP_VALUE_TEST_SUPPORT = CPP_VALUE_TEST_RENDERER.backend_support()


def render_cpp_values_runner(
    profile: ValueTestProfilePlan, assets: RenderAssets
) -> str:
    functions = [
        _guarded(render_cpp_case(case), case) for case in profile.runner_cases
    ]
    body = "\n\n".join(functions)
    call_lines = "\n".join(
        _guarded(f"  failures += {case.function_name}();", case)
        for case in profile.runner_cases
    )
    support_includes = "".join(
        f'#include "{header}"\n' for header in profile.support_headers
    )
    return assets.fill(
        "cpp_value_tests.cpp.tmpl",
        support_includes=support_includes,
        body=body,
        call_lines=call_lines,
    )


def _guarded(text: str, case: ValueTestCasePlan) -> str:
    guarded = text
    for feature in reversed(case.required_compiler_features):
        guarded = (
            "#if defined(__has_feature)\n"
            f"#  if __has_feature({feature})\n"
            f"{guarded}\n"
            "#  endif\n"
            "#endif"
        )
    if case.header_group is not None:
        macro = f"TSL_ENABLE_{case.header_group.upper()}"
        guarded = f"#if defined({macro})\n{guarded}\n#endif"
    return guarded


__all__ = ["CPP_VALUE_TEST_SUPPORT", "render_cpp_values_runner"]
