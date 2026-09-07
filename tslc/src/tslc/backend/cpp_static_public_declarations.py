"""Exact stable declarations owned by the static C++ public headers."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.cpp_public_declarations import (
    CppPublicDeclaration,
    CppPublicParameter,
    CppTemplateParameter,
    CppTemplateParameterKind,
    cpp_type_parameter,
    cpp_value_parameter,
)
from tslc.backend.public_declarations import (
    PublicDeclarationKind,
    PublicDeclarationStability,
)


CPP_CORE_PUBLIC_IDENTITIES = (
    "tsl::array_type",
    "tsl::dataparallel::fixed",
    "tsl::dataparallel::generic",
    "tsl::dataparallel::native",
    "tsl::implementation_state",
    "tsl::precondition_error",
    "tsl::reg_param",
    "tsl::simd",
    "tsl::span",
)


@dataclass(frozen=True, slots=True)
class _StaticDeclaration:
    asset: str
    hole: str
    declaration: CppPublicDeclaration
    complete_definition: bool = False
    indent: int = 0

    def render(self) -> str:
        rendered = (
            self.declaration.render_type_definition()
            if self.complete_definition
            else self.declaration.render_head()
        )
        rendered += ";" if self.complete_definition else ""
        if self.indent:
            prefix = " " * self.indent
            rendered = "\n".join(
                f"{prefix}{line}" if line else "" for line in rendered.splitlines()
            )
        return rendered


def _type(
    identity: str,
    *,
    name: str,
    owner: str,
    header: str,
    form: str,
    templates: tuple[CppTemplateParameter, ...] = (),
    attributes: tuple[str, ...] = (),
    underlying_type: str | None = None,
    enumerators: tuple[str, ...] = (),
    overload: str = "static-public-type",
) -> CppPublicDeclaration:
    return CppPublicDeclaration(
        identity=identity,
        name=name,
        owner=owner,
        reachability=("tsl.hpp", header),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TYPE,
        overload=overload,
        template_parameters=tuple(templates),
        attributes=attributes,
        type_form=form,
        underlying_type=underlying_type,
        enumerators=enumerators,
    )


def _alias(
    identity: str,
    *,
    name: str,
    owner: str,
    header: str,
    target: str,
    templates: tuple[CppTemplateParameter, ...] = (),
) -> CppPublicDeclaration:
    return CppPublicDeclaration(
        identity=identity,
        name=name,
        owner=owner,
        reachability=("tsl.hpp", header),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.TYPE_ALIAS,
        overload="static-public-type-alias",
        template_parameters=tuple(templates),
        alias_target=target,
    )


def _member(
    identity: str,
    *,
    name: str,
    owner: str,
    header: str,
    kind: PublicDeclarationKind,
    overload: str,
    templates: tuple[CppTemplateParameter, ...] = (),
    parameters: tuple[CppPublicParameter, ...] = (),
    result_type: str | None = None,
    specifiers: tuple[str, ...] = (),
    attributes: tuple[str, ...] = (),
    noexcept: bool = False,
    trailing_return: bool = False,
    qualifiers: tuple[str, ...] = (),
    alias_target: str | None = None,
    type_spelling: str | None = None,
    value: str | None = None,
    stability: PublicDeclarationStability = PublicDeclarationStability.STABLE,
) -> CppPublicDeclaration:
    return CppPublicDeclaration(
        identity=identity,
        name=name,
        owner=owner,
        reachability=("tsl.hpp", header),
        stability=stability,
        kind=kind,
        overload=overload,
        template_parameters=templates,
        parameters=parameters,
        result_type=result_type,
        specifiers=specifiers,
        attributes=attributes,
        noexcept=noexcept,
        trailing_return=trailing_return,
        qualifiers=qualifiers,
        alias_target=alias_target,
        type_spelling=type_spelling,
        value=value,
    )


def _static_member(
    asset: str,
    hole: str,
    declaration: CppPublicDeclaration,
) -> _StaticDeclaration:
    return _StaticDeclaration(asset, hole, declaration, indent=2)


_DECLARATIONS = (
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_implementation_state",
        _type(
            "tsl::implementation_state",
            name="implementation_state",
            owner="tsl",
            header="tsl_core.hpp",
            form="enum class",
            enumerators=("native", "composed", "fallback", "unknown"),
            overload="implementation-state-enum",
        ),
        complete_definition=True,
    ),
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_precondition_error",
        _type(
            "tsl::precondition_error",
            name="precondition_error",
            owner="tsl",
            header="tsl_core.hpp",
            form="enum class",
            underlying_type="std::uint8_t",
            enumerators=(
                "none",
                "index_out_of_bounds",
                "zero_divisor",
                "insufficient_extent",
                "insufficient_input",
                "insufficient_output",
                "misaligned",
                "overlapping_ranges",
                "address_overflow",
            ),
            overload="checked-error-enum",
        ),
        complete_definition=True,
    ),
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_span",
        _type(
            "tsl::span",
            name="span",
            owner="tsl",
            header="tsl_core.hpp",
            form="class",
            templates=(cpp_type_parameter("T"),),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_alias_element_type",
        _member(
            "tsl::span<T>::element_type",
            name="element_type",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.TYPE_ALIAS,
            overload="span-element-alias",
            alias_target="T",
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_constructor_pointer",
        _member(
            "tsl::span<T>::span#pointer-size",
            name="span",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.CONSTRUCTOR,
            overload="pointer-size",
            parameters=(
                CppPublicParameter("data", "T*", "range-pointer"),
                CppPublicParameter("size", "std::size_t", "range-size"),
            ),
            specifiers=("constexpr",),
            noexcept=True,
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_constructor_array",
        _member(
            "tsl::span<T>::span#array",
            name="span",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.CONSTRUCTOR,
            overload="array",
            templates=(cpp_value_parameter("std::size_t", "Size"),),
            parameters=(
                CppPublicParameter(
                    "data",
                    "T (&)[Size]",
                    "range-array",
                    declaration_spelling="T (&{name})[Size]",
                ),
            ),
            specifiers=("constexpr",),
            noexcept=True,
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_constructor_conversion",
        _member(
            "tsl::span<T>::span#conversion",
            name="span",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.CONSTRUCTOR,
            overload="compatible-span-conversion",
            templates=(
                cpp_type_parameter("U"),
                CppTemplateParameter(
                    None,
                    CppTemplateParameterKind.VALUE,
                    type_spelling=(
                        "std::enable_if_t<"
                        "std::is_convertible_v<U (*)[], T (*)[]>, int>"
                    ),
                    default="0",
                ),
            ),
            parameters=(
                CppPublicParameter("other", "span<U>", "source-range"),
            ),
            specifiers=("constexpr",),
            noexcept=True,
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_method_data",
        _member(
            "tsl::span<T>::data",
            name="data",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="range-data",
            result_type="T*",
            specifiers=("constexpr",),
            attributes=("[[nodiscard]]",),
            noexcept=True,
            trailing_return=True,
            qualifiers=("const",),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_span_method_size",
        _member(
            "tsl::span<T>::size",
            name="size",
            owner="tsl::span<T>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="range-size",
            result_type="std::size_t",
            specifiers=("constexpr",),
            attributes=("[[nodiscard]]",),
            noexcept=True,
            trailing_return=True,
            qualifiers=("const",),
        ),
    ),
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_simd",
        _type(
            "tsl::simd",
            name="simd",
            owner="tsl",
            header="tsl_core.hpp",
            form="struct",
            templates=(cpp_type_parameter("T"), cpp_type_parameter("Ext")),
        ),
    ),
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_reg_param",
        _type(
            "tsl::reg_param",
            name="reg_param",
            owner="tsl",
            header="tsl_core.hpp",
            form="struct",
            templates=(cpp_type_parameter("Vec"),),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_reg_param_alias_type",
        _member(
            "tsl::reg_param<Vec>::type",
            name="type",
            owner="tsl::reg_param<Vec>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.TYPE_ALIAS,
            overload="register-parameter-alias",
            alias_target="typename Vec::register_type",
        ),
    ),
    _StaticDeclaration(
        "tsl_core.hpp",
        "core_declaration_array_type",
        _type(
            "tsl::array_type",
            name="array_type",
            owner="tsl",
            header="tsl_core.hpp",
            form="struct",
            templates=(
                cpp_type_parameter("T"),
                cpp_value_parameter("std::size_t", "N"),
                cpp_value_parameter(
                    "std::size_t", "Align", default="alignof(T)"
                ),
            ),
            attributes=("alignas(Align)",),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_field_storage",
        _member(
            "tsl::array_type<T,N,Align>::_storage",
            name="_storage",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.FIELD,
            overload="owned-storage-field",
            type_spelling="std::array<T, N>",
            stability=PublicDeclarationStability.IMPLEMENTATION_DETAIL,
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_data_mut",
        _member(
            "tsl::array_type<T,N,Align>::data#mutable",
            name="data",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="mutable",
            result_type="T*",
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_data_const",
        _member(
            "tsl::array_type<T,N,Align>::data#const",
            name="data",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="const",
            result_type="const T*",
            qualifiers=("const",),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_as_ptr",
        _member(
            "tsl::array_type<T,N,Align>::as_ptr",
            name="as_ptr",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="const-pointer",
            result_type="const T*",
            qualifiers=("const",),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_as_mut_ptr",
        _member(
            "tsl::array_type<T,N,Align>::as_mut_ptr",
            name="as_mut_ptr",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="mutable-pointer",
            result_type="T*",
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_index_mut",
        _member(
            "tsl::array_type<T,N,Align>::operator[]#mutable",
            name="operator[]",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="mutable-index",
            parameters=(CppPublicParameter("i", "std::size_t", "index"),),
            result_type="T&",
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_index_const",
        _member(
            "tsl::array_type<T,N,Align>::operator[]#const",
            name="operator[]",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="const-index",
            parameters=(CppPublicParameter("i", "std::size_t", "index"),),
            result_type="const T&",
            qualifiers=("const",),
        ),
    ),
    _static_member(
        "tsl_core.hpp",
        "core_array_method_fill",
        _member(
            "tsl::array_type<T,N,Align>::fill",
            name="fill",
            owner="tsl::array_type<T, N, Align>",
            header="tsl_core.hpp",
            kind=PublicDeclarationKind.METHOD,
            overload="fill",
            parameters=(CppPublicParameter("value", "const T&", "value"),),
            result_type="void",
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_declaration_native",
        _type(
            "tsl::dataparallel::native",
            name="native",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            form="struct",
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_declaration_fixed",
        _type(
            "tsl::dataparallel::fixed",
            name="fixed",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            form="struct",
            templates=(cpp_value_parameter("std::size_t", "N"),),
        ),
    ),
    _static_member(
        "tsl_dataparallel.hpp",
        "dataparallel_fixed_constant_lanes",
        _member(
            "tsl::dataparallel::fixed<N>::lanes",
            name="lanes",
            owner="tsl::dataparallel::fixed<N>",
            header="tsl_dataparallel.hpp",
            kind=PublicDeclarationKind.CONSTANT,
            overload="policy-lane-count",
            specifiers=("static", "constexpr"),
            type_spelling="std::size_t",
            value="N",
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_declaration_generic",
        _type(
            "tsl::dataparallel::generic",
            name="generic",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            form="struct",
            templates=(cpp_value_parameter("std::size_t", "N"),),
        ),
    ),
    _static_member(
        "tsl_dataparallel.hpp",
        "dataparallel_generic_constant_lanes",
        _member(
            "tsl::dataparallel::generic<N>::lanes",
            name="lanes",
            owner="tsl::dataparallel::generic<N>",
            header="tsl_dataparallel.hpp",
            kind=PublicDeclarationKind.CONSTANT,
            overload="policy-lane-count",
            specifiers=("static", "constexpr"),
            type_spelling="std::size_t",
            value="N",
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_declaration_simd_for",
        _type(
            "tsl::dataparallel::simd_for",
            name="simd_for",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            form="struct",
            templates=(cpp_type_parameter("Policy"), cpp_type_parameter("T")),
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_alias_simd_for_t",
        _alias(
            "tsl::dataparallel::simd_for_t",
            name="simd_for_t",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            target="typename simd_for<Policy, T>::type",
            templates=(cpp_type_parameter("Policy"), cpp_type_parameter("T")),
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_alias_register_t",
        _alias(
            "tsl::dataparallel::register_t",
            name="register_t",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            target="typename simd_for_t<Policy, T>::register_type",
            templates=(cpp_type_parameter("Policy"), cpp_type_parameter("T")),
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_alias_rebind_base_t",
        _alias(
            "tsl::dataparallel::rebind_base_t",
            name="rebind_base_t",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            target="typename Vec::template with_base_type<ToT>",
            templates=(cpp_type_parameter("Vec"), cpp_type_parameter("ToT")),
        ),
    ),
    _StaticDeclaration(
        "tsl_dataparallel.hpp",
        "dataparallel_alias_rebind_simd_for_t",
        _alias(
            "tsl::dataparallel::rebind_simd_for_t",
            name="rebind_simd_for_t",
            owner="tsl::dataparallel",
            header="tsl_dataparallel.hpp",
            target="rebind_base_t<simd_for_t<Policy, FromT>, ToT>",
            templates=(
                cpp_type_parameter("Policy"),
                cpp_type_parameter("FromT"),
                cpp_type_parameter("ToT"),
            ),
        ),
    ),
    _StaticDeclaration(
        "tsl_algorithm_tags.hpp",
        "algorithm_declaration_vector_tag",
        _type(
            "tsl::algo::vector_tag",
            name="vector_tag",
            owner="tsl::algo",
            header="tsl_algorithm_tags.hpp",
            form="struct",
            templates=(cpp_type_parameter("Vec"),),
            overload="algorithm-vector-policy",
        ),
    ),
    _static_member(
        "tsl_algorithm_tags.hpp",
        "algorithm_vector_tag_alias_type",
        _member(
            "tsl::algo::vector_tag<Vec>::type",
            name="type",
            owner="tsl::algo::vector_tag<Vec>",
            header="tsl_algorithm_tags.hpp",
            kind=PublicDeclarationKind.TYPE_ALIAS,
            overload="algorithm-vector-policy-alias",
            alias_target="Vec",
        ),
    ),
    *(
        _StaticDeclaration(
            "tsl_algorithm_tags.hpp",
            f"algorithm_declaration_alignment_{name}",
            _type(
                f"tsl::algo::alignment::{name}",
                name=name,
                owner="tsl::algo::alignment",
                header="tsl_algorithm_tags.hpp",
                form="struct",
                overload="algorithm-alignment-policy",
            ),
        )
        for name in (
            "detect",
            "unaligned",
            "assume_aligned",
            "assume_inputs_aligned",
            "assume_output_aligned",
            "peel_to_aligned",
        )
    ),
    *(
        _StaticDeclaration(
            "tsl_algorithm_tags.hpp",
            f"algorithm_declaration_mask_layout_{name}",
            _type(
                f"tsl::algo::mask_layout::{name}",
                name=name,
                owner="tsl::algo::mask_layout",
                header="tsl_algorithm_tags.hpp",
                form="struct",
                overload="algorithm-mask-layout-policy",
            ),
        )
        for name in ("integral", "native", "bytes", "bits")
    ),
)


def cpp_static_public_declarations() -> tuple[CppPublicDeclaration, ...]:
    return tuple(item.declaration for item in _DECLARATIONS)


def cpp_static_declaration_holes(asset: str) -> dict[str, str]:
    return {
        item.hole: item.render()
        for item in _DECLARATIONS
        if item.asset == asset
    }


__all__ = (
    "CPP_CORE_PUBLIC_IDENTITIES",
    "cpp_static_declaration_holes",
    "cpp_static_public_declarations",
)
