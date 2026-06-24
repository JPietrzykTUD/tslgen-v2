"""Pure C++ formatting helpers for value-test renderers."""

from __future__ import annotations

from tslc.value_tests.literals import cpp_literal, cpp_literal_list
from tslc.value_tests.model import ValueTestCasePlan


def append_vector_inputs(
    lines: list[str],
    case: ValueTestCasePlan,
    register_type: str,
    prefix: str,
) -> list[str]:
    names: list[str] = []
    for position, values in enumerate(case.vector_inputs):
        literals = cpp_literal_list(values, case.type_tag)
        lines.append(
            f"  static const {case.base_spelling} in{position}[{case.lanes}] = "
            f"{{{literals}}};"
        )
        lines.append(f"  {register_type} {prefix}{position};")
        lines.append(
            f"  for (std::size_t i = 0; i < {case.lanes}; ++i) "
            f"{prefix}{position}[i] = in{position}[i];"
        )
        names.append(f"{prefix}{position}")
    return names


def append_call_args(lines: list[str], case: ValueTestCasePlan) -> list[str]:
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    scalar_index = 0
    for position, kind in enumerate(case.param_kinds):
        if kind == "v":
            values = case.vector_inputs[vector_index]
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
        elif kind == "m":
            lines.append(
                f"  typename Vec::mask_type m{mask_index} = "
                f"{uint_literal(case.mask_inputs[mask_index])};"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        elif kind == "im":
            lines.append(
                f"  typename Vec::imask_type im{mask_index} = "
                f"static_cast<typename Vec::imask_type>("
                f"{uint_literal(case.mask_inputs[mask_index])});"
            )
            args.append(f"im{mask_index}")
            mask_index += 1
        elif kind in {"s", "sImm"}:
            value = cpp_literal(case.scalar_inputs[scalar_index], case.type_tag)
            lines.append(f"  {case.base_spelling} s{scalar_index} = {value};")
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind == "usize":
            lines.append(
                f"  std::size_t s{scalar_index} = "
                f"static_cast<std::size_t>({case.scalar_inputs[scalar_index]});"
            )
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind == "o":
            lines.append(f"  std::string out{position};")
            args.append(f"out{position}")
        else:
            raise ValueError(f"unsupported C++ value-test argument kind {kind!r}")
    return args


def scalar_result_type(case: ValueTestCasePlan) -> str:
    if case.result_kind == "usize":
        return "std::size_t"
    if case.result_kind == "im":
        return "typename Vec::imask_type"
    return case.base_spelling


def scalar_expected(case: ValueTestCasePlan, result_type: str) -> str:
    token = case.expected[0]
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
    return "".join(f", {value}" for value in case.axis_args)


__all__ = (
    "append_call_args",
    "append_vector_inputs",
    "axis_suffix",
    "cast_literal_list",
    "cpp_string_literal",
    "scalar_expected",
    "scalar_result_type",
    "uint_literal",
)
