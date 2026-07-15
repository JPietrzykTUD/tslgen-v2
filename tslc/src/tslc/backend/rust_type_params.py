"""Rust bounds and dispatch keys for lowered SIMD type parameters."""

from __future__ import annotations

from dataclasses import replace

from tslc.backend.rust_names import rust_primitive_trait_name
from tslc.lower.lowerer import LoweredSpecialization, LoweredTypeParam
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def with_consistent_type_param_bounds(
    specializations: tuple[LoweredSpecialization, ...],
) -> tuple[LoweredSpecialization, ...]:
    """Give every Rust impl the public trait's complete type-parameter bounds.

    Different implementation bodies can call different primitives through the
    same SIMD type parameter. Rust requires every implementation of the shared
    trait to repeat all bounds from that trait's type-parameter declaration,
    including native implementations that do not use a portable fallback's
    dependency themselves.
    """

    bounds_by_name: dict[str, list[str]] = {}
    for spec in specializations:
        for param in spec.type_params:
            merged = bounds_by_name.setdefault(param.name, [])
            for bound in param.bounds:
                if bound not in merged:
                    merged.append(bound)

    if not bounds_by_name:
        return specializations
    return tuple(
        replace(
            spec,
            type_params=tuple(
                replace(param, bounds=tuple(bounds_by_name[param.name]))
                for param in spec.type_params
            ),
        )
        for spec in specializations
    )


def type_param_decls(
    shape: LoweredSpecialization,
    *,
    trait_prefix: str = "",
) -> list[str]:
    """Render generic declarations for free SIMD type parameters."""

    decls: list[str] = []
    for param in shape.type_params:
        traits = [
            "StaticSimdVector",
            *(f"{trait_prefix}{rust_primitive_trait_name(bound)}" for bound in param.bounds),
        ]
        decls.append(f"{param.name}: {' + '.join(traits)}")
    return decls


def index_where(
    shape: LoweredSpecialization,
    *,
    impl_register: str | None = None,
    base_dispatch: str = "none",
) -> str:
    """Render constraints for index vectors and specialized base dispatch."""

    clauses = type_param_where_clauses(shape, base_dispatch=base_dispatch)
    if not clauses:
        return ""
    if impl_register is not None and _needs_index_base_constraint(shape):
        index = shape.type_params[0].name
        clauses.insert(0, f"{index}: SimdVector<RegisterType = {impl_register}>")
    return " where " + ", ".join(clauses)


def type_param_where_clauses(
    shape: LoweredSpecialization,
    *,
    base_dispatch: str,
) -> list[str]:
    clauses: list[str] = []
    if _needs_index_base_constraint(shape):
        clauses.append(f"{shape.type_params[0].name}::BaseType: IndexBase")
    clauses.extend(_base_dispatch_clauses(shape, mode=base_dispatch))
    return clauses


def type_param_names(shape: LoweredSpecialization) -> list[str]:
    return [param.name for param in shape.type_params]


def type_param_base_key_decls(shape: LoweredSpecialization) -> list[str]:
    return [_base_key_param_name(param) for param in _specialized_params(shape)]


def type_param_base_key_args(
    shape: LoweredSpecialization,
    *,
    mode: str,
) -> list[str]:
    args: list[str] = []
    for param in _specialized_params(shape):
        if mode == "projection":
            args.append(f"<{param.name}::BaseType as BaseTypeDispatch>::Key")
        elif mode == "concrete":
            args.append(rust_base_dispatch_key_tag(param.base_type_binding))
    return args


def rust_base_dispatch_key_tag(base_tag: str | None) -> str:
    mapping = {
        "si8": "BaseSi8",
        "si16": "BaseSi16",
        "si32": "BaseSi32",
        "si64": "BaseSi64",
        "ui8": "BaseUi8",
        "ui16": "BaseUi16",
        "ui32": "BaseUi32",
        "ui64": "BaseUi64",
        "f32": "BaseF32",
        "f64": "BaseF64",
    }
    return mapping.get(base_tag or "", "()")


def _needs_index_base_constraint(shape: LoweredSpecialization) -> bool:
    if not shape.type_params:
        return False
    index = shape.type_params[0].name
    return (
        DEFAULT_SUPPORT_POLICY.index_vector_kind in shape.param_kinds
        or any(
            override is not None and f"{index}::BaseType" in override
            for override in shape.effective_param_type_overrides
        )
    )


def _base_dispatch_clauses(
    shape: LoweredSpecialization,
    *,
    mode: str,
) -> list[str]:
    clauses: list[str] = []
    for param in _specialized_params(shape):
        if mode == "hidden":
            clauses.append(
                f"{param.name}::BaseType: BaseTypeDispatch<Key = "
                f"{_base_key_param_name(param)}>"
            )
        elif mode == "projection":
            clauses.append(f"{param.name}::BaseType: BaseTypeDispatch")
        elif mode == "concrete":
            clauses.append(
                f"{param.name}::BaseType: BaseTypeDispatch<Key = "
                f"{rust_base_dispatch_key_tag(param.base_type_binding)}>"
            )
    return clauses


def _specialized_params(
    shape: LoweredSpecialization,
) -> tuple[LoweredTypeParam, ...]:
    return tuple(param for param in shape.type_params if param.specialize_base)


def _base_key_param_name(param: LoweredTypeParam) -> str:
    return f"{param.name}BaseKey"
