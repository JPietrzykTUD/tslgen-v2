"""Load the narrow repository policy layered over typed release facts."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
from typing import Any

from tslc.maintenance.release_contract_model import (
    AcceleratedCorePolicy,
    BackendProfilePolicy,
    ComponentPolicy,
    ProductPolicy,
    ProfileSelection,
    ReleasePolicy,
    TargetScopePolicy,
    TargetSpecificCallable,
)


def load_release_policy(path: Path) -> ReleasePolicy:
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read release policy {path}: {error}") from error
    data = object_value(root, "release policy")
    exact_keys(
        data,
        {
            "schema_version",
            "product",
            "components",
            "backend_profiles",
            "target_scopes",
            "target_specific_callables",
            "accelerated_core",
        },
        "release policy",
    )
    version = integer_value(data.get("schema_version"), "schema_version")
    if version != 1:
        raise ValueError(f"unsupported release policy schema_version {version}")

    product_data = object_value(data.get("product"), "product")
    exact_keys(product_data, {"id", "name", "version", "status"}, "product")
    product = ProductPolicy(
        string_value(product_data.get("id"), "product.id"),
        string_value(product_data.get("name"), "product.name"),
        string_value(product_data.get("version"), "product.version"),
        string_value(product_data.get("status"), "product.status"),
    )

    components = tuple(
        _component_policy(item, index)
        for index, item in enumerate(list_value(data.get("components"), "components"))
    )
    if len({item.component_id for item in components}) != len(components):
        raise ValueError("release policy components must have unique ids")

    backend_data = object_value(data.get("backend_profiles"), "backend_profiles")
    backend_profiles = tuple(
        _backend_profile_policy(backend_id, value)
        for backend_id, value in sorted(backend_data.items())
    )
    if not backend_profiles:
        raise ValueError("release policy must declare at least one backend")

    target_scopes = tuple(
        _target_scope_policy(item, index)
        for index, item in enumerate(
            list_value(data.get("target_scopes"), "target_scopes")
        )
    )
    target_specific = tuple(
        _target_specific_callable(item, index)
        for index, item in enumerate(
            list_value(
                data.get("target_specific_callables"),
                "target_specific_callables",
            )
        )
    )
    accelerated_data = object_value(data.get("accelerated_core"), "accelerated_core")
    exact_keys(
        accelerated_data,
        {
            "selection",
            "portable_callable_names",
            "fallback_policy",
            "fallback_exceptions",
        },
        "accelerated_core",
    )
    accelerated = AcceleratedCorePolicy(
        selection=string_value(
            accelerated_data.get("selection"), "accelerated_core.selection"
        ),
        portable_callable_names=string_tuple(
            accelerated_data.get("portable_callable_names"),
            "accelerated_core.portable_callable_names",
        ),
        fallback_policy=string_value(
            accelerated_data.get("fallback_policy"),
            "accelerated_core.fallback_policy",
        ),
        fallback_exceptions=string_tuple(
            accelerated_data.get("fallback_exceptions"),
            "accelerated_core.fallback_exceptions",
        ),
    )
    if accelerated.selection != "all_except_portable_and_target_specific":
        raise ValueError(
            "accelerated_core.selection must be "
            "'all_except_portable_and_target_specific'"
        )
    if not accelerated.portable_callable_names:
        raise ValueError("accelerated_core.portable_callable_names must be non-empty")
    if len(set(accelerated.portable_callable_names)) != len(
        accelerated.portable_callable_names
    ):
        raise ValueError(
            "accelerated_core.portable_callable_names must not contain duplicates"
        )
    if accelerated.fallback_policy != "forbidden_without_reviewed_exception":
        raise ValueError(
            "accelerated_core.fallback_policy must be "
            "'forbidden_without_reviewed_exception'"
        )
    return ReleasePolicy(
        schema_version=version,
        product=product,
        components=components,
        backend_profiles=backend_profiles,
        target_scopes=target_scopes,
        target_specific_callables=target_specific,
        accelerated_core=accelerated,
    )


def _component_policy(value: object, index: int) -> ComponentPolicy:
    owner = f"components[{index}]"
    data = object_value(value, owner)
    exact_keys(data, {"id", "compatibility", "required_major"}, owner)
    compatibility = string_value(data.get("compatibility"), f"{owner}.compatibility")
    if compatibility != "independent":
        raise ValueError(f"{owner}.compatibility must be 'independent'")
    return ComponentPolicy(
        component_id=string_value(data.get("id"), f"{owner}.id"),
        compatibility=compatibility,
        required_major=integer_value(
            data.get("required_major"), f"{owner}.required_major"
        ),
    )


def _backend_profile_policy(
    backend_id: str, value: object
) -> BackendProfilePolicy:
    owner = f"backend_profiles.{backend_id}"
    data = object_value(value, owner)
    exact_keys(data, {"selection", "profiles"}, owner)
    selection_text = string_value(data.get("selection"), f"{owner}.selection")
    try:
        selection = ProfileSelection(selection_text)
    except ValueError as error:
        raise ValueError(
            f"{owner}.selection must be one of: "
            + ", ".join(item.value for item in ProfileSelection)
        ) from error
    profiles = string_tuple(data.get("profiles"), f"{owner}.profiles")
    if selection is ProfileSelection.ALL_SUPPORTED and profiles:
        raise ValueError(f"{owner}.profiles must be empty for all_supported")
    if selection is ProfileSelection.EXPLICIT and not profiles:
        raise ValueError(f"{owner}.profiles must be non-empty for explicit")
    if len(set(profiles)) != len(profiles):
        raise ValueError(f"{owner}.profiles must not contain duplicates")
    return BackendProfilePolicy(backend_id, selection, profiles)


def _target_scope_policy(value: object, index: int) -> TargetScopePolicy:
    owner = f"target_scopes[{index}]"
    data = object_value(value, owner)
    exact_keys(
        data,
        {"id", "backend", "profiles", "runtime_scalable_profiles", "excludes"},
        owner,
    )
    profiles = string_tuple(data.get("profiles"), f"{owner}.profiles")
    runtime = string_tuple(
        data.get("runtime_scalable_profiles"),
        f"{owner}.runtime_scalable_profiles",
    )
    if not profiles:
        raise ValueError(f"{owner}.profiles must be non-empty")
    if not set(runtime) <= set(profiles):
        raise ValueError(f"{owner}.runtime_scalable_profiles must be in profiles")
    return TargetScopePolicy(
        scope_id=string_value(data.get("id"), f"{owner}.id"),
        backend_id=string_value(data.get("backend"), f"{owner}.backend"),
        profiles=profiles,
        runtime_scalable_profiles=runtime,
        excludes=string_tuple(data.get("excludes"), f"{owner}.excludes"),
    )


def _target_specific_callable(value: object, index: int) -> TargetSpecificCallable:
    owner = f"target_specific_callables[{index}]"
    data = object_value(value, owner)
    exact_keys(data, {"name", "reason"}, owner)
    return TargetSpecificCallable(
        name=string_value(data.get("name"), f"{owner}.name"),
        reason=string_value(data.get("reason"), f"{owner}.reason"),
    )


def object_value(value: object, owner: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{owner} must be an object")
    return value


def list_value(value: object, owner: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{owner} must be an array")
    return value


def string_value(value: object, owner: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{owner} must be a non-empty string")
    return value


def string_tuple(value: object, owner: str) -> tuple[str, ...]:
    values = list_value(value, owner)
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise ValueError(f"{owner} must contain non-empty strings")
    return tuple(item for item in values if isinstance(item, str))


def integer_value(value: object, owner: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{owner} must be an integer")
    return value


def exact_keys(data: Mapping[str, object], expected: set[str], owner: str) -> None:
    missing = sorted(expected - set(data))
    unknown = sorted(set(data) - expected)
    if missing or unknown:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(missing))
        if unknown:
            parts.append("unknown " + ", ".join(unknown))
        raise ValueError(f"{owner} fields are invalid: {'; '.join(parts)}")


__all__ = (
    "exact_keys",
    "integer_value",
    "list_value",
    "load_release_policy",
    "object_value",
    "string_tuple",
    "string_value",
)
