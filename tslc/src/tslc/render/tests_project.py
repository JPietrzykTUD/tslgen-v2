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
    # Differential tests build a hardware register via the round-trip harness; emit them only
    # when those primitives are present in this project (seeded by `test_harness`).
    harness_ready = {"from_array", "to_array"} <= set(profile_render.cpp)
    if catalog is not None:
        for name in sorted(profile_render.cpp):
            specs = profile_render.cpp[name]
            primitive = catalog.primitive(name, unmasked=True)
            if primitive is None or not _is_golden_supported(specs[0]):
                continue
            for index, case in enumerate(primitive.tests):
                emitted = _cpp_golden_case(name, index, case, specs)
                if emitted is not None:
                    function, call = emitted
                    functions.append(function)
                    calls.append(call)
                # Differential: only when the round-trip harness is in this project, and only for
                # vector results today (a mask result's hardware normalization comes later).
                if harness_ready and specs[0].result_kind == "v":
                    for diff in _cpp_differential_cases(name, index, case, specs, catalog):
                        functions.append(diff[0])
                        calls.append(diff[1])

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


def _is_golden_supported(spec: LoweredSpecialization) -> bool:
    """A primitive the golden generator handles today: a vector OR mask result with all-vector
    params and none of the extra axes (masked variant/immediate/axis/generic-params/repr-change).
    Both run against the generic reference — a vector result is read back as an array, a mask
    result as the reference's integer-bitset mask."""

    return (
        spec.result_kind in ("v", "m")
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
    if len(case.expected) != case.lanes:
        return None  # per-lane expected required (buffer-shaped store cases handled later)
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
    call = f"tsl::{name}<Vec>({', '.join(arg_names)})"
    if specs[0].result_kind == "m":
        # A mask result: the reference's mask is an integer bitset; assert which lanes are set.
        expected_set = ", ".join("1" if _token_truthy(v) else "0" for v in case.expected)
        lines.append(f"  static const int expected[{lanes}] = {{{expected_set}}};")
        lines.append(f"  typename Vec::mask_type result = {call};")
        lines.append(f'  return tsl::test::check_mask("{case.name}", result, expected, {lanes});')
    else:
        expected = ", ".join(_cpp_literal(v, is_float) for v in case.expected)
        lines.append(f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};")
        lines.append(f"  typename Vec::register_type result = {call};")
        lines.append(
            f'  return tsl::test::check_lanes<{base_spelling}>('
            f'"{case.name}", result, expected, {lanes});'
        )
    lines.append("}")
    return "\n".join(lines), fn_name


def _cpp_differential_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
) -> list[tuple[str, str]]:
    """Differential cases: run each width-matching hardware specialization on the case inputs and
    assert lane-equality with the generic reference at the same lane count. No corpus ``expected``
    is consulted — the reference IS the oracle; this catches hardware-intrinsic divergence."""

    if case.lanes is None or case.expected_rule is not None:
        return []
    base_spelling = _base_spelling(specs, case.type_tag)
    type_bits = _type_bits(case.type_tag)
    if base_spelling is None or type_bits is None:
        return []
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if len(vector_inputs) != len(specs[0].param_kinds):
        return []
    lanes = case.lanes
    is_float = case.type_tag.startswith("f")
    emitted: list[tuple[str, str]] = []
    for spec in specs:
        if spec.uses_sized_vector or spec.extension_name == "scalar":
            continue  # the generic reference and scalar are not hardware subjects
        if spec.type_tag != case.type_tag:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits != lanes * type_bits:
            continue  # width-pinned: only the specialization holding exactly `lanes` lanes
        fn_name = f"test_{name}_diff_{spec.extension_name}_{index}_{_sanitize(case.name)}"
        lines = [
            f"int {fn_name}() {{",
            f"  using Hw = tsl::simd<{base_spelling}, tsl::{spec.extension_name}>;",
            f"  using Ref = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        ]
        hw_args: list[str] = []
        ref_args: list[str] = []
        for position, arg in enumerate(vector_inputs):
            literals = ", ".join(_cpp_literal(v, is_float) for v in arg.values)
            lines.append(
                f"  static const {base_spelling} in{position}[{lanes}] = {{{literals}}};"
            )
            lines.append(f"  typename tsl::array_for<Hw>::type hin{position};")
            lines.append(f"  typename Ref::register_type r{position};")
            lines.append(
                f"  for (std::size_t i = 0; i < {lanes}; ++i) "
                f"{{ hin{position}[i] = in{position}[i]; r{position}[i] = in{position}[i]; }}"
            )
            hw_args.append(f"tsl::from_array<Hw>(hin{position})")
            ref_args.append(f"r{position}")
        lines.append(
            f"  typename tsl::array_for<Hw>::type hout = "
            f"tsl::to_array<Hw>(tsl::{name}<Hw>({', '.join(hw_args)}));"
        )
        lines.append(
            f"  typename Ref::register_type ref = tsl::{name}<Ref>({', '.join(ref_args)});"
        )
        lines.append(
            f'  return tsl::test::check_match<{base_spelling}>('
            f'"{fn_name}", hout, ref, {lanes});'
        )
        lines.append("}")
        emitted.append(("\n".join(lines), fn_name))
    return emitted


def _type_bits(type_tag: str) -> int | None:
    digits = "".join(c for c in type_tag if c.isdigit())
    return int(digits) if digits else None


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


def _token_truthy(token: str) -> bool:
    """Whether a mask-expected lane token denotes a set lane (any nonzero all-ones encoding)."""
    try:
        return int(token) != 0
    except ValueError:
        try:
            return float(token) != 0.0
        except ValueError:
            return True


def _sanitize(text_value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text_value)


__all__ = ["cpp_test_artifacts"]
