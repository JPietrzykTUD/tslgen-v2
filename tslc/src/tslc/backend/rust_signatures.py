"""Rust type, generic, parameter, and call-argument spelling."""

from __future__ import annotations

from tslc.backend.rust_type_params import (
    type_param_decls,
    type_param_names,
)
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES, rust_free_type
from tslc.backend.target_capability import rust_extension_tag
from tslc.lower.lowerer import (
    LoweredArithmeticPrecondition,
    LoweredArithmeticPreconditionKind,
    LoweredSpecialization,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def unsafe_prefix(enabled: bool) -> str:
    return "unsafe " if enabled else ""


def unsafe_call(call: str, enabled: bool) -> str:
    return f"unsafe {{ {call} }}" if enabled else call


def free_kind_type(kind: str, spec: LoweredSpecialization) -> str:
    """Map a free-function kind to its concrete Rust type."""

    return rust_free_type(
        kind,
        spec.base_type_spelling,
        base_type_tag=spec.type_tag,
    )


def impl_generic_parts(
    shape: LoweredSpecialization,
) -> tuple[list[str], list[str]]:
    """Return Rust impl generic declarations and matching turbofish names."""

    const_decls: list[str] = []
    const_names: list[str] = []
    lane_parameter = shape.lane_parameter
    if (
        shape.uses_sized_vector
        and lane_parameter is not None
        and not lane_parameter.isdigit()
    ):
        const_decls.append(f"const {lane_parameter}: usize")
        const_names.append(lane_parameter)
    if shape.immediate is not None:
        const_decls.append(f"const {shape.immediate[0]}: {shape.immediate[1]}")
        const_names.append(shape.immediate[0])
    for name, typ, _default in shape.generic_params:
        const_decls.append(f"const {name}: {typ}")
        const_names.append(name)
    return (
        [*type_param_decls(shape), *const_decls],
        [*type_param_names(shape), *const_names],
    )


def axis_name(key: str) -> str:
    return key.upper()


def extension_tag(extension_name: str) -> str:
    return rust_extension_tag(extension_name)


def concrete_type(spec: LoweredSpecialization, kind: str) -> str:
    return RUST_SIGNATURE_TYPES.concrete_type(
        kind,
        base=spec.base_type_spelling,
        register=spec.register_spelling,
        array=concrete_array(spec),
    )


def concrete_param_type(spec: LoweredSpecialization, kind: str) -> str:
    if DEFAULT_SUPPORT_POLICY.is_borrowed_parameter_kind(kind):
        return f"&{concrete_array(spec)}"
    return concrete_type(spec, kind)


def concrete_result_type(spec: LoweredSpecialization) -> str:
    return concrete_type(spec, spec.result_kind)


def concrete_array(spec: LoweredSpecialization) -> str:
    return f"array_type<{spec.base_type_spelling}, {spec.lane_parameter}>"


def vector_type(spec: LoweredSpecialization) -> str:
    if spec.vector_spelling is not None:
        return spec.vector_spelling
    if spec.uses_sized_vector:
        return (
            f"Simd<{spec.base_type_spelling}, "
            f"{extension_tag(spec.extension_name)}<{spec.lane_parameter}>>"
        )
    return f"Simd<{spec.base_type_spelling}, {extension_tag(spec.extension_name)}>"


def arithmetic_preconditions(spec: LoweredSpecialization) -> str:
    return "".join(
        f"        {_arithmetic_precondition(precondition)}\n"
        for precondition in spec.arithmetic_preconditions
    )


def _arithmetic_precondition(
    precondition: LoweredArithmeticPrecondition,
) -> str:
    if (
        precondition.kind
        is LoweredArithmeticPreconditionKind.INTEGER_IMMEDIATE_NONZERO
    ):
        return (
            f"const {{ assert!(({precondition.parameter_name} as "
            f"u{precondition.lane_bit_width}) != 0, "
            f'"{precondition.marker}"); }}'
        )
    raise AssertionError(f"unhandled arithmetic precondition {precondition.kind!r}")


def kind_type(kind: str, owner: str) -> str:
    return RUST_SIGNATURE_TYPES.owner_type(kind, owner=owner)


def param_kind_type(kind: str, owner: str) -> str:
    return RUST_SIGNATURE_TYPES.parameter_type(kind, owner=owner)


def params(
    shape: LoweredSpecialization,
    owner: str,
    *,
    target_owner: str | None = None,
    vidx_type: str | None = None,
) -> str:
    parts: list[str] = []
    for index, (name, kind) in enumerate(zip(shape.param_names, shape.param_kinds)):
        if kind == DEFAULT_SUPPORT_POLICY.immediate_kind:
            continue
        override = shape.effective_param_type_overrides[index]
        if override is not None:
            typ = override
        elif DEFAULT_SUPPORT_POLICY.is_target_vector_parameter_kind(kind):
            assert target_owner is not None
            typ = param_kind_type(kind, target_owner)
        elif kind == DEFAULT_SUPPORT_POLICY.index_vector_kind:
            assert vidx_type is not None
            typ = vidx_type
        else:
            typ = param_kind_type(kind, owner)
        parts.append(f"{name}: {typ}")
    return ", ".join(parts)


def runtime_names(shape: LoweredSpecialization) -> str:
    return ", ".join(
        name
        for name, kind in zip(shape.param_names, shape.param_kinds)
        if kind != DEFAULT_SUPPORT_POLICY.immediate_kind
    )


def generic_decls(shape: LoweredSpecialization) -> list[str]:
    declarations = [f"const {axis_name(key)}: bool" for key, _ in shape.axis]
    if shape.immediate is not None:
        declarations.append(
            f"const {shape.immediate[0]}: {shape.immediate[1]}"
        )
    declarations.extend(
        f"const {name}: {typ}" for name, typ, _ in shape.generic_params
    )
    return declarations


def trait_args_by_name(shape: LoweredSpecialization) -> list[str]:
    args = [axis_name(key) for key, _ in shape.axis]
    if shape.immediate is not None:
        args.append(shape.immediate[0])
    args.extend(name for name, _, _ in shape.generic_params)
    return args


def trait_args_by_value(spec: LoweredSpecialization) -> list[str]:
    args = [value for _, value in spec.axis]
    if spec.immediate is not None:
        args.append(spec.immediate[0])
    args.extend(name for name, _, _ in spec.generic_params)
    return args


__all__ = (
    "arithmetic_preconditions",
    "axis_name",
    "concrete_array",
    "concrete_param_type",
    "concrete_result_type",
    "concrete_type",
    "extension_tag",
    "free_kind_type",
    "generic_decls",
    "impl_generic_parts",
    "kind_type",
    "param_kind_type",
    "params",
    "runtime_names",
    "trait_args_by_name",
    "trait_args_by_value",
    "unsafe_call",
    "unsafe_prefix",
    "vector_type",
)
