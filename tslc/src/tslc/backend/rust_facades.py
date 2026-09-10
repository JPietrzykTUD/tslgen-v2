"""Rust dataparallel primitive facade rendering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tslc.backend.checked_api import public_call_requires_unsafe
from tslc.backend.primitive_facade import (
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


@dataclass(frozen=True, slots=True)
class RustAlgorithmPrimitiveFacade:
    """One fully classified primitive facade ready for Rust formatting."""

    primitive_name: str
    function_name: str
    trait_name: str
    caller_unsafe: bool
    kind: DataparallelPrimitiveFacadeKind
    parameter_names: tuple[str, ...] = ()
    parameter_kinds: tuple[str, ...] = ()
    result_kind: str | None = None
    has_target: bool = False
    memory_access: MemoryAccess | None = None
    overload_parameter_positions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.primitive_name or not self.function_name or not self.trait_name:
            raise ValueError("Rust primitive facade records require identities")
        is_memory = self.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
        if is_memory != (self.memory_access is not None):
            raise ValueError("Rust memory facade records require typed memory access")
        if is_memory and (
            self.parameter_names
            or self.parameter_kinds
            or self.result_kind is not None
            or self.has_target
        ):
            raise ValueError("Rust memory facade records retain only memory facts")
        if not is_memory and (
            len(self.parameter_names) != len(self.parameter_kinds)
            or self.result_kind is None
            or self.overload_parameter_positions
        ):
            raise ValueError("Rust primitive facade records require a complete signature")
        if self.has_target != (
            self.kind is DataparallelPrimitiveFacadeKind.TARGET_BASE_CONVERSION
        ):
            raise ValueError("Rust facade target binding disagrees with its kind")
        if (
            self.memory_access is MemoryAccess.READ
            and self.overload_parameter_positions
        ):
            raise ValueError("Rust memory reads cannot dispatch an overload")

    @property
    def requires_rebind(self) -> bool:
        return self.has_target


def plan_rust_algorithm_primitive_facades(
    by_primitive: Mapping[str, tuple[LoweredSpecialization, ...]],
    *,
    reserved_names: frozenset[str],
) -> tuple[RustAlgorithmPrimitiveFacade, ...]:
    """Classify algorithm primitive facades before target formatting."""

    records: list[RustAlgorithmPrimitiveFacade] = []
    for primitive_name in sorted(by_primitive):
        function_name = rust_raw_identifier(primitive_name)
        if function_name in reserved_names:
            continue
        specs = by_primitive[primitive_name]
        facade = classify_dataparallel_primitive_facade(primitive_name, specs)
        if facade is None:
            continue
        records.append(
            RustAlgorithmPrimitiveFacade(
                primitive_name=primitive_name,
                function_name=function_name,
                trait_name=rust_primitive_trait_name(primitive_name),
                caller_unsafe=public_call_requires_unsafe(specs),
                kind=facade.kind,
                parameter_names=(
                    ()
                    if facade.kind
                    is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
                    else facade.shape.param_names
                ),
                parameter_kinds=(
                    ()
                    if facade.kind
                    is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
                    else facade.shape.param_kinds
                ),
                result_kind=(
                    None
                    if facade.kind
                    is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
                    else facade.shape.result_kind
                ),
                has_target=(
                    facade.kind
                    is not DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY
                    and facade.shape.target is not None
                ),
                memory_access=facade.memory_access,
                overload_parameter_positions=facade.overload_parameter_positions,
            )
        )
    return tuple(records)


def rust_algorithm_primitive_facades(
    facades: tuple[RustAlgorithmPrimitiveFacade, ...],
) -> str:
    parts: list[str] = []
    for facade in facades:
        function_name = facade.function_name
        if facade.kind is DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY:
            parts.append(_rust_algorithm_memory_facade(function_name, facade))
            continue
        source_type = "FromT" if facade.has_target else "T"
        source_vec = f"<Policy as VectorFor<Profile, {source_type}>>::Vec"
        target_vec = f"ReboundBase<{source_vec}, ToT>" if facade.has_target else None
        params = [
            "        _policy: Policy,",
            *(
                f"        {name}: {_rust_facade_param_type(kind, source_vec, target_vec)},"
                for name, kind in zip(
                    facade.parameter_names, facade.parameter_kinds
                )
            ),
        ]
        args = ", ".join(facade.parameter_names)
        result_type = _rust_facade_result_type(
            facade.result_kind or "", target_vec or source_vec
        )
        function_generics = "Policy, FromT, ToT" if facade.has_target else "Policy, T"
        target_trait_arg = f"<{target_vec}>" if target_vec is not None else ""
        vec_bound = (
            f"RebindBase<ToT> + super::detail::primitives::{facade.trait_name}{target_trait_arg}"
            if target_vec is not None
            else f"super::detail::primitives::{facade.trait_name}"
        )
        parts.append(
            "\n".join(
                (
                    f"    pub {'unsafe ' if facade.caller_unsafe else ''}fn "
                    f"{function_name}<{function_generics}>(",
                    *params,
                    f"    ) -> {result_type}",
                    "    where",
                    f"        Policy: VectorFor<Profile, {source_type}>,",
                    f"        {source_vec}: {vec_bound},",
                    "    {",
                    (
                        "        unsafe { "
                        f"super::{function_name}::<{source_vec}"
                        f"{', ' + target_vec if target_vec is not None else ''}>({args})"
                        " }"
                        if facade.caller_unsafe
                        else f"        super::{function_name}::<{source_vec}"
                        f"{', ' + target_vec if target_vec is not None else ''}>({args})"
                    ),
                    "    }",
                )
            )
        )
    return "\n\n".join(parts)


def _rust_algorithm_memory_facade(
    function_name: str,
    facade: RustAlgorithmPrimitiveFacade,
) -> str:
    trait_name = facade.trait_name
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
    "RustAlgorithmPrimitiveFacade",
    "plan_rust_algorithm_primitive_facades",
    "rust_algorithm_primitive_facades",
    "rust_primitive_tag_name",
)
