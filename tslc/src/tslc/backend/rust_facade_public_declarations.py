"""Exact public declarations for the opaque Rust SIMD facade."""

from __future__ import annotations

from tslc.backend.checked_api import CheckedConditionPlan
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_api_arms import (
    RustCuratedMethodImplementationArm,
    RustFacadeArmSelection,
    RustFacadeBitConversionImplementationArm,
)
from tslc.backend.rust_api_kinds import (
    RustCuratedMethodKind,
    RustFacadeBitConversionDirection,
    RustFacadeConstParameterSource,
    RustFacadeParameterPlacement,
    RustFacadeReceiverKind,
)
from tslc.backend.rust_api_model import (
    RustComprehensiveMethod,
    RustCuratedMethod,
    RustFacadeConstParameter,
    RustFacadeParameter,
    RustFacadePlan,
    RustFacadeShape,
)
from tslc.backend.rust_api_types import RUST_FACADE_SIGNATURE_TYPES
from tslc.backend.rust_facade_checked import (
    rust_checked_conditions_for_type,
    rust_checked_public_parameter_type,
)
from tslc.backend.rust_names import rust_primitive_tag_name
from tslc.backend.rust_public_declarations import (
    RustGenericParameter,
    RustPublicDeclaration,
    RustPublicParameter,
    rust_const_parameter,
    rust_type_parameter,
)
from tslc.backend.rust_translation import rust_raw_identifier


