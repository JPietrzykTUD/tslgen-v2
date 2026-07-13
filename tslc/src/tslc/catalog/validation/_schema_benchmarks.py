"""Schema validation for primitive ``benchmarks:`` workload facts."""

from __future__ import annotations

from tslc.catalog.signatures import parse_signature
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    validate_known_fields,
)
from tslc.catalog.validation.source_spans import children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import ParsedPrimitiveDeclaration, ParsedTslMapValue

_KNOWN_BENCHMARK_FIELDS = frozenset({"latency_chain"})


def validate_benchmarks(
    declaration: ParsedPrimitiveDeclaration,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate the small semantic benchmark contract before catalog promotion."""

    for parsed in declaration.fields_by_name("benchmarks"):
        field = parsed.field
        if not field.children and not isinstance(field.value, ParsedTslMapValue):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-CATALOG-BENCHMARKS-NOT-MAP",
                    message=(
                        f"primitive {declaration.name!r}: `benchmarks` must be a field map"
                    ),
                    source=source_span(field.source),
                )
            )
            continue
        entries = children(field)
        validate_known_fields(
            entries,
            _KNOWN_BENCHMARK_FIELDS,
            diagnostics,
            owner=f"primitive {declaration.name!r} benchmarks",
        )
        diagnose_duplicate_fields(entries, diagnostics, label="benchmark field")
        latency_fields = tuple(
            entry for entry in entries if entry.key.text == "latency_chain"
        )
        for latency in latency_fields:
            parameter = field_text(latency)
            if not parameter or parameter not in declaration.parameters:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-BENCHMARK-BAD-LATENCY-CHAIN",
                        message=(
                            f"primitive {declaration.name!r}: benchmark latency_chain must "
                            "name a declared parameter"
                        ),
                        source=source_span(latency.source),
                    )
                )
                continue
            shape = parse_signature(declaration.signature)
            parameter_index = declaration.parameters.index(parameter)
            if (
                shape is None
                or parameter_index >= len(shape.param_kinds)
                or shape.result_kind != "v"
                or shape.param_kinds[parameter_index] != "v"
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-BENCHMARK-BAD-LATENCY-CHAIN",
                        message=(
                            f"primitive {declaration.name!r}: benchmark latency_chain "
                            "requires a vector result and a vector parameter"
                        ),
                        source=source_span(latency.source),
                    )
                )


__all__ = ("validate_benchmarks",)
