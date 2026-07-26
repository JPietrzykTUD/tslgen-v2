"""Render comprehensive Rust facade items from finalized planner records."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustFacadeDelegate,
    RustFacadeConstParameter,
    RustFacadeConstParameterSource,
    RustFacadeParameter,
    RustFacadeParameterPlacement,
    RustFacadePlan,
    RustFacadeReceiverKind,
    RustFacadeRepresentation,
    RustFacadeShape,
)
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.documentation import documentation_block, render_rust_doc
from tslc.render.rust_facade_common import (
    cfg_attribute,
    combined_selection_cfg,
    lower_module,
    private_vector_descriptor,
    representations_can_coexist,
    selection_cfg,
    surface_delegate,
    surface_delegate_for_profile,
    surface_delegate_owner,
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
            for block in _private_impls(plan, method)
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
        f"{_raw_type(parameter.kind, owner='Self', target_owner='Self')}"
        for parameter in runtime_parameters
    )
    const_generics = _const_generic_declarations(method)
    return_type = _raw_type(
        method.result_kind, owner="Self", target_owner=target_owner
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
    plan: RustFacadePlan,
    method: RustComprehensiveMethod,
) -> tuple[str, ...]:
    blocks: list[str] = []
    target_parameter = _target_type_parameter(method)
    for source_shape in _method_shapes(plan, method):
        if target_parameter is None:
            for source_representation in source_shape.representations:
                delegate = surface_delegate(
                    method.delegates, source_shape, source_representation
                )
                blocks.extend(
                    _private_impl_variants(
                        method,
                        source_shape,
                        source_representation,
                        delegate,
                    )
                )
            continue
        for pair in method.conversion_pairs:
            if (
                pair.source_type_tag != source_shape.type_tag
                or (source_shape.type_tag, source_shape.lanes)
                not in pair.shape_keys
            ):
                continue
            target_shape = next(
                (
                    shape
                    for shape in plan.shapes
                    if shape.type_tag == pair.target_type_tag
                    and shape.lanes == source_shape.lanes
                ),
                None,
            )
            if target_shape is None:
                continue
            for source_representation in source_shape.representations:
                for target_representation in target_shape.representations:
                    if not representations_can_coexist(
                        source_representation, target_representation
                    ):
                        continue
                    active_representation = (
                        source_representation
                        if source_representation.profile_name is not None
                        else target_representation
                    )
                    delegate = surface_delegate_for_profile(
                        pair.delegates,
                        source_shape,
                        source_representation,
                        active_representation.profile_name,
                    )
                    blocks.extend(
                        _private_impl_variants(
                            method,
                            source_shape,
                            source_representation,
                            delegate,
                            target_shape=target_shape,
                            target_representation=target_representation,
                            cfg=combined_selection_cfg(
                                source_representation, target_representation
                            ),
                            active_representation=active_representation,
                        )
                    )
    return tuple(blocks)


def _private_impl_variants(
    method: RustComprehensiveMethod,
    source_shape: RustFacadeShape,
    source_representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
    *,
    target_shape: RustFacadeShape | None = None,
    target_representation: RustFacadeRepresentation | None = None,
    cfg: str | None = None,
    active_representation: RustFacadeRepresentation | None = None,
) -> tuple[str, ...]:
    identity_parameters = _identity_const_parameters(method)
    combinations = _delegate_attribute_combinations(
        delegate, source_shape, source_representation
    )
    if not identity_parameters:
        combinations = ((),)
    return tuple(
        _private_impl(
            method,
            source_shape,
            source_representation,
            delegate,
            attribute_values=combination,
            target_shape=target_shape,
            target_representation=target_representation,
            cfg=cfg,
            active_representation=active_representation,
        )
        for combination in combinations
        if tuple(name for name, _value in combination)
        == tuple(parameter.source_name for parameter in identity_parameters)
    )


def _delegate_attribute_combinations(
    delegate: RustFacadeDelegate,
    shape: RustFacadeShape,
    representation: RustFacadeRepresentation,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    expected_extension = surface_delegate_owner(
        delegate,
        shape,
        representation,
    )
    matches = tuple(
        vector
        for vector in delegate.vectors
        if vector.extension_name == expected_extension
        and vector.type_tag == shape.type_tag
    )
    if len(matches) != 1:
        raise ValueError(
            "Rust comprehensive delegate has no unique vector attribute inventory "
            f"for {shape.type_tag}x{shape.lanes}"
        )
    return matches[0].attribute_combinations or ((),)


def _private_impl(
    method: RustComprehensiveMethod,
    source_shape: RustFacadeShape,
    source_representation: RustFacadeRepresentation,
    delegate: RustFacadeDelegate,
    *,
    attribute_values: tuple[tuple[str, str], ...],
    target_shape: RustFacadeShape | None = None,
    target_representation: RustFacadeRepresentation | None = None,
    cfg: str | None = None,
    active_representation: RustFacadeRepresentation | None = None,
) -> str:
    trait_name = _private_trait_name(method)
    trait_argument_parts = [
        *((target_shape.base_spelling,) if target_shape is not None else ()),
        str(source_shape.lanes),
        *(value for _name, value in attribute_values),
    ]
    trait_arguments = ", ".join(trait_argument_parts)
    runtime_parameters = _runtime_parameters(method)
    parameters = ", ".join(
        f"{_identifier(parameter.public_name)}: "
        f"{_impl_raw_type(parameter.kind, 'Self', source_shape.lanes)}"
        for parameter in runtime_parameters
    )
    const_generics = _const_generic_declarations(method)
    return_type = _impl_raw_type(
        method.result_kind,
        target_shape.base_spelling if target_shape else "Self",
        source_shape.lanes,
    )
    return_suffix = "" if method.result_kind == "void" else f" -> {return_type}"
    call_representation = active_representation or source_representation
    generic_arguments = [private_vector_descriptor(source_representation)]
    if target_representation is not None:
        generic_arguments.append(private_vector_descriptor(target_representation))
    generic_arguments.extend(value for _name, value in attribute_values)
    generic_arguments.extend(
        parameter.public_name for parameter in _method_const_parameters(method)
    )
    generic_arguments.extend("_" for _ in delegate.overload_parameter_positions)
    call = (
        f"{lower_module(call_representation)}::"
        f"{rust_raw_identifier(delegate.primitive_name)}"
        f"::<{', '.join(generic_arguments)}>"
        f"({', '.join(_lower_call_arguments(method, source_representation))})"
    )
    if method.caller_unsafe:
        call = f"unsafe {{ {call} }}"
    result = _adapt_lower_result(method.result_kind, call, source_representation)
    unsafe_prefix = "unsafe " if method.caller_unsafe else ""
    body_lines = []
    if method.caller_unsafe:
        body_lines.append(
            "        // SAFETY: forwarded from the public facade caller contract."
        )
    body_lines.append(f"        {result}")
    return "\n".join(
        (
            cfg_attribute(cfg or selection_cfg(source_representation)),
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
    plan: RustFacadePlan,
    method: RustComprehensiveMethod,
) -> tuple[str, ...]:
    if method.receiver_kind is RustFacadeReceiverKind.FREE:
        return (_public_free_function(method),)
    return tuple(
        _public_inherent_method(method, shape)
        for shape in _method_shapes(plan, method)
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
        + _public_type(
            parameter.kind,
            shape.base_spelling,
            str(shape.lanes),
            shape.base_spelling,
        )
        for parameter in runtime_parameters
    )
    signature_parameters = (
        f"self, {parameter_declarations}" if parameter_declarations else "self"
    )
    target = _target_type_parameter(method)
    type_generics = [target] if target is not None else []
    generic_declarations = _public_generic_declarations(method, type_generics)
    return_type = _public_type(
        method.result_kind,
        shape.base_spelling,
        str(shape.lanes),
        "U" if target is not None else shape.base_spelling,
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
    result = _adapt_public_result(method.result_kind, call, target is not None)
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
        f"{_public_type(parameter.kind, 'T', 'N', 'T')}"
        for parameter in runtime_parameters
    )
    target = _target_type_parameter(method)
    type_generics = ["T", *(("U",) if target is not None else ())]
    generic_declarations = _public_generic_declarations(
        method, [*type_generics, "const N: usize"]
    )
    return_type = _public_type(
        method.result_kind, "T", "N", "U" if target is not None else "T"
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
    result = _adapt_public_result(method.result_kind, call, target is not None)
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
                        + _public_type(
                            method.result_kind,
                            element,
                            lanes,
                            "U" if method.type_parameters else element,
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
            if method.public_name in _STANDARD_TRAIT_METHOD_NAMES
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


def _lower_call_arguments(
    method: RustComprehensiveMethod,
    representation: RustFacadeRepresentation,
) -> tuple[str, ...]:
    arguments: list[str] = []
    for parameter in sorted(
        _runtime_parameters(method), key=lambda item: item.source_index
    ):
        name = _identifier(parameter.public_name)
        if parameter.kind in {"im", "imt"}:
            arguments.append(
                name
                if representation.mapping.imask_spelling == "u64"
                else f"{name} as {representation.mapping.imask_spelling}"
            )
        else:
            arguments.append(name)
    return tuple(arguments)


def _public_call_arguments(method: RustComprehensiveMethod) -> tuple[str, ...]:
    arguments: list[str] = []
    for parameter in _runtime_parameters(method):
        if parameter.placement is RustFacadeParameterPlacement.RECEIVER:
            arguments.append("self.value")
            continue
        name = _identifier(parameter.public_name)
        arguments.append(f"{name}.value" if parameter.kind in {"v", "m"} else name)
    return tuple(arguments)


def _adapt_lower_result(
    kind: str,
    call: str,
    representation: RustFacadeRepresentation,
) -> str:
    if kind in {"im", "imt"}:
        return (
            call
            if representation.mapping.imask_spelling == "u64"
            else f"{call} as u64"
        )
    return call


def _adapt_public_result(kind: str, call: str, has_target: bool) -> str:
    if kind == "v":
        return f"Simd {{ value: {call} }}"
    if kind == "m":
        owner = "U" if has_target else "_"
        return f"Mask::<{owner}, _> {{ value: {call} }}"
    return call


def _raw_type(kind: str, *, owner: str, target_owner: str) -> str:
    return {
        "void": "()",
        "v": f"<{target_owner if target_owner != owner else owner} as Representation<N>>::Vector"
        if target_owner != owner
        else f"{owner}::Vector",
        "m": f"<{target_owner if target_owner != owner else owner} as Representation<N>>::Mask"
        if target_owner != owner
        else f"{owner}::Mask",
        "im": "u64",
        "imt": "u64",
        "s": owner,
        "usize": "usize",
        "ptr": f"*mut {owner}",
        "cptr": f"*const {owner}",
    }[kind]


_STANDARD_TRAIT_METHOD_NAMES = frozenset(
    {
        "add",
        "bitand",
        "bitor",
        "bitxor",
        "div",
        "mul",
        "neg",
        "not",
        "rem",
        "shl",
        "shr",
        "sub",
    }
)


def _impl_raw_type(kind: str, owner: str, lanes: int) -> str:
    return {
        "void": "()",
        "v": f"<{owner} as private::Representation<{lanes}>>::Vector",
        "m": f"<{owner} as private::Representation<{lanes}>>::Mask",
        "im": "u64",
        "imt": "u64",
        "s": "Self",
        "usize": "usize",
        "ptr": "*mut Self",
        "cptr": "*const Self",
    }[kind]


def _public_type(
    kind: str,
    element: str,
    lanes: str,
    result_element: str,
) -> str:
    return {
        "void": "()",
        "v": f"Simd<{result_element}, {lanes}>",
        "m": f"Mask<{result_element}, {lanes}>",
        "im": "u64",
        "imt": "u64",
        "s": element,
        "usize": "usize",
        "ptr": f"*mut {element}",
        "cptr": f"*const {element}",
    }[kind]


def _method_shapes(
    plan: RustFacadePlan,
    method: RustComprehensiveMethod,
) -> tuple[RustFacadeShape, ...]:
    keys = set(method.shape_keys)
    return tuple(
        shape
        for shape in plan.shapes
        if (shape.type_tag, shape.lanes) in keys
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
