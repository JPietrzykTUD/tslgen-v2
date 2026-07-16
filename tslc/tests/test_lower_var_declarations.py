"""``var<typed>`` uninitialized-form routing lowers from exact source shapes."""

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


def _with_body(slot, body_text: str):
    return replace(slot, implementation=replace(slot.implementation, body_text=body_text))


def test_uninit_scalar_routes_to_the_scalar_uninit_template(
    catalog: Catalog, machine_profiles
) -> None:
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    # `var_uninit` is `{type} {name};` — the value-initializing `var_array_uninit`
    # (`{type} {name}{};`) must not be selected for `uninit::scalar`.
    assert "int32_t result;" in lowered.body_text
    assert "result{}" not in lowered.body_text


def test_uninit_array_still_routes_to_the_array_template(
    catalog: Catalog, machine_profiles
) -> None:
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")
    slot = _with_body(
        slot,
        "var<typed>(base::in, result, value(uninit::array));\ncomplete(result);",
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "int32_t result{};" in lowered.body_text


def test_ordinary_initializer_containing_uninit_is_preserved(
    catalog: Catalog, machine_profiles
) -> None:
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")
    slot = _with_body(
        slot,
        "int32_t my_uninit_count = 0;\n"
        "var<typed>(base::in, result, my_uninit_count);\n"
        "complete(result);",
    )

    lowered = Lowerer().lower(
        slot, catalog, create_backend_dialect(catalog, "cpp")
    ).specialization

    assert lowered is not None
    assert "result = my_uninit_count;" in lowered.body_text


def test_complete_inside_a_loop_block_satisfies_the_complete_precheck(
    catalog: Catalog, machine_profiles
) -> None:
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")
    slot = _with_body(
        slot,
        "var<typed>(base::in, result, value(uninit::scalar));\n"
        "loop<backend>(i, 0, 1, 1) {\n"
        "  complete(result);\n"
        "}",
    )

    result = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert "TSL-LOWER-NO-COMPLETE" not in {d.code for d in result.diagnostics}
    assert result.specialization is not None


def test_unsupported_uninit_form_is_a_structured_skip(
    catalog: Catalog, machine_profiles
) -> None:
    slot = _scalar_slot(catalog, machine_profiles, "set_undef")
    slot = _with_body(
        slot,
        "var<typed>(base::in, result, value(uninit::garbage));\ncomplete(result);",
    )

    result = Lowerer().lower(slot, catalog, create_backend_dialect(catalog, "cpp"))

    assert result.specialization is None
    diagnostic = next(
        d for d in result.diagnostics if d.code == "TSL-LOWER-UNSUPPORTED-VAR"
    )
    assert "uninit::garbage" in diagnostic.message
