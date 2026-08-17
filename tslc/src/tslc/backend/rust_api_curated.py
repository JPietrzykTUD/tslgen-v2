"""Plan curated Rust methods, traits, conversions, and operation facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from tslc.backend.primitive_facade import plan_dataparallel_primitive_facade
from tslc.backend.rust_api_candidates import (
    _Candidate,
    _CandidateKey,
    _PublicOperand,
    _candidate_invocation,
    _delegate_diagnostic,
    _delegates,
    _diagnostic,
    _invocation_diagnostic,
    _invocation_from_roles,
)
from tslc.backend.rust_api_comprehensive import _method_for_candidate
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustCuratedTraitImplementation,
    RustFacadeBitConversion,
    RustFacadeConversionPair,
    RustFacadeOperationBinding,
    RustFacadeReceiverKind,
    RustFacadeShape,
    RustFacadeTraitRhsKind,
    RustOperationValue,
)
from tslc.backend.rust_api_surface import (
    RUST_FACADE_CORE_OPERATION_REQUIREMENTS,
    _finalize_conversion_pair,
    _unique_facade_base_spelling,
)
from tslc.catalog.arithmetic import (
    ArithmeticGuarantee,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.conversion import ConversionKind, LaneCountRelation
from tslc.catalog.memory import MemoryAlignment
from tslc.catalog.model import PrimitiveMaskMode
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.diagnostics import Diagnostic


def _curated_methods(
    methods: list[RustComprehensiveMethod],
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[list[RustCuratedMethod], tuple[Diagnostic, ...]]:
    planned: list[RustCuratedMethod] = []
    diagnostics: list[Diagnostic] = []
    names = {
        PrimitiveOperation.COMPARE_EQUAL: "simd_eq",
        PrimitiveOperation.COMPARE_NOT_EQUAL: "simd_ne",
        PrimitiveOperation.COMPARE_LESS: "simd_lt",
        PrimitiveOperation.COMPARE_LESS_EQUAL: "simd_le",
        PrimitiveOperation.COMPARE_GREATER: "simd_gt",
        PrimitiveOperation.COMPARE_GREATER_EQUAL: "simd_ge",
    }
    for candidate in candidates.values():
        operation = candidate.key.operation
        if (
            operation is PrimitiveOperation.SELECT
            and candidate.key.mask_policy in {None, PrimitiveMaskMode.PASS_THROUGH}
            and candidate.key.result_kind == "v"
            and sorted(candidate.key.param_kinds) == ["m", "v", "v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    (
                        (OperandRole.CONTROL_MASK, "m"),
                        (OperandRole.PRIMARY, "v"),
                        (OperandRole.PASS_THROUGH, "v"),
                    ),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name="select",
                        receiver_kind=RustFacadeReceiverKind.MASK,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        conversion_pairs=(),
                        delegates=method.delegates,
                    )
                )
        if (
            operation in names
            and candidate.key.mask_policy is None
            and candidate.key.result_kind == "m"
            and sorted(candidate.key.param_kinds) == ["v", "v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    (
                        (OperandRole.PRIMARY, "v"),
                        (OperandRole.SECONDARY, "v"),
                    ),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name=names[operation],
                        receiver_kind=RustFacadeReceiverKind.VECTOR,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        conversion_pairs=(),
                        delegates=method.delegates,
                    )
                )
        conversion = candidate.representative.primitive_semantics.conversion
        if (
            operation is PrimitiveOperation.CONVERT
            and conversion is not None
            and conversion.kind is ConversionKind.NUMERIC
            and conversion.lane_count is LaneCountRelation.PRESERVE_LANE_COUNT
            and candidate.key.result_vector_param is not None
            and candidate.key.result_kind == "v"
            and sorted(candidate.key.param_kinds) == ["v"]
        ):
            method = _method_for_candidate(methods, candidate)
            if method is not None and not method.caller_unsafe:
                invocation = _candidate_invocation(
                    candidate,
                    ((OperandRole.PRIMARY, "v"),),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                planned.append(
                    RustCuratedMethod(
                        public_name="cast",
                        receiver_kind=RustFacadeReceiverKind.VECTOR,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=method.type_tags,
                        shape_keys=(),
                        caller_unsafe=False,
                        invocation=invocation,
                        conversion_pairs=method.conversion_pairs,
                        delegates=(),
                    )
                )
    return _deduplicate_curated_methods(planned), tuple(diagnostics)


def _bit_conversions(
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[tuple[RustFacadeBitConversion, ...], tuple[Diagnostic, ...]]:
    conversions: list[RustFacadeBitConversion] = []
    diagnostics: list[Diagnostic] = []
    for candidate in candidates.values():
        if _delegate_diagnostic(candidate) is not None:
            continue
        conversion = candidate.representative.primitive_semantics.conversion
        if (
            candidate.key.operation is not PrimitiveOperation.REINTERPRET
            or conversion is None
            or conversion.kind is not ConversionKind.BIT_PATTERN
            or conversion.lane_count is not LaneCountRelation.PRESERVE_REGISTER_WIDTH
            or candidate.key.result_kind != "v"
            or candidate.key.param_kinds != ("v",)
        ):
            continue
        safety_values = {
            spec.safety.caller_unsafe for _profile, spec in candidate.specs
        }
        if safety_values != {False}:
            continue
        fallback_pairs = {
            (spec.type_tag, spec.target.base_tag)
            for profile_name, spec in candidate.specs
            if profile_name is None and spec.target is not None
        }
        for float_tag, bits_tag in (("f32", "ui32"), ("f64", "ui64")):
            if {
                (float_tag, bits_tag),
                (bits_tag, float_tag),
            } <= fallback_pairs:
                invocation = _candidate_invocation(
                    candidate,
                    ((OperandRole.PRIMARY, "v"),),
                )
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    break
                directional_specs = {
                    (source_type_tag, target_type_tag): tuple(
                        (profile_name, spec)
                        for profile_name, spec in candidate.specs
                        if spec.type_tag == source_type_tag
                        and spec.target is not None
                        and spec.target.base_tag == target_type_tag
                    )
                    for source_type_tag, target_type_tag in (
                        (float_tag, bits_tag),
                        (bits_tag, float_tag),
                    )
                }
                conversions.append(
                    RustFacadeBitConversion(
                        float_type_tag=float_tag,
                        bits_type_tag=bits_tag,
                        source_primitive_name=candidate.key.source_name,
                        shape_keys=(),
                        invocation=invocation,
                        to_bits=RustFacadeConversionPair(
                            source_type_tag=float_tag,
                            target_type_tag=bits_tag,
                            shape_keys=(),
                            delegates=_delegates(
                                candidate,
                                directional_specs[(float_tag, bits_tag)],
                            ),
                        ),
                        from_bits=RustFacadeConversionPair(
                            source_type_tag=bits_tag,
                            target_type_tag=float_tag,
                            shape_keys=(),
                            delegates=_delegates(
                                candidate,
                                directional_specs[(bits_tag, float_tag)],
                            ),
                        ),
                    )
                )
    return (
        tuple(
            sorted(
                conversions,
                key=lambda item: (item.float_type_tag, item.bits_type_tag),
            )
        ),
        tuple(diagnostics),
    )


def _finalize_bit_conversions(
    conversions: tuple[RustFacadeBitConversion, ...],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[RustFacadeBitConversion, ...]:
    by_key = {(shape.type_tag, shape.lanes): shape for shape in shapes}
    finalized: list[RustFacadeBitConversion] = []
    for conversion in conversions:
        to_bits = _finalize_conversion_pair(conversion.to_bits, shapes)
        from_bits = _finalize_conversion_pair(conversion.from_bits, shapes)
        lanes = sorted(
            {
                lanes
                for type_tag, lanes in to_bits.shape_keys
                if type_tag == conversion.float_type_tag
                and (conversion.bits_type_tag, lanes) in by_key
                and (conversion.bits_type_tag, lanes) in from_bits.shape_keys
            }
        )
        shape_keys = tuple(
            (conversion.float_type_tag, lane_count)
            for lane_count in lanes
        )
        if shape_keys:
            to_bits = replace(
                to_bits,
                shape_keys=tuple(
                    (conversion.float_type_tag, lane_count)
                    for lane_count in lanes
                ),
            )
            from_bits = replace(
                from_bits,
                shape_keys=tuple(
                    (conversion.bits_type_tag, lane_count)
                    for lane_count in lanes
                ),
            )
            finalized.append(
                replace(
                    conversion,
                    shape_keys=shape_keys,
                    to_bits=to_bits,
                    from_bits=from_bits,
                )
            )
    return tuple(finalized)


def _curated_traits(
    methods: list[RustComprehensiveMethod],
    candidates: dict[_CandidateKey, _Candidate],
    shapes: tuple[RustFacadeShape, ...],
) -> tuple[list[RustCuratedTraitImplementation], tuple[Diagnostic, ...]]:
    traits: list[RustCuratedTraitImplementation] = []
    diagnostics: list[Diagnostic] = []
    base_spellings_by_type: dict[str, set[str]] = defaultdict(set)
    for shape in shapes:
        base_spellings_by_type[shape.type_tag].add(shape.base_spelling)
    for candidate in candidates.values():
        if candidate.key.mask_policy is not None:
            continue
        method = _method_for_candidate(methods, candidate)
        if method is None or method.caller_unsafe:
            continue
        trait_facts = _trait_facts(candidate)
        for (
            trait_path,
            method_name,
            operation,
            type_tags,
            rhs_kind,
            rhs_types,
            public_operands,
        ) in trait_facts:
            if type_tags:
                invocation = _candidate_invocation(candidate, public_operands)
                if invocation is None:
                    diagnostics.append(_invocation_diagnostic(candidate))
                    continue
                try:
                    rhs_type_spellings = tuple(
                        _unique_facade_base_spelling(
                            type_tag, base_spellings_by_type
                        )
                        for type_tag in rhs_types
                    )
                except ValueError as error:
                    diagnostics.append(
                        _diagnostic(
                            candidate,
                            "TSL-BACKEND-RUST-FACADE-SCALAR-TYPE-MAPPING",
                            str(error),
                        )
                    )
                    continue
                traits.append(
                    RustCuratedTraitImplementation(
                        trait_path=trait_path,
                        method_name=method_name,
                        receiver_kind=method.receiver_kind,
                        operation=operation,
                        source_primitive_name=candidate.key.source_name,
                        type_tags=type_tags,
                        rhs_kind=rhs_kind,
                        rhs_type_tags=rhs_types,
                        rhs_type_spellings=rhs_type_spellings,
                        shape_keys=(),
                        invocation=invocation,
                        delegates=method.delegates,
                    )
                )
    return _deduplicate_traits(traits), tuple(diagnostics)


def _trait_facts(
    candidate: _Candidate,
) -> tuple[
    tuple[
        str,
        str,
        ArithmeticOperation | PrimitiveOperation,
        tuple[str, ...],
        RustFacadeTraitRhsKind | None,
        tuple[str, ...],
        tuple[_PublicOperand, ...],
    ],
    ...,
]:
    spec = candidate.representative
    arithmetic = spec.primitive_semantics.arithmetic
    facts: list[
        tuple[
            str,
            str,
            ArithmeticOperation | PrimitiveOperation,
            tuple[str, ...],
            RustFacadeTraitRhsKind | None,
            tuple[str, ...],
            tuple[_PublicOperand, ...],
        ]
    ] = []
    if arithmetic is not None:
        mapping = {
            ArithmeticOperation.ADDITION: ("core::ops::Add", "add"),
            ArithmeticOperation.SUBTRACTION: ("core::ops::Sub", "sub"),
            ArithmeticOperation.MULTIPLICATION: ("core::ops::Mul", "mul"),
            ArithmeticOperation.DIVISION: ("core::ops::Div", "div"),
            ArithmeticOperation.REMAINDER: ("core::ops::Rem", "rem"),
            ArithmeticOperation.NEGATION: ("core::ops::Neg", "neg"),
        }
        for operation in arithmetic.ordered_operations:
            spelling = mapping.get(operation)
            if spelling is None or not _arithmetic_guarantees_admit(
                operation, arithmetic.guarantees
            ):
                continue
            rhs_kind = _arithmetic_rhs_kind(candidate, operation)
            if operation is not ArithmeticOperation.NEGATION and rhs_kind is None:
                continue
            if operation is ArithmeticOperation.NEGATION and (
                candidate.key.result_kind != "v"
                or candidate.key.param_kinds != ("v",)
            ):
                continue
            type_tags = candidate.type_tags
            if operation is ArithmeticOperation.NEGATION:
                type_tags = tuple(
                    type_tag
                    for type_tag in type_tags
                    if type_tag in SCALAR_TYPE_INFOS
                    and SCALAR_TYPE_INFOS[type_tag].signed
                )
            facts.append(
                (
                    *spelling,
                    operation,
                    type_tags,
                    rhs_kind,
                    (),
                    _arithmetic_public_operands(operation),
                )
            )
    primitive_operation = candidate.key.operation
    integer_tags = tuple(
        tag
        for tag in candidate.type_tags
        if tag in SCALAR_TYPE_INFOS and not SCALAR_TYPE_INFOS[tag].floating
    )
    primitive_mapping = {
        PrimitiveOperation.BIT_AND: ("core::ops::BitAnd", "bitand"),
        PrimitiveOperation.BIT_OR: ("core::ops::BitOr", "bitor"),
        PrimitiveOperation.BIT_XOR: ("core::ops::BitXor", "bitxor"),
        PrimitiveOperation.BIT_NOT: ("core::ops::Not", "not"),
        PrimitiveOperation.MASK_AND: ("core::ops::BitAnd", "bitand"),
        PrimitiveOperation.MASK_OR: ("core::ops::BitOr", "bitor"),
        PrimitiveOperation.MASK_XOR: ("core::ops::BitXor", "bitxor"),
        PrimitiveOperation.MASK_NOT: ("core::ops::Not", "not"),
        PrimitiveOperation.SHIFT_LEFT_WRAPPING: ("core::ops::Shl", "shl"),
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING: ("core::ops::Shr", "shr"),
    }
    spelling = (
        None
        if primitive_operation is None
        else primitive_mapping.get(primitive_operation)
    )
    admitted, rhs_kind = _primitive_trait_shape(candidate, primitive_operation)
    if spelling is not None and primitive_operation is not None and admitted:
        type_tags = (
            candidate.type_tags
            if primitive_operation in _MASK_OPERATIONS
            else integer_tags
        )
        rhs_types = (
            spec.primitive_semantics.shift.scalar_count_types
            if primitive_operation
            in {
                PrimitiveOperation.SHIFT_LEFT_WRAPPING,
                PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
            }
            and spec.primitive_semantics.shift is not None
            else ()
        )
        facts.append(
            (
                *spelling,
                primitive_operation,
                type_tags,
                rhs_kind,
                rhs_types,
                _primitive_public_operands(primitive_operation, rhs_kind),
            )
        )
    return tuple(facts)


def _arithmetic_rhs_kind(
    candidate: _Candidate,
    operation: ArithmeticOperation,
) -> RustFacadeTraitRhsKind | None:
    if operation is ArithmeticOperation.NEGATION:
        return None
    if (
        candidate.key.result_kind != "v"
        or sorted(candidate.key.param_kinds) != ["v", "v"]
    ):
        return None
    return RustFacadeTraitRhsKind.SAME_TYPE


def _arithmetic_public_operands(
    operation: ArithmeticOperation,
) -> tuple[_PublicOperand, ...]:
    if operation is ArithmeticOperation.NEGATION:
        return ((ArithmeticOperandRole.PRIMARY, "v"),)
    rhs_role = (
        ArithmeticOperandRole.DIVISOR
        if operation in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ArithmeticOperandRole.SECONDARY
    )
    return (
        (ArithmeticOperandRole.PRIMARY, "v"),
        (rhs_role, "v"),
    )


def _primitive_public_operands(
    operation: PrimitiveOperation,
    rhs_kind: RustFacadeTraitRhsKind | None,
) -> tuple[_PublicOperand, ...]:
    if operation in {PrimitiveOperation.BIT_NOT, PrimitiveOperation.MASK_NOT}:
        kind = "m" if operation is PrimitiveOperation.MASK_NOT else "v"
        return ((OperandRole.PRIMARY, kind),)
    if operation in {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }:
        return (
            (OperandRole.PRIMARY, "v"),
            (
                OperandRole.COUNT,
                "s" if rhs_kind is RustFacadeTraitRhsKind.SCALAR else "v",
            ),
        )
    kind = "m" if operation in _MASK_OPERATIONS else "v"
    return (
        (OperandRole.PRIMARY, kind),
        (OperandRole.SECONDARY, kind),
    )


def _primitive_trait_shape(
    candidate: _Candidate,
    operation: PrimitiveOperation | None,
) -> tuple[bool, RustFacadeTraitRhsKind | None]:
    key = candidate.key
    unary = {
        PrimitiveOperation.BIT_NOT,
        PrimitiveOperation.MASK_NOT,
    }
    binary_vectors = {
        PrimitiveOperation.BIT_AND,
        PrimitiveOperation.BIT_OR,
        PrimitiveOperation.BIT_XOR,
    }
    binary_masks = {
        PrimitiveOperation.MASK_AND,
        PrimitiveOperation.MASK_OR,
        PrimitiveOperation.MASK_XOR,
    }
    shifts = {
        PrimitiveOperation.SHIFT_LEFT_WRAPPING,
        PrimitiveOperation.SHIFT_RIGHT_WRAPPING,
    }
    if operation in unary:
        expected = ("m",) if operation is PrimitiveOperation.MASK_NOT else ("v",)
        expected_result = "m" if operation is PrimitiveOperation.MASK_NOT else "v"
        return (key.param_kinds == expected and key.result_kind == expected_result, None)
    if (
        operation in binary_vectors
        and key.result_kind == "v"
        and sorted(key.param_kinds) == ["v", "v"]
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if (
        operation in binary_masks
        and key.result_kind == "m"
        and sorted(key.param_kinds) == ["m", "m"]
    ):
        return True, RustFacadeTraitRhsKind.SAME_TYPE
    if operation in shifts and key.result_kind == "v":
        if sorted(key.param_kinds) == ["v", "v"]:
            return True, RustFacadeTraitRhsKind.SAME_TYPE
        if sorted(key.param_kinds) == ["s", "v"]:
            return True, RustFacadeTraitRhsKind.SCALAR
    return False, None


def _arithmetic_guarantees_admit(
    operation: ArithmeticOperation,
    guarantees: frozenset[ArithmeticGuarantee],
) -> bool:
    required = {
        ArithmeticOperation.ADDITION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.SUBTRACTION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.MULTIPLICATION: {ArithmeticGuarantee.INTEGER_WRAPPING},
        ArithmeticOperation.NEGATION: {
            ArithmeticGuarantee.INTEGER_WRAPPING,
            ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE,
        },
        ArithmeticOperation.DIVISION: {
            ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO,
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
            ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN,
            ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES,
        },
        ArithmeticOperation.REMAINDER: {
            ArithmeticGuarantee.INTEGER_REMAINDER_HAS_DIVIDEND_SIGN,
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
            ArithmeticGuarantee.SIGNED_MIN_REM_NEG_ONE_RETURNS_ZERO,
            ArithmeticGuarantee.FLOATING_REMAINDER_TRUNCATING,
        },
    }[operation]
    return required <= guarantees


def _operation_values(
    traits: list[RustCuratedTraitImplementation],
) -> tuple[RustOperationValue, ...]:
    values: dict[ArithmeticOperation | PrimitiveOperation, RustOperationValue] = {}
    for trait in sorted(traits, key=_trait_sort_key):
        public_name = trait.trait_path.rsplit("::", 1)[-1]
        values.setdefault(
            trait.operation,
            RustOperationValue(
                public_name,
                trait.operation,
                trait.source_primitive_name,
                trait.type_tags,
            ),
        )
    return tuple(sorted(values.values(), key=lambda item: item.public_name))


def _operation_bindings(
    candidates: dict[_CandidateKey, _Candidate],
    baseline_keys: set[_CandidateKey],
) -> tuple[tuple[RustFacadeOperationBinding, ...], tuple[Diagnostic, ...]]:
    bindings: list[RustFacadeOperationBinding] = []
    diagnostics: list[Diagnostic] = []
    for candidate in candidates.values():
        key = candidate.key
        if (
            key not in baseline_keys
            or key.operation is None
            or key.result_vector_param is not None
            or key.has_concrete_target
        ):
            continue
        safety_values = {
            spec.safety.caller_unsafe for _profile, spec in candidate.specs
        }
        if len(safety_values) != 1 or _delegate_diagnostic(candidate) is not None:
            continue
        memory_alignment_axis_name: str | None = None
        memory_alignment_modes: tuple[MemoryAlignment, ...] = ()
        if key.memory is not None:
            memory_decision = plan_dataparallel_primitive_facade(
                key.source_name,
                tuple(spec for _profile_name, spec in candidate.specs),
            )
            if memory_decision.diagnostic_reason is not None:
                continue
            alignments = tuple(
                spec.primitive_semantics.memory_alignment
                for _profile_name, spec in candidate.specs
            )
            if any(alignment is None for alignment in alignments):
                continue
            alignment_axis_names = {
                alignment.axis_name
                for alignment in alignments
                if alignment is not None
            }
            if len(alignment_axis_names) != 1:
                diagnostics.append(
                    _diagnostic(
                        candidate,
                        "TSL-BACKEND-RUST-FACADE-MEMORY-CONTRACT",
                        "has inconsistent resolved memory alignment axes",
                    )
                )
                continue
            memory_alignment_axis_name = next(iter(alignment_axis_names))
            memory_alignment_modes = tuple(
                sorted(
                    {
                        alignment.mode
                        for alignment in alignments
                        if alignment is not None
                    },
                    key=lambda item: item.value,
                )
            )
        core_requirements = tuple(
            requirement
            for requirement in RUST_FACADE_CORE_OPERATION_REQUIREMENTS
            if key.operation is requirement.operation
            and key.result_kind == requirement.result_kind
            and sorted(key.param_kinds) == sorted(requirement.parameter_kinds)
            and key.axis_names == requirement.axis_names
            and key.memory
            == (
                (
                    requirement.memory_access,
                    requirement.memory_addressing,
                )
                if requirement.memory_access is not None
                else None
            )
            and memory_alignment_modes == requirement.memory_alignment_modes
            and key.mask_policy is None
            and key.overload == requirement.overload
            and next(iter(safety_values))
            == (
                requirement.operation
                in {PrimitiveOperation.LOAD, PrimitiveOperation.STORE}
            )
        )
        if any(
            _invocation_from_roles(
                key.param_kinds,
                key.operation_roles,
                tuple(zip(requirement.public_roles, requirement.parameter_kinds)),
            )
            is None
            for requirement in core_requirements
        ):
            diagnostics.append(_invocation_diagnostic(candidate))
            continue
        bindings.append(
            RustFacadeOperationBinding(
                operation=key.operation,
                source_primitive_name=key.source_name,
                result_kind=key.result_kind,
                parameter_kinds=key.param_kinds,
                operand_roles=key.operation_roles,
                axis_names=key.axis_names,
                memory_access=key.memory[0] if key.memory is not None else None,
                memory_addressing=(
                    key.memory[1] if key.memory is not None else None
                ),
                memory_alignment_axis_name=memory_alignment_axis_name,
                memory_alignment_modes=memory_alignment_modes,
                mask_policy=key.mask_policy,
                overload=key.overload,
                type_tags=candidate.type_tags,
                caller_unsafe=next(iter(safety_values)),
                delegates=_delegates(candidate),
            )
        )
    return (
        tuple(sorted(bindings, key=_operation_binding_sort_key)),
        tuple(diagnostics),
    )


def _trait_collision_diagnostics(
    traits: list[RustCuratedTraitImplementation],
    candidates: dict[_CandidateKey, _Candidate],
) -> tuple[Diagnostic, ...]:
    del candidates
    grouped: dict[
        tuple[RustFacadeReceiverKind, str, RustFacadeTraitRhsKind | None], set[str]
    ] = defaultdict(set)
    for trait in traits:
        grouped[(trait.receiver_kind, trait.trait_path, trait.rhs_kind)].add(
            trait.source_primitive_name
        )
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-BACKEND-RUST-FACADE-TRAIT-COLLISION",
            message=(
                f"Rust facade trait {trait_path!r} for {receiver.value} values is "
                "provided by multiple primitives: " + ", ".join(sorted(sources))
            ),
        )
        for (receiver, trait_path, _rhs_kind), sources in sorted(
            grouped.items(),
            key=lambda item: (
                item[0][0].value,
                item[0][1],
                item[0][2].value if item[0][2] is not None else "",
            ),
        )
        if len(sources) > 1
    )


def _deduplicate_curated_methods(
    methods: list[RustCuratedMethod],
) -> list[RustCuratedMethod]:
    return list(
        {
            (method.receiver_kind, method.public_name, method.source_primitive_name): method
            for method in methods
        }.values()
    )


def _deduplicate_traits(
    traits: list[RustCuratedTraitImplementation],
) -> list[RustCuratedTraitImplementation]:
    return list(
        {
            (
                trait.receiver_kind,
                trait.trait_path,
                trait.source_primitive_name,
                trait.type_tags,
                trait.rhs_kind,
                trait.rhs_type_tags,
            ): trait
            for trait in traits
        }.values()
    )


def _curated_method_sort_key(method: RustCuratedMethod) -> tuple[str, str, str]:
    return (method.receiver_kind.value, method.public_name, method.source_primitive_name)


def _operation_binding_sort_key(
    binding: RustFacadeOperationBinding,
) -> tuple[object, ...]:
    return (
        binding.operation.value,
        binding.source_primitive_name,
        binding.result_kind,
        binding.parameter_kinds,
        tuple(
            (role.value, index, kind)
            for role, index, kind in binding.operand_roles
        ),
        binding.axis_names,
        binding.mask_policy or "",
        binding.overload or ("", "", False),
    )


def _trait_sort_key(
    trait: RustCuratedTraitImplementation,
) -> tuple[str, str, str, tuple[str, ...]]:
    return (
        trait.receiver_kind.value,
        trait.trait_path,
        trait.source_primitive_name,
        trait.type_tags,
    )


_MASK_OPERATIONS = frozenset(
    {
        PrimitiveOperation.MASK_AND,
        PrimitiveOperation.MASK_OR,
        PrimitiveOperation.MASK_XOR,
        PrimitiveOperation.MASK_NOT,
    }
)
