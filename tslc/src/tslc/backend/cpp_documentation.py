"""Documentation render facts for lowered C++ primitives."""

from __future__ import annotations

from tslc.backend.primitive_rendering import runtime_parameter_summary
from tslc.backend.signature_types import CPP_SIGNATURE_TYPES
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PrimitivePrecondition,
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
    checked: bool = False,
) -> str:
    return render_cpp_doc(
        _doc_block(spec, context=context, concrete=concrete, checked=checked),
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
            include_unchecked_consequence=not checked,
        )
        condition_facts = (
            (
                ("Checks", preconditions),
                (
                    "Success",
                    "sets `precondition_error::none` and returns the operation result",
                ),
                (
                    "Failure",
                    f"sets {_cpp_checked_errors(spec.primitive_semantics.preconditions)}, "
                    "returns a fully initialized "
                    "placeholder with no TSL-defined value, and does not invoke "
                    "the unchecked operation",
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
                ("Parameters", runtime_parameter_summary(spec)),
                *condition_facts,
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
    if preconditions := precondition_fact(spec.primitive_semantics.preconditions):
        facts.append(("Caller preconditions", preconditions))
    return documentation_block(
        spec.documentation,
        facts=tuple(facts),
        facts_title="Specialization",
    )


def _cpp_checked_errors(
    preconditions: tuple[PrimitivePrecondition, ...],
) -> str:
    return ", ".join(
        f"`precondition_error::{_cpp_error_name(error)}`"
        for error in sorted(
            {
                PRECONDITION_DESCRIPTORS[item.kind].error
                for item in preconditions
            },
            key=lambda item: item.value,
        )
    )


def _cpp_error_name(error: PreconditionErrorKind) -> str:
    if error is PreconditionErrorKind.INDEX_OUT_OF_BOUNDS:
        return "index_out_of_bounds"
    raise ValueError(f"unsupported C++ precondition error {error.value!r}")


def _template_summary(spec: LoweredSpecialization) -> str:
    params = ["Vec selects the SIMD vector type"]
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
    return "; ".join(params)


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
