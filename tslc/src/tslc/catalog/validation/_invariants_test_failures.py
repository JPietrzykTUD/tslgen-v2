"""Catalog invariants for authored expected-failure value tests."""

from __future__ import annotations

from collections.abc import Hashable

from tslc.catalog.arithmetic import ArithmeticOperandRole, ArithmeticOperation
from tslc.catalog.model import (
    Catalog,
    ImmediateRangeUpperKind,
    Primitive,
    RESULT_DIM_BASE,
    TestCase,
    TestFailureReason,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at


def validate_test_failure_cases(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate each source-authored failure case once across wildcard variants."""

    seen: set[Hashable] = set()
    for index, primitive in enumerate(catalog.primitives):
        key: Hashable = (
            primitive.source
            if primitive.source is not None
            else (primitive.name, primitive.signature, index)
        )
        if key in seen:
            continue
        seen.add(key)
        for case in primitive.tests:
            if case.role not in {"runtime_failure", "compile_failure"}:
                continue
            _validate_failure_case(primitive, case, diagnostics)


def _validate_failure_case(
    primitive: Primitive,
    case: TestCase,
    diagnostics: list[Diagnostic],
) -> None:
    source = case.failure_source or case.source or primitive.source
    if case.failure is TestFailureReason.CONVERSION_CHUNK_INDEX_OUT_OF_RANGE:
        _validate_conversion_chunk_index(primitive, case, source, diagnostics)
        return
    if case.role == "runtime_failure":
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-RUNTIME-FAILURE-IS-PRECONDITION",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "runtime integer-zero-divisor cases must be expressed by "
                    "the active_divisor_nonzero precondition and checked tests"
                ),
                source=source,
            )
        )
        return
    if case.failure is TestFailureReason.INTEGER_ZERO_DIVISOR:
        _validate_integer_zero_divisor(primitive, case, source, diagnostics)


def _validate_integer_zero_divisor(
    primitive: Primitive,
    case: TestCase,
    source: SourceSpan | None,
    diagnostics: list[Diagnostic],
) -> None:
    contract = primitive.arithmetic
    if contract is None or not contract.operations.intersection(
        {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-CONTRACT",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "integer-zero-divisor compile failure requires an "
                    "arithmetic division or remainder operation"
                ),
                source=source,
            )
        )
        return
    binding = contract.binding(ArithmeticOperandRole.DIVISOR)
    if binding is None:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-DIVISOR",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "integer-zero-divisor failure requires a resolved divisor role"
                ),
                source=source,
            )
        )
        return
    info = SCALAR_TYPE_INFOS.get(case.type_tag)
    if info is not None and info.floating:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-DOMAIN",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "integer-zero-divisor failure requires an integer lane type"
                ),
                source=source,
            )
        )
    if binding.parameter_kind != "sImm":
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-PHASE",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: role "
                    f"{case.role!r} requires a compile-time sImm divisor binding, got "
                    f"{binding.parameter_kind!r}"
                ),
                source=source,
            )
        )


def _validate_conversion_chunk_index(
    primitive: Primitive,
    case: TestCase,
    source: SourceSpan | None,
    diagnostics: list[Diagnostic],
) -> None:
    if case.role != "compile_failure":
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-PHASE",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "conversion chunk-index failure must use role 'compile_failure'"
                ),
                source=source,
            )
        )
        return
    immediate = next(
        (
            parameter
            for parameter in primitive.immediate_params
            if parameter.valid_range is not None
            and parameter.valid_range.upper.kind
            is ImmediateRangeUpperKind.CONVERSION_CHUNK_COUNT
        ),
        None,
    )
    if (
        primitive.result_target != (RESULT_DIM_BASE, "ToBase")
        or immediate is None
    ):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-CONTRACT",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "conversion chunk-index failure requires a typed "
                    "conversion_chunk_count valid_range"
                ),
                source=source,
            )
        )
        return
    source_info = SCALAR_TYPE_INFOS.get(case.type_tag)
    target_info = SCALAR_TYPE_INFOS.get(case.to_type or "")
    if source_info is None or target_info is None or case.index is None:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-DOMAIN",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: "
                    "conversion chunk-index failure requires source type, "
                    "target type, and index"
                ),
                source=source,
            )
        )
        return
    narrower, wider = sorted((source_info.bit_width, target_info.bit_width))
    if wider % narrower:
        return
    chunk_count = wider // narrower
    if 0 <= case.index < chunk_count:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-TEST-FAILURE-NOT-INVALID",
                message=(
                    f"primitive {primitive.name!r} test {case.name!r}: index "
                    f"{case.index} is valid for {chunk_count} conversion chunks"
                ),
                source=source,
            )
        )


__all__ = ("validate_test_failure_cases",)
