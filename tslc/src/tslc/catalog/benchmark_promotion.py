"""Promote primitive ``benchmarks:`` blocks into typed catalog facts."""

from __future__ import annotations

from typing import Literal, cast

from tslc.syntax.access import child as _child
from tslc.syntax.access import children as _children
from tslc.syntax.access import field_text as _field_text
from tslc.syntax.access import source_span as _source_span
from tslc.catalog.model import (
    PrimitiveBenchmarkOperandDomain,
    PrimitiveBenchmarkSpec,
)
from tslc.syntax.ast import ParsedPrimitiveDeclaration


def build_benchmark_spec(declaration: ParsedPrimitiveDeclaration) -> PrimitiveBenchmarkSpec:
    fields = declaration.fields_by_name("benchmarks")
    if not fields:
        return PrimitiveBenchmarkSpec()
    field = fields[0].field
    operand_domains = tuple(
        PrimitiveBenchmarkOperandDomain(
            parameter=operand.key.text,
            domain=cast(
                Literal["nonzero", "shift_count"],
                _field_text(operand),
            ),
            source=_source_span(operand.source),
        )
        for operand in _children(_child(field, "operand_domains"))
        if _field_text(operand) in {"nonzero", "shift_count"}
    )
    return PrimitiveBenchmarkSpec(
        latency_chain=_field_text(_child(field, "latency_chain")),
        operand_domains=operand_domains,
        source=_source_span(field.source),
    )


__all__ = ("build_benchmark_spec",)
