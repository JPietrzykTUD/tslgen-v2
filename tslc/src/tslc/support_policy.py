"""Central support policy for the current TSLc prototype.

This module owns small, explicit facts about what this generator slice can emit
today. Selection, lowering, validation, and render naming consume these facts;
they should not each grow their own local copy of the same support matrix.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tslc.catalog.model import RESULT_DIM_BASE, Extension
from tslc.catalog.scalar_types import (
    same_scalar_width,
    scalar_bit_width,
    scalar_bit_width_or_default,
)
from tslc.catalog.signatures import LANE_LIST_KIND, SignatureShape

# Extension families that are ISA-portable — emitted for every profile regardless of its ISA.
_UNIVERSAL_EXTENSION_FAMILIES = frozenset({"scalar", "generic_like"})
# Machine-profile ISA family -> the one ISA-specific extension family it hosts. A profile family
# absent here (e.g. "generic") hosts only the universal families above.
_PROFILE_ISA_EXTENSION_FAMILY = {"x86": "x86", "aarch64": "arm"}


@dataclass(frozen=True, slots=True)
class SupportPolicy:
    backend_ids: frozenset[str]
    emitted_extension_families: frozenset[str]
    supported_signature_kinds: frozenset[str]
    maskable_result_kinds: frozenset[str]
    mask_deferred_param_kinds: frozenset[str]
    mask_suffixes: tuple[tuple[str, str], ...]
    immediate_kind: str
    lane_list_kind: str
    index_vector_kind: str
    pointer_kinds: frozenset[str]
    const_pointer_kinds: frozenset[str]
    mutable_pointer_kinds: frozenset[str]
    sized_vector_bits_kinds: frozenset[str]
    scalable_vector_bits_kinds: frozenset[str]
    scalable_deferred_signature_kinds: frozenset[str]
    scalar_register_policy_kind: str
    default_size_parameter_name: str
    target_marker_values: frozenset[str]
    deferred_cases: tuple[str, ...]

    @property
    def default_backend_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.backend_ids))

    def supports_backend(self, backend_id: str) -> bool:
        return backend_id in self.backend_ids

    def backend_label(self) -> str:
        backends = sorted(self.backend_ids)
        return " or ".join(backends)

    def supports_extension_family(self, family: str) -> bool:
        return family in self.emitted_extension_families

    def supports_extension(self, extension: Extension) -> bool:
        return self.supports_extension_family(extension.family) and (
            extension.vector_bits_kind not in self.scalable_vector_bits_kinds
            or self.uses_scalable_vector(extension)
        )

    def extension_targets_profile(self, extension_family: str, profile_family: str) -> bool:
        """Whether an extension of ``extension_family`` belongs in a project built for a profile of
        ``profile_family``. ISA-portable families (`scalar`/`generic_like`) emit on every profile;
        an ISA-specific family emits only on a profile of its own ISA. So an aarch64 profile never
        registers the `x86` substrate and vice-versa — e.g. the ISA-independent ``requires []``
        scalar-store body, keyed to every extension, no longer leaks its `simd<T, avx2>`
        registration onto a neon profile."""
        if extension_family in _UNIVERSAL_EXTENSION_FAMILIES:
            return True
        return extension_family == _PROFILE_ISA_EXTENSION_FAMILY.get(profile_family)

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
        return frozenset(k for k in kinds if k not in self.supported_signature_kinds)

    def unsupported_signature_kinds_for_extension(
        self, shape: SignatureShape, extension: Extension
    ) -> frozenset[str]:
        unsupported = set(self.unsupported_signature_kinds(shape))
        if self.uses_scalable_vector(extension):
            kinds = {shape.result_kind, *shape.param_kinds}
            unsupported.update(kinds & self.scalable_deferred_signature_kinds)
            if shape.result_term.is_lane_list_like:
                unsupported.add(shape.result_kind)
            unsupported.update(
                term.kind for term in shape.param_terms if term.is_lane_list_like
            )
        return frozenset(unsupported)

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
    ) -> str:
        """The sized vector's lane-count term for a *windowing* base change (`convert_up`/`down`):
        the output keeps the total width, so the lane count scales by the byte ratio —
        ``(LANES * from_bits / to_bits)`` (e.g. i8->i16 -> ``(LANES * 8 / 16)``). Same-width gives
        plain ``LANES``. C++ accepts this const expression in lane-count position; stable Rust does
        not (the window query skips there). Lane-PRESERVING base changes (`cast`/`reinterpret`)
        keep plain ``LANES`` and must NOT use this."""
        base = self.size_parameter_name(extension)
        from_bits = self.type_bit_width_or_default(from_type)
        to_bits = self.type_bit_width_or_default(to_type)
        if from_bits == to_bits:
            return base
        return f"({base} * {from_bits} / {to_bits})"

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
        return kind in self.const_pointer_kinds

    def is_mutable_pointer_kind(self, kind: str) -> bool:
        return kind in self.mutable_pointer_kinds

    def is_borrowed_parameter_kind(self, kind: str) -> bool:
        return kind in {"s[]", self.lane_list_kind}

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

    def supports_all_backends(self, backend_ids: Iterable[str]) -> bool:
        return all(self.supports_backend(backend_id) for backend_id in backend_ids)


DEFAULT_SUPPORT_POLICY = SupportPolicy(
    backend_ids=frozenset({"cpp", "rust"}),
    emitted_extension_families=frozenset({"scalar", "x86", "arm", "generic_like"}),
    supported_signature_kinds=frozenset(
        {
            "v",
            "s",
            "m",
            "im",
            "usize",
            "sImm",
            "ptr",
            "ptr+",
            "cptr",
            "cptr+",
            "void",
            "s[]",
            LANE_LIST_KIND,
            "vt",
            "vidx",
            "o",
        }
    ),
    maskable_result_kinds=frozenset({"v", "m", "im", "void"}),
    mask_deferred_param_kinds=frozenset({"vidx"}),
    mask_suffixes=(("pass_through", "_mask"), ("zero", "_maskz")),
    immediate_kind="sImm",
    lane_list_kind=LANE_LIST_KIND,
    index_vector_kind="vidx",
    pointer_kinds=frozenset({"ptr", "ptr+", "cptr", "cptr+"}),
    const_pointer_kinds=frozenset({"cptr", "cptr+"}),
    mutable_pointer_kinds=frozenset({"ptr", "ptr+"}),
    # Sized vectors carry a source-visible `LANES` parameter. Scalable vectors are native runtime
    # length vectors: they can be selected for intrinsic-only C++ bodies, but fixed-lane queries
    # such as `vector::length` stay unsupported until a typed scalable lane model exists.
    sized_vector_bits_kinds=frozenset({"sized"}),
    scalable_vector_bits_kinds=frozenset({"scalable"}),
    scalable_deferred_signature_kinds=frozenset({"s[]", LANE_LIST_KIND}),
    scalar_register_policy_kind="base_type",
    default_size_parameter_name="LANES",
    target_marker_values=frozenset({"==", "*"}),
    deferred_cases=(
        "scalable-vector fixed-lane queries and value tests",
        "masked gather/scatter forms with vidx parameters",
        "masked reductions that return scalar values",
        "sized-vector extension-dimension representation changes",
        "different-width reinterpret representation targets",
    ),
)

__all__ = ("DEFAULT_SUPPORT_POLICY", "SupportPolicy")
