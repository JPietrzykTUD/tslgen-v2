"""Typed arithmetic contracts promoted from primitive source data."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.diagnostics import SourceSpan


class ArithmeticOperation(StrEnum):
    ADDITION = "addition"
    DIVISION = "division"
    MULTIPLICATION = "multiplication"
    NEGATION = "negation"
    REMAINDER = "remainder"
    SUBTRACTION = "subtraction"


class ArithmeticOperandRole(StrEnum):
    DIVISOR = "divisor"
    PRIMARY = "primary"
    SECONDARY = "secondary"


class ArithmeticGuarantee(StrEnum):
    INTEGER_WRAPPING = "integer_wrapping"
    INTEGER_QUOTIENT_TOWARD_ZERO = "integer_quotient_toward_zero"
    INTEGER_REMAINDER_HAS_DIVIDEND_SIGN = "integer_remainder_has_dividend_sign"
    INTEGER_ZERO_DIVISOR_FAILS = "integer_zero_divisor_fails"
    SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN = "signed_min_div_neg_one_returns_min"
    SIGNED_MIN_REM_NEG_ONE_RETURNS_ZERO = "signed_min_rem_neg_one_returns_zero"
    FLOATING_DIVISION_IEEE754_VALUES = "floating_division_ieee754_values"
    FLOATING_SIGN_BIT_TOGGLE = "floating_sign_bit_toggle"
    FLOATING_REMAINDER_TRUNCATING = "floating_remainder_truncating"
    INACTIVE_LANES_DO_NOT_PARTICIPATE = "inactive_lanes_do_not_participate"


class ArithmeticNumericDomain(StrEnum):
    INTEGER = "integer"
    SIGNED_INTEGER = "signed_integer"
    FLOATING = "floating"


class ArithmeticMaskRequirement(StrEnum):
    ANY = "any"
    MASKED = "masked"


class ArithmeticConflictGroup(StrEnum):
    INTEGER_OVERFLOW = "integer_overflow"
    INTEGER_QUOTIENT_ROUNDING = "integer_quotient_rounding"
    INTEGER_REMAINDER_SIGN = "integer_remainder_sign"
    INTEGER_ZERO_DIVISOR = "integer_zero_divisor"
    SIGNED_DIVISION_OVERFLOW = "signed_division_overflow"
    SIGNED_REMAINDER_OVERFLOW = "signed_remainder_overflow"
    FLOATING_DIVISION = "floating_division"
    FLOATING_NEGATION = "floating_negation"
    FLOATING_REMAINDER = "floating_remainder"
    MASKED_PARTICIPATION = "masked_participation"


@dataclass(frozen=True, slots=True)
class ArithmeticGuaranteeSpec:
    """Applicability and conflict metadata for one atomic guarantee."""

    guarantee: ArithmeticGuarantee
    description: str
    required_all_operations: frozenset[ArithmeticOperation] = frozenset()
    required_any_operations: frozenset[ArithmeticOperation] = frozenset()
    numeric_domain: ArithmeticNumericDomain | None = None
    mask_requirement: ArithmeticMaskRequirement = ArithmeticMaskRequirement.ANY
    prerequisite_roles: frozenset[ArithmeticOperandRole] = frozenset()
    conflict_group: ArithmeticConflictGroup | None = None


@dataclass(frozen=True, slots=True)
class ArithmeticOperandBinding:
    """A semantic role resolved to one declaration-local signature operand."""

    role: ArithmeticOperandRole
    parameter_name: str
    parameter_index: int
    non_mask_ordinal: int
    parameter_kind: str
    source: SourceSpan | None = None
    parameter_source: SourceSpan | None = None

    @property
    def family_identity(self) -> tuple[ArithmeticOperandRole, int, str]:
        return (self.role, self.non_mask_ordinal, self.parameter_kind)


@dataclass(frozen=True, slots=True)
class ArithmeticContract:
    """One primitive declaration's explicit language-neutral arithmetic facts."""

    operations: frozenset[ArithmeticOperation]
    operand_bindings: tuple[ArithmeticOperandBinding, ...]
    guarantees: frozenset[ArithmeticGuarantee]
    source: SourceSpan | None = None
    operations_source: SourceSpan | None = None
    guarantees_source: SourceSpan | None = None

    def binding(self, role: ArithmeticOperandRole) -> ArithmeticOperandBinding | None:
        return next(
            (binding for binding in self.operand_bindings if binding.role is role),
            None,
        )

    def has_guarantee(self, guarantee: ArithmeticGuarantee) -> bool:
        return guarantee in self.guarantees

    @property
    def ordered_operations(self) -> tuple[ArithmeticOperation, ...]:
        return tuple(sorted(self.operations, key=lambda operation: operation.value))

    @property
    def ordered_guarantees(self) -> tuple[ArithmeticGuarantee, ...]:
        return tuple(sorted(self.guarantees, key=lambda guarantee: guarantee.value))

    @property
    def non_mask_guarantees(self) -> frozenset[ArithmeticGuarantee]:
        return frozenset(
            guarantee
            for guarantee in self.guarantees
            if ARITHMETIC_GUARANTEE_SPECS[guarantee].mask_requirement
            is not ArithmeticMaskRequirement.MASKED
        )

    @property
    def family_operand_identity(
        self,
    ) -> tuple[tuple[ArithmeticOperandRole, int, str], ...]:
        return tuple(
            sorted(
                (binding.family_identity for binding in self.operand_bindings),
                key=lambda item: item[0].value,
            )
        )


