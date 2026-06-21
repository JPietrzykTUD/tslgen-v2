"""Central support policy for the current TSLc prototype.

This module owns small, explicit facts about what this generator slice can emit
today. Selection, lowering, validation, and render naming consume these facts;
they should not each grow their own local copy of the same support matrix.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from tslc.catalog.model import RESULT_DIM_BASE, Extension
from tslc.catalog.signatures import SignatureShape


@dataclass(frozen=True, slots=True)
class SupportPolicy:
    backend_ids: frozenset[str]
    emitted_extension_families: frozenset[str]
    supported_signature_kinds: frozenset[str]
    maskable_result_kinds: frozenset[str]
    mask_deferred_param_kinds: frozenset[str]
    mask_suffixes: tuple[tuple[str, str], ...]
    immediate_kind: str
    variadic_scalar_kind: str
    index_vector_kind: str
    pointer_kinds: frozenset[str]
    sized_vector_bits_kinds: frozenset[str]
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

    def supports_signature(self, shape: SignatureShape) -> bool:
        return (
            shape.result_kind in self.supported_signature_kinds
            and not self.unsupported_signature_kinds(shape)
        )

    def unsupported_signature_kinds(self, shape: SignatureShape) -> frozenset[str]:
        kinds = {shape.result_kind, *shape.param_kinds}
        return frozenset(k for k in kinds if k not in self.supported_signature_kinds)

    def has_immediate_operand(self, shape: SignatureShape) -> bool:
        return self.immediate_kind in shape.param_kinds

    def is_variadic_signature(self, shape: SignatureShape) -> bool:
        return self.variadic_scalar_kind in shape.param_kinds

    def skips_variadic_on_extension(self, extension: Extension, shape: SignatureShape) -> bool:
        return self.uses_sized_vector(extension) and self.is_variadic_signature(shape)

    def uses_sized_vector(self, extension: Extension) -> bool:
        return extension.vector_bits_kind in self.sized_vector_bits_kinds

    def size_parameter_name(self, extension: Extension) -> str:
        return extension.size_parameter_name or self.default_size_parameter_name

    def register_is_base(self, extension: Extension) -> bool:
        return extension.vector_register_type_policy == self.scalar_register_policy_kind

    def lane_count(self, extension: Extension, type_tag: str) -> int | None:
        if self.uses_sized_vector(extension):
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
        if self.uses_sized_vector(extension):
            return self.type_bit_width_or_default(type_tag) // 8
        return max(1, extension.vector_bits // 8)

    def requires_unsafe_frame(self, shape: SignatureShape) -> bool:
        return any(kind in self.pointer_kinds for kind in shape.param_kinds)

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
        tw, sw = self.type_bit_width(target_tag), self.type_bit_width(source_tag)
        return tw is not None and tw == sw

    def type_bit_width(self, type_tag: str) -> int | None:
        digits = "".join(c for c in type_tag if c.isdigit())
        return int(digits) if digits else None

    def type_bit_width_or_default(self, type_tag: str, default: int = 8) -> int:
        return self.type_bit_width(type_tag) or default

    def supports_all_backends(self, backend_ids: Iterable[str]) -> bool:
        return all(self.supports_backend(backend_id) for backend_id in backend_ids)


DEFAULT_SUPPORT_POLICY = SupportPolicy(
    backend_ids=frozenset({"cpp", "rust"}),
    emitted_extension_families=frozenset({"scalar", "x86", "generic_like"}),
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
            "void",
            "s[]",
            "vt",
            "vidx",
            "s...",
            "o",
        }
    ),
    maskable_result_kinds=frozenset({"v", "m", "im", "void"}),
    mask_deferred_param_kinds=frozenset({"vidx"}),
    mask_suffixes=(("pass_through", "_mask"), ("zero", "_maskz")),
    immediate_kind="sImm",
    variadic_scalar_kind="s...",
    index_vector_kind="vidx",
    pointer_kinds=frozenset({"ptr", "ptr+"}),
    sized_vector_bits_kinds=frozenset({"sized"}),
    scalar_register_policy_kind="base_type",
    default_size_parameter_name="LANES",
    target_marker_values=frozenset({"==", "*"}),
    deferred_cases=(
        "non-scalar/non-x86/non-generic_like extension family emission",
        "masked gather/scatter forms with vidx parameters",
        "masked reductions that return scalar values",
        "sized-vector variadic fallback loops",
        "sized-vector extension-dimension representation changes",
        "different-width reinterpret representation targets",
    ),
)

__all__ = ("DEFAULT_SUPPORT_POLICY", "SupportPolicy")
