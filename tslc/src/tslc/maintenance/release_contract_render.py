"""Deterministic JSON and Markdown release-contract projections."""

from __future__ import annotations

import json

from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.lower.implementation_facts import (
    ImplementationState,
    implementation_state_description,
)
from tslc.maintenance.release_contract_model import ReleaseContract
from tslc.support_policy import DEFAULT_SUPPORT_POLICY


def serialize_json(contract: ReleaseContract) -> str:
    return json.dumps(contract.payload(), indent=2, ensure_ascii=False) + "\n"


def render_markdown(contract: ReleaseContract) -> str:
    product = contract.policy.product
    lines = [
        f"# {product.name} {product.version} support contract",
        "",
        "This file is generated from the typed TSL catalog, machine profiles, support",
        "policy, public-API baseline, package metadata, and",
        "`supplementary/release/tsl-v1-policy.json`. Do not edit it by hand.",
        "",
        f"Release status: **{product.status}**.",
        "",
        "## Product and component versions",
        "",
        "The generated C++/Rust library is the product carrying `1.0.0`. `tslc` and",
        "the VS Code extension have independent compatibility policies and remain on",
        "their own `0.x` version lines.",
        "",
        "| Component | Version | Compatibility |",
        "| --- | --- | --- |",
        f"| Generated TSL library | `{product.version}` | stable v1 product |",
        *(
            f"| `{component.component_id}` | `{component.version}` | "
            f"{component.compatibility} |"
            for component in contract.components
        ),
        "",
        "## Backend/profile matrix",
        "",
        "| Backend | Release profile rule | Profiles |",
        "| --- | --- | --- |",
        *(
            f"| `{backend.backend_id}` | `{backend.selection.value}` | "
            + ", ".join(f"`{profile.name}`" for profile in backend.profiles)
            + " |"
            for backend in contract.backends
        ),
        "",
        "C++ v1 includes the declared SVE, fixed-width SVE, and RV64 Vector 1.0",
        "profiles below. These claims do not imply SVE2, undeclared optional RVV",
        "extensions or LMULs, or stable Rust SVE/RVV.",
        "",
        "| Scope | Backend | Profile → target extension | Runtime-scalable profiles | Excludes |",
        "| --- | --- | --- | --- | --- |",
        *(
            f"| `{scope.scope_id}` | `{scope.backend_id}` | "
            + ", ".join(
                f"`{profile}` → `{extension}`"
                for profile, extension in scope.profile_extensions
            )
            + " | "
            + ", ".join(f"`{name}`" for name in scope.runtime_scalable_profiles)
            + " | "
            + "; ".join(scope.excludes)
            + " |"
            for scope in contract.policy.target_scopes
        ),
        "",
        "## Stable callable universe",
        "",
        f"- Scalar types: {', '.join(f'`{tag}`' for tag in DEFAULT_SCALAR_TYPE_TAGS)}.",
        f"- Primitive callable families: {len(contract.callable_families)}.",
        f"- Algorithm callable families: {len(contract.algorithms)}.",
        f"- Accelerated-core callable families: {len(contract.accelerated_core)}.",
        f"- Portable utility callable families: {len(contract.portable_utility_families)}.",
        "- Portable utility names: "
        + ", ".join(
            f"`{name}`"
            for name in contract.policy.accelerated_core.portable_callable_names
        )
        + ".",
        "- Fixed-shape signature kinds: "
        + ", ".join(
            f"`{kind}`"
            for kind in sorted(
                DEFAULT_SUPPORT_POLICY.fixed_shape_signature_kinds
            )
        )
        + ".",
        "",
        "The exact callable-family records below are projected from",
        "`coverage/tsl-v1-public-api.json`; generated projects also carry their",
        "scope-exact backend declaration manifests.",
        "",
        f"Public-API baseline SHA-256: `{contract.public_api_baseline_digest}`.",
        "",
        "### Primitive callable families",
        "",
        "| Identity | Checked | Fixed-shape only | Semantic categories |",
        "| --- | --- | --- | --- |",
        *(
            f"| `{family.identity}` | {'yes' if family.checked_companion else 'no'} | "
            f"{'yes' if family.fixed_shape_only else 'no'} | "
            + (", ".join(family.semantic_categories) or "not yet annotated")
            + " |"
            for family in contract.callable_families
        ),
        "",
        "### Algorithm callable families",
        "",
        ", ".join(f"`{name}`" for name in contract.algorithms) + ".",
        "",
        "### Target-specific callables",
        "",
        *(
            f"- `{item.name}`: {item.reason}."
            for item in contract.policy.target_specific_callables
        ),
        "",
        "## Safety API",
        "",
        "Unchecked calls perform the operation directly and do not sanitize inputs.",
        "Documented caller preconditions remain the caller's responsibility. A",
        "`*_checked` companion exists only when all applicable catastrophic runtime",
        "preconditions are complete, checkable, and representable. C++ value-returning",
        "checked calls return the vector/register value directly and report through an",
        "explicit `precondition_error&`; Rust checked calls return `Result`, while raw",
        "pointer APIs remain `unsafe`.",
        "",
        "## Implementation quality policy",
        "",
        "The accelerated core contains every stable primitive family except the",
        "explicit target-neutral utility names above and target-specific callables.",
        "This conservative default prevents incomplete semantic annotations from",
        "silently weakening the quality gate. A fallback in that set is forbidden",
        "unless its exact identity is a",
        "reviewed exception with correctness and performance evidence. There are",
        f"currently {len(contract.policy.accelerated_core.fallback_exceptions)} exceptions.",
        "",
        "The coarse implementation-state meanings are:",
        "",
        *(
            f"- `{state.value}`: {implementation_state_description(state)}"
            for state in ImplementationState
        ),
        "",
    ]
    return "\n".join(lines)


__all__ = ("render_markdown", "serialize_json")
