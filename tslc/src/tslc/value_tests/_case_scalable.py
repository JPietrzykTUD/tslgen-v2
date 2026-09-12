"""Scalable-vector value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.conversion import ConversionKind
from tslc.catalog.model import Catalog, TestCase, TestComparison
from tslc.catalog.preconditions import PRECONDITION_DESCRIPTORS, PreconditionKind
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import OperandRole
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    scalable_case_facts,
    scalable_function_name,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    immediate_value as _immediate_value,
    mask_inputs as _mask_inputs,
    scalar_inputs as _scalar_inputs,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestCheckedPrecondition,
    ValueTestExpectation,
    ValueTestFailure,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestInvalidPreconditionValue,
    ValueTestIndex,
    ValueTestTarget,
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


def scalable_immediate_cases(
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
        case.lanes is None
        or case.expected_rule is not None
        or harness.load is None
        or harness.store is None
        or not _args_match(case, specs[0].param_kinds)
        or not tiling_is_safe(specs, catalog)
    ):
        return ()
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    immediate_inputs = _scalar_inputs(case)
    if (
        not vector_inputs
        or len(immediate_inputs) != 1
        or len(case.expected) != case.lanes
        or len(vector_inputs) != specs[0].param_kinds.count("v")
        or len(mask_inputs) != specs[0].param_kinds.count("m")
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
            store_name=harness.store,
        )
        if scalable is None:
            continue
        masked = bool(mask_inputs)
        plans.append(
            ValueTestCasePlan(
                kind=(
                    "scalable_masked_immediate"
                    if masked
                    else "scalable_immediate"
                ),
                function_name=scalable_function_name(
                    spec.extension_name,
                    case.name,
                    call_name=name if masked else None,
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(
                    vectors=vector_inputs,
                    masks=mask_inputs,
                ),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=case.comparison,
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                    immediate=_immediate_value(
                        immediate_inputs[0], spec.immediate
                    ),
                    generic_defaults=tuple(
                        default for _name, _type, default in spec.generic_params
                    ),
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_scalar_vector_cases(
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
        case.lanes is None
        or case.expected_rule is not None
        or harness.load is None
        or harness.store is None
        or not _args_match(case, specs[0].param_kinds)
        or not tiling_is_safe(specs, catalog)
    ):
        return ()
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    scalar_inputs = _scalar_inputs(case)
    runtime_indexed_lane = specs[0].param_kinds == ("v", "usize", "s")
    expected_scalar_count = 2 if runtime_indexed_lane else 1
    if (
        not vector_inputs
        or len(scalar_inputs) != expected_scalar_count
        or len(case.expected) != case.lanes
        or len(vector_inputs) != specs[0].param_kinds.count("v")
        or len(mask_inputs) != specs[0].param_kinds.count("m")
    ):
        return ()
    indexed_lane = case.index is not None or runtime_indexed_lane
    if indexed_lane:
        index_value = case.index if case.index is not None else int(scalar_inputs[0])
        if (
            mask_inputs
            or len(vector_inputs) != 1
            or not 0 <= index_value < case.lanes
            or any(
                actual != expected
                for lane, (actual, expected) in enumerate(
                    zip(vector_inputs[0], case.expected, strict=True)
                )
                if lane != index_value
            )
        ):
            return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "v":
            continue
        if case.index is not None and len(spec.generic_params) != 1:
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            mask_bit_tokens=mask_inputs,
            load_name=harness.load,
            store_name=harness.store,
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_scalar_vector",
                function_name=scalable_function_name(
                    spec.extension_name, case.name, call_name=name
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(
                    vectors=vector_inputs,
                    masks=mask_inputs,
                    scalars=scalar_inputs,
                ),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=case.comparison,
                    scalable_layout=(
                        "indexed_lane" if indexed_lane else "tiled"
                    ),
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                    generic_defaults=(
                        ()
                        if indexed_lane
                        else tuple(
                            default
                            for _name, _type, default in spec.generic_params
                        )
                    ),
                ),
                index=(
                    ValueTestIndex(
                        value=str(
                            case.index if case.index is not None else scalar_inputs[0]
                        )
                    )
                    if indexed_lane
                    else None
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_runtime_scalar_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    """Plan a scalar result selected by a runtime lane index."""

    del index
    vectors = _vector_inputs(case)
    scalars = _scalar_inputs(case)
    if (
        case.lanes is None
        or case.expected_rule is not None
        or len(case.expected) != 1
        or len(vectors) != 1
        or len(vectors[0]) != case.lanes
        or len(scalars) != 1
        or harness.load is None
    ):
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if (
            spec.type_tag != case.type_tag
            or spec.result_kind != "s"
            or spec.param_kinds != ("v", "usize")
        ):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        scalable = scalable_case_facts(
            spec,
            catalog,
            backend,
            load_name=harness.load,
        )
        if scalable is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="scalable_scalar_result",
                function_name=scalable_function_name(
                    spec.extension_name, case.name, call_name=name
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vectors, scalars=scalars),
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


def scalable_repr_cast_cases(
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
        case.lanes is None
        or case.expected_rule is not None
        or case.to_type is None
        or harness.load is None
        or harness.store is None
    ):
        return ()
    source_info = SCALAR_TYPE_INFOS.get(case.type_tag)
    target_info = SCALAR_TYPE_INFOS.get(case.to_type)
    vector_inputs = _vector_inputs(case)
    if (
        source_info is None
        or target_info is None
        or source_info.bit_width != target_info.bit_width
        or len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != case.lanes
    ):
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        target = spec.target
        if (
            spec.type_tag != case.type_tag
            or spec.result_kind != "v"
            or target is None
            or target.base_tag != case.to_type
        ):
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
                kind="scalable_repr_cast",
                function_name=scalable_function_name(
                    spec.extension_name, case.name, call_name=name
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs),
                expectation=ValueTestExpectation(
                    values=case.expected,
                    comparison=(
                        TestComparison.BITWISE
                        if spec.primitive_semantics.conversion is not None
                        and spec.primitive_semantics.conversion.kind
                        is ConversionKind.BIT_PATTERN
                        else case.comparison
                    ),
                ),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                target=ValueTestTarget(
                    type_tag=target.base_tag,
                    base_spelling=target.base_spelling,
                    lanes=case.lanes,
                ),
                scalable=scalable,
            )
        )
    return tuple(plans)


def scalable_lane_convert_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    """Plan scalable lane conversion without executing an invalid default call."""

    del index
    if (
        case.lanes is None
        or case.expected_rule is not None
        or case.to_type is None
        or harness.load is None
    ):
        return ()
    source_info = SCALAR_TYPE_INFOS.get(case.type_tag)
    target_info = SCALAR_TYPE_INFOS.get(case.to_type)
    vector_inputs = _vector_inputs(case)
    if (
        source_info is None
        or target_info is None
        or len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != case.lanes
    ):
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if (
            spec.type_tag != case.type_tag
            or spec.result_kind != "v"
            or spec.result_vector_param is None
            or spec.param_kinds != ("v",)
        ):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        target_param = next(
            (
                param
                for param in spec.type_params
                if param.name == spec.result_vector_param
                and param.base_type_binding == case.to_type
            ),
            None,
        )
        if target_param is None or target_param.base_type_binding_spelling is None:
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
        target = ValueTestTarget(
            type_tag=case.to_type,
            base_spelling=target_param.base_type_binding_spelling,
            lanes=case.lanes,
        )
        invocation = ValueTestInvocation(
            result_kind=spec.result_kind,
            param_kinds=spec.param_kinds,
        )
        if source_info.bit_width == target_info.bit_width:
            if harness.store is None or not tiling_is_safe(specs, catalog):
                continue
            plans.append(
                ValueTestCasePlan(
                    kind="scalable_repr_cast",
                    function_name=scalable_function_name(
                        spec.extension_name, case.name, call_name=name
                    ),
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
                    invocation=invocation,
                    target=target,
                    scalable=scalable,
                )
            )
            continue
        precondition = next(
            (
                item
                for item in spec.primitive_semantics.preconditions
                if item.kind is PreconditionKind.EQUAL_LANE_COUNT
            ),
            None,
        )
        binding = (
            precondition.binding(OperandRole.PRIMARY)
            if precondition is not None
            else None
        )
        if binding is None:
            continue
        plans.append(
            ValueTestCasePlan(
                kind="checked_precondition",
                function_name=scalable_function_name(
                    spec.extension_name,
                    f"{case.name}_checked_lane_count",
                    call_name=name,
                ),
                case_name=f"{case.name} checked lane-count mismatch",
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs),
                invocation=invocation,
                target=target,
                scalable=scalable,
                checked_precondition=ValueTestCheckedPrecondition(
                    PreconditionKind.EQUAL_LANE_COUNT,
                    PRECONDITION_DESCRIPTORS[
                        PreconditionKind.EQUAL_LANE_COUNT
                    ].error,
                    binding.parameter_index,
                    ValueTestInvalidPreconditionValue.LANE_COUNT_MISMATCH,
                ),
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
    "scalable_immediate_cases",
    "scalable_masked_cases",
    "scalable_repr_cast_cases",
    "scalable_lane_convert_cases",
    "scalable_runtime_scalar_cases",
    "scalable_scalar_vector_cases",
    "scalable_runtime_failure_cases",
)
