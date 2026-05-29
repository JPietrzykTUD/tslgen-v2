"""Resolve exact vector member type values from explicit extension metadata."""

from __future__ import annotations

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, Extension, ExtensionTypePolicy, TypeTag
from tslgen.lowering.model import (
    LoweredScalarTypeIdentity,
    LoweredTypeValue,
    LoweredVectorMemberType,
)
from tslgen.lowering.scalar_types import lookup_scalar_type_descriptor

_EXACT_UNSIGNED_INTEGER_TAGS = {
    8: TypeTag("ui8"),
    16: TypeTag("ui16"),
    32: TypeTag("ui32"),
    64: TypeTag("ui64"),
}


def resolve_vector_member_scalar_type(
    value: LoweredTypeValue,
    *,
    catalog: Catalog | None,
    source: SourceLocation,
) -> LoweredScalarTypeIdentity | Diagnostic | None:
    """Resolve a vector member type to a concrete scalar type when proven."""

    if not isinstance(value, LoweredVectorMemberType):
        return None

    extension = _extension(value, catalog, source)
    if isinstance(extension, Diagnostic):
        return extension

    policy = _policy_for_member(value, extension, source)
    if isinstance(policy, Diagnostic):
        return policy

    return _resolve_policy(value, extension, policy, source)


def _extension(
    value: LoweredVectorMemberType,
    catalog: Catalog | None,
    source: SourceLocation,
) -> Extension | Diagnostic:
    if catalog is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            "catalog extension metadata",
        )

    extension = catalog.extensions.get(str(value.extension))
    if extension is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"known extension {str(value.extension)!r}",
        )
    return extension


def _policy_for_member(
    value: LoweredVectorMemberType,
    extension: Extension,
    source: SourceLocation,
) -> ExtensionTypePolicy | Diagnostic:
    if value.member == "mask":
        policy = extension.mask_type_policy
        policy_name = "mask_type_policy"
    elif value.member in {"imask", "mask_underlying"}:
        policy = extension.integral_mask_type_policy
        policy_name = "integral_mask_type_policy"
    else:
        return _unsupported_member_diagnostic(
            value,
            source,
            f"member {value.member!r} is not a scalar mask member",
        )

    if policy is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"{policy_name} for extension {extension.name!r}",
        )
    return policy


def _resolve_policy(
    value: LoweredVectorMemberType,
    extension: Extension,
    policy: ExtensionTypePolicy,
    source: SourceLocation,
) -> LoweredScalarTypeIdentity | Diagnostic:
    if policy.kind == "same_as_mask_type":
        mask_policy = extension.mask_type_policy
        if mask_policy is None:
            return _missing_metadata_diagnostic(
                value,
                source,
                f"mask_type_policy for extension {extension.name!r}",
            )
        if mask_policy.kind == "same_as_mask_type":
            return _unsupported_member_diagnostic(
                value,
                source,
                "same_as_mask_type policy refers back to itself",
            )
        return _resolve_policy(value, extension, mask_policy, source)

    if policy.kind == "lane_bitmask":
        return _resolve_lane_bitmask_policy(value, extension, source)

    return _unsupported_member_diagnostic(
        value,
        source,
        f"policy kind {policy.kind!r} does not prove a concrete scalar TypeTag",
    )


def _resolve_lane_bitmask_policy(
    value: LoweredVectorMemberType,
    extension: Extension,
    source: SourceLocation,
) -> LoweredScalarTypeIdentity | Diagnostic:
    if extension.runtime_lanes is not False:
        return _missing_metadata_diagnostic(
            value,
            source,
            "explicit non-runtime fixed vector lanes",
        )

    if extension.size_parameter is not None:
        return _missing_metadata_diagnostic(
            value,
            source,
            "fixed vector_bits independent of size parameters",
        )

    if not isinstance(extension.vector_bits, int):
        return _missing_metadata_diagnostic(
            value,
            source,
            "fixed integer vector_bits",
        )

    descriptor = lookup_scalar_type_descriptor(str(value.type_tag))
    if descriptor is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"accepted scalar descriptor for TypeTag {str(value.type_tag)!r}",
        )
    scalar_bits = descriptor.bit_width

    if scalar_bits <= 0 or extension.vector_bits <= 0:
        return _missing_metadata_diagnostic(
            value,
            source,
            "positive scalar and vector bit widths",
        )

    if extension.vector_bits % scalar_bits != 0:
        return _missing_metadata_diagnostic(
            value,
            source,
            "vector_bits divisible by selected scalar bit width",
        )

    lanes = extension.vector_bits // scalar_bits
    type_tag = _EXACT_UNSIGNED_INTEGER_TAGS.get(lanes)
    if type_tag is None:
        return _unsupported_member_diagnostic(
            value,
            source,
            f"no accepted unsigned scalar TypeTag has exactly {lanes} bits",
        )

    if lookup_scalar_type_descriptor(str(type_tag)) is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"accepted scalar descriptor for exact unsigned TypeTag {str(type_tag)!r}",
        )

    return LoweredScalarTypeIdentity(type_tag=type_tag)


def _missing_metadata_diagnostic(
    value: LoweredVectorMemberType,
    source: SourceLocation,
    missing: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MISSING-VECTOR-MEMBER-TYPE-METADATA",
        message=(
            "vector member type cannot be resolved to a concrete scalar "
            f"TypeTag; missing {missing} for member {value.member!r} on "
            f"extension {str(value.extension)!r} and type {str(value.type_tag)!r}"
        ),
        location=source,
    )


def _unsupported_member_diagnostic(
    value: LoweredVectorMemberType,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-TYPE",
        message=(
            "vector member type cannot be resolved to a concrete scalar "
            f"TypeTag by the M173 boundary; {reason}; got member "
            f"{value.member!r} on extension {str(value.extension)!r} and "
            f"type {str(value.type_tag)!r}"
        ),
        location=source,
    )
