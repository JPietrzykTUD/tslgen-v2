"""Typed generation requests and their cross-field validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from tslc.backend.capability import BackendCapability
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.machine_profiles import MachineProfile
from tslc.diagnostics import Diagnostic
from tslc.project_render import (
    DEFAULT_PROJECT_RENDER_CONFIG,
    ProjectRenderConfig,
)

GenerationMode = Literal["partial", "strict"]


def _default_backend_ids() -> tuple[str, ...]:
    """Resolve registry defaults when a request is created, not at import time."""

    return registered_backend_ids()


@dataclass(frozen=True, slots=True)
class BackendProfileScope:
    """Restrict one requested backend to a subset of requested machine profiles."""

    backend_id: str
    profiles: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BackendCompilerCapabilitySet:
    """Compiler capabilities explicitly enabled for one generated backend."""

    backend_id: str
    capabilities: frozenset[str]


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """All typed inputs and feature switches for one compiler invocation."""

    source_paths: tuple[Path, ...]
    machine_profiles_path: Path
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    type_tags: tuple[str, ...]
    extensions: tuple[str, ...] | None = None
    backends: tuple[str, ...] = field(default_factory=_default_backend_ids)
    backend_profile_scopes: tuple[BackendProfileScope, ...] = ()
    backend_compiler_capabilities: tuple[BackendCompilerCapabilitySet, ...] = ()
    mode: GenerationMode = "partial"
    # Pull compiler-owned harness primitives into generated value-test closure.
    test_harness: bool = False
    # Report authored value cases outside the current backend harness surface.
    value_test_warnings: bool = False
    # Emit runtime differential fuzz cases in generated value tests.
    value_test_fuzz: bool = False
    # Stop before project planning and rendering when false.
    render_artifacts: bool = True
    # Load backend policy for focused projections that do not render a project.
    load_policy_inputs: bool = False
    # Retain the lowered dependency graph for explicit analysis commands.
    collect_lowering_trace: bool = False
    render_config: ProjectRenderConfig = DEFAULT_PROJECT_RENDER_CONFIG


def compiler_capability_diagnostics(
    request: GenerationRequest,
    backends: tuple[BackendCapability, ...],
) -> tuple[Diagnostic, ...]:
    requested_backends = {capability.backend_id for capability in backends}
    known = {
        capability.backend_id: frozenset(
            item.capability_id for item in capability.compiler_capabilities
        )
        for capability in backends
    }
    seen: set[str] = set()
    diagnostics: list[Diagnostic] = []
    for item in request.backend_compiler_capabilities:
        if item.backend_id in seen:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-DUPLICATE-COMPILER-CAPABILITY-SET",
                    message=(
                        "compiler capability set repeats backend "
                        f"{item.backend_id!r}"
                    ),
                )
            )
        seen.add(item.backend_id)
        if item.backend_id not in requested_backends:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-UNREQUESTED-COMPILER-CAPABILITY-BACKEND",
                    message=(
                        f"compiler capability set names {item.backend_id!r}, which "
                        "is not a requested backend"
                    ),
                )
            )
            continue
        unknown = item.capabilities - known[item.backend_id]
        if unknown:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-UNKNOWN-COMPILER-CAPABILITY",
                    message=(
                        f"backend {item.backend_id!r} uses unknown compiler "
                        f"capabilities: {', '.join(sorted(unknown))}; expected "
                        f"{', '.join(sorted(known[item.backend_id])) or '(none)'}"
                    ),
                )
            )
    return tuple(diagnostics)


def backend_profile_scope_diagnostics(
    request: GenerationRequest,
    backends: tuple[BackendCapability, ...],
    machine_profiles: Mapping[str, MachineProfile],
    requested_profiles: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    requested_backends = frozenset(
        capability.backend_id for capability in backends
    )
    requested_profile_names = frozenset(requested_profiles)
    seen: set[str] = set()
    diagnostics: list[Diagnostic] = []
    for scope in request.backend_profile_scopes:
        if scope.backend_id in seen:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-DUPLICATE-BACKEND-PROFILE-SCOPE",
                    message=(
                        "backend profile scope repeats backend "
                        f"{scope.backend_id!r}"
                    ),
                )
            )
        seen.add(scope.backend_id)
        if scope.backend_id not in requested_backends:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-UNREQUESTED-BACKEND-PROFILE-SCOPE",
                    message=(
                        f"backend profile scope names {scope.backend_id!r}, which "
                        "is not a requested backend"
                    ),
                )
            )
        if not scope.profiles:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TSL-PIPELINE-EMPTY-BACKEND-PROFILE-SCOPE",
                    message=f"backend {scope.backend_id!r} profile scope is empty",
                )
            )
        for profile_name in sorted(set(scope.profiles)):
            if profile_name not in machine_profiles:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PIPELINE-UNKNOWN-BACKEND-PROFILE",
                        message=(
                            f"backend {scope.backend_id!r} profile scope names "
                            f"unknown machine profile {profile_name!r}"
                        ),
                    )
                )
            elif profile_name not in requested_profile_names:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TSL-PIPELINE-OUT-OF-SCOPE-BACKEND-PROFILE",
                        message=(
                            f"backend {scope.backend_id!r} profile {profile_name!r} "
                            "is not in the requested profile set"
                        ),
                    )
                )
    return tuple(diagnostics)


__all__ = (
    "BackendCompilerCapabilitySet",
    "BackendProfileScope",
    "GenerationMode",
    "GenerationRequest",
    "backend_profile_scope_diagnostics",
    "compiler_capability_diagnostics",
)
