"""Pure C++ formatting helpers for value-test renderers."""

from __future__ import annotations

from tslc.value_tests.lane_math import runtime_tile_index
from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan


def append_call_args(lines: list[str], case: ValueTestCasePlan) -> list[str]:
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    scalar_index = 0
    for position, kind in enumerate(case.invocation.param_kinds):
        if kind == "v":
            values = case.inputs.vectors[vector_index]
            literals = cpp_literal_list(values, case.type_tag)
            lines.append(
                f"  static const {case.base_spelling} in{vector_index}[{case.lanes}] = "
                f"{{{literals}}};"
            )
            lines.append(f"  typename Vec::register_type v{vector_index};")
            lines.append(
                f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
                f"v{vector_index}[i] = in{vector_index}[i];"
            )
            args.append(f"v{vector_index}")
            vector_index += 1
        elif kind == "vidx":
            index = case.index
            if (
                index is None
                or index.type_tag is None
                or index.base_spelling is None
                or index.lanes is None
            ):
                raise ValueError("indexed C++ value test requires an index-vector layout")
            values = case.inputs.vectors[vector_index]
            literals = cpp_literal_list(values, index.type_tag)
            lines.append(
                f"  static const {index.base_spelling} in{vector_index}[{index.lanes}] = "
                f"{{{literals}}};"
            )
            lines.append(f"  typename Indices::register_type v{vector_index};")
            lines.append(
                f"  for (std::size_t i = 0; i < {index.lanes}; ++i) "
                f"v{vector_index}[i] = in{vector_index}[i];"
            )
            args.append(f"v{vector_index}")
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"  typename Vec::mask_type m{mask_index} = "
                f"{uint_literal(case.inputs.masks[mask_index])};"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        elif kind == "im":
            lines.append(
                f"  typename Vec::imask_type im{mask_index} = "
                f"static_cast<typename Vec::imask_type>("
                f"{uint_literal(case.inputs.masks[mask_index])});"
            )
            args.append(f"im{mask_index}")
            mask_index += 1
        elif kind in {"s", "sImm"}:
            value = cpp_literal(case.inputs.scalars[scalar_index], case.type_tag)
            lines.append(f"  {case.base_spelling} s{scalar_index} = {value};")
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind == "usize":
            lines.append(
                f"  std::size_t s{scalar_index} = "
                f"static_cast<std::size_t>({case.inputs.scalars[scalar_index]});"
            )
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind in {"ptr", "cptr"}:
            values = case.inputs.vectors[vector_index]
            initial = cpp_literal(values[0], case.type_tag) if values else "{}"
            qualifier = "const " if kind == "cptr" else ""
            lines.append(
                f"  {qualifier}{case.base_spelling} pointed{vector_index} = {initial};"
            )
            args.append(f"&pointed{vector_index}")
            vector_index += 1
        elif kind == "o":
            lines.append(f"  std::string out{position};")
            args.append(f"out{position}")
        else:
            raise ValueError(f"unsupported C++ value-test argument kind {kind!r}")
    return args


def scalar_result_type(case: ValueTestCasePlan) -> str:
    if case.invocation.result_kind == "usize":
        return "std::size_t"
    if case.invocation.result_kind == "im":
        return "typename Vec::imask_type"
    return case.base_spelling


def scalar_expected(case: ValueTestCasePlan, result_type: str) -> str:
    token = case.expectation.values[0]
    if result_type == "std::size_t":
        return f"static_cast<std::size_t>({token})"
    if result_type == "typename Vec::imask_type":
        return f"static_cast<typename Vec::imask_type>({uint_literal(token)})"
    return cpp_literal(token, case.type_tag)


def uint_literal(token: str) -> str:
    stripped = token.strip()
    if stripped.lower().endswith(("u", "ul", "ull")):
        return stripped
    return f"{stripped}ull"


def cast_literal_list(values: tuple[str, ...], target: str) -> str:
    return ", ".join(f"static_cast<{target}>({uint_literal(value)})" for value in values)


