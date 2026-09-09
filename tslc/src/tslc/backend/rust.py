"""Rust backend: render a primitive as a trait + Simd<> impls + generic wrapper fn."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from tslc.backend.primitive_rendering import body_for as _body_for
from tslc.backend.checked_api import (
    CheckedApiPlan,
    CheckedConditionPlan,
    applicable_checked_api_plan,
    checked_api_plan,
    checked_memory_condition,
    public_call_requires_unsafe,
)
from tslc.backend.primitive_rendering import variant_names as _variant_names
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.rust_direct_calls import (
    checked_free_function as _checked_free_function,
    checked_free_function_declaration as _checked_free_function_declaration,
    free_function as _free_function,
    free_function_declaration as _free_function_declaration,
    free_variant_functions as _free_variant_functions,
    implementation_lint_allowance as _implementation_lint_allowance,
    implementation_trait_name as _implementation_trait_name,
    indent as _indent,
    primitive_module as _primitive_module,
    rust_implementation_state as _rust_implementation_state,
    specialization_implementation_state as _spec_implementation_state,
    variant_primitive_name as _variant_primitive_name,
)
from tslc.backend.rust_documentation_api import (
    documentation_checked_wrapper as _documentation_checked_wrapper,
    documentation_free_function as _documentation_free_function,
    documentation_overloaded_checked_wrapper as _documentation_overloaded_checked_wrapper,
    documentation_overloaded_wrapper as _documentation_overloaded_wrapper,
    documentation_wrapper as _documentation_wrapper,
)
from tslc.backend.rust_implementation_state import (
    render_implementation_state_queries as _implementation_state_queries,
)
from tslc.backend.rust_policy_selection import (
    RustPolicySelection,
    RustPolicySelectionProfile,
    rust_policy_selection_shape_reason,
)
from tslc.backend.rust_signatures import (
    arithmetic_preconditions as _rust_arithmetic_preconditions,
    axis_name as _axis_name,
    checked_parameter_types as _checked_parameter_types,
    checked_runtime_names as _checked_runtime_names,
    checked_type_where as _checked_type_where,
    checked_type_where_predicates as _checked_type_where_predicates,
    concrete_param_type as _rust_concrete_param,
    concrete_result_type as _rust_concrete_result,
    concrete_type as _rust_concrete,
    generic_decls as _generic_decls,
    impl_generic_parts as _impl_generic_parts,
    immediate_precondition as _rust_immediate_precondition,
    kind_type as _kind_type,
    param_kind_type as _param_kind_type,
    params as _params,
    parameter_types as _parameter_types,
    runtime_names as _runtime_names,
    trait_args_by_name as _trait_args_by_name,
    trait_args_by_value as _trait_args_by_value,
    unsafe_call as _unsafe_call,
    unsafe_prefix as _unsafe_prefix,
    vector_type as _vector_type,
)
from tslc.backend.rust_public_declarations import (
    RustGenericParameter,
    RustPublicDeclaration,
    RustPublicParameter,
    rust_const_parameter,
    rust_parameter_role,
    rust_type_parameter,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_documentation import rust_doc as _rust_doc
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_type_params import (
    index_where as _index_where,
    type_param_where_clauses as _type_param_where_clauses,
    rust_base_dispatch_key_tag as _rust_base_dispatch_key_tag,
    type_param_base_key_args as _type_param_base_key_args,
    type_param_base_key_decls as _type_param_base_key_decls,
    type_param_decls as _type_param_decls,
    type_param_names as _type_param_names,
    with_consistent_type_param_bounds as _with_consistent_type_param_bounds,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.benchmark.model import SpecializationKey
from tslc.catalog.preconditions import (
    PreconditionCheckPrimitive,
    PreconditionErrorKind,
    PreconditionKind,
)
from tslc.catalog.memory import (
    MemoryAccess,
    MemoryAddressing,
    MemoryIndexedLaneExtent,
    MemoryPayloadExtent,
)
from tslc.catalog.scalar_types import SCALAR_TYPE_INFOS
from tslc.lower.lowerer import (
    LoweredSpecialization,
    effective_param_types,
    varying_positions,
)
from tslc.target_text import LoweredBody, RenderContext
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_PRIMITIVE_TRAIT_PREFIX = "detail::primitives::"
_PRECONDITION_METHOD = "__tsl_precondition_error"
_CHECKED_MEMORY_EXTENT_METHOD = "__tsl_checked_memory_extent"
_CHECKED_MEMORY_ALIGNMENT_METHOD = "__tsl_checked_memory_alignment"


def _qualified_primitive_trait_prefix(module_prefix: str) -> str:
    module = module_prefix.removesuffix("::")
    if not module:
        return _PRIMITIVE_TRAIT_PREFIX
    return f"{module}::{_PRIMITIVE_TRAIT_PREFIX}"


def _rust_precondition_error(error: PreconditionErrorKind) -> str:
    return rust_precondition_error(error)


def _rust_trait_precondition_condition(
    spec: LoweredSpecialization,
) -> CheckedConditionPlan | None:
    plan = checked_api_plan((spec,))
    if plan is None:
        return None
    conditions = tuple(
        condition
        for condition in plan.conditions
        if condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO
    )
    if not conditions:
        return None
    if len(conditions) != 1:
        raise ValueError("Rust implementation trait supports one delegated check")
    return conditions[0]


def _rust_precondition_method_parameters(
    spec: LoweredSpecialization,
    condition: CheckedConditionPlan,
    *,
    owner: str,
    arguments: bool = False,
) -> str:
    indexes = {condition.parameter_index}
    if condition.mask_parameter_index is not None:
        indexes.add(condition.mask_parameter_index)
    parts = []
    for index, (name, kind) in enumerate(zip(spec.param_names, spec.param_kinds)):
        if index not in indexes:
            continue
        parts.append(
            f"&{name}" if arguments else f"{name}: &{_param_kind_type(kind, owner)}"
        )
    return ", ".join(parts)


def _rust_trait_precondition_declaration(spec: LoweredSpecialization) -> str:
    condition = _rust_trait_precondition_condition(spec)
    if condition is None:
        return ""
    params = _rust_precondition_method_parameters(spec, condition, owner="Self")
    return f"    fn {_PRECONDITION_METHOD}({params}) -> Option<PreconditionError>;\n"


def _rust_impl_precondition_method(spec: LoweredSpecialization) -> str:
    condition = _rust_trait_precondition_condition(spec)
    if condition is None:
        return ""
    params = _rust_precondition_method_parameters(spec, condition, owner="Self")
    info = SCALAR_TYPE_INFOS.get(spec.type_tag)
    if info is None:
        raise ValueError(f"checked precondition has unknown type {spec.type_tag!r}")
    if info.floating:
        body = "None"
    else:
        required = {
            PreconditionCheckPrimitive.ZERO_VECTOR,
            PreconditionCheckPrimitive.EQUAL,
            PreconditionCheckPrimitive.MASK_POPULATION_COUNT,
        }
        if not required.issubset(condition.check_primitives):
            raise ValueError("zero-divisor check plan is missing support primitives")
        zero = rust_raw_identifier(PreconditionCheckPrimitive.ZERO_VECTOR.value)
        equal = rust_raw_identifier(PreconditionCheckPrimitive.EQUAL.value)
        population = rust_raw_identifier(
            PreconditionCheckPrimitive.MASK_POPULATION_COUNT.value
        )
        lines = [
            f"let zero_divisors = {equal}::<Self>(",
            f"    *{condition.parameter_name}, {zero}::<Self>());",
        ]
        checked_mask = "zero_divisors"
        if condition.mask_parameter_name is not None:
            if PreconditionCheckPrimitive.MASK_AND not in condition.check_primitives:
                raise ValueError("masked zero-divisor check has no mask-and primitive")
            mask_and = rust_raw_identifier(PreconditionCheckPrimitive.MASK_AND.value)
            lines.extend(
                (
                    f"let active_zero_divisors = {mask_and}::<Self>(",
                    f"    *{condition.mask_parameter_name}, zero_divisors);",
                )
            )
            checked_mask = "active_zero_divisors"
        lines.extend(
            (
                f"if {population}::<Self>({checked_mask}) != 0 {{",
                f"    Some({_rust_precondition_error(condition.error)})",
                "} else {",
                "    None",
                "}",
            )
        )
        body = "\n".join(lines)
    return (
        f"    #[inline]\n"
        f"    #[allow(unused_variables)]\n"
        f"    fn {_PRECONDITION_METHOD}({params}) -> Option<PreconditionError> {{\n"
        f"{_indent(body, 8)}\n"
        "    }\n"
    )


def _rust_forwarded_precondition_method(
    spec: LoweredSpecialization,
    selected_trait_name: str,
) -> str:
    condition = _rust_trait_precondition_condition(spec)
    if condition is None:
        return ""
    params = _rust_precondition_method_parameters(spec, condition, owner="Self")
    args = _rust_precondition_method_parameters(
        spec, condition, owner="Self", arguments=True
    )
    return (
        f"    #[inline(always)]\n"
        f"    fn {_PRECONDITION_METHOD}({params}) -> Option<PreconditionError> {{\n"
        f"        <Self as {selected_trait_name}>::{_PRECONDITION_METHOD}({args})\n"
        "    }\n"
    )


def _rust_checked_memory_extent(
    condition: CheckedConditionPlan,
    owner: str,
    *,
    target_owner: str | None = None,
) -> str:
    payload_extents = condition.memory_payload_extents
    if payload_extents == (MemoryPayloadExtent.SCALAR,):
        return "1"
    if payload_extents == (MemoryPayloadExtent.VECTOR,):
        return f"{owner}::lane_count()"
    if payload_extents == (MemoryPayloadExtent.TARGET_VECTOR,):
        if target_owner is None:
            raise ValueError(
                "target-vector checked memory requires a target owner"
            )
        return f"{target_owner}::lane_count()"
    raise ValueError(
        "non-overloaded Rust checked memory API requires one static payload extent"
    )


def _rust_checked_memory_alignment(
    condition: CheckedConditionPlan,
    owner: str,
) -> tuple[str, str]:
    payload_extents = condition.memory_payload_extents
    if payload_extents in {
        (MemoryPayloadExtent.SCALAR,),
        (MemoryPayloadExtent.TARGET_VECTOR,),
    }:
        alignment = f"core::mem::align_of::<{owner}::BaseType>()"
    elif payload_extents in {
        (MemoryPayloadExtent.VECTOR,),
        (MemoryPayloadExtent.ACTIVE_LANES,),
    }:
        alignment = f"{owner}::ALIGN"
    else:
        raise ValueError(
            "non-overloaded Rust checked memory API requires one payload extent"
        )
    axis = (
        None
        if condition.memory_alignment_axis_name is None
        else _axis_name(condition.memory_alignment_axis_name)
    )
    if axis is None:
        raise ValueError("Rust checked alignment condition has no alignment axis")
    return alignment, axis


def _rust_overloaded_memory_trait_members(
    specializations: tuple[LoweredSpecialization, ...],
) -> str:
    plan = applicable_checked_api_plan(specializations)
    if plan is None or not any(
        condition.memory_access is not None for condition in plan.conditions
    ):
        return ""
    return (
        "    #[doc(hidden)]\n"
        f"    fn {_CHECKED_MEMORY_EXTENT_METHOD}() -> usize;\n"
        "    #[doc(hidden)]\n"
        f"    fn {_CHECKED_MEMORY_ALIGNMENT_METHOD}() -> usize;\n"
    )


def _rust_overloaded_memory_impl_members(
    specialization: LoweredSpecialization,
    vector_type: str,
) -> str:
    plan = applicable_checked_api_plan((specialization,))
    if plan is None or not any(
        condition.memory_access is not None for condition in plan.conditions
    ):
        return ""
    memory = specialization.primitive_semantics.memory
    if memory is None:
        raise ValueError("checked Rust memory overload has no memory contract")
    if memory.payload_extent is MemoryPayloadExtent.SCALAR:
        extent = "1"
        alignment = "core::mem::align_of::<Self>()"
    else:
        extent = f"<{vector_type} as SimdVector>::lane_count()"
        alignment = f"<{vector_type} as SimdVector>::ALIGN"
    return (
        "    #[inline]\n"
        f"    fn {_CHECKED_MEMORY_EXTENT_METHOD}() -> usize {{ {extent} }}\n"
        "    #[inline]\n"
        f"    fn {_CHECKED_MEMORY_ALIGNMENT_METHOD}() -> usize {{ {alignment} }}\n"
    )


@dataclass(frozen=True, slots=True)
class _RustPublicWrapperFacts:
    trait_args: tuple[str, ...]
    public_trait_args: tuple[str, ...]
    generic_parameters: tuple[RustGenericParameter, ...]
    target_owner: str | None
    result_owner: str
    index_type: str | None
    vector_bound: str


def _rust_const_generic_parameters(
    shape: LoweredSpecialization,
) -> tuple[RustGenericParameter, ...]:
    parameters = [
        rust_const_parameter(_axis_name(key), "bool") for key, _ in shape.axis
    ]
    if shape.immediate is not None:
        parameters.append(
            rust_const_parameter(shape.immediate[0], shape.immediate[1])
        )
    parameters.extend(
        rust_const_parameter(name, typ)
        for name, typ, _default in shape.generic_params
    )
    return tuple(parameters)


def _rust_type_generic_parameters(
    shape: LoweredSpecialization,
) -> tuple[RustGenericParameter, ...]:
    return tuple(
        rust_type_parameter(
            parameter.name,
            "StaticSimdVector",
            *(
                f"{_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(bound)}"
                for bound in parameter.bounds
            ),
        )
        for parameter in shape.type_params
    )


def _rust_public_wrapper_facts(
    primitive_name: str,
    shape: LoweredSpecialization,
) -> _RustPublicWrapperFacts:
    public_trait_args = list(_trait_args_by_name(shape))
    trait_args = list(public_trait_args)
    generic_parameters: list[RustGenericParameter] = list(
        _rust_const_generic_parameters(shape)
    )
    target_owner: str | None = None
    result_owner = "S"
    if shape.target is not None:
        trait_args.insert(0, "T")
        public_trait_args.insert(0, "T")
        generic_parameters.insert(0, rust_type_parameter("T", "StaticSimdVector"))
        target_owner = "T"
        result_owner = "T"
    index_type: str | None = None
    if shape.type_params:
        type_names = _type_param_names(shape)
        trait_args = [
            *type_names,
            *_type_param_base_key_args(shape, mode="projection"),
            *trait_args,
        ]
        public_trait_args = [*type_names, *public_trait_args]
        generic_parameters = [
            *_rust_type_generic_parameters(shape),
            *generic_parameters,
        ]
        index_type = f"{shape.type_params[0].name}::RegisterType"
        if shape.result_vector_param is not None:
            result_owner = shape.result_vector_param
    rendered_trait_args = (
        f"<{', '.join(trait_args)}>" if trait_args else ""
    )
    vector_bound = (
        f"{_PRIMITIVE_TRAIT_PREFIX}"
        f"{rust_primitive_trait_name(primitive_name)}{rendered_trait_args}"
    )
    return _RustPublicWrapperFacts(
        trait_args=tuple(trait_args),
        public_trait_args=tuple(public_trait_args),
        generic_parameters=tuple(generic_parameters),
        target_owner=target_owner,
        result_owner=result_owner,
        index_type=index_type,
        vector_bound=vector_bound,
    )


def _rust_checked_generic_parameters(
    shape: LoweredSpecialization,
    facts: _RustPublicWrapperFacts,
    plan: CheckedApiPlan,
) -> tuple[RustGenericParameter, ...]:
    """Add checked-guard dependencies owned by a free SIMD type parameter."""

    if not shape.type_params:
        return facts.generic_parameters
    index_owner = shape.type_params[0].name
    index_bounds: list[str] = []
    for condition in plan.conditions:
        if condition.kind is not PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
            continue
        if (
            PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
            in condition.check_primitives
        ):
            primitive = PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
            index_bounds.append(
                f"{_PRIMITIVE_TRAIT_PREFIX}"
                f"{rust_primitive_trait_name(primitive.value)}"
            )
    if not index_bounds:
        return facts.generic_parameters
    return tuple(
        rust_type_parameter(
            parameter.name,
            *parameter.bounds,
            *(bound for bound in index_bounds if bound not in parameter.bounds),
        )
        if parameter.name == index_owner
        else parameter
        for parameter in facts.generic_parameters
    )


def _rust_overload_identity(
    specializations: tuple[LoweredSpecialization, ...], surface: str
) -> str:
    shapes = sorted(
        {
            f"{spec.result_kind}=({','.join(spec.param_kinds)})"
            for spec in specializations
        }
    )
    return f"{surface}:" + "|".join(shapes)


def _rust_wrapper_declaration(
    primitive_name: str,
    shape: LoweredSpecialization,
    *,
    caller_unsafe: bool,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration:
    facts = _rust_public_wrapper_facts(primitive_name, shape)
    parameters = tuple(
        RustPublicParameter(
            name,
            typ,
            rust_parameter_role(shape, index, shape.param_kinds[index]),
        )
        for index, name, typ in _parameter_types(
            shape,
            "S",
            target_owner=facts.target_owner,
            vidx_type=facts.index_type,
        )
    )
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}#vector",
        name=rust_raw_identifier(primitive_name),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=_rust_overload_identity((shape,), "vector"),
        visibility="pub",
        generic_parameters=(
            rust_type_parameter("S", facts.vector_bound),
            *facts.generic_parameters,
        ),
        parameters=parameters,
        where_predicates=tuple(
            _type_param_where_clauses(shape, base_dispatch="projection")
        ),
        where_inline=True,
        result_type=_kind_type(shape.result_kind, facts.result_owner),
        result_form="direct",
        unsafe=caller_unsafe,
    )


def _rust_checked_wrapper_declaration(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    *,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration | None:
    plan = applicable_checked_api_plan(specializations)
    if plan is None:
        return None
    shape = specializations[0]
    facts = _rust_public_wrapper_facts(primitive_name, shape)
    checked_where = _checked_type_where_predicates(plan, "S")
    index_where = tuple(
        _type_param_where_clauses(shape, base_dispatch="projection")
    )
    if checked_where and index_where:
        raise ValueError(
            "checked wrapper cannot combine numeric-domain and index-vector bounds"
        )
    parameters = tuple(
        RustPublicParameter(
            name,
            typ,
            rust_parameter_role(shape, index, shape.param_kinds[index]),
        )
        for index, name, typ in _checked_parameter_types(
            shape,
            "S",
            plan,
            target_owner=facts.target_owner,
            vidx_type=facts.index_type,
        )
    )
    ordinary_identity = f"crate::profile::{primitive_name}#vector"
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}_checked#vector",
        name=rust_raw_identifier(f"{primitive_name}_checked"),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=_rust_overload_identity(specializations, "checked-vector"),
        visibility="pub",
        generic_parameters=(
            rust_type_parameter("S", facts.vector_bound),
            *_rust_checked_generic_parameters(shape, facts, plan),
        ),
        parameters=parameters,
        where_predicates=checked_where or index_where,
        result_type=(
            f"Result<{_kind_type(shape.result_kind, facts.result_owner)}, "
            "PreconditionError>"
        ),
        result_form="result",
        attributes=("#[inline]",),
        checked_of=ordinary_identity,
        error_form="result",
    )


def _rust_overloaded_wrapper_declaration(
    primitive_name: str,
    specializations: tuple[LoweredSpecialization, ...],
    *,
    checked: bool,
    caller_unsafe: bool,
    reachability: tuple[str, ...],
) -> RustPublicDeclaration | None:
    shape = specializations[0]
    varying = varying_positions(specializations)
    if len(varying) != 1:
        raise ValueError("Rust public overload requires one varying parameter")
    varying_index = varying[0]
    axis_args = "".join(f", {_axis_name(key)}" for key, _ in shape.axis)
    generic_args = "".join(
        f", {name}" for name, _typ, _default in shape.generic_params
    )
    arg_trait = (
        f"{_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
    )
    generics: tuple[RustGenericParameter, ...] = (
        rust_type_parameter("S", "StaticSimdVector"),
        *_rust_const_generic_parameters(shape),
        rust_type_parameter("V", f"{arg_trait}<S{axis_args}{generic_args}>")
    )
    plan = applicable_checked_api_plan(specializations) if checked else None
    if checked and plan is None:
        return None
    memory = checked_memory_condition(plan.conditions) if plan is not None else None
    parameters: list[RustPublicParameter] = []
    for index, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds)):
        if index == varying_index:
            typ = "V"
        elif memory is not None and index == memory.parameter_index:
            typ = (
                "&[S::BaseType]"
                if memory.memory_access is MemoryAccess.READ
                else "&mut [S::BaseType]"
            )
        else:
            typ = _param_kind_type(kind, "S")
        parameters.append(
            RustPublicParameter(
                name,
                typ,
                rust_parameter_role(shape, index, kind),
            )
        )
    suffix = "_checked" if checked else ""
    ordinary_identity = f"crate::profile::{primitive_name}#overload"
    result = _kind_type(shape.result_kind, "S")
    return RustPublicDeclaration(
        identity=f"crate::profile::{primitive_name}{suffix}#overload",
        name=rust_raw_identifier(f"{primitive_name}{suffix}"),
        owner="crate::profile",
        reachability=reachability,
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=_rust_overload_identity(
            specializations, "checked-overload" if checked else "overload"
        ),
        visibility="pub",
        generic_parameters=generics,
        parameters=tuple(parameters),
        result_type=(
            f"Result<{result}, PreconditionError>" if checked else result
        ),
        result_form="result" if checked else "direct",
        attributes=("#[inline]",) if checked else (),
        unsafe=caller_unsafe and not checked,
        checked_of=ordinary_identity if checked else None,
        error_form="result" if checked else None,
    )


class RustBackend:
    backend_id = "rust"

    def __init__(
        self,
        *,
        feature_spellings: Mapping[str, str] | None = None,
        emit_target_features: bool = True,
        policy_selection: RustPolicySelectionProfile | None = None,
        deferred_policy_mapping_file: str | None = None,
    ) -> None:
        self._feature_spellings = dict(feature_spellings or {})
        self._emit_target_features = emit_target_features
        self._policy_selection = policy_selection
        if deferred_policy_mapping_file is not None and policy_selection is None:
            raise ValueError(
                "deferred Rust policy selection requires a typed selection profile"
            )
        self._deferred_policy_mapping_file = deferred_policy_mapping_file

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        internal = self.render_primitive_internal(primitive_name, specializations)
        public = self.render_primitive_public(primitive_name, specializations)
        if not internal:
            return public
        return "\n\n".join([self.render_primitive_module(internal), public])

    def render_primitive_module(self, internal: str) -> str:
        if not internal.strip():
            return ""
        if (
            self._deferred_policy_mapping_file is not None
            and self._policy_selection is not None
            and self._policy_selection.selections
        ):
            internal = (
                f"{internal}\n\n"
                "include!(concat!(env!(\"OUT_DIR\"), "
                f'"/{self._deferred_policy_mapping_file}"));'
            )
        return _primitive_module(internal)

    def render_policy_selection_impl(
        self,
        selection: RustPolicySelection,
    ) -> str:
        """Render one trusted mapping fragment from typed backend facts."""

        if self._policy_selection is None:
            raise ValueError("Rust policy mapping rendering requires a selection profile")
        expected = next(
            (
                candidate
                for candidate in self._policy_selection.selections
                if candidate.key == selection.key
            ),
            None,
        )
        if expected is None or (
            expected.specialization != selection.specialization
            or expected.candidate_ids != selection.candidate_ids
        ):
            raise ValueError(
                "Rust policy mapping selection is foreign or stale for this profile"
            )
        return self._selection_impl(
            selection,
            caller_unsafe=public_call_requires_unsafe(
                (selection.specialization,)
            ),
        )

    def render_primitive_internal(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return _free_variant_functions(specializations, backend=self)
        # Rust has no fn overloading: a primitive with several signatures (e.g. store's
        # `(ptr,v)`/`(ptr,s)`) dispatches on the varying argument's type via a trait
        # implemented for that type. Single-signature primitives keep the simple trait.
        if varying_positions(specializations):
            parts = [self._render_overloaded_internal(primitive_name, specializations)]
            parts.extend(
                rendered
                for name in _variant_names(specializations)
                if (
                    rendered := self._render_overloaded_internal(
                        primitive_name,
                        specializations,
                        variant_name=name,
                    )
                )
            )
            return "\n\n".join(parts)
        caller_unsafe = public_call_requires_unsafe(specializations)
        trait = self._trait(primitive_name, shape, caller_unsafe=caller_unsafe)
        impls = [
            self._impl(spec, caller_unsafe=caller_unsafe)
            for spec in specializations
            if self._selection_for(spec) is None
        ]
        parts = [trait, *impls]
        selections = tuple(
            selection
            for spec in specializations
            if (selection := self._selection_for(spec)) is not None
        )
        if selections:
            default_primitive = _variant_primitive_name(primitive_name, "default")
            parts.append(
                self._trait(
                    default_primitive,
                    shape,
                    caller_unsafe=caller_unsafe,
                )
            )
            parts.extend(
                self._impl(
                    selection.specialization,
                    caller_unsafe=caller_unsafe,
                    implementation_trait_variant="default",
                )
                for selection in selections
            )
        for name in _variant_names(specializations):
            variant_primitive = _variant_primitive_name(primitive_name, name)
            variant_impls = [
                rendered
                for spec in specializations
                if (rendered := self._impl(
                    spec,
                    caller_unsafe=caller_unsafe,
                    variant_name=name,
                ))
            ]
            if variant_impls:
                parts.append(
                    self._trait(
                        variant_primitive,
                        shape,
                        caller_unsafe=caller_unsafe,
                    )
                )
                parts.extend(variant_impls)
        if self._deferred_policy_mapping_file is None:
            parts.extend(
                self._selection_impl(selection, caller_unsafe=caller_unsafe)
                for selection in selections
            )
        return "\n\n".join(parts)

    def render_primitive_public(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            # A non-vector primitive (`allocate`/`deallocate`): a plain `pub fn` in the module,
            # not a `SimdVector`-bound trait/impl/wrapper.
            return "\n\n".join(
                part
                for part in (
                    _free_function(shape, backend=self),
                    _checked_free_function(shape),
                )
                if part
            )
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            ordinary = self._render_overloaded_wrapper(
                primitive_name, specializations, caller_unsafe=caller_unsafe
            )
            checked = self._render_overloaded_checked_wrapper(
                primitive_name, specializations
            )
            return "\n\n".join(part for part in (ordinary, checked) if part)
        ordinary = self._wrapper(primitive_name, shape, caller_unsafe=caller_unsafe)
        checked = self._checked_wrapper(primitive_name, specializations)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def public_declarations(
        self,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
        *,
        reachability: tuple[str, ...],
    ) -> tuple[RustPublicDeclaration, ...]:
        """Finalize the stable profile-callable declarations for one group."""

        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind, shape.param_kinds
        ):
            ordinary = _free_function_declaration(
                shape, reachability=reachability
            )
            checked = _checked_free_function_declaration(
                shape, reachability=reachability
            )
            return (ordinary,) if checked is None else (ordinary, checked)
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            overloaded_ordinary = _rust_overloaded_wrapper_declaration(
                primitive_name,
                specializations,
                checked=False,
                caller_unsafe=caller_unsafe,
                reachability=reachability,
            )
            overloaded_checked = _rust_overloaded_wrapper_declaration(
                primitive_name,
                specializations,
                checked=True,
                caller_unsafe=caller_unsafe,
                reachability=reachability,
            )
            assert overloaded_ordinary is not None
            return (
                (overloaded_ordinary,)
                if overloaded_checked is None
                else (overloaded_ordinary, overloaded_checked)
            )
        ordinary = _rust_wrapper_declaration(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
            reachability=reachability,
        )
        checked = _rust_checked_wrapper_declaration(
            primitive_name,
            specializations,
            reachability=reachability,
        )
        return (ordinary,) if checked is None else (ordinary, checked)

    def render_documentation_api(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render one profile-neutral public API stub for rustdoc.

        The generated function preserves the public parameter, result, generic,
        safety, and documentation shape without depending on a profile-local
        dispatch trait or implementation body.
        """

        specializations = _with_consistent_type_param_bounds(specializations)
        shape = specializations[0]
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            shape.result_kind,
            shape.param_kinds,
        ):
            return "\n\n".join(
                part
                for part in (
                    _documentation_free_function(shape),
                    _checked_free_function(shape),
                )
                if part
            )
        caller_unsafe = public_call_requires_unsafe(specializations)
        if varying_positions(specializations):
            ordinary = _documentation_overloaded_wrapper(
                primitive_name,
                specializations,
                caller_unsafe=caller_unsafe,
            )
            checked = _documentation_overloaded_checked_wrapper(
                primitive_name, specializations
            )
            return "\n\n".join(part for part in (ordinary, checked) if part)
        ordinary = _documentation_wrapper(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
        )
        checked = _documentation_checked_wrapper(primitive_name, specializations)
        return "\n\n".join(part for part in (ordinary, checked) if part)

    def render_implementation_state_queries(
        self,
        by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    ) -> str:
        return _implementation_state_queries(
            {
                primitive_name: _with_consistent_type_param_bounds(specializations)
                for primitive_name, specializations in by_primitive.items()
            }
        )

    def concrete_vector_type(self, spec: LoweredSpecialization) -> str:
        """Spell the concrete Rust SIMD type selected for one specialization."""

        return _vector_type(spec)

    def render_direct_implementation_call(
        self,
        spec: LoweredSpecialization,
        variant_name: str | None,
        arguments: tuple[str, ...],
        *,
        module_prefix: str = "",
        immediate_value: str | None = None,
        overload_parameter_positions: tuple[int, ...] = (),
        selection_key: SpecializationKey | None = None,
    ) -> str:
        """Render a direct call to one already-emitted implementation trait.

        This is the backend-owned call boundary for projections such as the
        generated benchmark harness.  It deliberately bypasses the public
        wrapper without duplicating Rust trait naming, const-argument order,
        concrete vector spelling, or caller-unsafe framing.
        """

        if _body_for(spec, variant_name) is None:
            candidate = "default" if variant_name is None else variant_name
            raise ValueError(
                f"Rust implementation candidate {candidate!r} is not available for "
                f"{spec.primitive_name!r}"
            )
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            spec.result_kind,
            spec.param_kinds,
        ):
            raise ValueError("direct Rust implementation trait calls require a SIMD shape")
        expected_arguments = sum(
            kind != DEFAULT_SUPPORT_POLICY.immediate_kind for kind in spec.param_kinds
        )
        if len(arguments) != expected_arguments:
            raise ValueError(
                f"Rust implementation call for {spec.primitive_name!r} requires "
                f"{expected_arguments} runtime arguments, got {len(arguments)}"
            )
        if immediate_value is not None and spec.immediate is None:
            raise ValueError(
                f"Rust implementation call for {spec.primitive_name!r} has no immediate"
            )
        if spec.type_params:
            raise ValueError(
                "direct Rust implementation calls with SIMD type parameters require "
                "concrete type arguments"
            )
        trait_prefix = _qualified_primitive_trait_prefix(module_prefix)

        if overload_parameter_positions:
            if len(overload_parameter_positions) != 1:
                raise ValueError(
                    "direct Rust implementation calls support one overload parameter"
                )
            if spec.immediate is not None or spec.target is not None:
                raise ValueError(
                    "direct overloaded Rust implementation calls do not support "
                    "immediate or target-vector shapes"
                )
            varying = overload_parameter_positions[0]
            if not 0 <= varying < len(arguments):
                raise ValueError("Rust overload parameter position is out of range")
            overload_trait_arguments = [
                self.concrete_vector_type(spec),
                *(value for _name, value in spec.axis),
                *(default for _name, _type, default in spec.generic_params),
            ]
            trait_name = _implementation_trait_name(
                spec.primitive_name, variant_name
            )
            fixed_arguments = [
                argument
                for position, argument in enumerate(arguments)
                if position != varying
            ]
            call_arguments = ", ".join(
                (arguments[varying], *fixed_arguments)
            )
            receiver_type = _rust_concrete(spec, spec.param_kinds[varying])
            call = (
                f"<{receiver_type} as {trait_prefix}{trait_name}Arg"
                f"<{', '.join(overload_trait_arguments)}>>::apply({call_arguments})"
            )
            return _unsafe_call(call, spec.safety.caller_unsafe)

        trait_arguments: list[str] = []
        if spec.target is not None:
            trait_arguments.append(spec.target.vector_spelling)
        trait_arguments.extend(value for _name, value in spec.axis)
        if spec.immediate is not None:
            trait_arguments.append(immediate_value or spec.immediate[0])
        trait_arguments.extend(default for _name, _type, default in spec.generic_params)
        generic_args = (
            f"<{', '.join(trait_arguments)}>" if trait_arguments else ""
        )
        direct_variant = variant_name
        if (
            variant_name is None
            and selection_key is not None
            and rust_policy_selection_shape_reason(selection_key, spec) is None
        ):
            direct_variant = "default"
        trait_name = _implementation_trait_name(spec.primitive_name, direct_variant)
        call = (
            f"<{self.concrete_vector_type(spec)} as {trait_prefix}{trait_name}"
            f"{generic_args}>::apply({', '.join(arguments)})"
        )
        return _unsafe_call(call, public_call_requires_unsafe((spec,)))

    def _render_overloaded_internal(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
        *,
        variant_name: str | None = None,
    ) -> str:
        shape = specs[0]
        internal_name = _variant_primitive_name(primitive_name, variant_name)
        caller_unsafe = public_call_requires_unsafe(specs)
        # Exactly one varying position: wider overloads were rejected by
        # validate_rust_profiles (TSL-BACKEND-RUST-UNSUPPORTED-MULTI-POSITION-OVERLOAD).
        vi = varying_positions(specs)[0]
        arg_trait = f"{rust_primitive_trait_name(internal_name)}Arg"
        fixed = [
            (name, kind)
            for i, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds))
            if i != vi
        ]
        # In the arg-trait `Self` is the *argument* type, not the vector — a vector-typed
        # result (e.g. shift's `v` -> register) must project through the vector param `S`.
        ret = _kind_type(shape.result_kind, "S")
        axis_decl = "".join(f", const {_axis_name(k)}: bool" for k, _ in shape.axis)
        # `generic_params` (e.g. `PreserveSign`) are free const generics on the arg-trait too.
        gp_decl = "".join(f", const {name}: {typ}" for name, typ, _ in shape.generic_params)
        gp_names = [name for name, _, _ in shape.generic_params]
        fixed_trait = "".join(f", {n}: {_param_kind_type(k, 'S')}" for n, k in fixed)
        doc = _rust_doc(
            shape,
            context="Rust overload dispatch trait",
            concrete=False,
            specializations=specs,
        )
        trait = (
            (f"{doc}\n" if doc else "")
            + f"pub trait {arg_trait}<S: StaticSimdVector{axis_decl}{gp_decl}> {{\n"
            "    const IMPLEMENTATION_STATE: ImplementationState;\n"
            f"{_rust_overloaded_memory_trait_members(specs)}"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_trait}) -> {ret};\n"
            f"}}"
        )

        # Dedup is per (Vec, axis) group — one impl per distinct argument type *within*
        # a group (scalar's register==base collapses its two overloads to one).
        impls: list[str] = []
        seen: set[tuple[str, str, tuple, tuple[str, ...]]] = set()
        for spec in specs:
            body_ref = _body_for(spec, variant_name)
            if body_ref is None:
                continue
            signature = (
                spec.base_type_spelling,
                spec.extension_name,
                spec.axis,
                effective_param_types(spec),
            )
            if signature in seen:
                continue
            seen.add(signature)
            # A sized vector's overloaded impls are parameterized by its lane parameter — UNLESS
            # the slot is monomorphized at a concrete lane count (a numeric `lane_parameter` like
            # "16"), in which case the impl is over a concrete `Generic<16>` with no lane generic.
            lane_parameter = spec.lane_parameter
            has_lane_generic = (
                spec.uses_sized_vector
                and lane_parameter is not None
                and not lane_parameter.isdigit()
            )
            impl_generics = (
                [f"const {lane_parameter}: usize"]
                if has_lane_generic
                else []
            ) + [
                f"const {name}: {typ}" for name, typ, _ in spec.generic_params
            ]
            impl_generic_names = (
                [lane_parameter]
                if has_lane_generic and lane_parameter is not None
                else []
            ) + [name for name, _, _ in spec.generic_params]
            vec = self.concrete_vector_type(spec)
            impl_prefix = f"impl<{', '.join(impl_generics)}>" if impl_generics else "impl"
            self_ty = _rust_concrete(spec, spec.param_kinds[vi])
            trait_args = (
                "<"
                + vec
                + "".join(f", {value}" for _, value in spec.axis)
                + "".join(f", {name}" for name in gp_names)
                + ">"
            )
            fixed_impl = "".join(
                f", {n}: {_rust_concrete_param(spec, k)}" for n, k in fixed
            )
            ret_impl = _rust_concrete_result(spec)
            body_context = RenderContext(
                current_owner=f"<{vec} as SimdVector>",
                current_vector=vec,
                current_register=spec.register_spelling,
                current_base=spec.base_type_spelling,
                current_mask=f"<{vec} as SimdVector>::MaskType",
                current_imask=f"<{vec} as SimdVector>::ImaskType",
            )
            helper_params = ", ".join(
                (
                    f"{spec.param_names[vi]}: {self_ty}",
                    *(f"{n}: {_rust_concrete_param(spec, k)}" for n, k in fixed),
                )
            )
            helper_args = ", ".join((spec.param_names[vi], *[n for n, _ in fixed]))
            method_body = "\n".join(
                (
                    f"let {spec.param_names[vi]} = self;",
                    self._target_feature_body(
                        spec,
                        body_ref,
                        render_context=body_context,
                        params=helper_params,
                        args=helper_args,
                        return_type=ret_impl,
                        generic_decls=impl_generics,
                        generic_names=impl_generic_names,
                        receiver_type=vec,
                    ),
                )
            )
            doc_context = (
                "Rust specialization"
                if variant_name is None
                else f"Rust specialization variant {variant_name}"
            )
            doc = _rust_doc(spec, context=doc_context)
            impls.append(
                (f"{doc}\n" if doc else "")
                + f"{impl_prefix} {arg_trait}{trait_args} for {self_ty} {{\n"
                f"    const IMPLEMENTATION_STATE: ImplementationState = "
                f"{_rust_implementation_state(_spec_implementation_state(spec, variant_name))};\n"
                f"{_rust_overloaded_memory_impl_members(spec, vec)}"
                f"{_indent(_implementation_lint_allowance(spec), 4)}\n"
                f"    {_unsafe_prefix(caller_unsafe)}fn apply(self{fixed_impl}) -> {ret_impl} {{\n"
                f"{_indent(method_body, 8)}\n"
                f"    }}\n"
                f"}}"
            )
            shift = spec.primitive_semantics.shift
            if shift is not None and spec.param_kinds[vi] == "s":
                forwarded_args = ", ".join(name for name, _kind in fixed)
                for count_tag in shift.scalar_count_types:
                    count_type = SCALAR_TYPE_INFOS[
                        count_tag
                    ].documentation_short_label
                    if count_type == self_ty:
                        continue
                    call = (
                        f"<{self_ty} as {arg_trait}{trait_args}>::apply("
                        f"self as {self_ty}"
                        + (f", {forwarded_args}" if forwarded_args else "")
                        + ")"
                    )
                    if caller_unsafe:
                        call = f"unsafe {{ {call} }}"
                    impls.append(
                        f"{impl_prefix} {arg_trait}{trait_args} for {count_type} {{\n"
                        "    const IMPLEMENTATION_STATE: ImplementationState = "
                        f"<{self_ty} as {arg_trait}{trait_args}>::"
                        "IMPLEMENTATION_STATE;\n"
                        f"    {_unsafe_prefix(caller_unsafe)}fn apply("
                        f"self{fixed_impl}) -> {ret_impl} {{\n"
                        f"        {call}\n"
                        "    }\n"
                        "}"
                    )

        return "\n\n".join([trait, *impls]) if impls else ""

    def _render_overloaded_wrapper(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
        *,
        caller_unsafe: bool,
    ) -> str:
        shape = specs[0]
        vi = varying_positions(specs)[0]
        arg_trait = (
            f"{_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
        )
        axis_args = "".join(f", {_axis_name(k)}" for k, _ in shape.axis)
        gp_args = "".join(
            f", {name}" for name, _typ, _default in shape.generic_params
        )
        fixed_names = [
            name
            for index, name in enumerate(shape.param_names)
            if index != vi
        ]
        call_args = ", ".join((shape.param_names[vi], *fixed_names))
        call = f"<V as {arg_trait}<S{axis_args}{gp_args}>>::apply({call_args})"
        call = _unsafe_call(call, caller_unsafe)
        doc = _rust_doc(
            shape,
            context="Rust wrapper",
            concrete=False,
            specializations=specs,
        )
        declaration = _rust_overloaded_wrapper_declaration(
            primitive_name,
            specs,
            checked=False,
            caller_unsafe=caller_unsafe,
            reachability=("profile",),
        )
        assert declaration is not None
        return (
            (f"{doc}\n" if doc else "")
            + declaration.render_definition_head()
            + "\n"
            f"    {call}\n"
            f"}}"
        )

    def _render_overloaded_checked_wrapper(
        self,
        primitive_name: str,
        specs: tuple[LoweredSpecialization, ...],
    ) -> str:
        plan = applicable_checked_api_plan(specs)
        if plan is None:
            return ""
        memory = checked_memory_condition(plan.conditions)
        if memory is None:
            raise ValueError("checked Rust overload has no supported memory plan")
        shape = specs[0]
        varying = varying_positions(specs)
        if len(varying) != 1:
            raise ValueError("checked Rust overload requires one varying parameter")
        varying_index = varying[0]
        memory_index, memory_name, memory_access, alignment_axis = (
            memory.parameter_index,
            memory.parameter_name,
            memory.memory_access,
            memory.memory_alignment_axis_name,
        )
        if memory_access is not MemoryAccess.WRITE:
            raise ValueError("checked Rust memory overload currently requires writable memory")
        if alignment_axis is None:
            raise ValueError("checked Rust memory overload has no alignment axis")
        arg_trait = (
            f"{_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}Arg"
        )
        axis_args = "".join(f", {_axis_name(key)}" for key, _ in shape.axis)
        generic_args = "".join(
            f", {name}" for name, _typ, _default in shape.generic_params
        )
        fixed_arguments = tuple(
            (
                f"{name}.as_mut_ptr()" if index == memory_index else name
            )
            for index, name in enumerate(shape.param_names)
            if index != varying_index
        )
        trait_application = f"<V as {arg_trait}<S{axis_args}{generic_args}>>"
        call = (
            f"unsafe {{ {trait_application}::apply("
            f"{shape.param_names[varying_index]}"
            f"{''.join(f', {argument}' for argument in fixed_arguments)}) }}"
        )
        checks: list[str] = []
        for condition in plan.conditions:
            error = _rust_precondition_error(condition.error)
            if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
                checks.extend(
                    (
                        f"    if {memory_name}.len() < "
                        f"{trait_application}::{_CHECKED_MEMORY_EXTENT_METHOD}() {{",
                        f"        return Err({error});",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
                checks.extend(
                    (
                        f"    if {_axis_name(alignment_axis)} && "
                        f"!({memory_name}.as_ptr() as usize).is_multiple_of("
                        f"{trait_application}::{_CHECKED_MEMORY_ALIGNMENT_METHOD}()) {{",
                        f"        return Err({error});",
                        "    }",
                    )
                )
                continue
            raise ValueError(
                f"unsupported checked Rust overload condition {condition.kind.value!r}"
            )
        success = (
            f"    {call};\n    Ok(())"
            if shape.result_kind == "void"
            else f"    Ok({call})"
        )
        body = "\n".join((*checks, success))
        doc = _rust_doc(
            shape,
            context="Rust checked wrapper",
            concrete=False,
            checked_conditions=plan.conditions,
            specializations=specs,
        )
        declaration = _rust_overloaded_wrapper_declaration(
            primitive_name,
            specs,
            checked=True,
            caller_unsafe=False,
            reachability=("profile",),
        )
        assert declaration is not None
        return (
            (f"{doc}\n" if doc else "")
            + declaration.render_attributes()
            + "\n"
            + declaration.render_definition_head()
            + "\n"
            f"{body}\n"
            "}"
        )

    def _trait(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        # Boolean-wildcard axes and an `sImm` immediate become const-generics on the trait,
        # so the `[aligned=*]` variants are distinct impls (`StoreImpl<false>`/`StoreImpl<true>`)
        # and the immediate is a free param (`MulImmImpl<const factor: u32>`).
        decls = _generic_decls(shape)
        ret = _kind_type(shape.result_kind, "Self")
        target_owner: str | None = None
        # A representation-change primitive takes the target vector as a first generic
        # `ToVec`; its result and target-owned parameters project through that vector.
        if shape.target is not None:
            decls = ["ToVec: StaticSimdVector", *decls]
            ret = _kind_type(shape.result_kind, "ToVec")
            target_owner = "ToVec"
        elif shape.result_vector_param is not None:
            ret = _kind_type(shape.result_kind, shape.result_vector_param)
        # Free SIMD type params (gather's `IndicesType`) — a `vidx` param projects through one.
        decls = _type_param_decls(shape) + _type_param_base_key_decls(shape) + decls
        vidx_type = f"{shape.type_params[0].name}::RegisterType" if shape.type_params else None
        params = _params(
            shape,
            "Self",
            target_owner=target_owner,
            vidx_type=vidx_type,
        )
        generics = f"<{', '.join(decls)}>" if decls else ""
        trait_header = (
            f"pub trait {rust_primitive_trait_name(primitive_name)}{generics}: "
            f"StaticSimdVector{_index_where(shape, base_dispatch='hidden')}"
        )
        doc = _rust_doc(shape, context="Rust dispatch trait", concrete=False)
        return (
            (f"{doc}\n" if doc else "")
            + f"{trait_header} {{\n"
            "    const IMPLEMENTATION_STATE: ImplementationState;\n"
            f"{_rust_trait_precondition_declaration(shape)}"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret};\n"
            f"}}"
        )

    def _impl(
        self,
        spec: LoweredSpecialization,
        *,
        caller_unsafe: bool,
        variant_name: str | None = None,
        implementation_trait_variant: str | None = None,
    ) -> str:
        body_ref = _body_for(spec, variant_name)
        if body_ref is None:
            return ""
        # A sized vector's impl is parameterized by its lane const generic; an `sImm` immediate
        # is a further free const generic. A monomorphized slot (numeric `lane_parameter`) is over
        # a concrete `Generic<N>` instead, so it declares no lane generic.
        impl_parts, impl_generic_names = _impl_generic_parts(spec)
        key = self.concrete_vector_type(spec)
        impl_generics = f"<{', '.join(impl_parts)}>" if impl_parts else ""
        targs = _trait_args_by_value(spec)
        ret = _kind_type(spec.result_kind, "Self")
        target_owner: str | None = None
        # The target vector is concrete in the impl's trait args; the result and
        # target-owned parameters project through that concrete vector.
        if spec.target is not None:
            targs = [spec.target.vector_spelling, *targs]
            target_owner = f"<{spec.target.vector_spelling} as SimdVector>"
            ret = _kind_type(spec.result_kind, target_owner)
        elif spec.result_vector_param is not None:
            ret = _kind_type(spec.result_kind, spec.result_vector_param)
        targs = [
            *_type_param_names(spec),
            *_type_param_base_key_args(spec, mode="concrete"),
            *targs,
        ]
        vidx_type = f"{spec.type_params[0].name}::RegisterType" if spec.type_params else None
        params = _params(
            spec,
            "Self",
            target_owner=target_owner,
            vidx_type=vidx_type,
        )
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        # Native index intrinsics take the concrete integer-register type for the selected ISA.
        # Lowering resolves it from source extension metadata; scalar/generic stay opaque.
        impl_register = spec.index_register_spelling
        body_context = RenderContext(
            current_vector=key,
            current_register=spec.register_spelling,
            current_base=spec.base_type_spelling,
            current_mask=f"<{key} as SimdVector>::MaskType",
            current_imask=f"<{key} as SimdVector>::ImaskType",
        )
        concrete_owner = f"<{key} as SimdVector>"
        body = self._target_feature_body(
            spec,
            body_ref,
            render_context=body_context,
            params=_params(
                spec,
                concrete_owner,
                target_owner=target_owner,
                vidx_type=vidx_type,
            ),
            args=_runtime_names(spec),
            return_type=_kind_type(
                spec.result_kind,
                target_owner or spec.result_vector_param or concrete_owner,
            ),
            generic_decls=impl_parts,
            generic_names=impl_generic_names,
            where_clause=_index_where(
                spec,
                impl_register=impl_register,
                base_dispatch="concrete",
            ),
            receiver_type=key,
        )
        doc_context = (
            "Rust specialization"
            if variant_name is None
            else f"Rust specialization variant {variant_name}"
        )
        doc = _rust_doc(spec, context=doc_context)
        trait_name = _implementation_trait_name(
            spec.primitive_name,
            implementation_trait_variant
            if implementation_trait_variant is not None
            else variant_name,
        )
        preconditions = (
            _rust_immediate_precondition(spec)
            + _rust_arithmetic_preconditions(spec)
        )
        return (
            (f"{doc}\n" if doc else "")
            + f"impl{impl_generics} {trait_name}"
            + f"{trait_args} for {key}"
            f"{_index_where(spec, impl_register=impl_register, base_dispatch='concrete')} {{\n"
            f"    const IMPLEMENTATION_STATE: ImplementationState = "
            f"{_rust_implementation_state(_spec_implementation_state(spec, variant_name))};\n"
            f"{_rust_impl_precondition_method(spec)}"
            f"{_indent(_implementation_lint_allowance(spec), 4)}\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {ret} {{\n"
            f"{preconditions}"
            f"{_indent(body, 8)}\n"
            f"    }}\n"
            f"}}"
        )

    def _selection_for(
        self,
        spec: LoweredSpecialization,
    ) -> RustPolicySelection | None:
        if self._policy_selection is None:
            return None
        return next(
            (
                selection
                for selection in self._policy_selection.selections
                if selection.specialization == spec
            ),
            None,
        )

    def _selection_impl(
        self,
        selection: RustPolicySelection,
        *,
        caller_unsafe: bool,
    ) -> str:
        spec = selection.specialization
        reason = rust_policy_selection_shape_reason(selection.key, spec)
        if reason is not None:
            raise ValueError(
                f"Rust policy selection renderer received an unsupported shape: {reason}"
            )
        selected_variant = (
            "default"
            if selection.selected_candidate == "default"
            else selection.selected_candidate
        )
        trait_name = _implementation_trait_name(spec.primitive_name)
        selected_trait_name = _implementation_trait_name(
            spec.primitive_name, selected_variant
        )
        key = self.concrete_vector_type(spec)
        params = _params(spec, "Self")
        result = _kind_type(spec.result_kind, "Self")
        call = (
            f"<Self as {selected_trait_name}>::apply({_runtime_names(spec)})"
        )
        call = _unsafe_call(call, caller_unsafe)
        return (
            f"impl {trait_name} for {key} {{\n"
            f"    const IMPLEMENTATION_STATE: ImplementationState = "
            f"<Self as {selected_trait_name}>::IMPLEMENTATION_STATE;\n"
            f"{_rust_forwarded_precondition_method(spec, selected_trait_name)}"
            "    #[inline(always)]\n"
            f"    {_unsafe_prefix(caller_unsafe)}fn apply({params}) -> {result} {{\n"
            f"        {call}\n"
            "    }\n"
            "}"
        )

    def _wrapper(
        self,
        primitive_name: str,
        shape: LoweredSpecialization,
        *,
        caller_unsafe: bool,
    ) -> str:
        names = _runtime_names(shape)
        # `S` comes first, then the const-generic axis/immediate params — the same turbofish
        # order as the overloaded wrapper (`S, ALIGNED, V`), so a call site can spell
        # `name::<Self, …>` uniformly. The trait bound carries them (`S: MulImmImpl<factor>`);
        # Rust allows referencing a const-generic in the bound before it is declared.
        targs = _trait_args_by_name(shape)
        # A representation-change primitive takes the target vector `T` as a generic, bounds `S`
        # on `…Impl<T, …>`, and projects the result and target-owned parameters through `T`;
        # the call is qualified to pin the target.
        if shape.target is not None:
            targs = ["T", *targs]
        # Free SIMD type params: declare them (bounded) and pass them as trait args. The call is
        # qualified — `IndicesType::RegisterType` is non-injective, so it can't be inferred from
        # the `vidx` argument; pinning `IndicesType` in the trait path resolves `apply`.
        if shape.type_params:
            targs = [
                *_type_param_names(shape),
                *_type_param_base_key_args(shape, mode="projection"),
                *targs,
            ]
        trait_args = f"<{', '.join(targs)}>" if targs else ""
        call = (
            f"<S as {_PRIMITIVE_TRAIT_PREFIX}{rust_primitive_trait_name(primitive_name)}"
            f"{trait_args}>::apply({names})"
        )
        call = _unsafe_call(call, caller_unsafe)
        doc = _rust_doc(shape, context="Rust wrapper", concrete=False)
        declaration = _rust_wrapper_declaration(
            primitive_name,
            shape,
            caller_unsafe=caller_unsafe,
            reachability=("profile",),
        )
        return (
            (f"{doc}\n" if doc else "")
            + declaration.render_definition_head()
            + "\n"
            f"    {call}\n"
            f"}}"
        )

    def _checked_wrapper(
        self,
        primitive_name: str,
        specializations: tuple[LoweredSpecialization, ...],
    ) -> str:
        plan = applicable_checked_api_plan(specializations)
        if plan is None:
            return ""
        shape = specializations[0]
        public_trait_args = _trait_args_by_name(shape)
        trait_args = list(public_trait_args)
        target_owner: str | None = shape.result_vector_param
        if shape.target is not None:
            trait_args = ["T", *trait_args]
            public_trait_args = ["T", *public_trait_args]
            target_owner = "T"
        if shape.type_params:
            type_names = _type_param_names(shape)
            trait_args = [
                *type_names,
                *_type_param_base_key_args(shape, mode="projection"),
                *trait_args,
            ]
            public_trait_args = [*type_names, *public_trait_args]
        rendered_trait_args = f"<{', '.join(trait_args)}>" if trait_args else ""
        vector_bound = (
            f"{_PRIMITIVE_TRAIT_PREFIX}"
            f"{rust_primitive_trait_name(primitive_name)}{rendered_trait_args}"
        )
        doc = _rust_doc(
            shape,
            context="Rust checked wrapper",
            concrete=False,
            checked_conditions=plan.conditions,
        )
        call = (
            f"unsafe {{ {rust_raw_identifier(primitive_name)}"
            f"::<{', '.join(('S', *public_trait_args))}>"
            f"({_checked_runtime_names(shape, plan)}) }}"
        )
        checks: list[str] = []
        for condition in plan.conditions:
            if condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
                checks.extend(
                    (
                        f"    if {condition.parameter_name} >= S::lane_count() {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.EQUAL_LANE_COUNT:
                if target_owner is None:
                    raise ValueError(
                        "Rust equal-lane-count check has no target vector type"
                    )
                checks.extend(
                    (
                        f"    if S::lane_count() != {target_owner}::lane_count() {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
                args = _rust_precondition_method_parameters(
                    shape, condition, owner="S", arguments=True
                )
                checks.extend(
                    (
                        f"    if let Some(error) = <S as {vector_bound}>::"
                        f"{_PRECONDITION_METHOD}({args}) {{",
                        "        return Err(error);",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
                extent = _rust_checked_memory_extent(
                    condition, "S", target_owner=target_owner
                )
                checks.extend(
                    (
                        f"    if {condition.parameter_name}.len() < {extent} {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
                alignment, axis = _rust_checked_memory_alignment(condition, "S")
                active_guard = ""
                if condition.memory_addressing is MemoryAddressing.COMPACTED:
                    if condition.mask_parameter_name is None:
                        raise ValueError(
                            "Rust checked compacted alignment has no mask binding"
                        )
                    active_guard = (
                        f"(0..S::lane_count()).any(|__tsl_lane| "
                        f"S::mask_lane_test({condition.mask_parameter_name}, "
                        "__tsl_lane)) && "
                    )
                checks.extend(
                    (
                        f"    if {axis} && {active_guard}!({condition.parameter_name}.as_ptr() as usize)"
                        f".is_multiple_of({alignment}) {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.INDEXED_MEMORY_ADDRESS_VALID:
                if (
                    condition.index_parameter_name is None
                    or condition.scale_parameter_name is None
                    or condition.memory_indexed_lane_extent is None
                ):
                    raise ValueError("Rust checked indexed memory plan is incomplete")
                if (
                    PreconditionCheckPrimitive.VECTOR_EXTRACT_LANE
                    not in condition.check_primitives
                ):
                    raise ValueError(
                        "indexed-memory check plan has no lane-extraction primitive"
                    )
                if len(shape.type_params) != 1:
                    raise ValueError(
                        "Rust checked indexed memory requires exactly one index vector type"
                    )
                index_owner = shape.type_params[0].name
                if (
                    condition.memory_indexed_lane_extent
                    is MemoryIndexedLaneExtent.VECTOR
                ):
                    invalid_lane_extent = (
                        f"{index_owner}::lane_count() < S::lane_count()"
                    )
                    accessed_lanes = "S::lane_count()"
                elif (
                    condition.memory_indexed_lane_extent
                    is MemoryIndexedLaneExtent.INDEX_VECTOR
                ):
                    invalid_lane_extent = (
                        f"{index_owner}::lane_count() > S::lane_count()"
                    )
                    accessed_lanes = f"{index_owner}::lane_count()"
                else:  # pragma: no cover - closed enum, guarded above
                    raise AssertionError("unknown indexed memory lane extent")
                active = (
                    "true"
                    if condition.mask_parameter_name is None
                    else f"S::mask_lane_test({condition.mask_parameter_name}, __tsl_lane)"
                )
                checks.extend(
                    (
                        f"    if {invalid_lane_extent} {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                        f"    for __tsl_lane in 0..{accessed_lanes} {{",
                        f"        if {active} {{",
                        f"            let __tsl_index = unsafe {{ "
                        f"extract_value_at::<{index_owner}>("
                        f"{condition.index_parameter_name}, __tsl_lane) }};",
                        "            if let Some(error) = "
                        "indexed_memory_address_error::<_, S::BaseType>(",
                        "                __tsl_index, "
                        f"{condition.scale_parameter_name}, "
                        f"{condition.parameter_name}.len(),",
                        "            ) {",
                        "                return Err(error);",
                        "            }",
                        "        }",
                        "    }",
                    )
                )
                continue
            if condition.kind is PreconditionKind.COMPACTED_MEMORY_EXTENT:
                if condition.mask_parameter_name is None:
                    raise ValueError("Rust checked compacted memory plan has no mask")
                if (
                    PreconditionCheckPrimitive.MASK_POPULATION_COUNT
                    not in condition.check_primitives
                ):
                    raise ValueError(
                        "compacted-memory check plan has no mask population primitive"
                    )
                checks.extend(
                    (
                        "    let mut __tsl_required = 0usize;",
                        "    for __tsl_lane in 0..S::lane_count() {",
                        f"        if S::mask_lane_test({condition.mask_parameter_name}, __tsl_lane) {{",
                        "            __tsl_required += 1;",
                        "        }",
                        "    }",
                        f"    if {condition.parameter_name}.len() < __tsl_required {{",
                        f"        return Err({_rust_precondition_error(condition.error)});",
                        "    }",
                    )
                )
                continue
            raise ValueError(
                f"unsupported Rust checked condition {condition.kind.value!r}"
            )
        success = (
            f"    {call};\n    Ok(())"
            if shape.result_kind == "void"
            else f"    Ok({call})"
        )
        body = "\n".join((*checks, success))
        declaration = _rust_checked_wrapper_declaration(
            primitive_name,
            specializations,
            reachability=("profile",),
        )
        assert declaration is not None
        return (
            (f"{doc}\n" if doc else "")
            + declaration.render_attributes()
            + "\n"
            + declaration.render_definition_head()
            + "\n"
            f"{body}\n"
            "}"
        )

    def _target_feature_body(
        self,
        spec: LoweredSpecialization,
        body: LoweredBody,
        *,
        render_context: RenderContext | None = None,
        params: str,
        args: str,
        return_type: str,
        generic_decls: list[str] | tuple[str, ...] = (),
        generic_names: list[str] | tuple[str, ...] = (),
        where_clause: str = "",
        receiver_type: str | None = None,
    ) -> str:
        attrs = self._target_feature_attrs(spec)
        active_context = render_context or RenderContext()
        if attrs and receiver_type is not None:
            active_context = replace(
                active_context,
                current_owner=f"<{receiver_type} as SimdVector>",
            )
        rendered_body = body.render(active_context)
        if not attrs:
            return rendered_body
        decls = f"<{', '.join(generic_decls)}>" if generic_decls else ""
        call_generics = f"::<{', '.join(generic_names)}>" if generic_names else ""
        attr_lines = "\n".join(attrs)
        return (
            f"{attr_lines}\n"
            f"unsafe fn __tsl_target_feature_body{decls}({params}) -> {return_type}"
            f"{where_clause} {{\n"
            f"{_indent(rendered_body, 4)}\n"
            f"}}\n"
            f"unsafe {{ __tsl_target_feature_body{call_generics}({args}) }}"
        )

    def _target_feature_attrs(self, spec: LoweredSpecialization) -> tuple[str, ...]:
        if not self._emit_target_features or not spec.required_features:
            return ()
        return tuple(
            f'#[target_feature(enable = "{self._feature_spellings.get(feature, feature)}")]'
            for feature in sorted(spec.required_features)
        )
