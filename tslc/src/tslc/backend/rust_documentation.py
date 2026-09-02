"""Documentation render facts for lowered Rust primitives."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.primitive_rendering import runtime_parameter_summary
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PrimitivePrecondition,
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
) -> str:
    rendered = render_rust_doc(
        _doc_block(spec, context=context, concrete=concrete, checked=checked)
    )
    preconditions = spec.primitive_semantics.preconditions
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
        f"is not invoked. {detail}"
        if checked
        else "/// # Safety\n///\n/// " + detail
    )
    return f"{rendered}\n///\n{section}" if rendered else section


def _rust_checked_error_facts(
    preconditions: tuple[PrimitivePrecondition, ...],
) -> str:
    return " ".join(
        f"Returns `{_rust_error_name(descriptor.error)}` when "
        f"{descriptor.description[:1].lower() + descriptor.description[1:]}"
        for descriptor in (
            PRECONDITION_DESCRIPTORS[item.kind] for item in preconditions
        )
    )


def _rust_error_name(error: PreconditionErrorKind) -> str:
    if error is PreconditionErrorKind.INDEX_OUT_OF_BOUNDS:
        return "PreconditionError::IndexOutOfBounds"
    raise ValueError(f"unsupported Rust precondition error {error.value!r}")


def _doc_block(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool,
    checked: bool,
) -> DocumentationBlock:
    if not concrete:
        preconditions = precondition_fact(
            spec.primitive_semantics.preconditions,
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
                ("Parameters", runtime_parameter_summary(spec)),
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
        if spec.primitive_semantics.preconditions
        else spec.safety
    )
    facts.append(("Safety", safety_fact(documented_safety)))
    if preconditions := precondition_fact(spec.primitive_semantics.preconditions):
        facts.append(("Caller preconditions", preconditions))
    return documentation_block(
        spec.documentation,
        facts=tuple(facts),
        facts_title="Specialization",
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
