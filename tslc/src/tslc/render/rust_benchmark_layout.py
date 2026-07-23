"""Shared Cargo layout for generated Rust benchmark profiles."""

from __future__ import annotations

from dataclasses import dataclass

from tslc.render._common import slug


@dataclass(frozen=True, slots=True)
class RustBenchmarkLayout:
    """Final Cargo names shared by project and benchmark rendering."""

    profile_name: str
    profile_slug: str
    benchmark_target: str
    cargo_features: tuple[str, ...]
    artifact_subdirectory: str
    context_example: str

    def __post_init__(self) -> None:
        if any(
            not value
            for value in (
                self.profile_name,
                self.profile_slug,
                self.benchmark_target,
                self.artifact_subdirectory,
                self.context_example,
            )
        ) or self.cargo_features:
            raise ValueError("Rust benchmark layout must be complete")

    @property
    def cargo_features_argument(self) -> str:
        return ",".join(self.cargo_features)


@dataclass(frozen=True, slots=True)
class RustBenchmarkLayoutPlan:
    """Deterministic Cargo layout for every emitted Rust profile."""

    profiles: tuple[RustBenchmarkLayout, ...]

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if len(set(names)) != len(names):
            raise ValueError("Rust benchmark layout profile names must be unique")

    def profile(self, profile_name: str) -> RustBenchmarkLayout | None:
        return next(
            (
                profile
                for profile in self.profiles
                if profile.profile_name == profile_name
            ),
            None,
        )


def plan_rust_benchmark_layout(
    profile_names: tuple[str, ...],
) -> RustBenchmarkLayoutPlan:
    """Project profile identities into shared Cargo benchmark names once."""

    profiles = []
    for profile_name in profile_names:
        profile_slug = slug(profile_name)
        profiles.append(
            RustBenchmarkLayout(
                profile_name=profile_name,
                profile_slug=profile_slug,
                benchmark_target=f"tsl_variant_bench_{profile_slug}",
                cargo_features=(),
                artifact_subdirectory=f"tsl-benchmark/{profile_slug}",
                context_example=f"local-native-{profile_slug}-v1",
            )
        )
    return RustBenchmarkLayoutPlan(profiles=tuple(profiles))


__all__ = (
    "RustBenchmarkLayout",
    "RustBenchmarkLayoutPlan",
    "plan_rust_benchmark_layout",
)
