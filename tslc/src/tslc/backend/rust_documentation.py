"""Documentation render facts for lowered Rust primitives."""

from __future__ import annotations

from tslc.backend.primitive_rendering import runtime_parameter_summary
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
from tslc.documentation import (
    DocumentationBlock,
    documentation_block,
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
) -> str:
    return render_rust_doc(_doc_block(spec, context=context, concrete=concrete))


def _doc_block(
    spec: LoweredSpecialization,
    *,
    context: str,
    concrete: bool,
) -> DocumentationBlock:
    if not concrete:
        return documentation_block(
            spec.documentation,
            facts=(
                ("Type parameters", _type_parameter_summary(spec)),
                ("Returns", _result_summary(spec, concrete=False)),
                ("Parameters", runtime_parameter_summary(spec)),
            ),
            facts_title="API",
        )
    facts = [
        ("Extension", spec.extension_name),
        ("Element type", spec.base_type_spelling),
        ("Register type", spec.register_spelling),
        ("Returns", _result_summary(spec, concrete=True)),
        ("Parameters", runtime_parameter_summary(spec)),
    ]
    if spec.target is not None:
        facts.extend(
            [
                ("Target vector", spec.target.vector_spelling),
                ("Target register", spec.target.register_spelling),
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
            rust_free_type(spec.result_kind, spec.base_type_spelling),
        )
    if concrete:
        return result_summary(spec.result_kind, _concrete_result(spec))
    if spec.target is not None:
        return result_summary(spec.result_kind, "T::RegisterType")
    return result_summary(
        spec.result_kind,
        RUST_SIGNATURE_TYPES.owner_type(spec.result_kind, owner="S"),
    )


def _concrete_result(spec: LoweredSpecialization) -> str:
    return RUST_SIGNATURE_TYPES.concrete_type(
        spec.result_kind,
        base=spec.base_type_spelling,
        register=spec.register_spelling,
        array=f"array_type<{spec.base_type_spelling}, {spec.lane_parameter}>",
    )
