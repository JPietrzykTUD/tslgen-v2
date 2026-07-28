"""Cargo layout projection for typed Rust policy-consumption facts."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.backend.rust_policy_consumption import (
    RustPolicyConsumptionPlan,
    RustPolicyConsumptionProfile,
)
from tslc.backend.rust_static_selection import (
    RustStaticProfileSelection,
    RustStaticSelectionPlan,
)
from tslc.render._common import slug


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionNames:
    """Generated Cargo and artifact names for one consumable profile."""

    profile_slug: str
    descriptor_path: str
    mapping_source_path: str
    materialized_mapping_file: str

    def __post_init__(self) -> None:
        if any(
            not value
            for value in (
                self.profile_slug,
                self.descriptor_path,
                self.mapping_source_path,
                self.materialized_mapping_file,
            )
        ):
            raise ValueError("Rust policy consumption names must be complete")


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionRenderProfile:
    """One semantic consumption profile paired with its Cargo layout."""

    profile: RustPolicyConsumptionProfile
    static_selection: RustStaticProfileSelection
    names: RustPolicyConsumptionNames

    def __post_init__(self) -> None:
        if self.static_selection.profile_name != self.profile.profile_name:
            raise ValueError(
                "Rust policy consumption target must match its profile"
            )


@dataclass(frozen=True, slots=True)
class RustPolicyConsumptionRenderPlan:
    """One layout projection shared by project and benchmark rendering."""

    profiles: tuple[RustPolicyConsumptionRenderProfile, ...]

    def __post_init__(self) -> None:
        names = tuple(profile.profile.profile_name for profile in self.profiles)
        if len(set(names)) != len(names):
            raise ValueError("Rust policy render profile names must be unique")

    def profile(
        self, profile_name: str
    ) -> RustPolicyConsumptionRenderProfile | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile.profile_name == profile_name
            ),
            None,
        )


EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN = RustPolicyConsumptionRenderPlan(
    profiles=()
)


def plan_rust_policy_consumption_render(
    plan: RustPolicyConsumptionPlan,
    static_selection_plan: RustStaticSelectionPlan,
) -> RustPolicyConsumptionRenderPlan:
    """Project semantic consumption facts into deterministic Cargo names once."""

    profiles = []
    for profile in plan.profiles:
        profile_slug = slug(profile.profile_name)
        static_selection = static_selection_plan.profile(profile.profile_name)
        if static_selection is None:
            raise ValueError(
                f"Rust policy profile {profile.profile_name!r} has no compile-target selection"
            )
        profiles.append(
            RustPolicyConsumptionRenderProfile(
                profile=profile,
                static_selection=static_selection,
                names=RustPolicyConsumptionNames(
                    profile_slug=profile_slug,
                    descriptor_path=(
                        f"bench/policy_consumption_{profile_slug}.json"
                    ),
                    mapping_source_path=(
                        f"bench/policy_consumption_{profile_slug}.rs"
                    ),
                    materialized_mapping_file=(
                        f"tsl_variant_policy_{profile_slug}.rs"
                    ),
                ),
            )
        )
    return RustPolicyConsumptionRenderPlan(profiles=tuple(profiles))


__all__ = (
    "EMPTY_RUST_POLICY_CONSUMPTION_RENDER_PLAN",
    "RustPolicyConsumptionNames",
    "RustPolicyConsumptionRenderPlan",
    "RustPolicyConsumptionRenderProfile",
    "plan_rust_policy_consumption_render",
)
