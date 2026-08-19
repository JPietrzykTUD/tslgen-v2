"""Shared fixtures and helpers for extension selection/lowering tests."""

from __future__ import annotations

import pytest

from tslc.backend.registry import create_backend_dialect
from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import Selector
from tslc.support_policy import DEFAULT_SUPPORT_POLICY
from tslc.support_policy_views import concrete_target_candidates

_TYPES = ("si32", "ui32", "f32", "f64")
_ALL_ARITH_TYPES = (
    "si8",
    "ui8",
    "si16",
    "ui16",
    "si32",
    "ui32",
    "si64",
    "ui64",
    "f32",
    "f64",
)


def _slots(catalog, profile, primitive):
    return Selector().select_profile(
        catalog, profile, primitive, _TYPES, backend_id="cpp"
    ).selected


def _by_key(catalog, profile, primitive):
    result = {}
    for slot in _slots(catalog, profile, primitive):
        if slot.primitive.mask_mode is not None:
            continue
        key = (slot.type_tag, slot.extension.name)
        current = result.get(key)
        if current is None or len(slot.primitive.parameters) < len(
            current.primitive.parameters
        ):
            result[key] = slot
    return result


def _assert_x86_shift_register_path(cpp, expected_fragment: str) -> None:
    assert cpp is not None
    assert expected_fragment in cpp.body_text
    if expected_fragment == "::tsl::extract<Vec":
        assert "::tsl::insert<" in cpp.body_text
        assert "_mm" not in cpp.body_text
    assert "to_array" not in cpp.body_text
    assert "from_array" not in cpp.body_text


def _wasm_slot(catalog: Catalog, machine_profiles, primitive: str, type_tag: str):
    return next(
        slot
        for slot in Selector()
        .select_profile(
            catalog,
            machine_profiles["wasm32-simd128"],
            primitive,
            (type_tag,),
            backend_id="cpp",
        )
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.mask_mode is None
    )


__all__ = (
    'pytest',
    'create_backend_dialect',
    'Catalog',
    'parse_signature',
    'Lowerer',
    'Selector',
    'DEFAULT_SUPPORT_POLICY',
    'concrete_target_candidates',
    '_TYPES',
    '_ALL_ARITH_TYPES',
    '_slots',
    '_by_key',
    '_assert_x86_shift_register_path',
    '_wasm_slot',
)
