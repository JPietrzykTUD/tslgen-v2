"""Scalable-vector memory value-test case-plan builders."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.checked_api import applicable_checked_condition
from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.catalog.memory import MemoryIndexedLaneExtent
from tslc.catalog.preconditions import (
    PreconditionErrorKind,
    PreconditionKind,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
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
    ValueTestCheckedPrecondition,
    ValueTestExpectation,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestInvalidPreconditionValue,
    ValueTestIndex,
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


def scalable_indexed_memory_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
    *,
    result_kind: str,
    index_base_spelling: str | None,
) -> tuple[ValueTestCasePlan, ...]:
    """Plan runtime-lane indexed memory tests for scalable vector profiles."""

    if case.lanes is None or case.expected_rule is not None or case.scale is None:
        return ()
    if harness.load is None or harness.store is None:
        return ()
    vectors = _vector_inputs(case)
    masks = _maskish_inputs(case)
    expected_vectors = (2, 3) if result_kind == "v" else (2,)
    if len(vectors) not in expected_vectors or not case.expected:
        return ()
    if case.index_type is not None and index_base_spelling is None:
        return ()
    checked_condition = applicable_checked_condition(
        specs,
        PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID,
    )
    plans: list[ValueTestCasePlan] = []
    selected_extensions: set[str] = set()
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != result_kind:
            continue
        if "vidx" not in spec.param_kinds and tuple(spec.param_kinds) != (
            "cptr",
            "cptr",
            "sImm",
        ):
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
            mask_bit_tokens=masks,
            load_name=harness.load,
            store_name=harness.store,
        )
        if scalable is None:
            continue
        selected_extensions.add(spec.extension_name)
        memory = spec.primitive_semantics.memory
        partial = (
            memory is not None
            and memory.indexed_lane_extent is MemoryIndexedLaneExtent.INDEX_VECTOR
        )
        index_spelling = index_base_spelling or spec.base_type_spelling
        plan = ValueTestCasePlan(
            kind=(
                "scalable_indexed_load"
                if result_kind == "v"
                else "scalable_indexed_store"
            ),
            function_name=scalable_function_name(
                spec.extension_name, case.name, call_name=name
            ),
            case_name=case.name,
            call_name=name,
            type_tag=case.type_tag,
            base_spelling=spec.base_type_spelling,
            lanes=case.lanes,
            inputs=ValueTestInputs(vectors=vectors, masks=masks),
            expectation=ValueTestExpectation(
                values=case.expected,
                comparison=case.comparison,
                scalable_layout="indexed_partial" if partial else "tiled",
            ),
            invocation=ValueTestInvocation(
                result_kind=spec.result_kind,
                param_kinds=spec.param_kinds,
                immediate=str(case.scale),
            ),
            target=(
                ValueTestTarget(
                    type_tag=case.type_tag,
                    base_spelling=spec.base_type_spelling,
                    lanes=case.lanes,
                )
                if result_kind == "v"
                else None
            ),
            index=ValueTestIndex(
                type_tag=case.index_type or case.type_tag,
                base_spelling=index_spelling,
                lanes=len(vectors[1]),
                style=(
                    "pointer"
                    if tuple(spec.param_kinds) == ("cptr", "cptr", "sImm")
                    else "register"
                ),
            ),
            memory=ValueTestMemory(
                buffer_length=(
                    len(vectors[0])
                    if result_kind == "v"
                    else len(case.expected)
                )
            ),
            scalable=scalable,
        )
        plans.append(plan)
        if index != 0 or checked_condition is None:
            continue
        failures = [
            (
                "out_of_range",
                checked_condition.error,
                ValueTestInvalidPreconditionValue.INDEXED_ADDRESS_OUT_OF_RANGE,
                plan.invocation.immediate,
            )
        ]
        invalid_lane = 0
        if scalable.mask_bits:
            active_lane = next(
                (
                    lane
                    for lane in range(case.lanes)
                    if (scalable.mask_bits[0] >> lane) & 1
                ),
                None,
            )
            if active_lane is None:
                continue
            invalid_lane = active_lane
        scalar_info = SCALAR_TYPE_INFOS.get(case.type_tag)
        if (
            scalar_info is not None
            and scalar_info.bit_width > 8
            and PreconditionErrorKind.MISALIGNED in checked_condition.errors
        ):
            failures.append(
                (
                    "misaligned",
                    PreconditionErrorKind.MISALIGNED,
                    ValueTestInvalidPreconditionValue.INDEXED_ADDRESS_MISALIGNED,
                    "1",
                )
            )
        for suffix, error, invalid_value, immediate in failures:
            plans.append(
                replace(
                    plan,
                    kind="checked_precondition",
                    function_name=f"{plan.function_name}__checked_{suffix}",
                    case_name=f"{plan.case_name} checked {suffix}",
                    expectation=ValueTestExpectation(),
                    invocation=replace(plan.invocation, immediate=immediate),
                    checked_precondition=ValueTestCheckedPrecondition(
                        PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID,
                        error,
                        checked_condition.parameter_index,
                        invalid_value,
                        invalid_lane_index=invalid_lane,
                    ),
                )
            )
    return tuple(plans)


def _axis_matches_case(spec: LoweredSpecialization, case: TestCase) -> bool:
    return all(case.attrs.get(name, value) == value for name, value in spec.axis)


__all__ = (
    "scalable_mask_store_cases",
    "scalable_masked_pointer_load_cases",
    "scalable_masked_pointer_store_cases",
    "scalable_indexed_memory_cases",
)
