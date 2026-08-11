"""Rust direct free functions, variants, and implementation wrappers."""

from __future__ import annotations

from typing import Protocol

from tslc.backend.primitive_rendering import body_for
from tslc.backend.rust_documentation import rust_doc
from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.backend.rust_signatures import free_kind_type, runtime_names, unsafe_prefix
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import LoweredSpecialization
from tslc.target_text import LoweredBody


class TargetFeatureBodyRenderer(Protocol):
    def _target_feature_body(
        self,
        spec: LoweredSpecialization,
        body: LoweredBody,
        *,
        params: str,
        args: str,
        return_type: str,
    ) -> str: ...


def free_function(
    spec: LoweredSpecialization,
    *,
    backend: TargetFeatureBodyRenderer,
) -> str:
    rendered_params = ", ".join(
        f"{name}: {free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    result_type = (
        "()"
        if spec.result_kind == "void"
        else free_kind_type(spec.result_kind, spec)
    )
    result_clause = "" if result_type == "()" else f" -> {result_type}"
    function_name = rust_raw_identifier(spec.primitive_name)
    rendered_body = backend._target_feature_body(
        spec,
        spec.body,
        params=rendered_params,
        args=runtime_names(spec),
        return_type=result_type,
    )
    doc = rust_doc(spec, context="Rust free function")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(spec.safety.caller_unsafe)}fn "
        f"{function_name}({rendered_params}){result_clause} {{\n"
        f"{indent(rendered_body, 4)}\n"
        "}"
    )


def specialization_implementation_state(
    spec: LoweredSpecialization,
    variant_name: str | None,
) -> ImplementationState:
    if variant_name is None:
        return spec.implementation_state
    for variant in spec.variant_bodies:
        if variant.name == variant_name:
            return variant.implementation_state
    return ImplementationState.UNKNOWN


def rust_implementation_state(state: ImplementationState) -> str:
    return {
        ImplementationState.NATIVE: "ImplementationState::Native",
        ImplementationState.COMPOSED: "ImplementationState::Composed",
        ImplementationState.FALLBACK: "ImplementationState::Fallback",
        ImplementationState.UNKNOWN: "ImplementationState::Unknown",
    }[state]


def free_variant_functions(
    specializations: tuple[LoweredSpecialization, ...],
    *,
    backend: TargetFeatureBodyRenderer,
) -> str:
    return "\n\n".join(
        free_function_variant(spec, variant.name, backend=backend)
        for spec in specializations
        for variant in spec.variant_bodies
    )


def free_function_variant(
    spec: LoweredSpecialization,
    variant_name: str,
    *,
    backend: TargetFeatureBodyRenderer,
) -> str:
    body = body_for(spec, variant_name)
    if body is None:
        return ""
    rendered_params = ", ".join(
        f"{name}: {free_kind_type(kind, spec)}"
        for name, kind in zip(spec.param_names, spec.param_kinds)
    )
    result_type = (
        "()"
        if spec.result_kind == "void"
        else free_kind_type(spec.result_kind, spec)
    )
    result_clause = "" if result_type == "()" else f" -> {result_type}"
    function_name = rust_raw_identifier(
        variant_primitive_name(spec.primitive_name, variant_name)
    )
    rendered_body = backend._target_feature_body(
        spec,
        body,
        params=rendered_params,
        args=runtime_names(spec),
        return_type=result_type,
    )
    doc = rust_doc(spec, context=f"Rust free function variant {variant_name}")
    return (
        (f"{doc}\n" if doc else "")
        + f"pub {unsafe_prefix(spec.safety.caller_unsafe)}fn "
        f"{function_name}({rendered_params}){result_clause} {{\n"
        f"{indent(rendered_body, 4)}\n"
        "}"
    )


def variant_primitive_name(
    primitive_name: str, variant_name: str | None = None
) -> str:
    return (
        primitive_name
        if variant_name is None
        else f"{primitive_name}_{variant_name}"
    )


def implementation_trait_name(
    primitive_name: str, variant_name: str | None = None
) -> str:
    return rust_primitive_trait_name(
        variant_primitive_name(primitive_name, variant_name)
    )


def primitive_module(internal: str) -> str:
    return (
        "#[doc(hidden)]\n"
        "pub mod detail {\n"
        "    pub mod primitives {\n"
        "        use super::super::*;\n\n"
        f"{indent(internal, 8)}\n"
        "    }\n"
        "}"
    )


def indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(
        prefix + line if line else line for line in text.splitlines()
    )


def any_caller_unsafe(specs: tuple[LoweredSpecialization, ...]) -> bool:
    return any(spec.safety.caller_unsafe for spec in specs)


def implementation_lint_allowance(spec: LoweredSpecialization) -> str:
    if not spec.required_features:
        return (
            "// Raw implementation text may intentionally ignore signature parameters.\n"
            "#[allow(unused_variables)]"
        )
    return (
        "// Static TSIL specialization can make shared expression grouping,\n"
        "// conservative unsafe framing, and unrolled formulas lint-trivial.\n"
        "// Keep these allowances on the internal implementation boundary.\n"
        "#[allow(\n"
        "    unused_assignments,\n"
        "    unused_comparisons,\n"
        "    unused_mut,\n"
        "    unused_parens,\n"
        "    unused_unsafe,\n"
        "    unused_variables,\n"
        "    clippy::absurd_extreme_comparisons,\n"
        "    clippy::eq_op,\n"
        "    clippy::erasing_op,\n"
        ")]"
    )


__all__ = (
    "any_caller_unsafe",
    "free_function",
    "free_variant_functions",
    "implementation_lint_allowance",
    "implementation_trait_name",
    "indent",
    "primitive_module",
    "rust_implementation_state",
    "specialization_implementation_state",
    "variant_primitive_name",
)
