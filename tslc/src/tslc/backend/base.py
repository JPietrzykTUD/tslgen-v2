"""Backend protocol: render a lowered function as target-language text."""

from __future__ import annotations

from typing import Protocol

from tslc.lower.lowerer import LoweredSpecialization


class Backend(Protocol):
    backend_id: str

    def render_primitive(
        self, primitive_name: str, specializations: tuple[LoweredSpecialization, ...]
    ) -> str:
        """Render a primitive as its full specialization structure for the backend."""
