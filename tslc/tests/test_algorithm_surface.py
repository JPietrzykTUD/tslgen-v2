"""Target-neutral algorithm identity and backend projection coverage."""

from __future__ import annotations

from tslc.backend.algorithm_contracts import ALGORITHM_CONTRACTS
from tslc.backend.algorithm_surface import (
    ALGORITHM_CALLABLE_FORMS,
    ALGORITHM_CHECKED_TWINS,
    ALGORITHM_FORMS_BY_NAME,
    ALGORITHM_PUBLIC_FAMILIES,
    ALGORITHM_SCALED_CHECKED_TWINS,
    ALGORITHM_SURFACE_FAMILIES,
    AlgorithmArity,
    AlgorithmMaskForm,
    AlgorithmResultKind,
    AlgorithmSemanticFamily,
    AlgorithmShape,
    AlgorithmSurfaceFamily,
)
from tslc.backend.cpp_algorithm_contracts import (
    cpp_checked_algorithm_declarations,
)
from tslc.backend.cpp_algorithm_public_declarations import (
    cpp_algorithm_checked_twin_identity,
    cpp_consume_aggregate_declarations,
    cpp_algorithm_declaration_holes,
    cpp_algorithm_form_support,
    cpp_algorithm_public_declarations,
    cpp_iteration_predicate_count_declarations,
    cpp_selection_declarations,
    cpp_transform_declarations,
)
from tslc.backend.public_declarations import PublicDeclarationKind
from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_algorithm_public_declarations import (
    rust_algorithm_form_support,
    rust_consume_aggregate_function_declarations,
    rust_iteration_predicate_count_function_declarations,
    rust_profile_algorithm_declaration_holes,
    rust_profile_algorithm_public_declarations,
    rust_selection_function_declarations,
    rust_transform_function_declarations,
)


def test_algorithm_surface_forms_and_contracts_are_bijective() -> None:
    assert len(ALGORITHM_SURFACE_FAMILIES) == 44
    assert len(ALGORITHM_CALLABLE_FORMS) == 56
    assert tuple(ALGORITHM_FORMS_BY_NAME.values()) == ALGORITHM_CALLABLE_FORMS
    assert {
        family.name for family in ALGORITHM_SURFACE_FAMILIES
    } == ALGORITHM_PUBLIC_FAMILIES

    contract_forms = {
        form.name: form
        for form in ALGORITHM_CALLABLE_FORMS
        if form.family.has_contract
    }
    assert set(contract_forms) == set(ALGORITHM_CONTRACTS)
    assert all(
        contract_forms[name].family.result_kind is contract.result_kind
        for name, contract in ALGORITHM_CONTRACTS.items()
    )
    assert dict(ALGORITHM_CHECKED_TWINS) == {
        f"{name}_checked": name for name in contract_forms
    }
    assert dict(ALGORITHM_SCALED_CHECKED_TWINS) == {
        form.scaled_checked_name: form.scaled_raw_name
        for form in contract_forms.values()
        if form.scaled_checked_name is not None
    }


def test_backend_declarations_join_the_shared_surface_exactly() -> None:
    cpp_function_names = {
        declaration.name
        for declaration in cpp_algorithm_public_declarations()
        if declaration.kind is PublicDeclarationKind.FUNCTION
    }
    assert cpp_function_names == ALGORITHM_PUBLIC_FAMILIES

    for form in ALGORITHM_CALLABLE_FORMS:
        cpp_support = cpp_algorithm_form_support(form)
        rust_support = rust_algorithm_form_support(form)
        if form.mask_form is AlgorithmMaskForm.LAYOUT:
            assert not cpp_support.supported
            assert cpp_support.reason is not None
        else:
            assert cpp_support.supported
            assert cpp_support.reason is None
        assert rust_support.supported
        assert rust_support.reason is None

    reachability = ("crate", "profile", "selection:test", "algo")
    rust_declarations = (
        *rust_profile_algorithm_public_declarations(reachability),
        *rust_profile_scaled_checked_algorithm_declarations(reachability),
    )
    assert {
        declaration.name for declaration in rust_declarations
    } == RUST_ALGORITHM_RESERVED_NAMES


def test_checked_relations_derive_from_surface_forms() -> None:
    for declaration in cpp_checked_algorithm_declarations():
        name = declaration.name.removesuffix("_checked")
        fixed = declaration.identity.endswith("#fixed")
        assert declaration.checked_of == cpp_algorithm_checked_twin_identity(
            name,
            fixed=fixed,
        )

    reachability = ("crate", "profile", "selection:test", "algo")
    for declaration in rust_profile_algorithm_public_declarations(reachability):
        if declaration.checked_of is None:
            continue
        ordinary_name = ALGORITHM_CHECKED_TWINS[declaration.name]
        assert declaration.checked_of == (
            f"crate::profile::algo::{ordinary_name}#algorithm-alias"
        )
    for declaration in rust_profile_scaled_checked_algorithm_declarations(
        reachability
    ):
        ordinary_name = ALGORITHM_SCALED_CHECKED_TWINS[declaration.name]
        assert declaration.checked_of == (
            f"crate::profile::algo::{ordinary_name}#algorithm"
        )