ARITHMETIC_OPERATION_DESCRIPTIONS: Mapping[ArithmeticOperation, str] = MappingProxyType(
    {
        ArithmeticOperation.ADDITION: "Produces the lane-wise sum of two values.",
        ArithmeticOperation.DIVISION: "Produces a quotient from a dividend and divisor.",
        ArithmeticOperation.MULTIPLICATION: "Produces the lane-wise product of two values.",
        ArithmeticOperation.NEGATION: "Negates each lane of one value.",
        ArithmeticOperation.REMAINDER: (
            "Produces the remainder associated with a dividend and divisor."
        ),
        ArithmeticOperation.SUBTRACTION: "Produces the lane-wise difference of two values.",
    }
)

ARITHMETIC_OPERAND_ROLE_DESCRIPTIONS: Mapping[ArithmeticOperandRole, str] = (
    MappingProxyType(
        {
            ArithmeticOperandRole.DIVISOR: (
                "The declared operand used as the divisor for division or remainder."
            ),
            ArithmeticOperandRole.PRIMARY: (
                "The primary arithmetic value and natural method receiver."
            ),
            ArithmeticOperandRole.SECONDARY: "The second arithmetic value operand.",
        }
    )
)

ARITHMETIC_DIVISOR_KINDS = frozenset({"v", "s", "sImm"})
ARITHMETIC_OPERAND_ROLE_KINDS: Mapping[ArithmeticOperandRole, frozenset[str]] = (
    MappingProxyType(
        {
            ArithmeticOperandRole.DIVISOR: ARITHMETIC_DIVISOR_KINDS,
            ArithmeticOperandRole.PRIMARY: frozenset({"v"}),
            ArithmeticOperandRole.SECONDARY: frozenset({"v", "s", "sImm"}),
        }
    )
)
ARITHMETIC_INTEGER_IMMEDIATE_ZERO_MARKER = "TSL_ARITH_INTEGER_IMMEDIATE_ZERO"


def _spec(
    guarantee: ArithmeticGuarantee,
    description: str,
    *,
    all_operations: frozenset[ArithmeticOperation] = frozenset(),
    any_operations: frozenset[ArithmeticOperation] = frozenset(),
    domain: ArithmeticNumericDomain | None = None,
    mask: ArithmeticMaskRequirement = ArithmeticMaskRequirement.ANY,
    roles: frozenset[ArithmeticOperandRole] = frozenset(),
    conflict: ArithmeticConflictGroup | None = None,
) -> ArithmeticGuaranteeSpec:
    return ArithmeticGuaranteeSpec(
        guarantee=guarantee,
        description=description,
        required_all_operations=all_operations,
        required_any_operations=any_operations,
        numeric_domain=domain,
        mask_requirement=mask,
        prerequisite_roles=roles,
        conflict_group=conflict,
    )


_DIVISION = frozenset({ArithmeticOperation.DIVISION})
_REMAINDER = frozenset({ArithmeticOperation.REMAINDER})
_NEGATION = frozenset({ArithmeticOperation.NEGATION})
_DIVISION_OR_REMAINDER = frozenset(
    {ArithmeticOperation.DIVISION, ArithmeticOperation.REMAINDER}
)
_DIVISOR = frozenset({ArithmeticOperandRole.DIVISOR})
_WRAPPING_OPERATIONS = frozenset(
    {
        ArithmeticOperation.ADDITION,
        ArithmeticOperation.MULTIPLICATION,
        ArithmeticOperation.NEGATION,
        ArithmeticOperation.SUBTRACTION,
    }
)

