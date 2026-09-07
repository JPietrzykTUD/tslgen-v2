"""Documentation render facts for lowered C++ primitives."""

from __future__ import annotations

from tslc.backend.checked_api import (
    CheckedConditionPlan,
    checked_memory_condition,
)
from tslc.backend.primitive_rendering import (
    family_runtime_parameter_descriptions,
    family_runtime_parameter_summary,
    runtime_parameter_summary,
)
from tslc.backend.precondition_error_rendering import cpp_precondition_error
from tslc.backend.primitive_facade import DataparallelPrimitiveFacade
from tslc.backend.signature_types import CPP_SIGNATURE_TYPES
from tslc.catalog.memory import MemoryAccess, MemoryAddressing
from tslc.catalog.preconditions import (
    PreconditionErrorKind,
    PrimitivePrecondition,
    precondition_applies_to_type,
)
from tslc.documentation import (
    DocumentationBlock,
    documentation_block,
    precondition_fact,
    render_cpp_doc,
    result_summary,
    safety_fact,
)
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def cpp_doc(
    spec: LoweredSpecialization,
    *,
    context: str,
    indent: str = "",
    concrete: bool = True,
    checked_conditions: tuple[CheckedConditionPlan, ...] | None = None,
    specializations: tuple[LoweredSpecialization, ...] = (),
) -> str:
    return render_cpp_doc(
        _doc_block(
            spec,
            context=context,
            concrete=concrete,
            checked_conditions=checked_conditions,
            specializations=specializations or (spec,),
        ),
        indent=indent,
    )


def cpp_register_doc(spec: LoweredSpecialization) -> str:
    return _native_register_doc(
        base_spelling=spec.base_type_spelling,
        uses_sized_vector=spec.uses_sized_vector,
        lane_parameter=spec.lane_parameter,
        register_is_base=spec.register_is_base,
        fallback=spec.native_register_spelling or spec.register_spelling,
    )


def cpp_target_register_doc(spec: LoweredSpecialization) -> str:
    if spec.target is None:
        return ""
    return _native_register_doc(
        base_spelling=spec.target.base_spelling,
        uses_sized_vector=spec.target.uses_sized_vector,
        lane_parameter=spec.target.lane_parameter or spec.lane_parameter,
        register_is_base=False,
        fallback=spec.target.native_register_spelling or spec.target.register_spelling,
    )


def cpp_dataparallel_facade_doc(facade: DataparallelPrimitiveFacade) -> str:
    """Document the policy overload as its own public callable identity."""

    shape = facade.shape
    type_parameters = (
        "Policy selects the lane-width policy; FromT selects the source element "
        "type; ToT selects the target element type"
        if shape.target is not None
        else "Policy selects the lane-width policy; T selects the element type"
    )
    return render_cpp_doc(
        DocumentationBlock(
            brief=f"Policy-based overload of `{facade.primitive_name}`.",
            facts=(
                ("Template parameters", type_parameters),
                (
                    "Parameters",
                    _parameter_summary((shape,), checked_conditions=None),
                ),
                (
                    "Dispatch",
                    "Resolves the vector type through `tsl::dataparallel::simd_for_t` "
                    "and delegates to the vector-typed overload",
                ),
            ),
            facts_title="Policy API",
        )
    )


def _doc_block(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool,
    checked_conditions: tuple[CheckedConditionPlan, ...] | None,
    specializations: tuple[LoweredSpecialization, ...],
) -> DocumentationBlock:
    if not concrete:
        checked = checked_conditions is not None
        documented_conditions = (
            checked_conditions
            if checked_conditions is not None
            else _documented_preconditions(spec, concrete=concrete)
        )
        preconditions = precondition_fact(
            documented_conditions,
            include_unchecked_consequence=not checked,
        )
        condition_facts = (
            (
                ("Checks", preconditions),
                (
                    "Success",
                    (
                        "sets `precondition_error::none` and returns the operation result"
                        if spec.result_kind != "void"
                        else "returns `precondition_error::none` after invoking the operation"
                    ),
                ),
                (
                    "Failure",
                    (
                        f"sets {_cpp_checked_errors(checked_conditions or ())}, "
                        "returns a fully initialized placeholder with no TSL-defined "
                        "value, and does not invoke the unchecked operation"
                        if spec.result_kind != "void"
                        else (
                            "returns "
                            f"{_cpp_checked_errors(checked_conditions or ())} "
                            "and does not invoke the unchecked operation"
                        )
                    ),
                ),
            )
            if checked and preconditions
            else (("Caller preconditions", preconditions),)
            if preconditions
            else ()
        )
        return documentation_block(
            spec.documentation,
            facts=(
                ("Template parameters", _template_summary(spec)),
                ("Returns", _result_summary(spec, concrete=False)),
                (
                    "Parameters",
                    _parameter_summary(
                        specializations,
                        checked_conditions=checked_conditions,
                    ),
                ),
                *condition_facts,
                *(
                    (
                        (
                            "Range validity",
                            "The span must denote its declared live, addressable "
                            "element range for the duration of the call; construction "
                            "does not validate that C++ object invariant",
                        ),
                    )
                    if checked and spec.primitive_semantics.memory is not None
                    else ()
                ),
            ),
            facts_title="API",
        )
    facts = [
        ("Extension", spec.extension_name),
        ("Element type", spec.base_type_spelling),
        ("Register type", cpp_register_doc(spec)),
        ("Returns", _result_summary(spec, concrete=True)),
        ("Parameters", runtime_parameter_summary(spec)),
    ]
    if spec.target is not None:
        facts.extend(
            [
                ("Target vector", spec.target.vector_spelling),
                ("Target register", cpp_target_register_doc(spec)),
            ]
        )
    if spec.axis:
        facts.append(
            ("Attributes", ", ".join(f"{key}={value}" for key, value in spec.axis))
        )
    if spec.immediate is not None:
        facts.append(("Immediate", f"{spec.immediate[0]}: {spec.immediate[1]}"))
    facts.append(
        (
            "Required target features",
            ", ".join(sorted(spec.required_features))
            if spec.required_features
            else "none",
        )
    )
    facts.append(("Safety", safety_fact(spec.safety)))
    if preconditions := precondition_fact(
        _documented_preconditions(spec, concrete=concrete)
    ):
        facts.append(("Caller preconditions", preconditions))
    return documentation_block(
        spec.documentation,
        facts=tuple(facts),
        facts_title="Specialization",
    )


