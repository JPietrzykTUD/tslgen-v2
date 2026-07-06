"""Shared policy for generated dataparallel primitive facades."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslc.lower.lowerer import LoweredSpecialization, varying_positions


class DataparallelPrimitiveFacadeKind(Enum):
    """The facade shape a backend may print for a lowered primitive."""

    REGISTER_MASK_OR_REDUCTION = "register_mask_or_reduction"
    TARGET_BASE_CONVERSION = "target_base_conversion"
    CONTIGUOUS_MEMORY = "contiguous_memory"


@dataclass(frozen=True, slots=True)
class DataparallelPrimitiveFacade:
    primitive_name: str
    shape: LoweredSpecialization
    kind: DataparallelPrimitiveFacadeKind


def classify_dataparallel_primitive_facade(
    primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
) -> DataparallelPrimitiveFacade | None:
    """Classify whether a primitive can expose a policy-based facade.

    This is shared compiler policy: a facade is admitted only for primitive
    signatures whose vector choice can be expressed as `(Policy, T)` without
    backend-specific overload repair.
    """

    memory_shape = _memory_facade_shape(primitive_name, specializations)
    if memory_shape is not None:
        return DataparallelPrimitiveFacade(
            primitive_name=primitive_name,
            shape=memory_shape,
            kind=DataparallelPrimitiveFacadeKind.CONTIGUOUS_MEMORY,
        )
    if not specializations:
        return None
    shape = specializations[0]
    target_base_conversion = _is_target_base_conversion(shape, specializations)
    if not _supports_register_mask_or_reduction_facade(
        shape, target_base_conversion
    ):
        return None
    if (
        shape.type_params
        or shape.axis
        or shape.immediate is not None
        or shape.generic_params
        or varying_positions(specializations)
    ):
        return None
    return DataparallelPrimitiveFacade(
        primitive_name=primitive_name,
        shape=shape,
        kind=(
            DataparallelPrimitiveFacadeKind.TARGET_BASE_CONVERSION
            if target_base_conversion
            else DataparallelPrimitiveFacadeKind.REGISTER_MASK_OR_REDUCTION
        ),
    )


def _memory_facade_shape(
    primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
) -> LoweredSpecialization | None:
    supported_shapes = {
        "load": ("v", ("cptr",)),
        "store": ("void", ("ptr", "v")),
    }
    expected = supported_shapes.get(primitive_name)
    if expected is None:
        return None
    expected_result, expected_params = expected
    for spec in specializations:
        if (
            spec.target is None
            and spec.result_kind == expected_result
            and spec.param_kinds == expected_params
            and not spec.type_params
            and len(spec.axis) == 1
            and spec.axis[0][0] == "aligned"
            and spec.immediate is None
            and not spec.generic_params
        ):
            return spec
    return None


def _is_target_base_conversion(
    shape: LoweredSpecialization, specializations: tuple[LoweredSpecialization, ...]
) -> bool:
    return (
        shape.result_kind == "v"
        and shape.param_kinds == ("v",)
        and shape.target is not None
        and all(
            spec.target is not None
            and spec.target.extension_isa == spec.extension_name
            for spec in specializations
        )
    )


def _supports_register_mask_or_reduction_facade(
    shape: LoweredSpecialization, target_base_conversion: bool
) -> bool:
    return (
        target_base_conversion
        or (
            shape.target is None
            and shape.result_kind == "v"
            and shape.param_kinds in {("v",), ("v", "v")}
        )
        or (
            shape.target is None
            and shape.result_kind == "m"
            and shape.param_kinds in {(), ("v",), ("v", "v"), ("m",), ("m", "m")}
        )
        or (
            shape.target is None
            and shape.result_kind == "s"
            and shape.param_kinds in {("v",), ("m", "v"), ("v", "s")}
        )
        or (
            shape.target is None
            and shape.result_kind == "usize"
            and shape.param_kinds == ("m",)
        )
    )
