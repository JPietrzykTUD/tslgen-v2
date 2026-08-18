"""Collect normalized Rust facade candidates and exact delegate inventory."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.rust_api_model import (
    RustFacadeConversionPair,
    RustFacadeDelegate,
    RustFacadeDelegateVector,
    RustFacadeInvocation,
)
from tslc.backend.rust_static_selection import (
    RustStaticSelectionPlan,
    RustStaticVectorMapping,
)
from tslc.catalog.arithmetic import ArithmeticOperandRole, ArithmeticOperation
from tslc.catalog.conversion import (
    ConversionKind,
    LaneCountRelation,
    NumericConversionMode,
)
from tslc.catalog.memory import MemoryAccess, MemoryAddressing
from tslc.catalog.model import Extension, PrimitiveMaskMode, VectorBitsKind
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.catalog.semantics import OperandRole, PrimitiveOperation
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.lower.lowerer import LoweredSpecialization, varying_positions


_FacadeOperandRole = OperandRole | ArithmeticOperandRole
_PublicOperand = tuple[_FacadeOperandRole, str]
_RoleBinding = tuple[_FacadeOperandRole, int, str]


@dataclass(frozen=True, slots=True)
class _CandidateKey:
    source_name: str
    result_kind: str
    param_names: tuple[str, ...]
    param_kinds: tuple[str, ...]
    axis_names: tuple[str, ...]
    immediate: tuple[str, str] | None
    generic_params: tuple[tuple[str, str, str], ...]
    type_param_names: tuple[str, ...]
    result_vector_param: str | None
    conversion: tuple[
        ConversionKind, LaneCountRelation, NumericConversionMode | None
    ] | None
    memory: tuple[MemoryAccess, MemoryAddressing] | None
    has_concrete_target: bool
    mask_policy: PrimitiveMaskMode | None
    overload: tuple[str, str, bool] | None
    operation: PrimitiveOperation | None
    operation_roles: tuple[tuple[OperandRole, int, str], ...]
    arithmetic_operations: tuple[ArithmeticOperation, ...]
    arithmetic_roles: tuple[tuple[ArithmeticOperandRole, int, str], ...]
    param_type_overrides: tuple[str | None, ...]

    @property
    def signature(self) -> str:
        return f"{self.result_kind}:=({','.join(self.param_kinds)})"


@dataclass(slots=True)
class _Candidate:
    key: _CandidateKey
    specs: list[tuple[str | None, LoweredSpecialization]]
    overload_positions: dict[tuple[str | None, str], tuple[int, ...]]
    extensions_by_profile: dict[str | None, dict[str, Extension]]

    @property
    def representative(self) -> LoweredSpecialization:
        return self.specs[0][1]

    @property
    def type_tags(self) -> tuple[str, ...]:
        return tuple(sorted({spec.type_tag for _profile, spec in self.specs}))


def _candidates(
    profiles: tuple[EmittedProfile, ...],
    static_selection: RustStaticSelectionPlan,
) -> dict[_CandidateKey, _Candidate]:
    grouped: dict[_CandidateKey, _Candidate] = {}
    selected_profile_names = {
        profile.profile_name for profile in static_selection.profiles
    }
    extensions_by_profile: dict[str | None, dict[str, Extension]] = {
        None: static_selection.fallback_module.extensions_by_name(),
        **{
            profile.profile.name: dict(profile.extensions)
            for profile in profiles
            if profile.profile.name in selected_profile_names
        },
    }
    inputs: list[tuple[str | None, LoweredSpecialization]] = [
        (None, spec)
        for _name, specs in sorted(
            static_selection.fallback_module.primitive_specializations
        )
        for spec in sorted(specs, key=_specialization_sort_key)
    ]
    inputs.extend(
        (profile.profile.name, spec)
        for profile in sorted(profiles, key=lambda item: item.profile.name)
        if profile.profile.name in selected_profile_names
        for _name, specs in sorted(profile.specializations("rust").items())
        for spec in sorted(specs, key=_specialization_sort_key)
    )
    seen: set[
        tuple[
            str | None,
            _CandidateKey,
            str,
            str,
            str,
            tuple[tuple[str, str | None], ...],
            tuple[str, str] | None,
            tuple[tuple[str, str], ...],
            bool,
        ]
    ] = set()
    for profile_name, spec in inputs:
        key = _candidate_key(spec)
        identity = (
            profile_name,
            key,
            spec.primitive_name,
            spec.extension_name,
            spec.type_tag,
            tuple((param.name, param.base_type_binding) for param in spec.type_params),
            (
                (spec.target.extension_isa, spec.target.base_tag)
                if spec.target is not None
                else None
            ),
            spec.axis,
            spec.safety.caller_unsafe,
        )
        if identity in seen:
            continue
        seen.add(identity)
        candidate = grouped.setdefault(
            key,
            _Candidate(key, [], {}, extensions_by_profile),
        )
        candidate.specs.append((profile_name, spec))
    by_delegate: dict[
        tuple[str | None, str], list[LoweredSpecialization]
    ] = defaultdict(list)
    for profile_name, spec in inputs:
        by_delegate[(profile_name, spec.primitive_name)].append(spec)
    overload_positions = {
        key: varying_positions(tuple(specs))
        for key, specs in by_delegate.items()
    }
    for candidate in grouped.values():
        candidate.overload_positions.update(overload_positions)
    return grouped


def _fallback_mapping_owner_diagnostics(
    plan: RustStaticSelectionPlan,
) -> tuple[Diagnostic, ...]:
    extensions = plan.fallback_module.extensions_by_name()
    specializations = tuple(
        spec
        for _primitive_name, specs in plan.fallback_module.primitive_specializations
        for spec in specs
    )
    return tuple(
        Diagnostic(
            severity="error",
            code="TSL-BACKEND-RUST-FACADE-MISSING-FALLBACK-OWNER",
            message=(
                "Rust facade fallback mapping "
                f"{mapping.type_tag}x{mapping.lanes} has no matching emitted "
                "specialization owned by an implementation-fallback extension"
            ),
        )
        for mapping in plan.fallback_mappings
        if not any(
            (extension := extensions.get(spec.extension_name)) is not None
            and extension.family_capability.implementation_fallback
            and _fallback_specialization_matches_mapping(
                spec,
                extension,
                mapping,
            )
            for spec in specializations
        )
    )


def _fallback_specialization_matches_mapping(
    specialization: LoweredSpecialization,
    extension: Extension,
    mapping: RustStaticVectorMapping,
) -> bool:
    if mapping.type_tag not in _specialization_vector_type_tags(specialization):
        return False
    if specialization.uses_sized_vector != mapping.uses_sized_vector:
        return False
    if mapping.uses_sized_vector:
        return True
    if extension.vector_bits_kind != "fixed":
        return False
    vector_bits = extension.vector_bits
    if vector_bits == 0:
        element_bits = scalar_bit_width(mapping.type_tag)
        if element_bits is None:
            return False
        vector_bits = element_bits
    return vector_bits == mapping.total_bits


def _specialization_vector_type_tags(
    specialization: LoweredSpecialization,
) -> frozenset[str]:
    result_vector_param = specialization.result_vector_param
    return frozenset(
        {specialization.type_tag}
        | (
            {specialization.target.base_tag}
            if specialization.target is not None
            else set()
        )
        | {
            parameter.base_type_binding
            for parameter in specialization.type_params
            if parameter.name == result_vector_param
            and parameter.base_type_binding is not None
        }
    )


def _candidate_key(spec: LoweredSpecialization) -> _CandidateKey:
    semantics = spec.primitive_semantics
    operation = semantics.operation
    arithmetic = semantics.arithmetic
    overload = semantics.overload
    conversion = semantics.conversion
    memory = semantics.memory
    return _CandidateKey(
        source_name=spec.source_primitive_name,
        result_kind=spec.result_kind,
        param_names=spec.param_names,
        param_kinds=spec.param_kinds,
        axis_names=tuple(name for name, _value in spec.axis),
        immediate=spec.immediate,
        generic_params=spec.generic_params,
        type_param_names=tuple(param.name for param in spec.type_params),
        result_vector_param=spec.result_vector_param,
        conversion=(
            (conversion.kind, conversion.lane_count, conversion.numeric_mode)
            if conversion is not None
            else None
        ),
        memory=(
            (memory.access, memory.addressing)
            if memory is not None
            else None
        ),
        has_concrete_target=spec.target is not None,
        mask_policy=spec.mask_policy,
        overload=(
            (overload.axis, overload.value, overload.is_primary_value)
            if overload is not None
            else None
        ),
        operation=operation.kind if operation is not None else None,
        operation_roles=tuple(
            sorted(
                (
                    (binding.role, binding.parameter_index, binding.parameter_kind)
                    for binding in operation.operand_bindings
                ),
                key=lambda item: item[0].value,
            )
        )
        if operation is not None
        else (),
        arithmetic_operations=arithmetic.ordered_operations if arithmetic else (),
        arithmetic_roles=tuple(
            sorted(
                (
                    (binding.role, binding.parameter_index, binding.parameter_kind)
                    for binding in arithmetic.operand_bindings
                ),
                key=lambda item: item[0].value,
            )
        )
        if arithmetic is not None
        else (),
        param_type_overrides=spec.effective_param_type_overrides,
    )


def _result_type_tag(
    specialization: LoweredSpecialization,
    result_vector_param: str,
) -> str | None:
    return next(
        (
            parameter.base_type_binding
            for parameter in specialization.type_params
            if parameter.name == result_vector_param
        ),
        None,
    )


def _conversion_pairs(
    candidate: _Candidate,
) -> tuple[RustFacadeConversionPair, ...]:
    result_vector_param = candidate.key.result_vector_param
    if result_vector_param is None:
        return ()
    grouped: dict[
        tuple[str, str],
        list[tuple[str | None, LoweredSpecialization]],
    ] = defaultdict(list)
    baseline_pairs: set[tuple[str, str]] = set()
    for profile_name, specialization in candidate.specs:
        target_type_tag = _result_type_tag(
            specialization,
            result_vector_param,
        )
        if target_type_tag is None:
            continue
        pair = (specialization.type_tag, target_type_tag)
        grouped[pair].append((profile_name, specialization))
        if profile_name is None:
            baseline_pairs.add(pair)
    return tuple(
        RustFacadeConversionPair(
            source_type_tag=source_type_tag,
            target_type_tag=target_type_tag,
            shape_keys=(),
            delegates=_delegates(candidate, tuple(grouped[pair])),
        )
        for pair in sorted(baseline_pairs)
        for source_type_tag, target_type_tag in (pair,)
    )


def _primary_indices(key: _CandidateKey) -> tuple[int, ...]:
    indices = {
        index
        for role, index, _kind in key.operation_roles
        if role is OperandRole.PRIMARY
    }
    indices.update(
        index
        for role, index, _kind in key.arithmetic_roles
        if role is ArithmeticOperandRole.PRIMARY
    )
    return tuple(sorted(indices))


def _role_signature_diagnostic(candidate: _Candidate) -> Diagnostic | None:
    key = candidate.key
    roles = (*key.operation_roles, *key.arithmetic_roles)
    for role, index, declared_kind in roles:
        if (
            index < 0
            or index >= len(key.param_kinds)
            or key.param_kinds[index] != declared_kind
        ):
            return _diagnostic(
                candidate,
                "TSL-BACKEND-RUST-FACADE-ROLE-MISMATCH",
                f"binds {role.value!r} to a parameter that does not match "
                f"signature kind {declared_kind!r}",
            )
    return None


def _candidate_invocation(
    candidate: _Candidate,
    public_operands: tuple[_PublicOperand, ...],
) -> RustFacadeInvocation | None:
    bindings: tuple[_RoleBinding, ...]
    if public_operands and isinstance(
        public_operands[0][0], ArithmeticOperandRole
    ):
        bindings = candidate.key.arithmetic_roles
    else:
        bindings = candidate.key.operation_roles
    return _invocation_from_roles(
        candidate.key.param_kinds,
        bindings,
        public_operands,
    )


def _invocation_from_roles(
    parameter_kinds: tuple[str, ...],
    role_bindings: tuple[_RoleBinding, ...],
    public_operands: tuple[_PublicOperand, ...],
) -> RustFacadeInvocation | None:
    if len(parameter_kinds) != len(public_operands):
        return None
    public_roles = tuple(role for role, _kind in public_operands)
    if len(set(public_roles)) != len(public_roles):
        return None
    if len(role_bindings) != len(parameter_kinds):
        return None
    if {role for role, _index, _kind in role_bindings} != set(public_roles):
        return None
    source_indices = tuple(index for _role, index, _kind in role_bindings)
    if tuple(sorted(source_indices)) != tuple(range(len(parameter_kinds))):
        return None

    public_index_by_role = {
        role: public_index
        for public_index, (role, _kind) in enumerate(public_operands)
    }
    public_kind_by_role = dict(public_operands)
    public_index_by_source_index = [-1] * len(parameter_kinds)
    for role, source_index, declared_kind in role_bindings:
        if (
            parameter_kinds[source_index] != declared_kind
            or public_kind_by_role[role] != declared_kind
        ):
            return None
        public_index_by_source_index[source_index] = public_index_by_role[role]
    return RustFacadeInvocation(tuple(public_index_by_source_index))


def _invocation_diagnostic(candidate: _Candidate) -> Diagnostic:
    return _diagnostic(
        candidate,
        "TSL-BACKEND-RUST-FACADE-INVOCATION-MISMATCH",
        "does not provide one complete, kind-compatible source index for every "
        "public operand role",
    )


def _roles_by_index(
    key: _CandidateKey,
) -> dict[int, OperandRole | ArithmeticOperandRole]:
    roles: dict[int, OperandRole | ArithmeticOperandRole] = {}
    for operation_role, index, _kind in key.operation_roles:
        roles.setdefault(index, operation_role)
    for arithmetic_role, index, _kind in key.arithmetic_roles:
        roles.setdefault(index, arithmetic_role)
    return roles


def _delegates(
    candidate: _Candidate,
    specs: tuple[tuple[str | None, LoweredSpecialization], ...] | None = None,
) -> tuple[RustFacadeDelegate, ...]:
    selected_specs = tuple(candidate.specs) if specs is None else specs
    by_profile: dict[
        str | None,
        dict[
            str,
            dict[
                tuple[str, str, bool, bool, bool, VectorBitsKind, int],
                set[tuple[tuple[str, str], ...]],
            ],
        ],
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for profile_name, spec in selected_specs:
        extension = candidate.extensions_by_profile.get(profile_name, {}).get(
            spec.extension_name
        )
        by_profile[profile_name][spec.primitive_name][
            (
                spec.extension_name,
                spec.type_tag,
                spec.uses_sized_vector,
                bool(
                    extension is not None
                    and extension.family_capability.implementation_fallback
                ),
                bool(
                    extension is not None
                    and extension.is_unconditional_implementation_fallback
                ),
                extension.vector_bits_kind if extension is not None else "",
                extension.vector_bits if extension is not None else 0,
            )
        ].add(spec.axis)
    return tuple(
        RustFacadeDelegate(
            profile_name,
            primitive_name,
            tuple(
                sorted(
                    (
                        RustFacadeDelegateVector(
                            extension_name=extension_name,
                            type_tag=type_tag,
                            attribute_combinations=tuple(
                                sorted(attribute_combinations)
                            ),
                            uses_sized_vector=uses_sized_vector,
                            implementation_fallback=implementation_fallback,
                            unconditional_implementation_fallback=(
                                unconditional_implementation_fallback
                            ),
                            vector_bits_kind=vector_bits_kind,
                            vector_bits=vector_bits,
                        )
                        for (
                            extension_name,
                            type_tag,
                            uses_sized_vector,
                            implementation_fallback,
                            unconditional_implementation_fallback,
                            vector_bits_kind,
                            vector_bits,
                        ), attribute_combinations in by_name[
                            primitive_name
                        ].items()
                    ),
                    key=lambda item: (
                        item.extension_name,
                        item.type_tag,
                        item.uses_sized_vector,
                    ),
                )
            ),
            candidate.overload_positions.get(
                (profile_name, primitive_name),
                (),
            ),
        )
        for profile_name, by_name in sorted(
            by_profile.items(), key=lambda item: (item[0] is not None, item[0] or "")
        )
        if len(by_name) == 1
        for primitive_name in by_name
    )


def _delegate_diagnostic(candidate: _Candidate) -> Diagnostic | None:
    by_profile: dict[tuple[str | None, str, str], set[str]] = defaultdict(set)
    for profile_name, spec in candidate.specs:
        target_type_tag = (
            _result_type_tag(spec, candidate.key.result_vector_param)
            if candidate.key.result_vector_param is not None
            else spec.target.base_tag
            if spec.target is not None
            else None
        )
        by_profile[
            (
                profile_name,
                spec.type_tag if target_type_tag is not None else "",
                target_type_tag or "",
            )
        ].add(spec.primitive_name)
    ambiguous = tuple(
        (key, tuple(sorted(names)))
        for key, names in by_profile.items()
        if len(names) > 1
    )
    if not ambiguous:
        return None
    rendered = "; ".join(
        (
            f"{profile_name or 'fallback'}"
            + (
                f" {source_type_tag}->{target_type_tag}"
                if target_type_tag
                else ""
            )
            + f": {', '.join(names)}"
        )
        for (
            profile_name,
            source_type_tag,
            target_type_tag,
        ), names in sorted(
            ambiguous,
            key=lambda item: (
                item[0][0] is not None,
                item[0][0] or "",
                item[0][1],
                item[0][2],
            ),
        )
    )
    return _diagnostic(
        candidate,
        "TSL-BACKEND-RUST-FACADE-DELEGATE-MISMATCH",
        f"has multiple lower-level delegates for one profile ({rendered})",
    )


def _diagnostic(
    candidate: _Candidate,
    code: str,
    detail: str,
) -> Diagnostic:
    return diagnostic_at(
        severity="error",
        code=code,
        message=f"Rust facade candidate {candidate.key.source_name!r} {detail}",
        source=candidate.representative.source,
    )


def _candidate_sort_key(candidate: _Candidate) -> tuple[object, ...]:
    key = candidate.key
    return (key.source_name, key.signature, key.mask_policy or "", key.overload or ())


def _specialization_sort_key(spec: LoweredSpecialization) -> tuple[object, ...]:
    return (
        spec.source_primitive_name,
        spec.primitive_name,
        spec.extension_name,
        spec.type_tag,
        tuple(
            (param.name, param.base_type_binding or "") for param in spec.type_params
        ),
        spec.axis,
    )
