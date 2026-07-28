"""Conversion and extension-representation value-test case-plan builders."""

from __future__ import annotations

from tslc.catalog.arithmetic import ArithmeticGuarantee, ArithmeticOperandRole
from tslc.catalog.model import Catalog, Primitive, TestCase
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import (
    args_match as _args_match,
    base_spelling as _base_spelling,
    convert_match as _convert_match,
    extension_repr_match as _extension_repr_match,
    function_name as _function_name,
    immediate_value as _immediate_value,
    load_convert_match as _load_convert_match,
    lane_convert_match as _lane_convert_match,
    mask_inputs as _mask_inputs,
    repr_cast_match as _repr_cast_match,
    sanitize as _sanitize,
    scalar_inputs as _scalar_inputs,
    valid_generic_lanes as _valid_generic_lanes,
    vector_inputs as _vector_inputs,
)
from tslc.value_tests.lane_math import SEED_MIX_64, whole_lanes as _whole_lanes
from tslc.value_tests.model import (
    HarnessPrimitiveNames,
    ValueTestCasePlan,
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestRepresentation,
    ValueTestTarget,
)


def extension_result_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    *,
    undefined_upper: bool,
) -> ValueTestCasePlan | None:
    """Plan a fixed-extension result with one or more source-width vectors.

    Undefined-width growth still has a deterministic low prefix.  The planner
    decides that comparison width here; renderers only compare the authored
    expectation carried by the plan.
    """

    if case.expected_rule is not None or case.lanes is None:
        return None
    if not harness.round_trip_ready:
        return None
    match = _extension_repr_match(case, specs)
    if match is None or case.to_extension is None:
        return None
    target_extension = catalog.extensions.get(case.to_extension)
    if (
        target_extension is None
        or target_extension.vector_bits_kind != "fixed"
        or target_extension.vector_bits <= 0
    ):
        return None
    target_lanes = _whole_lanes(target_extension.vector_bits, case.type_tag)
    if target_lanes is None:
        return None
    vector_inputs = _vector_inputs(case)
    if (
        len(vector_inputs) != len(match.param_kinds)
        or any(len(values) != case.lanes for values in vector_inputs)
    ):
        return None
    expected_lanes = case.lanes if undefined_upper else target_lanes
    if len(case.expected) != expected_lanes:
        return None
    return ValueTestCasePlan(
        kind="extension_result",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        invocation=ValueTestInvocation(
            result_kind=match.result_kind,
            param_kinds=match.param_kinds,
        ),
        target=ValueTestTarget(
            type_tag=case.type_tag,
            base_spelling=match.base_type_spelling,
            lanes=target_lanes,
        ),
        representation=ValueTestRepresentation(
            source_extension=case.extension or match.extension_name,
            target_extension=case.to_extension,
            from_array_name=harness.from_array,
            to_array_name=harness.to_array,
        ),
    )

def load_convert_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames | None = None,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None or case.to_type is None:
        return None
    match = _load_convert_match(case, specs)
    if match is None or match.target is None:
        return None
    if case.extension is not None and (harness is None or harness.to_array is None):
        return None
    vector_inputs = _vector_inputs(case)
    if len(vector_inputs) != 1 or len(case.expected) == 0:
        return None
    source_lanes = _valid_generic_lanes(case.type_tag, len(vector_inputs[0]))
    return ValueTestCasePlan(
        kind="load_convert",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=source_lanes,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        invocation=ValueTestInvocation(
            result_kind=match.result_kind,
            param_kinds=match.param_kinds,
        ),
        target=ValueTestTarget(
            type_tag=case.to_type,
            base_spelling=match.target.base_spelling,
            lanes=len(case.expected),
        ),
        representation=(
            ValueTestRepresentation(
                source_extension=match.extension_name,
                target_extension=match.target.extension_isa,
                to_array_name=harness.to_array if harness else None,
            )
            if case.extension is not None
            else None
        ),
    )

def convert_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> ValueTestCasePlan | None:
    if case.index is None or case.expected_rule is not None:
        return None
    match = _convert_match(case, specs)
    if match is None or match.target is None or match.target.lane_parameter is None:
        return None
    vector_inputs = _vector_inputs(case)
    out_lanes = int(match.target.lane_parameter)
    if (
        len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != out_lanes
    ):
        return None
    return ValueTestCasePlan(
        kind="convert",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes or 0,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        target=ValueTestTarget(
            type_tag=case.to_type,
            base_spelling=match.target.base_spelling,
            lanes=out_lanes,
        ),
        index=ValueTestIndex(value=str(case.index)),
    )

