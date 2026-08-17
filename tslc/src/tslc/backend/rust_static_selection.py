"""Typed compile-target selection for generated Rust representations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re

from tslc.backend.emitted_profile import EmittedProfile, used_vector_type_specs
from tslc.backend.rust_vectors import (
    RustVectorRegistration,
    rust_imask_type,
    rust_imask_width,
    rust_mask_type,
    rust_vector_registrations,
)
from tslc.backend.target_capability import rust_arch_module, rust_extension_tag
from tslc.catalog.model import Extension
from tslc.catalog.scalar_types import scalar_bit_width
from tslc.diagnostics import Diagnostic, diagnostic_at, sort_diagnostics
from tslc.lower.lowerer import LoweredSpecialization
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

_RUST_CFG_ARCH = re.compile(r"^[a-z0-9_]+$")
_RUST_CFG_FEATURE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class RustTargetRequirement:
    """One source-derived Rust compile-target predicate."""

    target_arch: str
    target_features: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _RUST_CFG_ARCH.fullmatch(self.target_arch):
            raise ValueError("Rust target architecture is not a valid cfg value")
        if tuple(sorted(set(self.target_features))) != self.target_features:
            raise ValueError("Rust target features must be sorted and unique")
        if any(not _RUST_CFG_FEATURE.fullmatch(item) for item in self.target_features):
            raise ValueError("Rust target feature is not a valid cfg value")

    def strictly_contains(self, other: RustTargetRequirement) -> bool:
        return self.target_arch == other.target_arch and set(
            self.target_features
        ) > set(other.target_features)


@dataclass(frozen=True, slots=True)
class RustStaticVectorMapping:
    """One admitted ``(element, lanes)`` representation for a compile target."""

    type_tag: str
    base_spelling: str
    lanes: int
    total_bits: int
    vector_spelling: str
    imask_spelling: str
    extension_name: str | None = None
    extension_tag_spelling: str | None = None
    uses_sized_vector: bool = False
    imask_bits: int = 0

    def __post_init__(self) -> None:
        if (
            not self.type_tag
            or not self.base_spelling
            or not self.vector_spelling
            or not self.imask_spelling
        ):
            raise ValueError("Rust static vector mappings require complete type facts")
        if self.lanes <= 0 or self.total_bits <= 0:
            raise ValueError("Rust static vector mappings require positive sizes")
        if (self.extension_name is None) != (self.extension_tag_spelling is None):
            raise ValueError(
                "Rust hardware mappings require both extension identity and tag spelling"
            )
        if self.extension_name is not None and self.uses_sized_vector:
            raise ValueError("Rust hardware mappings cannot use sized fallback vectors")
        if self.imask_bits == 0:
            canonical_width = {
                "u8": 8,
                "u16": 16,
                "u32": 32,
                "u64": 64,
            }.get(self.imask_spelling)
            object.__setattr__(
                self,
                "imask_bits",
                canonical_width or rust_imask_width(self.lanes),
            )
        if self.imask_bits not in {8, 16, 32, 64}:
            raise ValueError(
                "Rust static vector mappings require an 8-, 16-, 32-, "
                "or 64-bit integral mask"
            )

    @property
    def uses_hardware(self) -> bool:
        return self.extension_name is not None


@dataclass(frozen=True, slots=True)
class RustStaticProfileSelection:
    """One emitted profile selected by target cfg, excluding stronger profiles."""

    profile_name: str
    requirement: RustTargetRequirement
    stronger_requirements: tuple[RustTargetRequirement, ...]
    mappings: tuple[RustStaticVectorMapping, ...]

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("Rust static profile selections require a profile name")
        if any(
            not requirement.strictly_contains(self.requirement)
            for requirement in self.stronger_requirements
        ):
            raise ValueError("Rust static selection exclusions must be stronger targets")
        keys = tuple((item.type_tag, item.lanes) for item in self.mappings)
        if len(set(keys)) != len(keys):
            raise ValueError("Rust static profile mappings must be unique")


@dataclass(frozen=True, slots=True)
class RustStaticFallbackModule:
    """Source-selected generic/scalar bodies used when no hardware profile matches."""

    primitive_specializations: tuple[
        tuple[str, tuple[LoweredSpecialization, ...]], ...
    ]
    extensions: tuple[tuple[str, Extension], ...]
    metadata_profile_name: str = "target_fallback"
    metadata_profile_family: str = "fallback"

    def __post_init__(self) -> None:
        primitive_names = tuple(name for name, _specs in self.primitive_specializations)
        extension_names = tuple(name for name, _extension in self.extensions)
        if not self.metadata_profile_name or not self.metadata_profile_family:
            raise ValueError(
                "Rust static fallback metadata requires profile and family identities"
            )
        if len(set(primitive_names)) != len(primitive_names):
            raise ValueError("Rust static fallback primitives must be unique")
        if len(set(extension_names)) != len(extension_names):
            raise ValueError("Rust static fallback extensions must be unique")
        if any(not specs for _name, specs in self.primitive_specializations):
            raise ValueError("Rust static fallback primitive groups cannot be empty")
        if any(
            not extension.is_unconditional_implementation_fallback
            for _name, extension in self.extensions
        ):
            raise ValueError(
                "Rust static fallback extensions must be unconditional source fallbacks"
            )

    def specializations_by_primitive(
        self,
    ) -> dict[str, tuple[LoweredSpecialization, ...]]:
        return dict(self.primitive_specializations)

    def extensions_by_name(self) -> dict[str, Extension]:
        return dict(self.extensions)


@dataclass(frozen=True, slots=True)
class RustStaticSelectionPlan:
    """One deterministic target-selected profile plus an exact generic fallback."""

    profiles: tuple[RustStaticProfileSelection, ...]
    fallback_mappings: tuple[RustStaticVectorMapping, ...]
    fallback_module: RustStaticFallbackModule

    def __post_init__(self) -> None:
        names = tuple(profile.profile_name for profile in self.profiles)
        if len(set(names)) != len(names):
            raise ValueError("Rust static profile names must be unique")
        fallback_keys = tuple(
            (item.type_tag, item.lanes) for item in self.fallback_mappings
        )
        if len(set(fallback_keys)) != len(fallback_keys):
            raise ValueError("Rust static fallback mappings must be unique")
        if any(item.uses_hardware for item in self.fallback_mappings):
            raise ValueError("Rust static fallback mappings cannot use hardware")

    def profile(self, profile_name: str) -> RustStaticProfileSelection | None:
        return next(
            (profile for profile in self.profiles if profile.profile_name == profile_name),
            None,
        )


class RustStaticSelectionError(ValueError):
    """Planning failed with source-oriented backend diagnostics."""

    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(item.message for item in diagnostics))


def plan_rust_static_selection(
    profiles: tuple[EmittedProfile, ...],
) -> RustStaticSelectionPlan:
    """Build the immutable Rust representation mapping from emitted facts."""

    plan, diagnostics = _plan_rust_static_selection(profiles)
    if diagnostics:
        raise RustStaticSelectionError(diagnostics)
    assert plan is not None
    return plan


def validate_rust_static_selection(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[Diagnostic, ...]:
    """Return source/profile diagnostics without entering rendering."""

    _plan, diagnostics = _plan_rust_static_selection(profiles)
    return diagnostics


def validate_rust_static_selection_plan(
    profiles: tuple[EmittedProfile, ...],
    plan: RustStaticSelectionPlan,
) -> None:
    """Reject a stale or foreign target-selection plan before rendering."""

    if plan != plan_rust_static_selection(profiles):
        raise ValueError(
            "Rust static selection plan does not match the emitted profile inventory"
        )


def _plan_rust_static_selection(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[RustStaticSelectionPlan | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    type_facts = _generic_type_facts(profiles)
    admitted_widths = _admitted_fixed_widths(profiles)
    fallback_mappings = _fallback_mappings(type_facts, admitted_widths)
    fallback_module, fallback_diagnostics = _fallback_module(profiles)
    diagnostics.extend(fallback_diagnostics)
    candidates: list[
        tuple[EmittedProfile, RustTargetRequirement, tuple[RustStaticVectorMapping, ...]]
    ] = []

    for emitted_profile in sorted(profiles, key=lambda item: item.profile.name):
        hardware_extensions = _hardware_extensions(emitted_profile)
        if not hardware_extensions:
            continue
        backend = (
            emitted_profile.profile_family.backend("rust")
            if emitted_profile.profile_family is not None
            else None
        )
        target_arch = None if backend is None else backend.target_arch
        if target_arch is None or not _RUST_CFG_ARCH.fullmatch(target_arch):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-RUST-MISSING-TARGET-ARCH",
                    message=(
                        f"Rust profile {emitted_profile.profile.name!r} emits hardware "
                        "vectors but its target-family backend has no valid target_arch"
                    ),
                    source=(
                        emitted_profile.profile_family.source
                        if emitted_profile.profile_family is not None
                        else None
                    ),
                )
            )
            continue
        extension_arches = tuple(
            rust_arch_module(extension) for extension in hardware_extensions
        )
        if any(arch is None for arch in extension_arches) or set(
            extension_arches
        ) != {target_arch}:
            rendered_arches = tuple(
                sorted({arch or "<missing>" for arch in extension_arches})
            )
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-RUST-TARGET-ARCH-MISMATCH",
                    message=(
                        f"Rust profile {emitted_profile.profile.name!r} target_arch "
                        f"{target_arch!r} does not match emitted register architecture(s): "
                        + ", ".join(rendered_arches)
                    ),
                    source=hardware_extensions[0].source,
                )
            )
            continue
        rendered_features = tuple(
            emitted_profile.profile.feature_spelling(feature, "rust")
            for feature in sorted(emitted_profile.profile.features)
        )
        duplicate_features = tuple(
            sorted(
                feature
                for feature in set(rendered_features)
                if rendered_features.count(feature) > 1
            )
        )
        if duplicate_features:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-RUST-DUPLICATE-TARGET-FEATURE-SPELLING",
                    message=(
                        f"Rust profile {emitted_profile.profile.name!r} maps multiple "
                        "source target features to the same rustc spelling(s): "
                        + ", ".join(duplicate_features)
                    ),
                    source=(
                        emitted_profile.profile_family.source
                        if emitted_profile.profile_family is not None
                        else None
                    ),
                )
            )
            continue
        target_features = tuple(sorted(rendered_features))
        invalid_features = tuple(
            feature
            for feature in target_features
            if not _RUST_CFG_FEATURE.fullmatch(feature)
        )
        if invalid_features:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-RUST-INVALID-TARGET-FEATURE",
                    message=(
                        f"Rust profile {emitted_profile.profile.name!r} has invalid rustc "
                        "target feature spelling(s): " + ", ".join(invalid_features)
                    ),
                    source=(
                        emitted_profile.profile_family.source
                        if emitted_profile.profile_family is not None
                        else None
                    ),
                )
            )
            continue
        requirement = RustTargetRequirement(target_arch, target_features)
        mappings, mapping_diagnostics = _profile_mappings(
            emitted_profile,
            type_facts,
            admitted_widths,
            frozenset(extension.name for extension in hardware_extensions),
        )
        diagnostics.extend(mapping_diagnostics)
        candidates.append((emitted_profile, requirement, mappings))

    by_arch: dict[
        str,
        list[tuple[EmittedProfile, RustTargetRequirement, tuple[RustStaticVectorMapping, ...]]],
    ] = defaultdict(list)
    for candidate in candidates:
        by_arch[candidate[1].target_arch].append(candidate)
    for arch, arch_candidates in sorted(by_arch.items()):
        for index, left in enumerate(arch_candidates):
            for right in arch_candidates[index + 1 :]:
                left_features = set(left[1].target_features)
                right_features = set(right[1].target_features)
                if left_features < right_features or right_features < left_features:
                    continue
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-RUST-AMBIGUOUS-TARGET-PROFILES",
                        message=(
                            f"Rust profiles {left[0].profile.name!r} and "
                            f"{right[0].profile.name!r} have overlapping, unordered "
                            f"compile-target requirements for {arch!r}"
                        ),
                        source=(
                            left[0].profile_family.source
                            if left[0].profile_family is not None
                            else None
                        ),
                    )
                )

    ordered_diagnostics = sort_diagnostics(diagnostics)
    if ordered_diagnostics:
        return None, ordered_diagnostics

    selections = tuple(
        RustStaticProfileSelection(
            profile_name=emitted_profile.profile.name,
            requirement=requirement,
            stronger_requirements=tuple(
                sorted(
                    (
                        other_requirement
                        for _other_profile, other_requirement, _mappings in candidates
                        if other_requirement.strictly_contains(requirement)
                    ),
                    key=lambda item: (item.target_arch, item.target_features),
                )
            ),
            mappings=mappings,
        )
        for emitted_profile, requirement, mappings in sorted(
            candidates,
            key=lambda item: (
                item[1].target_arch,
                len(item[1].target_features),
                item[1].target_features,
                item[0].profile.name,
            ),
        )
    )
    return RustStaticSelectionPlan(
        selections,
        fallback_mappings,
        fallback_module,
    ), ()


def _fallback_module(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[RustStaticFallbackModule, tuple[Diagnostic, ...]]:
    collected: dict[str, list[LoweredSpecialization]] = {}
    extensions: dict[str, Extension] = {}
    diagnostics: list[Diagnostic] = []
    for emitted_profile in sorted(profiles, key=lambda item: item.profile.name):
        for name, extension in emitted_profile.extensions.items():
            if not extension.is_unconditional_implementation_fallback:
                continue
            previous = extensions.setdefault(name, extension)
            if previous != extension:
                diagnostics.append(
                    diagnostic_at(
                        severity="error",
                        code="TSL-BACKEND-RUST-CONFLICTING-FALLBACK-EXTENSION",
                        message=(
                            "Rust emitted profiles disagree about fallback extension "
                            f"{name!r}"
                        ),
                        source=extension.source,
                    )
                )
        for primitive_name, specializations in emitted_profile.specializations(
            "rust"
        ).items():
            destination = collected.setdefault(primitive_name, [])
            for specialization in specializations:
                fallback_extension = emitted_profile.extensions.get(
                    specialization.extension_name
                )
                target_extension = (
                    emitted_profile.extensions.get(
                        specialization.target.extension_isa
                    )
                    if specialization.target is not None
                    else None
                )
                if (
                    fallback_extension is None
                    or not fallback_extension.is_unconditional_implementation_fallback
                    or (
                        target_extension is not None
                        and not target_extension.is_unconditional_implementation_fallback
                    )
                ):
                    continue
                if specialization not in destination:
                    destination.append(specialization)
    module = RustStaticFallbackModule(
        primitive_specializations=tuple(
            (name, tuple(specializations))
            for name, specializations in sorted(collected.items())
            if specializations
        ),
        extensions=tuple(sorted(extensions.items())),
    )
    return module, sort_diagnostics(diagnostics)


def _hardware_extensions(emitted_profile: EmittedProfile) -> tuple[Extension, ...]:
    supported_names = _profile_supported_hardware_extensions(emitted_profile)
    extensions: list[Extension] = []
    for name in emitted_profile.used_extensions("rust"):
        extension = emitted_profile.extensions.get(name)
        if (
            extension is not None
            and name in supported_names
            and extension.supports_backend("rust")
            and not extension.family_capability.implementation_fallback
            and extension.vector_bits_kind == "fixed"
            and extension.vector_bits > 0
        ):
            extensions.append(extension)
    return tuple(extensions)


def _profile_supported_hardware_extensions(
    emitted_profile: EmittedProfile,
) -> frozenset[str]:
    """Return extensions backed by source activation or selected feature evidence."""

    supported = {
        name
        for name, extension in emitted_profile.extensions.items()
        if (
            extension.active_when.target_features
            or extension.active_when.compile_modes
        )
        and extension.active_when.is_satisfied_by(
            emitted_profile.profile.features,
            emitted_profile.profile.compile_modes,
        )
    }
    for specializations in emitted_profile.specializations("rust").values():
        for specialization in specializations:
            if (
                not specialization.required_features
                or not specialization.required_features
                <= emitted_profile.profile.features
            ):
                continue
            supported.add(specialization.extension_name)
            if specialization.target is not None:
                supported.add(specialization.target.extension_isa)
    return frozenset(supported)


def _generic_type_facts(
    profiles: tuple[EmittedProfile, ...],
) -> tuple[tuple[str, str], ...]:
    facts: set[tuple[str, str]] = set()
    for emitted_profile in profiles:
        by_primitive = emitted_profile.specializations("rust")
        for extension_name, type_tag, base_spelling in used_vector_type_specs(
            by_primitive
        ):
            extension = emitted_profile.extensions.get(extension_name)
            if extension is not None and DEFAULT_SUPPORT_POLICY.uses_sized_vector(
                extension
            ):
                facts.add((type_tag, base_spelling))
    return tuple(sorted(facts))


def _admitted_fixed_widths(profiles: tuple[EmittedProfile, ...]) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                extension.vector_bits
                for emitted_profile in profiles
                for extension in emitted_profile.extensions.values()
                if extension.supports_backend("rust")
                and extension.vector_bits_kind == "fixed"
                and extension.vector_bits > 0
                and rust_arch_module(extension) is not None
            }
        )
    )


def _fallback_mappings(
    type_facts: tuple[tuple[str, str], ...],
    admitted_widths: tuple[int, ...],
) -> tuple[RustStaticVectorMapping, ...]:
    mappings: list[RustStaticVectorMapping] = []
    for type_tag, base_spelling in type_facts:
        element_bits = scalar_bit_width(type_tag)
        if element_bits is None:
            continue
        mappings.append(
            RustStaticVectorMapping(
                type_tag,
                base_spelling,
                1,
                element_bits,
                f"Simd<{base_spelling}, Scalar>",
                "u64",
            )
        )
        for total_bits in admitted_widths:
            if total_bits % element_bits:
                continue
            lanes = total_bits // element_bits
            mappings.append(
                RustStaticVectorMapping(
                    type_tag,
                    base_spelling,
                    lanes,
                    total_bits,
                    f"Simd<{base_spelling}, Generic<{lanes}>>",
                    "u64",
                    uses_sized_vector=True,
                )
            )
    return tuple(sorted(mappings, key=lambda item: (item.type_tag, item.lanes)))


def _profile_mappings(
    emitted_profile: EmittedProfile,
    type_facts: tuple[tuple[str, str], ...],
    admitted_widths: tuple[int, ...],
    hardware_extension_names: frozenset[str],
) -> tuple[tuple[RustStaticVectorMapping, ...], tuple[Diagnostic, ...]]:
    by_primitive = emitted_profile.specializations("rust")
    registrations = rust_vector_registrations(by_primitive, emitted_profile.extensions)
    by_shape: dict[tuple[str, int], list[RustVectorRegistration]] = defaultdict(list)
    for registration in registrations:
        if registration.extension_name not in hardware_extension_names:
            continue
        lanes = registration.vector_bits // registration.type_bits
        by_shape[(registration.type_tag, lanes)].append(registration)

    diagnostics: list[Diagnostic] = []
    mappings: list[RustStaticVectorMapping] = []
    for fallback in _fallback_mappings(type_facts, admitted_widths):
        candidates = by_shape.get((fallback.type_tag, fallback.lanes), [])
        if not candidates or fallback.lanes == 1:
            mappings.append(fallback)
            continue
        ranked = sorted(
            candidates,
            key=lambda item: (
                emitted_profile.extensions[item.extension_name].metadata.native_sort_order
                or 0,
                item.extension_name,
                item.register_spelling,
            ),
            reverse=True,
        )
        best = ranked[0]
        best_preference = (
            emitted_profile.extensions[best.extension_name].metadata.native_sort_order
            or 0
        )
        equally_ranked = {
            (item.extension_name, item.register_spelling)
            for item in ranked
            if (
                emitted_profile.extensions[item.extension_name].metadata.native_sort_order
                or 0
            )
            == best_preference
        }
        if len(equally_ranked) > 1:
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BACKEND-RUST-AMBIGUOUS-STATIC-MAPPING",
                    message=(
                        f"Rust profile {emitted_profile.profile.name!r} has ambiguous "
                        f"exact-width mappings for {fallback.type_tag}x{fallback.lanes}: "
                        + ", ".join(name for name, _spelling in sorted(equally_ranked))
                    ),
                    source=emitted_profile.extensions[best.extension_name].source,
                )
            )
            continue
        extension = emitted_profile.extensions[best.extension_name]
        mask_spelling = rust_mask_type(
            extension, best.type_bits, best.register_spelling
        )
        mappings.append(
            RustStaticVectorMapping(
                type_tag=best.type_tag,
                base_spelling=best.base_spelling,
                lanes=fallback.lanes,
                total_bits=best.vector_bits,
                vector_spelling=(
                    f"Simd<{best.base_spelling}, {rust_extension_tag(extension)}>"
                ),
                imask_spelling=rust_imask_type(
                    extension,
                    best.type_bits,
                    mask_spelling,
                    best.vector_bits,
                ),
                extension_name=best.extension_name,
                extension_tag_spelling=rust_extension_tag(extension),
            )
        )
    return (
        tuple(sorted(mappings, key=lambda item: (item.type_tag, item.lanes))),
        tuple(diagnostics),
    )


__all__ = (
    "RustStaticFallbackModule",
    "RustStaticProfileSelection",
    "RustStaticSelectionError",
    "RustStaticSelectionPlan",
    "RustStaticVectorMapping",
    "RustTargetRequirement",
    "plan_rust_static_selection",
    "validate_rust_static_selection",
    "validate_rust_static_selection_plan",
)
