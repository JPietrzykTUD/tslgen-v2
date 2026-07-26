"""Canonical type and boundary-adaptation policy for the Rust facade."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.backend.rust_static_selection import RustStaticVectorMapping
from tslc.backend.signature_types import RUST_SIGNATURE_TYPES


class RustFacadeTypeCategory(StrEnum):
    UNIT = "unit"
    VECTOR = "vector"
    MASK = "mask"
    INTEGRAL_MASK = "integral_mask"
    SCALAR = "scalar"
    USIZE = "usize"
    MUT_POINTER = "mut_pointer"
    CONST_POINTER = "const_pointer"


class RustFacadeBoundaryAdaptation(StrEnum):
    IDENTITY = "identity"
    UNWRAP_VECTOR = "unwrap_vector"
    WRAP_VECTOR = "wrap_vector"
    UNWRAP_MASK = "unwrap_mask"
    WRAP_MASK = "wrap_mask"
    NARROW_INTEGRAL_MASK = "narrow_integral_mask"
    WIDEN_INTEGRAL_MASK = "widen_integral_mask"


@dataclass(frozen=True, slots=True)
class RustFacadeSignatureType:
    kind: str
    category: RustFacadeTypeCategory
    public_argument: RustFacadeBoundaryAdaptation = (
        RustFacadeBoundaryAdaptation.IDENTITY
    )
    public_result: RustFacadeBoundaryAdaptation = (
        RustFacadeBoundaryAdaptation.IDENTITY
    )
    lower_argument: RustFacadeBoundaryAdaptation = (
        RustFacadeBoundaryAdaptation.IDENTITY
    )
    lower_result: RustFacadeBoundaryAdaptation = (
        RustFacadeBoundaryAdaptation.IDENTITY
    )

    def __post_init__(self) -> None:
        if self.kind not in RUST_SIGNATURE_TYPES.supported_kinds:
            raise ValueError(
                f"Rust facade kind {self.kind!r} has no canonical lower type"
            )


class RustFacadeSignatureTypes:
    """Project admitted runtime kinds without redefining the lower Rust ABI."""

    def __init__(self, policies: tuple[RustFacadeSignatureType, ...]) -> None:
        by_kind = {policy.kind: policy for policy in policies}
        if len(by_kind) != len(policies):
            raise ValueError("Rust facade signature kinds must be unique")
        self._by_kind = MappingProxyType(by_kind)

    @property
    def supported_runtime_kinds(self) -> frozenset[str]:
        return frozenset(self._by_kind)

    def supports_runtime_kind(self, kind: str) -> bool:
        return kind in self._by_kind

    def policy(self, kind: str) -> RustFacadeSignatureType:
        try:
            return self._by_kind[kind]
        except KeyError as error:
            raise ValueError(
                f"Rust facade has no runtime type policy for {kind!r}"
            ) from error

    def lower_parameter_type(self, kind: str, *, owner: str) -> str:
        self.policy(kind)
        return RUST_SIGNATURE_TYPES.parameter_type(kind, owner=owner)

    def lower_result_type(self, kind: str, *, owner: str) -> str:
        self.policy(kind)
        return RUST_SIGNATURE_TYPES.owner_type(kind, owner=owner)

    def private_trait_type(
        self,
        kind: str,
        *,
        owner: str,
        target_owner: str,
        lanes: str,
    ) -> str:
        policy = self.policy(kind)
        category = policy.category
        if category in {
            RustFacadeTypeCategory.VECTOR,
            RustFacadeTypeCategory.MASK,
        }:
            member = (
                "Vector"
                if category is RustFacadeTypeCategory.VECTOR
                else "Mask"
            )
            return (
                f"{owner}::{member}"
                if target_owner == owner
                else f"<{target_owner} as Representation<{lanes}>>::{member}"
            )
        return self._nonaggregate_type(category, owner)

    def private_impl_type(
        self,
        kind: str,
        *,
        owner: str,
        lanes: int,
    ) -> str:
        category = self.policy(kind).category
        if category is RustFacadeTypeCategory.VECTOR:
            return f"<{owner} as private::Representation<{lanes}>>::Vector"
        if category is RustFacadeTypeCategory.MASK:
            return f"<{owner} as private::Representation<{lanes}>>::Mask"
        return self._nonaggregate_type(category, owner)

    def public_type(
        self,
        kind: str,
        *,
        element: str,
        lanes: str,
        result_element: str,
    ) -> str:
        category = self.policy(kind).category
        if category is RustFacadeTypeCategory.VECTOR:
            return f"Simd<{result_element}, {lanes}>"
        if category is RustFacadeTypeCategory.MASK:
            return f"Mask<{result_element}, {lanes}>"
        return self._nonaggregate_type(category, element)

    def adapt_public_argument(self, kind: str, value: str) -> str:
        adaptation = self.policy(kind).public_argument
        if adaptation in {
            RustFacadeBoundaryAdaptation.UNWRAP_VECTOR,
            RustFacadeBoundaryAdaptation.UNWRAP_MASK,
        }:
            return f"{value}.value"
        if adaptation is RustFacadeBoundaryAdaptation.IDENTITY:
            return value
        raise ValueError(
            f"Rust facade public argument cannot apply {adaptation.value}"
        )

    def adapt_public_result(
        self,
        kind: str,
        call: str,
        *,
        target_element: str | None,
    ) -> str:
        adaptation = self.policy(kind).public_result
        if adaptation is RustFacadeBoundaryAdaptation.WRAP_VECTOR:
            return f"Simd {{ value: {call} }}"
        if adaptation is RustFacadeBoundaryAdaptation.WRAP_MASK:
            return f"Mask::<{target_element or '_'}, _> {{ value: {call} }}"
        if adaptation is RustFacadeBoundaryAdaptation.IDENTITY:
            return call
        raise ValueError(
            f"Rust facade public result cannot apply {adaptation.value}"
        )

    def adapt_lower_argument(
        self,
        kind: str,
        value: str,
        mapping: RustStaticVectorMapping,
    ) -> str:
        adaptation = self.policy(kind).lower_argument
        if adaptation is RustFacadeBoundaryAdaptation.NARROW_INTEGRAL_MASK:
            self.validate_integral_mask_mapping(mapping)
            return (
                value
                if mapping.imask_spelling == "u64"
                else f"{value} as {mapping.imask_spelling}"
            )
        if adaptation is RustFacadeBoundaryAdaptation.IDENTITY:
            return value
        raise ValueError(
            f"Rust facade lower argument cannot apply {adaptation.value}"
        )

    def adapt_lower_result(
        self,
        kind: str,
        call: str,
        mapping: RustStaticVectorMapping,
    ) -> str:
        adaptation = self.policy(kind).lower_result
        if adaptation is RustFacadeBoundaryAdaptation.WIDEN_INTEGRAL_MASK:
            self.validate_integral_mask_mapping(mapping)
            return (
                call
                if mapping.imask_spelling == "u64"
                else f"{call} as u64"
            )
        if adaptation is RustFacadeBoundaryAdaptation.IDENTITY:
            return call
        raise ValueError(
            f"Rust facade lower result cannot apply {adaptation.value}"
        )

    def validate_integral_mask_mapping(
        self,
        mapping: RustStaticVectorMapping,
    ) -> None:
        if mapping.imask_bits not in {8, 16, 32, 64}:
            raise ValueError(
                "Rust facade integral-mask adaptation requires an unsigned "
                "8-, 16-, 32-, or 64-bit lower representation"
            )
        expected_scalar = RUST_SIGNATURE_TYPES.concrete_integral_mask_type(
            "im", width=str(mapping.imask_bits)
        )
        if (
            re.fullmatch(r"[iu][0-9]+", mapping.imask_spelling)
            and mapping.imask_spelling != expected_scalar
        ):
            raise ValueError(
                "Rust facade integral-mask adaptation requires the lower "
                f"scalar spelling {expected_scalar!r}, got "
                f"{mapping.imask_spelling!r}"
            )

    @staticmethod
    def _nonaggregate_type(
        category: RustFacadeTypeCategory,
        owner: str,
    ) -> str:
        if category is RustFacadeTypeCategory.UNIT:
            return "()"
        if category is RustFacadeTypeCategory.INTEGRAL_MASK:
            return "u64"
        if category is RustFacadeTypeCategory.SCALAR:
            return owner
        if category is RustFacadeTypeCategory.USIZE:
            return "usize"
        if category is RustFacadeTypeCategory.MUT_POINTER:
            return f"*mut {owner}"
        if category is RustFacadeTypeCategory.CONST_POINTER:
            return f"*const {owner}"
        raise ValueError(f"Rust facade has no scalar form for {category.value}")


RUST_FACADE_SIGNATURE_TYPES = RustFacadeSignatureTypes(
    (
        RustFacadeSignatureType("void", RustFacadeTypeCategory.UNIT),
        RustFacadeSignatureType(
            "v",
            RustFacadeTypeCategory.VECTOR,
            public_argument=RustFacadeBoundaryAdaptation.UNWRAP_VECTOR,
            public_result=RustFacadeBoundaryAdaptation.WRAP_VECTOR,
        ),
        RustFacadeSignatureType(
            "m",
            RustFacadeTypeCategory.MASK,
            public_argument=RustFacadeBoundaryAdaptation.UNWRAP_MASK,
            public_result=RustFacadeBoundaryAdaptation.WRAP_MASK,
        ),
        RustFacadeSignatureType(
            "im",
            RustFacadeTypeCategory.INTEGRAL_MASK,
            lower_argument=RustFacadeBoundaryAdaptation.NARROW_INTEGRAL_MASK,
            lower_result=RustFacadeBoundaryAdaptation.WIDEN_INTEGRAL_MASK,
        ),
        RustFacadeSignatureType(
            "imt",
            RustFacadeTypeCategory.INTEGRAL_MASK,
            lower_argument=RustFacadeBoundaryAdaptation.NARROW_INTEGRAL_MASK,
            lower_result=RustFacadeBoundaryAdaptation.WIDEN_INTEGRAL_MASK,
        ),
        RustFacadeSignatureType("s", RustFacadeTypeCategory.SCALAR),
        RustFacadeSignatureType("usize", RustFacadeTypeCategory.USIZE),
        RustFacadeSignatureType("ptr", RustFacadeTypeCategory.MUT_POINTER),
        RustFacadeSignatureType("cptr", RustFacadeTypeCategory.CONST_POINTER),
    )
)


__all__ = (
    "RUST_FACADE_SIGNATURE_TYPES",
    "RustFacadeBoundaryAdaptation",
    "RustFacadeSignatureType",
    "RustFacadeSignatureTypes",
    "RustFacadeTypeCategory",
)
