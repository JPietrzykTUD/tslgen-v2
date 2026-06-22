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

from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.output.artifacts import Artifact
from tslc.render._common import asset, slug, text
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

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
            if _is_golden_supported(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_golden_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
                    # Differential: only when the round-trip harness is in this project. Vector
                    # results compare lane arrays; mask results compare via `to_integral`.
                    if harness_ready:
                        for diff in _cpp_differential_cases(name, index, case, specs, catalog):
                            functions.append(diff[0])
                            calls.append(diff[1])
            elif _is_masked_value(specs[0]):
                primitive = _masked_source(catalog, name, specs[0])
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_masked_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_store(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_store_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_reduction(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_reduction_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_load(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_load_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_mask_logic(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_mask_logic_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_to_array(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_to_array_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_broadcast(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_broadcast_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_immediate(specs[0]):
                primitive = _immediate_source(catalog, name)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_immediate_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])
            elif _is_to_vector(specs[0]):
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _cpp_to_vector_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted[0])
                        calls.append(emitted[1])

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
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    lanes = case.lanes
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
    ]
    arg_names: list[str] = []
    for position, arg in enumerate(vector_inputs):
        literals = ", ".join(_cpp_literal(v, case.type_tag) for v in arg.values)
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
        expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
        lines.append(f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};")
        lines.append(f"  typename Vec::register_type result = {call};")
        lines.append(
            f'  return tsl::test::check_lanes<{base_spelling}>('
            f'"{case.name}", result, expected, {lanes});'
        )
    lines.append("}")
    return "\n".join(lines), fn_name


def _is_masked_value(spec: LoweredSpecialization) -> bool:
    """A masked value op (`add_mask`/`add_maskz`): a vector result with exactly one mask param
    and the rest vectors, no other axes. The generic reference takes the mask as its `u64`
    bitset directly, so no mask-materialization primitive is needed."""

    return (
        spec.result_kind == "v"
        and spec.mask_policy in ("zero", "pass_through")
        and spec.param_kinds.count("m") == 1
        and all(kind in ("m", "v") for kind in spec.param_kinds)
        and spec.target is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _masked_source(
    catalog: Catalog, emitted_name: str, spec: LoweredSpecialization
) -> Primitive | None:
    """The masked source primitive (with its `tests`) for an emitted `_mask`/`_maskz` name: the
    `<base>` primitive whose `[mask=<policy>]` matches this spec's policy."""

    base = DEFAULT_SUPPORT_POLICY.mask_split_base(emitted_name)
    for primitive in catalog.primitives_named(base, unmasked=False):
        if primitive.attributes.get("mask") == spec.mask_policy:
            return primitive
    return None


def _cpp_masked_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    if base_spelling is None or len(case.expected) != case.lanes:
        return None
    mask_args = [arg for arg in case.inputs if arg.kind == "mask"]
    vector_args = [arg for arg in case.inputs if arg.kind == "vector"]
    param_kinds = specs[0].param_kinds
    if len(mask_args) != 1 or len(vector_args) != param_kinds.count("v"):
        return None
    if mask_args[0].mask_bits is None:
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  typename Vec::mask_type mask = {mask_args[0].mask_bits}ull;",
    ]
    vector_names: list[str] = []
    for position, arg in enumerate(vector_args):
        literals = ", ".join(_cpp_literal(v, case.type_tag) for v in arg.values)
        lines.append(f"  static const {base_spelling} in{position}[{lanes}] = {{{literals}}};")
        lines.append(f"  typename Vec::register_type v{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {lanes}; ++i) v{position}[i] = in{position}[i];"
        )
        vector_names.append(f"v{position}")
    # Assemble the call in parameter order, routing the mask to its `m` slot by kind.
    next_vector = iter(vector_names)
    call_args = ["mask" if kind == "m" else next(next_vector) for kind in param_kinds]
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines.append(f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};")
    lines.append(f"  typename Vec::register_type result = tsl::{name}<Vec>({', '.join(call_args)});")
    lines.append(
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});'
    )
    lines.append("}")
    return "\n".join(lines), fn_name


def _is_to_vector(spec: LoweredSpecialization) -> bool:
    """`to_vector(mask)` (`v:=m`): expand a mask to a vector (all-ones / 0 per lane). Compared
    against the generic reference, which fills each lane from the bitset."""

    return (
        spec.result_kind == "v"
        and tuple(spec.param_kinds) == ("m",)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_to_vector_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    mask_args = [arg for arg in case.inputs if arg.kind == "mask" and arg.mask_bits is not None]
    if base_spelling is None or len(mask_args) != 1 or len(case.expected) != case.lanes:
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  typename Vec::mask_type mask = {mask_args[0].mask_bits}ull;",
        f"  typename Vec::register_type result = tsl::{name}<Vec>(mask);",
        f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});',
        "}",
    ]
    return "\n".join(lines), fn_name


