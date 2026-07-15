"""Deterministic YAML formatting for decided PIVOT export values."""

from __future__ import annotations

import json

from tslc.pivot.model import PivotDefinition, PivotDocument


def render_pivot_yaml(document: PivotDocument) -> str:
    lines = [
        f"name: {_scalar(document.name)}",
        "input:" if document.inputs else "input: []",
        *(f"  - {_scalar(name)}" for name in document.inputs),
        f"output: {_scalar(document.output)}",
        "definitions:",
    ]
    for definition in document.definitions:
        lines.extend(_definition_lines(definition))
    return "\n".join(lines) + "\n"


def _definition_lines(definition: PivotDefinition) -> list[str]:
    lines = [
        f"  - isa: {_scalar(definition.isa)}",
        f"    dtype: {_scalar(definition.dtype)}",
        "    signature:",
    ]
    lines.extend(
        f"      {_key(name)}: {_scalar(type_spelling)}"
        for name, type_spelling in definition.signature
    )
    lines.append("    direct:")
    lines.extend(f"      - {_scalar(statement)}" for statement in definition.direct)
    return lines


def _key(value: str) -> str:
    return value if value.isidentifier() else _scalar(value)


def _scalar(value: str) -> str:
    # JSON double-quoted strings are YAML 1.2 scalars and avoid emitter-specific
    # coercions for values such as ``null``, ``on``, or intrinsic punctuation.
    return json.dumps(value, ensure_ascii=False)


__all__ = ("render_pivot_yaml",)
