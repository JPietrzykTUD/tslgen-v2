"""Scalable-vector memory value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests._case_scalable_common import (
    render_extension_test_template,
    tiling_is_safe,
)
from tslc.value_tests.case_helpers import (
    axis_args as _axis_args,
    maskish_inputs as _maskish_inputs,
    sanitize as _sanitize,
)
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestBackendSupport,
    ValueTestCasePlan,
    ValueTestExpectation,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestScalable,
    ValueTestTarget,
)
from tslc.value_tests.param_layouts import resolve_param_layout


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
    if "scalable_mask_store" not in backend.case_kinds:
        return ()
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
        extension = catalog.extensions.get(spec.extension_name)
        if extension is None or extension.vector_bits_kind != "scalable":
            continue
        runtime_lanes = extension.test_runtime_lanes.get(backend.backend_id)
        mask_template = extension.test_mask_from_bits.get(backend.backend_id)
        if runtime_lanes is None or mask_template is None:
            continue
        layout = resolve_param_layout(primitive, "ptr", case, (spec,))
        if layout is None:
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
                kind="scalable_mask_store",
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
                scalable=ValueTestScalable(
                    source_extension=spec.extension_name,
                    runtime_lanes_expr=runtime_lanes,
                    mask_from_bits_exprs=(mask_expr,),
                ),
            )
        )
    return tuple(plans)


def _axis_matches_case(spec: LoweredSpecialization, case: TestCase) -> bool:
    return all(case.attrs.get(name, value) == value for name, value in spec.axis)


__all__ = ("scalable_mask_store_cases",)
