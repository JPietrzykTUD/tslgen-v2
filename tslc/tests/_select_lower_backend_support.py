"""Shared fixtures and helpers for backend selection/lowering tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.backend.cpp import CppBackend
from tslc.backend.registry import create_backend_dialect
from tslc.backend.rust import RustBackend
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
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import Lowerer
from tslc.select.selector import (
    SelectedImplementation,
    Selector,
    SimdTypeBaseBinding,
)

_TYPES = ("si32", "ui32", "f32", "f64")


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
    result = {}
    for slot in _slots(catalog, profile, primitive):
        if slot.primitive.attributes.get("mask") is not None:
            continue
        key = (slot.type_tag, slot.extension.name)
        current = result.get(key)
        if current is None or len(slot.primitive.parameters) < len(
            current.primitive.parameters
        ):
            result[key] = slot
    return result


def _wasm_slot(catalog: Catalog, machine_profiles, primitive: str, type_tag: str):
    return next(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["wasm32-simd128"], primitive, (type_tag,))
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.attributes.get("mask") is None
    )


def _wasm_unmasked_slots(
    catalog: Catalog,
    machine_profiles,
    primitive: str,
    type_tag: str,
):
    return tuple(
        slot
        for slot in Selector()
        .select_profile(catalog, machine_profiles["wasm32-simd128"], primitive, (type_tag,))
        .selected
        if slot.extension.name == "wasm128"
        and slot.primitive.attributes.get("mask") is None
    )


class _RecordingSyntax:
    def __init__(self, inner) -> None:  # noqa: ANN001
        self.inner = inner
        self.borrowed_call_arg_prefix = inner.borrowed_call_arg_prefix
        self.param_type_calls: list[tuple[bool, bool]] = []

    def frame_return(self, value):  # noqa: ANN001, ANN201
        return self.inner.frame_return(value)

    def render_call(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        return self.inner.render_call(*args, **kwargs)

    def render_pointer_cast(self, inner, *, is_const, operand):  # noqa: ANN001, ANN201
        return self.inner.render_pointer_cast(inner, is_const=is_const, operand=operand)

    def render_param_type(  # noqa: ANN001, ANN201
        self,
        value,
        *,
        is_pointer: bool = False,
        is_const: bool = False,
    ):
        self.param_type_calls.append((is_pointer, is_const))
        return self.inner.render_param_type(
            value,
            is_pointer=is_pointer,
            is_const=is_const,
        )

    def render_assume_aligned(self, expr, alignment):  # noqa: ANN001, ANN201
        return self.inner.render_assume_aligned(expr, alignment)

    def render_compile_switch(self, selector, arms):  # noqa: ANN001, ANN201
        return self.inner.render_compile_switch(selector, arms)

    def render_unsafe_block(self, body: str) -> str:
        return self.inner.render_unsafe_block(body)


class _RecordingDialect:
    def __init__(self, inner, syntax: _RecordingSyntax) -> None:  # noqa: ANN001
        self.backend_id = inner.backend_id
        self.types = inner.types
        self.intrinsics = inner.intrinsics
        self.templates = inner.templates
        self.syntax = syntax


def _generic_slots(catalog, machine_profiles, primitive, type_tag):
    return [
        s
        for s in Selector()
        .select_profile(catalog, machine_profiles["avx2"], primitive, (type_tag,))
        .selected
        if s.extension.name == "generic"
        and s.type_tag == type_tag
        and s.primitive.attributes.get("mask") is None
    ]


__all__ = (
    'replace',
    'pytest',
    'CppBackend',
    'create_backend_dialect',
    'RustBackend',
    'Catalog',
    'Extension',
    'GenericParam',
    'GenericParamBaseWidthConstraint',
    'Implementation',
    'Primitive',
    'ExtensionFamilyCapability',
    'ProfileFamilyCapability',
    'TargetFamilyCatalog',
    'ImplementationState',
    'Lowerer',
    'SelectedImplementation',
    'Selector',
    'SimdTypeBaseBinding',
    '_TYPES',
    '_scalar_target_families',
    '_slots',
    '_by_key',
    '_wasm_slot',
    '_wasm_unmasked_slots',
    '_RecordingSyntax',
    '_RecordingDialect',
    '_generic_slots',
)
