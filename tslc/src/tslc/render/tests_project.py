"""Render generated value-correctness tests.

The oracle is the **generic software impl** — emitted for every profile and parametric in
``LANES``. For the golden layer we exercise it directly: ``simd<T, generic<N>>::register_type``
*is* an indexable ``array_type<T, N>``, so a case's ``inputs`` go straight into a register and
the result is read straight back, with no construction/readback primitives in the closure. The
hand-authored ``{inputs, expected}`` cases thus pin the reference's absolute correctness; the
differential layer (a later increment) compares each hardware specialization against this same
reference.

This module emits the test sources only; the build wiring (a `tsl_values_<profile>` executable
run under ctest) lives in the C++ CMake template, and failures are surfaced by the verify step.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.render._common import asset, slug, text

if TYPE_CHECKING:
    from tslc.render.project import ProfileRender


def cpp_test_artifacts(
    profiles: tuple[ProfileRender, ...],
    catalog: Catalog | None,
) -> list[Artifact]:
    """The C++ value-test sources: the shared helper asset plus one runner per profile.

    A runner is always emitted (even with zero cases) so the `tsl_values` CMake target and its
    ctest registration stay valid regardless of which primitives were generated."""

    artifacts = [text("cpp/include/tsl_test_core.hpp", asset("tsl_test_core.hpp"))]
    for profile_render in profiles:
        source = _cpp_values_runner(profile_render, catalog)
        artifacts.append(
            text(f"cpp/tests/values_{slug(profile_render.profile.name)}.cpp", source)
        )
    return artifacts


def _cpp_values_runner(profile_render: ProfileRender, catalog: Catalog | None) -> str:
    functions: list[str] = []
    calls: list[str] = []
    if catalog is not None:
        for name in sorted(profile_render.cpp):
            specs = profile_render.cpp[name]
            primitive = catalog.primitive(name, unmasked=True)
            if primitive is None or not _is_golden_elementwise(specs[0]):
                continue
            for index, case in enumerate(primitive.tests):
                emitted = _cpp_golden_case(name, index, case, specs)
                if emitted is not None:
                    function, call = emitted
                    functions.append(function)
                    calls.append(call)

    body = "\n\n".join(functions)
    call_lines = "\n".join(f"  failures += {call}();" for call in calls)
    return (
        "#include <tsl.hpp>\n"
        '#include "tsl_test_core.hpp"\n'
        "#include <cmath>\n"
        "#include <cstddef>\n"
        "#include <cstdint>\n"
        "#include <cstdio>\n\n"
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


def _is_golden_elementwise(spec: LoweredSpecialization) -> bool:
    """A lane-local primitive the golden generator handles today: vector result, all-vector
    params, and none of the extra axes (mask/immediate/axis/generic-params/repr-change)."""

    return (
        spec.result_kind == "v"
        and all(kind == "v" for kind in spec.param_kinds)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_golden_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    if base_spelling is None:
        return None
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if len(vector_inputs) != len(specs[0].param_kinds):
        return None  # arity must match the all-vector signature
    is_float = case.type_tag.startswith("f")
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    lanes = case.lanes
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
    ]
    arg_names: list[str] = []
    for position, arg in enumerate(vector_inputs):
        literals = ", ".join(_cpp_literal(v, is_float) for v in arg.values)
        lines.append(f"  static const {base_spelling} in{position}[{lanes}] = {{{literals}}};")
        lines.append(f"  typename Vec::register_type a{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {lanes}; ++i) a{position}[i] = in{position}[i];"
        )
        arg_names.append(f"a{position}")
    expected = ", ".join(_cpp_literal(v, is_float) for v in case.expected)
    lines.append(f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};")
    lines.append(f"  typename Vec::register_type result = tsl::{name}<Vec>({', '.join(arg_names)});")
    lines.append(
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});'
    )
    lines.append("}")
    return "\n".join(lines), fn_name


def _base_spelling(
    specs: tuple[LoweredSpecialization, ...], type_tag: str
) -> str | None:
    for spec in specs:
        if spec.type_tag == type_tag:
            return spec.base_type_spelling
    return None


def _cpp_literal(token: str, is_float: bool) -> str:
    upper = token.upper()
    if upper in ("INFINITY", "+INFINITY"):
        return "INFINITY"
    if upper == "-INFINITY":
        return "-INFINITY"
    if upper in ("NAN", "+NAN"):
        return "NAN"
    return token


def _sanitize(text_value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text_value)


__all__ = ["cpp_test_artifacts"]
