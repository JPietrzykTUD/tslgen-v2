"""Render comprehensive Rust facade items from finalized planner records."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.checked_api import CheckedConditionPlan
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
from tslc.backend.rust_facade_checked import (
    rust_checked_conditions_for_type,
    rust_checked_error_names,
    rust_checked_guards,
    rust_checked_memory_alignment_condition,
    rust_checked_memory_alignment_expression,
    rust_checked_public_call_argument,
)
from tslc.backend.rust_facade_public_declarations import (
    rust_facade_private_trait_name,
    rust_public_free_declaration as _planned_public_free_declaration,
    rust_public_inherent_declaration as _planned_public_inherent_declaration,
)
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
            *(
                (
                    "    #[doc(hidden)]",
                    "    fn __tsl_checked_memory_alignment() -> usize;",
                )
                if rust_checked_memory_alignment_condition(
                    method.checked_conditions
                )
                is not None
                else ()
            ),
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
    memory_condition = rust_checked_memory_alignment_condition(
        method.checked_conditions
    )
    memory_alignment = (
        rust_checked_memory_alignment_expression(memory_condition, arm)
        if memory_condition is not None
        else None
    )
    memory_members = (
        (
            "    #[inline]",
            "    fn __tsl_checked_memory_alignment() -> usize {",
            f"        {memory_alignment}",
            "    }",
        )
        if memory_alignment is not None
        else ()
    )
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
            *memory_members,
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
        return (
            _public_free_function(method),
            *(
                (_public_free_function(method, checked=True),)
                if method.checked_conditions
                else ()
            ),
        )
    return tuple(
        block
        for shape in method.public_shapes
        for block in (
            _public_inherent_method(method, shape),
            *(
                (_public_inherent_method(method, shape, checked=True),)
                if rust_checked_conditions_for_type(
                    method.checked_conditions, shape.type_tag
                )
                else ()
            ),
        )
    )


def _public_inherent_method(
    method: RustComprehensiveMethod,
    shape: RustFacadeShape,
    *,
    checked: bool = False,
) -> str:
    checked_conditions = rust_checked_conditions_for_type(
        method.checked_conditions, shape.type_tag
    )
    shape_caller_unsafe = shape.type_tag in method.caller_unsafe_type_tags
    owner = (
        f"Simd<{shape.base_spelling}, {shape.lanes}>"
        if method.receiver_kind is RustFacadeReceiverKind.VECTOR
        else f"Mask<{shape.base_spelling}, {shape.lanes}>"
    )
    target = _target_type_parameter(method)
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
    call_args = ", ".join(
        _public_call_arguments(
            method,
            checked_conditions=checked_conditions if checked else (),
        )
    )
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
        *(
            rust_checked_guards(
                method,
                checked_conditions,
                shape.base_spelling,
                str(shape.lanes),
                trait_name=trait_name,
                identity_const_names=tuple(
                    parameter.public_name
                    for parameter in _identity_const_parameters(method)
                ),
                indent="        ",
            )
            if checked
            else ()
        ),
        *((
            (
                "        // SAFETY: checked above before forwarding."
                if checked
                else (
                    "        // SAFETY: upheld by this method's caller contract."
                    if shape_caller_unsafe
                    else "        // SAFETY: this lane type has no applicable public precondition."
                )
            ),
        ) if method.caller_unsafe else ()),
        *_public_success_lines(
            result,
            result_kind=method.result_kind,
            checked=checked,
            indent="        ",
        ),
    ]
    declaration = _planned_public_inherent_declaration(
        method, shape, checked=checked
    )
    return "\n".join(
        (
            f"impl {owner} {{",
            _indent(
                _method_docs(
                    method,
                    shape.base_spelling,
                    str(shape.lanes),
                    checked=checked,
                    caller_unsafe=shape_caller_unsafe,
                    checked_conditions=checked_conditions,
                ),
                4,
            ),
            *(_indent(attribute, 4) for attribute in declaration.attributes),
            _indent(declaration.render_definition_head(), 4),
            *body,
            "    }",
            "}",
        )
    )


def _public_free_function(
    method: RustComprehensiveMethod, *, checked: bool = False
) -> str:
    target = _target_type_parameter(method)
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
    call_arguments = _public_call_arguments(
        method,
        checked_conditions=method.checked_conditions if checked else (),
    )
    call = (
        f"<T as private::{trait_name}<{trait_arguments}>>::"
        f"call{_const_generic_arguments(method)}"
        f"({', '.join(call_arguments)})"
    )
    call = _unsafe_forward(method, call)
    result = RUST_FACADE_SIGNATURE_TYPES.adapt_public_result(
        method.result_kind,
        call,
        target_element="U" if target is not None else None,
    )
    body = [
        *(
            rust_checked_guards(
                method,
                method.checked_conditions,
                "T",
                "N",
                trait_name=trait_name,
                identity_const_names=tuple(
                    parameter.public_name
                    for parameter in _identity_const_parameters(method)
                ),
                indent="    ",
            )
            if checked
            else ()
        ),
        *((
            (
                "    // SAFETY: checked above before forwarding."
                if checked
                else "    // SAFETY: upheld by this function's caller contract."
            ),
        ) if method.caller_unsafe else ()),
        *_public_success_lines(
            result,
            result_kind=method.result_kind,
            checked=checked,
            indent="    ",
        ),
    ]
    declaration = _planned_public_free_declaration(method, checked=checked)
    return "\n".join(
        (
            _method_docs(method, "T", "N", checked=checked),
            *declaration.attributes,
            declaration.render_definition_head(),
            *body,
            "}",
        )
    )


def _method_docs(
    method: RustComprehensiveMethod,
    element: str,
    lanes: str,
    *,
    checked: bool = False,
    caller_unsafe: bool | None = None,
    checked_conditions: tuple[CheckedConditionPlan, ...] | None = None,
) -> str:
    if caller_unsafe is None:
        caller_unsafe = method.caller_unsafe
    if checked_conditions is None:
        checked_conditions = method.checked_conditions
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
    call_form = _example_call(
        method,
        checked=checked,
        caller_unsafe=caller_unsafe,
    )
    lines.extend(("///", "/// # Examples", "/// ```ignore", f"/// {call_form}", "/// ```"))
    if method.panic_conditions:
        lines.extend(("///", "/// # Panics", "///"))
        lines.extend(f"/// {condition}" for condition in method.panic_conditions)
    if checked:
        lines.extend(("///", "/// # Errors", "///"))
        lines.extend(
            "/// Returns "
            f"{rust_checked_error_names(condition.errors)} "
            "when this precondition is violated: "
            f"{condition.description}"
            for condition in checked_conditions
        )
    elif caller_unsafe:
        lines.extend(("///", "/// # Safety", "///"))
        lines.extend(
            f"/// {requirement}" for requirement in method.safety_requirements
        )
        lines.extend(
            f"/// {condition.description}"
            for condition in checked_conditions
        )
    return "\n".join(lines)


def _example_call(
    method: RustComprehensiveMethod,
    *,
    checked: bool = False,
    caller_unsafe: bool | None = None,
) -> str:
    if caller_unsafe is None:
        caller_unsafe = method.caller_unsafe
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
            f"tsl::{rust_raw_identifier(method.public_name + ('_checked' if checked else ''))}"
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
            f"value.{rust_raw_identifier(method.public_name + ('_checked' if checked else ''))}"
            f"{generic}({arguments})"
        )
    if caller_unsafe and not checked:
        call = f"unsafe {{ {call} }}"
    prefix = "let result = " if method.must_use else ""
    return f"{prefix}{call};"


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


def _public_call_arguments(
    method: RustComprehensiveMethod,
    *,
    checked_conditions: tuple[CheckedConditionPlan, ...] = (),
) -> tuple[str, ...]:
    return tuple(
        rust_checked_public_call_argument(
            parameter,
            checked_conditions,
            (
                "self"
                if parameter.placement is RustFacadeParameterPlacement.RECEIVER
                else _identifier(parameter.public_name)
            ),
        )
        or RUST_FACADE_SIGNATURE_TYPES.adapt_public_argument(
            parameter.kind,
            (
                "self"
                if parameter.placement is RustFacadeParameterPlacement.RECEIVER
                else _identifier(parameter.public_name)
            ),
        )
        for parameter in _runtime_parameters(method)
    )


def _public_success_lines(
    result: str,
    *,
    result_kind: str,
    checked: bool,
    indent: str,
) -> tuple[str, ...]:
    if not checked:
        return (f"{indent}{result}",)
    if result_kind == "void":
        return (f"{indent}{result};", f"{indent}Ok(())")
    return (f"{indent}Ok({result})",)


def _private_trait_name(method: RustComprehensiveMethod) -> str:
    return rust_facade_private_trait_name(method)


def _identifier(name: str) -> str:
    if name in {"self", "Self", "crate", "super"}:
        return f"{name.lower()}_value"
    return rust_raw_identifier(name)


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


__all__ = ("RustComprehensiveRendering", "render_comprehensive_facade")
