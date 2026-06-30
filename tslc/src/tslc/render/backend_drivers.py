"""Render-driver accessors backed by the central backend registry."""

from __future__ import annotations

from tslc.backend.registry import BackendCapability, backend_capabilities

from tslc.value_tests.model import ValueTestBackendSupport


RenderBackendDriver = BackendCapability


def render_backend_drivers(backend_ids: tuple[str, ...]) -> tuple[RenderBackendDriver, ...]:
    return backend_capabilities(backend_ids)


def value_test_supports(backend_ids: tuple[str, ...]) -> tuple[ValueTestBackendSupport, ...]:
    return tuple(driver.value_test_support() for driver in render_backend_drivers(backend_ids))


__all__ = [
    "RenderBackendDriver",
    "render_backend_drivers",
    "value_test_supports",
]
