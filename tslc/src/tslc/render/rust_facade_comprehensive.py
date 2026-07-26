"""Render comprehensive Rust facade items from finalized planner records."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_api_arms import (
    RustComprehensivePrivateImplementationArm,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustFacadeConstParameter,
    RustFacadeConstParameterSource,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeShape,
)
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.documentation import documentation_block, render_rust_doc
from tslc.render.rust_facade_common import (
    arm_selection_cfg,
    cfg_attribute,
    lower_call_expression,
)


@dataclass(frozen=True, slots=True)
class RustComprehensiveRendering:
    private_traits: str
    private_impls: str
    public_items: str


def render_comprehensive_facade(
    plan: RustFacadePlan,
) -> RustComprehensiveRendering:
    methods = plan.comprehensive_methods
    return RustComprehensiveRendering(
        private_traits="\n\n".join(_private_trait(method) for method in methods),
        private_impls="\n\n".join(
            block
            for method in methods
            for block in _private_impls(method)
        ),
        public_items="\n\n".join(
            block
            for method in methods
            for block in _public_items(plan, method)
        ),
    )


def _private_trait(method: RustComprehensiveMethod) -> str:
    trait_name = _private_trait_name(method)
    target = _target_type_parameter(method)
    generic_parts = (
        ([target] if target is not None else [])
        + ["const N: usize"]
        + [
            f"const {parameter.public_name}: {parameter.type_spelling}"
            for parameter in _identity_const_parameters(method)
        ]
    )
    where_clause = (
        "\n    where\n        U: Representation<N>,"
        if target is not None
        else ""
    )
    runtime_parameters = _runtime_parameters(method)
    target_owner = "U" if target is not None else "Self"
    parameters = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        + RUST_FACADE_SIGNATURE_TYPES.private_trait_type(
            parameter.kind,
            owner="Self",
            target_owner="Self",
            lanes="N",
        )
        for parameter in runtime_parameters
    )
    const_generics = _const_generic_declarations(method)
    return_type = RUST_FACADE_SIGNATURE_TYPES.private_trait_type(
        method.result_kind,
        owner="Self",
        target_owner=target_owner,
        lanes="N",
    )
    return_suffix = "" if method.result_kind == "void" else f" -> {return_type}"
    unsafe_prefix = "unsafe " if method.caller_unsafe else ""
    return "\n".join(
        (
            f"pub trait {trait_name}<{', '.join(generic_parts)}>: Representation<N>"
            f"{where_clause}",
            "{",
            (
                f"    {unsafe_prefix}fn call{const_generics}"
                f"({parameters}){return_suffix};"
            ),
            "}",
        )
    )


def _private_impls(
    method: RustComprehensiveMethod,
) -> tuple[str, ...]:
    return tuple(
        _private_impl(method, arm)
        for arm in method.implementation_arms
    )


def _private_impl(
    method: RustComprehensiveMethod,
    arm: RustComprehensivePrivateImplementationArm,
) -> str:
    source_shape = arm.source_shape
    target_shape = arm.target_shape
    trait_name = _private_trait_name(method)
    trait_argument_parts = [
        *((target_shape.base_spelling,) if target_shape is not None else ()),
        str(source_shape.lanes),
        *(value for _name, value in arm.attribute_values),
    ]
    trait_arguments = ", ".join(trait_argument_parts)
    runtime_parameters = _runtime_parameters(method)
    parameters = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        + RUST_FACADE_SIGNATURE_TYPES.private_impl_type(
            parameter.kind,
            owner="Self",
            lanes=source_shape.lanes,
        )
        for parameter in runtime_parameters
    )
    const_generics = _const_generic_declarations(method)
    return_type = RUST_FACADE_SIGNATURE_TYPES.private_impl_type(
        method.result_kind,
        owner=target_shape.base_spelling if target_shape else "Self",
        lanes=source_shape.lanes,
    )
    return_suffix = "" if method.result_kind == "void" else f" -> {return_type}"
    call = lower_call_expression(
        arm.call,
        include_result_suffix=False,
    )
    if method.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    result = f"{call}{arm.call.result_suffix}"
    unsafe_prefix = "unsafe " if method.caller_unsafe else ""
    body_lines = []
    if method.caller_unsafe:
        body_lines.append(
            "        // SAFETY: forwarded from the public facade caller contract."
        )
    body_lines.append(f"        {result}")
    return "\n".join(
        (
            cfg_attribute(arm_selection_cfg(arm.selection)),
            (
                f"impl private::{trait_name}<{trait_arguments}> "
                f"for {source_shape.base_spelling} {{"
            ),
            (
                f"    {unsafe_prefix}fn call{const_generics}"
                f"({parameters}){return_suffix} {{"
            ),
            *body_lines,
            "    }",
            "}",
        )
    )


def _public_items(
    _plan: RustFacadePlan,
    method: RustComprehensiveMethod,
) -> tuple[str, ...]:
    if method.receiver_kind is RustFacadeReceiverKind.FREE:
        return (_public_free_function(method),)
    return tuple(
        _public_inherent_method(method, shape)
        for shape in method.public_shapes
    )


def _public_inherent_method(
    method: RustComprehensiveMethod,
    shape: RustFacadeShape,
) -> str:
    owner = (
        f"Simd<{shape.base_spelling}, {shape.lanes}>"
        if method.receiver_kind is RustFacadeReceiverKind.VECTOR
        else f"Mask<{shape.base_spelling}, {shape.lanes}>"
    )
    runtime_parameters = tuple(
        parameter
        for parameter in _runtime_parameters(method)
        if parameter.placement is not RustFacadeParameterPlacement.RECEIVER
    )
    parameter_declarations = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        + RUST_FACADE_SIGNATURE_TYPES.public_type(
            parameter.kind,
            element=shape.base_spelling,
            lanes=str(shape.lanes),
            result_element=shape.base_spelling,
        )
        for parameter in runtime_parameters
    )
    signature_parameters = (
        f"self, {parameter_declarations}" if parameter_declarations else "self"
    )
    target = _target_type_parameter(method)
    type_generics = [target] if target is not None else []
    generic_declarations = _public_generic_declarations(method, type_generics)
    return_type = RUST_FACADE_SIGNATURE_TYPES.public_type(
        method.result_kind,
        element=shape.base_spelling,
        lanes=str(shape.lanes),
        result_element="U" if target is not None else shape.base_spelling,
    )
    trait_name = _private_trait_name(method)
    trait_arguments = ", ".join(
        (
            *(("U",) if target is not None else ()),
            str(shape.lanes),
            *(
                parameter.public_name
                for parameter in _identity_const_parameters(method)
            ),
        )
    )
    needs_private_bound = target is not None or bool(
        _identity_const_parameters(method)
    )
    where_lines = (
        (
            *(
                (f"        U: SupportedSimd<{shape.lanes}>,",)
                if target is not None
                else ()
            ),
            (
                f"        {shape.base_spelling}: "
                f"private::{trait_name}<{trait_arguments}>,"
            ),
        )
        if needs_private_bound
        else ()
    )
    call_args = ", ".join(_public_call_arguments(method))
    call = (
        f"<{shape.base_spelling} as private::{trait_name}<{trait_arguments}>>::"
        f"call{_const_generic_arguments(method)}({call_args})"
    )
    call = _unsafe_forward(method, call)
    result = RUST_FACADE_SIGNATURE_TYPES.adapt_public_result(
        method.result_kind,
        call,
        target_element="U" if target is not None else None,
    )
    body = [
        *_bounds_checks(method, str(shape.lanes)),
        *((
            "        // SAFETY: upheld by this method's caller contract.",
        ) if method.caller_unsafe else ()),
        f"        {result}",
    ]
    attributes = _public_attributes(
        method, has_private_bound=needs_private_bound
    )
    signature = (
        f"    pub {'unsafe ' if method.caller_unsafe else ''}fn "
        f"{rust_raw_identifier(method.public_name)}{generic_declarations}"
        f"({signature_parameters})"
        f"{'' if method.result_kind == 'void' else f' -> {return_type}'}"
    )
    return "\n".join(
        (
            f"impl {owner} {{",
            _indent(_method_docs(method, shape.base_spelling, str(shape.lanes)), 4),
            *attributes,
            signature,
            *(("    where", *where_lines) if where_lines else ()),
            "    {",
            *body,
            "    }",
            "}",
        )
    )


def _public_free_function(method: RustComprehensiveMethod) -> str:
    runtime_parameters = _runtime_parameters(method)
    parameter_declarations = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        + RUST_FACADE_SIGNATURE_TYPES.public_type(
            parameter.kind,
            element="T",
            lanes="N",
            result_element="T",
        )
        for parameter in runtime_parameters
    )
    target = _target_type_parameter(method)
    type_generics = ["T", *(("U",) if target is not None else ())]
    generic_declarations = _public_generic_declarations(
        method, [*type_generics, "const N: usize"]
    )
    return_type = RUST_FACADE_SIGNATURE_TYPES.public_type(
        method.result_kind,
        element="T",
        lanes="N",
        result_element="U" if target is not None else "T",
    )
    trait_name = _private_trait_name(method)
    trait_arguments = ", ".join(
        (
            *(("U",) if target is not None else ()),
            "N",
            *(
                parameter.public_name
                for parameter in _identity_const_parameters(method)
            ),
        )
    )
    where_lines = [
        "    T: SupportedSimd<N>",
        f"        + private::{trait_name}<{trait_arguments}>,",
    ]
    if target is not None:
        where_lines.append("    U: SupportedSimd<N>,")
    call = (
        f"<T as private::{trait_name}<{trait_arguments}>>::"
        f"call{_const_generic_arguments(method)}"
        f"({', '.join(_public_call_arguments(method))})"
    )
    call = _unsafe_forward(method, call)
    result = RUST_FACADE_SIGNATURE_TYPES.adapt_public_result(
        method.result_kind,
        call,
        target_element="U" if target is not None else None,
    )
    body = [
        *_bounds_checks(method, "N"),
        *((
            "    // SAFETY: upheld by this function's caller contract.",
        ) if method.caller_unsafe else ()),
        f"    {result}",
    ]
    return "\n".join(
        (
            _method_docs(method, "T", "N"),
            *(
                line.removeprefix("    ")
                for line in _public_attributes(method, has_private_bound=True)
            ),
            (
                f"pub {'unsafe ' if method.caller_unsafe else ''}fn "
                f"{rust_raw_identifier(method.public_name)}{generic_declarations}"
                f"({parameter_declarations})"
                f"{'' if method.result_kind == 'void' else f' -> {return_type}'}"
            ),
            "where",
            *where_lines,
            "{",
            *body,
            "}",
        )
    )


def _method_docs(
    method: RustComprehensiveMethod,
    element: str,
    lanes: str,
) -> str:
    receiver = {
        RustFacadeReceiverKind.VECTOR: f"`Simd<{element}, {lanes}>`",
        RustFacadeReceiverKind.MASK: f"`Mask<{element}, {lanes}>`",
        RustFacadeReceiverKind.FREE: "free function",
    }[method.receiver_kind]
    rendered = render_rust_doc(
        documentation_block(
            method.documentation,
            facts=(
                ("Rust receiver", receiver),
                (
                    "Rust result",
                    (
                        "`"
                        + RUST_FACADE_SIGNATURE_TYPES.public_type(
                            method.result_kind,
                            element=element,
                            lanes=lanes,
                            result_element=(
                                "U" if method.type_parameters else element
                            ),
                        )
                        + "`"
                    ),
                ),
            ),
            facts_title="Rust API",
        )
    )
    lines = rendered.splitlines() if rendered else [
        f"/// Calls the source `{method.source_primitive_name}` primitive."
    ]
    call_form = _example_call(method)
    lines.extend(("///", "/// # Examples", "/// ```ignore", f"/// {call_form}", "/// ```"))
    if method.panic_conditions:
        lines.extend(("///", "/// # Panics", "///"))
        lines.extend(f"/// {condition}" for condition in method.panic_conditions)
    if method.caller_unsafe:
        lines.extend(("///", "/// # Safety", "///"))
        lines.extend(
            f"/// {requirement}" for requirement in method.safety_requirements
        )
    return "\n".join(lines)


def _example_call(method: RustComprehensiveMethod) -> str:
    const_arguments = [
        "false" if parameter.type_spelling == "bool" else "0"
        for parameter in method.const_parameters
    ]
    arguments = ", ".join(
        _identifier(parameter.public_name)
        for parameter in _runtime_parameters(method)
        if parameter.placement is not RustFacadeParameterPlacement.RECEIVER
    )
    if method.receiver_kind is RustFacadeReceiverKind.FREE:
        generic_arguments = [
            "i32",
            *(("f32",) if method.type_parameters else ()),
            "4",
            *const_arguments,
        ]
        call = (
            f"tsl::{rust_raw_identifier(method.public_name)}"
            f"::<{', '.join(generic_arguments)}>({arguments})"
        )
    else:
        generic_arguments = [
            *(("f32",) if method.type_parameters else ()),
            *const_arguments,
        ]
        generic = (
            f"::<{', '.join(generic_arguments)}>" if generic_arguments else ""
        )
        call = (
            f"value.{rust_raw_identifier(method.public_name)}"
            f"{generic}({arguments})"
        )
    if method.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    prefix = "let result = " if method.must_use else ""
    return f"{prefix}{call};"


def _public_attributes(
    method: RustComprehensiveMethod,
    *,
    has_private_bound: bool,
) -> tuple[str, ...]:
    return (
        "    #[inline]",
        *(("    #[must_use]",) if method.must_use else ()),
        *(("    #[track_caller]",) if method.panic_conditions else ()),
        *(
            ("    #[allow(clippy::should_implement_trait)]",)
            if method.suppress_should_implement_trait_lint
            else ()
        ),
        *(("    #[allow(private_bounds)]",) if has_private_bound else ()),
    )


def _bounds_checks(
    method: RustComprehensiveMethod,
    lanes: str,
) -> tuple[str, ...]:
    return tuple(
        (
            f'        assert!({_identifier(name)} < {lanes}, '
            f'"lane index {{}} is out of bounds for {{}} lanes", '
            f"{_identifier(name)}, {lanes});"
        )
        for name in method.bounds_checked_parameters
    )


def _unsafe_forward(method: RustComprehensiveMethod, call: str) -> str:
    return f"unsafe {{ {call} }}" if method.caller_unsafe else call


def _runtime_parameters(
    method: RustComprehensiveMethod,
) -> tuple[RustFacadeParameter, ...]:
    return tuple(
        parameter
        for parameter in method.parameters
        if parameter.placement is not RustFacadeParameterPlacement.CONST_GENERIC
    )


def _target_type_parameter(method: RustComprehensiveMethod) -> str | None:
    if not method.type_parameters:
        return None
    if len(method.type_parameters) != 1:
        raise ValueError("Rust comprehensive methods support one result element type")
    return method.type_parameters[0].public_name


def _const_generic_declarations(method: RustComprehensiveMethod) -> str:
    parameters = _method_const_parameters(method)
    if not parameters:
        return ""
    declarations = ", ".join(
        f"const {parameter.public_name}: {parameter.type_spelling}"
        for parameter in parameters
    )
    return f"<{declarations}>"


def _public_generic_declarations(
    method: RustComprehensiveMethod,
    leading: list[str],
) -> str:
    consts = [
        f"const {parameter.public_name}: {parameter.type_spelling}"
        for parameter in method.const_parameters
    ]
    parts = [*leading, *consts]
    return f"<{', '.join(parts)}>" if parts else ""


def _const_generic_arguments(method: RustComprehensiveMethod) -> str:
    parameters = _method_const_parameters(method)
    if not parameters:
        return ""
    return f"::<{', '.join(item.public_name for item in parameters)}>"


def _identity_const_parameters(
    method: RustComprehensiveMethod,
) -> tuple[RustFacadeConstParameter, ...]:
    return tuple(
        parameter
        for parameter in method.const_parameters
        if parameter.source is RustFacadeConstParameterSource.ATTRIBUTE
    )


def _method_const_parameters(
    method: RustComprehensiveMethod,
) -> tuple[RustFacadeConstParameter, ...]:
    return tuple(
        parameter
        for parameter in method.const_parameters
        if parameter.source is not RustFacadeConstParameterSource.ATTRIBUTE
    )


def _public_call_arguments(method: RustComprehensiveMethod) -> tuple[str, ...]:
    return tuple(
        RUST_FACADE_SIGNATURE_TYPES.adapt_public_argument(
            parameter.kind,
            (
                "self"
                if parameter.placement is RustFacadeParameterPlacement.RECEIVER
                else _identifier(parameter.public_name)
            ),
        )
        for parameter in _runtime_parameters(method)
    )


def _private_trait_name(method: RustComprehensiveMethod) -> str:
    receiver = {
        RustFacadeReceiverKind.VECTOR: "Vector",
        RustFacadeReceiverKind.MASK: "Mask",
        RustFacadeReceiverKind.FREE: "Free",
    }[method.receiver_kind]
    return (
        f"FacadePrimitive{receiver}"
        f"{rust_primitive_tag_name(method.public_name)}"
    )


def _identifier(name: str) -> str:
    if name in {"self", "Self", "crate", "super"}:
        return f"{name.lower()}_value"
    return rust_raw_identifier(name)


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


__all__ = ("RustComprehensiveRendering", "render_comprehensive_facade")
