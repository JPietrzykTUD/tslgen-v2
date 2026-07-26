"""Shared typed builders for focused Rust facade planner tests."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_static_selection import (
    RustStaticFallbackModule,
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
)
from tslc.catalog.arithmetic import (
    ArithmeticContract,
    ArithmeticGuarantee,
    ArithmeticOperandBinding,
    ArithmeticOperandRole,
    ArithmeticOperation,
)
from tslc.catalog.conversion import PrimitiveConversionContract
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryAlignment,
    PrimitiveMemoryContract,
)
from tslc.catalog.model import Extension, ImplementationSafety
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.catalog.semantics import (
    OperandBinding,
    OperandRole,
    PrimitiveOperation,
    PrimitiveSemanticContract,
)
from tslc.catalog.target_families import ExtensionFamilyCapability
from tslc.lower.lowerer import LoweredSpecialization
from tslc.lower.primitive_semantics import (
    LoweredMemoryAlignment,
    LoweredPrimitiveSemantics,
)
from tslc.target_text import LoweredBody


def _operation(
    kind: PrimitiveOperation,
    roles: tuple[tuple[OperandRole, int, str], ...],
    names: tuple[str, ...],
) -> PrimitiveSemanticContract:
    return PrimitiveSemanticContract(
        kind,
        tuple(
            OperandBinding(role, names[index], index, parameter_kind)
            for role, index, parameter_kind in roles
        ),
    )


def _spec(
    name: str,
    *,
    result_kind: str = "v",
    param_names: tuple[str, ...] = ("data", "value"),
    param_kinds: tuple[str, ...] = ("v", "s"),
    operation: PrimitiveOperation = PrimitiveOperation.BIT_AND_NOT,
    roles: tuple[tuple[OperandRole, int, str], ...] = (
        (OperandRole.PRIMARY, 0, "v"),
        (OperandRole.SECONDARY, 1, "s"),
    ),
    overload: ResolvedPrimitiveOverload | None = None,
    immediate: tuple[str, str] | None = None,
    mask_policy: str | None = None,
    safety: ImplementationSafety = ImplementationSafety(),
    arithmetic: ArithmeticContract | None = None,
    conversion: PrimitiveConversionContract | None = None,
    memory: PrimitiveMemoryContract | None = None,
    memory_alignment: LoweredMemoryAlignment | None = None,
    emitted_name: str | None = None,
) -> LoweredSpecialization:
    return LoweredSpecialization(
        backend_id="rust",
        primitive_name=emitted_name or name,
        source_primitive_name=name,
        extension_name="generic",
        type_tag="si32",
        base_type_spelling="i32",
        register_spelling="array_type<i32, LANES>",
        result_kind=result_kind,
        param_names=param_names,
        param_kinds=param_kinds,
        body=LoweredBody.from_text(""),
        primitive_semantics=LoweredPrimitiveSemantics(
            overload=overload,
            arithmetic=arithmetic,
            operation=_operation(operation, roles, param_names),
            memory=memory,
            memory_alignment=memory_alignment,
            conversion=conversion,
        ),
        uses_sized_vector=True,
        lane_parameter="LANES",
        immediate=immediate,
        mask_policy=mask_policy,
        safety=safety,
    )


def _aligned_memory_specs(
    name: str,
    *,
    operation: PrimitiveOperation,
    access: MemoryAccess,
    result_kind: str,
    param_names: tuple[str, ...],
    param_kinds: tuple[str, ...],
    roles: tuple[tuple[OperandRole, int, str], ...],
    overload: ResolvedPrimitiveOverload | None = None,
) -> tuple[LoweredSpecialization, LoweredSpecialization]:
    unaligned = _spec(
        name,
        result_kind=result_kind,
        param_names=param_names,
        param_kinds=param_kinds,
        operation=operation,
        roles=roles,
        overload=overload,
        safety=ImplementationSafety(caller_unsafe=True),
        memory=PrimitiveMemoryContract(
            access,
            MemoryAddressing.CONTIGUOUS,
        ),
        memory_alignment=LoweredMemoryAlignment(
            "aligned",
            MemoryAlignment.UNALIGNED,
        ),
    )
    unaligned = replace(unaligned, axis=(("aligned", "false"),))
    aligned = replace(
        unaligned,
        axis=(("aligned", "true"),),
        primitive_semantics=replace(
            unaligned.primitive_semantics,
            memory_alignment=LoweredMemoryAlignment(
                "aligned",
                MemoryAlignment.ALIGNED,
            ),
        ),
    )
    return unaligned, aligned


def _arithmetic_spec(
    name: str = "sum",
    *,
    operation: ArithmeticOperation = ArithmeticOperation.ADDITION,
    reordered: bool = False,
) -> LoweredSpecialization:
    names = ("right", "left") if reordered else ("left", "right")
    rhs_role = (
        ArithmeticOperandRole.DIVISOR
        if operation in {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
        else ArithmeticOperandRole.SECONDARY
    )
    primary_index = 1 if reordered else 0
    rhs_index = 0 if reordered else 1
    guarantees = {
        ArithmeticOperation.ADDITION: frozenset(
            {ArithmeticGuarantee.INTEGER_WRAPPING}
        ),
        ArithmeticOperation.SUBTRACTION: frozenset(
            {ArithmeticGuarantee.INTEGER_WRAPPING}
        ),
        ArithmeticOperation.DIVISION: frozenset(
            {
                ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO,
                ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
                ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN,
                ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES,
            }
        ),
    }[operation]
    arithmetic = ArithmeticContract(
        frozenset({operation}),
        (
            ArithmeticOperandBinding(
                ArithmeticOperandRole.PRIMARY,
                "left",
                primary_index,
                primary_index,
                "v",
            ),
            ArithmeticOperandBinding(
                rhs_role,
                "right",
                rhs_index,
                rhs_index,
                "v",
            ),
        ),
        guarantees,
    )
    return _spec(
        name,
        param_names=names,
        param_kinds=("v", "v"),
        roles=(),
        arithmetic=arithmetic,
    )


def _fallback_extension(
    name: str,
    *,
    sized: bool,
) -> Extension:
    family = "generic_like" if sized else "scalar"
    return Extension(
        name,
        name,
        family,
        {},
        {},
        family_capability=ExtensionFamilyCapability(
            family,
            implementation_fallback=True,
        ),
        vector_bits_kind="sized" if sized else "fixed",
    )


def _plan(
    *specs: LoweredSpecialization,
    profiles: tuple[EmittedProfile, ...] = (),
    fallback_extensions: tuple[Extension, ...] | None = None,
    fallback_mappings: tuple[RustStaticVectorMapping, ...] | None = None,
) -> RustStaticSelectionPlan:
    del profiles
    by_name: dict[str, list[LoweredSpecialization]] = {}
    for spec in specs:
        by_name.setdefault(spec.primitive_name, []).append(spec)
    return RustStaticSelectionPlan(
        profiles=(),
        fallback_mappings=fallback_mappings
        or (
            RustStaticVectorMapping(
                "si32",
                "i32",
                4,
                128,
                "Simd<i32, Generic<4>>",
                "u64",
                uses_sized_vector=True,
            ),
        ),
        fallback_module=RustStaticFallbackModule(
            tuple(
                (name, tuple(group)) for name, group in sorted(by_name.items())
            ),
            tuple(
                (extension.name, extension)
                for extension in (
                    fallback_extensions
                    if fallback_extensions is not None
                    else (_fallback_extension("generic", sized=True),)
                )
            ),
        ),
    )
