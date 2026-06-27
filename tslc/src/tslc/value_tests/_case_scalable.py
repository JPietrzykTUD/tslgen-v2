"""Scalable-vector value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    render_extension_test_template,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    mask_inputs as _mask_inputs,
    sanitize as _sanitize,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
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
    if "scalable_golden" not in backend.case_kinds:
        return ()
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
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        if runtime_lanes is None:
            continue
        runtime_lanes = render_extension_test_template(
            runtime_lanes,
            base_type=spec.base_type_spelling,
            base=spec.base_type_spelling,
        )
        plans.append(
            ValueTestCasePlan(
                kind="scalable_golden",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                vector_inputs=vector_inputs,
                expected=case.expected,
                result_kind=spec.result_kind,
                param_kinds=spec.param_kinds,
                source_extension=spec.extension_name,
                load_name=harness.load,
                store_name=harness.store,
                runtime_lanes_expr=runtime_lanes,
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
    if "scalable_masked" not in backend.case_kinds:
        return ()
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
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_template = extension.test_mask_from_bits.get(backend.backend_id)
        if runtime_lanes is None or mask_template is None:
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
        plans.append(
            ValueTestCasePlan(
                kind="scalable_masked",
                function_name=(
                    f"test_scalable_{_sanitize(spec.extension_name)}_"
                    f"{_sanitize(name)}_{_sanitize(case.name)}"
                ),
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=spec.base_type_spelling,
                lanes=case.lanes,
                vector_inputs=vector_inputs,
                expected=case.expected,
                result_kind=spec.result_kind,
                param_kinds=spec.param_kinds,
                mask_inputs=mask_inputs,
                source_extension=spec.extension_name,
                load_name=harness.load,
                store_name=harness.store,
                runtime_lanes_expr=runtime_lanes,
                mask_from_bits_exprs=(mask_expr,),
            )
        )
    return tuple(plans)


__all__ = (
    "scalable_golden_cases",
    "scalable_masked_cases",
)
