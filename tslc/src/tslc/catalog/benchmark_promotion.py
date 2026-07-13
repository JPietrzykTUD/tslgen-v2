"""Promote primitive ``benchmarks:`` blocks into typed catalog facts."""

from __future__ import annotations

from tslc.catalog._builder_common import _child, _field_text, _source_span
from tslc.catalog.model import PrimitiveBenchmarkSpec
from tslc.syntax.ast import ParsedPrimitiveDeclaration


def build_benchmark_spec(declaration: ParsedPrimitiveDeclaration) -> PrimitiveBenchmarkSpec:
    fields = declaration.fields_by_name("benchmarks")
    if not fields:
        return PrimitiveBenchmarkSpec()
    field = fields[0].field
    return PrimitiveBenchmarkSpec(
        latency_chain=_field_text(_child(field, "latency_chain")),
        source=_source_span(field.source),
    )


__all__ = ("build_benchmark_spec",)
