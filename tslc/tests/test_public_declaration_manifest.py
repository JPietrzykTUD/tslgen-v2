"""Exact backend declaration records are the public compatibility boundary."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_declaration_holes,
    cpp_algorithm_public_declarations,
)
from tslc.backend.cpp_public_declarations import (
    CppPublicDeclaration,
    CppPublicParameter,
    cpp_constraint_parameter,
    cpp_type_parameter,
)
from tslc.backend.cpp_public_api import (
    cpp_static_public_declarations as cpp_classified_static_public_declarations,
)
from tslc.backend.cpp_static_public_declarations import (
    cpp_static_declaration_holes,
    cpp_static_public_declarations,
)
from tslc.backend.public_api_manifest import BackendPublicApiManifest
from tslc.backend.public_declarations import (
    PublicDeclarationClassificationScope,
    PublicDeclarationKind,
    PublicDeclarationStability,
)
from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_public_declarations import (
    rust_profile_algorithm_declaration_holes,
    rust_profile_algorithm_module_declaration,
    rust_profile_algorithm_public_declarations,
)
from tslc.backend.rust_facade_public_declarations import (
    rust_facade_type_declaration_holes,
    rust_facade_type_public_declarations,
)
from tslc.backend.rust_public_declarations import (
    RustPublicDeclaration,
    RustPublicParameter,
    rust_type_parameter,
)
from tslc.backend.rust_static_public_declarations import (
    rust_static_declaration_holes,
)
from tslc.compiler_assets import load_default_render_assets


def _cpp_declaration() -> CppPublicDeclaration:
    return CppPublicDeclaration(
        identity="tsl::demo#vector",
        name="demo",
        owner="tsl",
        reachability=("tsl.hpp", "profile:demo"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload="vector:v:=(v)",
        template_parameters=(cpp_type_parameter("Vec"),),
        parameters=(CppPublicParameter("value", "reg_param_t<Vec>", "value"),),
        result_type="typename Vec::register_type",
        specifiers=("TSL_FORCE_INLINE",),
        attributes=("[[nodiscard]]",),
        noexcept=True,
        trailing_return=True,
    )


def _rust_declaration() -> RustPublicDeclaration:
    return RustPublicDeclaration(
        identity="crate::profile::demo#vector",
        name="demo",
        owner="crate::profile",
        reachability=("crate", "profile", "selection:demo"),
        stability=PublicDeclarationStability.STABLE,
        kind=PublicDeclarationKind.FUNCTION,
        overload="vector:v:=(v)",
        visibility="pub",
        generic_parameters=(rust_type_parameter("S", "StaticSimdVector"),),
        parameters=(RustPublicParameter("value", "S::RegisterType", "value"),),
        where_predicates=("S::BaseType: Copy",),
        result_type="S::RegisterType",
        result_form="direct",
        attributes=("#[inline]",),
    )


def _serialize(declaration: CppPublicDeclaration | RustPublicDeclaration) -> str:
    return BackendPublicApiManifest(
        backend="test",
        scope=("z", "a"),
        declarations=(declaration,),
    ).serialize()


def test_manifest_serialization_is_deterministic_under_input_order() -> None:
    cpp = _cpp_declaration()
    rust = _rust_declaration()
    left = BackendPublicApiManifest("mixed", ("z", "a"), (cpp, rust))
    right = BackendPublicApiManifest("mixed", ("a", "z"), (rust, cpp))

    assert left.serialize() == right.serialize()
    assert left.payload()["scope"] == ["a", "z"]


def test_cpp_manifest_detects_each_exact_signature_dimension() -> None:
    declaration = _cpp_declaration()
    baseline = _serialize(declaration)
    template = declaration.template_parameters[0]
    parameter = declaration.parameters[0]
    drifts = (
        replace(declaration, specifiers=("inline",)),
        replace(
            declaration,
            template_parameters=(
                template,
                cpp_constraint_parameter("std::is_integral_v<typename Vec::base_type>"),
            ),
        ),
        replace(
            declaration,
            parameters=(replace(parameter, type_spelling="typename Vec::register_type"),),
        ),
        replace(declaration, result_type="void"),
        replace(declaration, noexcept=False),
        replace(declaration, reachability=("other.hpp",)),
    )

    assert all(_serialize(drift) != baseline for drift in drifts)


def test_rust_manifest_detects_each_exact_signature_dimension() -> None:
    declaration = _rust_declaration()
    baseline = _serialize(declaration)
    generic = declaration.generic_parameters[0]
    parameter = declaration.parameters[0]
    drifts = (
        replace(declaration, visibility="pub(crate)"),
        replace(
            declaration,
            generic_parameters=(
                replace(
                    generic,
                    declaration="S: Copy",
                    bounds=("Copy",),
                ),
            ),
        ),
        replace(declaration, parameters=(replace(parameter, type_spelling="S"),)),
        replace(declaration, result_type="()"),
        replace(declaration, unsafe=True),
        replace(declaration, reachability=("crate", "other")),
    )

    assert all(_serialize(drift) != baseline for drift in drifts)


def test_manifest_rejects_missing_or_nonordinary_checked_twins() -> None:
    ordinary = _cpp_declaration()
    checked = replace(
        ordinary,
        identity="tsl::demo_checked#vector",
        name="demo_checked",
        checked_of=ordinary.identity,
        error_form="result-plus-error-reference",
    )
    with pytest.raises(ValueError, match="missing owners"):
        BackendPublicApiManifest("cpp", ("demo",), (checked,))

    checked_target = replace(
        ordinary,
        identity="tsl::demo_second_checked#vector",
        name="demo_second_checked",
        checked_of="tsl::other#vector",
        error_form="result-plus-error-reference",
    )
    target = replace(
        checked,
        identity="tsl::other#vector",
        checked_of=ordinary.identity,
    )
    with pytest.raises(ValueError, match="ordinary owners"):
        BackendPublicApiManifest(
            "cpp",
            ("demo",),
            (ordinary, checked_target, target),
        )


def test_manifest_relations_resolve_one_exact_reachable_owner() -> None:
    ordinary = _cpp_declaration()
    other_profile = replace(
        ordinary,
        reachability=("tsl.hpp", "profile:other"),
    )
    checked = replace(
        ordinary,
        identity="tsl::demo_checked#vector",
        name="demo_checked",
        reachability=("tsl.hpp", "profile:missing"),
        checked_of=ordinary.identity,
        error_form="result-plus-error-reference",
    )

    with pytest.raises(ValueError, match="ambiguous at its reachability"):
        BackendPublicApiManifest(
            "cpp",
            ("demo",),
            (ordinary, other_profile, checked),
        )


def test_manifest_rejects_coarse_stable_overload_sets() -> None:
    declaration = replace(
        _rust_declaration(),
        kind=PublicDeclarationKind.OVERLOAD_SET,
        generic_parameters=(),
        parameters=(),
        where_predicates=(),
        result_type=None,
        result_form="implicit-unit",
    )

    with pytest.raises(ValueError, match="exact overload records"):
        BackendPublicApiManifest("rust", ("demo",), (declaration,))


def test_manifest_rejects_stable_macros_without_an_expansion_model() -> None:
    declaration = replace(
        _cpp_declaration(),
        kind=PublicDeclarationKind.MACRO,
        template_parameters=(),
        parameters=(),
        result_type=None,
        specifiers=(),
        attributes=(),
        noexcept=False,
        trailing_return=False,
    )

    with pytest.raises(ValueError, match="exact expansion model"):
        BackendPublicApiManifest("cpp", ("demo",), (declaration,))


def test_descendant_classification_is_reserved_for_nonstable_containers() -> None:
    with pytest.raises(ValueError, match="non-stable Rust modules or types"):
        replace(
            _rust_declaration(),
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        )
    unstable_type = replace(
        _rust_declaration(),
        stability=PublicDeclarationStability.UNSTABLE,
        kind=PublicDeclarationKind.TYPE,
        generic_parameters=(),
        parameters=(),
        where_predicates=(),
        result_type=None,
        result_form="implicit-unit",
        type_form="struct",
        classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
    )
    assert unstable_type.classification_scope is (
        PublicDeclarationClassificationScope.DESCENDANTS
    )
    with pytest.raises(ValueError, match=r"non-stable C\+\+ modules or types"):
        replace(
            _cpp_declaration(),
            kind=PublicDeclarationKind.TYPE,
            parameters=(),
            result_type=None,
            type_form="struct",
            classification_scope=PublicDeclarationClassificationScope.DESCENDANTS,
        )


def test_static_stable_types_are_exact_and_rendered_from_their_records() -> None:
    cpp = cpp_static_public_declarations()
    rust = rust_facade_type_public_declarations()

    assert all(
        declaration.kind is PublicDeclarationKind.TYPE_ALIAS
        or declaration.render_head()
        for declaration in (*cpp, *rust)
    )
    cpp_by_identity = {declaration.identity: declaration for declaration in cpp}
    span_data = cpp_by_identity["tsl::span<T>::data"]
    assert span_data.qualifiers == ("const",)
    assert span_data.noexcept
    assert span_data.parameters == ()
    assert span_data.result_type == "T*"
    assert _serialize(span_data) != _serialize(
        replace(span_data, qualifiers=())
    )
    assert cpp_by_identity["tsl::span<T>::span#array"].parameters[
        0
    ].declaration_spelling == "T (&{name})[Size]"
    assert cpp_by_identity["tsl::span<T>::span#array"].manifest()["parameters"] == [
        {
            "name": "data",
            "type": "T (&)[Size]",
            "role": "range-array",
            "declaration": "T (&data)[Size]",
        }
    ]
    assert cpp_by_identity[
        "tsl::array_type<T,N,Align>::_storage"
    ].stability is PublicDeclarationStability.IMPLEMENTATION_DETAIL
    rust_holes = rust_facade_type_declaration_holes()
    assert rust_holes["facade_declaration_simd"].endswith(
        "where\n    T: SupportedSimd<N>,"
    )


def test_cpp_static_support_surface_has_explicit_classifications() -> None:
    declarations = cpp_classified_static_public_declarations(
        supports_algorithm=False
    )
    by_identity = {declaration.identity: declaration for declaration in declarations}

    assert by_identity["TSL_FORCE_INLINE#macro"].kind is (
        PublicDeclarationKind.MACRO
    )
    assert by_identity["TSL_FORCE_INLINE#macro"].owner == "preprocessor"
    assert by_identity["tsl::ostream_write#static-support"].kind is (
        PublicDeclarationKind.OVERLOAD_SET
    )
    assert by_identity[
        "tsl::indexed_memory_address_error#static-support"
    ].stability is PublicDeclarationStability.UNSTABLE
    assert by_identity[
        "tsl::dataparallel::simd_for#static-registrations"
    ].classification_scope is PublicDeclarationClassificationScope.DESCENDANTS
    assert by_identity[
        "tsl::simd#scalar-registration"
    ].classification_scope is PublicDeclarationClassificationScope.DESCENDANTS
    assert by_identity["tsl::detail#namespace"].reachability == (
        "tsl.hpp",
        "tsl_core.hpp",
        "physical-profile-header",
    )
    assert by_identity["tsl::primitive#tags"].reachability == (
        "tsl.hpp",
        "tsl_primitives.hpp",
    )
    assert by_identity["tsl::implementation_state_of#template"].reachability == (
        "tsl.hpp",
        "tsl_core.hpp",
    )
    assert by_identity["tsl::algo::detail#namespace"].reachability[0] == "tsl.hpp"


def test_static_assets_have_one_hole_for_each_owned_declaration_fragment() -> None:
    assets = load_default_render_assets()
    by_asset = {
        name: cpp_static_declaration_holes(name)
        for name in (
            "tsl_core.hpp",
            "tsl_dataparallel.hpp",
            "tsl_algorithm_tags.hpp",
        )
    }
    by_asset["tsl_core.rs"] = rust_static_declaration_holes()
    by_asset["rust_facade.rs.tmpl"] = rust_facade_type_declaration_holes()

    for asset_name, holes in by_asset.items():
        asset = assets.text(asset_name)
        assert all(asset.count(f"@{{{name}}}") == 1 for name in holes)


def test_algorithm_records_and_render_holes_are_bijective() -> None:
    cpp = cpp_algorithm_public_declarations()
    cpp_holes = cpp_algorithm_declaration_holes()
    rust_reachability = ("crate", "profile", "selection:test", "algo")
    rust = (
        *rust_profile_algorithm_public_declarations(rust_reachability),
        *rust_profile_scaled_checked_algorithm_declarations(rust_reachability),
    )
    rust_holes = rust_profile_algorithm_declaration_holes()

    assert len(cpp_holes) == len(cpp)
    assert len(rust_holes) == sum(
        declaration.kind is PublicDeclarationKind.FUNCTION
        and declaration.overload != "selected-row-scaled-checked"
        for declaration in rust
    )
    assert not any(
        declaration.kind is PublicDeclarationKind.OVERLOAD_SET
        for declaration in (*cpp, *rust)
    )
    assert all(
        (declaration.result_form == "result")
        == (declaration.checked_of is not None)
        for declaration in rust
        if declaration.kind is PublicDeclarationKind.FUNCTION
    )


def test_rust_profile_algorithm_module_is_exact_stable_and_renderable() -> None:
    reachability = ("crate", "profile", "selection:test")
    declaration = rust_profile_algorithm_module_declaration(reachability)

    assert declaration.identity == "crate::profile::algo#module"
    assert declaration.owner == "crate::profile"
    assert declaration.reachability == reachability
    assert declaration.stability is PublicDeclarationStability.STABLE
    assert declaration.kind is PublicDeclarationKind.MODULE
    assert declaration.classification_scope is (
        PublicDeclarationClassificationScope.EXACT
    )
    assert declaration.render_head() == "pub mod algo"