def _is_immediate(spec: LoweredSpecialization) -> bool:
    """An immediate op (`mul_imm`/`mod_imm`/`shift_left`-imm): a vector result with vector runtime
    params and a compile-time immediate (spelled as a const template arg). Generic params (e.g.
    shift's `PreserveSign`) are allowed and appended as their defaults."""

    return (
        spec.result_kind == "v"
        and spec.immediate is not None
        and "sImm" in spec.param_kinds
        and all(kind in ("v", "sImm") for kind in spec.param_kinds)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and not spec.type_params
    )


def _immediate_value(token: str, immediate: tuple[str, str] | None) -> str:
    """The immediate template-arg token, wrapped to its declared const type's range so a corpus
    value wider/negative for the type (e.g. factor -2 for a `uint32_t` immediate) binds as a
    converted constant — the result is modular-identical to the intended value."""
    if immediate is None:
        return token
    spelling = immediate[1]
    digits = "".join(c for c in spelling if c.isdigit())
    if not digits:
        return token
    try:
        value = int(token)
    except ValueError:
        return token
    bits = int(digits)
    value %= 1 << bits
    if not spelling.lstrip().startswith("u") and value >= (1 << (bits - 1)):
        value -= 1 << bits
    return str(value)


def _immediate_source(catalog: Catalog, emitted_name: str) -> "Primitive | None":
    """The source primitive (with `tests`) for an emitted immediate name — directly, or with the
    immediate-split `_imm` suffix stripped (`shift_left_imm` -> `shift_left`)."""
    primitive = catalog.primitive(emitted_name, unmasked=True)
    if primitive is not None:
        return primitive
    if emitted_name.endswith("_imm"):
        return catalog.primitive(emitted_name[: -len("_imm")], unmasked=True)
    return None


def _cpp_immediate_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    # The immediate parses as a bare scalar (mask-kind) arg; its token is the compile-time value.
    imm_args = [arg for arg in case.inputs if arg.kind == "mask" and arg.mask_bits is not None]
    if base_spelling is None or len(imm_args) != 1 or len(case.expected) != case.lanes:
        return None
    if len(vector_inputs) != specs[0].param_kinds.count("v"):
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    immediate = _immediate_value(imm_args[0].mask_bits, specs[0].immediate)
    targs = [f"tsl::simd<{base_spelling}, tsl::generic<{lanes}>>", immediate]
    targs.extend(default for _name, _type, default in specs[0].generic_params)
    lines = [f"int {fn_name}() {{"]
    arg_names: list[str] = []
    for position, arg in enumerate(vector_inputs):
        literals = ", ".join(_cpp_literal(v, case.type_tag) for v in arg.values)
        lines.append(f"  static const {base_spelling} in{position}[{lanes}] = {{{literals}}};")
        lines.append(
            f"  typename tsl::simd<{base_spelling}, tsl::generic<{lanes}>>::register_type "
            f"a{position};"
        )
        lines.append(
            f"  for (std::size_t i = 0; i < {lanes}; ++i) a{position}[i] = in{position}[i];"
        )
        arg_names.append(f"a{position}")
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines.append(f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};")
    lines.append(
        f"  auto result = tsl::{name}<{', '.join(targs)}>({', '.join(arg_names)});"
    )
    lines.append(
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});'
    )
    lines.append("}")
    return "\n".join(lines), fn_name