def test_first_slice_forms_project_to_the_existing_exact_records_and_holes() -> None:
    cpp = cpp_algorithm_public_declarations()
    cpp_holes = cpp_algorithm_declaration_holes()
    reachability = ("crate", "profile", "selection:test", "algo")
    rust = rust_profile_algorithm_public_declarations(reachability)
    rust_holes = rust_profile_algorithm_declaration_holes()

    for form in ALGORITHM_CALLABLE_FORMS:
        if form.family.semantic_family not in {
            AlgorithmSemanticFamily.ITERATION,
            AlgorithmSemanticFamily.PREDICATE,
            AlgorithmSemanticFamily.COUNT,
        }:
            continue
        if form.mask_form is AlgorithmMaskForm.DEFAULT:
            cpp_projected = cpp_iteration_predicate_count_declarations(form)
            assert cpp_projected == tuple(
                declaration
                for declaration in cpp
                if declaration.kind is PublicDeclarationKind.FUNCTION
                and declaration.name == form.family.name
            )
            assert all(
                f"algorithm_declaration_{declaration.name}_"
                f"{declaration.identity.rsplit('-', 1)[-1]}" in cpp_holes
                for declaration in cpp_projected
            )

        rust_projected = rust_iteration_predicate_count_function_declarations(
            form,
            reachability,
        )
        projected_identities = {
            declaration.identity for declaration in rust_projected
        }
        assert rust_projected == tuple(
            declaration
            for declaration in rust
            if declaration.identity in projected_identities
        )
        assert all(
            f"profile_algorithm_declaration_{declaration.name}" in rust_holes
            for declaration in rust_projected
        )


def test_first_slice_projectors_accept_additive_semantic_forms() -> None:
    synthetic_unary = AlgorithmSurfaceFamily(
        "synthetic_predicate_unary",
        AlgorithmSemanticFamily.PREDICATE,
        AlgorithmArity.UNARY,
        AlgorithmShape.PLAIN,
        AlgorithmResultKind.COUNT,
        has_contract=True,
        has_mask_layout_form=True,
    )
    synthetic_masked_binary = AlgorithmSurfaceFamily(
        "synthetic_count_masked_binary",
        AlgorithmSemanticFamily.COUNT,
        AlgorithmArity.BINARY,
        AlgorithmShape.MASKED,
        AlgorithmResultKind.COUNT,
        has_contract=True,
        has_mask_layout_form=True,
    )
    reachability = ("crate", "profile", "selection:synthetic", "algo")

    for family in (synthetic_unary, synthetic_masked_binary):
        default_form, layout_form = family.callable_forms
        cpp = cpp_iteration_predicate_count_declarations(default_form)
        assert [declaration.overload for declaration in cpp] == [
            "algorithm-overload-4",
            "algorithm-overload-2",
            "algorithm-overload-3",
            "algorithm-overload-1",
        ]
        for form in (default_form, layout_form):
            rust = rust_iteration_predicate_count_function_declarations(
                form,
                reachability,
            )
            assert [declaration.name for declaration in rust] == [
                f"{form.name}_checked",
                f"{form.name}_raw",
            ]


def test_selection_forms_project_to_existing_exact_records_and_holes() -> None:
    cpp = cpp_algorithm_public_declarations()
    cpp_holes = cpp_algorithm_declaration_holes()
    reachability = ("crate", "profile", "selection:test", "algo")
    rust = rust_profile_algorithm_public_declarations(reachability)
    rust_holes = rust_profile_algorithm_declaration_holes()

    for form in ALGORITHM_CALLABLE_FORMS:
        if form.family.semantic_family is not AlgorithmSemanticFamily.SELECT:
            continue
        if form.mask_form is AlgorithmMaskForm.DEFAULT:
            cpp_projected = cpp_selection_declarations(form)
            assert cpp_projected == tuple(
                declaration
                for declaration in cpp
                if declaration.kind is PublicDeclarationKind.FUNCTION
                and declaration.name == form.family.name
            )
            assert all(
                f"algorithm_declaration_{declaration.name}_"
                f"{declaration.identity.rsplit('-', 1)[-1]}" in cpp_holes
                for declaration in cpp_projected
            )

        rust_projected = rust_selection_function_declarations(
            form,
            reachability,
        )
        projected_identities = {
            declaration.identity for declaration in rust_projected
        }
        assert rust_projected == tuple(
            declaration
            for declaration in rust
            if declaration.identity in projected_identities
        )
        assert all(
            f"profile_algorithm_declaration_{declaration.name}" in rust_holes
            for declaration in rust_projected
        )


