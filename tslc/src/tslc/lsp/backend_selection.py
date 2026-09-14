"""Deterministic backend selection for compiler-owned authoring projections."""

from __future__ import annotations

from tslc.backend.capability import BackendCapability
from tslc.backend.registry import backend_capability, registered_backend_ids


def select_authoring_backend(
    configured: tuple[str, ...],
    requested: str | None,
) -> BackendCapability:
    """Select an available backend while preserving project/registry order."""

    candidates = configured or registered_backend_ids()
    if not candidates:
        raise ValueError("authoring requires at least one registered backend")
    backend_id = requested if requested in candidates else candidates[0]
    try:
        return backend_capability(backend_id)
    except ValueError as exc:
        raise ValueError(
            f"configured authoring backend {backend_id!r} is not registered"
        ) from exc


__all__ = ("select_authoring_backend",)
