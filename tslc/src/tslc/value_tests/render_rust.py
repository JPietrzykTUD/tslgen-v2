"""Render Rust value-test plans."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.compiler_assets import RenderAssets
from tslc.render._common import slug
from tslc.value_tests._render_rust_conversion import (
    _convert,
    _differential,
    _extension_extract,
    _extension_insert,
    _extension_result,
    _load_convert,
    _lane_convert,
    _repr_cast,
    _target_imask,
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
    _runtime_failure,
    _scalar_result,
    _scalar_vector,
    _status_pointer,
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
from tslc.value_tests.model import (
    ValueTestCasePlan,
    ValueTestProfileCaseExclusion,
    ValueTestProfilePlan,
)
from tslc.value_tests.renderer_capability import ValueTestRendererCapability


def render_rust_values_file(
    profiles: tuple[ValueTestProfilePlan, ...],
    assets: RenderAssets,
    *,
    profile_cfgs: Mapping[str, str] | None = None,
    profile_modules: Mapping[str, str] | None = None,
) -> str:
    profile_cfgs = profile_cfgs or {}
    profile_modules = profile_modules or {}
    modules = []
    for profile in profiles:
        if not profile.runner_cases:
            continue
        profile_slug = slug(profile.profile_name)
        body = "\n\n".join(_render_case(case) for case in profile.runner_cases)
        modules.append(
            assets.fill(
                "rust_value_tests_profile.rs.tmpl",
                profile_slug=profile_slug,
                profile_module=profile_modules.get(
                    profile.profile_name, f"tsl_{profile_slug}"
                ),
                target_cfg=profile_cfgs.get(profile.profile_name, "all()"),
                body=body,
            ).rstrip()
        )
    rendered_profile_modules = "\n\n" + "\n\n".join(modules) if modules else "\n"
    source = assets.fill(
        "rust_value_tests.rs.tmpl",
        profile_modules=rendered_profile_modules,
    )
    return "\n".join(line.rstrip() for line in source.splitlines()) + "\n"


def _render_case(case: ValueTestCasePlan) -> str:
    return RUST_VALUE_TEST_RENDERER.render_case(case)


RUST_VALUE_TEST_RENDERER = ValueTestRendererCapability(
    backend_id="rust",
    supports_differential=True,
    overload_inference_placeholders=1,
    isolated_case_kinds=frozenset({"compile_failure"}),
    profile_case_exclusions=(
        ValueTestProfileCaseExclusion(
            profile_family="wasm32",
            case_kind="runtime_failure",
            reason=(
                "the generated wasm32 Rust target uses aborting panics, so "
                "catch_unwind cannot observe the runtime-failure marker"
            ),
        ),
    ),
    case_renderers={
        "array_to_vector": _array_to_vector,
        "broadcast": _broadcast,
        "compile_only": _compile_only,
        "convert": _convert,
        "differential": _differential,
        "extension_extract": _extension_extract,
        "extension_insert": _extension_insert,
        "extension_result": _extension_result,
        "generic_golden": _generic_golden,
        "immediate": _immediate,
        "indexed_load": _indexed_load,
        "indexed_store": _indexed_store,
        "lane_list": _lane_list,
        "load": _load,
        "load_convert": _load_convert,
        "lane_convert": _lane_convert,
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
        "runtime_failure": _runtime_failure,
        "repr_cast": _repr_cast,
        "scalar_pointer_load": _scalar_pointer_load,
        "scalar_result": _scalar_result,
        "scalar_vector": _scalar_vector,
        "store": _store,
        "target_imask": _target_imask,
        "status_pointer": _status_pointer,
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
