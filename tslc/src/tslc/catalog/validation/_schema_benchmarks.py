"""Schema validation for primitive ``benchmarks:`` workload facts."""

from __future__ import annotations

from tslc.catalog.signatures import parse_signature
from tslc.catalog.validation._schema_common import (
    diagnose_duplicate_fields,
    validate_known_fields,
)
from tslc.syntax.access import children, field_text, source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.syntax.ast import ParsedPrimitiveDeclaration, ParsedTslMapValue

KNOWN_BENCHMARK_FIELDS = frozenset({"latency_chain", "operand_domains"})
KNOWN_OPERAND_DOMAINS = frozenset({"nonzero", "shift_count"})


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
            KNOWN_BENCHMARK_FIELDS,
            diagnostics,
            owner=f"primitive {declaration.name!r} benchmarks",
        )
        diagnose_duplicate_fields(entries, diagnostics, label="benchmark field")
        shape = parse_signature(declaration.signature)
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
        operand_domain_fields = tuple(
            entry for entry in entries if entry.key.text == "operand_domains"
        )
        for operand_domains in operand_domain_fields:
            if not operand_domains.children and not isinstance(
                operand_domains.value, ParsedTslMapValue
            ):
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-CATALOG-BENCHMARK-OPERAND-DOMAINS-NOT-MAP",
                        message=(
                            f"primitive {declaration.name!r}: benchmark "
                            "operand_domains must be a parameter field map"
                        ),
                        source=source_span(operand_domains.source),
                    )
                )
                continue
            operands = children(operand_domains)
            diagnose_duplicate_fields(
                operands,
                diagnostics,
                label="benchmark operand domain",
            )
            for operand in operands:
                parameter = operand.key.text
                domain = field_text(operand)
                if parameter not in declaration.parameters:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-BENCHMARK-BAD-OPERAND",
                            message=(
                                f"primitive {declaration.name!r}: benchmark operand "
                                f"domain names undeclared parameter {parameter!r}"
                            ),
                            source=source_span(operand.source),
                        )
                    )
                    continue
                parameter_index = declaration.parameters.index(parameter)
                allowed_kinds = {"v", "s"} if domain == "shift_count" else {"v"}
                if (
                    shape is None
                    or parameter_index >= len(shape.param_kinds)
                    or shape.param_kinds[parameter_index] not in allowed_kinds
                ):
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-BENCHMARK-BAD-OPERAND",
                            message=(
                                f"primitive {declaration.name!r}: benchmark operand "
                                f"domain {domain!r} is not valid for this parameter kind"
                            ),
                            source=source_span(operand.source),
                        )
                    )
                if domain not in KNOWN_OPERAND_DOMAINS:
                    diagnostics.append(
                        diagnostic_at(
                            severity="error",
                            code="TSL-CATALOG-BENCHMARK-BAD-OPERAND-DOMAIN",
                            message=(
                                f"primitive {declaration.name!r}: unknown benchmark "
                                f"operand domain {domain!r}; expected one of: "
                                f"{', '.join(sorted(KNOWN_OPERAND_DOMAINS))}"
                            ),
                            source=source_span(operand.source),
                        )
                    )


__all__ = ("validate_benchmarks",)
