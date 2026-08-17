"""Shared fixtures and helpers for core selection/lowering tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.rust import RustBackend
from tslc.backend.registry import create_backend_dialect
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import (
    Catalog,
    Extension,
    GenericParam,
    GenericParamBaseWidthConstraint,
    Implementation,
    Primitive,
)
from tslc.catalog.target_families import (
    ExtensionFamilyCapability,
    ProfileFamilyCapability,
    TargetFamilyCatalog,
)
from tslc.catalog.signatures import parse_signature
from tslc.lower import lowerer as lowerer_module
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import Lowerer
from tslc.lower.target_vectors import TargetVector, resolve_target_vector
from tslc.select.selector import SelectedImplementation, Selector, SimdTypeBaseBinding
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


def _scalar_target_families() -> TargetFamilyCatalog:
    return TargetFamilyCatalog(
        known_extension_families=frozenset({"scalar"}),
        universal_extension_families=frozenset({"scalar"}),
        extension_families={
            "scalar": ExtensionFamilyCapability(
                "scalar",
                implementation_fallback=True,
                requires_declared_vector_register=False,
            )
        },
        profile_families={"generic": ProfileFamilyCapability("generic")},
    )


def _slots(catalog, profile, primitive):
    return Selector().select_profile(
        catalog, profile, primitive, _TYPES, backend_id="cpp"
    ).selected


def _by_key(catalog, profile, primitive):
    # The ordinary specs keyed by (type, ext). A dual source name can also select
    # masked-policy variants and explicit leading-mask overloads (same key until
    # emitted-name finalization), so prefer the declaration with fewer parameters.
    # Mask-consuming primitives such as to_integral remain visible when they are the
    # only declaration for the name.
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


__all__ = (
    'replace',
    'pytest',
    'CppBackend',
    'RustBackend',
    'create_backend_dialect',
    'MachineProfile',
    'Catalog',
    'Extension',
    'GenericParam',
    'GenericParamBaseWidthConstraint',
    'Implementation',
    'Primitive',
    'ExtensionFamilyCapability',
    'ProfileFamilyCapability',
    'TargetFamilyCatalog',
    'parse_signature',
    'lowerer_module',
    'ImplementationState',
    'Lowerer',
    'TargetVector',
    'resolve_target_vector',
    'SelectedImplementation',
    'Selector',
    'SimdTypeBaseBinding',
    'DEFAULT_SUPPORT_POLICY',
    'concrete_target_candidates',
    '_TYPES',
    '_ALL_ARITH_TYPES',
    '_scalar_target_families',
    '_slots',
    '_by_key',
    '_assert_x86_shift_register_path',
)
