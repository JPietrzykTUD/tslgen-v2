"""Typed values in the generated-library release contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tslc.catalog.primitive_identity import primitive_declaration_identity
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.lower.implementation_facts import (
    ImplementationState,
    implementation_state_description,
)
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


class ProfileSelection(Enum):
    ALL_SUPPORTED = "all_supported"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class ProductPolicy:
    product_id: str
    name: str
    version: str
    status: str


@dataclass(frozen=True, slots=True)
class ComponentPolicy:
    component_id: str
    compatibility: str
    required_major: int


@dataclass(frozen=True, slots=True)
class BackendProfilePolicy:
    backend_id: str
    selection: ProfileSelection
    profiles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetScopePolicy:
    scope_id: str
    backend_id: str
    profiles: tuple[str, ...]
    runtime_scalable_profiles: tuple[str, ...]
    profile_extensions: tuple[tuple[str, str], ...]
    excludes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetSpecificCallable:
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class TargetSlotExclusionPolicy:
    """One reviewed exclusion from an otherwise declared target scope."""

    profiles: tuple[str, ...]
    backend_id: str
    callable_identities: tuple[str, ...]
    type_tags: tuple[str, ...]
    reason_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class AcceleratedCorePolicy:
    selection: str
    portable_callable_names: tuple[str, ...]
    fallback_policy: str
    fallback_exceptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReleasePolicy:
    schema_version: int
    product: ProductPolicy
    components: tuple[ComponentPolicy, ...]
    backend_profiles: tuple[BackendProfilePolicy, ...]
    target_scopes: tuple[TargetScopePolicy, ...]
    target_specific_callables: tuple[TargetSpecificCallable, ...]
    target_slot_exclusions: tuple[TargetSlotExclusionPolicy, ...]
    accelerated_core: AcceleratedCorePolicy


@dataclass(frozen=True, slots=True)
class CallableFamily:
    name: str
    signature: str
    attributes: tuple[tuple[str, str], ...]
    result_target: tuple[str, ...]
    overload: tuple[str, str, bool] | None
    checked_companion: bool
    semantic_categories: tuple[str, ...]
    fixed_shape_only: bool
    source_contract_sha256: str

    @property
    def identity(self) -> str:
        return primitive_declaration_identity(
            self.name,
            self.signature,
            self.attributes,
            self.result_target,
            self.overload,
        )

    def payload(self) -> dict[str, object]:
        return {
            "identity": self.identity,
            "name": self.name,
            "signature": self.signature,
            "attributes": dict(self.attributes),
            "result_target": list(self.result_target),
            "overload": (
                None
                if self.overload is None
                else {
                    "axis": self.overload[0],
                    "value": self.overload[1],
                    "declares_primary": self.overload[2],
                }
            ),
            "checked_companion": self.checked_companion,
            "semantic_categories": list(self.semantic_categories),
            "fixed_shape_only": self.fixed_shape_only,
            "source_contract_sha256": self.source_contract_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReleaseProfile:
    name: str
    family: str
    features: tuple[str, ...]
    compile_modes: tuple[str, ...]
    auto_detect_gate: str | None

    def payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "family": self.family,
            "features": list(self.features),
            "compile_modes": list(self.compile_modes),
            "auto_detect_gate": self.auto_detect_gate,
        }


@dataclass(frozen=True, slots=True)
class BackendReleaseContract:
    backend_id: str
    selection: ProfileSelection
    profiles: tuple[ReleaseProfile, ...]

    def payload(self) -> dict[str, object]:
        return {
            "id": self.backend_id,
            "profile_selection": self.selection.value,
            "profiles": [profile.payload() for profile in self.profiles],
        }


@dataclass(frozen=True, slots=True)
class ComponentContract:
    component_id: str
    version: str
    compatibility: str

    def payload(self) -> dict[str, object]:
        return {
            "id": self.component_id,
            "version": self.version,
            "compatibility": self.compatibility,
        }


@dataclass(frozen=True, slots=True)
class ReleaseContract:
    policy: ReleasePolicy
    components: tuple[ComponentContract, ...]
    backends: tuple[BackendReleaseContract, ...]
    callable_families: tuple[CallableFamily, ...]
    algorithms: tuple[str, ...]
    accelerated_core: tuple[str, ...]
    portable_utility_families: tuple[str, ...]
    public_api_baseline_version: int
    public_api_baseline_digest: str
    exact_cpp_declarations: int
    exact_rust_declarations: int

    def backend(self, backend_id: str) -> BackendReleaseContract:
        for backend in self.backends:
            if backend.backend_id == backend_id:
                return backend
        raise KeyError(backend_id)

    def payload(self) -> dict[str, object]:
        fixed_shape = tuple(
            family.identity for family in self.callable_families if family.fixed_shape_only
        )
        target_specific = {
            item.name: item.reason for item in self.policy.target_specific_callables
        }
        return {
            "schema_version": 1,
            "product": {
                "id": self.policy.product.product_id,
                "name": self.policy.product.name,
                "version": self.policy.product.version,
                "status": self.policy.product.status,
            },
            "components": [component.payload() for component in self.components],
            "backends": [backend.payload() for backend in self.backends],
            "support_universe": {
                "scalar_types": list(DEFAULT_SCALAR_TYPE_TAGS),
                "primitive_callable_families": [
                    family.payload() for family in self.callable_families
                ],
                "algorithm_callable_families": list(self.algorithms),
                "fixed_shape_signature_kinds": sorted(
                    DEFAULT_SUPPORT_POLICY.fixed_shape_signature_kinds
                ),
                "fixed_shape_callable_families": list(fixed_shape),
                "target_specific_callables": target_specific,
                "target_slot_exclusions": [
                    {
                        "profiles": list(item.profiles),
                        "backend": item.backend_id,
                        "callable_identities": list(item.callable_identities),
                        "type_tags": list(item.type_tags),
                        "reason_id": item.reason_id,
                        "reason": item.reason,
                    }
                    for item in self.policy.target_slot_exclusions
                ],
                "accelerated_core_callable_families": list(self.accelerated_core),
                "portable_utility_callable_families": list(
                    self.portable_utility_families
                ),
                "public_api_baseline": {
                    "path": "coverage/tsl-v1-public-api.json",
                    "schema_version": self.public_api_baseline_version,
                    "sha256": self.public_api_baseline_digest,
                    "exact_declaration_counts": {
                        "cpp": self.exact_cpp_declarations,
                        "rust": self.exact_rust_declarations,
                    },
                },
            },
            "safety_api": {
                "unchecked": (
                    "direct operation with no hidden sanitization; documented caller "
                    "preconditions remain the caller's responsibility"
                ),
                "checked_companion": (
                    "exists only when every applicable catastrophic runtime "
                    "precondition is complete, checkable, and representable"
                ),
                "cpp_value_result": (
                    "returns the operation value directly and reports through "
                    "precondition_error&"
                ),
                "cpp_failure_result": (
                    "the operation is not invoked; an initialized but semantically "
                    "unspecified value placeholder must not be used before inspecting "
                    "the error"
                ),
                "rust": (
                    "checked calls return Result; an unsuffixed function is unsafe "
                    "only when a catastrophic caller obligation remains"
                ),
                "internal_unsafety": (
                    "internal_unsafe and raw_memory implementation mechanisms do not "
                    "by themselves make a public Rust function unsafe"
                ),
            },
            "implementation_states": [
                {
                    "id": state.value,
                    "meaning": implementation_state_description(state),
                }
                for state in ImplementationState
            ],
            "accelerated_core_policy": {
                "selection": self.policy.accelerated_core.selection,
                "portable_callable_names": list(
                    self.policy.accelerated_core.portable_callable_names
                ),
                "fallback_policy": self.policy.accelerated_core.fallback_policy,
                "fallback_exceptions": list(
                    self.policy.accelerated_core.fallback_exceptions
                ),
            },
            "target_scopes": [
                {
                    "id": scope.scope_id,
                    "backend": scope.backend_id,
                    "profiles": list(scope.profiles),
                    "runtime_scalable_profiles": list(
                        scope.runtime_scalable_profiles
                    ),
                    "profile_extensions": dict(scope.profile_extensions),
                    "excludes": list(scope.excludes),
                }
                for scope in self.policy.target_scopes
            ],
        }


__all__ = (
    "AcceleratedCorePolicy",
    "BackendProfilePolicy",
    "BackendReleaseContract",
    "CallableFamily",
    "ComponentContract",
    "ComponentPolicy",
    "ProductPolicy",
    "ProfileSelection",
    "ReleaseContract",
    "ReleasePolicy",
    "ReleaseProfile",
    "TargetScopePolicy",
    "TargetSlotExclusionPolicy",
    "TargetSpecificCallable",
)
