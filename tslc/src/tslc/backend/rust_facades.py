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
from tslc.catalog.memory import MemoryAccess
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
    trait_name = rust_primitive_trait_name(facade.primitive_name)
    if facade.memory_access is MemoryAccess.READ:
        return "\n".join(
            (
                f"    pub unsafe fn {function_name}<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *const T,",
                "    ) -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                "        <Policy as VectorFor<Profile, T>>::Vec:",
                f"            super::detail::primitives::{trait_name}<ALIGNED>,",
                "    {",
                f"        unsafe {{ super::{function_name}::<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED>(ptr) }}",
                "    }",
            )
        )
    if facade.memory_access is MemoryAccess.WRITE:
        if facade.overload_parameter_positions:
            bound = (
                "        <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType:\n"
                f"            super::detail::primitives::{trait_name}Arg<\n"
                "                <Policy as VectorFor<Profile, T>>::Vec,\n"
                "                ALIGNED,\n"
                "            >,"
            )
            call_generics = (
                "<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED, _>"
            )
        else:
            bound = (
                "        <Policy as VectorFor<Profile, T>>::Vec:\n"
                f"            super::detail::primitives::{trait_name}<ALIGNED>,"
            )
            call_generics = (
                "<<Policy as VectorFor<Profile, T>>::Vec, ALIGNED>"
            )
        return "\n".join(
            (
                f"    pub unsafe fn {function_name}<Policy, T, const ALIGNED: bool>(",
                "        _policy: Policy,",
                "        ptr: *mut T,",
                "        data: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType,",
                "    )",
                "    where",
                "        Policy: VectorFor<Profile, T>,",
                bound,
                "    {",
                f"        unsafe {{ super::{function_name}::{call_generics}(ptr, data) }}",
                "    }",
            )
        )
    raise ValueError("Rust memory facade has no supported typed memory access")


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
