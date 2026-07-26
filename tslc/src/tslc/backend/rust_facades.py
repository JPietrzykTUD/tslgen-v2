"""Rust dataparallel primitive facade rendering."""

from __future__ import annotations

from collections.abc import Mapping

from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacade,
    DataparallelPrimitiveFacadeKind,
    classify_dataparallel_primitive_facade,
)
from tslc.backend.rust_names import (
    rust_primitive_tag_name,
    rust_primitive_trait_name,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def rust_algorithm_primitive_facades(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    *,
    reserved_names: frozenset[str],
) -> str:
    parts: list[str] = []
    for primitive_name in sorted(by_primitive):
        function_name = rust_raw_identifier(primitive_name)
        if function_name in reserved_names:
            continue
        specs = by_primitive[primitive_name]
        facade = classify_dataparallel_primitive_facade(primitive_name, specs)
        if facade is None:
            continue
        if facade.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY:
            parts.append(_rust_algorithm_memory_facade(function_name, facade))
            continue
        shape = facade.shape
        source_type = "FromT" if shape.target is not None else "T"
        source_vec = f"<Policy as VectorFor<Profile, {source_type}>>::Vec"
        target_vec = f"ReboundBase<{source_vec}, ToT>" if shape.target is not None else None
        params = [
            "        _policy: Policy,",
            *(
                f"        {name}: {_rust_facade_param_type(kind, source_vec, target_vec)},"
                for name, kind in zip(shape.param_names, shape.param_kinds)
            ),
        ]
        args = ", ".join(shape.param_names)
        trait_name = rust_primitive_trait_name(primitive_name)
        result_type = _rust_facade_result_type(shape.result_kind, target_vec or source_vec)
        function_generics = "Policy, FromT, ToT" if shape.target is not None else "Policy, T"
        target_trait_arg = f"<{target_vec}>" if target_vec is not None else ""
        vec_bound = (
            f"RebindBase<ToT> + super::detail::primitives::{trait_name}{target_trait_arg}"
            if target_vec is not None
            else f"super::detail::primitives::{trait_name}"
        )
        parts.append(
            "\n".join(
                (
                    f"    pub fn {function_name}<{function_generics}>(",
                    *params,
                    f"    ) -> {result_type}",
                    "    where",
                    f"        Policy: VectorFor<Profile, {source_type}>,",
                    f"        {source_vec}: {vec_bound},",
                    "    {",
                    f"        super::{function_name}::<{source_vec}{', ' + target_vec if target_vec is not None else ''}>({args})",
                    "    }",
                )
            )
        )
    return "\n\n".join(parts)


def rust_algorithm_primitive_facades_require_rebind(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    *,
    reserved_names: frozenset[str],
) -> bool:
    """Whether the selected algorithm facades include a base-type conversion."""

    for primitive_name in sorted(by_primitive):
        if rust_raw_identifier(primitive_name) in reserved_names:
            continue
        facade = classify_dataparallel_primitive_facade(
            primitive_name, by_primitive[primitive_name]
        )
        if (
            facade is not None
            and facade.kind is not DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
            and facade.shape.target is not None
        ):
            return True
    return False


def _rust_algorithm_memory_facade(
    function_name: str,
    facade: DataparallelPrimitiveFacade,
) -> str:
    del facade
    if function_name == "load":
        return "\n".join(
            (
                "    pub unsafe fn load<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *const T,",
                "    ) -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                "        <Policy as VectorFor<Profile, T>>::Vec:",
                "            super::detail::primitives::LoadImpl<ALIGNED>,",
                "    {",
                "        unsafe { super::load::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED>(ptr) }",
                "    }",
            )
        )
    if function_name == "store":
        return "\n".join(
            (
                "    pub unsafe fn store<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *mut T,",
                "        data: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType,",
                "    )",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                "        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:",
                "            super::detail::primitives::StoreImplArg<",
                "                <Policy as VectorFor<Profile, T>>::Vec,",
                "                ALIGNED,",
                "            >,",
                "    {",
                "        unsafe { super::store::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED, _>(ptr, data) }",
                "    }",
            )
        )
    raise AssertionError(f"unsupported Rust memory facade: {function_name}")


def _rust_facade_result_type(result_kind: str, vec: str) -> str:
    return RUST_SIGNATURE_TYPES.owner_type(result_kind, owner=f"<{vec} as SimdVector>")


def _rust_facade_param_type(param_kind: str, vec: str, target_vec: str | None) -> str:
    if (
        DEFAULT_SUPPORT_POLICY.is_target_vector_parameter_kind(param_kind)
        and target_vec is not None
    ):
        vec = target_vec
    return RUST_SIGNATURE_TYPES.parameter_type(
        param_kind, owner=f"<{vec} as SimdVector>"
    )


__all__ = (
    "rust_algorithm_primitive_facades",
    "rust_algorithm_primitive_facades_require_rebind",
    "rust_primitive_tag_name",
)
