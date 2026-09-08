#!/usr/bin/env python3
"""Build the reviewed TSL v1 product/support contract from typed owners."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import tomllib
from typing import Any

from tslc.catalog.machine_profiles import MachineProfile, load_machine_profiles_checked
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.maintenance._catalog import load_repository_catalog
from tslc.maintenance._repo_context import RepoContext
from tslc.maintenance.release_contract_model import (
    BackendProfilePolicy,
    BackendReleaseContract,
    CallableFamily,
    ComponentContract,
    ProfileSelection,
    ReleaseContract,
    ReleasePolicy,
    ReleaseProfile,
)
from tslc.maintenance.release_contract_policy import (
    exact_keys,
    integer_value,
    list_value,
    load_release_policy,
    object_value,
    string_tuple,
    string_value,
)
from tslc.project_config import load_project_config
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


_SEMANTIC_KEYS = ("arithmetic", "operation", "memory", "conversion", "shift")


def canonical_policy_path(context: RepoContext) -> Path:
    return context.root / "supplementary" / "release" / "tsl-v1-policy.json"


def canonical_json_path(context: RepoContext) -> Path:
    return context.coverage_root / "tsl-v1-support.json"


def canonical_markdown_path(context: RepoContext) -> Path:
    return context.root / "docs" / "tsl-v1-support.md"


def select_release_profiles(
    policy: BackendProfilePolicy,
    profiles: Mapping[str, MachineProfile],
) -> tuple[MachineProfile, ...]:
    """Apply one release profile policy through typed profile capabilities."""

    if policy.selection is ProfileSelection.ALL_SUPPORTED:
        selected = tuple(
            profile
            for profile in profiles.values()
            if profile.supports_backend(policy.backend_id)
        )
    else:
        missing = sorted(set(policy.profiles) - set(profiles))
        if missing:
            raise ValueError(
                f"backend {policy.backend_id!r} release profiles are unknown: "
                + ", ".join(missing)
            )
        selected = tuple(profiles[name] for name in policy.profiles)
        unsupported = [
            profile.name
            for profile in selected
            if not profile.supports_backend(policy.backend_id)
        ]
        if unsupported:
            raise ValueError(
                f"backend {policy.backend_id!r} release profiles do not support it: "
                + ", ".join(unsupported)
            )
    if not selected:
        raise ValueError(f"backend {policy.backend_id!r} has no release profiles")
    return tuple(sorted(selected, key=lambda item: (item.family, item.name)))


def build_release_contract(context: RepoContext) -> ReleaseContract:
    policy = load_release_policy(canonical_policy_path(context))
    catalog = load_repository_catalog(context, purpose="TSL v1 release contract")
    loaded_profiles = load_machine_profiles_checked(
        context.machine_profiles_path,
        catalog.target_families,
    )
    if has_errors(loaded_profiles.diagnostics):
        rendered = "\n".join(
            format_diagnostic(diagnostic) for diagnostic in loaded_profiles.diagnostics
        )
        raise ValueError(f"cannot build release profile contract:\n{rendered}")

    catalog_backends = frozenset(catalog.type_spellings) & frozenset(
        catalog.translations
    )
    policy_backends = frozenset(item.backend_id for item in policy.backend_profiles)
    if policy_backends != catalog_backends:
        raise ValueError(
            "release backends must match the typed catalog backends: "
            f"policy={sorted(policy_backends)}, catalog={sorted(catalog_backends)}"
        )

    backends = tuple(
        BackendReleaseContract(
            backend_id=item.backend_id,
            selection=item.selection,
            profiles=tuple(
                _release_profile(profile)
                for profile in select_release_profiles(item, loaded_profiles.profiles)
            ),
        )
        for item in policy.backend_profiles
    )
    _validate_target_scopes(policy, backends)

    project = load_project_config(context.root / "tslc.toml")
    if project is None:
        raise ValueError("repository tslc.toml was not found")
    if project.rust_package.name != "tsl":
        raise ValueError("generated Rust package must be named 'tsl'")
    if project.rust_package.version != policy.product.version:
        raise ValueError(
            "generated Rust package version does not match the v1 product: "
            f"{project.rust_package.version!r} != {policy.product.version!r}"
        )

    components = _component_contracts(context, policy)
    baseline_path = context.coverage_root / "tsl-v1-public-api.json"
    baseline_text = baseline_path.read_text(encoding="utf-8")
    baseline = object_value(json.loads(baseline_text), "public API baseline")
    families = _callable_families(baseline)
    family_names = frozenset(family.name for family in families)
    unknown_target_specific = sorted(
        item.name
        for item in policy.target_specific_callables
        if item.name not in family_names
    )
    if unknown_target_specific:
        raise ValueError(
            "target-specific callables are absent from the public API baseline: "
            + ", ".join(unknown_target_specific)
        )
    target_specific_names = frozenset(
        item.name for item in policy.target_specific_callables
    )
    portable_names = frozenset(policy.accelerated_core.portable_callable_names)
    unknown_portable = sorted(portable_names - family_names)
    if unknown_portable:
        raise ValueError(
            "portable callable names are absent from the public API baseline: "
            + ", ".join(unknown_portable)
        )
    overlap = sorted(portable_names & target_specific_names)
    if overlap:
        raise ValueError(
            "callables cannot be both portable and target-specific: "
            + ", ".join(overlap)
        )
    accelerated = tuple(
        family.identity
        for family in families
        if family.name not in portable_names | target_specific_names
    )
    portable = tuple(
        family.identity
        for family in families
        if family.name in portable_names
    )
    unknown_exceptions = sorted(
        set(policy.accelerated_core.fallback_exceptions) - set(accelerated)
    )
    if unknown_exceptions:
        raise ValueError(
            "accelerated-core fallback exceptions are not accelerated-core identities: "
            + ", ".join(unknown_exceptions)
        )

    exact = object_value(
        baseline.get("exact_backend_declarations"), "exact declarations"
    )
    return ReleaseContract(
        policy=policy,
        components=components,
        backends=backends,
        callable_families=families,
        algorithms=string_tuple(
            baseline.get("algorithm_callable_families"),
            "public API algorithm_callable_families",
        ),
        accelerated_core=accelerated,
        portable_utility_families=portable,
        public_api_baseline_version=integer_value(
            baseline.get("version"), "public API baseline version"
        ),
        public_api_baseline_digest=sha256(baseline_text.encode("utf-8")).hexdigest(),
        exact_cpp_declarations=_declaration_count(exact, "cpp"),
        exact_rust_declarations=_declaration_count(exact, "rust"),
    )


def _release_profile(profile: MachineProfile) -> ReleaseProfile:
    return ReleaseProfile(
        name=profile.name,
        family=profile.family,
        features=tuple(sorted(profile.features)),
        compile_modes=tuple(sorted(profile.compile_modes)),
        auto_detect_gate=profile.auto_detect_gate,
    )


def _validate_target_scopes(
    policy: ReleasePolicy, backends: tuple[BackendReleaseContract, ...]
) -> None:
    by_backend = {
        backend.backend_id: frozenset(profile.name for profile in backend.profiles)
        for backend in backends
    }
    seen_ids: set[str] = set()
    for scope in policy.target_scopes:
        if scope.scope_id in seen_ids:
            raise ValueError(f"duplicate target scope id {scope.scope_id!r}")
        seen_ids.add(scope.scope_id)
        missing = sorted(
            set(scope.profiles) - by_backend.get(scope.backend_id, frozenset())
        )
        if missing:
            raise ValueError(
                f"target scope {scope.scope_id!r} profiles are outside backend "
                f"{scope.backend_id!r}: " + ", ".join(missing)
            )


def _component_contracts(
    context: RepoContext, policy: ReleasePolicy
) -> tuple[ComponentContract, ...]:
    versions = {
        "tslc": _pyproject_version(context.root / "tslc" / "pyproject.toml"),
        "vscode-tsl": _package_json_version(
            context.root / "editors" / "vscode-tsl" / "package.json"
        ),
    }
    unknown = sorted(
        set(item.component_id for item in policy.components) - set(versions)
    )
    if unknown:
        raise ValueError("release policy has unknown components: " + ", ".join(unknown))
    contracts: list[ComponentContract] = []
    for item in policy.components:
        version = versions[item.component_id]
        major = _version_major(version, item.component_id)
        if major != item.required_major:
            raise ValueError(
                f"{item.component_id} version {version!r} must remain on "
                f"major line {item.required_major}.x"
            )
        contracts.append(
            ComponentContract(item.component_id, version, item.compatibility)
        )
    return tuple(contracts)


def _pyproject_version(path: Path) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = object_value(data.get("project"), f"{path}: project")
    return string_value(project.get("version"), f"{path}: project.version")


def _package_json_version(path: Path) -> str:
    data = object_value(json.loads(path.read_text(encoding="utf-8")), str(path))
    return string_value(data.get("version"), f"{path}: version")


def _version_major(version: str, owner: str) -> int:
    major, separator, _remainder = version.partition(".")
    if not separator or not major.isdigit():
        raise ValueError(f"{owner} version {version!r} has no numeric major")
    return int(major)


def _callable_families(baseline: Mapping[str, Any]) -> tuple[CallableFamily, ...]:
    values = list_value(
        baseline.get("primitive_callable_families"),
        "public API primitive_callable_families",
    )
    families: list[CallableFamily] = []
    for index, value in enumerate(values):
        owner = f"public API primitive_callable_families[{index}]"
        data = object_value(value, owner)
        signature = string_value(data.get("signature"), f"{owner}.signature")
        shape = parse_signature(signature)
        if shape is None:
            raise ValueError(f"{owner}.signature is invalid: {signature!r}")
        kinds = {shape.result_kind, *shape.param_kinds}
        attributes_data = object_value(data.get("attributes"), f"{owner}.attributes")
        if not all(
            isinstance(key, str) and isinstance(item, str)
            for key, item in attributes_data.items()
        ):
            raise ValueError(f"{owner}.attributes must map strings to strings")
        checked = data.get("checked_source_contract")
        if not isinstance(checked, bool):
            raise ValueError(f"{owner}.checked_source_contract must be Boolean")
        families.append(
            CallableFamily(
                name=string_value(data.get("name"), f"{owner}.name"),
                signature=signature,
                attributes=tuple(sorted(attributes_data.items())),
                result_target=string_tuple(
                    data.get("result_target"), f"{owner}.result_target"
                ),
                overload=_overload(data.get("overload"), owner),
                checked_companion=checked,
                semantic_categories=tuple(
                    key for key in _SEMANTIC_KEYS if data.get(key) is not None
                ),
                fixed_shape_only=bool(
                    kinds & DEFAULT_SUPPORT_POLICY.scalable_deferred_signature_kinds
                ),
                source_contract_sha256=sha256(
                    json.dumps(
                        data,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest(),
            )
        )
    families.sort(key=lambda family: family.identity)
    identities = [family.identity for family in families]
    if len(set(identities)) != len(identities):
        raise ValueError("public API baseline has duplicate callable-family identities")
    return tuple(families)


def _declaration_count(exact: Mapping[str, Any], backend_id: str) -> int:
    backend = object_value(exact.get(backend_id), f"exact declarations.{backend_id}")
    return len(list_value(backend.get("declarations"), f"{backend_id}.declarations"))


def _overload(value: object, owner: str) -> tuple[str, str, bool] | None:
    if value is None:
        return None
    data = object_value(value, f"{owner}.overload")
    exact_keys(
        data,
        {"axis", "value", "declares_primary"},
        f"{owner}.overload",
    )
    primary = data.get("declares_primary")
    if not isinstance(primary, bool):
        raise ValueError(f"{owner}.overload.declares_primary must be Boolean")
    return (
        string_value(data.get("axis"), f"{owner}.overload.axis"),
        string_value(data.get("value"), f"{owner}.overload.value"),
        primary,
    )


__all__ = (
    "BackendProfilePolicy",
    "BackendReleaseContract",
    "ProfileSelection",
    "ReleaseContract",
    "ReleasePolicy",
    "build_release_contract",
    "canonical_json_path",
    "canonical_markdown_path",
    "canonical_policy_path",
    "load_release_policy",
    "select_release_profiles",
)


if __name__ == "__main__":
    from tslc.maintenance.release_contract_cli import main

    raise SystemExit(main())
