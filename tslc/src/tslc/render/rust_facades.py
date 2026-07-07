"""Rust dataparallel primitive facade rendering."""

from __future__ import annotations

import re
from collections.abc import Mapping

from tslc.backend.primitive_facade import (
    DataparallelPrimitiveFacade,
    DataparallelPrimitiveFacadeKind,
    classify_dataparallel_primitive_facade,
)
from tslc.backend.rust_translation import rust_raw_identifier
from tslc.lower.lowerer import LoweredSpecialization


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


def rust_public_function_names(source: str) -> frozenset[str]:
    return frozenset(re.findall(r"pub (?:unsafe )?fn ([A-Za-z_][A-Za-z0-9_]*)", source))


def _rust_facade_result_type(result_kind: str, vec: str) -> str:
    vec = f"<{vec} as SimdVector>"
    if result_kind == "v":
        return f"{vec}::RegisterType"
    if result_kind == "m":
        return f"{vec}::MaskType"
    if result_kind == "s":
        return f"{vec}::BaseType"
    if result_kind == "usize":
        return "usize"
    raise AssertionError(f"unsupported Rust facade result kind: {result_kind}")


def _rust_facade_param_type(param_kind: str, vec: str, target_vec: str | None) -> str:
    vec = f"<{vec} as SimdVector>"
    if param_kind == "v":
        return f"{vec}::RegisterType"
    if param_kind == "vt" and target_vec is not None:
        return f"<{target_vec} as SimdVector>::RegisterType"
    if param_kind == "m":
        return f"{vec}::MaskType"
    if param_kind == "s":
        return f"{vec}::BaseType"
    raise AssertionError(f"unsupported Rust facade parameter kind: {param_kind}")


def rust_primitive_trait_name(primitive_name: str) -> str:
    return f"{primitive_name[:1].upper()}{primitive_name[1:]}Impl"


def rust_primitive_tag_name(primitive_name: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in primitive_name.split("_"))


__all__ = (
    "rust_algorithm_primitive_facades",
    "rust_primitive_tag_name",
    "rust_public_function_names",
)