def _is_broadcast(spec: LoweredSpecialization) -> bool:
    """`set1(value)` (`v:=s`): broadcast one scalar to every lane. Compared against the generic
    reference, which fills its array with the value."""

    return (
        spec.result_kind == "v"
        and tuple(spec.param_kinds) == ("s",)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_broadcast_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    # A bare-scalar input (`inputs [7]`) parses as a mask-kind arg; for a scalar (`s`) parameter
    # its token is the broadcast value, not a mask.
    scalar_args = [arg for arg in case.inputs if arg.kind == "mask" and arg.mask_bits is not None]
    if base_spelling is None or len(scalar_args) != 1 or len(case.expected) != case.lanes:
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    value = _cpp_literal(scalar_args[0].mask_bits, case.type_tag)
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  {base_spelling} value = {value};",
        f"  typename Vec::register_type result = tsl::{name}<Vec>(value);",
        f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});',
        "}",
    ]
    return "\n".join(lines), fn_name


def _is_to_array(spec: LoweredSpecialization) -> bool:
    """`to_array(v)` (`s[]:=v`): the lane array of a vector — the harness's own readback path, so
    value-testing it checks the tool the other cases rely on. Compared against the generic array."""

    return (
        spec.result_kind == "s[]"
        and tuple(spec.param_kinds) == ("v",)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_to_array_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if base_spelling is None or len(vector_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    lanes = case.lanes
    if len(vector_inputs[0].values) != lanes:
        return None
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    literals = ", ".join(_cpp_literal(v, case.type_tag) for v in vector_inputs[0].values)
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {base_spelling} in0[{lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) v[i] = in0[i];",
        f"  auto result = tsl::{name}<Vec>(v);",
        f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});',
        "}",
    ]
    return "\n".join(lines), fn_name


def _is_mask_logic(spec: LoweredSpecialization) -> bool:
    """A mask logic op (`mask_binary_and`/`_or`/`_xor`/`_not`): a mask result from one or more
    mask operands, no other axes. Compared against the generic reference's integer bitset."""

    return (
        spec.result_kind == "m"
        and len(spec.param_kinds) >= 1
        and all(kind == "m" for kind in spec.param_kinds)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_mask_logic_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None or len(case.expected) != 1:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    mask_args = [arg for arg in case.inputs if arg.kind == "mask"]
    if base_spelling is None or len(mask_args) != len(specs[0].param_kinds):
        return None
    if any(arg.mask_bits is None for arg in mask_args):
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
    ]
    arg_names: list[str] = []
    for position, arg in enumerate(mask_args):
        lines.append(f"  typename Vec::mask_type m{position} = {arg.mask_bits}ull;")
        arg_names.append(f"m{position}")
    expected_int = int(case.expected[0])
    bits = ", ".join("1" if (expected_int >> i) & 1 else "0" for i in range(lanes))
    lines.append(f"  typename Vec::mask_type result = tsl::{name}<Vec>({', '.join(arg_names)});")
    lines.append(f"  static const int expected[{lanes}] = {{{bits}}};")
    lines.append(f'  return tsl::test::check_mask("{case.name}", result, expected, {lanes});')
    lines.append("}")
    return "\n".join(lines), fn_name


def _is_reduction(spec: LoweredSpecialization) -> bool:
    """A horizontal reduction (`hadd`/`hmax`/`hor`/…): a scalar result from a single vector, no
    other axes. The generic reference reduces over its lanes to one value."""

    return (
        spec.result_kind == "s"
        and tuple(spec.param_kinds) == ("v",)
        and spec.target is None
        and spec.mask_policy is None
        and not spec.axis
        and spec.immediate is None
        and not spec.generic_params
        and not spec.type_params
    )


