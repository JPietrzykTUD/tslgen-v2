"""Typed compile-time implementation selection for generated Rust profiles."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from typing import Literal

from tslc.backend.emitted_profile import EmittedProfile
from tslc.benchmark.model import SpecializationKey
from tslc.lower.lowerer import LoweredSpecialization

RustPolicySelectionStatus = Literal["supported", "report_only"]
_PolicySlot = tuple[
    SpecializationKey,
    LoweredSpecialization,
    tuple[str, ...],
    str | None,
    tuple[str, str] | None,
]


@dataclass(frozen=True, slots=True)
class RustPolicySelection:
    """One policy-supported Rust specialization and its compile-time choice."""

    key: SpecializationKey
    specialization: LoweredSpecialization
    candidate_ids: tuple[str, ...]
    selected_candidate: str

    def __post_init__(self) -> None:
        expected_candidates = ("default", *self.specialization.variant_names)
        if self.candidate_ids != expected_candidates:
            raise ValueError(
                "Rust policy selection candidates do not match the lowered specialization"
            )
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("Rust policy selection candidate IDs must be unique")
        if self.selected_candidate not in self.candidate_ids:
            raise ValueError(
                f"Rust policy selects unavailable candidate {self.selected_candidate!r}"
            )
        if reason := rust_policy_selection_reason(self.key, self.specialization):
            raise ValueError(f"unsupported Rust policy selection: {reason}")


@dataclass(frozen=True, slots=True)
class RustPolicySelectionCoverageEntry:
    """Policy eligibility kept separate from benchmark-report coverage."""

    key: SpecializationKey
    candidate_ids: tuple[str, ...]
    status: RustPolicySelectionStatus
    reason: str = ""

    def __post_init__(self) -> None:
        if self.key.backend_id != "rust":
            raise ValueError("Rust policy coverage requires a Rust specialization key")
        if not self.candidate_ids or self.candidate_ids[0] != "default":
            raise ValueError("Rust policy coverage must include the authored default")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("Rust policy coverage candidate IDs must be unique")
        if self.status == "supported" and self.reason:
            raise ValueError("supported Rust policy coverage cannot have a reason")
        if self.status == "report_only" and not self.reason:
            raise ValueError("report-only Rust policy coverage requires a reason")


@dataclass(frozen=True, slots=True)
class RustPolicySelectionProfile:
    """Complete policy-selection evidence for one generated Rust profile."""

    profile_name: str
    selections: tuple[RustPolicySelection, ...]
    coverage: tuple[RustPolicySelectionCoverageEntry, ...]

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("Rust policy selection profiles require a name")
        selection_keys = tuple(selection.key for selection in self.selections)
        coverage_keys = tuple(entry.key for entry in self.coverage)
        if any(key.profile_name != self.profile_name for key in selection_keys):
            raise ValueError("Rust policy selections must match their profile name")
        if any(key.profile_name != self.profile_name for key in coverage_keys):
            raise ValueError("Rust policy coverage must match its profile name")
        if len(set(selection_keys)) != len(selection_keys):
            raise ValueError("Rust policy selection keys must be unique within a profile")
        if len(set(coverage_keys)) != len(coverage_keys):
            raise ValueError("Rust policy coverage keys must be unique within a profile")
        supported = {
            entry.key: entry.candidate_ids
            for entry in self.coverage
            if entry.status == "supported"
        }
        selected = {
            selection.key: selection.candidate_ids for selection in self.selections
        }
        if selected != supported:
            raise ValueError(
                "Rust policy selections must exactly match supported coverage entries"
            )


@dataclass(frozen=True, slots=True)
class RustPolicySelectionPlan:
    """Deterministic complete default mapping plus report-only evidence."""

    profiles: tuple[RustPolicySelectionProfile, ...]

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if len(set(names)) != len(names):
            raise ValueError("Rust policy selection profile names must be unique")

    def profile(self, profile_name: str) -> RustPolicySelectionProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile_name == profile_name
            ),
            None,
        )

    def with_forced_selection(
        self,
        key: SpecializationKey,
        candidate_id: str,
    ) -> RustPolicySelectionPlan:
        """Return a validated immutable plan with one supported choice replaced."""

        updated_profiles: list[RustPolicySelectionProfile] = []
        matched = False
        for profile in self.profiles:
            selections: list[RustPolicySelection] = []
            for selection in profile.selections:
                if selection.key != key:
                    selections.append(selection)
                    continue
                matched = True
                if candidate_id not in selection.candidate_ids:
                    raise ValueError(
                        f"Rust policy candidate {candidate_id!r} is unavailable for "
                        f"{key.primitive_name!r}"
                    )
                selections.append(
                    replace(selection, selected_candidate=candidate_id)
                )
            updated_profiles.append(replace(profile, selections=tuple(selections)))

        if not matched:
            report_only = next(
                (
                    entry
                    for profile in self.profiles
                    for entry in profile.coverage
                    if entry.key == key and entry.status == "report_only"
                ),
                None,
            )
            if report_only is not None:
                raise ValueError(
                    f"Rust specialization {key.primitive_name!r} is report-only: "
                    f"{report_only.reason}"
                )
            raise ValueError("Rust policy specialization key is not present in this plan")

        return replace(self, profiles=tuple(updated_profiles))


def plan_rust_policy_selection(
    profiles: tuple[EmittedProfile, ...],
) -> RustPolicySelectionPlan:
    """Plan the narrow stable-Rust selection family from finalized backend facts."""

    # The benchmark subsystem owns policy identity.  Keep this import local so
    # the Rust backend depends only on its small typed identity projection.
    from tslc.benchmark.identity import specialization_key

    planned_profiles: list[RustPolicySelectionProfile] = []
    for profile in sorted(profiles, key=lambda item: item.profile.name):
        by_primitive = profile.specializations("rust")
        slots: list[_PolicySlot] = []
        for primitive_name in sorted(by_primitive):
            specializations = by_primitive[primitive_name]
            for spec in specializations:
                if not spec.variant_bodies:
                    continue
                key = specialization_key(
                    backend_id="rust",
                    profile=profile,
                    specialization=spec,
                    primitive_specializations=specializations,
                )
                candidate_ids = ("default", *spec.variant_names)
                reason = rust_policy_selection_reason(key, spec)
                if (
                    reason is None
                    and candidate_ids != ("default", "generic_fallback")
                ):
                    reason = (
                        "initial Rust policy selection requires the proven pilot "
                        "candidate inventory"
                    )
                impl_identity = (
                    (primitive_name, spec.vector_spelling)
                    if reason is None and spec.vector_spelling is not None
                    else None
                )
                slots.append((key, spec, candidate_ids, reason, impl_identity))

        identity_counts = Counter(
            identity
            for _key, _spec, _candidates, reason, identity in slots
            if reason is None and identity is not None
        )
        slots_by_key: dict[SpecializationKey, list[_PolicySlot]] = {}
        for slot in slots:
            slots_by_key.setdefault(slot[0], []).append(slot)
        selections: list[RustPolicySelection] = []
        coverage: list[RustPolicySelectionCoverageEntry] = []
        for key in sorted(
            slots_by_key, key=lambda item: repr(item.canonical_fields())
        ):
            matching_slots = slots_by_key[key]
            if len(matching_slots) > 1:
                candidate_ids = (
                    "default",
                    *sorted(
                        {
                            candidate_id
                            for _key, _spec, candidates, _reason, _identity
                            in matching_slots
                            for candidate_id in candidates
                            if candidate_id != "default"
                        }
                    ),
                )
                coverage.append(
                    RustPolicySelectionCoverageEntry(
                        key=key,
                        candidate_ids=candidate_ids,
                        status="report_only",
                        reason="multiple lowered slots share the same Rust policy key",
                    )
                )
                continue
            _key, spec, candidate_ids, reason, impl_identity = matching_slots[0]
            if (
                reason is None
                and impl_identity is not None
                and identity_counts[impl_identity] > 1
            ):
                reason = (
                    "multiple specialization keys would emit the same Rust selection impl"
                )
            if reason is not None:
                coverage.append(
                    RustPolicySelectionCoverageEntry(
                        key=key,
                        candidate_ids=candidate_ids,
                        status="report_only",
                        reason=reason,
                    )
                )
                continue
            selection = RustPolicySelection(
                key=key,
                specialization=spec,
                candidate_ids=candidate_ids,
                selected_candidate="default",
            )
            selections.append(selection)
            coverage.append(
                RustPolicySelectionCoverageEntry(
                    key=key,
                    candidate_ids=candidate_ids,
                    status="supported",
                )
            )

        planned_profiles.append(
            RustPolicySelectionProfile(
                profile_name=profile.profile.name,
                selections=tuple(selections),
                coverage=tuple(coverage),
            )
        )
    return RustPolicySelectionPlan(profiles=tuple(planned_profiles))


def validate_rust_policy_selection_plan(
    profiles: tuple[EmittedProfile, ...],
    plan: RustPolicySelectionPlan,
) -> None:
    """Reject a stale, partial, or foreign mapping before Rust source rendering."""

    expected = plan_rust_policy_selection(profiles)
    expected_by_name = {
        profile.profile_name: profile for profile in expected.profiles
    }
    actual_by_name = {profile.profile_name: profile for profile in plan.profiles}
    if actual_by_name.keys() != expected_by_name.keys():
        raise ValueError(
            "Rust policy selection plan does not match the rendered profile inventory"
        )
    for profile_name, expected_profile in expected_by_name.items():
        actual_profile = actual_by_name[profile_name]
        expected_inventory = tuple(
            (selection.key, selection.specialization, selection.candidate_ids)
            for selection in expected_profile.selections
        )
        actual_inventory = tuple(
            (selection.key, selection.specialization, selection.candidate_ids)
            for selection in actual_profile.selections
        )
        if (
            actual_profile.coverage != expected_profile.coverage
            or actual_inventory != expected_inventory
        ):
            raise ValueError(
                "Rust policy selection plan is stale or incomplete for profile "
                f"{profile_name!r}"
            )


def rust_policy_selection_reason(
    key: SpecializationKey,
    spec: LoweredSpecialization,
) -> str | None:
    """Return why an exact Rust candidate key cannot use the stable selection seam."""

    if key.backend_id != "rust" or spec.backend_id != "rust":
        return "policy selection requires Rust backend facts"
    key_identity = (
        key.primitive_name,
        key.source_primitive_name,
        key.extension_name,
        key.type_tag,
        key.result_kind,
        key.param_kinds,
    )
    spec_identity = (
        spec.primitive_name,
        spec.source_primitive_name,
        spec.extension_name,
        spec.type_tag,
        spec.result_kind,
        spec.param_kinds,
    )
    if key_identity != spec_identity:
        return "Rust policy selection key does not match its specialization"
    if key.lanes is None or key.lanes <= 0:
        return "policy selection requires a fixed-width hardware vector"
    if key.header_group is not None:
        return "opt-in header-group specializations are report-only"
    if spec.uses_sized_vector:
        return "sized-vector specializations are report-only"
    if spec.vector_spelling is None:
        return "policy selection requires a concrete Rust vector spelling"
    if spec.immediate is not None or key.immediate is not None:
        return "immediate specializations are report-only"
    if spec.result_kind != "v" or not spec.param_kinds or any(
        kind != "v" for kind in spec.param_kinds
    ):
        return (
            "policy selection supports only vector-register results with "
            "vector-register parameters"
        )
    if any(override is not None for override in spec.effective_param_type_overrides):
        return "backend-specific parameter type overrides are report-only"
    if key.overload_parameter_positions:
        return "overloaded Rust wrapper shapes are report-only"
    if spec.mask_policy is not None:
        return "masked specializations are report-only"
    if (
        spec.target is not None
        or key.target_type_tag is not None
        or key.target_extension_name is not None
    ):
        return "representation-changing specializations are report-only"
    if spec.axis or key.axis:
        return "const-generic axis specializations are report-only"
    if spec.generic_params or key.generic_values:
        return "const-generic specializations are report-only"
    if spec.type_params or key.simd_type_base_bindings:
        return "SIMD-type-parameter specializations are report-only"
    if spec.lane_list_params:
        return "lane-list specializations are report-only"
    if (
        key.profile_name,
        key.primitive_name,
        key.source_primitive_name,
        key.extension_name,
        key.type_tag,
        key.result_kind,
        key.param_kinds,
        key.lanes,
        spec.vector_spelling,
        spec.safety.caller_unsafe,
    ) != (
        "sse2",
        "mul",
        "mul",
        "sse",
        "si8",
        "v",
        ("v", "v"),
        16,
        "Simd<i8, Sse>",
        False,
    ):
        return "initial Rust policy selection supports only the proven sse2 mul pilot"
    return None


__all__ = (
    "RustPolicySelection",
    "RustPolicySelectionCoverageEntry",
    "RustPolicySelectionPlan",
    "RustPolicySelectionProfile",
    "RustPolicySelectionStatus",
    "plan_rust_policy_selection",
    "rust_policy_selection_reason",
    "validate_rust_policy_selection_plan",
)
