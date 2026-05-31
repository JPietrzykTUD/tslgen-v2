"""Resolve fixed vector member byte sizes from explicit extension metadata."""

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import Catalog, Extension, ExtensionTypePolicy
from tslgen.lowering.model import LoweredTypeValue, LoweredVectorMemberType
from tslgen.lowering.scalar_types import lookup_scalar_type_descriptor


def resolve_vector_member_size_bytes(
    value: LoweredTypeValue,
    *,
    catalog: Catalog,
    source: SourceLocation,
) -> int | Diagnostic | None:
    """Resolve a lowered vector member type to fixed storage bytes when proven."""

    if not isinstance(value, LoweredVectorMemberType):
        return None

    extension = catalog.extensions.get(str(value.extension))
    if extension is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"known extension {str(value.extension)!r}",
        )

    if value.member == "register":
        return _fixed_register_size_bytes(value, extension, source)
    if value.member == "mask":
        return _mask_policy_size_bytes(
            value,
            extension,
            extension.mask_type_policy,
            "mask_type_policy",
            source,
        )
    if value.member in {"imask", "mask_underlying"}:
        return _mask_policy_size_bytes(
            value,
            extension,
            extension.integral_mask_type_policy,
            "integral_mask_type_policy",
            source,
        )
    return _unsupported_diagnostic(
        value,
        source,
        f"member {value.member!r} has no accepted fixed byte-size rule",
    )


def _fixed_register_size_bytes(
    value: LoweredVectorMemberType,
    extension: Extension,
    source: SourceLocation,
) -> int | Diagnostic:
    fixed = _fixed_vector_bits(value, extension, source)
    if isinstance(fixed, Diagnostic):
        return fixed
    if fixed % 8 != 0:
        return _missing_metadata_diagnostic(value, source, "byte-aligned vector_bits")
    return fixed // 8


def _mask_policy_size_bytes(
    value: LoweredVectorMemberType,
    extension: Extension,
    policy: ExtensionTypePolicy | None,
    policy_name: str,
    source: SourceLocation,
) -> int | Diagnostic:
    if policy is None:
        return _missing_metadata_diagnostic(
            value,
            source,
            f"{policy_name} for extension {extension.name!r}",
        )

    if policy.kind == "same_as_mask_type":
        if policy_name == "mask_type_policy":
            return _unsupported_diagnostic(
                value,
                source,
                "same_as_mask_type policy refers back to itself",
            )
        return _mask_policy_size_bytes(
            value,
            extension,
            extension.mask_type_policy,
            "mask_type_policy",
            source,
        )

    if policy.kind == "lane_bitmask":
        lane_count = _fixed_lane_count(value, extension, source)
        if isinstance(lane_count, Diagnostic):
            return lane_count
        return _ceil_div(lane_count, 8)

    if policy.kind == "native_predicate_by_lanes":
        lane_count = _fixed_lane_count(value, extension, source)
        if isinstance(lane_count, Diagnostic):
            return lane_count
        capacity = _native_predicate_lane_capacity(value, policy, lane_count, source)
        if isinstance(capacity, Diagnostic):
            return capacity
        return _ceil_div(capacity, 8)

    return _unsupported_diagnostic(
        value,
        source,
        f"policy kind {policy.kind!r} does not prove a fixed byte size",
    )


def _fixed_lane_count(
    value: LoweredVectorMemberType,
    extension: Extension,
    source: SourceLocation,
) -> int | Diagnostic:
    descriptor = lookup_scalar_type_descriptor(str(value.type_tag))
    if descriptor is None:
        return Diagnostic(
            severity="error",
            code="TSL-LOWER-MISSING-SCALAR-FACT",
            message=(
                "generation value query requires scalar bit width for scalar "
                f"type {str(value.type_tag)!r}"
            ),
            location=source,
        )

    fixed = _fixed_vector_bits(value, extension, source)
    if isinstance(fixed, Diagnostic):
        return fixed
    if descriptor.bit_width <= 0 or fixed % descriptor.bit_width != 0:
        return _missing_metadata_diagnostic(
            value,
            source,
            "vector_bits divisible by selected scalar bit width",
        )
    return fixed // descriptor.bit_width


def _fixed_vector_bits(
    value: LoweredVectorMemberType,
    extension: Extension,
    source: SourceLocation,
) -> int | Diagnostic:
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
    if not isinstance(extension.vector_bits, int) or extension.vector_bits <= 0:
        return _missing_metadata_diagnostic(
            value,
            source,
            "fixed positive integer vector_bits",
        )
    return extension.vector_bits


def _native_predicate_lane_capacity(
    value: LoweredVectorMemberType,
    policy: ExtensionTypePolicy,
    lane_count: int,
    source: SourceLocation,
) -> int | Diagnostic:
    capacities = tuple(sorted({spelling.lanes for spelling in policy.lane_spellings}))
    if not capacities:
        return _missing_metadata_diagnostic(
            value,
            source,
            "native predicate lane-capacity metadata",
        )
    for capacity in capacities:
        if capacity >= lane_count:
            return capacity
    return _unsupported_diagnostic(
        value,
        source,
        f"no native predicate lane capacity can hold {lane_count} lanes",
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _missing_metadata_diagnostic(
    value: LoweredVectorMemberType,
    source: SourceLocation,
    expected: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-MISSING-VECTOR-MEMBER-SIZE-METADATA",
        message=(
            "generation value query cannot compute a fixed byte size for "
            f"vector member {value.member!r} on extension "
            f"{str(value.extension)!r} and type {str(value.type_tag)!r}; "
            f"expected {expected}"
        ),
        location=source,
    )


def _unsupported_diagnostic(
    value: LoweredVectorMemberType,
    source: SourceLocation,
    reason: str,
) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-LOWER-UNSUPPORTED-VECTOR-MEMBER-SIZE",
        message=(
            "generation value query cannot compute a fixed byte size for "
            f"vector member {value.member!r} on extension "
            f"{str(value.extension)!r} and type {str(value.type_tag)!r}; "
            f"{reason}"
        ),
        location=source,
    )
