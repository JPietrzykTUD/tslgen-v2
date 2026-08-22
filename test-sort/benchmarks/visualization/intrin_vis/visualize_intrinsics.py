#!/usr/bin/env python3
"""
simdvis.py — Render a small SIMD data-flow YAML DSL as SVG.

Supported instructions
----------------------
permutexvar
    inputs: [source]
    indices: [source_lane_for_destination_lane_0, ...]

cmpgt
    inputs: [lhs, rhs]
    Produces a mask register.

Bitmasks
--------
Declare concrete masks with either ``bitmasks`` or ``masks``:

    bitmasks:
      m0: [T, F, T, F, T, F, T, F]
      m1: 0x55
      m2: "0b01010101"

For scalar masks, bit 0 controls SIMD lane 0.

Use a mask on an operation with:

    mask: m0
    mask_mode: merge       # merge or zero
    passthrough: a         # optional; defaults to first vector input

For a vector result:
    merge: result[i] = mask[i] ? operation[i] : passthrough[i]
    zero:  result[i] = mask[i] ? operation[i] : 0

For a mask result such as cmpgt, inactive lanes are 0.

Two-column layout
-----------------
Keep masks and input registers in a shared section, then place every operation
result in exactly one of two side-by-side columns:

    layout:
      columns:
        - title: Left flow
          results: [leftPacked, leftOutput]
        - title: Right flow
          results: [rightPacked, rightOutput]

Usage:
    python simdvis.py input.yaml -o output.svg
"""

from __future__ import annotations

import argparse
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML is required. Install it with:\n"
        "  python -m pip install pyyaml"
    ) from exc


@dataclass(frozen=True)
class Theme:
    background: str = "#ffffff"
    text: str = "#172033"
    muted: str = "#667085"
    vector_fill: str = "#eef4ff"
    result_fill: str = "#ecfdf3"
    mask_fill: str = "#fff7df"
    inactive_fill: str = "#f3f4f6"
    lane_border: str = "#7b8494"
    data_arrow: str = "#344054"
    passthrough_arrow: str = "#98a2b3"
    mask_arrow: str = "#b54708"
    operation_fill: str = "#f4f3ff"
    operation_border: str = "#6938ef"
    separator: str = "#d0d5dd"
    true_bit: str = "#067647"
    false_bit: str = "#b42318"


@dataclass(frozen=True)
class Layout:
    margin_x: int = 38
    margin_y: int = 34
    label_width: int = 82
    lane_width: int = 82
    lane_height: int = 46
    row_gap: int = 130
    gutter_width: int = 72
    operation_width: int = 220
    operation_height: int = 66
    right_margin: int = 34

    @property
    def register_x(self) -> int:
        return self.margin_x + self.label_width


@dataclass
class Register:
    name: str
    lanes: list[str]
    kind: str = "vector"              # vector | mask
    producer: str | None = None
    bit_values: list[bool | None] | None = None
    active_lanes: list[bool | None] | None = None


@dataclass(frozen=True)
class Operation:
    result: str
    instruction: str
    inputs: list[str]
    indices: list[int] | None = None
    mask: str | None = None
    mask_mode: str = "merge"
    passthrough: str | None = None


@dataclass(frozen=True)
class RenderColumn:
    title: str
    results: tuple[str, ...]


@dataclass(frozen=True)
class RegisterPlacement:
    x: float
    y: float


@dataclass(frozen=True)
class OperationPlacement:
    vector_right: float
    separator_x: float
    operation_x: float


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def svg_text(
    x: float,
    y: float,
    text: object,
    *,
    size: int = 13,
    anchor: str = "middle",
    weight: str = "normal",
    fill: str = "#172033",
    family: str = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}">{esc(text)}</text>'
    )


