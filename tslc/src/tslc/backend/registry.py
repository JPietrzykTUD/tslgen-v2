"""Central registry for generated backend capabilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tslc.backend.capability import BackendCapability
from tslc.backend.cpp_capability import CPP_BACKEND
from tslc.backend.rust_capability import RUST_BACKEND

if TYPE_CHECKING:
    from tslc.backend.translation import BackendDialect
    from tslc.catalog.model import Catalog


BACKEND_CAPABILITIES: tuple[BackendCapability, ...] = (
    CPP_BACKEND,
    RUST_BACKEND,
)

_BY_ID = {capability.backend_id: capability for capability in BACKEND_CAPABILITIES}


def backend_capability(backend_id: str) -> BackendCapability:
    capability = _BY_ID.get(backend_id)
    if capability is None:
        raise ValueError(f"unsupported backend {backend_id!r}")
    return capability


def backend_capabilities(backend_ids: tuple[str, ...]) -> tuple[BackendCapability, ...]:
    requested = set(backend_ids)
    unknown = requested - set(_BY_ID)
    if unknown:
        names = ", ".join(repr(name) for name in sorted(unknown))
        raise ValueError(f"unsupported backend {names}")
    return tuple(
        capability
        for capability in BACKEND_CAPABILITIES
        if capability.backend_id in requested
    )


def registered_backend_ids() -> tuple[str, ...]:
    return tuple(sorted(_BY_ID))


def supports_backend(backend_id: str) -> bool:
    return backend_id in _BY_ID


def create_backend_dialect(catalog: Catalog, backend_id: str) -> BackendDialect:
    return backend_capability(backend_id).create_dialect(catalog)


__all__ = [
    "BACKEND_CAPABILITIES",
    "BackendCapability",
    "backend_capabilities",
    "backend_capability",
    "create_backend_dialect",
    "registered_backend_ids",
    "supports_backend",
]