def rust_facade_type_public_declarations() -> tuple[RustPublicDeclaration, ...]:
    """Return exact definitions for the stable opaque facade types."""

    simd_element = RustPublicDeclaration(
        identity="crate::tsl_facade::SimdElement#definition",
        name="SimdElement",
        owner="crate::tsl_facade",
        reachability=("crate", "opaque-facade"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TRAIT,
        overload="opaque-element-trait",
        visibility="pub",
        attributes=("#[allow(private_bounds)]",),
        type_form="trait",
        supertraits=(
            "private::SealedElement",
            "Copy",
            "core::fmt::Debug",
            "Send",
            "Sync",
            "Unpin",
            "'static",
        ),
        associated_items=(
            "type NativeSimd: Copy + Send + Sync + Unpin + 'static;",
            "type NativeMask: Copy + Send + Sync + Unpin + 'static;",
        ),
    )
    supported = RustPublicDeclaration(
        identity="crate::tsl_facade::SupportedSimd#definition",
        name="SupportedSimd",
        owner="crate::tsl_facade",
        reachability=("crate", "opaque-facade"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TRAIT,
        overload="opaque-supported-shape-trait",
        visibility="pub",
        attributes=("#[allow(private_bounds)]",),
        generic_parameters=(rust_const_parameter("N", "usize"),),
        type_form="trait",
        supertraits=(
            "SimdElement",
            "private::Representation<N>",
            "private::FacadeOps<N>",
        ),
    )

    def opaque_type(name: str) -> RustPublicDeclaration:
        return RustPublicDeclaration(
            identity=f"crate::tsl_facade::{name}#definition",
            name=name,
            owner="crate::tsl_facade",
            reachability=("crate", "opaque-facade"),
            stability=PublicDeclarationStability.STABLE,
            kind=PublicDeclarationKind.TYPE,
            overload="opaque-owned-value",
            visibility="pub",
            attributes=("#[derive(Clone, Copy)]", "#[allow(private_bounds)]"),
            generic_parameters=(
                rust_type_parameter("T"),
                rust_const_parameter("N", "usize"),
            ),
            where_predicates=("T: SupportedSimd<N>",),
            type_form="struct",
        )

    native_simd = RustPublicDeclaration(
        identity="crate::tsl_facade::NativeSimd#definition",
        name="NativeSimd",
        owner="crate::tsl_facade",
        reachability=("crate", "opaque-facade"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TYPE_ALIAS,
        overload="opaque-native-alias",
        visibility="pub",
        generic_parameters=(rust_type_parameter("T"),),
        alias_target="<T as SimdElement>::NativeSimd",
    )
    native_mask = RustPublicDeclaration(
        identity="crate::tsl_facade::NativeMask#definition",
        name="NativeMask",
        owner="crate::tsl_facade",
        reachability=("crate", "opaque-facade"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TYPE_ALIAS,
        overload="opaque-native-alias",
        visibility="pub",
        generic_parameters=(rust_type_parameter("T"),),
        alias_target="<T as SimdElement>::NativeMask",
    )
    return (
        simd_element,
        supported,
        opaque_type("Simd"),
        opaque_type("Mask"),
        native_simd,
        native_mask,
    )


def rust_facade_type_declaration_holes() -> dict[str, str]:
    """Render stable facade type declarations from their manifest records."""

    declarations = {
        declaration.name: declaration
        for declaration in rust_facade_type_public_declarations()
    }
    simd_element = declarations["SimdElement"]
    supported = declarations["SupportedSimd"]
    return {
        "facade_declaration_simd_element": "\n".join(
            (*simd_element.attributes, simd_element.render_head())
        ),
        "facade_declaration_native_simd_associated": simd_element.associated_items[0],
        "facade_declaration_native_mask_associated": simd_element.associated_items[1],
        "facade_declaration_supported_simd": "\n".join(
            (*supported.attributes, supported.render_type_definition())
        ),
        **{
            f"facade_declaration_{name.lower()}": "\n".join(
                (*declarations[name].attributes, declarations[name].render_head())
            )
            for name in ("Simd", "Mask")
        },
        "facade_declaration_native_simd": declarations["NativeSimd"].render_head()
        + ";",
        "facade_declaration_native_mask": declarations["NativeMask"].render_head()
        + ";",
    }


def rust_facade_core_public_declarations() -> tuple[RustPublicDeclaration, ...]:
    """Return the exact generic methods and constants owned by the facade shell."""

    return tuple(record for _hole, record in _rust_facade_core_items())


def rust_facade_core_declaration_owners() -> tuple[tuple[str, str], ...]:
    """Expose template-hole ownership without reparsing rendered Rust heads."""

    return tuple(
        (hole, declaration.name)
        for hole, declaration in _rust_facade_core_items()
    )


def rust_facade_core_declaration_holes() -> dict[str, str]:
    """Render facade-shell declaration holes from the same stable records."""

    rendered: dict[str, str] = {}
    for hole, declaration in _rust_facade_core_items():
        if declaration.kind is PublicDeclarationKind.CONSTANT:
            text = declaration.render_head() + ";"
        else:
            text = "\n".join(
                (*declaration.attributes, declaration.render_definition_head())
            )
        rendered[hole] = _indent(text, 4)
    return rendered


def rust_curated_public_declarations(
    plan: RustFacadePlan,
) -> tuple[RustPublicDeclaration, ...]:
    """Return exact public records for curated and bit-conversion methods."""

    declarations: list[RustPublicDeclaration] = []
    for method in plan.curated_methods:
        if method.kind is RustCuratedMethodKind.NUMERIC_CAST:
            declarations.append(rust_numeric_cast_declaration())
            continue
        declarations.extend(
            rust_curated_method_declaration(method, arm)
            for arm in method.implementation_arms
        )
    declarations.extend(
        rust_bit_conversion_declaration(arm)
        for conversion in plan.bit_conversions
        for arm in conversion.implementation_arms
    )
    return tuple(declarations)


def rust_numeric_cast_declaration() -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity="crate::Simd<T,N>::cast#numeric",
        name="cast",
        owner="crate::Simd<T, N>",
        reachability=("crate", "opaque-facade", "generic"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.METHOD,
        overload="numeric-cast",
        visibility="pub",
        generic_parameters=(rust_type_parameter("U"),),
        parameters=(RustPublicParameter("self", None, "receiver", receiver=True),),
        where_predicates=(
            "U: SupportedSimd<N>",
            "T: private::ConvertTo<U, N>",
        ),
        result_type="Simd<U, N>",
        result_form="direct",
        attributes=("#[inline]", "#[must_use]", "#[allow(private_bounds)]"),
    )


def rust_curated_method_declaration(
    method: RustCuratedMethod,
    arm: RustCuratedMethodImplementationArm,
) -> RustPublicDeclaration:
    if method.kind not in {
        RustCuratedMethodKind.COMPARISON,
        RustCuratedMethodKind.SELECTION,
    }:
        raise ValueError("curated implementation arms require comparison or selection")
    shape = arm.shape
    vector = f"Simd<{shape.base_spelling}, {shape.lanes}>"
    mask = f"Mask<{shape.base_spelling}, {shape.lanes}>"
    if method.kind is RustCuratedMethodKind.SELECTION:
        owner = mask
        parameters: tuple[RustPublicParameter, ...] = (
            RustPublicParameter("self", None, "receiver", receiver=True),
            RustPublicParameter("true_values", vector, "operation:true_value"),
            RustPublicParameter("false_values", vector, "operation:false_value"),
        )
        result_type = vector
    else:
        owner = vector
        parameters = (
            RustPublicParameter("self", None, "receiver", receiver=True),
            RustPublicParameter("other", "Self", "operation:right"),
        )
        result_type = mask
    return RustPublicDeclaration(
        identity=f"crate::{owner}::{method.public_name}#{method.operation.value}",
        name=method.public_name,
        owner=f"crate::{owner}",
        reachability=(
            "crate",
            "opaque-facade",
            *rust_facade_selection_reachability(arm.selection),
        ),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.METHOD,
        overload=(
            f"curated:{method.operation.value}:{shape.type_tag}x{shape.lanes}"
        ),
        visibility="pub",
        parameters=parameters,
        result_type=result_type,
        result_form="direct",
        attributes=("#[inline]", "#[must_use]"),
        unsafe=method.caller_unsafe,
    )


def rust_bit_conversion_declaration(
    arm: RustFacadeBitConversionImplementationArm,
) -> RustPublicDeclaration:
    float_shape = arm.float_shape
    bits_shape = arm.bits_shape
    owner = f"Simd<{float_shape.base_spelling}, {float_shape.lanes}>"
    bits = f"Simd<{bits_shape.base_spelling}, {bits_shape.lanes}>"
    to_bits = arm.direction is RustFacadeBitConversionDirection.TO_BITS
    name = "to_bits" if to_bits else "from_bits"
    parameters = (
        (RustPublicParameter("self", None, "receiver", receiver=True),)
        if to_bits
        else (RustPublicParameter("bits", bits, "bit_pattern"),)
    )
    return RustPublicDeclaration(
        identity=f"crate::{owner}::{name}#bit-cast",
        name=name,
        owner=f"crate::{owner}",
        reachability=(
            "crate",
            "opaque-facade",
            *rust_facade_selection_reachability(arm.conversion.selection),
        ),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.METHOD,
        overload=(
            f"bit-cast:{float_shape.type_tag}:{bits_shape.type_tag}:"
            f"{float_shape.lanes}:{arm.direction.value}"
        ),
        visibility="pub",
        parameters=parameters,
        result_type=bits if to_bits else "Self",
        result_form="direct",
        attributes=("#[inline]", "#[must_use]"),
    )


def rust_facade_selection_reachability(
    selection: RustFacadeArmSelection,
) -> tuple[str, ...]:
    """Serialize typed representation selection without recovering target text."""

    facts: list[str] = []
    for representation in selection.representations:
        if representation.requirement is None:
            facts.append("selection:fallback")
            facts.extend(
                "excludes:"
                + excluded.requirement.target_arch
                + ":"
                + ",".join(excluded.requirement.target_features)
                for excluded in representation.fallback_exclusions
            )
            continue
        requirement = representation.requirement
        facts.extend(
            (
                f"selection:{representation.profile_name}",
                f"target-arch:{requirement.target_arch}",
                "target-features:" + ",".join(requirement.target_features),
            )
        )
        facts.extend(
            "excludes:"
            + excluded.target_arch
            + ":"
            + ",".join(excluded.target_features)
            for excluded in representation.stronger_requirements
        )
    return tuple(facts)


def _rust_facade_core_items(
) -> tuple[tuple[str, RustPublicDeclaration], ...]:
    simd = "crate::Simd<T, N>"
    mask = "crate::Mask<T, N>"

    def method(
        hole: str,
        name: str,
        owner: str,
        parameters: tuple[RustPublicParameter, ...],
        result_type: str | None,
        *,
        attributes: tuple[str, ...] = ("#[inline]",),
        generics: tuple[RustGenericParameter, ...] = (),
        where: tuple[str, ...] = (),
        unsafe: bool = False,
    ) -> tuple[str, RustPublicDeclaration]:
        return (
            hole,
            RustPublicDeclaration(
                identity=f"{owner}::{name}#core",
                name=name,
                owner=owner,
                reachability=("crate", "opaque-facade", "generic"),
                stability=PublicDeclarationStability.STABLE,
                kind=PublicDeclarationKind.METHOD,
                overload="opaque-core-method",
                visibility="pub",
                generic_parameters=generics,
                parameters=parameters,
                where_predicates=where,
                result_type=result_type,
                result_form="implicit-unit" if result_type is None else "direct",
                attributes=attributes,
                unsafe=unsafe,
            ),
        )

    self_value = RustPublicParameter("self", None, "receiver", receiver=True)
    self_ref = RustPublicParameter("&self", None, "receiver", receiver=True)
    self_mut = RustPublicParameter("&mut self", None, "receiver", receiver=True)
    must_use = ("#[inline]", "#[must_use]")
    tracked_use = ("#[inline]", "#[must_use]", "#[track_caller]")
    tracked = ("#[inline]", "#[track_caller]")
    return (
        (
            "core_simd_lanes",
            RustPublicDeclaration(
                identity=f"{simd}::LANES#core",
                name="LANES",
                owner=simd,
                reachability=("crate", "opaque-facade", "generic"),
                stability=PublicDeclarationStability.STABLE,
                kind=PublicDeclarationKind.CONSTANT,
                overload="opaque-core-constant",
                visibility="pub",
                type_spelling="usize",
                value="N",
            ),
        ),
        method(
            "core_simd_splat",
            "splat",
            simd,
            (RustPublicParameter("value", "T", "value"),),
            "Self",
            attributes=must_use,
        ),
        method(
            "core_simd_from_array",
            "from_array",
            simd,
            (RustPublicParameter("values", "[T; N]", "input"),),
            "Self",
            attributes=must_use,
        ),
        method(
            "core_simd_to_array",
            "to_array",
            simd,
            (self_value,),
            "[T; N]",
            attributes=must_use,
        ),
        method(
            "core_simd_lane",
            "lane",
            simd,
            (self_ref, RustPublicParameter("index", "usize", "index")),
            "T",
            attributes=tracked_use,
        ),
        method(
            "core_simd_set_lane",
            "set_lane",
            simd,
            (
                self_mut,
                RustPublicParameter("index", "usize", "index"),
                RustPublicParameter("value", "T", "value"),
            ),
            None,
            attributes=tracked,
        ),
        method(
            "core_simd_from_slice",
            "from_slice",
            simd,
            (RustPublicParameter("source", "&[T]", "read_range"),),
            "Self",
            attributes=tracked_use,
        ),
        method(
            "core_simd_from_ptr",
            "from_ptr",
            simd,
            (RustPublicParameter("source", "*const T", "read_pointer"),),
            "Self",
            attributes=must_use,
            unsafe=True,
        ),
        method(
            "core_simd_copy_to_slice",
            "copy_to_slice",
            simd,
            (
                self_value,
                RustPublicParameter(
                    "destination", "&mut [T]", "write_range"
                ),
            ),
            None,
            attributes=tracked,
        ),
        method(
            "core_simd_copy_to_ptr",
            "copy_to_ptr",
            simd,
            (
                self_value,
                RustPublicParameter("destination", "*mut T", "write_pointer"),
            ),
            None,
            unsafe=True,
        ),
        (
            "core_mask_lanes",
            RustPublicDeclaration(
                identity=f"{mask}::LANES#core",
                name="LANES",
                owner=mask,
                reachability=("crate", "opaque-facade", "generic"),
                stability=PublicDeclarationStability.STABLE,
                kind=PublicDeclarationKind.CONSTANT,
                overload="opaque-core-constant",
                visibility="pub",
                type_spelling="usize",
                value="N",
            ),
        ),
        method(
            "core_mask_splat",
            "splat",
            mask,
            (RustPublicParameter("value", "bool", "value"),),
            "Self",
            attributes=must_use,
        ),
        method(
            "core_mask_from_array",
            "from_array",
            mask,
            (RustPublicParameter("values", "[bool; N]", "input"),),
            "Self",
            attributes=must_use,
        ),
        method(
            "core_mask_to_array",
            "to_array",
            mask,
            (self_value,),
            "[bool; N]",
            attributes=must_use,
        ),
        method(
            "core_mask_test",
            "test",
            mask,
            (self_ref, RustPublicParameter("index", "usize", "index")),
            "bool",
            attributes=tracked_use,
        ),
        method(
            "core_mask_set",
            "set",
            mask,
            (
                self_mut,
                RustPublicParameter("index", "usize", "index"),
                RustPublicParameter("value", "bool", "value"),
            ),
            None,
            attributes=tracked,
        ),
        method("core_mask_any", "any", mask, (self_value,), "bool", attributes=must_use),
        method("core_mask_all", "all", mask, (self_value,), "bool", attributes=must_use),
        method(
            "core_mask_count_ones",
            "count_ones",
            mask,
            (self_value,),
            "usize",
            attributes=must_use,
        ),
        method(
            "core_mask_from_bitmask",
            "from_bitmask",
            mask,
            (RustPublicParameter("bits", "u64", "bitset"),),
            "Self",
            attributes=must_use,
        ),
        method(
            "core_mask_to_bitmask",
            "to_bitmask",
            mask,
            (self_value,),
            "u64",
            attributes=must_use,
        ),
        method(
            "core_mask_cast",
            "cast",
            mask,
            (self_value,),
            "Mask<U, N>",
            attributes=must_use,
            generics=(rust_type_parameter("U"),),
            where=("U: SupportedSimd<N>",),
        ),
    )


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def rust_comprehensive_public_declarations(
    plan: RustFacadePlan,
) -> tuple[RustPublicDeclaration, ...]:
    """Return every stable record consumed by comprehensive facade rendering."""

    declarations: list[RustPublicDeclaration] = []
    for method in plan.comprehensive_methods:
        if method.receiver_kind is RustFacadeReceiverKind.FREE:
            declarations.append(rust_public_free_declaration(method, checked=False))
            if method.checked_conditions:
                declarations.append(rust_public_free_declaration(method, checked=True))
            continue
        for shape in method.public_shapes:
            declarations.append(
                rust_public_inherent_declaration(method, shape, checked=False)
            )
            if rust_checked_conditions_for_type(
                method.checked_conditions, shape.type_tag
            ):
                declarations.append(
                    rust_public_inherent_declaration(method, shape, checked=True)
                )
    return tuple(declarations)


def rust_facade_private_trait_name(method: RustComprehensiveMethod) -> str:
    receiver = {
        RustFacadeReceiverKind.VECTOR: "Vector",
        RustFacadeReceiverKind.MASK: "Mask",
        RustFacadeReceiverKind.FREE: "Free",
    }[method.receiver_kind]
    return (
        f"FacadePrimitive{receiver}"
        f"{rust_primitive_tag_name(method.public_name)}"
    )


def rust_public_inherent_declaration(
    method: RustComprehensiveMethod,
    shape: RustFacadeShape,
    *,
    checked: bool,
) -> RustPublicDeclaration:
    checked_conditions = rust_checked_conditions_for_type(
        method.checked_conditions, shape.type_tag
    )
    shape_caller_unsafe = shape.type_tag in method.caller_unsafe_type_tags
    owner_name = (
        "Simd"
        if method.receiver_kind is RustFacadeReceiverKind.VECTOR
        else "Mask"
    )
    owner = f"crate::{owner_name}<{shape.base_spelling}, {shape.lanes}>"
    runtime_parameters = tuple(
        parameter
        for parameter in _runtime_parameters(method)
        if parameter.placement is not RustFacadeParameterPlacement.RECEIVER
    )
    parameters = (
        RustPublicParameter("self", None, "receiver", receiver=True),
        *(
            RustPublicParameter(
                _identifier(parameter.public_name),
                _public_parameter_type(
                    parameter,
                    element=shape.base_spelling,
                    lanes=str(shape.lanes),
                    checked_conditions=(checked_conditions if checked else ()),
                ),
                _facade_parameter_role(parameter),
            )
            for parameter in runtime_parameters
        ),
    )
    target = _target_type_parameter(method)
    generic_parameters = (
        *((rust_type_parameter(target),) if target is not None else ()),
        *_public_const_parameters(method),
    )
    trait_name = rust_facade_private_trait_name(method)
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
    where_predicates = (
        (
            *((f"U: SupportedSimd<{shape.lanes}>",) if target is not None else ()),
            f"{shape.base_spelling}: private::{trait_name}<{trait_arguments}>",
        )
        if needs_private_bound
        else ()
    )
    direct_result = RUST_FACADE_SIGNATURE_TYPES.public_type(
        method.result_kind,
        element=shape.base_spelling,
        lanes=str(shape.lanes),
        result_element="U" if target is not None else shape.base_spelling,
    )
    result_type = (
        f"Result<{direct_result}, crate::PreconditionError>"
        if checked
        else None if method.result_kind == "void" else direct_result
    )
    public_name = method.public_name + ("_checked" if checked else "")
    ordinary_identity = (
        f"{owner}::{rust_raw_identifier(method.public_name)}#{method.signature}"
    )
    return RustPublicDeclaration(
        identity=f"{owner}::{rust_raw_identifier(public_name)}#{method.signature}",
        name=rust_raw_identifier(public_name),
        owner=owner,
        reachability=("crate", "opaque-facade", owner_name),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.METHOD,
        overload=(
            f"{method.signature}:{shape.type_tag}x{shape.lanes}:"
            f"{'checked' if checked else 'ordinary'}"
        ),
        visibility="pub",
        generic_parameters=generic_parameters,
        parameters=parameters,
        where_predicates=where_predicates,
        result_type=result_type,
        result_form=(
            "result"
            if checked
            else "implicit-unit" if result_type is None else "direct"
        ),
        attributes=_public_attributes(
            method,
            has_private_bound=needs_private_bound,
            checked=checked,
        ),
        unsafe=shape_caller_unsafe and not checked,
        checked_of=ordinary_identity if checked else None,
        error_form="result" if checked else None,
    )


def rust_public_free_declaration(
    method: RustComprehensiveMethod,
    *,
    checked: bool,
) -> RustPublicDeclaration:
    target = _target_type_parameter(method)
    generic_parameters = (
        rust_type_parameter("T"),
        *((rust_type_parameter("U"),) if target is not None else ()),
        rust_const_parameter("N", "usize"),
        *_public_const_parameters(method),
    )
    parameters = tuple(
        RustPublicParameter(
            _identifier(parameter.public_name),
            _public_parameter_type(
                parameter,
                element="T",
                lanes="N",
                checked_conditions=(method.checked_conditions if checked else ()),
            ),
            _facade_parameter_role(parameter),
        )
        for parameter in _runtime_parameters(method)
    )
    trait_name = rust_facade_private_trait_name(method)
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
    where_predicates = (
        f"T: SupportedSimd<N> + private::{trait_name}<{trait_arguments}>",
        *(("U: SupportedSimd<N>",) if target is not None else ()),
    )
    direct_result = RUST_FACADE_SIGNATURE_TYPES.public_type(
        method.result_kind,
        element="T",
        lanes="N",
        result_element="U" if target is not None else "T",
    )
    result_type = (
        f"Result<{direct_result}, crate::PreconditionError>"
        if checked
        else None if method.result_kind == "void" else direct_result
    )
    public_name = method.public_name + ("_checked" if checked else "")
    ordinary_identity = (
        "crate::tsl_facade::"
        f"{rust_raw_identifier(method.public_name)}#{method.signature}"
    )
    return RustPublicDeclaration(
        identity=(
            "crate::tsl_facade::"
            f"{rust_raw_identifier(public_name)}#{method.signature}"
        ),
        name=rust_raw_identifier(public_name),
        owner="crate::tsl_facade",
        reachability=("crate", "opaque-facade"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload=f"{method.signature}:{'checked' if checked else 'ordinary'}",
        visibility="pub",
        generic_parameters=generic_parameters,
        parameters=parameters,
        where_predicates=where_predicates,
        result_type=result_type,
        result_form=(
            "result"
            if checked
            else "implicit-unit" if result_type is None else "direct"
        ),
        attributes=_public_attributes(
            method,
            has_private_bound=True,
            checked=checked,
        ),
        unsafe=method.caller_unsafe and not checked,
        checked_of=ordinary_identity if checked else None,
        error_form="result" if checked else None,
    )


def _facade_parameter_role(parameter: RustFacadeParameter) -> str:
    if parameter.role is not None:
        return f"operand:{parameter.role.value}"
    return f"signature:{parameter.kind}"


def _public_const_parameters(
    method: RustComprehensiveMethod,
) -> tuple[RustGenericParameter, ...]:
    return tuple(
        rust_const_parameter(parameter.public_name, parameter.type_spelling)
        for parameter in method.const_parameters
    )


def _public_attributes(
    method: RustComprehensiveMethod,
    *,
    has_private_bound: bool,
    checked: bool,
) -> tuple[str, ...]:
    return (
        "#[inline]",
        *(("#[must_use]",) if method.must_use and not checked else ()),
        *(("#[track_caller]",) if method.panic_conditions else ()),
        *(
            ("#[allow(clippy::should_implement_trait)]",)
            if method.suppress_should_implement_trait_lint
            else ()
        ),
        *(("#[allow(private_bounds)]",) if has_private_bound else ()),
    )


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


def _identity_const_parameters(
    method: RustComprehensiveMethod,
) -> tuple[RustFacadeConstParameter, ...]:
    return tuple(
        parameter
        for parameter in method.const_parameters
        if parameter.source is RustFacadeConstParameterSource.ATTRIBUTE
    )


def _public_parameter_type(
    parameter: RustFacadeParameter,
    *,
    element: str,
    lanes: str,
    checked_conditions: tuple[CheckedConditionPlan, ...],
) -> str:
    return rust_checked_public_parameter_type(
        parameter, checked_conditions, element
    ) or RUST_FACADE_SIGNATURE_TYPES.public_type(
        parameter.kind,
        element=element,
        lanes=lanes,
        result_element=element,
    )


def _identifier(name: str) -> str:
    if name in {"self", "Self", "crate", "super"}:
        return f"{name.lower()}_value"
    return rust_raw_identifier(name)


__all__ = (
    "rust_bit_conversion_declaration",
    "rust_comprehensive_public_declarations",
    "rust_curated_method_declaration",
    "rust_curated_public_declarations",
    "rust_facade_core_declaration_holes",
    "rust_facade_core_declaration_owners",
    "rust_facade_core_public_declarations",
    "rust_facade_type_declaration_holes",
    "rust_facade_type_public_declarations",
    "rust_facade_private_trait_name",
    "rust_facade_selection_reachability",
    "rust_numeric_cast_declaration",
    "rust_public_free_declaration",
    "rust_public_inherent_declaration",
)
