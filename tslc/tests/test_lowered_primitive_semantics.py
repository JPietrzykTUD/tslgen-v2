"""Semantic source facts survive selection and lowering unchanged."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import pytest

from tslc.backend.registry import create_backend_dialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, ImplementationVariant
from tslc.catalog.overloads import ResolvedPrimitiveOverload
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.select.selector import SelectedImplementation, Selector


def _selected_slot(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    signature: str,
    *,
    attributes: dict[str, str] | None = None,
) -> SelectedImplementation:
    expected_attributes = attributes or {}
    selected = Selector().select_profile(
        catalog,
        machine_profiles["avx2"],
        primitive_name,
        ("si32",),
        backend_id="rust",
    )
    assert selected.diagnostics == ()
    return next(
        slot
        for slot in selected.selected
        if slot.extension.name == "avx2"
        and slot.primitive.signature == signature
        and all(
            slot.primitive.attributes.get(key) == value
            for key, value in expected_attributes.items()
        )
    )


def _lower(
    catalog: Catalog,
    slot: SelectedImplementation,
) -> LoweredSpecialization:
    result = Lowerer().lower(
        slot,
        catalog,
        create_backend_dialect(catalog, "rust"),
    )
    assert result.specialization is not None, result.diagnostics
    return result.specialization


@pytest.mark.parametrize(
    ("primitive_name", "signature", "attributes", "expected"),
    (
        (
            "shift_left",
            "v:=(v,s)",
            {},
            ResolvedPrimitiveOverload("count_distribution", "uniform", True),
        ),
        (
            "shift_left",
            "v:=(v,sImm)",
            {},
            ResolvedPrimitiveOverload("count_distribution", "uniform", True),
        ),
        (
            "shift_left",
            "v:=(m,v,sImm)",
            {"mask": "pass_through"},
            ResolvedPrimitiveOverload("count_distribution", "uniform", True),
        ),
        (
            "shift_left",
            "v:=(v,v)",
            {},
            ResolvedPrimitiveOverload("count_distribution", "per_lane", False),
        ),
        (
            "shift_left_wrapping",
            "v:=(v,s)",
            {},
            ResolvedPrimitiveOverload("count_distribution", "uniform", True),
        ),
        (
            "shift_left_wrapping",
            "v:=(v,v)",
            {},
            ResolvedPrimitiveOverload("count_distribution", "per_lane", False),
        ),
        (
            "store",
            "void:=(ptr,v)",
            {"aligned": "false"},
            ResolvedPrimitiveOverload("payload_extent", "vector", True),
        ),
        (
            "store",
            "void:=(ptr,s)",
            {"aligned": "false"},
            ResolvedPrimitiveOverload("payload_extent", "scalar", False),
        ),
    ),
)
def test_lowering_carries_resolved_overload_matrix(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    signature: str,
    attributes: dict[str, str],
    expected: ResolvedPrimitiveOverload,
) -> None:
    slot = _selected_slot(
        catalog,
        machine_profiles,
        primitive_name,
        signature,
        attributes=attributes,
    )

    spec = _lower(catalog, slot)

    assert spec.primitive_semantics.overload == expected
    assert spec.primitive_semantics.operation is slot.primitive.operation
    assert spec.primitive_semantics.memory is slot.primitive.memory


@pytest.mark.parametrize(
    ("primitive_name", "signature", "attributes", "field"),
    (
        ("add", "v:=(v,v)", {}, "arithmetic"),
        ("load", "v:=cptr", {"aligned": "false"}, "memory"),
        (
            "reinterpret",
            "v:=v",
            {"cast": "reinterpret"},
            "conversion",
        ),
        ("shift_left_wrapping", "v:=(v,s)", {}, "shift"),
    ),
)
def test_lowering_carries_promoted_contract_objects(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
    primitive_name: str,
    signature: str,
    attributes: dict[str, str],
    field: str,
) -> None:
    slot = _selected_slot(
        catalog,
        machine_profiles,
        primitive_name,
        signature,
        attributes=attributes,
    )

    spec = _lower(catalog, slot)

    assert getattr(spec.primitive_semantics, field) is getattr(slot.primitive, field)
    assert spec.primitive_semantics.operation is slot.primitive.operation


def test_lowered_semantics_do_not_depend_on_target_body_text(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    slot = _selected_slot(
        catalog,
        machine_profiles,
        "shift_left",
        "v:=(v,s)",
    )
    original = _lower(catalog, slot)
    changed_slot = replace(
        slot,
        implementation=replace(
            slot.implementation,
            body_text="complete(data);",
            body_source=None,
            variants=(
                ImplementationVariant(
                    name="alternate",
                    body_text="complete(data);",
                ),
            ),
        ),
    )

    changed = _lower(catalog, changed_slot)

    assert changed.body_text != original.body_text
    assert changed.variant_names == ("alternate",)
    assert changed.primitive_semantics == original.primitive_semantics


def test_specialization_replacement_preserves_lowered_semantics(
    catalog: Catalog,
    machine_profiles: Mapping[str, MachineProfile],
) -> None:
    spec = _lower(
        catalog,
        _selected_slot(catalog, machine_profiles, "add", "v:=(v,v)"),
    )

    renamed = replace(spec, primitive_name="renamed_for_projection")

    assert renamed.primitive_semantics is spec.primitive_semantics