def test_selection_projectors_accept_masked_index_and_scaled_forms() -> None:
    masked_indices = AlgorithmSurfaceFamily(
        "synthetic_select_masked_indices_binary",
        AlgorithmSemanticFamily.SELECT,
        AlgorithmArity.BINARY,
        AlgorithmShape.MASKED_INDICES,
        AlgorithmResultKind.COUNT,
        has_contract=True,
        has_mask_layout_form=True,
    )
    selected_indices = AlgorithmSurfaceFamily(
        "synthetic_select_selected_indices_unary",
        AlgorithmSemanticFamily.SELECT,
        AlgorithmArity.UNARY,
        AlgorithmShape.SELECTED_INDICES,
        AlgorithmResultKind.COUNT,
        has_contract=True,
        has_scaled_form=True,
    )
    reachability = ("crate", "profile", "selection:synthetic", "algo")

    masked_default, masked_layout = masked_indices.callable_forms
    cpp_masked = cpp_selection_declarations(masked_default)
    assert len(cpp_masked) == 4
    assert any(
        parameter.name == "masks" and parameter.type_spelling == "const MaskRange&"
        for parameter in cpp_masked[-1].parameters
    )
    assert [
        declaration.name
        for declaration in rust_selection_function_declarations(
            masked_layout,
            reachability,
        )
    ] == [
        "synthetic_select_masked_indices_binary_mask_layout_checked",
        "synthetic_select_masked_indices_binary_mask_layout_raw",
    ]

    selected = selected_indices.callable_forms[0]
    cpp_selected = cpp_selection_declarations(selected)
    assert len(cpp_selected) == 2
    assert cpp_selected[0].template_parameters[1].name == "Scale"
    assert [
        declaration.name
        for declaration in rust_selection_function_declarations(
            selected,
            reachability,
        )
    ] == [
        "synthetic_select_selected_indices_unary_checked",
        "synthetic_select_selected_indices_unary_raw",
        "synthetic_select_selected_indices_unary_scaled_raw",
    ]


def test_transform_forms_project_to_existing_exact_records_and_holes() -> None:
    cpp = cpp_algorithm_public_declarations()
    cpp_holes = cpp_algorithm_declaration_holes()
    reachability = ("crate", "profile", "selection:test", "algo")
    rust = rust_profile_algorithm_public_declarations(reachability)
    rust_holes = rust_profile_algorithm_declaration_holes()

    for form in ALGORITHM_CALLABLE_FORMS:
        if form.family.semantic_family is not AlgorithmSemanticFamily.TRANSFORM:
            continue
        if form.mask_form is AlgorithmMaskForm.DEFAULT:
            cpp_projected = cpp_transform_declarations(form)
            assert cpp_projected == tuple(
                declaration
                for declaration in cpp
                if declaration.kind is PublicDeclarationKind.FUNCTION
                and declaration.name == form.family.name
            )
            assert all(
                f"algorithm_declaration_{declaration.name}_"
                f"{declaration.identity.rsplit('-', 1)[-1]}" in cpp_holes
                for declaration in cpp_projected
            )

        rust_projected = rust_transform_function_declarations(
            form,
            reachability,
        )
        projected_identities = {
            declaration.identity for declaration in rust_projected
        }
        assert rust_projected == tuple(
            declaration
            for declaration in rust
            if declaration.identity in projected_identities
        )
        assert all(
            f"profile_algorithm_declaration_{declaration.name}" in rust_holes
            for declaration in rust_projected
        )


def test_transform_projectors_accept_layout_and_scaled_forms() -> None:
    where_binary = AlgorithmSurfaceFamily(
        "synthetic_transform_where_binary",
        AlgorithmSemanticFamily.TRANSFORM,
        AlgorithmArity.BINARY,
        AlgorithmShape.WHERE,
        AlgorithmResultKind.VOID,
        has_contract=True,
        has_mask_layout_form=True,
    )
    selected_unary = AlgorithmSurfaceFamily(
        "synthetic_transform_selected_unary",
        AlgorithmSemanticFamily.TRANSFORM,
        AlgorithmArity.UNARY,
        AlgorithmShape.SELECTED,
        AlgorithmResultKind.VOID,
        has_contract=True,
        has_scaled_form=True,
    )
    reachability = ("crate", "profile", "selection:synthetic", "algo")

    where_default, where_layout = where_binary.callable_forms
    assert len(cpp_transform_declarations(where_default)) == 4
    assert [
        declaration.name
        for declaration in rust_transform_function_declarations(
            where_layout,
            reachability,
        )
    ] == [
        "synthetic_transform_where_binary_mask_layout_checked",
        "synthetic_transform_where_binary_mask_layout_raw",
    ]

    selected = selected_unary.callable_forms[0]
    cpp_selected = cpp_transform_declarations(selected)
    assert len(cpp_selected) == 2
    assert cpp_selected[0].template_parameters[1].name == "Scale"
    assert [
        declaration.name
        for declaration in rust_transform_function_declarations(
            selected,
            reachability,
        )
    ] == [
        "synthetic_transform_selected_unary_checked",
        "synthetic_transform_selected_unary_raw",
        "synthetic_transform_selected_unary_scaled_raw",
    ]


