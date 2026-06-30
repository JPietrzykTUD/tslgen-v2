"""Shared helpers for scalable-vector value-test planning."""

from __future__ import annotations

from tslc.catalog.model import Catalog
from tslc.lower.lowerer import LoweredSpecialization


def render_extension_test_template(template: str, **values: str) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result


def tiling_is_safe(
    specs: tuple[LoweredSpecialization, ...], catalog: Catalog
) -> bool:
    """Whether the subject primitive may be tiled across a runtime lane count.

    Every scalable case kind that replicates an authored fixed-length pattern with
    ``i % authored_lanes`` is sound only when output lane i depends solely on input lane i.
    We trust the corpus-declared ``Primitive.cross_lane`` fact: the elementwise common case
    leaves it False (tiling-safe), and a cross-lane op (reduce, shuffle, compress, conflict,
    iota) declares it True so it is never tiled into a wrong scalable test. A primitive that
    cannot be resolved is treated conservatively as unsafe.
    """

    primitive = catalog.primitive(specs[0].source_primitive_name, unmasked=False)
    return primitive is not None and not primitive.cross_lane