def _cpp_reduction_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if base_spelling is None or len(vector_inputs) != 1 or len(case.expected) != 1:
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    literals = ", ".join(_cpp_literal(v, case.type_tag) for v in vector_inputs[0].values)
    expected = _cpp_literal(case.expected[0], case.type_tag)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {base_spelling} in0[{lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) v[i] = in0[i];",
        f"  {base_spelling} result = tsl::{name}<Vec>(v);",
        f"  static const {base_spelling} expected = {expected};",
        f'  return tsl::test::check_scalar<{base_spelling}>("{case.name}", result, expected);',
        "}",
    ]
    return "\n".join(lines), fn_name


def _is_load(spec: LoweredSpecialization) -> bool:
    """A `load(ptr)`: vector result from a pointer, only the `aligned`/`packed` axes. Mirror of
    store — the generic reference reads the lane array from a plain buffer."""

    return (
        spec.result_kind == "v"
        and tuple(spec.param_kinds) == ("ptr",)
        and spec.mask_policy is None
        and spec.immediate is None
        and spec.target is None
        and not spec.generic_params
        and not spec.type_params
        and all(axis_name in ("aligned", "packed") for axis_name, _ in spec.axis)
    )


def _cpp_load_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> tuple[str, str] | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if base_spelling is None or len(vector_inputs) != 1 or len(case.expected) != case.lanes:
        return None
    lanes = case.lanes
    offset = case.offset or 0
    if len(vector_inputs[0].values) != lanes:
        return None
    axis = "".join(f", {case.attrs.get(axis_name, value)}" for axis_name, value in specs[0].axis)
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    literals = ", ".join(_cpp_literal(v, case.type_tag) for v in vector_inputs[0].values)
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {base_spelling} data[{lanes}] = {{{literals}}};",
        f"  {base_spelling} buf[{offset + lanes}] = {{0}};",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) buf[{offset} + i] = data[i];",
        f"  typename Vec::register_type result = tsl::{name}<Vec{axis}>(buf + {offset});",
        f"  static const {base_spelling} expected[{lanes}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", result, expected, {lanes});',
        "}",
    ]
    return "\n".join(lines), fn_name


def _is_store(spec: LoweredSpecialization) -> bool:
    """A `store(ptr, v)`: void result, a pointer + a vector, only the `aligned`/`packed` axes.
    Run against the generic reference, which writes the lane array into a plain buffer."""

    return (
        spec.result_kind == "void"
        and tuple(spec.param_kinds) == ("ptr", "v")
        and spec.mask_policy is None
        and spec.immediate is None
        and spec.target is None
        and not spec.generic_params
        and not spec.type_params
        and all(axis_name in ("aligned", "packed") for axis_name, _ in spec.axis)
    )


