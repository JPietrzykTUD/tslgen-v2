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
    RustFacadeCheckedCondition,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeShape,
)
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.catalog.memory import MemoryAccess, MemoryPayloadExtent
from tslc.catalog.preconditions import (
    PRECONDITION_DESCRIPTORS,
    PreconditionErrorKind,
    PreconditionKind,
)
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
                if _checked_memory_condition(method.checked_conditions) is not None
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
    memory_condition = _checked_memory_condition(method.checked_conditions)
    memory_alignment = (
        _checked_memory_alignment_expression(memory_condition, arm)
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
                if _checked_conditions_for_type(method, shape.type_tag)
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
    checked_conditions = _checked_conditions_for_type(method, shape.type_tag)
    shape_caller_unsafe = shape.type_tag in method.caller_unsafe_type_tags
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
        + _public_parameter_type(
            parameter,
            element=shape.base_spelling,
            lanes=str(shape.lanes),
            checked_conditions=checked_conditions if checked else (),
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
            _checked_guards(
                method,
                checked_conditions,
                shape.base_spelling,
                str(shape.lanes),
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
    attributes = _public_attributes(
        method,
        has_private_bound=needs_private_bound,
        checked=checked,
    )
    rendered_return_type = (
        f"Result<{return_type}, crate::PreconditionError>"
        if checked
        else return_type
    )
    public_name = method.public_name + ("_checked" if checked else "")
    signature = (
        f"    pub {'unsafe ' if shape_caller_unsafe and not checked else ''}fn "
        f"{rust_raw_identifier(public_name)}{generic_declarations}"
        f"({signature_parameters})"
        f"{'' if method.result_kind == 'void' and not checked else f' -> {rendered_return_type}'}"
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
            *attributes,
            signature,
            *(("    where", *where_lines) if where_lines else ()),
            "    {",
            *body,
            "    }",
            "}",
        )
    )


def _public_free_function(
    method: RustComprehensiveMethod, *, checked: bool = False
) -> str:
    runtime_parameters = _runtime_parameters(method)
    parameter_declarations = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        + _public_parameter_type(
            parameter,
            element="T",
            lanes="N",
            checked_conditions=method.checked_conditions if checked else (),
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
            _checked_guards(
                method,
                method.checked_conditions,
                "T",
                "N",
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
    rendered_return_type = (
        f"Result<{return_type}, crate::PreconditionError>"
        if checked
        else return_type
    )
    public_name = method.public_name + ("_checked" if checked else "")
    return "\n".join(
        (
            _method_docs(method, "T", "N", checked=checked),
            *(
                line.removeprefix("    ")
                for line in _public_attributes(
                    method,
                    has_private_bound=True,
                    checked=checked,
                )
            ),
            (
                f"pub {'unsafe ' if method.caller_unsafe and not checked else ''}fn "
                f"{rust_raw_identifier(public_name)}{generic_declarations}"
                f"({parameter_declarations})"
                f"{'' if method.result_kind == 'void' and not checked else f' -> {rendered_return_type}'}"
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
    *,
    checked: bool = False,
    caller_unsafe: bool | None = None,
    checked_conditions: tuple[RustFacadeCheckedCondition, ...] | None = None,
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
            f"`{_facade_precondition_error(condition.error).removeprefix('crate::')}` "
            "when this precondition is violated: "
            f"{PRECONDITION_DESCRIPTORS[condition.kind].description}"
            for condition in checked_conditions
        )
    elif caller_unsafe:
        lines.extend(("///", "/// # Safety", "///"))
        lines.extend(
            f"/// {requirement}" for requirement in method.safety_requirements
        )
        lines.extend(
            f"/// {PRECONDITION_DESCRIPTORS[condition.kind].description}"
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


def _public_attributes(
    method: RustComprehensiveMethod,
    *,
    has_private_bound: bool,
    checked: bool,
) -> tuple[str, ...]:
    return (
        "    #[inline]",
        *(("    #[must_use]",) if method.must_use and not checked else ()),
        *(("    #[track_caller]",) if method.panic_conditions else ()),
        *(
            ("    #[allow(clippy::should_implement_trait)]",)
            if method.suppress_should_implement_trait_lint
            else ()
        ),
        *(("    #[allow(private_bounds)]",) if has_private_bound else ()),
    )


def _checked_guards(
    method: RustComprehensiveMethod,
    conditions: tuple[RustFacadeCheckedCondition, ...],
    element: str,
    lanes: str,
    *,
    indent: str,
) -> tuple[str, ...]:
    guards: list[str] = []
    for condition_index, condition in enumerate(conditions):
        error = _facade_precondition_error(condition.error)
        if condition.kind is PreconditionKind.LANE_INDEX_IN_RANGE:
            parameter = _checked_parameter_expression(
                method, condition.parameter_name
            )
            guards.append(
                f"{indent}if {parameter} >= {lanes} {{"
                f" return Err({error}); }}"
            )
            continue
        if condition.kind is PreconditionKind.ACTIVE_DIVISOR_NONZERO:
            divisor = _checked_parameter_expression(
                method, condition.parameter_name
            )
            divisor_lanes = f"__tsl_checked_divisors_{condition_index}"
            guards.append(f"{indent}let {divisor_lanes} = {divisor}.to_array();")
            if condition.mask_parameter_name is not None:
                mask = _checked_parameter_expression(
                    method, condition.mask_parameter_name
                )
                active_lanes = f"__tsl_checked_active_{condition_index}"
                guards.append(f"{indent}let {active_lanes} = {mask}.to_array();")
                guards.extend(
                    (
                        f"{indent}if {divisor_lanes}.into_iter().enumerate().any(",
                        f"{indent}    |(lane, value)| {active_lanes}[lane] "
                        "&& value == 0,",
                        f"{indent}) {{ return Err({error}); }}",
                    )
                )
            else:
                guards.extend(
                    (
                        f"{indent}if {divisor_lanes}.into_iter().any(",
                        f"{indent}    |value| value == 0,",
                        f"{indent}) {{ return Err({error}); }}",
                    )
                )
            continue
        if condition.kind is PreconditionKind.CONTIGUOUS_MEMORY_EXTENT:
            memory = _checked_parameter_expression(
                method, condition.parameter_name
            )
            required_extent = _checked_memory_extent(condition, lanes)
            invalid_extent = (
                f"{memory}.is_empty()"
                if required_extent == "1"
                else f"{memory}.len() < {required_extent}"
            )
            guards.append(
                f"{indent}if {invalid_extent} {{"
                f" return Err({error}); }}"
            )
            continue
        if condition.kind is PreconditionKind.SELECTED_MEMORY_ALIGNMENT:
            memory = _checked_parameter_expression(
                method, condition.parameter_name
            )
            alignment_parameter = next(
                (
                    parameter.public_name
                    for parameter in method.const_parameters
                    if parameter.source_name
                    == condition.memory_alignment_axis_name
                ),
                None,
            )
            if alignment_parameter is None:
                raise ValueError(
                    "checked Rust facade memory alignment axis is unresolved"
                )
            identity_arguments = "".join(
                f", {parameter.public_name}"
                for parameter in _identity_const_parameters(method)
            )
            guards.append(
                f"{indent}if {alignment_parameter} && "
                f"!({memory}.as_ptr() as usize).is_multiple_of("
                f"<{element} as private::"
                f"{_private_trait_name(method)}<{lanes}"
                f"{identity_arguments}"
                ">>::__tsl_checked_memory_alignment()) {"
                f" return Err({error}); }}"
            )
            continue
        raise ValueError(f"unsupported Rust facade check {condition.kind.value!r}")
    return tuple(guards)


def _checked_conditions_for_type(
    method: RustComprehensiveMethod,
    type_tag: str,
) -> tuple[RustFacadeCheckedCondition, ...]:
    return tuple(
        condition
        for condition in method.checked_conditions
        if type_tag in condition.applicable_type_tags
    )


def _checked_parameter_expression(
    method: RustComprehensiveMethod,
    source_name: str,
) -> str:
    parameter = next(
        (item for item in method.parameters if item.source_name == source_name),
        None,
    )
    if parameter is None:
        raise ValueError(f"checked facade parameter {source_name!r} is unresolved")
    if parameter.placement is RustFacadeParameterPlacement.RECEIVER:
        return "self"
    return _identifier(parameter.public_name)


def _facade_precondition_error(error: PreconditionErrorKind) -> str:
    if error is PreconditionErrorKind.INDEX_OUT_OF_BOUNDS:
        return "crate::PreconditionError::IndexOutOfBounds"
    if error is PreconditionErrorKind.ZERO_DIVISOR:
        return "crate::PreconditionError::ZeroDivisor"
    if error is PreconditionErrorKind.INSUFFICIENT_EXTENT:
        return "crate::PreconditionError::InsufficientExtent"
    if error is PreconditionErrorKind.MISALIGNED:
        return "crate::PreconditionError::Misaligned"
    raise ValueError(f"unsupported Rust facade precondition error {error.value!r}")


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


def _public_call_arguments(
    method: RustComprehensiveMethod,
    *,
    checked_conditions: tuple[RustFacadeCheckedCondition, ...] = (),
) -> tuple[str, ...]:
    memory = _checked_memory_condition(checked_conditions)
    return tuple(
        (
            f"{_identifier(parameter.public_name)}.as_ptr()"
            if memory is not None
            and memory.memory_access is MemoryAccess.READ
            and parameter.source_name == memory.parameter_name
            else f"{_identifier(parameter.public_name)}.as_mut_ptr()"
            if memory is not None
            and parameter.source_name == memory.parameter_name
            else RUST_FACADE_SIGNATURE_TYPES.adapt_public_argument(
                parameter.kind,
                (
                    "self"
                    if parameter.placement is RustFacadeParameterPlacement.RECEIVER
                    else _identifier(parameter.public_name)
                ),
            )
        )
        for parameter in _runtime_parameters(method)
    )


def _public_parameter_type(
    parameter: RustFacadeParameter,
    *,
    element: str,
    lanes: str,
    checked_conditions: tuple[RustFacadeCheckedCondition, ...],
) -> str:
    memory = _checked_memory_condition(checked_conditions)
    if memory is not None and parameter.source_name == memory.parameter_name:
        borrow = "&" if memory.memory_access is MemoryAccess.READ else "&mut "
        return f"{borrow}[{element}]"
    return RUST_FACADE_SIGNATURE_TYPES.public_type(
        parameter.kind,
        element=element,
        lanes=lanes,
        result_element=element,
    )


def _checked_memory_condition(
    conditions: tuple[RustFacadeCheckedCondition, ...],
) -> RustFacadeCheckedCondition | None:
    memory_conditions = tuple(
        condition for condition in conditions if condition.memory_access is not None
    )
    if not memory_conditions:
        return None
    identities = {
        (
            condition.parameter_name,
            condition.memory_access,
            condition.memory_payload_extents,
            condition.memory_alignment_axis_name,
        )
        for condition in memory_conditions
    }
    if len(identities) != 1:
        raise ValueError("checked Rust facade memory conditions disagree")
    return memory_conditions[0]


def _checked_memory_extent(
    condition: RustFacadeCheckedCondition,
    lanes: str,
) -> str:
    if condition.memory_payload_extents == (MemoryPayloadExtent.SCALAR,):
        return "1"
    if condition.memory_payload_extents == (MemoryPayloadExtent.VECTOR,):
        return lanes
    raise ValueError("checked Rust facade requires one memory payload extent")


def _checked_memory_alignment_expression(
    condition: RustFacadeCheckedCondition,
    arm: RustComprehensivePrivateImplementationArm,
) -> str:
    if condition.memory_payload_extents == (MemoryPayloadExtent.SCALAR,):
        return f"core::mem::align_of::<{arm.source_shape.base_spelling}>()"
    if condition.memory_payload_extents == (MemoryPayloadExtent.VECTOR,):
        return (
            f"<{arm.source_representation.vector_descriptor} "
            "as crate::tsl_core::SimdVector>::ALIGN"
        )
    raise ValueError("checked Rust facade requires one memory payload extent")


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
