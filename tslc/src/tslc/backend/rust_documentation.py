"""Documentation render facts for lowered Rust primitives."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.checked_api import (
    CheckedConditionPlan,
    applicable_checked_api_plan,
    checked_memory_condition,
)
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.primitive_rendering import (
    family_runtime_parameter_descriptions,
    family_runtime_parameter_summary,
    runtime_parameter_summary,
)
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
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
    render_rust_doc,
    result_summary,
    safety_fact,
)
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def rust_checked_api_examples(profiles: tuple[EmittedProfile, ...]) -> str:
    """Project overview examples only when their typed primitive is emitted."""

    example_specs = tuple(
        spec
        for profile in profiles
        for spec in profile.specializations("rust").get("extract_value_at", ())
        if spec.type_tag == "si32" and spec.extension_name == "scalar"
    )
    if not example_specs or applicable_checked_api_plan(example_specs) is None:
        return ""
    return """# Examples

The ordinary lower-level path requires the caller to uphold its safety
contract:

```
use tsl::tsl_core::{Scalar, Simd as ProfileSimd};

type V = ProfileSimd<i32, Scalar>;
let lane = unsafe { tsl::profile::extract_value_at::<V>(7, 0) };
if lane != 7 {
    std::process::abort();
}
```

The checked path reports invalid runtime data without invoking the ordinary
operation:

```
use tsl::tsl_core::{Scalar, Simd as ProfileSimd};
use tsl::PreconditionError;

type V = ProfileSimd<i32, Scalar>;
let result = tsl::profile::extract_value_at_checked::<V>(7, 1);
if result != Err(PreconditionError::IndexOutOfBounds) {
    std::process::abort();
}
```"""


def rust_doc(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool = True,
    checked_conditions: tuple[CheckedConditionPlan, ...] | None = None,
    specializations: tuple[LoweredSpecialization, ...] = (),
) -> str:
    rendered = render_rust_doc(
        _doc_block(
            spec,
            context=context,
            concrete=concrete,
            checked_conditions=checked_conditions,
            specializations=specializations or (spec,),
        )
    )
    if concrete:
        return rendered
    if checked_conditions is not None:
        if not checked_conditions:
            return rendered
        section = (
            "/// # Errors\n"
            "///\n"
            f"/// {_rust_checked_error_facts(checked_conditions)} The unchecked operation "
            "is not invoked."
        )
    else:
        preconditions = _documented_preconditions(spec, concrete=concrete)
        if not preconditions:
            return rendered
        section = "/// # Safety\n///\n/// " + precondition_fact(preconditions)
    return f"{rendered}\n///\n{section}" if rendered else section


def _rust_checked_error_facts(
    conditions: tuple[CheckedConditionPlan, ...],
) -> str:
    return " ".join(
        f"Returns {_rust_error_names(condition.errors)} when this precondition "
        f"is violated: {condition.description}"
        for condition in conditions
    )


def _rust_error_names(errors: tuple[PreconditionErrorKind, ...]) -> str:
    return ", ".join(f"`{_rust_error_name(error)}`" for error in errors)


def _rust_error_name(error: PreconditionErrorKind) -> str:
    return rust_precondition_error(error)


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
    access = "shared" if read_only else "exclusive mutable"
    shape = {
        MemoryAddressing.CONTIGUOUS: "contiguous slice",
        MemoryAddressing.INDEXED: "indexed base slice",
        MemoryAddressing.COMPACTED: "compacted-memory slice",
    }[addressing]
    return f"{access} {shape}"


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
            include_unchecked_consequence=False,
        )
        condition_facts = (
            (("Checks", preconditions),)
            if checked and preconditions
            else ()
        )
        return documentation_block(
            spec.documentation,
            facts=(
                ("Type parameters", _type_parameter_summary(spec)),
                ("Returns", _result_summary(spec, concrete=False)),
                (
                    "Parameters",
                    _parameter_summary(
                        specializations,
                        checked_conditions=checked_conditions,
                    ),
                ),
                *condition_facts,
            ),
            facts_title="API",
        )
    facts = [
        ("Extension", spec.extension_name),
        ("Element type", _inline_code(spec.base_type_spelling)),
        ("Register type", _inline_code(spec.register_spelling)),
        ("Returns", _result_summary(spec, concrete=True)),
        ("Parameters", runtime_parameter_summary(spec)),
    ]
    if spec.target is not None:
        facts.extend(
            [
                ("Target vector", _inline_code(spec.target.vector_spelling)),
                ("Target register", _inline_code(spec.target.register_spelling)),
            ]
        )
    if spec.axis:
        facts.append(
            ("Attributes", ", ".join(f"{key}={value}" for key, value in spec.axis))
        )
    if spec.immediate is not None:
        facts.append(
            (
                "Immediate",
                f"{spec.immediate[0]}: {_inline_code(spec.immediate[1])}",
            )
        )
    facts.append(
        (
            "Required target features",
            ", ".join(sorted(spec.required_features))
            if spec.required_features
            else "none",
        )
    )
    documented_safety = (
        replace(spec.safety, caller_unsafe=True)
        if _documented_preconditions(spec, concrete=concrete)
        else spec.safety
    )
    facts.append(("Safety", safety_fact(documented_safety)))
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


def _type_parameter_summary(spec: LoweredSpecialization) -> str:
    params = (
        []
        if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
            spec.result_kind, spec.param_kinds
        )
        else ["S selects the SIMD vector type"]
    )
    if spec.target is not None:
        params.append("T selects the target SIMD vector type")
    params.extend(
        f"{param.name} selects an additional SIMD vector type"
        for param in spec.type_params
    )
    params.extend(f"{key.upper()} selects `{key}`" for key, _ in spec.axis)
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
            _inline_code(
                rust_free_type(
                    spec.result_kind,
                    spec.base_type_spelling,
                    base_type_tag=spec.type_tag,
                )
            ),
        )
    if concrete:
        return result_summary(spec.result_kind, _inline_code(_concrete_result(spec)))
    if spec.target is not None:
        return result_summary(
            spec.result_kind,
            _inline_code(
                RUST_SIGNATURE_TYPES.owner_type(spec.result_kind, owner="T")
            ),
        )
    if spec.result_vector_param is not None:
        return result_summary(
            spec.result_kind,
            _inline_code(
                RUST_SIGNATURE_TYPES.owner_type(
                    spec.result_kind,
                    owner=spec.result_vector_param,
                )
            ),
        )
    return result_summary(
        spec.result_kind,
        _inline_code(RUST_SIGNATURE_TYPES.owner_type(spec.result_kind, owner="S")),
    )


def _concrete_result(spec: LoweredSpecialization) -> str:
    if spec.target is not None:
        return RUST_SIGNATURE_TYPES.owner_type(
            spec.result_kind,
            owner=f"<{spec.target.vector_spelling} as SimdVector>",
        )
    if spec.result_vector_param is not None:
        return RUST_SIGNATURE_TYPES.owner_type(
            spec.result_kind,
            owner=spec.result_vector_param,
        )
    return RUST_SIGNATURE_TYPES.concrete_type(
        spec.result_kind,
        base=spec.base_type_spelling,
        register=spec.register_spelling,
        array=f"array_type<{spec.base_type_spelling}, {spec.lane_parameter}>",
    )


def _inline_code(value: str) -> str:
    """Protect generated Rust type spellings from Markdown HTML parsing."""

    return f"`{value}`"