def _cpp_store_case(
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
    if len(vector_inputs) != 1:
        return None
    lanes = case.lanes
    offset = case.offset or 0
    buflen = len(case.expected)
    if buflen < offset + lanes:
        return None  # the expected buffer must hold the stored lanes at the offset
    # Axis values come from the case attrs (the `aligned`/`packed` the case pins), in the spec's
    # axis order; both bool instantiations are emitted, so either is callable.
    axis = "".join(f", {case.attrs.get(axis_name, value)}" for axis_name, value in specs[0].axis)
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    literals = ", ".join(_cpp_literal(v, case.type_tag) for v in vector_inputs[0].values)
    expected = ", ".join(_cpp_literal(v, case.type_tag) for v in case.expected)
    lines = [
        f"int {fn_name}() {{",
        f"  using Vec = tsl::simd<{base_spelling}, tsl::generic<{lanes}>>;",
        f"  static const {base_spelling} in0[{lanes}] = {{{literals}}};",
        "  typename Vec::register_type v;",
        f"  for (std::size_t i = 0; i < {lanes}; ++i) v[i] = in0[i];",
        f"  {base_spelling} buf[{buflen}] = {{0}};",
        f"  tsl::{name}<Vec{axis}>(buf + {offset}, v);",
        f"  static const {base_spelling} expected[{buflen}] = {{{expected}}};",
        f'  return tsl::test::check_lanes<{base_spelling}>('
        f'"{case.name}", buf, expected, {buflen});',
        "}",
    ]
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
            literals = ", ".join(_cpp_literal(v, case.type_tag) for v in arg.values)
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
        hw_call = f"tsl::{name}<Hw>({', '.join(hw_args)})"
        ref_call = f"tsl::{name}<Ref>({', '.join(ref_args)})"
        if specs[0].result_kind == "m":
            # Normalize the hardware mask to its integer bitset; the generic mask already is one.
            lines.append(f"  auto hw = tsl::to_integral<Hw>({hw_call});")
            lines.append(f"  typename Ref::mask_type ref = {ref_call};")
            lines.append(
                f'  return tsl::test::check_mask_match("{fn_name}", hw, ref, {lanes});'
            )
        else:
            lines.append(
                f"  typename tsl::array_for<Hw>::type hout = tsl::to_array<Hw>({hw_call});"
            )
            lines.append(f"  typename Ref::register_type ref = {ref_call};")
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


def _wrapped_int(token: str, type_tag: str) -> str | None:
    """A decimal integer token wrapped to the lane type's range (so 130 for si8 -> -126: the value
    actually stored in the lane, and one a typed array literal accepts), or None if not an int."""

    bits = _type_bits(type_tag)
    if bits is None:
        return None
    try:
        value = int(token)
    except ValueError:
        return None
    value %= 1 << bits
    if type_tag.startswith("s") and value >= (1 << (bits - 1)):
        value -= 1 << bits
    return str(value)


def _cpp_literal(token: str, type_tag: str) -> str:
    if type_tag.startswith("f"):
        upper = token.upper()
        if upper in ("INFINITY", "+INFINITY"):
            return "INFINITY"
        if upper == "-INFINITY":
            return "-INFINITY"
        if upper in ("NAN", "+NAN", "-NAN"):
            return "NAN"
        return token
    wrapped = _wrapped_int(token, type_tag)
    return wrapped if wrapped is not None else token


def _rust_literal(token: str, type_tag: str) -> str:
    if type_tag.startswith("f"):
        ty = "f32" if "32" in type_tag else "f64"
        upper = token.upper()
        if upper in ("INFINITY", "+INFINITY"):
            return f"{ty}::INFINITY"
        if upper == "-INFINITY":
            return f"{ty}::NEG_INFINITY"
        if upper in ("NAN", "+NAN", "-NAN"):
            return f"{ty}::NAN"
        return token
    wrapped = _wrapped_int(token, type_tag)
    return wrapped if wrapped is not None else token


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


# --- Rust value tests --------------------------------------------------------
#
# Mirror of the C++ golden layer. The Rust generic register (`array_type<T, LANES>`) builds via
# `Default` + `IndexMut` (both public), so golden cases need no construction primitive — like C++.
# Value tests are gated behind the `value_tests` cargo feature so `cargo test` only runs them when
# asked (parity with the C++ opt-in); each profile's tests are further `cfg`-gated on that
# profile's feature, so only the active profile's module is referenced.


def rust_test_artifacts(
    profiles: tuple[ProfileRender, ...],
    catalog: Catalog | None,
) -> list[Artifact]:
    """The Rust value-test sources: the shared helper module plus one `tests/values.rs` whose
    per-profile sections are `cfg`-gated (so only the active profile's module is compiled)."""

    artifacts = [text("rust/src/tsl_test_core.rs", asset("tsl_test_core.rs"))]
    artifacts.append(text("rust/tests/values.rs", _rust_values_file(profiles, catalog)))
    return artifacts


def _rust_values_file(profiles: tuple[ProfileRender, ...], catalog: Catalog | None) -> str:
    sections: list[str] = ['#![cfg(feature = "value_tests")]', ""]
    if catalog is not None:
        for profile_render in profiles:
            profile_slug = slug(profile_render.profile.name)
            functions: list[str] = []
            for name in sorted(profile_render.rust):
                specs = profile_render.rust[name]
                if not _is_golden_supported(specs[0]):
                    continue
                primitive = catalog.primitive(name, unmasked=True)
                if primitive is None:
                    continue
                for index, case in enumerate(primitive.tests):
                    emitted = _rust_golden_case(name, index, case, specs)
                    if emitted is not None:
                        functions.append(emitted)
            if not functions:
                continue
            body = "\n\n".join(functions)
            sections.append(
                f'#[cfg(feature = "{profile_slug}")]\n'
                f"mod {profile_slug}_values {{\n"
                "    #![allow(non_snake_case)]\n"
                "    use tsl_generated::tsl_core::*;\n"
                f"    use tsl_generated::tsl_{profile_slug}::*;\n"
                "    use tsl_generated::tsl_test_core::*;\n\n"
                f"{body}\n"
                "}"
            )
    return "\n\n".join(sections) + "\n"


def _rust_golden_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> str | None:
    if case.lanes is None or case.expected_rule is not None:
        return None
    base_spelling = _base_spelling(specs, case.type_tag)
    if base_spelling is None:
        return None
    vector_inputs = [arg for arg in case.inputs if arg.kind == "vector"]
    if len(vector_inputs) != len(specs[0].param_kinds):
        return None
    if len(case.expected) != case.lanes:
        return None
    lanes = case.lanes
    fn_name = f"test_{name}_{index}_{_sanitize(case.name)}"
    lines = [
        "    #[test]",
        f"    fn {fn_name}() {{",
        f"        type Vec = Simd<{base_spelling}, Generic<{lanes}>>;",
    ]
    arg_names: list[str] = []
    for position, arg in enumerate(vector_inputs):
        literals = ", ".join(_rust_literal(v, case.type_tag) for v in arg.values)
        lines.append(f"        let in{position}: [{base_spelling}; {lanes}] = [{literals}];")
        lines.append(
            f"        let mut a{position}: <Vec as SimdVector>::RegisterType = "
            "Default::default();"
        )
        lines.append(
            f"        for i in 0..{lanes} {{ a{position}[i] = in{position}[i]; }}"
        )
        arg_names.append(f"a{position}")
    # A primitive whose name is a Rust keyword (`mod`) is called via the same raw identifier the
    # wrapper is defined with (`r#mod`), not the bare keyword.
    call = f"{rust_raw_identifier(name)}::<Vec>({', '.join(arg_names)})"
    if specs[0].result_kind == "m":
        bits = ", ".join("true" if _token_truthy(v) else "false" for v in case.expected)
        lines.append(f"        let expected: [bool; {lanes}] = [{bits}];")
        lines.append(f"        let result = {call};")
        lines.append(
            f"        for i in 0..{lanes} {{ assert_eq!(mask_bit(result as u64, i), "
            f'expected[i], "{case.name} lane {{}}", i); }}'
        )
    else:
        literals = ", ".join(_rust_literal(v, case.type_tag) for v in case.expected)
        lines.append(f"        let expected: [{base_spelling}; {lanes}] = [{literals}];")
        lines.append(f"        let result = {call};")
        lines.append(
            f"        for i in 0..{lanes} {{ assert!(result[i].lane_eq(expected[i]), "
            f'"{case.name} lane {{}}: expected {{:?}}, got {{:?}}", i, expected[i], result[i]); }}'
        )
    lines.append("    }")
    return "\n".join(lines)


__all__ = ["cpp_test_artifacts", "rust_test_artifacts"]
