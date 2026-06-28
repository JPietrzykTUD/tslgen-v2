"""Static registry for backend dialect factories."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tslc.backend.translation import BackendDialect
    from tslc.catalog.model import Catalog

DialectFactory = Callable[["Catalog"], "BackendDialect"]


@dataclass(frozen=True, slots=True)
class BackendDialectRegistration:
    backend_id: str
    create: DialectFactory


def _create_cpp(catalog: Catalog) -> BackendDialect:
    from tslc.backend.cpp_translation import CppBackendDialect

    return CppBackendDialect(catalog)


def _create_rust(catalog: Catalog) -> BackendDialect:
    from tslc.backend.rust_translation import RustBackendDialect

    return RustBackendDialect(catalog)


BACKEND_DIALECTS: tuple[BackendDialectRegistration, ...] = (
    BackendDialectRegistration("cpp", _create_cpp),
    BackendDialectRegistration("rust", _create_rust),
)

_BY_ID = {registration.backend_id: registration for registration in BACKEND_DIALECTS}


def registered_backend_ids() -> tuple[str, ...]:
    return tuple(sorted(_BY_ID))


def supports_backend(backend_id: str) -> bool:
    return backend_id in _BY_ID


def create_backend_dialect(catalog: Catalog, backend_id: str) -> BackendDialect:
    registration = _BY_ID.get(backend_id)
    if registration is None:
        raise ValueError(f"unsupported backend {backend_id!r}")
    return registration.create(catalog)


__all__ = [
    "BACKEND_DIALECTS",
    "BackendDialectRegistration",
    "create_backend_dialect",
    "registered_backend_ids",
    "supports_backend",
]
