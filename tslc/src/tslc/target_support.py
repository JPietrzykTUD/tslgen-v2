"""Typed exact-support facts produced by selection and generation.

The selector owns the expected slot universe.  The pipeline advances each
selected realization through lowering and dependency closure.  Maintenance
reports may serialize these values, but must not reconstruct either decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from tslc.catalog.model import Primitive
from tslc.catalog.primitive_identity import primitive_declaration_identity
from tslc.lower.implementation_facts import ImplementationState

if TYPE_CHECKING:
    from tslc.select.selector import SelectedImplementation


class TargetSupportStatus(StrEnum):
    ABSENT = "absent"
    SELECTED = "selected"
    LOWERED = "lowered"
    PRUNED = "pruned"
    POLICY_DEFERRED = "policy_deferred"
    EMITTED = "emitted"


@dataclass(frozen=True, slots=True)
class TargetSupportKey:
    """One expected public specialization slot before body selection."""

    profile: str
    backend: str
    primitive: str
    signature: str
    attributes: tuple[tuple[str, str], ...]
    result_target: tuple[str, str] | None
    overload: tuple[str, str, bool] | None
    type_tag: str
    target_extension: str
    conversion_target: str | None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.profile,
            self.backend,
            self.primitive,
            self.signature,
            self.attributes,
            self.result_target or (),
            self.overload or (),
            self.type_tag,
            self.target_extension,
            self.conversion_target or "",
        )

    @property
    def declaration_identity(self) -> str:
        return primitive_declaration_identity(
            self.primitive,
            self.signature,
            self.attributes,
            self.result_target,
            self.overload,
        )


@dataclass(frozen=True, slots=True)
class TargetSupportRealizationKey:
    """Exact selector-owned identity below one expected slot."""

    source_extension: str
    selector_path: tuple[str, ...]
    required_features: tuple[str, ...]
    required_compiler_capabilities: tuple[str, ...]
    concrete_lanes: int | None
    simd_type_base_bindings: tuple[tuple[str, str], ...]
    variant_names: tuple[str, ...]

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.source_extension,
            self.selector_path,
            self.required_features,
            self.required_compiler_capabilities,
            -1 if self.concrete_lanes is None else self.concrete_lanes,
            self.simd_type_base_bindings,
            self.variant_names,
        )


@dataclass(frozen=True, slots=True)
class TargetSupportEntry:
    """Final generation outcome for one expected slot realization."""

    key: TargetSupportKey
    realization: TargetSupportRealizationKey | None
    status: TargetSupportStatus
    reason_id: str | None = None
    implementation_state: ImplementationState | None = None

    def sort_key(self) -> tuple[object, ...]:
        return (
            *self.key.sort_key(),
            () if self.realization is None else self.realization.sort_key(),
        )


@dataclass(frozen=True, slots=True)
class TargetSupportTrace:
    entries: tuple[TargetSupportEntry, ...]


def target_support_key(
    profile: str,
    backend: str,
    primitive: Primitive,
    target_extension: str,
    type_tag: str,
    conversion_target: str | None,
) -> TargetSupportKey:
    overload = primitive.overload
    return TargetSupportKey(
        profile=profile,
        backend=backend,
        primitive=primitive.name,
        signature=primitive.signature,
        attributes=tuple(sorted(primitive.attributes.items())),
        result_target=primitive.result_target,
        overload=(
            None
            if overload is None
            else (overload.axis, overload.value, overload.declares_primary)
        ),
        type_tag=type_tag,
        target_extension=target_extension,
        conversion_target=conversion_target,
    )


def realization_key(
    selected: "SelectedImplementation",
) -> TargetSupportRealizationKey:
    return TargetSupportRealizationKey(
        source_extension=selected.implementation.extension,
        selector_path=selected.implementation.selector_path,
        required_features=tuple(sorted(selected.required_features)),
        required_compiler_capabilities=tuple(
            sorted(selected.required_compiler_capabilities)
        ),
        concrete_lanes=selected.concrete_lanes,
        simd_type_base_bindings=tuple(
            (item.param_name, item.base_tag)
            for item in selected.simd_type_base_bindings
        ),
        variant_names=tuple(
            variant.name for variant in selected.implementation.variants
        ),
    )


__all__ = (
    "TargetSupportEntry",
    "TargetSupportKey",
    "TargetSupportRealizationKey",
    "TargetSupportStatus",
    "TargetSupportTrace",
    "realization_key",
    "target_support_key",
)
