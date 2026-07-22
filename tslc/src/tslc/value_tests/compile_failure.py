"""Render isolated expected-compilation-failure cases."""

from __future__ import annotations

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.render._common import slug
from tslc.value_tests.case_helpers import sanitize
from tslc.value_tests.literals import cpp_literal_list, rust_literal_list
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProfilePlan

RUST_COMPILE_FAILURE_FEATURE = "tsl_compile_failures"


def compile_failure_target_name(
    profile: ValueTestProfilePlan,
    case: ValueTestCasePlan,
) -> str:
    if case.kind != "compile_failure":
        raise ValueError("compile-failure target naming requires a compile_failure case")
    return f"tsl_compile_failure_{slug(profile.profile_name)}_{sanitize(case.function_name)}"


def render_cpp_compile_failure(case: ValueTestCasePlan) -> str:
    lines = [
        '#include "tsl.hpp"',
        "",
        "int main() {",
        f"  using Vec = tsl::simd<{case.base_spelling}, tsl::generic<{case.lanes}>>;",
    ]
    args = _cpp_immediate_args(lines, case)
    template_args = _template_args(case)
    lines.extend(
        (
            f"  (void)tsl::{case.call_name}<{', '.join(template_args)}>"
            f"({', '.join(args)});",
            "  return 0;",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def render_rust_compile_failure(case: ValueTestCasePlan) -> str:
    lines = [
        "use tsl::profile::*;",
        "use tsl::tsl_core::*;",
        "",
        "fn main() {",
        f"    type Vec = Simd<{case.base_spelling}, Generic<{case.lanes}>>;",
    ]
    args = _rust_immediate_args(lines, case)
    template_args = _template_args(case)
    lines.extend(
        (
            f"    let _ = {rust_raw_identifier(case.call_name)}"
            f"::<{', '.join(template_args)}>({', '.join(args)});",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def _template_args(case: ValueTestCasePlan) -> list[str]:
    args = ["Vec"]
    if case.invocation.immediate is not None:
        args.append(case.invocation.immediate)
    args.extend(case.invocation.generic_defaults)
    return args


def _cpp_immediate_args(lines: list[str], case: ValueTestCasePlan) -> list[str]:
    for position, values in enumerate(case.inputs.vectors):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(
            f"  const {case.base_spelling} in{position}[{case.lanes}] = "
            f"{{{literals}}};"
        )
        lines.append(f"  typename Vec::register_type a{position}{{}};")
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
            f"a{position}[i] = in{position}[i];"
        )
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            args.append(f"a{vector_index}")
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"  typename Vec::mask_type m{mask_index} = "
                f"{case.inputs.masks[mask_index]}ull;"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        elif kind != "sImm":
            raise ValueError(f"unsupported compile-failure argument kind {kind!r}")
    return args


def _rust_immediate_args(lines: list[str], case: ValueTestCasePlan) -> list[str]:
    for position, values in enumerate(case.inputs.vectors):
        literals = rust_literal_list(values, case.type_tag)
        lines.append(
            f"    let in{position}: [{case.base_spelling}; {case.lanes}] = "
            f"[{literals}];"
        )
        lines.append(
            f"    let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(
            f"    for i in 0..{case.lanes} {{ a{position}[i] = in{position}[i]; }}"
        )
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            args.append(f"a{vector_index}")
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"    let m{mask_index}: <Vec as SimdVector>::MaskType = "
                f"{case.inputs.masks[mask_index]}u64;"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        elif kind != "sImm":
            raise ValueError(f"unsupported compile-failure argument kind {kind!r}")
    return args


__all__ = (
    "RUST_COMPILE_FAILURE_FEATURE",
    "compile_failure_target_name",
    "render_cpp_compile_failure",
    "render_rust_compile_failure",
)
