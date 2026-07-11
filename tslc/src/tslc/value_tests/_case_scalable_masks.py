"""Scalable-vector mask value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    render_extension_test_template,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    mask_inputs as _mask_inputs,
    maskish_inputs as _maskish_inputs,
    sanitize as _sanitize,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.literals import token_truthy
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestExpectation,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestScalable,
)


def scalable_mask_result_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    if "scalable_mask_result" not in backend.case_kinds:
        return ()
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if harness.load is None:
        return ()
    if not tiling_is_safe(specs, catalog):
        return ()
    vector_inputs = _vector_inputs(case)
    if len(case.expected) != case.lanes:
        return ()
    expected_bits = _expected_mask_bits(case.expected)
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "m":
            continue
        if len(vector_inputs) != len(spec.param_kinds):
            continue
        if any(kind != "v" for kind in spec.param_kinds):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if runtime_lanes is None or mask_check_template is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        vec_type = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        check_expr = render_extension_test_template(
            mask_check_template,
            vec=vec_type,
            case_name=f'"{case.name}"',
            mask="result",
            expected_bits=f"{expected_bits}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_mask_result",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs),
                expectation=ValueTestExpectation(values=case.expected),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    load_name=harness.load,
                    runtime_lanes_expr=runtime_lanes,
                    mask_check_expr=check_expr,
                ),
            )
        )
    return tuple(plans)

def scalable_masked_mask_result_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    if "scalable_masked_mask_result" not in backend.case_kinds:
        return ()
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if harness.load is None:
        return ()
    if not tiling_is_safe(specs, catalog):
        return ()
    mask_inputs = _maskish_inputs(case)
    vector_inputs = _vector_inputs(case)
    if len(mask_inputs) != 1 or len(case.expected) != case.lanes:
        return ()
    expected_bits = _expected_mask_bits(case.expected)
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "m":
            continue
        if spec.param_kinds.count("m") != 1:
            continue
        if any(kind not in ("m", "v") for kind in spec.param_kinds):
            continue
        if len(vector_inputs) != spec.param_kinds.count("v"):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_template = extension.test_mask_from_bits.get(backend.backend_id)
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if runtime_lanes is None or mask_template is None or mask_check_template is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        vec_type = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        mask_expr = render_extension_test_template(
            mask_template,
            vec=vec_type,
            mask_bits=f"{mask_inputs[0]}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        check_expr = render_extension_test_template(
            mask_check_template,
            vec=vec_type,
            case_name=f'"{case.name}"',
            mask="result",
            expected_bits=f"{expected_bits}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_masked_mask_result",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(vectors=vector_inputs, masks=mask_inputs),
                expectation=ValueTestExpectation(values=case.expected),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    load_name=harness.load,
                    runtime_lanes_expr=runtime_lanes,
                    mask_from_bits_exprs=(mask_expr,),
                    mask_check_expr=check_expr,
                ),
            )
        )
    return tuple(plans)

def scalable_mask_logic_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    del harness
    if "scalable_mask_logic" not in backend.case_kinds:
        return ()
    if case.lanes is None or case.expected_rule is not None:
        return ()
    mask_inputs = _mask_inputs(case)
    if len(case.expected) != 1:
        return ()
    expected_bits = _mask_bits(case.expected[0])
    if expected_bits is None:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "m":
            continue
        if not spec.param_kinds or any(kind != "m" for kind in spec.param_kinds):
            continue
        if len(mask_inputs) != len(spec.param_kinds):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_template = extension.test_mask_from_bits.get(backend.backend_id)
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if runtime_lanes is None or mask_template is None or mask_check_template is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        vec_type = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        mask_exprs = tuple(
            render_extension_test_template(
                mask_template,
                vec=vec_type,
                mask_bits=f"{mask_bits}ull",
                authored_lanes=str(case.lanes),
                lanes="lanes",
                base_type=spec.base_type_spelling,
                base=spec.base_type_spelling,
            )
            for mask_bits in mask_inputs
        )
        check_expr = render_extension_test_template(
            mask_check_template,
            vec=vec_type,
            case_name=f'"{case.name}"',
            mask="result",
            expected_bits=f"{expected_bits}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_mask_logic",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(masks=mask_inputs),
                expectation=ValueTestExpectation(values=case.expected),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    runtime_lanes_expr=runtime_lanes,
                    mask_from_bits_exprs=mask_exprs,
                    mask_check_expr=check_expr,
                ),
            )
        )
    return tuple(plans)

def scalable_mask_constant_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    del harness
    if "scalable_mask_constant" not in backend.case_kinds:
        return ()
    if case.lanes is None or case.expected_rule is not None:
        return ()
    if len(case.expected) != 1:
        return ()
    expected_bits = _mask_bits(case.expected[0])
    if expected_bits is None:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag or spec.result_kind != "m":
            continue
        if spec.param_kinds:
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if runtime_lanes is None or mask_check_template is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        vec_type = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        check_expr = render_extension_test_template(
            mask_check_template,
            vec=vec_type,
            case_name=f'"{case.name}"',
            mask="result",
            expected_bits=f"{expected_bits}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_mask_constant",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                expectation=ValueTestExpectation(values=case.expected),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    runtime_lanes_expr=runtime_lanes,
                    mask_check_expr=check_expr,
                ),
            )
        )
    return tuple(plans)

def scalable_mask_conversion_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend: ValueTestBackendSupport,
) -> tuple[ValueTestCasePlan, ...]:
    del index
    del harness
    if "scalable_mask_conversion" not in backend.case_kinds:
        return ()
    if case.lanes is None or case.expected_rule is not None:
        return ()
    mask_inputs = _maskish_inputs(case)
    if len(mask_inputs) != 1 or len(case.expected) != 1:
        return ()
    expected_bits = _mask_bits(case.expected[0])
    if expected_bits is None:
        return ()
    plans: list[ValueTestCasePlan] = []
    for spec in specs:
        if spec.type_tag != case.type_tag:
            continue
        if (spec.result_kind, spec.param_kinds) not in (("m", ("im",)), ("im", ("m",))):
            continue
        if case.extension is not None and spec.extension_name != case.extension:
            continue
        extension = catalog.extensions.get(spec.extension_name)
        if (
            extension is None
            or extension.vector_bits_kind != "scalable"
            or extension.imask_policy.kind != "same_as_mask_type"
        ):
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_template = extension.test_mask_from_bits.get(backend.backend_id)
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if runtime_lanes is None or mask_template is None or mask_check_template is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        vec_type = f"tsl::simd<{spec.base_type_spelling}, tsl::{spec.extension_name}>"
        mask_expr = render_extension_test_template(
            mask_template,
            vec=vec_type,
            mask_bits=f"{mask_inputs[0]}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        check_expr = render_extension_test_template(
            mask_check_template,
            vec=vec_type,
            case_name=f'"{case.name}"',
            mask="result",
            expected_bits=f"{expected_bits}ull",
            authored_lanes=str(case.lanes),
            lanes="lanes",
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_mask_conversion",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(masks=mask_inputs),
                expectation=ValueTestExpectation(values=case.expected),
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    runtime_lanes_expr=runtime_lanes,
                    mask_from_bits_exprs=(mask_expr,),
                    mask_check_expr=check_expr,
                ),
            )
        )
    return tuple(plans)

def _expected_mask_bits(values: tuple[str, ...]) -> int:
    bits = 0
    for index, value in enumerate(values):
        if token_truthy(value):
            bits |= 1 << index
    return bits

def _mask_bits(token: str) -> int | None:
    try:
        return int(token.strip().strip('"'), 0)
    except ValueError:
        return None

__all__ = (
    "scalable_mask_constant_cases",
    "scalable_mask_conversion_cases",
    "scalable_mask_logic_cases",
    "scalable_mask_result_cases",
    "scalable_masked_mask_result_cases",
)