def _documented_preconditions(
    spec: LoweredSpecialization,
    *,
    concrete: bool,
) -> tuple[PrimitivePrecondition, ...]:
    preconditions = spec.primitive_semantics.preconditions
    if not concrete:
        return preconditions
    return tuple(
        item
        for item in preconditions
        if precondition_applies_to_type(item, spec.type_tag)
    )


def _cpp_checked_errors(
    conditions: tuple[CheckedConditionPlan, ...],
) -> str:
    return ", ".join(
        f"`precondition_error::{_cpp_error_name(error)}`"
        for error in sorted(
            {
                error
                for condition in conditions
                for error in condition.errors
            },
            key=lambda item: item.value,
        )
    )


def _cpp_error_name(error: PreconditionErrorKind) -> str:
    return cpp_precondition_error(error, qualified=False)


def _parameter_summary(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    checked_conditions: tuple[CheckedConditionPlan, ...] | None,
) -> str:
    spec = specializations[0]
    memory = spec.primitive_semantics.memory
    if checked_conditions is None or memory is None:
        return family_runtime_parameter_summary(specializations)
    checked_memory = checked_memory_condition(checked_conditions)
    if checked_memory is None:
        return family_runtime_parameter_summary(specializations)
    return "; ".join(
        f"{name}: "
        + (
            _memory_parameter_description(memory.addressing, read_only=True)
            if index == checked_memory.parameter_index
            and memory.access is MemoryAccess.READ
            else _memory_parameter_description(memory.addressing, read_only=False)
            if index == checked_memory.parameter_index
            else description
        )
        for index, name, description in family_runtime_parameter_descriptions(
            specializations
        )
    )


def _memory_parameter_description(
    addressing: MemoryAddressing,
    *,
    read_only: bool,
) -> str:
    access = "read-only" if read_only else "writable"
    shape = {
        MemoryAddressing.CONTIGUOUS: "contiguous span",
        MemoryAddressing.INDEXED: "indexed base span",
        MemoryAddressing.COMPACTED: "compacted-memory span",
    }[addressing]
    return f"{access} {shape}"


def _template_summary(spec: LoweredSpecialization) -> str:
    params = (
        []
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            spec.result_kind, spec.param_kinds
        )
        else ["Vec selects the SIMD vector type"]
    )
    if spec.target is not None:
        params.append("ToVec selects the target SIMD vector type")
    params.extend(
        f"{param.name} selects an additional SIMD vector type"
        for param in spec.type_params
    )
    params.extend(
        f"{key[:1].upper() + key[1:]} selects `{key}`" for key, _ in spec.axis
    )
    if spec.immediate is not None:
        params.append(f"{spec.immediate[0]} is a compile-time immediate")
    params.extend(
        f"{name} selects `{name}`" for name, _typ, _default in spec.generic_params
    )
    return "; ".join(params) if params else "none"


def _result_summary(spec: LoweredSpecialization, *, concrete: bool) -> str:
    if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    ):
        return result_summary(
            spec.result_kind,
            CPP_SIGNATURE_TYPES.free_type(
                spec.result_kind,
                base=spec.base_type_spelling,
                base_type_tag=spec.type_tag,
            ),
        )
    if concrete:
        result_type = (
            (
                cpp_target_register_doc(spec)
                if spec.result_kind == "v"
                else CPP_SIGNATURE_TYPES.member_type(
                    spec.result_kind,
                    vector=spec.target.vector_spelling,
                )
            )
            if spec.target is not None
            else CPP_SIGNATURE_TYPES.member_type(
                spec.result_kind,
                vector=spec.result_vector_param,
            )
            if spec.result_vector_param is not None
            else cpp_register_doc(spec)
            if spec.result_kind == "v"
            else CPP_SIGNATURE_TYPES.result_type(spec.result_kind)
        )
        return result_summary(spec.result_kind, result_type)
    if spec.target is not None:
        return result_summary(
            spec.result_kind,
            CPP_SIGNATURE_TYPES.member_type(spec.result_kind, vector="ToVec"),
        )
    if spec.result_vector_param is not None:
        return result_summary(
            spec.result_kind,
            CPP_SIGNATURE_TYPES.member_type(
                spec.result_kind,
                vector=spec.result_vector_param,
            ),
        )
    return result_summary(spec.result_kind, CPP_SIGNATURE_TYPES.result_type(spec.result_kind))


def _native_register_doc(
    *,
    base_spelling: str,
    uses_sized_vector: bool,
    lane_parameter: str | None,
    register_is_base: bool,
    fallback: str,
) -> str:
    if uses_sized_vector:
        return f"::tsl::array_type<{base_spelling}, {lane_parameter}>"
    if register_is_base:
        return base_spelling
    return fallback
