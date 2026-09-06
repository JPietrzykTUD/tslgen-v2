"""Documentation render facts for lowered Rust primitives."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.primitive_rendering import (
    family_runtime_parameter_descriptions,
    family_runtime_parameter_summary,
    runtime_parameter_summary,
)
from tslc.backend.precondition_error_rendering import rust_precondition_error
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
from tslc.catalog.memory import MemoryAccess, MemoryAddressing
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
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


def rust_doc(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool = True,
    checked: bool = False,
    specializations: tuple[LoweredSpecialization, ...] = (),
) -> str:
    rendered = render_rust_doc(
        _doc_block(
            spec,
            context=context,
            concrete=concrete,
            checked=checked,
            specializations=specializations or (spec,),
        )
    )
    preconditions = _documented_preconditions(spec, concrete=concrete)
    if concrete or not preconditions:
        return rendered
    detail = precondition_fact(
        preconditions,
        include_unchecked_consequence=not checked,
    )
    section = (
        "/// # Errors\n"
        "///\n"
        f"/// {_rust_checked_error_facts(preconditions)} The unchecked operation "
        "is not invoked."
        if checked
        else "/// # Safety\n///\n/// " + detail
    )
    return f"{rendered}\n///\n{section}" if rendered else section


def _rust_checked_error_facts(
    preconditions: tuple[PrimitivePrecondition, ...],
) -> str:
    return " ".join(
        f"Returns {_rust_error_names(descriptor.errors)} when this precondition "
        f"is violated: {descriptor.description}"
        for descriptor in (
            PRECONDITION_DESCRIPTORS[item.kind] for item in preconditions
        )
    )


def _rust_error_names(errors: tuple[PreconditionErrorKind, ...]) -> str:
    return ", ".join(f"`{_rust_error_name(error)}`" for error in errors)


def _rust_error_name(error: PreconditionErrorKind) -> str:
    return rust_precondition_error(error)


def _parameter_summary(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    checked: bool,
) -> str:
    spec = specializations[0]
    memory = spec.primitive_semantics.memory
    if not checked or memory is None:
        return family_runtime_parameter_summary(specializations)
    memory_indexes = {
        binding.parameter_index
        for condition in spec.primitive_semantics.preconditions
        for binding in condition.operand_bindings
        if binding.parameter_index < len(spec.param_kinds)
        and spec.param_kinds[binding.parameter_index] in {"cptr", "ptr"}
    }
    return "; ".join(
        f"{name}: "
        + (
            _memory_parameter_description(memory.addressing, read_only=True)
            if index in memory_indexes and memory.access is MemoryAccess.READ
            else _memory_parameter_description(memory.addressing, read_only=False)
            if index in memory_indexes
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
    checked: bool,
    specializations: tuple[LoweredSpecialization, ...],
) -> DocumentationBlock:
    if not concrete:
        preconditions = precondition_fact(
            _documented_preconditions(spec, concrete=concrete),
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
                    _parameter_summary(specializations, checked=checked),
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
    params = ["S selects the SIMD vector type"]
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
    return "; ".join(params)


def _result_summary(spec: LoweredSpecialization, *, concrete: bool) -> str:
    if DEFAULT_SUPPORT_POLICY.is_free_function_signature(
        spec.result_kind,
        spec.param_kinds,
    ):
        return result_summary(
            spec.result_kind,
            _inline_code(rust_free_type(spec.result_kind, spec.base_type_spelling)),
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
