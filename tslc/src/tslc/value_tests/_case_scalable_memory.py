"""Scalable-vector memory value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    scalable_case_facts,
    scalable_function_name,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    axis_args as _axis_args,
    maskish_inputs as _maskish_inputs,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestExpectation,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestTarget,
)
from tslc.value_tests.param_layouts import resolve_param_layout


def scalable_masked_pointer_load_cases(
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
    mask_inputs = _maskish_inputs(case)
    if len(mask_inputs) != 1 or len(case.expected) != case.lanes:
        return ()
    plans: list[ValueTestCasePlan] = []
    selected_extensions: set[str] = set()
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "v":
            continue
        if tuple(spec.param_kinds) not in {("m", "cptr"), ("m", "cptr", "v")}:
            continue
        if len(vector_inputs) != 1 + spec.param_kinds.count("v"):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        if not _axis_matches_case(spec, case):
            continue
        if spec.extension_name in selected_extensions:
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
        selected_extensions.add(spec.extension_name)
        plans.append(
            ValueTestCasePlan(
                kind="scalable_masked_pointer_load",
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
                    axis_args=_axis_args(spec, case),
                ),
                memory=ValueTestMemory(buffer_offset=case.offset or 0),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_masked_pointer_store_cases(
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
    mask_inputs = _maskish_inputs(case)
    if (
        len(vector_inputs) != 1
        or len(mask_inputs) != 1
        or len(case.expected) != case.lanes
    ):
        return ()
    plans: list[ValueTestCasePlan] = []
    selected_extensions: set[str] = set()
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "void":
            continue
        if tuple(spec.param_kinds) != ("m", "ptr", "v"):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        if not _axis_matches_case(spec, case):
            continue
        if spec.extension_name in selected_extensions:
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
        selected_extensions.add(spec.extension_name)
        plans.append(
            ValueTestCasePlan(
                kind="scalable_masked_pointer_store",
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
                    axis_args=_axis_args(spec, case),
                ),
                memory=ValueTestMemory(buffer_offset=case.offset or 0),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_mask_store_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
    primitive: Primitive,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    del harness
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if not tiling_is_safe(specs, catalog):
        return ()
    if case.attrs.get("packed") != "false":
        return ()
    offset = case.offset or 0
    if len(case.expected) < offset + case.lanes:
        return ()
    mask_inputs = _maskish_inputs(case)
    if len(mask_inputs) != 1:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "void":
            continue
        if tuple(spec.param_kinds) != ("ptr", "m"):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        if not _axis_matches_case(spec, case):
            continue
        layout = resolve_param_layout(primitive, "ptr", case, (spec,))
        if layout is None:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            mask_bit_tokens=(mask_inputs[0],),
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_mask_store",
                function_name=scalable_function_name(
                    spec.extension_name, case.name, call_name=name
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(masks=mask_inputs),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=case.comparison,
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                    axis_args=_axis_args(spec, case),
                ),
                target=ValueTestTarget(
                    type_tag=layout.type_tag,
                    base_spelling=layout.base_spelling,
                ),
                memory=ValueTestMemory(
                    buffer_offset=offset,
                    buffer_length=len(case.expected),
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def _axis_matches_case(spec: LoweredSpecialization, case: TestCase) -> bool:
    return all(case.attrs.get(name, value) == value for name, value in spec.axis)


__all__ = (
    "scalable_mask_store_cases",
    "scalable_masked_pointer_load_cases",
    "scalable_masked_pointer_store_cases",
)
