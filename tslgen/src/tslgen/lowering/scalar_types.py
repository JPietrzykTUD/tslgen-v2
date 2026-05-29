"""Lowering-owned scalar type descriptors for the tiny clean slice."""

from dataclasses import dataclass
from typing import Literal

ScalarTypeKind = Literal["scalar"]
ScalarTypeFamily = Literal["integer", "floating"]
ScalarSignedness = Literal["signed", "unsigned", "not_applicable"]


@dataclass(frozen=True, slots=True)
class ScalarTypeDescriptor:
    tag: str
    kind: ScalarTypeKind
    family: ScalarTypeFamily
    bit_width: int
    signedness: ScalarSignedness

    @property
    def is_floating(self) -> bool:
        return self.family == "floating"


SUPPORTED_SCALAR_TYPE_DESCRIPTORS: tuple[ScalarTypeDescriptor, ...] = (
    ScalarTypeDescriptor(
        tag="si8",
        kind="scalar",
        family="integer",
        bit_width=8,
        signedness="signed",
    ),
    ScalarTypeDescriptor(
        tag="ui8",
        kind="scalar",
        family="integer",
        bit_width=8,
        signedness="unsigned",
    ),
    ScalarTypeDescriptor(
        tag="si16",
        kind="scalar",
        family="integer",
        bit_width=16,
        signedness="signed",
    ),
    ScalarTypeDescriptor(
        tag="ui16",
        kind="scalar",
        family="integer",
        bit_width=16,
        signedness="unsigned",
    ),
    ScalarTypeDescriptor(
        tag="si32",
        kind="scalar",
        family="integer",
        bit_width=32,
        signedness="signed",
    ),
    ScalarTypeDescriptor(
        tag="ui32",
        kind="scalar",
        family="integer",
        bit_width=32,
        signedness="unsigned",
    ),
    ScalarTypeDescriptor(
        tag="si64",
        kind="scalar",
        family="integer",
        bit_width=64,
        signedness="signed",
    ),
    ScalarTypeDescriptor(
        tag="ui64",
        kind="scalar",
        family="integer",
        bit_width=64,
        signedness="unsigned",
    ),
    ScalarTypeDescriptor(
        tag="f32",
        kind="scalar",
        family="floating",
        bit_width=32,
        signedness="not_applicable",
    ),
    ScalarTypeDescriptor(
        tag="f64",
        kind="scalar",
        family="floating",
        bit_width=64,
        signedness="not_applicable",
    ),
)


def lookup_scalar_type_descriptor(tag: str) -> ScalarTypeDescriptor | None:
    for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS:
        if descriptor.tag == tag:
            return descriptor
    return None


def supported_scalar_type_tags() -> tuple[str, ...]:
    return tuple(descriptor.tag for descriptor in SUPPORTED_SCALAR_TYPE_DESCRIPTORS)