def cpp_string_literal(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def axis_suffix(case: ValueTestCasePlan) -> str:
    return "".join(f", {value}" for value in case.invocation.axis_args)


def render_extension_test_template(template: str, **values: str) -> str:
    """Fill one extension-authored test template's ``{placeholder}`` slots."""

    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result


def _scalable_vec_type(case: ValueTestCasePlan) -> str:
    scalable = case.scalable
    assert scalable is not None
    return f"tsl::simd<{case.base_spelling}, tsl::{scalable.source_extension}>"


def scalable_runtime_lanes(case: ValueTestCasePlan) -> str:
    """The C++ runtime lane-count expression from the plan's raw extension template."""

    scalable = case.scalable
    assert scalable is not None
    return render_extension_test_template(
        scalable.runtime_lanes_template,
        base_type=case.base_spelling,
        base=case.base_spelling,
    )


def scalable_mask_from_bits(case: ValueTestCasePlan, position: int) -> str:
    """The C++ mask-materialization expression for the mask input at ``position``."""

    scalable = case.scalable
    assert scalable is not None and scalable.mask_from_bits_template is not None
    return render_extension_test_template(
        scalable.mask_from_bits_template,
        vec=_scalable_vec_type(case),
        mask_bits=f"{scalable.mask_bits[position]}ull",
        authored_lanes=str(case.lanes),
        lanes="lanes",
        base_type=case.base_spelling,
        base=case.base_spelling,
    )


def scalable_mask_check(case: ValueTestCasePlan) -> str:
    """The C++ mask-verification expression over the local ``result`` mask."""

    scalable = case.scalable
    assert scalable is not None
    assert scalable.mask_check_template is not None
    assert scalable.expected_mask_bits is not None
    return render_extension_test_template(
        scalable.mask_check_template,
        vec=_scalable_vec_type(case),
        case_name=cpp_string_literal(case.case_name),
        mask="result",
        expected_bits=f"{scalable.expected_mask_bits}ull",
        authored_lanes=str(case.lanes),
        lanes="lanes",
        base_type=case.base_spelling,
        base=case.base_spelling,
    )


def scalable_header(case: ValueTestCasePlan) -> list[str]:
    """Open a scalable (runtime-length) value-test function: SVE-style `Vec` + runtime `lanes`."""

    scalable = case.scalable
    assert scalable is not None
    return [
        f"int {case.function_name}() {{",
        f"  using Vec = {_scalable_vec_type(case)};",
        f"  const std::size_t lanes = static_cast<std::size_t>({scalable_runtime_lanes(case)});",
    ]


def append_runtime_vector_input(
    lines: list[str], case: ValueTestCasePlan, position: int
) -> str:
    """Materialize one vector input into a runtime-length buffer and load it; return its name.

    The authored (fixed-length) pattern is tiled across the runtime lane count with
    ``i % case.lanes``; this is only sound for lane-local ops — see ``lane_model``.
    """

    values = case.inputs.vectors[position]
    scalable = case.scalable
    assert scalable is not None and scalable.load_name is not None
    literals = cpp_literal_list(values, case.type_tag)
    lines.append(
        f"  static const {case.base_spelling} authored{position}[{case.lanes}] = "
        f"{{{literals}}};"
    )
    lines.append(f"  std::vector<{case.base_spelling}> in{position}(lanes);")
    lines.append(
        f"  for (std::size_t i = 0; i < lanes; ++i) "
        f"in{position}[i] = authored{position}[{runtime_tile_index('i', case.lanes)}];"
    )
    lines.append(
        f"  typename Vec::register_type v{position} = "
        f"tsl::{scalable.load_name}<Vec, false>(in{position}.data());"
    )
    return f"v{position}"


__all__ = (
    "append_call_args",
    "append_runtime_vector_input",
    "axis_suffix",
    "cast_literal_list",
    "cpp_string_literal",
    "render_extension_test_template",
    "scalable_header",
    "scalable_mask_check",
    "scalable_mask_from_bits",
    "scalable_runtime_lanes",
    "scalar_expected",
    "scalar_result_type",
    "uint_literal",
)
