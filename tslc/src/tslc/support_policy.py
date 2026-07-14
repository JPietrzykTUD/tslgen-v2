"""Central support policy for the current TSLc prototype.

This module owns small, explicit facts about what this generator slice can emit
today. Selection, lowering, validation, and render naming consume these facts;
they should not each grow their own local copy of the same support matrix.
"""

from __future__ import annotations

from dataclasses import dataclass

from tslc.catalog.model import RESULT_DIM_BASE, Extension
from tslc.catalog.scalar_types import (
    same_scalar_width,
    scalar_bit_width,
    scalar_bit_width_or_default,
)
from tslc.catalog.signature_kinds import (
    DEFAULT_SIGNATURE_KINDS,
    SignatureKindCatalog,
)
from tslc.catalog.signatures import SignatureShape
from tslc.catalog.target_families import TargetFamilyCatalog
from tslc.lane_count import LaneCount


@dataclass(frozen=True, slots=True)
class SupportPolicy:
    signature_kinds: SignatureKindCatalog
    mask_suffixes: tuple[tuple[str, str], ...]
    sized_vector_bits_kinds: frozenset[str]
    scalable_vector_bits_kinds: frozenset[str]
    scalar_register_policy_kind: str
    default_size_parameter_name: str
    target_marker_values: frozenset[str]
    deferred_cases: tuple[str, ...]

    @property
    def supported_signature_kinds(self) -> frozenset[str]:
        return self.signature_kinds.supported_kinds

    @property
    def maskable_result_kinds(self) -> frozenset[str]:
        return self.signature_kinds.maskable_result_kinds

    @property
    def mask_deferred_param_kinds(self) -> frozenset[str]:
        return self.signature_kinds.mask_deferred_param_kinds

    @property
    def immediate_kind(self) -> str:
        return self.signature_kinds.immediate_kind

    @property
    def lane_list_kind(self) -> str:
        return self.signature_kinds.lane_list_kind

    @property
    def index_vector_kind(self) -> str:
        return self.signature_kinds.index_vector_kind

    @property
    def pointer_kinds(self) -> frozenset[str]:
        return self.signature_kinds.pointer_kinds

    @property
    def const_pointer_kinds(self) -> frozenset[str]:
        return self.signature_kinds.const_pointer_kinds

    @property
    def mutable_pointer_kinds(self) -> frozenset[str]:
        return self.signature_kinds.mutable_pointer_kinds

    @property
    def scalable_deferred_signature_kinds(self) -> frozenset[str]:
        return self.signature_kinds.scalable_deferred_kinds

    def supports_extension_family(
        self,
        family: str,
        target_families: TargetFamilyCatalog,
    ) -> bool:
        return target_families.supports_extension_family(family)

    def supports_extension(
        self,
        extension: Extension,
        target_families: TargetFamilyCatalog,
    ) -> bool:
        return self.supports_extension_family(extension.family, target_families) and (
            extension.vector_bits_kind not in self.scalable_vector_bits_kinds
            or self.uses_scalable_vector(extension)
        )

    def extension_targets_profile(
        self,
        extension_family: str,
        profile_family: str,
        target_families: TargetFamilyCatalog,
    ) -> bool:
        """Whether an extension of ``extension_family`` belongs in a project built for a profile of
        ``profile_family``. The concrete family names come from source data; this method only
        applies the routing rule carried by the typed catalog."""
        return target_families.extension_targets_profile(extension_family, profile_family)

    def supports_signature(self, shape: SignatureShape) -> bool:
        return (
            shape.result_kind in self.supported_signature_kinds
            and not shape.result_term.is_lane_list_like
            and all(
                not term.is_lane_list_like or term.kind == self.lane_list_kind
                for term in shape.param_terms
            )
            and not self.unsupported_signature_kinds(shape)
        )

    def unsupported_signature_kinds(self, shape: SignatureShape) -> frozenset[str]:
        kinds = {shape.result_kind, *shape.param_kinds}
        return self.signature_kinds.unsupported_kinds(kinds)

    def unsupported_signature_kinds_for_extension(
        self, shape: SignatureShape, extension: Extension
    ) -> frozenset[str]:
        unsupported = set(self.unsupported_signature_kinds(shape))
        unsupported.update(self.deferred_signature_kinds_for_extension(shape, extension))
        return frozenset(unsupported)

    def deferred_signature_kinds_for_extension(
        self, shape: SignatureShape, extension: Extension
    ) -> frozenset[str]:
        if not self.uses_scalable_vector(extension):
            return frozenset()
        kinds = {shape.result_kind, *shape.param_kinds}
        deferred = set(kinds & self.scalable_deferred_signature_kinds)
        if shape.result_term.is_lane_list_like:
            deferred.add(shape.result_kind)
        deferred.update(term.kind for term in shape.param_terms if term.is_lane_list_like)
        return frozenset(deferred)

    def has_immediate_operand(self, shape: SignatureShape) -> bool:
        return self.immediate_kind in shape.param_kinds

    def has_lane_list_parameter(self, shape: SignatureShape) -> bool:
        return self.lane_list_kind in shape.param_kinds

    def uses_sized_vector(self, extension: Extension) -> bool:
        return extension.vector_bits_kind in self.sized_vector_bits_kinds

    def uses_scalable_vector(self, extension: Extension) -> bool:
        return extension.vector_bits_kind in self.scalable_vector_bits_kinds

    def size_parameter_name(self, extension: Extension) -> str:
        return extension.size_parameter_name or self.default_size_parameter_name

    def windowed_lane_parameter(
        self, extension: Extension, from_type: str, to_type: str
    ) -> LaneCount:
        """Typed lane count for a width-preserving sized-vector window.

        The output keeps the total bit width, so its count scales the source
        parameter by the source/target element-width ratio. Backends decide how
        to spell or reject that arithmetic.
        """
        base = self.size_parameter_name(extension)
        from_bits = self.type_bit_width_or_default(from_type)
        to_bits = self.type_bit_width_or_default(to_type)
        return LaneCount.symbolic(
            base,
            multiplier=from_bits,
            divisor=to_bits,
        )

    def windowed_lane_count(self, from_type: str, to_type: str, lanes: int) -> int:
        """The concrete windowed lane count for a width-changing convert at a fixed source
        ``lanes`` — the integer value of :meth:`windowed_lane_parameter` with ``LANES`` bound to
        ``lanes`` (e.g. i8->i16 at 8 lanes -> ``8 * 8 / 16`` = 4). Used by the smoke to instantiate
        the windowed target at a concrete count, computed from the type widths rather than rewriting
        the symbolic parameter string."""
        from_bits = self.type_bit_width_or_default(from_type)
        to_bits = self.type_bit_width_or_default(to_type)
        return lanes * from_bits // to_bits

    def register_is_base(self, extension: Extension) -> bool:
        return extension.vector_register_type_policy == self.scalar_register_policy_kind

    def lane_count(self, extension: Extension, type_tag: str) -> int | None:
        if self.uses_sized_vector(extension) or self.uses_scalable_vector(extension):
            return None
        if extension.vector_bits <= 0:
            return 1
        return extension.vector_bits // self.type_bit_width_or_default(type_tag)

    def lane_expression(self, extension: Extension, type_tag: str) -> str:
        lanes = self.lane_count(extension, type_tag)
        if lanes is None:
            return self.size_parameter_name(extension)
        return str(lanes)

    def vector_alignment_bytes(self, extension: Extension, type_tag: str) -> int:
        if self.uses_sized_vector(extension) or self.uses_scalable_vector(extension):
            return self.type_bit_width_or_default(type_tag) // 8
        return max(1, extension.vector_bits // 8)

    def requires_unsafe_frame(self, shape: SignatureShape) -> bool:
        return any(kind in self.pointer_kinds for kind in shape.param_kinds)

    def is_const_pointer_kind(self, kind: str) -> bool:
        return self.signature_kinds.is_const_pointer(kind)

    def is_mutable_pointer_kind(self, kind: str) -> bool:
        return self.signature_kinds.is_mutable_pointer(kind)

    def is_borrowed_parameter_kind(self, kind: str) -> bool:
        return self.signature_kinds.is_borrowed_parameter(kind)

    def signature_kind_requires_vector_axis(self, kind: str) -> bool:
        return self.signature_kinds.requires_vector_axis(kind)

    def is_free_function_signature(
        self,
        result_kind: str,
        param_kinds: tuple[str, ...],
    ) -> bool:
        return self.signature_kinds.is_free_function_signature(
            result_kind,
            param_kinds,
        )

    def shape_is_free_function(self, shape: SignatureShape) -> bool:
        return self.is_free_function_signature(shape.result_kind, shape.param_kinds)

    def overload_identity_token(self, kind: str, *, register_is_base: bool) -> str:
        return self.signature_kinds.overload_identity_token(
            kind,
            register_is_base=register_is_base,
        )

    def is_maskable_signature(self, shape: SignatureShape) -> bool:
        return (
            shape.result_kind in self.maskable_result_kinds
            and not any(kind in self.mask_deferred_param_kinds for kind in shape.param_kinds)
        )

    def mask_suffix(self, policy: str) -> str:
        for candidate, suffix in self.mask_suffixes:
            if candidate == policy:
                return suffix
        return "_mask_" + policy

    def mask_split_base(self, name: str) -> str:
        for suffix in sorted(
            (suffix for _policy, suffix in self.mask_suffixes),
            key=len,
            reverse=True,
        ):
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    def supports_sized_vector_target_dimension(self, result_dim: str) -> bool:
        return result_dim == RESULT_DIM_BASE

    def same_type_width(self, target_tag: str, source_tag: str) -> bool:
        return same_scalar_width(target_tag, source_tag)

    def type_bit_width(self, type_tag: str) -> int | None:
        return scalar_bit_width(type_tag)

    def type_bit_width_or_default(self, type_tag: str, default: int = 8) -> int:
        return scalar_bit_width_or_default(type_tag, default)

DEFAULT_SUPPORT_POLICY = SupportPolicy(
    signature_kinds=DEFAULT_SIGNATURE_KINDS,
    mask_suffixes=(("pass_through", "_mask"), ("zero", "_maskz")),
    # Sized vectors carry a source-visible `LANES` parameter. Scalable vectors are native runtime
    # length vectors: they can be selected for intrinsic-only C++ bodies, but fixed-lane queries
    # such as `vector::length` stay unsupported until a typed scalable lane model exists.
    sized_vector_bits_kinds=frozenset({"sized"}),
    scalable_vector_bits_kinds=frozenset({"scalable"}),
    scalar_register_policy_kind="base_type",
    default_size_parameter_name="LANES",
    target_marker_values=frozenset({"==", "*"}),
    deferred_cases=(
        "scalable-vector fixed-lane queries and value tests",
        "sized-vector extension-dimension representation changes",
        "different-width reinterpret representation targets",
    ),
)

__all__ = ("DEFAULT_SUPPORT_POLICY", "SupportPolicy")
