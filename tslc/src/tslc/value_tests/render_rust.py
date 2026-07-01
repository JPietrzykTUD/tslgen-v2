"""Render Rust value-test plans."""

from __future__ import annotations

from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug
from tslc.value_tests._render_rust_conversion import (
    _convert,
    _extension_extract,
    _extension_insert,
    _load_convert,
    _repr_cast,
)
from tslc.value_tests._render_rust_core import (
    _array_to_vector,
    _broadcast,
    _compile_only,
    _generic_golden,
    _immediate,
    _lane_list,
    _mask_logic,
    _mask_result,
    _mask_store,
    _mask_to_vector,
    _masked,
    _reduction,
    _scalar_result,
    _scalar_vector,
    _vector_to_array,
)
from tslc.value_tests._render_rust_memory import (
    _indexed_load,
    _indexed_store,
    _load,
    _mask_pointer_load,
    _masked_pointer_load,
    _masked_pointer_store,
    _memory_copy,
    _pointer_free,
    _pointer_lifetime,
    _scalar_pointer_load,
    _store,
    _stream,
)
from tslc.value_tests.model import ValueTestCasePlan, ValueTestProfilePlan
from tslc.value_tests.renderer_capability import ValueTestRendererCapability


def render_rust_values_file(
    profiles: tuple[ValueTestProfilePlan, ...], assets: RenderAssets
) -> str:
    modules = []
    for profile in profiles:
        if not profile.cases:
            continue
        profile_slug = slug(profile.profile_name)
        body = "\n\n".join(_render_case(case) for case in profile.cases)
        modules.append(
            assets.fill(
                "rust_value_tests_profile.rs.tmpl",
                profile_slug=profile_slug,
                body=body,
            ).rstrip()
        )
    profile_modules = "\n\n" + "\n\n".join(modules) if modules else "\n"
    source = assets.fill(
        "rust_value_tests.rs.tmpl",
        profile_modules=profile_modules,
    )
    return "\n".join(line.rstrip() for line in source.splitlines()) + "\n"


def _render_case(case: ValueTestCasePlan) -> str:
    return RUST_VALUE_TEST_RENDERER.render_case(case)


RUST_VALUE_TEST_RENDERER = ValueTestRendererCapability(
    backend_id="rust",
    case_renderers={
        "array_to_vector": _array_to_vector,
        "broadcast": _broadcast,
        "compile_only": _compile_only,
        "convert": _convert,
        "extension_extract": _extension_extract,
        "extension_insert": _extension_insert,
        "generic_golden": _generic_golden,
        "immediate": _immediate,
        "indexed_load": _indexed_load,
        "indexed_store": _indexed_store,
        "lane_list": _lane_list,
        "load": _load,
        "load_convert": _load_convert,
        "mask_logic": _mask_logic,
        "mask_pointer_load": _mask_pointer_load,
        "mask_result": _mask_result,
        "mask_store": _mask_store,
        "mask_to_vector": _mask_to_vector,
        "masked": _masked,
        "masked_pointer_load": _masked_pointer_load,
        "masked_pointer_store": _masked_pointer_store,
        "memory_copy": _memory_copy,
        "pointer_free": _pointer_free,
        "pointer_lifetime": _pointer_lifetime,
        "reduction": _reduction,
        "repr_cast": _repr_cast,
        "scalar_pointer_load": _scalar_pointer_load,
        "scalar_result": _scalar_result,
        "scalar_vector": _scalar_vector,
        "store": _store,
        "stream": _stream,
        "vector_to_array": _vector_to_array,
    },
)

RUST_VALUE_TEST_SUPPORT = RUST_VALUE_TEST_RENDERER.backend_support()


__all__ = [
    "RUST_VALUE_TEST_RENDERER",
    "RUST_VALUE_TEST_SUPPORT",
    "render_rust_values_file",
]
