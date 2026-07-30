"""Scalable-vector value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    scalable_case_facts,
    scalable_function_name,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    mask_inputs as _mask_inputs,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestExpectation,
    ValueTestFailure,
    ValueTestInputs,
    ValueTestInvocation,
)


def scalable_golden_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if harness.load is None or harness.store is None:
        return ()
    if not tiling_is_safe(specs, catalog):
        return ()
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != len(specs[0].param_kinds) or len(case.expected) != case.lanes:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "v":
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            load_name=harness.load,
            store_name=harness.store,
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_golden",
                function_name=scalable_function_name(spec.extension_name, case.name),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=case.comparison,
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_masked_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if harness.load is None or harness.store is None:
        return ()
    if not tiling_is_safe(specs, catalog):
        return ()
    mask_inputs = _mask_inputs(case)
    vector_inputs = _vector_inputs(case)
    if len(mask_inputs) != 1 or len(case.expected) != case.lanes:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "v":
            continue
        if len(vector_inputs) != spec.param_kinds.count("v"):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            mask_bit_tokens=(mask_inputs[0],),
            load_name=harness.load,
            store_name=harness.store,
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_masked",
                function_name=scalable_function_name(
                    spec.extension_name, case.name, call_name=name
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs, masks=mask_inputs),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=case.comparison,
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_runtime_failure_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    if (
        case.role != "runtime_failure"
        or case.failure is None
        or case.lanes is None
        or harness.load is None
        or not _args_match(case, specs[0].param_kinds)
        or not tiling_is_safe(specs, catalog)
    ):
        return ()
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    if (
        not vector_inputs
        or any(len(values) != case.lanes for values in vector_inputs)
        or any(kind not in {"m", "v"} for kind in specs[0].param_kinds)
    ):
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag:
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            mask_bit_tokens=mask_inputs,
            load_name=harness.load,
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_runtime_failure",
                function_name=scalable_function_name(spec.extension_name, case.name),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs, masks=mask_inputs),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=scalable,
                failure=ValueTestFailure(reason=case.failure),
            )
        )
    return tuple(plans)


__all__ = (
    "scalable_golden_cases",
    "scalable_masked_cases",
    "scalable_runtime_failure_cases",
)