def test_consume_aggregate_forms_project_to_existing_records_and_holes() -> None:
    cpp = cpp_algorithm_public_declarations()
    cpp_holes = cpp_algorithm_declaration_holes()
    reachability = ("crate", "profile", "selection:test", "algo")
    rust = rust_profile_algorithm_public_declarations(reachability)
    rust_holes = rust_profile_algorithm_declaration_holes()

    for form in ALGORITHM_CALLABLE_FORMS:
        if form.family.semantic_family not in {
            AlgorithmSemanticFamily.CONSUME,
            AlgorithmSemanticFamily.AGGREGATE,
        }:
            continue
        cpp_projected = cpp_consume_aggregate_declarations(form)
        assert cpp_projected == tuple(
            declaration
            for declaration in cpp
            if declaration.kind is PublicDeclarationKind.FUNCTION
            and declaration.name == form.family.name
        )
        assert all(
            f"algorithm_declaration_{declaration.name}_"
            f"{declaration.identity.rsplit('-', 1)[-1]}" in cpp_holes
            for declaration in cpp_projected
        )

        rust_projected = rust_consume_aggregate_function_declarations(
            form,
            reachability,
        )
        projected_identities = {
            declaration.identity for declaration in rust_projected
        }
        assert rust_projected == tuple(
            declaration
            for declaration in rust
            if declaration.identity in projected_identities
        )
        assert all(
            f"profile_algorithm_declaration_{declaration.name}" in rust_holes
            for declaration in rust_projected
        )


def test_consume_aggregate_projectors_accept_masked_and_scaled_forms() -> None:
    masked_aggregate = AlgorithmSurfaceFamily(
        "synthetic_aggregate_masked_binary",
        AlgorithmSemanticFamily.AGGREGATE,
        AlgorithmArity.BINARY,
        AlgorithmShape.MASKED,
        AlgorithmResultKind.VALUE,
        has_contract=True,
    ).callable_forms[0]
    selected_consume = AlgorithmSurfaceFamily(
        "synthetic_consume_selected_unary",
        AlgorithmSemanticFamily.CONSUME,
        AlgorithmArity.UNARY,
        AlgorithmShape.SELECTED,
        AlgorithmResultKind.VOID,
        has_contract=True,
        has_scaled_form=True,
    ).callable_forms[0]
    reachability = ("crate", "profile", "selection:synthetic", "algo")

    cpp_masked = cpp_consume_aggregate_declarations(masked_aggregate)
    assert len(cpp_masked) == 4
    assert all(declaration.result_type == "auto" for declaration in cpp_masked)
    rust_masked = rust_consume_aggregate_function_declarations(
        masked_aggregate,
        reachability,
    )
    assert rust_masked[0].result_type is not None
    assert "MaskedBinaryAggregateKernel" in rust_masked[0].result_type

    cpp_selected = cpp_consume_aggregate_declarations(selected_consume)
    assert len(cpp_selected) == 2
    assert cpp_selected[0].template_parameters[1].name == "Scale"
    assert [
        declaration.name
        for declaration in rust_consume_aggregate_function_declarations(
            selected_consume,
            reachability,
        )
    ] == [
        "synthetic_consume_selected_unary_checked",
        "synthetic_consume_selected_unary_raw",
        "synthetic_consume_selected_unary_scaled_raw",
    ]


def test_unregistered_form_is_explicitly_unsupported_by_both_backends() -> None:
    synthetic = AlgorithmSurfaceFamily(
        "synthetic_transform_unary",
        AlgorithmSemanticFamily.TRANSFORM,
        AlgorithmArity.UNARY,
        AlgorithmShape.PLAIN,
        AlgorithmResultKind.VOID,
        has_contract=False,
    ).callable_forms[0]

    for support in (
        cpp_algorithm_form_support(synthetic),
        rust_algorithm_form_support(synthetic),
    ):
        assert not support.supported
        assert support.reason == (
            "algorithm form is not registered in the shared surface"
        )