def parse_registers(raw: Any) -> dict[str, Register]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("'registers' must be a non-empty mapping.")

    result: dict[str, Register] = {}
    lane_count: int | None = None

    for name, values in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError("Register names must be non-empty strings.")
        if not isinstance(values, list) or not values:
            raise ValueError(f"Register '{name}' must be a non-empty list.")

        lanes = [str(value) for value in values]
        if lane_count is None:
            lane_count = len(lanes)
        elif len(lanes) != lane_count:
            raise ValueError(
                f"Register '{name}' has {len(lanes)} lanes; expected {lane_count}."
            )

        result[name] = Register(name=name, lanes=lanes)

    return result


def parse_bit(value: Any, *, mask_name: str, lane: int) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"0", "f", "false"}:
            return False
        if lowered in {"1", "t", "true"}:
            return True
    raise ValueError(
        f"Bitmask '{mask_name}' lane {lane} must be T/F, 0/1, or false/true."
    )


def scalar_mask_bits(value: int, lane_count: int, name: str) -> list[bool]:
    if value < 0:
        raise ValueError(f"Bitmask '{name}' must not be negative.")
    if value >= (1 << lane_count):
        raise ValueError(
            f"Bitmask '{name}' needs more than {lane_count} bits."
        )
    return [bool((value >> lane) & 1) for lane in range(lane_count)]


def parse_bitmasks(raw: Any, lane_count: int) -> dict[str, Register]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("'bitmasks' must be a mapping.")

    result: dict[str, Register] = {}

    for name, raw_value in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError("Bitmask names must be non-empty strings.")

        if isinstance(raw_value, list):
            if len(raw_value) != lane_count:
                raise ValueError(
                    f"Bitmask '{name}' has {len(raw_value)} lanes; "
                    f"expected {lane_count}."
                )
            bits = [
                parse_bit(bit, mask_name=name, lane=lane)
                for lane, bit in enumerate(raw_value)
            ]
        elif isinstance(raw_value, int):
            bits = scalar_mask_bits(raw_value, lane_count, name)
        elif isinstance(raw_value, str):
            text = raw_value.strip().replace("_", "")
            try:
                if text.lower().startswith("0b"):
                    scalar = int(text, 2)
                elif text.lower().startswith("0x"):
                    scalar = int(text, 16)
                elif text and set(text) <= {"0", "1"}:
                    scalar = int(text, 2)
                else:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(
                    f"Bitmask '{name}' must be a lane list, integer, "
                    "binary string, or hexadecimal string."
                ) from exc
            bits = scalar_mask_bits(scalar, lane_count, name)
        else:
            raise ValueError(
                f"Bitmask '{name}' must be a lane list, integer, "
                "binary string, or hexadecimal string."
            )

        result[name] = Register(
            name=name,
            lanes=["T" if bit else "F" for bit in bits],
            kind="mask",
            bit_values=list(bits),
        )

    return result


def parse_operations(raw: Any) -> list[Operation]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("'operations' must be a list.")

    operations: list[Operation] = []

    for number, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Operation #{number} must be a mapping.")

        try:
            result = item["result"]
            instruction = item["instruction"]
            inputs = item["inputs"]
        except KeyError as exc:
            raise ValueError(
                f"Operation #{number} is missing {exc.args[0]!r}."
            ) from exc

        if not isinstance(result, str) or not result:
            raise ValueError(f"Operation #{number}: invalid result name.")
        if not isinstance(instruction, str) or not instruction:
            raise ValueError(f"Operation #{number}: invalid instruction.")
        if not isinstance(inputs, list) or not inputs or not all(
            isinstance(name, str) and name for name in inputs
        ):
            raise ValueError(
                f"Operation #{number}: 'inputs' must be a non-empty name list."
            )

        indices = item.get("indices")
        if indices is not None and (
            not isinstance(indices, list)
            or not all(isinstance(index, int) for index in indices)
        ):
            raise ValueError(
                f"Operation #{number}: 'indices' must be an integer list."
            )

        mask = item.get("mask")
        if mask is not None and not isinstance(mask, str):
            raise ValueError(f"Operation #{number}: 'mask' must be a name.")

        mask_mode = str(item.get("mask_mode", "merge")).lower()
        if mask_mode not in {"merge", "zero"}:
            raise ValueError(
                f"Operation #{number}: mask_mode must be 'merge' or 'zero'."
            )

        passthrough = item.get("passthrough")
        if passthrough is not None and not isinstance(passthrough, str):
            raise ValueError(
                f"Operation #{number}: 'passthrough' must be a name."
            )

        operations.append(
            Operation(
                result=result,
                instruction=instruction.lower(),
                inputs=list(inputs),
                indices=indices,
                mask=mask,
                mask_mode=mask_mode,
                passthrough=passthrough,
            )
        )

    return operations


