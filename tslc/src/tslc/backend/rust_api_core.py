"""One typed owner for the ordinary Rust facade's core operation surface."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_api_model import RustFacadeCoreOperationRequirement
from tslc.catalog.memory import MemoryAccess, MemoryAddressing, MemoryAlignment
from tslc.catalog.semantics import OperandRole, PrimitiveOperation


@dataclass(frozen=True, slots=True)
class RustFacadeCoreCallForm:
    """One emitted FacadeOps call and the semantic delegate role it consumes."""

    role: str
    delegate_role: str
    arguments: tuple[str, ...]
    extra_generics: tuple[str, ...] = ()
    argument_kind: str | None = None
    result_kind: str | None = None

    def __post_init__(self) -> None:
        if not self.role or not self.delegate_role:
            raise ValueError("Rust facade core call forms require non-empty roles")
        if any(not argument for argument in self.arguments):
            raise ValueError("Rust facade core call arguments cannot be empty")
        if any(not generic for generic in self.extra_generics):
            raise ValueError("Rust facade core call generics cannot be empty")


@dataclass(frozen=True, slots=True)
class RustFacadeCoreInventory:
    """Joined semantic requirements and Rust call forms for ``FacadeOps``."""

    requirements: tuple[RustFacadeCoreOperationRequirement, ...]
    call_forms: tuple[RustFacadeCoreCallForm, ...]

    def __post_init__(self) -> None:
        requirement_roles = tuple(item.role for item in self.requirements)
        if len(set(requirement_roles)) != len(requirement_roles):
            raise ValueError("Rust facade core requirement roles must be unique")
        emitted_roles = tuple(item.role for item in self.call_forms)
        if len(set(emitted_roles)) != len(emitted_roles):
            raise ValueError("Rust facade core emitted call roles must be unique")
        delegate_roles = frozenset(item.delegate_role for item in self.call_forms)
        requirement_role_set = frozenset(requirement_roles)
        if delegate_roles != requirement_role_set:
            missing = requirement_role_set - delegate_roles
            unknown = delegate_roles - requirement_role_set
            details: list[str] = []
            if missing:
                details.append(f"missing call forms: {', '.join(sorted(missing))}")
            if unknown:
                details.append(
                    f"unknown delegate roles: {', '.join(sorted(unknown))}"
                )
            raise ValueError(
                "Rust facade core call forms must cover every semantic role "
                "without unknown roles; " + "; ".join(details)
            )

    @property
    def emitted_roles(self) -> tuple[str, ...]:
        return tuple(item.role for item in self.call_forms)

    @property
    def delegate_roles(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.delegate_role for item in self.call_forms))


_CORE_OPERATION_REQUIREMENTS = (
    RustFacadeCoreOperationRequirement(
        "vector_splat",
        PrimitiveOperation.VECTOR_SPLAT,
        "v",
        ("s",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_from_array",
        PrimitiveOperation.VECTOR_FROM_ARRAY,
        "v",
        ("s[]",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_to_array",
        PrimitiveOperation.VECTOR_TO_ARRAY,
        "s[]",
        ("v",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "vector_zero", PrimitiveOperation.VECTOR_ZERO, "v", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "extract_lane",
        PrimitiveOperation.EXTRACT_LANE,
        "s",
        ("v", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "insert_lane",
        PrimitiveOperation.INSERT_LANE,
        "v",
        ("v", "usize", "s"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "load",
        PrimitiveOperation.LOAD,
        "v",
        ("cptr",),
        (OperandRole.MEMORY_SOURCE,),
        axis_names=("aligned",),
        memory_access=MemoryAccess.READ,
        memory_addressing=MemoryAddressing.CONTIGUOUS,
        memory_alignment_modes=(
            MemoryAlignment.ALIGNED,
            MemoryAlignment.UNALIGNED,
        ),
    ),
    RustFacadeCoreOperationRequirement(
        "store",
        PrimitiveOperation.STORE,
        "void",
        ("ptr", "v"),
        (OperandRole.MEMORY_DESTINATION, OperandRole.VALUE),
        axis_names=("aligned",),
        memory_access=MemoryAccess.WRITE,
        memory_addressing=MemoryAddressing.CONTIGUOUS,
        memory_alignment_modes=(
            MemoryAlignment.ALIGNED,
            MemoryAlignment.UNALIGNED,
        ),
        overload=("payload_extent", "vector", True),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_false", PrimitiveOperation.MASK_ALL_FALSE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_true", PrimitiveOperation.MASK_ALL_TRUE, "m", (), ()
    ),
    RustFacadeCoreOperationRequirement(
        "mask_to_integral",
        PrimitiveOperation.MASK_TO_INTEGRAL,
        "im",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_from_integral",
        PrimitiveOperation.MASK_FROM_INTEGRAL,
        "m",
        ("im",),
        (OperandRole.VALUE,),
    ),
    RustFacadeCoreOperationRequirement(
        "integral_mask_test",
        PrimitiveOperation.INTEGRAL_MASK_TEST,
        "im",
        ("im", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_set_lane",
        PrimitiveOperation.MASK_SET_LANE,
        "m",
        ("m", "usize", "usize"),
        (OperandRole.PRIMARY, OperandRole.INDEX, OperandRole.VALUE),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_population_count",
        PrimitiveOperation.MASK_POPULATION_COUNT,
        "usize",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_and",
        PrimitiveOperation.MASK_AND,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_or",
        PrimitiveOperation.MASK_OR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_xor",
        PrimitiveOperation.MASK_XOR,
        "m",
        ("m", "m"),
        (OperandRole.PRIMARY, OperandRole.SECONDARY),
    ),
    RustFacadeCoreOperationRequirement(
        "mask_not",
        PrimitiveOperation.MASK_NOT,
        "m",
        ("m",),
        (OperandRole.PRIMARY,),
    ),
)


_CORE_CALL_FORMS = (
    RustFacadeCoreCallForm("vector_splat", "vector_splat", ("value",)),
    RustFacadeCoreCallForm(
        "vector_from_array", "vector_from_array", ("&values",)
    ),
    RustFacadeCoreCallForm("vector_to_array", "vector_to_array", ("value",)),
    RustFacadeCoreCallForm("vector_zero", "vector_zero", ()),
    RustFacadeCoreCallForm(
        "extract_lane", "extract_lane", ("value", "index")
    ),
    RustFacadeCoreCallForm(
        "insert_lane", "insert_lane", ("value", "index", "lane")
    ),
    RustFacadeCoreCallForm("load", "load", ("source",), ("false",)),
    RustFacadeCoreCallForm(
        "store", "store", ("destination", "value"), ("false", "_")
    ),
    RustFacadeCoreCallForm("mask_false", "mask_false", ()),
    RustFacadeCoreCallForm("mask_true", "mask_true", ()),
    RustFacadeCoreCallForm(
        "mask_from_bitmask",
        "mask_from_integral",
        ("bits",),
        argument_kind="im",
    ),
    RustFacadeCoreCallForm(
        "mask_to_bitmask",
        "mask_to_integral",
        ("value",),
        result_kind="im",
    ),
    RustFacadeCoreCallForm(
        "mask_to_integral_for_test", "mask_to_integral", ("value",)
    ),
    RustFacadeCoreCallForm(
        "integral_mask_test", "integral_mask_test", ("bits", "index")
    ),
    RustFacadeCoreCallForm(
        "mask_set_lane",
        "mask_set_lane",
        ("value", "index", "if active { 1 } else { 0 }"),
    ),
    RustFacadeCoreCallForm(
        "mask_population_count", "mask_population_count", ("value",)
    ),
    RustFacadeCoreCallForm("mask_and", "mask_and", ("left", "right")),
    RustFacadeCoreCallForm("mask_or", "mask_or", ("left", "right")),
    RustFacadeCoreCallForm("mask_xor", "mask_xor", ("left", "right")),
    RustFacadeCoreCallForm("mask_not", "mask_not", ("value",)),
)


RUST_FACADE_CORE_INVENTORY = RustFacadeCoreInventory(
    requirements=_CORE_OPERATION_REQUIREMENTS,
    call_forms=_CORE_CALL_FORMS,
)
RUST_FACADE_CORE_OPERATION_REQUIREMENTS = RUST_FACADE_CORE_INVENTORY.requirements
RUST_FACADE_CORE_CALL_FORMS = RUST_FACADE_CORE_INVENTORY.call_forms
RUST_FACADE_CORE_CALL_ROLES = RUST_FACADE_CORE_INVENTORY.emitted_roles


__all__ = (
    "RUST_FACADE_CORE_CALL_FORMS",
    "RUST_FACADE_CORE_CALL_ROLES",
    "RUST_FACADE_CORE_INVENTORY",
    "RUST_FACADE_CORE_OPERATION_REQUIREMENTS",
    "RustFacadeCoreCallForm",
    "RustFacadeCoreInventory",
)
