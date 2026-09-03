"""Typed public range contracts for generated whole-array algorithms."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from tslc.catalog.preconditions import PreconditionErrorKind


ALGORITHM_ERROR_EXPLANATIONS: Mapping[PreconditionErrorKind, str] = (
    MappingProxyType(
        {
            PreconditionErrorKind.INSUFFICIENT_INPUT: (
                "a readable related range does not cover the driving extent"
            ),
            PreconditionErrorKind.INSUFFICIENT_OUTPUT: (
                "a writable related range cannot hold the driving extent"
            ),
            PreconditionErrorKind.INDEX_OUT_OF_BOUNDS: (
                "a selected index addresses outside a represented input"
            ),
            PreconditionErrorKind.ADDRESS_OVERFLOW: (
                "selected-index address arithmetic overflows"
            ),
            PreconditionErrorKind.MISALIGNED: (
                "a scaled selected address is not aligned for the element type"
            ),
            PreconditionErrorKind.OVERLAPPING_RANGES: (
                "an output overlaps a readable range contrary to the algorithm contract"
            ),
        }
    )
)


class AlgorithmRangeRole(StrEnum):
    """Semantic role of one extent-carrying algorithm argument."""

    DRIVING_INPUT = "driving_input"
    DRIVING_INDEX = "driving_index"
    SECONDARY_INPUT = "secondary_input"
    SELECTED_INPUT = "selected_input"
    MASK_INPUT = "mask_input"
    MASK_OUTPUT = "mask_output"
    VALUE_OUTPUT = "value_output"
    INDEX_OUTPUT = "index_output"


class AlgorithmRangeConditionKind(StrEnum):
    """Closed relations that a checked algorithm can validate before dispatch."""

    COVERS = "covers"
    MASK_COVERS = "mask_covers"
    SELECTED_ADDRESSES = "selected_addresses"


class AlgorithmResultKind(StrEnum):
    VOID = "void"
    COUNT = "count"
    VALUE = "value"


class AlgorithmMaskStorageKind(StrEnum):
    """How a mask range represents the driving element extent."""

    INTEGRAL_CHUNKS = "integral_chunks"
    LAYOUT_STORAGE = "layout_storage"


@dataclass(frozen=True, slots=True)
class AlgorithmRangeBinding:
    name: str
    role: AlgorithmRangeRole
    mask_storage: AlgorithmMaskStorageKind | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("algorithm range bindings require a name")
        is_mask = self.role in {
            AlgorithmRangeRole.MASK_INPUT,
            AlgorithmRangeRole.MASK_OUTPUT,
        }
        if is_mask != (self.mask_storage is not None):
            raise ValueError(
                "mask storage is required exactly for algorithm mask bindings"
            )


@dataclass(frozen=True, slots=True)
class AlgorithmRangeCondition:
    kind: AlgorithmRangeConditionKind
    range_name: str
    reference_name: str
    error: PreconditionErrorKind

    def __post_init__(self) -> None:
        if not self.range_name or not self.reference_name:
            raise ValueError("algorithm range conditions require both bindings")
        if self.range_name == self.reference_name:
            raise ValueError("algorithm range conditions require distinct bindings")


@dataclass(frozen=True, slots=True)
class AlgorithmAliasRule:
    writable_range_name: str
    readable_range_names: tuple[str, ...]
    allow_exact_alias: bool

    def __post_init__(self) -> None:
        if not self.writable_range_name or not self.readable_range_names:
            raise ValueError("algorithm alias rules require writable and readable ranges")
        if len(set(self.readable_range_names)) != len(self.readable_range_names):
            raise ValueError("algorithm alias-rule readable ranges must be unique")


@dataclass(frozen=True, slots=True)
class AlgorithmContract:
    name: str
    ranges: tuple[AlgorithmRangeBinding, ...]
    conditions: tuple[AlgorithmRangeCondition, ...]
    result_kind: AlgorithmResultKind
    alias_rules: tuple[AlgorithmAliasRule, ...] = ()

    @property
    def checked_errors(self) -> tuple[PreconditionErrorKind, ...]:
        """Return the ordered public errors projected by this contract."""

        errors: list[PreconditionErrorKind] = []
        for condition in self.conditions:
            if condition.kind is AlgorithmRangeConditionKind.SELECTED_ADDRESSES:
                errors.extend(
                    (
                        PreconditionErrorKind.INDEX_OUT_OF_BOUNDS,
                        PreconditionErrorKind.ADDRESS_OVERFLOW,
                        PreconditionErrorKind.MISALIGNED,
                    )
                )
            else:
                errors.append(condition.error)
        if self.alias_rules:
            errors.append(PreconditionErrorKind.OVERLAPPING_RANGES)
        return tuple(dict.fromkeys(errors))

    def __post_init__(self) -> None:
        if not self.name or not self.conditions:
            raise ValueError(
                "checked algorithm contracts require a name and conditions"
            )
        names = tuple(binding.name for binding in self.ranges)
        if len(set(names)) != len(names):
            raise ValueError("algorithm range binding names must be unique")
        by_name = {binding.name: binding for binding in self.ranges}
        driving = tuple(
            binding
            for binding in self.ranges
            if binding.role
            in {
                AlgorithmRangeRole.DRIVING_INPUT,
                AlgorithmRangeRole.DRIVING_INDEX,
            }
        )
        if len(driving) != 1:
            raise ValueError("algorithm contracts require exactly one driving input")
        for condition in self.conditions:
            if (
                condition.range_name not in by_name
                or condition.reference_name not in by_name
            ):
                raise ValueError("algorithm conditions must reference declared ranges")
            if condition.reference_name != driving[0].name:
                raise ValueError(
                    "algorithm conditions must reference the driving input"
                )
            role = by_name[condition.range_name].role
            if condition.kind is AlgorithmRangeConditionKind.COVERS:
                expected_error = (
                    PreconditionErrorKind.INSUFFICIENT_OUTPUT
                    if role
                    in {
                        AlgorithmRangeRole.VALUE_OUTPUT,
                        AlgorithmRangeRole.INDEX_OUTPUT,
                    }
                    else PreconditionErrorKind.INSUFFICIENT_INPUT
                )
                if condition.error is not expected_error:
                    raise ValueError(
                        "algorithm extent error disagrees with its range role"
                    )
                if role not in {
                    AlgorithmRangeRole.SECONDARY_INPUT,
                    AlgorithmRangeRole.VALUE_OUTPUT,
                    AlgorithmRangeRole.INDEX_OUTPUT,
                }:
                    raise ValueError(
                        "algorithm extent conditions require secondary or output ranges"
                    )
            elif condition.kind is AlgorithmRangeConditionKind.MASK_COVERS:
                if role not in {
                    AlgorithmRangeRole.MASK_INPUT,
                    AlgorithmRangeRole.MASK_OUTPUT,
                }:
                    raise ValueError(
                        "algorithm mask conditions require a mask range"
                    )
                expected_error = (
                    PreconditionErrorKind.INSUFFICIENT_OUTPUT
                    if role is AlgorithmRangeRole.MASK_OUTPUT
                    else PreconditionErrorKind.INSUFFICIENT_INPUT
                )
                if condition.error is not expected_error:
                    raise ValueError(
                        "algorithm mask error disagrees with its range role"
                    )
            elif condition.kind is AlgorithmRangeConditionKind.SELECTED_ADDRESSES:
                if role is not AlgorithmRangeRole.SELECTED_INPUT:
                    raise ValueError(
                        "algorithm selected-address conditions require selected inputs"
                    )
                if condition.error is not PreconditionErrorKind.INDEX_OUT_OF_BOUNDS:
                    raise ValueError(
                        "algorithm selected-address conditions require index errors"
                    )
        for rule in self.alias_rules:
            if rule.writable_range_name not in by_name or any(
                name not in by_name for name in rule.readable_range_names
            ):
                raise ValueError("algorithm alias rules must reference declared ranges")
            if by_name[rule.writable_range_name].role not in {
                AlgorithmRangeRole.VALUE_OUTPUT,
                AlgorithmRangeRole.INDEX_OUTPUT,
                AlgorithmRangeRole.MASK_OUTPUT,
            }:
                raise ValueError("algorithm alias rules require a writable output")
            if any(
                by_name[name].role
                not in {
                    AlgorithmRangeRole.DRIVING_INPUT,
                    AlgorithmRangeRole.SECONDARY_INPUT,
                    AlgorithmRangeRole.SELECTED_INPUT,
                    AlgorithmRangeRole.DRIVING_INDEX,
                    AlgorithmRangeRole.MASK_INPUT,
                }
                for name in rule.readable_range_names
            ):
                raise ValueError("algorithm aliases may only refer to readable inputs")


def _covers(
    range_name: str,
    reference_name: str,
    error: PreconditionErrorKind,
) -> AlgorithmRangeCondition:
    return AlgorithmRangeCondition(
        AlgorithmRangeConditionKind.COVERS,
        range_name,
        reference_name,
        error,
    )


def _range(
    name: str,
    role: AlgorithmRangeRole,
    mask_storage: AlgorithmMaskStorageKind | None = None,
) -> AlgorithmRangeBinding:
    return AlgorithmRangeBinding(name, role, mask_storage)


def _contract(
    name: str,
    ranges: tuple[AlgorithmRangeBinding, ...],
    result_kind: AlgorithmResultKind,
    *,
    alias_rules: tuple[AlgorithmAliasRule, ...] = (),
) -> AlgorithmContract:
    driving = next(
        binding
        for binding in ranges
        if binding.role
        in {AlgorithmRangeRole.DRIVING_INPUT, AlgorithmRangeRole.DRIVING_INDEX}
    )
    conditions: list[AlgorithmRangeCondition] = []
    for binding in ranges:
        if binding.role is AlgorithmRangeRole.SECONDARY_INPUT:
            conditions.append(
                _covers(
                    binding.name,
                    driving.name,
                    PreconditionErrorKind.INSUFFICIENT_INPUT,
                )
            )
        elif binding.role in {
            AlgorithmRangeRole.VALUE_OUTPUT,
            AlgorithmRangeRole.INDEX_OUTPUT,
        }:
            conditions.append(
                _covers(
                    binding.name,
                    driving.name,
                    PreconditionErrorKind.INSUFFICIENT_OUTPUT,
                )
            )
        elif binding.role in {
            AlgorithmRangeRole.MASK_INPUT,
            AlgorithmRangeRole.MASK_OUTPUT,
        }:
            conditions.append(
                AlgorithmRangeCondition(
                    AlgorithmRangeConditionKind.MASK_COVERS,
                    binding.name,
                    driving.name,
                    (
                        PreconditionErrorKind.INSUFFICIENT_OUTPUT
                        if binding.role is AlgorithmRangeRole.MASK_OUTPUT
                        else PreconditionErrorKind.INSUFFICIENT_INPUT
                    ),
                )
            )
        elif binding.role is AlgorithmRangeRole.SELECTED_INPUT:
            conditions.append(
                AlgorithmRangeCondition(
                    AlgorithmRangeConditionKind.SELECTED_ADDRESSES,
                    binding.name,
                    driving.name,
                    PreconditionErrorKind.INDEX_OUT_OF_BOUNDS,
                )
            )
    return AlgorithmContract(
        name=name,
        ranges=ranges,
        conditions=tuple(conditions),
        result_kind=result_kind,
        alias_rules=alias_rules,
    )


_DRIVE = AlgorithmRangeRole.DRIVING_INPUT
_DRIVE_INDEX = AlgorithmRangeRole.DRIVING_INDEX
_SECONDARY = AlgorithmRangeRole.SECONDARY_INPUT
_SELECTED = AlgorithmRangeRole.SELECTED_INPUT
_MASK_INPUT = AlgorithmRangeRole.MASK_INPUT
_MASK_OUTPUT = AlgorithmRangeRole.MASK_OUTPUT
_VALUE_OUTPUT = AlgorithmRangeRole.VALUE_OUTPUT
_INDEX_OUTPUT = AlgorithmRangeRole.INDEX_OUTPUT
_INTEGRAL = AlgorithmMaskStorageKind.INTEGRAL_CHUNKS
_LAYOUT = AlgorithmMaskStorageKind.LAYOUT_STORAGE


def _unary_ranges(*tail: AlgorithmRangeBinding) -> tuple[AlgorithmRangeBinding, ...]:
    return (_range("input", _DRIVE), *tail)


def _binary_ranges(*tail: AlgorithmRangeBinding) -> tuple[AlgorithmRangeBinding, ...]:
    return (_range("left", _DRIVE), _range("right", _SECONDARY), *tail)


def _selected_unary_ranges(
    index_name: str = "indices",
    *tail: AlgorithmRangeBinding,
) -> tuple[AlgorithmRangeBinding, ...]:
    return (
        _range("input", _SELECTED),
        _range(index_name, _DRIVE_INDEX),
        *tail,
    )


def _selected_binary_ranges(
    index_name: str = "indices",
    *tail: AlgorithmRangeBinding,
) -> tuple[AlgorithmRangeBinding, ...]:
    return (
        _range("left", _SELECTED),
        _range("right", _SELECTED),
        _range(index_name, _DRIVE_INDEX),
        *tail,
    )


def _output_alias(
    output: str,
    *readable: str,
    allow_exact_alias: bool,
) -> tuple[AlgorithmAliasRule, ...]:
    return (AlgorithmAliasRule(output, readable, allow_exact_alias),)


def _masked_output_alias(
    output: str,
    arity: str,
) -> tuple[AlgorithmAliasRule, ...]:
    readable = ("input",) if arity == "unary" else ("left", "right")
    return (
        AlgorithmAliasRule(output, readable, allow_exact_alias=True),
        AlgorithmAliasRule(output, ("masks",), allow_exact_alias=False),
    )


_ALGORITHM_CONTRACT_SEQUENCE = (
    _contract(
        "predicate_unary",
        _unary_ranges(_range("masks", _MASK_OUTPUT, _INTEGRAL)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias("masks", "input", allow_exact_alias=False),
    ),
    _contract(
        "predicate_binary",
        _binary_ranges(_range("masks", _MASK_OUTPUT, _INTEGRAL)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "masks", "left", "right", allow_exact_alias=False
        ),
    ),
    _contract(
        "predicate_unary_mask_layout",
        _unary_ranges(_range("masks", _MASK_OUTPUT, _LAYOUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias("masks", "input", allow_exact_alias=False),
    ),
    _contract(
        "predicate_binary_mask_layout",
        _binary_ranges(_range("masks", _MASK_OUTPUT, _LAYOUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "masks", "left", "right", allow_exact_alias=False
        ),
    ),
    _contract("count_binary", _binary_ranges(), AlgorithmResultKind.COUNT),
    _contract(
        "count_masked_unary",
        _unary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "count_masked_binary",
        _binary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "count_masked_unary_mask_layout",
        _unary_ranges(_range("masks", _MASK_INPUT, _LAYOUT)),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "count_masked_binary_mask_layout",
        _binary_ranges(_range("masks", _MASK_INPUT, _LAYOUT)),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "count_selected_unary",
        _selected_unary_ranges(),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "count_selected_binary",
        _selected_binary_ranges(),
        AlgorithmResultKind.COUNT,
    ),
    _contract(
        "select_unary",
        _unary_ranges(_range("output", _VALUE_OUTPUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias("output", "input", allow_exact_alias=True),
    ),
    _contract(
        "select_binary",
        _binary_ranges(_range("output", _VALUE_OUTPUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "output", "left", "right", allow_exact_alias=True
        ),
    ),
    *(
        _contract(
            f"select_masked_{arity}{suffix}",
            (
                (_unary_ranges if arity == "unary" else _binary_ranges)(
                    _range("masks", _MASK_INPUT, storage),
                    _range("output", _VALUE_OUTPUT),
                )
            ),
            AlgorithmResultKind.COUNT,
            alias_rules=_masked_output_alias("output", arity),
        )
        for suffix, storage in (("", _INTEGRAL), ("_mask_layout", _LAYOUT))
        for arity in ("unary", "binary")
    ),
    _contract(
        "select_indices_unary",
        _unary_ranges(_range("indices", _INDEX_OUTPUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias("indices", "input", allow_exact_alias=False),
    ),
    _contract(
        "select_indices_binary",
        _binary_ranges(_range("indices", _INDEX_OUTPUT)),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "indices", "left", "right", allow_exact_alias=False
        ),
    ),
    *(
        _contract(
            f"select_masked_indices_{arity}{suffix}",
            (
                (_unary_ranges if arity == "unary" else _binary_ranges)(
                    _range("masks", _MASK_INPUT, storage),
                    _range("indices", _INDEX_OUTPUT),
                )
            ),
            AlgorithmResultKind.COUNT,
            alias_rules=_output_alias(
                "indices",
                *("input",) if arity == "unary" else ("left", "right"),
                "masks",
                allow_exact_alias=False,
            ),
        )
        for suffix, storage in (("", _INTEGRAL), ("_mask_layout", _LAYOUT))
        for arity in ("unary", "binary")
    ),
    _contract(
        "select_selected_indices_unary",
        _selected_unary_ranges(
            "input_indices", _range("output_indices", _INDEX_OUTPUT)
        ),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "output_indices", "input", "input_indices", allow_exact_alias=False
        ),
    ),
    _contract(
        "select_selected_indices_binary",
        _selected_binary_ranges(
            "input_indices", _range("output_indices", _INDEX_OUTPUT)
        ),
        AlgorithmResultKind.COUNT,
        alias_rules=_output_alias(
            "output_indices",
            "left",
            "right",
            "input_indices",
            allow_exact_alias=False,
        ),
    ),
    *(
        _contract(
            f"{family}_selected_{arity}",
            (
                _selected_unary_ranges()
                if arity == "unary"
                else _selected_binary_ranges()
            )
            + (
                (_range("output", _VALUE_OUTPUT),)
                if family == "transform"
                else ()
            ),
            (
                AlgorithmResultKind.VALUE
                if family == "aggregate"
                else AlgorithmResultKind.VOID
            ),
            alias_rules=(
                _output_alias(
                    "output",
                    *("input",) if arity == "unary" else ("left", "right"),
                    "indices",
                    allow_exact_alias=False,
                )
                if family == "transform"
                else ()
            ),
        )
        for family in ("transform", "consume", "aggregate")
        for arity in ("unary", "binary")
    ),
    *(
        _contract(
            f"transform_{mode}_{arity}{suffix}",
            (
                (_unary_ranges if arity == "unary" else _binary_ranges)(
                    _range("masks", _MASK_INPUT, storage),
                    _range("output", _VALUE_OUTPUT),
                )
            ),
            AlgorithmResultKind.VOID,
            alias_rules=_masked_output_alias("output", arity),
        )
        for mode in ("where", "masked")
        for suffix, storage in (("", _INTEGRAL), ("_mask_layout", _LAYOUT))
        for arity in ("unary", "binary")
    ),
    _contract(
        "transform_unary",
        _unary_ranges(_range("output", _VALUE_OUTPUT)),
        AlgorithmResultKind.VOID,
        alias_rules=_output_alias("output", "input", allow_exact_alias=True),
    ),
    _contract(
        "transform_binary",
        _binary_ranges(_range("output", _VALUE_OUTPUT)),
        AlgorithmResultKind.VOID,
        alias_rules=_output_alias(
            "output", "left", "right", allow_exact_alias=True
        ),
    ),
    _contract("consume_binary", _binary_ranges(), AlgorithmResultKind.VOID),
    _contract(
        "consume_masked_unary",
        _unary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.VOID,
    ),
    _contract(
        "consume_masked_binary",
        _binary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.VOID,
    ),
    _contract("aggregate_binary", _binary_ranges(), AlgorithmResultKind.VALUE),
    _contract(
        "aggregate_masked_unary",
        _unary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.VALUE,
    ),
    _contract(
        "aggregate_masked_binary",
        _binary_ranges(_range("masks", _MASK_INPUT, _INTEGRAL)),
        AlgorithmResultKind.VALUE,
    ),
)

ALGORITHM_CONTRACTS: Mapping[str, AlgorithmContract] = MappingProxyType(
    {contract.name: contract for contract in _ALGORITHM_CONTRACT_SEQUENCE}
)

if len(ALGORITHM_CONTRACTS) != len(_ALGORITHM_CONTRACT_SEQUENCE):
    raise ValueError("algorithm contract names must be unique")


__all__ = (
    "ALGORITHM_ERROR_EXPLANATIONS",
    "ALGORITHM_CONTRACTS",
    "AlgorithmContract",
    "AlgorithmAliasRule",
    "AlgorithmRangeBinding",
    "AlgorithmRangeCondition",
    "AlgorithmRangeConditionKind",
    "AlgorithmRangeRole",
    "AlgorithmResultKind",
    "AlgorithmMaskStorageKind",
)