def parse_render_columns(
    raw: Any,
    operations: list[Operation],
) -> tuple[RenderColumn, RenderColumn] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("'layout' must be a mapping.")

    raw_columns = raw.get("columns")
    if raw_columns is None:
        return None
    if not isinstance(raw_columns, list) or len(raw_columns) != 2:
        raise ValueError("'layout.columns' must contain exactly two columns.")

    known_results = {op.result for op in operations}
    assigned: list[str] = []
    columns: list[RenderColumn] = []

    for number, item in enumerate(raw_columns, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Layout column #{number} must be a mapping.")
        title = item.get("title")
        results = item.get("results")
        if not isinstance(title, str) or not title:
            raise ValueError(f"Layout column #{number} needs a non-empty title.")
        if not isinstance(results, list) or not results or not all(
            isinstance(name, str) and name for name in results
        ):
            raise ValueError(
                f"Layout column #{number} needs a non-empty result-name list."
            )

        unknown = sorted(set(results) - known_results)
        if unknown:
            raise ValueError(
                f"Layout column #{number} references unknown results: "
                + ", ".join(unknown)
            )
        assigned.extend(results)
        columns.append(RenderColumn(title=title, results=tuple(results)))

    duplicates = sorted(
        name for name in set(assigned) if assigned.count(name) > 1
    )
    if duplicates:
        raise ValueError(
            "Results assigned to more than one layout column: "
            + ", ".join(duplicates)
        )

    missing = sorted(known_results - set(assigned))
    if missing:
        raise ValueError(
            "Operation results missing from 'layout.columns': "
            + ", ".join(missing)
        )

    return columns[0], columns[1]


def mask_activity(mask: Register | None, lane_count: int) -> list[bool | None]:
    if mask is None:
        return [True] * lane_count
    if mask.kind != "mask":
        raise ValueError(f"'{mask.name}' is not a mask register.")
    if mask.bit_values is None:
        return [None] * lane_count
    return list(mask.bit_values)


def apply_mask(
    activity: list[bool | None],
    active_values: list[str],
    inactive_values: list[str],
    mask_labels: list[str],
) -> list[str]:
    result: list[str] = []
    for active, selected, inactive, label in zip(
        activity, active_values, inactive_values, mask_labels, strict=True
    ):
        if active is True:
            result.append(selected)
        elif active is False:
            result.append(inactive)
        else:
            result.append(f"{label}?{selected}:{inactive}")
    return result


def evaluate(
    initial: dict[str, Register],
    operations: Iterable[Operation],
) -> tuple[dict[str, Register], list[Operation]]:
    registers = dict(initial)
    ordered = list(operations)

    for op in ordered:
        references = [*op.inputs]
        if op.mask:
            references.append(op.mask)
        if op.passthrough:
            references.append(op.passthrough)

        missing = [name for name in references if name not in registers]
        if missing:
            raise ValueError(
                f"Operation producing '{op.result}' references unknown names: "
                + ", ".join(sorted(set(missing)))
            )
        if op.result in registers:
            raise ValueError(f"Result '{op.result}' already exists.")

        first = registers[op.inputs[0]]
        lane_count = len(first.lanes)
        mask = registers[op.mask] if op.mask else None
        activity = mask_activity(mask, lane_count)
        mask_labels = mask.lanes if mask else ["1"] * lane_count

        if op.instruction == "permutexvar":
            if len(op.inputs) != 1:
                raise ValueError("permutexvar requires exactly one vector input.")
            if first.kind != "vector":
                raise ValueError("permutexvar requires a vector input.")
            if op.indices is None or len(op.indices) != lane_count:
                raise ValueError(
                    f"permutexvar producing '{op.result}' requires "
                    f"{lane_count} indices."
                )
            if any(index < 0 or index >= lane_count for index in op.indices):
                raise ValueError(
                    f"permutexvar producing '{op.result}' contains "
                    "an out-of-range index."
                )

            selected = [first.lanes[index] for index in op.indices]

            if op.mask is None:
                lanes = selected
            elif op.mask_mode == "zero":
                lanes = apply_mask(
                    activity, selected, ["0"] * lane_count, mask_labels
                )
            else:
                passthrough_name = op.passthrough or op.inputs[0]
                passthrough = registers[passthrough_name]
                if passthrough.kind != "vector":
                    raise ValueError("The passthrough source must be a vector.")
                if len(passthrough.lanes) != lane_count:
                    raise ValueError("The passthrough source has the wrong width.")
                lanes = apply_mask(
                    activity, selected, passthrough.lanes, mask_labels
                )

            registers[op.result] = Register(
                name=op.result,
                lanes=lanes,
                producer=op.instruction,
                active_lanes=activity if op.mask else None,
            )

        elif op.instruction == "cmpgt":
            if len(op.inputs) != 2:
                raise ValueError("cmpgt requires exactly two vector inputs.")
            lhs = registers[op.inputs[0]]
            rhs = registers[op.inputs[1]]
            if lhs.kind != "vector" or rhs.kind != "vector":
                raise ValueError("cmpgt requires vector inputs.")
            if len(lhs.lanes) != len(rhs.lanes):
                raise ValueError("cmpgt input widths differ.")

            comparisons = [
                f"{left}>{right}"
                for left, right in zip(lhs.lanes, rhs.lanes, strict=True)
            ]
            if op.mask:
                lanes = apply_mask(
                    activity, comparisons, ["0"] * lane_count, mask_labels
                )
                bits: list[bool | None] = [
                    False if active is False else None for active in activity
                ]
            else:
                lanes = comparisons
                bits = [None] * lane_count

            registers[op.result] = Register(
                name=op.result,
                lanes=lanes,
                kind="mask",
                producer=op.instruction,
                bit_values=bits,
                active_lanes=activity if op.mask else None,
            )
        else:
            raise ValueError(
                f"Unsupported instruction '{op.instruction}'. "
                "Supported instructions: permutexvar, cmpgt."
            )

    return registers, ordered


def bezier(x1: float, y1: float, x2: float, y2: float) -> str:
    dy = y2 - y1
    return (
        f"M {x1:.1f} {y1:.1f} "
        f"C {x1:.1f} {y1 + dy * 0.43:.1f}, "
        f"{x2:.1f} {y2 - dy * 0.43:.1f}, "
        f"{x2:.1f} {y2:.1f}"
    )


def render_register(
    register: Register,
    y: float,
    lane_count: int,
    layout: Layout,
    theme: Theme,
    *,
    register_x: float | None = None,
) -> list[str]:
    origin_x = layout.register_x if register_x is None else register_x
    parts = [
        svg_text(
            origin_x - 18,
            y + layout.lane_height / 2 + 5,
            register.name,
            size=17,
            anchor="end",
            weight="bold",
            fill=theme.text,
        )
    ]

    if register.kind == "mask":
        base_fill = theme.mask_fill
    elif register.producer:
        base_fill = theme.result_fill
    else:
        base_fill = theme.vector_fill

    for lane, text in enumerate(register.lanes):
        x = origin_x + lane * layout.lane_width
        active = (
            register.active_lanes[lane]
            if register.active_lanes is not None
            else True
        )
        fill = theme.inactive_fill if active is False else base_fill
        dash = ' stroke-dasharray="4 3"' if active is False else ""

        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" '
            f'width="{layout.lane_width}" height="{layout.lane_height}" '
            f'rx="5" fill="{fill}" stroke="{theme.lane_border}" '
            f'stroke-width="1.2"{dash}/>'
        )

        text_fill = theme.text
        if register.kind == "mask" and register.bit_values is not None:
            value = register.bit_values[lane]
            if value is True:
                text_fill = theme.true_bit
            elif value is False:
                text_fill = theme.false_bit

        font_size = 12 if len(text) <= 11 else 10
        parts.append(
            svg_text(
                x + layout.lane_width / 2,
                y + layout.lane_height / 2 + 5,
                text,
                size=font_size,
                weight="bold" if register.kind == "mask" else "normal",
                fill=text_fill,
            )
        )
        parts.append(
            svg_text(
                x + layout.lane_width / 2,
                y - 7,
                lane,
                size=10,
                fill=theme.muted,
            )
        )

    return parts


