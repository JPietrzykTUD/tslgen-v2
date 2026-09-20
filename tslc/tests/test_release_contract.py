"""Generated-library v1 release-contract projection and owner-equivalence gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.lower.implementation_facts import ImplementationState
from tslc.maintenance import _repo_context
from tslc.maintenance._catalog import load_repository_catalog
from tslc.maintenance.release_contract import (
    BackendProfilePolicy,
    ProfileSelection,
    build_release_contract,
    canonical_json_path,
    canonical_markdown_path,
    select_release_profiles,
)
from tslc.maintenance.release_contract_render import render_markdown, serialize_json
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def test_release_contract_matches_both_canonical_projections() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None
    contract = build_release_contract(context)

    assert serialize_json(contract) == canonical_json_path(context).read_text(
        encoding="utf-8"
    )
    assert render_markdown(contract) == canonical_markdown_path(context).read_text(
        encoding="utf-8"
    )

    payload = contract.payload()
    assert payload["product"] == {
        "id": "tsl-generated-library",
        "name": "TSL generated C++/Rust library",
        "version": "1.0.0",
        "status": "release-candidate",
    }
    component_versions = {
        item["id"]: item["version"] for item in payload["components"]
    }
    assert set(component_versions) == {"tslc", "vscode-tsl"}
    assert all(version.startswith("0.") for version in component_versions.values())
    assert [item["id"] for item in payload["implementation_states"]] == [
        state.value for state in ImplementationState
    ]
    safety = payload["safety_api"]
    assert "semantically unspecified" in safety["cpp_failure_result"]
    assert "only when a catastrophic caller obligation remains" in safety["rust"]
    assert "do not by themselves" in safety["internal_unsafety"]
    markdown = render_markdown(contract)
    assert "## Backend/profile/type matrix" in markdown
    assert (
        "| `cpp` | `all_supported` | `sve` | `aarch64` | runtime-scalable |"
        in markdown
    )
    assert (
        "| `cpp` | `all_supported` | `rvv` | `riscv` | runtime-scalable |"
        in markdown
    )
    assert (
        "| `rust` | `explicit` | `avx2` | `x86` | fixed/static |"
        in markdown
    )
    assert "Internal raw-memory" in markdown
    assert "does not by itself make the public Rust" in markdown
    assert "semantically unspecified" in markdown


def test_release_profiles_are_projections_of_typed_machine_capabilities() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None
    catalog = load_repository_catalog(context, purpose="release-contract test")
    profiles = load_machine_profiles_checked(
        context.machine_profiles_path,
        catalog.target_families,
    ).profiles
    contract = build_release_contract(context)

    cpp = contract.backend("cpp")
    assert {profile.name for profile in cpp.profiles} == {
        profile.name
        for profile in profiles.values()
        if profile.supports_backend("cpp")
    }
    assert {"sve", "sve128", "sve256", "sve512", "rvv"} <= {
        profile.name for profile in cpp.profiles
    }

    rust = contract.backend("rust")
    eligible_rust = tuple(
        sorted(
            profile.name
            for profile in profiles.values()
            if profile.supports_backend("rust")
            and profile.auto_detect_gate is None
        )
    )
    assert {profile.name for profile in rust.profiles} == set(eligible_rust)
    assert len(rust.profiles) == len(eligible_rust)
    hardware_rust = tuple(
        profiles[name]
        for name in eligible_rust
        if not profiles[name].default_build_fallback
    )
    assert all(
        profile.selection_priority_for_backend("rust") is not None
        for profile in hardware_rust
    )
    for family in {profile.family for profile in hardware_rust}:
        priorities = tuple(
            profile.selection_priority_for_backend("rust")
            for profile in hardware_rust
            if profile.family == family
        )
        assert len(priorities) == len(set(priorities))
    assert {
        "scalar",
        "cannonlake",
        "sapphire_emerald_granite_rapids",
        "zen5",
        "neon",
        "wasm32-simd128",
    } <= set(eligible_rust)
    assert not {
        profile.name
        for profile in profiles.values()
        if profile.auto_detect_gate is not None
    } & set(eligible_rust)
    assert not {"sve", "sve128", "sve256", "sve512", "rvv"} & {
        profile.name for profile in rust.profiles
    }
    scopes = {scope.scope_id: scope for scope in contract.policy.target_scopes}
    assert "stable Rust SVE" in scopes["arm-sve"].excludes
    assert "stable Rust RVV" in scopes["riscv-vector"].excludes


def test_all_supported_profile_selection_is_additive() -> None:
    policy = BackendProfilePolicy("cpp", ProfileSelection.ALL_SUPPORTED, ())
    first = MachineProfile(
        name="first",
        family="probe",
        features=frozenset(),
        alternatives={},
        supported_backends=frozenset({"cpp"}),
    )
    second = replace(first, name="second")

    before = select_release_profiles(policy, {first.name: first})
    after = select_release_profiles(
        policy,
        {first.name: first, second.name: second},
    )

    assert tuple(profile.name for profile in before) == ("first",)
    assert tuple(profile.name for profile in after) == ("first", "second")


def test_explicit_profile_selection_rejects_unknown_and_unsupported_profiles() -> None:
    profile = MachineProfile(
        name="cpp-only",
        family="probe",
        features=frozenset(),
        alternatives={},
        supported_backends=frozenset({"cpp"}),
    )
    with pytest.raises(ValueError, match="profiles are unknown: missing"):
        select_release_profiles(
            BackendProfilePolicy("rust", ProfileSelection.EXPLICIT, ("missing",)),
            {profile.name: profile},
        )
    with pytest.raises(ValueError, match="profiles do not support it: cpp-only"):
        select_release_profiles(
            BackendProfilePolicy("rust", ProfileSelection.EXPLICIT, (profile.name,)),
            {profile.name: profile},
        )


def test_callable_classification_uses_public_and_support_policy_owners() -> None:
    context = _repo_context.find_repo_context()
    assert context is not None
    contract = build_release_contract(context)
    payload = contract.payload()
    universe = payload["support_universe"]

    assert universe["fixed_shape_signature_kinds"] == sorted(
        DEFAULT_SUPPORT_POLICY.fixed_shape_signature_kinds
    )
    identities = {
        item["identity"] for item in universe["primitive_callable_families"]
    }
    assert set(universe["accelerated_core_callable_families"]) <= identities
    assert set(universe["portable_utility_callable_families"]) <= identities
    assert not (
        set(universe["accelerated_core_callable_families"])
        & set(universe["portable_utility_callable_families"])
    )
    assert universe["target_specific_callables"] == {
        "random_step": "x86 RDRAND operation with no portable fallback"
    }
    assert "abs#v:=(v)" in universe["accelerated_core_callable_families"]
    assert "sequence#v:=()" in universe["portable_utility_callable_families"]
    target_exclusions = universe["target_slot_exclusions"]
    assert target_exclusions
    assert all("callable_identities" in item for item in target_exclusions)
    assert all(
        set(item["callable_identities"]) <= identities
        for item in target_exclusions
    )
    classified = (
        set(universe["accelerated_core_callable_families"])
        | set(universe["portable_utility_callable_families"])
        | {
            identity
            for identity in identities
            if identity.split("#", 1)[0].split("[", 1)[0]
            in universe["target_specific_callables"]
        }
    )
    assert classified == identities
