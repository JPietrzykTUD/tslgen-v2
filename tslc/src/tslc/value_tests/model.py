"""Typed value-test plans consumed by backend test renderers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Literal

from tslc.diagnostics import Diagnostic

ValueTestCoverageStatus = Literal[
    "emitted",
    "compile_only_emitted",
    "missing_authored_tests",
    "authored_unplanned",
    "backend_unsupported",
]
ExpectedArity = Literal["optional", "non_empty", "one", "lanes", "target_lanes"]
InputArity = Literal["optional", "non_empty", "one"]


@dataclass(frozen=True, slots=True)
class ValueTestCaseRequirements:
    """Construction-time requirements for one value-test case kind.

    The case plan remains one frozen record because the C++ and Rust renderers
    share most fields, but every case kind now owns the facts its renderer
    assumes. This catches malformed plans at the builder boundary instead of
    letting optional fields act as an unchecked variant dictionary.
    """

    expected: ExpectedArity = "optional"
    vector_inputs: InputArity = "optional"
    mask_inputs: InputArity = "optional"
    scalar_inputs: InputArity = "optional"
    required_fields: frozenset[str] = frozenset()
    required_non_empty_fields: frozenset[str] = frozenset()
    vector_inputs_match_lanes: bool = False
    fuzz_case: bool = False


@dataclass(frozen=True, slots=True)
class ValueTestCaseCapability:
    """Registered value-test case kind and the plan invariants it requires."""

    kind: str
    requirements: ValueTestCaseRequirements

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("value-test case capability requires non-empty kind")


@dataclass(frozen=True, slots=True)
class HarnessPrimitiveNames:
    """Source-owned primitive names used by generated value-test harness code."""

    from_array: str | None
    to_array: str | None
    to_integral: str | None
    load: str | None = None
    store: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def round_trip_ready(self) -> bool:
        return self.from_array is not None and self.to_array is not None


@dataclass(frozen=True, slots=True)
class ValueTestCasePlan:
    """One backend-specific generated value-test function, before text rendering."""

    CASE_REQUIREMENTS: ClassVar[Mapping[str, ValueTestCaseRequirements]]

    kind: str
    function_name: str
    case_name: str
    call_name: str
    type_tag: str
    base_spelling: str
    lanes: int
    vector_inputs: tuple[tuple[str, ...], ...] = ()
    expected: tuple[str, ...] = ()
    expected_type_tag: str | None = None
    result_kind: str | None = None
    param_kinds: tuple[str, ...] = ()
    mask_inputs: tuple[str, ...] = ()
    scalar_input: str | None = None
    axis_args: tuple[str, ...] = ()
    immediate_value: str | None = None
    generic_defaults: tuple[str, ...] = ()
    target_base_spelling: str | None = None
    target_lanes: int | None = None
    index_type_tag: str | None = None
    index_base_spelling: str | None = None
    index_lanes: int | None = None
    source_extension: str | None = None
    target_extension: str | None = None
    index_value: str | None = None
    hardware_extension: str | None = None
    from_array_name: str | None = None
    to_array_name: str | None = None
    to_integral_name: str | None = None
    load_name: str | None = None
    store_name: str | None = None
    runtime_lanes_expr: str | None = None
    mask_from_bits_exprs: tuple[str, ...] = ()
    mask_check_expr: str | None = None
    buffer_offset: int = 0
    buffer_length: int | None = None
    source_offset: int = 0
    scalar_inputs: tuple[str, ...] = ()
    text_expected: str | None = None
    # Differential-fuzz cases (kind="differential_fuzz") carry no authored inputs: the emitted code
    # loops `fuzz_iterations` PRNG-seeded random inputs through hardware-vs-generic at runtime.
    fuzz_seed: int | None = None
    fuzz_iterations: int = 0

    @classmethod
    def checked(cls, **fields: object) -> "ValueTestCasePlan":
        """Keyword-only construction hook for builders.

        Direct dataclass construction is still supported for tests and small
        fixtures, but both paths run the same ``__post_init__`` validator.
        """

        return cls(**fields)  # type: ignore[arg-type]

    def __post_init__(self) -> None:
        self._validate_common_fields()
        try:
            requirements = self.CASE_REQUIREMENTS[self.kind]
        except KeyError as exc:
            raise ValueError(f"unsupported value-test case kind {self.kind!r}") from exc
        self._validate_required_fields(requirements)
        self._validate_expected(requirements)
        self._validate_inputs(requirements)
        self._validate_fuzz(requirements)
        self._validate_differential_helpers()

    def _validate_common_fields(self) -> None:
        for field_name in (
            "kind",
            "function_name",
            "case_name",
            "call_name",
            "type_tag",
            "base_spelling",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"value-test case {self.kind!r} requires non-empty {field_name}"
                )
        if self.lanes <= 0:
            raise ValueError(
                f"value-test case {self.function_name!r} requires positive lanes"
            )
        if self.buffer_length is not None and self.buffer_length <= 0:
            raise ValueError(
                f"value-test case {self.function_name!r} requires positive buffer_length"
            )
        if self.target_lanes is not None and self.target_lanes <= 0:
            raise ValueError(
                f"value-test case {self.function_name!r} requires positive target_lanes"
            )
        if self.index_lanes is not None and self.index_lanes <= 0:
            raise ValueError(
                f"value-test case {self.function_name!r} requires positive index_lanes"
            )
        if self.source_offset < 0 or self.buffer_offset < 0:
            raise ValueError(
                f"value-test case {self.function_name!r} offsets must be non-negative"
            )

    def _validate_required_fields(self, requirements: ValueTestCaseRequirements) -> None:
        for field_name in sorted(requirements.required_fields):
            if self._field_is_missing(field_name):
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    f"requires {field_name}"
                )
        for field_name in sorted(requirements.required_non_empty_fields):
            value = getattr(self, field_name)
            if not value:
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    f"requires non-empty {field_name}"
                )

    def _validate_expected(self, requirements: ValueTestCaseRequirements) -> None:
        expected_len = len(self.expected)
        if requirements.expected == "optional":
            return
        if requirements.expected == "non_empty" and expected_len == 0:
            raise ValueError(self._expected_error("at least one value"))
        if requirements.expected == "one" and expected_len != 1:
            raise ValueError(self._expected_error("exactly one value"))
        if requirements.expected == "lanes" and expected_len != self.lanes:
            raise ValueError(self._expected_error(f"{self.lanes} lane values"))
        if requirements.expected == "target_lanes":
            if self.target_lanes is None:
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    "requires target_lanes"
                )
            if expected_len != self.target_lanes:
                raise ValueError(
                    self._expected_error(f"{self.target_lanes} target lane values")
                )

    def _validate_inputs(self, requirements: ValueTestCaseRequirements) -> None:
        self._validate_tuple_arity("vector_inputs", requirements.vector_inputs)
        self._validate_tuple_arity("mask_inputs", requirements.mask_inputs)
        self._validate_tuple_arity("scalar_inputs", requirements.scalar_inputs)
        if requirements.vector_inputs_match_lanes:
            for index, values in enumerate(self.vector_inputs):
                if len(values) != self.lanes:
                    raise ValueError(
                        f"value-test case {self.function_name!r} kind {self.kind!r} "
                        f"requires vector_inputs[{index}] to have {self.lanes} values"
                    )
        if self.mask_from_bits_exprs and self.mask_inputs:
            if len(self.mask_from_bits_exprs) != len(self.mask_inputs):
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    "requires one mask_from_bits expression per mask input"
                )

    def _validate_tuple_arity(self, field_name: str, arity: InputArity) -> None:
        values = getattr(self, field_name)
        if arity == "optional":
            return
        if arity == "non_empty" and not values:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                f"requires non-empty {field_name}"
            )
        if arity == "one" and len(values) != 1:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                f"requires exactly one {field_name} entry"
            )

    def _validate_fuzz(self, requirements: ValueTestCaseRequirements) -> None:
        if not requirements.fuzz_case:
            return
        if self.fuzz_seed is None:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires fuzz_seed"
            )
        if self.fuzz_iterations <= 0:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires positive fuzz_iterations"
            )

    def _validate_differential_helpers(self) -> None:
        if self.kind not in {"differential", "differential_fuzz"}:
            return
        if self.result_kind == "m":
            if self.to_integral_name is None:
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    "requires to_integral_name for mask results"
                )
            return
        if self.to_array_name is None:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires to_array_name for value results"
            )

    def _field_is_missing(self, field_name: str) -> bool:
        value = getattr(self, field_name)
        if value is None:
            return True
        if isinstance(value, str) and value == "":
            return True
        return False

    def _expected_error(self, expectation: str) -> str:
        return (
            f"value-test case {self.function_name!r} kind {self.kind!r} "
            f"requires expected to contain {expectation}"
        )


_RESULT_AND_PARAMS = frozenset({"result_kind", "param_kinds"})
_SCALABLE_VALUE_FIELDS = frozenset(
    {
        "result_kind",
        "param_kinds",
        "source_extension",
        "load_name",
        "store_name",
        "runtime_lanes_expr",
    }
)
_SCALABLE_MASK_FIELDS = frozenset(
    {
        "result_kind",
        "param_kinds",
        "source_extension",
        "runtime_lanes_expr",
        "mask_check_expr",
    }
)
_EXTENSION_HELPER_FIELDS = frozenset(
    {"source_extension", "target_extension", "from_array_name", "to_array_name"}
)
_CONVERSION_TARGET_FIELDS = frozenset(
    {"expected_type_tag", "target_base_spelling", "target_lanes"}
)
_DIFFERENTIAL_FIELDS = frozenset(
    {"result_kind", "param_kinds", "hardware_extension", "from_array_name"}
)


_VALUE_TEST_CASE_REQUIREMENTS = MappingProxyType({
    "array_to_vector": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "broadcast": ValueTestCaseRequirements(
        expected="lanes",
        required_fields=frozenset({"scalar_input"}),
    ),
    "compile_only": ValueTestCaseRequirements(
        required_fields=frozenset({"result_kind"}),
    ),
    "convert": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_fields=_CONVERSION_TARGET_FIELDS | frozenset({"index_value"}),
    ),
    "differential": ValueTestCaseRequirements(
        vector_inputs="non_empty",
        required_fields=_DIFFERENTIAL_FIELDS,
    ),
    "differential_fuzz": ValueTestCaseRequirements(
        required_fields=_DIFFERENTIAL_FIELDS,
        fuzz_case=True,
    ),
    "extension_extract": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        required_fields=_EXTENSION_HELPER_FIELDS | frozenset({"index_value"}),
    ),
    "extension_insert": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="non_empty",
        required_fields=_EXTENSION_HELPER_FIELDS | frozenset({"index_value"}),
    ),
    "generic_golden": ValueTestCaseRequirements(
        expected="lanes",
        required_fields=_RESULT_AND_PARAMS,
        vector_inputs_match_lanes=True,
    ),
    "immediate": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        required_fields=frozenset({"immediate_value"}),
        vector_inputs_match_lanes=True,
    ),
    "indexed_load": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="non_empty",
        required_fields=frozenset({"immediate_value", "target_lanes"}),
    ),
    "indexed_store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="non_empty",
        required_fields=frozenset({"immediate_value", "buffer_length"}),
    ),
    "lane_list": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "load": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "load_convert": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_fields=_CONVERSION_TARGET_FIELDS,
    ),
    "mask_logic": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="non_empty",
        required_fields=frozenset({"param_kinds"}),
    ),
    "mask_pointer_load": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
    ),
    "mask_result": ValueTestCaseRequirements(
        expected="one",
        required_fields=frozenset({"param_kinds"}),
    ),
    "mask_store": ValueTestCaseRequirements(
        expected="non_empty",
        mask_inputs="one",
        required_fields=frozenset({"buffer_length"}),
    ),
    "mask_to_vector": ValueTestCaseRequirements(
        expected="lanes",
        mask_inputs="one",
    ),
    "masked": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        mask_inputs="one",
        required_fields=frozenset({"param_kinds"}),
        vector_inputs_match_lanes=True,
    ),
    "masked_pointer_load": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        mask_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "masked_pointer_store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        mask_inputs="one",
        required_fields=frozenset({"buffer_length"}),
        vector_inputs_match_lanes=True,
    ),
    "memory_copy": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        scalar_inputs="one",
        required_fields=frozenset({"buffer_length"}),
    ),
    "pointer_free": ValueTestCaseRequirements(
        scalar_inputs="one",
    ),
    "pointer_lifetime": ValueTestCaseRequirements(
        scalar_inputs="non_empty",
    ),
    "reduction": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        vector_inputs_match_lanes=True,
    ),
    "repr_cast": ValueTestCaseRequirements(
        expected="target_lanes",
        vector_inputs="one",
        required_fields=_CONVERSION_TARGET_FIELDS,
    ),
    "scalar_pointer_load": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        required_fields=frozenset({"buffer_length"}),
    ),
    "scalar_result": ValueTestCaseRequirements(
        expected="one",
        required_fields=frozenset({"result_kind", "param_kinds"}),
    ),
    "scalar_vector": ValueTestCaseRequirements(
        expected="lanes",
        required_fields=frozenset({"param_kinds"}),
    ),
    "scalable_golden": ValueTestCaseRequirements(
        expected="lanes",
        required_fields=_SCALABLE_VALUE_FIELDS,
    ),
    "scalable_mask_constant": ValueTestCaseRequirements(
        expected="one",
        required_fields=_SCALABLE_MASK_FIELDS,
    ),
    "scalable_mask_conversion": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="one",
        required_fields=_SCALABLE_MASK_FIELDS,
        required_non_empty_fields=frozenset({"mask_from_bits_exprs"}),
    ),
    "scalable_mask_logic": ValueTestCaseRequirements(
        expected="one",
        mask_inputs="non_empty",
        required_fields=_SCALABLE_MASK_FIELDS,
        required_non_empty_fields=frozenset({"mask_from_bits_exprs"}),
    ),
    "scalable_mask_result": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        required_fields=_SCALABLE_MASK_FIELDS | frozenset({"load_name"}),
    ),
    "scalable_mask_store": ValueTestCaseRequirements(
        expected="non_empty",
        mask_inputs="one",
        required_fields=frozenset(
            {
                "expected_type_tag",
                "result_kind",
                "param_kinds",
                "runtime_lanes_expr",
                "source_extension",
                "target_base_spelling",
            }
        ),
        required_non_empty_fields=frozenset({"mask_from_bits_exprs"}),
    ),
    "scalable_masked": ValueTestCaseRequirements(
        expected="lanes",
        mask_inputs="one",
        required_fields=_SCALABLE_VALUE_FIELDS,
        required_non_empty_fields=frozenset({"mask_from_bits_exprs"}),
    ),
    "scalable_masked_mask_result": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="non_empty",
        mask_inputs="one",
        required_fields=_SCALABLE_MASK_FIELDS | frozenset({"load_name"}),
        required_non_empty_fields=frozenset({"mask_from_bits_exprs"}),
    ),
    "store": ValueTestCaseRequirements(
        expected="non_empty",
        vector_inputs="one",
        required_fields=frozenset({"buffer_length"}),
        vector_inputs_match_lanes=True,
    ),
    "stream": ValueTestCaseRequirements(
        expected="one",
        vector_inputs="one",
        scalar_inputs="one",
        required_fields=frozenset({"text_expected"}),
        vector_inputs_match_lanes=True,
    ),
    "vector_to_array": ValueTestCaseRequirements(
        expected="lanes",
        vector_inputs="one",
        vector_inputs_match_lanes=True,
    ),
})


def _case_capabilities(
    requirements: Mapping[str, ValueTestCaseRequirements],
) -> tuple[ValueTestCaseCapability, ...]:
    return tuple(
        ValueTestCaseCapability(kind, requirement)
        for kind, requirement in sorted(requirements.items())
    )


def _case_requirements(
    capabilities: tuple[ValueTestCaseCapability, ...],
) -> Mapping[str, ValueTestCaseRequirements]:
    result: dict[str, ValueTestCaseRequirements] = {}
    for capability in capabilities:
        if capability.kind in result:
            raise ValueError(f"duplicate value-test case kind {capability.kind!r}")
        result[capability.kind] = capability.requirements
    return MappingProxyType(result)


DEFAULT_VALUE_TEST_CASE_CAPABILITIES = _case_capabilities(_VALUE_TEST_CASE_REQUIREMENTS)
DEFAULT_VALUE_TEST_CASE_KINDS = frozenset(
    capability.kind for capability in DEFAULT_VALUE_TEST_CASE_CAPABILITIES
)
ValueTestCasePlan.CASE_REQUIREMENTS = _case_requirements(
    DEFAULT_VALUE_TEST_CASE_CAPABILITIES
)


@dataclass(frozen=True, slots=True)
class ValueTestCoverageEntry:
    """Planning outcome for one authored value-test case or primitive test gap."""

    backend_id: str
    profile_name: str
    primitive_name: str
    case_name: str | None
    status: ValueTestCoverageStatus
    reason: str = ""
    case_kind: str | None = None


@dataclass(frozen=True, slots=True)
class ValueTestParityEntry:
    """Per-backend planning outcomes for one authored value-test identity."""

    profile_name: str
    primitive_name: str
    case_name: str | None
    backend_statuses: tuple[ValueTestCoverageEntry, ...]

    def status_for(self, backend_id: str) -> ValueTestCoverageStatus | None:
        for entry in self.backend_statuses:
            if entry.backend_id == backend_id:
                return entry.status
        return None


@dataclass(frozen=True, slots=True)
class ValueTestBackendSupport:
    """Value-test case kinds one backend renderer can consume."""

    backend_id: str
    case_kinds: frozenset[str]
    supports_differential: bool = False


@dataclass(frozen=True, slots=True)
class ValueTestProfilePlan:
    backend_id: str
    profile_name: str
    cases: tuple[ValueTestCasePlan, ...]
    support_headers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValueTestProjectPlan:
    profiles: tuple[ValueTestProfilePlan, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    coverage: tuple[ValueTestCoverageEntry, ...] = ()

    def profiles_for(self, backend_id: str) -> tuple[ValueTestProfilePlan, ...]:
        return tuple(profile for profile in self.profiles if profile.backend_id == backend_id)


__all__ = (
    "DEFAULT_VALUE_TEST_CASE_CAPABILITIES",
    "DEFAULT_VALUE_TEST_CASE_KINDS",
    "ValueTestBackendSupport",
    "ValueTestCaseCapability",
    "ValueTestCoverageEntry",
    "ValueTestCoverageStatus",
    "ValueTestParityEntry",
    "HarnessPrimitiveNames",
    "ValueTestCasePlan",
    "ValueTestCaseRequirements",
    "ValueTestProfilePlan",
    "ValueTestProjectPlan",
)