ARITHMETIC_GUARANTEE_SPECS: Mapping[
    ArithmeticGuarantee, ArithmeticGuaranteeSpec
] = MappingProxyType(
    {
        ArithmeticGuarantee.INTEGER_WRAPPING: _spec(
            ArithmeticGuarantee.INTEGER_WRAPPING,
            "Integer results wrap modulo the lane width.",
            any_operations=_WRAPPING_OPERATIONS,
            domain=ArithmeticNumericDomain.INTEGER,
            roles=frozenset({ArithmeticOperandRole.PRIMARY}),
            conflict=ArithmeticConflictGroup.INTEGER_OVERFLOW,
        ),
        ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO: _spec(
            ArithmeticGuarantee.INTEGER_QUOTIENT_TOWARD_ZERO,
            "Integer quotients discard the fractional part toward zero.",
            all_operations=_DIVISION,
            domain=ArithmeticNumericDomain.INTEGER,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.INTEGER_QUOTIENT_ROUNDING,
        ),
        ArithmeticGuarantee.INTEGER_REMAINDER_HAS_DIVIDEND_SIGN: _spec(
            ArithmeticGuarantee.INTEGER_REMAINDER_HAS_DIVIDEND_SIGN,
            "A nonzero integer remainder has the dividend's sign.",
            all_operations=_REMAINDER,
            domain=ArithmeticNumericDomain.INTEGER,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.INTEGER_REMAINDER_SIGN,
        ),
        ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS: _spec(
            ArithmeticGuarantee.INTEGER_ZERO_DIVISOR_FAILS,
            "A participating integer zero divisor prevents normal return.",
            any_operations=_DIVISION_OR_REMAINDER,
            domain=ArithmeticNumericDomain.INTEGER,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.INTEGER_ZERO_DIVISOR,
        ),
        ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN: _spec(
            ArithmeticGuarantee.SIGNED_MIN_DIV_NEG_ONE_RETURNS_MIN,
            "Signed MIN divided by -1 returns MIN.",
            all_operations=_DIVISION,
            domain=ArithmeticNumericDomain.SIGNED_INTEGER,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.SIGNED_DIVISION_OVERFLOW,
        ),
        ArithmeticGuarantee.SIGNED_MIN_REM_NEG_ONE_RETURNS_ZERO: _spec(
            ArithmeticGuarantee.SIGNED_MIN_REM_NEG_ONE_RETURNS_ZERO,
            "Signed MIN remainder -1 returns zero.",
            all_operations=_REMAINDER,
            domain=ArithmeticNumericDomain.SIGNED_INTEGER,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.SIGNED_REMAINDER_OVERFLOW,
        ),
        ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES: _spec(
            ArithmeticGuarantee.FLOATING_DIVISION_IEEE754_VALUES,
            "Floating division preserves ordinary IEEE 754 returned-value behavior.",
            all_operations=_DIVISION,
            domain=ArithmeticNumericDomain.FLOATING,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.FLOATING_DIVISION,
        ),
        ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE: _spec(
            ArithmeticGuarantee.FLOATING_SIGN_BIT_TOGGLE,
            "Floating results differ only by the sign bit, preserving all other bits.",
            all_operations=_NEGATION,
            domain=ArithmeticNumericDomain.FLOATING,
            roles=frozenset({ArithmeticOperandRole.PRIMARY}),
            conflict=ArithmeticConflictGroup.FLOATING_NEGATION,
        ),
        ArithmeticGuarantee.FLOATING_REMAINDER_TRUNCATING: _spec(
            ArithmeticGuarantee.FLOATING_REMAINDER_TRUNCATING,
            "Floating remainder uses a truncating quotient with fmod-style values.",
            all_operations=_REMAINDER,
            domain=ArithmeticNumericDomain.FLOATING,
            roles=_DIVISOR,
            conflict=ArithmeticConflictGroup.FLOATING_REMAINDER,
        ),
        ArithmeticGuarantee.INACTIVE_LANES_DO_NOT_PARTICIPATE: _spec(
            ArithmeticGuarantee.INACTIVE_LANES_DO_NOT_PARTICIPATE,
            "Inactive masked operands cannot affect the result or cause failure.",
            mask=ArithmeticMaskRequirement.MASKED,
            conflict=ArithmeticConflictGroup.MASKED_PARTICIPATION,
        ),
    }
)


def arithmetic_operation_values() -> tuple[str, ...]:
    return tuple(sorted(operation.value for operation in ArithmeticOperation))


def arithmetic_operand_role_values() -> tuple[str, ...]:
    return tuple(sorted(role.value for role in ArithmeticOperandRole))


def arithmetic_guarantee_values() -> tuple[str, ...]:
    return tuple(sorted(guarantee.value for guarantee in ArithmeticGuarantee))


__all__ = (
    "ARITHMETIC_DIVISOR_KINDS",
    "ARITHMETIC_GUARANTEE_SPECS",
    "ARITHMETIC_INTEGER_IMMEDIATE_ZERO_MARKER",
    "ARITHMETIC_OPERAND_ROLE_KINDS",
    "ARITHMETIC_OPERAND_ROLE_DESCRIPTIONS",
    "ARITHMETIC_OPERATION_DESCRIPTIONS",
    "ArithmeticConflictGroup",
    "ArithmeticContract",
    "ArithmeticGuarantee",
    "ArithmeticGuaranteeSpec",
    "ArithmeticMaskRequirement",
    "ArithmeticNumericDomain",
    "ArithmeticOperandBinding",
    "ArithmeticOperandRole",
    "ArithmeticOperation",
    "arithmetic_guarantee_values",
    "arithmetic_operand_role_values",
    "arithmetic_operation_values",
)