def repr_cast_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames | None = None,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None:
        return None
    match = _repr_cast_match(case, specs)
    if match is None or match.target is None:
        return None
    if case.extension is not None and (
        harness is None or not harness.round_trip_ready
    ):
        return None
    vector_inputs = _vector_inputs(case)
    if case.lanes is None or len(vector_inputs) != 1 or len(vector_inputs[0]) != case.lanes:
        return None
    target_lanes = len(case.expected)
    if target_lanes == 0:
        return None
    return ValueTestCasePlan(
        kind="repr_cast",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        target=ValueTestTarget(
            type_tag=case.to_type,
            base_spelling=match.target.base_spelling,
            lanes=target_lanes,
        ),
        representation=(
            ValueTestRepresentation(
                source_extension=match.extension_name,
                target_extension=match.target.extension_isa,
                from_array_name=harness.from_array if harness else None,
                to_array_name=harness.to_array if harness else None,
            )
            if case.extension is not None
            else None
        ),
    )


def lane_convert_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None or case.lanes is None:
        return None
    match = _lane_convert_match(case, specs)
    if match is None or match.result_vector_param is None:
        return None
    target_param = next(
        (
            param
            for param in match.type_params
            if param.name == match.result_vector_param
            and param.base_type_binding == case.to_type
        ),
        None,
    )
    if target_param is None or target_param.base_type_binding_spelling is None:
        return None
    if case.extension is not None and not harness.round_trip_ready:
        return None
    vector_inputs = _vector_inputs(case)
    if (
        len(vector_inputs) != 1
        or len(vector_inputs[0]) != case.lanes
        or len(case.expected) != case.lanes
    ):
        return None
    return ValueTestCasePlan(
        kind="lane_convert",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=case.lanes,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        target=ValueTestTarget(
            type_tag=case.to_type,
            base_spelling=target_param.base_type_binding_spelling,
            lanes=case.lanes,
        ),
        representation=(
            ValueTestRepresentation(
                source_extension=match.extension_name,
                target_extension="generic",
                from_array_name=harness.from_array,
                to_array_name=harness.to_array,
            )
            if case.extension is not None
            else None
        ),
    )