def operation_lines(op: Operation) -> tuple[str, str, str]:
    relation = f"{', '.join(op.inputs)} → {op.result}"
    if op.mask is None:
        return op.instruction, relation, "unmasked"
    if op.instruction == "cmpgt":
        return op.instruction, relation, f"mask {op.mask}; inactive → 0"
    if op.mask_mode == "zero":
        return op.instruction, relation, f"mask {op.mask}; zeroing"
    source = op.passthrough or op.inputs[0]
    return op.instruction, relation, f"mask {op.mask}; merge from {source}"


def render_svg(
    vector_names: list[str],
    mask_names: list[str],
    registers: dict[str, Register],
    operations: list[Operation],
    *,
    title: str,
    layout: Layout,
    theme: Theme,
    columns: tuple[RenderColumn, RenderColumn] | None = None,
) -> str:
    lane_count = len(registers[vector_names[0]].lanes)
    shared_names = [*mask_names, *vector_names]
    result_names = [op.result for op in operations]
    row_order = [*shared_names, *result_names]

    if len(row_order) != len(set(row_order)):
        raise ValueError("All vector, mask, and result names must be unique.")

    vector_width = lane_count * layout.lane_width
    placements: dict[str, RegisterPlacement] = {}
    operation_placements: dict[str, OperationPlacement] = {}
    headings: list[tuple[float, float, str, int]] = []
    separators: list[tuple[float, float, float]] = []
    single_column = columns is None

    if columns is None:
        for row, name in enumerate(row_order):
            placements[name] = RegisterPlacement(
                x=layout.register_x,
                y=layout.margin_y + 56 + row * layout.row_gap,
            )

        vector_right = layout.register_x + vector_width
        separator_x = vector_right + layout.gutter_width
        operation_x = separator_x + 24
        geometry = OperationPlacement(
            vector_right=vector_right,
            separator_x=separator_x,
            operation_x=operation_x,
        )
        operation_placements = {name: geometry for name in result_names}
        width = operation_x + layout.operation_width + layout.right_margin
        height = (
            layout.margin_y
            + 72
            + len(row_order) * layout.row_gap
            + layout.margin_y
        )
        headings.append(
            (
                operation_x + layout.operation_width / 2,
                layout.margin_y,
                "instruction column",
                12,
            )
        )
        separators.append(
            (
                separator_x,
                layout.margin_y + 18,
                height - layout.margin_y - 28,
            )
        )
    else:
        column_gap = 64
        column_span = (
            layout.label_width
            + vector_width
            + layout.gutter_width
            + 24
            + layout.operation_width
            + layout.right_margin
        )
        width = (
            layout.margin_x
            + len(columns) * column_span
            + (len(columns) - 1) * column_gap
        )
        shared_register_x = (width - vector_width) / 2
        shared_start_y = layout.margin_y + 82

        for row, name in enumerate(shared_names):
            placements[name] = RegisterPlacement(
                x=shared_register_x,
                y=shared_start_y + row * layout.row_gap,
            )

        last_shared_y = shared_start_y + (len(shared_names) - 1) * layout.row_gap
        branch_start_y = last_shared_y + layout.lane_height + 104
        max_column_rows = max(len(column.results) for column in columns)
        height = (
            branch_start_y
            + (max_column_rows - 1) * layout.row_gap
            + layout.lane_height
            + layout.margin_y
            + 52
        )
        headings.append(
            (
                shared_register_x + vector_width / 2,
                layout.margin_y + 58,
                "shared masks and inputs",
                13,
            )
        )

        for column_number, column in enumerate(columns):
            column_base_x = (
                layout.margin_x + column_number * (column_span + column_gap)
            )
            register_x = column_base_x + layout.label_width
            vector_right = register_x + vector_width
            separator_x = vector_right + layout.gutter_width
            operation_x = separator_x + 24
            geometry = OperationPlacement(
                vector_right=vector_right,
                separator_x=separator_x,
                operation_x=operation_x,
            )

            for row, name in enumerate(column.results):
                placements[name] = RegisterPlacement(
                    x=register_x,
                    y=branch_start_y + row * layout.row_gap,
                )
                operation_placements[name] = geometry

            headings.extend(
                [
                    (
                        column_base_x + (column_span - layout.right_margin) / 2,
                        branch_start_y - 55,
                        column.title,
                        16,
                    ),
                    (
                        operation_x + layout.operation_width / 2,
                        branch_start_y - 25,
                        "instruction",
                        11,
                    ),
                ]
            )
            separators.append(
                (
                    separator_x,
                    branch_start_y - 42,
                    height - layout.margin_y - 28,
                )
            )

    missing_placements = sorted(set(row_order) - set(placements))
    if missing_placements:
        raise ValueError(
            "Layout did not place registers: " + ", ".join(missing_placements)
        )

    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            'role="img" aria-labelledby="title desc">'
        ),
        f'<title id="title">{esc(title)}</title>',
        (
            '<desc id="desc">SIMD lane data flow with explicit instruction '
            'placement and operation-control masks.</desc>'
        ),
        "<defs>",
        (
            f'<marker id="arrowhead" markerWidth="8" markerHeight="8" '
            f'refX="7" refY="4" orient="auto">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{theme.data_arrow}"/>'
            "</marker>"
        ),
        (
            f'<marker id="mask-arrowhead" markerWidth="8" markerHeight="8" '
            f'refX="7" refY="4" orient="auto">'
            f'<path d="M0,0 L8,4 L0,8 z" fill="{theme.mask_arrow}"/>'
            "</marker>"
        ),
        "</defs>",
        f'<rect width="100%" height="100%" fill="{theme.background}"/>',
        svg_text(
            layout.margin_x,
            layout.margin_y,
            title,
            size=20,
            anchor="start",
            weight="bold",
            fill=theme.text,
            family="system-ui, -apple-system, Segoe UI, sans-serif",
        ),
    ]

    for x, y, text, size in headings:
        parts.append(
            svg_text(
                x,
                y,
                text,
                size=size,
                weight="bold",
                fill=theme.muted,
                family="system-ui, -apple-system, Segoe UI, sans-serif",
            )
        )
    for separator_x, separator_top, separator_bottom in separators:
        parts.append(
            f'<line x1="{separator_x:.1f}" y1="{separator_top:.1f}" '
            f'x2="{separator_x:.1f}" y2="{separator_bottom:.1f}" '
            f'stroke="{theme.separator}" stroke-width="1"/>'
        )

    lane_parts: list[str] = []
    dependency_parts: list[str] = []
    box_parts: list[str] = []

    # Lane-level data flow follows the source and destination register placement.
    for op in operations:
        target_placement = placements[op.result]
        target_y = target_placement.y
        geometry = operation_placements[op.result]
        target = registers[op.result]
        activity = target.active_lanes or [True] * lane_count

        if op.instruction == "permutexvar":
            source_placement = placements[op.inputs[0]]
            assert op.indices is not None
            passthrough_name = op.passthrough or op.inputs[0]
            passthrough_placement = placements[passthrough_name]

            for destination, (source_lane, active) in enumerate(
                zip(op.indices, activity, strict=True)
            ):
                dst_x = (
                    target_placement.x
                    + destination * layout.lane_width
                    + layout.lane_width / 2
                )

                if active is False and op.mask_mode == "zero":
                    continue

                if active is False:
                    src_x = (
                        passthrough_placement.x
                        + destination * layout.lane_width
                        + layout.lane_width / 2
                    )
                    src_y = passthrough_placement.y + layout.lane_height
                    stroke = theme.passthrough_arrow
                    dash = ' stroke-dasharray="5 4"'
                    marker = "arrowhead"
                else:
                    src_x = (
                        source_placement.x
                        + source_lane * layout.lane_width
                        + layout.lane_width / 2
                    )
                    src_y = source_placement.y + layout.lane_height
                    stroke = (
                        theme.data_arrow if active is True else theme.mask_arrow
                    )
                    dash = ' stroke-dasharray="3 3"' if active is None else ""
                    marker = (
                        "mask-arrowhead" if active is None else "arrowhead"
                    )

                lane_parts.append(
                    f'<path d="{bezier(src_x, src_y, dst_x, target_y)}" '
                    f'fill="none" stroke="{stroke}" stroke-width="1.5" '
                    f'opacity="0.78"{dash} marker-end="url(#{marker})"/>'
                )

        operation_x = geometry.operation_x
        separator_x = geometry.separator_x
        vector_right = geometry.vector_right
        box_y = target_y - layout.operation_height - 14
        line1, line2, line3 = operation_lines(op)

        box_parts.extend(
            [
                (
                    f'<rect x="{operation_x:.1f}" y="{box_y:.1f}" '
                    f'width="{layout.operation_width}" '
                    f'height="{layout.operation_height}" rx="8" '
                    f'fill="{theme.operation_fill}" '
                    f'stroke="{theme.operation_border}" stroke-width="1.3"/>'
                ),
                svg_text(
                    operation_x + layout.operation_width / 2,
                    box_y + 20,
                    line1,
                    size=13,
                    weight="bold",
                    fill=theme.text,
                ),
                svg_text(
                    operation_x + layout.operation_width / 2,
                    box_y + 40,
                    line2,
                    size=11,
                    fill=theme.muted,
                ),
                svg_text(
                    operation_x + layout.operation_width / 2,
                    box_y + 57,
                    line3,
                    size=10,
                    fill=theme.mask_arrow if op.mask else theme.muted,
                ),
            ]
        )

        if single_column:
            # Register-level dependencies stay in the single column's gutter.
            for input_number, input_name in enumerate(op.inputs):
                source_center_y = (
                    placements[input_name].y + layout.lane_height / 2
                )
                track_x = vector_right + 14 + input_number * 12
                target_box_y = box_y + 18 + input_number * 12
                dependency_parts.append(
                    f'<path d="M {vector_right + 3:.1f} {source_center_y:.1f} '
                    f'L {track_x:.1f} {source_center_y:.1f} '
                    f'L {track_x:.1f} {target_box_y:.1f} '
                    f'L {operation_x - 5:.1f} {target_box_y:.1f}" '
                    f'fill="none" stroke="{theme.data_arrow}" '
                    f'stroke-width="1.1" opacity="0.52" '
                    f'marker-end="url(#arrowhead)"/>'
                )

            if op.mask:
                source_center_y = (
                    placements[op.mask].y + layout.lane_height / 2
                )
                track_x = separator_x - 16
                target_box_y = box_y + layout.operation_height - 10
                dependency_parts.append(
                    f'<path d="M {vector_right + 3:.1f} {source_center_y:.1f} '
                    f'L {track_x:.1f} {source_center_y:.1f} '
                    f'L {track_x:.1f} {target_box_y:.1f} '
                    f'L {operation_x - 5:.1f} {target_box_y:.1f}" '
                    f'fill="none" stroke="{theme.mask_arrow}" '
                    f'stroke-width="1.4" stroke-dasharray="5 4" '
                    f'marker-end="url(#mask-arrowhead)"/>'
                )
        else:
            # Shared and cross-column dependencies connect directly to the box.
            for input_number, input_name in enumerate(op.inputs):
                source = placements[input_name]
                source_x = source.x + vector_width / 2
                source_y = source.y + layout.lane_height
                target_x = (
                    operation_x
                    + layout.operation_width / 2
                    - 12
                    + input_number * 24
                )
                dependency_parts.append(
                    f'<path d="{bezier(source_x, source_y, target_x, box_y - 5)}" '
                    f'fill="none" stroke="{theme.data_arrow}" '
                    f'stroke-width="1.1" opacity="0.32" '
                    f'marker-end="url(#arrowhead)"/>'
                )

            if op.mask:
                source = placements[op.mask]
                source_x = source.x + vector_width / 2
                source_y = source.y + layout.lane_height
                target_x = operation_x + layout.operation_width / 2 + 24
                dependency_parts.append(
                    f'<path d="{bezier(source_x, source_y, target_x, box_y - 5)}" '
                    f'fill="none" stroke="{theme.mask_arrow}" '
                    f'stroke-width="1.3" opacity="0.4" '
                    f'stroke-dasharray="5 4" '
                    f'marker-end="url(#mask-arrowhead)"/>'
                )

        # Operation output dependency stays to the right of the lane grid.
        result_center_y = target_y + layout.lane_height / 2
        output_track_x = separator_x - 30
        dependency_parts.append(
            f'<path d="M {operation_x:.1f} '
            f'{box_y + layout.operation_height / 2:.1f} '
            f'L {output_track_x:.1f} '
            f'{box_y + layout.operation_height / 2:.1f} '
            f'L {output_track_x:.1f} {result_center_y:.1f} '
            f'L {vector_right + 3:.1f} {result_center_y:.1f}" '
            f'fill="none" stroke="{theme.operation_border}" '
            f'stroke-width="1.2" marker-end="url(#arrowhead)"/>'
        )

    # Keep arrows behind instruction boxes, then draw registers last so lane
    # cells and labels remain readable even when the two branches cross.
    parts.extend(lane_parts)
    parts.extend(dependency_parts)
    parts.extend(box_parts)

    for name in row_order:
        placement = placements[name]
        parts.extend(
            render_register(
                registers[name],
                placement.y,
                lane_count,
                layout,
                theme,
                register_x=placement.x,
            )
        )

    parts.append(
        svg_text(
            layout.margin_x,
            height - layout.margin_y,
            (
                "solid lane arrow: executed · gray dashed: merge passthrough · "
                "omitted: zero-masked lane · orange dashed: mask control"
            ),
            size=11,
            anchor="start",
            fill=theme.muted,
            family="system-ui, -apple-system, Segoe UI, sans-serif",
        )
    )
    parts.append("</svg>")
    return "\n".join(parts)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read '{path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in '{path}': {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError("The YAML document must be a mapping.")
    return document


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Render a SIMD YAML description as SVG."
    )
    result.add_argument("input", type=Path)
    result.add_argument("-o", "--output", type=Path, default=Path("simd.svg"))
    result.add_argument(
        "--title",
        default="SIMD instruction visualization",
    )
    result.add_argument(
        "--lane-width",
        type=int,
        default=82,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)

    try:
        document = load_yaml(args.input)
        vectors = parse_registers(document.get("registers"))
        lane_count = len(next(iter(vectors.values())).lanes)

        if "bitmasks" in document and "masks" in document:
            raise ValueError(
                "Use either 'bitmasks' or the alias 'masks', not both."
            )
        masks = parse_bitmasks(
            document.get("bitmasks", document.get("masks")),
            lane_count,
        )

        duplicate_names = set(vectors) & set(masks)
        if duplicate_names:
            raise ValueError(
                "Names used as both vectors and masks: "
                + ", ".join(sorted(duplicate_names))
            )

        operations = parse_operations(document.get("operations"))
        columns = parse_render_columns(document.get("layout"), operations)
        registers, operations = evaluate(
            {**vectors, **masks},
            operations,
        )

        if args.lane_width < 48:
            raise ValueError("--lane-width must be at least 48.")

        svg = render_svg(
            list(vectors),
            list(masks),
            registers,
            operations,
            title=args.title,
            layout=Layout(lane_width=args.lane_width),
            theme=Theme(),
            columns=columns,
        )

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(svg, encoding="utf-8")
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
