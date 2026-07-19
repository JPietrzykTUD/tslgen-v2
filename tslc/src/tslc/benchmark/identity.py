"""Canonical identities for finalized benchmark specializations and bodies."""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import re

from tslc.backend.emitted_profile import EmittedProfile
from tslc.benchmark.model import SpecializationKey
from tslc.lower.lowerer import LoweredSpecialization, varying_positions
from tslc.value_tests.lane_math import whole_lanes

_STABLE_ID_RE = re.compile(r"[^0-9A-Za-z_]+")


def specialization_key(
    *,
    backend_id: str,
    profile: EmittedProfile,
    specialization: LoweredSpecialization,
    primitive_specializations: Sequence[LoweredSpecialization],
    immediate_value: str | None = None,
    simd_type_base_bindings: tuple[tuple[str, str], ...] = (),
) -> SpecializationKey:
    """Build one backend-local key from finalized profile and lowering facts."""

    if not backend_id:
        raise ValueError("benchmark specialization identities require a backend ID")
    if not primitive_specializations or any(
        candidate.primitive_name != specialization.primitive_name
        for candidate in primitive_specializations
    ):
        raise ValueError(
            "benchmark specialization identities require one complete primitive group"
        )
    if immediate_value is not None and specialization.immediate is None:
        raise ValueError(
            "a benchmark specialization without an immediate cannot bind a value"
        )

    extension = profile.extensions.get(specialization.extension_name)
    lanes = (
        whole_lanes(extension.vector_bits, specialization.type_tag)
        if extension is not None and extension.vector_bits > 0
        else None
    )
    target = specialization.target
    return SpecializationKey(
        backend_id=backend_id,
        profile_name=profile.profile.name,
        primitive_name=specialization.primitive_name,
        source_primitive_name=specialization.source_primitive_name,
        extension_name=specialization.extension_name,
        type_tag=specialization.type_tag,
        result_kind=specialization.result_kind,
        param_kinds=specialization.param_kinds,
        target_type_tag=target.base_tag if target is not None else None,
        target_extension_name=(
            target.extension_isa if target is not None else None
        ),
        axis=specialization.axis,
        immediate=immediate_value,
        generic_values=tuple(
            (name, default)
            for name, _type, default in specialization.generic_params
        ),
        simd_type_base_bindings=simd_type_base_bindings,
        overload_parameter_positions=varying_positions(
            tuple(primitive_specializations)
        ),
        lanes=lanes,
        header_group=(
            extension.header_group_for_backend(backend_id)
            if extension is not None
            else None
        ),
    )


def specialization_stable_id(key: SpecializationKey) -> str:
    """Return the readable, hash-suffixed identity used by benchmark protocols."""

    readable = _STABLE_ID_RE.sub(
        "_",
        "_".join(
            (
                key.profile_name,
                key.primitive_name,
                key.extension_name,
                key.type_tag,
            )
        ),
    ).strip("_")
    digest = sha256(repr(key.canonical_fields()).encode("utf-8")).hexdigest()[:12]
    return f"{readable}_{digest}"


def implementation_body_hash(body: str) -> str:
    """Hash one already-lowered backend body without normalizing target text."""

    return sha256(body.encode("utf-8")).hexdigest()


__all__ = (
    "implementation_body_hash",
    "specialization_key",
    "specialization_stable_id",
)
