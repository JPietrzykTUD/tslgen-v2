"""Shared helpers for Rust value-test renderers."""

from __future__ import annotations

from tslc.backend.target_capability import rust_extension_tag
from tslc.value_tests.literals import rust_literal, rust_literal_list
from tslc.value_tests.model import ValueTestCasePlan


def append_call_args(lines: list[str], case: ValueTestCasePlan) -> list[str]:
    args: list[str] = []
    vector_index = 0
    mask_index = 0
    scalar_index = 0
    for kind in case.invocation.param_kinds:
        if kind == "v":
            values = case.inputs.vectors[vector_index]
            literals = rust_literal_list(values, case.type_tag)
            lines.append(
                f"        let in{vector_index}: [{case.base_spelling}; {case.lanes}] = "
                f"[{literals}];"
            )
            lines.append(
                f"        let mut v{vector_index}: <Vec as SimdVector>::RegisterType = "
                "Default::default();"
            )
            lines.append(
                f"        for i in 0..{case.lanes} {{ v{vector_index}[i] = "
                f"in{vector_index}[i]; }}"
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
                raise ValueError("indexed Rust value test requires an index-vector layout")
            values = case.inputs.vectors[vector_index]
            literals = rust_literal_list(values, index.type_tag)
            lines.append(
                f"        let in{vector_index}: [{index.base_spelling}; {index.lanes}] = "
                f"[{literals}];"
            )
            lines.append(
                f"        let mut v{vector_index}: <Indices as SimdVector>::RegisterType = "
                "Default::default();"
            )
            lines.append(
                f"        for i in 0..{index.lanes} {{ v{vector_index}[i] = "
                f"in{vector_index}[i]; }}"
            )
            args.append(f"v{vector_index}")
            vector_index += 1
        elif kind == "m":
            lines.append(
                f"        let m{mask_index}: <Vec as SimdVector>::MaskType = "
                f"{case.inputs.masks[mask_index]}u64;"
            )
            args.append(f"m{mask_index}")
            mask_index += 1
        elif kind == "im":
            lines.append(
                f"        let im{mask_index}: <Vec as SimdVector>::ImaskType = "
                f"{case.inputs.masks[mask_index]}u64;"
            )
            args.append(f"im{mask_index}")
            mask_index += 1
        elif kind in {"s", "sImm"}:
            value = rust_literal(case.inputs.scalars[scalar_index], case.type_tag)
            lines.append(f"        let s{scalar_index}: {case.base_spelling} = {value};")
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind == "usize":
            lines.append(
                f"        let s{scalar_index}: usize = "
                f"{case.inputs.scalars[scalar_index]}usize;"
            )
            args.append(f"s{scalar_index}")
            scalar_index += 1
        elif kind in {"ptr", "cptr"}:
            values = case.inputs.vectors[vector_index]
            initial = rust_literal(values[0], case.type_tag) if values else "Default::default()"
            mutability = "mut " if kind == "ptr" else ""
            lines.append(
                f"        let {mutability}pointed{vector_index}: {case.base_spelling} = "
                f"{initial};"
            )
            pointer = "&mut " if kind == "ptr" else "&"
            args.append(f"{pointer}pointed{vector_index}")
            vector_index += 1
        else:
            raise ValueError(f"unsupported Rust value-test argument kind {kind!r}")
    return args


def axis_args(case: ValueTestCasePlan) -> str:
    return "".join(f", {value}" for value in case.invocation.axis_args)


def scalar_result_type(case: ValueTestCasePlan) -> str:
    if case.invocation.result_kind == "usize":
        return "usize"
    if case.invocation.result_kind == "im":
        return "<Vec as SimdVector>::ImaskType"
    return case.base_spelling


def scalar_expected(case: ValueTestCasePlan, result_type: str) -> str:
    token = case.expectation.values[0]
    if result_type == "usize":
        return f"{token}usize"
    if result_type == "<Vec as SimdVector>::ImaskType":
        return f"{token}u64"
    return rust_literal(token, case.type_tag)


def rust_string_literal(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


__all__ = [
    "append_call_args",
    "axis_args",
    "rust_extension_tag",
    "rust_string_literal",
    "scalar_expected",
    "scalar_result_type",
]