def extension_repr_case(
    kind: str,
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    harness: HarnessPrimitiveNames,
) -> ValueTestCasePlan | None:
    if case.expected_rule is not None:
        return None
    match = _extension_repr_match(case, specs)
    if match is None:
        return None
    vector_inputs = _vector_inputs(case)
    imm_inputs = _scalar_inputs(case)
    if len(imm_inputs) != 1:
        return None
    if kind == "extension_extract":
        lanes = case.lanes or (len(vector_inputs[0]) if vector_inputs else None)
        if lanes is None or len(vector_inputs) != 1 or len(vector_inputs[0]) != lanes:
            return None
    else:
        lanes = case.lanes or (len(vector_inputs[1]) if len(vector_inputs) > 1 else None)
        if lanes is None or len(vector_inputs) != 2 or len(vector_inputs[1]) != lanes:
            return None
    return ValueTestCasePlan(
        kind=kind,
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=case.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=lanes,
        inputs=ValueTestInputs(vectors=vector_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        index=ValueTestIndex(value=imm_inputs[0]),
        representation=ValueTestRepresentation(
            source_extension=case.extension or match.extension_name,
            target_extension=case.to_extension,
            from_array_name=harness.from_array,
            to_array_name=harness.to_array,
        ),
    )


def target_imask_case(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
) -> ValueTestCasePlan | None:
    """Plan a direct integral-mask operation whose result belongs to ToVec."""

    if (
        case.expected_rule is not None
        or len(case.expected) != 1
        or case.extension is None
        or (case.to_type is None) == (case.to_extension is None)
    ):
        return None
    match = next(
        (
            spec
            for spec in specs
            if spec.type_tag == case.type_tag
            and spec.extension_name == case.extension
            and spec.target is not None
            and (
                (
                    case.to_type is not None
                    and spec.target.base_tag == case.to_type
                    and spec.target.extension_isa == spec.extension_name
                )
                or (
                    case.to_extension is not None
                    and spec.target.base_tag == case.type_tag
                    and spec.target.extension_isa == case.to_extension
                )
            )
        ),
        None,
    )
    if match is None or match.target is None or not _args_match(case, match.param_kinds):
        return None
    source_bits = _fixed_extension_bits(catalog, match.extension_name)
    target_bits = _fixed_extension_bits(catalog, match.target.extension_isa)
    source_lanes = (
        _whole_lanes(source_bits, match.type_tag) if source_bits is not None else None
    )
    target_lanes = (
        _whole_lanes(target_bits, match.target.base_tag)
        if target_bits is not None
        else None
    )
    mask_inputs = _mask_inputs(case)
    scalar_inputs = _scalar_inputs(case)
    if source_lanes is None or target_lanes is None or len(scalar_inputs) != 1:
        return None
    return ValueTestCasePlan(
        kind="target_imask",
        function_name=_function_name(name, index, case),
        case_name=case.name,
        call_name=name,
        type_tag=match.type_tag,
        base_spelling=match.base_type_spelling,
        lanes=source_lanes,
        inputs=ValueTestInputs(masks=mask_inputs, scalars=scalar_inputs),
        expectation=ValueTestExpectation(
            values=case.expected,
            comparison=case.comparison,
        ),
        invocation=ValueTestInvocation(
            result_kind=match.result_kind,
            param_kinds=match.param_kinds,
        ),
        target=ValueTestTarget(
            type_tag=match.target.base_tag,
            base_spelling=match.target.base_spelling,
            lanes=target_lanes,
        ),
        representation=ValueTestRepresentation(
            source_extension=match.extension_name,
            target_extension=match.target.extension_isa,
        ),
    )


def _fixed_extension_bits(catalog: Catalog, name: str) -> int | None:
    extension = catalog.extensions.get(name)
    if extension is not None:
        return (
            extension.vector_bits
            if extension.vector_bits_kind == "fixed" and extension.vector_bits > 0
            else None
        )
    widths = {
        candidate.vector_bits
        for candidate in catalog.extensions.values()
        if candidate.isa_name == name
        and candidate.vector_bits_kind == "fixed"
        and candidate.vector_bits > 0
    }
    return next(iter(widths)) if len(widths) == 1 else None

# Random inputs swept per (primitive, type, extension) by one compiled fuzz function. 256 keeps
# the values binary fast while covering far more of the input space than the handful of authored
# cases. Deterministic: the seed is derived from the function name, so a failure reproduces.
FUZZ_ITERATIONS = 256


def _fuzz_seed(function_name: str) -> int:
    """A stable 64-bit seed from the function name (FNV-1a, mixed) — unlike ``hash()`` it is
    constant across runs, so a reported seed reproduces the exact input stream."""

    digest = 0xCBF29CE484222325
    for byte in function_name.encode("utf-8"):
        digest = ((digest ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return (digest ^ SEED_MIX_64) & 0xFFFFFFFFFFFFFFFF or 1  # xorshift must not start at 0


def differential_fuzz_cases(
    name: str,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend_id: str,
    primitive: Primitive | None = None,
    iterations: int = FUZZ_ITERATIONS,
) -> list[ValueTestCasePlan]:
    """Random-input differential cases: one runtime PRNG loop per hardware extension, comparing
    ``prim<Hw>`` against the generic scalar reference ``prim<Ref>`` over ``iterations`` random
    inputs. Needs no authored inputs — the generic impl is the oracle. Vector primitives may have
    one mask argument; each emitted slot derives its own lane count from the extension width."""

    spec0 = specs[0]
    if harness.from_array is None:
        return []
    if (
        not spec0.param_kinds
        or any(kind not in {"m", "v"} for kind in spec0.param_kinds)
        or spec0.param_kinds.count("m") > 1
    ):
        return []
    if spec0.result_kind == "m" and harness.to_integral is None:
        return []
    if "m" in spec0.param_kinds and harness.to_mask is None:
        return []
    emitted: list[ValueTestCasePlan] = []
    for spec in specs:
        extension = catalog.extensions.get(spec.extension_name)
        if (
            extension is None
            or not extension.default_test_target
            or spec.uses_sized_vector
            or extension.vector_bits <= 0
        ):
            continue
        lanes = _whole_lanes(extension.vector_bits, spec.type_tag)
        base_spelling = _base_spelling((spec,), spec.type_tag)
        if lanes is None or base_spelling is None:
            continue
        nonzero_argument_index = _fuzz_nonzero_argument_index(
            primitive,
            spec.type_tag,
        )
        function_name = f"fuzz_diff_{spec.extension_name}_{_sanitize(name)}_{spec.type_tag}"
        emitted.append(
            ValueTestCasePlan(
                kind="differential_fuzz",
                function_name=function_name,
                case_name=f"{name}:fuzz",
                call_name=name,
                type_tag=spec.type_tag,
                base_spelling=base_spelling,
                lanes=lanes,
                invocation=ValueTestInvocation(
                    result_kind=spec.result_kind,
                    param_kinds=spec.param_kinds,
                ),
                differential=ValueTestDifferential(
                    hardware_extension=spec.extension_name,
                    from_array_name=harness.from_array,
                    to_array_name=harness.to_array,
                    to_integral_name=harness.to_integral,
                    to_mask_name=harness.to_mask,
                    mask_from_bits_template=(
                        extension.test_mask_from_bits.get(backend_id)
                        if "m" in spec.param_kinds
                        else None
                    ),
                    nonzero_argument_index=nonzero_argument_index,
                    fuzz_seed=_fuzz_seed(function_name),
                    fuzz_iterations=iterations,
                ),
            )
        )
    return emitted


def _fuzz_nonzero_argument_index(
    primitive: Primitive | None,
    type_tag: str,
) -> int | None:
    if primitive is None:
        return None
    info = SCALAR_TYPE_INFOS.get(type_tag)
    contract = primitive.arithmetic
    if (
        info is None
        or info.floating
        or contract is None
        or not contract.has_guarantee(
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS
        )
    ):
        return None
    binding = contract.binding(ArithmeticOperandRole.DIVISOR)
    if binding is None or binding.parameter_kind != "v":
        return None
    return binding.parameter_index


def differential_cases(
    name: str,
    index: int,
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
    catalog: Catalog,
    harness: HarnessPrimitiveNames,
    backend_id: str,
) -> list[ValueTestCasePlan]:
    if case.lanes is None or case.expected_rule is not None:
        return []
    if harness.from_array is None:
        return []
    base_spelling = _base_spelling(specs, case.type_tag)
    vector_inputs = _vector_inputs(case)
    mask_inputs = _mask_inputs(case)
    scalar_inputs = _scalar_inputs(case)
    if base_spelling is None:
        return []
    if not _args_match(case, specs[0].param_kinds):
        return []
    if specs[0].result_kind == "m" and harness.to_integral is None:
        return []
    if "m" in specs[0].param_kinds and harness.to_mask is None:
        return []
    immediate = None
    if "sImm" in specs[0].param_kinds:
        if len(scalar_inputs) != 1 or specs[0].immediate is None:
            return []
        immediate = _immediate_value(scalar_inputs[0], specs[0].immediate)
    emitted: list[ValueTestCasePlan] = []
    for spec in specs:
        extension = catalog.extensions.get(spec.extension_name)
        if (
            extension is None
            or not extension.default_test_target
            or spec.uses_sized_vector
            or extension.vector_bits <= 0
        ):
            continue
        if spec.type_tag != case.type_tag:
            continue
        if _whole_lanes(extension.vector_bits, case.type_tag) != case.lanes:
            continue
        emitted.append(
            ValueTestCasePlan(
                kind="differential",
                function_name=f"test_diff_{spec.extension_name}_{_sanitize(case.name)}",
                case_name=case.name,
                call_name=name,
                type_tag=case.type_tag,
                base_spelling=base_spelling,
                lanes=case.lanes,
                inputs=ValueTestInputs(
                    vectors=vector_inputs,
                    masks=mask_inputs,
                    scalars=scalar_inputs,
                ),
                expectation=ValueTestExpectation(comparison=case.comparison),
                invocation=ValueTestInvocation(
                    result_kind=specs[0].result_kind,
                    param_kinds=specs[0].param_kinds,
                    generic_defaults=tuple(
                        default
                        for _name, _type, default in specs[0].generic_params
                    ),
                    immediate=immediate,
                ),
                differential=ValueTestDifferential(
                    hardware_extension=spec.extension_name,
                    from_array_name=harness.from_array,
                    to_array_name=harness.to_array,
                    to_integral_name=harness.to_integral,
                    to_mask_name=harness.to_mask,
                    mask_from_bits_template=(
                        extension.test_mask_from_bits.get(backend_id)
                        if mask_inputs
                        else None
                    ),
                ),
            )
        )
    return emitted

def extension_harness_available(
    case: TestCase,
    specs: tuple[LoweredSpecialization, ...],
) -> bool:
    return _extension_repr_match(case, specs) is not None

__all__ = (
    "load_convert_case",
    "convert_case",
    "lane_convert_case",
    "repr_cast_case",
    "extension_repr_case",
    "differential_cases",
    "extension_harness_available",
)
