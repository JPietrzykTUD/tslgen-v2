"""Shared helpers for scalable-vector value-test case planning."""

from __future__ import annotations

from tslc.catalog.model import Catalog
from tslc.lower.lowerer import LoweredSpecialization
from tslc.value_tests.case_helpers import sanitize as _sanitize
from tslc.value_tests.lane_math import tiling_preserves_lane_semantics
from tslc.value_tests.model import ValueTestBackendSupport, ValueTestScalable


def scalable_case_facts(
    spec: LoweredSpecialization,
    catalog: Catalog,
    backend: ValueTestBackendSupport,
    *,
    mask_bit_tokens: tuple[str, ...] = (),
    expected_mask_bits: int | None = None,
    load_name: str | None = None,
    store_name: str | None = None,
) -> ValueTestScalable | None:
    """Backend-neutral scalable facts for one specialization, or None.

    None when the specialization's extension is not scalable, a required per-backend
    test template is missing, or an authored mask-bits token is not a non-negative
    integer. The facts stay unrendered — raw extension templates, integer mask bits,
    and harness names; backend renderers own the final expression spelling.
    """

    extension = catalog.extensions.get(spec.extension_name)
    if extension is None or extension.vector_bits_kind != "scalable":
        return None
    runtime_lanes_template = extension.test_runtime_lanes.get(backend.backend_id)
    if runtime_lanes_template is None:
        return None
    mask_from_bits_template: str | None = None
    mask_bits: tuple[int, ...] = ()
    if mask_bit_tokens:
        parsed = tuple(mask_bits_value(token) for token in mask_bit_tokens)
        if any(bits is None for bits in parsed):
            return None
        mask_bits = tuple(bits for bits in parsed if bits is not None)
        mask_from_bits_template = extension.test_mask_from_bits.get(backend.backend_id)
        if mask_from_bits_template is None:
            return None
    mask_check_template: str | None = None
    if expected_mask_bits is not None:
        mask_check_template = extension.test_mask_check.get(backend.backend_id)
        if mask_check_template is None:
            return None
    return ValueTestScalable(
        source_extension=spec.extension_name,
        runtime_lanes_template=runtime_lanes_template,
        mask_from_bits_template=mask_from_bits_template,
        mask_check_template=mask_check_template,
        mask_bits=mask_bits,
        expected_mask_bits=expected_mask_bits,
        load_name=load_name,
        store_name=store_name,
    )


def mask_bits_value(token: str) -> int | None:
    """The non-negative integer value of one authored mask-bits token, or None."""

    try:
        value = int(token.strip().strip('"'), 0)
    except ValueError:
        return None
    return value if value >= 0 else None


def scalable_function_name(
    extension_name: str,
    case_name: str,
    *,
    call_name: str | None = None,
) -> str:
    """The deterministic ``test_scalable_…`` function name for one planned case."""

    parts = [_sanitize(extension_name)]
    if call_name is not None:
        parts.append(_sanitize(call_name))
    parts.append(_sanitize(case_name))
    return "test_scalable_" + "_".join(parts)


def tiling_is_safe(
    specs: tuple[LoweredSpecialization, ...], catalog: Catalog
) -> bool:
    """Whether the subject primitive may be tiled across a runtime lane count.

    Resolves the corpus primitive and delegates the invariant to
    :func:`tslc.value_tests.lane_math.tiling_preserves_lane_semantics`.
    """

    primitive = catalog.primitive(specs[0].source_primitive_name, unmasked=False)
    return tiling_preserves_lane_semantics(primitive)


__all__ = (
    "mask_bits_value",
    "scalable_case_facts",
    "scalable_function_name",
    "tiling_is_safe",
)
