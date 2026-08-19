"""Pointer-cast operands use typed TSIL address forms."""

from __future__ import annotations

from dataclasses import replace

from _select_lower_core_support import (
    Catalog,
    Lowerer,
    Selector,
    create_backend_dialect,
)


def _scalar_slot(catalog: Catalog, machine_profiles, primitive: str):
    return next(
        selected
        for selected in Selector()
        .select_profile(catalog, machine_profiles["scalar"], primitive, ("si32",))
        .selected
        if selected.extension.name == "scalar"
    )


def _lower_cast_body(
    catalog: Catalog, machine_profiles, backend_id: str, cast_text: str
):
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")
    slot = replace(
        slot,
        implementation=replace(
            slot.implementation,
            body_text=(
                "var<typed>(base::in, result, value(uninit::scalar));\n"
                f"var<const_infer>(p, {cast_text});\n"
                "complete(result);"
            ),
        ),
    )
    return Lowerer().lower(slot, catalog, create_backend_dialect(catalog, backend_id))


def test_rust_mutable_address_of_uses_addr_of_mut(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "rust",
        "cast<reinterpret, type=ptr>(void, address<borrow_mut>(buf))",
    )

    assert result.specialization is not None
    assert (
        "core::ptr::addr_of_mut!(buf).cast::<u8>()"
        in result.specialization.body_text
    )


def test_rust_address_of_is_classified_from_nested_region(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "rust",
        "cast<reinterpret, type=const_ptr>(void, address<of>(buf))",
    )

    assert result.specialization is not None
    assert (
        "core::ptr::addr_of!(buf).cast::<u8>()"
        in result.specialization.body_text
    )


def test_rust_parenthesized_address_of_keeps_target(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "rust",
        "cast<reinterpret, type=const_ptr>(void, address<of>((buf)))",
    )

    assert result.specialization is not None
    assert (
        "core::ptr::addr_of!((buf)).cast::<u8>()"
        in result.specialization.body_text
    )


def test_rust_pointer_valued_expression_casts_directly(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "rust",
        "cast<reinterpret, type=ptr>(void, buf_ptr)",
    )

    assert result.specialization is not None
    assert "buf_ptr as *mut u8" in result.specialization.body_text


def test_unsupported_address_selector_is_a_structured_skip(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "rust",
        "cast<reinterpret, type=ptr>(void, address<double>(buf))",
    )

    assert result.specialization is None
    diagnostic = next(
        d for d in result.diagnostics if d.code == "TSL-LOWER-UNSUPPORTED-CAST"
    )
    assert "operand form" in diagnostic.message


def test_cpp_address_of_render_is_byte_stable(
    catalog: Catalog, machine_profiles
) -> None:
    result = _lower_cast_body(
        catalog,
        machine_profiles,
        "cpp",
        "cast<reinterpret, type=const_ptr>(void, address<of>(buf))",
    )

    assert result.specialization is not None
    assert "reinterpret_cast<void const *>(&buf)" in result.specialization.body_text
