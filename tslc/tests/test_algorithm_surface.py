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
    cpp_algorithm_form_support,
    cpp_algorithm_public_declarations,
)
from tslc.backend.public_declarations import PublicDeclarationKind
from tslc.backend.rust_algorithm_contracts import (
    rust_profile_scaled_checked_algorithm_declarations,
)
from tslc.backend.rust_algorithm_manifest import RUST_ALGORITHM_RESERVED_NAMES
from tslc.backend.rust_algorithm_public_declarations import (
    rust_algorithm_form_support,
    rust_profile_algorithm_public_declarations,
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
