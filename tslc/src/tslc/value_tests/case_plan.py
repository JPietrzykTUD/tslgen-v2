"""Validated generated value-test case plan."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.value_tests.case_capabilities import DEFAULT_VALUE_TEST_CASE_REQUIREMENTS
from tslc.value_tests.case_components import (
    InputArity,
    ValueTestCaseRequirements,
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestFact,
    ValueTestIndex,
    ValueTestInputs,
    ValueTestInvocation,
    ValueTestMemory,
    ValueTestRepresentation,
    ValueTestScalable,
    ValueTestTarget,
)


@dataclass(frozen=True, slots=True)
class ValueTestCasePlan:
    """One backend-specific generated value-test function, before text rendering."""

    CASE_REQUIREMENTS = DEFAULT_VALUE_TEST_CASE_REQUIREMENTS

    kind: str
    function_name: str
    case_name: str
    call_name: str
    type_tag: str
    base_spelling: str
    lanes: int
    inputs: ValueTestInputs = field(default_factory=ValueTestInputs)
    expectation: ValueTestExpectation = field(default_factory=ValueTestExpectation)
    invocation: ValueTestInvocation = field(default_factory=ValueTestInvocation)
    target: ValueTestTarget | None = None
    index: ValueTestIndex | None = None
    memory: ValueTestMemory | None = None
    representation: ValueTestRepresentation | None = None
    scalable: ValueTestScalable | None = None
    differential: ValueTestDifferential | None = None

    def __post_init__(self) -> None:
        self._validate_common_fields()
        try:
            requirements = self.CASE_REQUIREMENTS[self.kind]
        except KeyError as exc:
            raise ValueError(f"unsupported value-test case kind {self.kind!r}") from exc
        self._validate_required_facts(requirements)
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

    def _validate_required_facts(
        self,
        requirements: ValueTestCaseRequirements,
    ) -> None:
        for fact in sorted(requirements.required_facts, key=lambda item: item.name):
            if not self._has_fact(fact):
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    f"requires {fact.name.lower()}"
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
        mask_exprs = self.scalable.mask_from_bits_exprs if self.scalable else ()
        if mask_exprs and self.mask_inputs and len(mask_exprs) != len(self.mask_inputs):
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires one mask_from_bits expression per mask input"
            )

    def _validate_tuple_arity(self, field_name: str, arity: InputArity) -> None:
        values = {
            "vector_inputs": self.vector_inputs,
            "mask_inputs": self.mask_inputs,
            "scalar_inputs": self.scalar_inputs,
        }[field_name]
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
        if self.differential is None or self.differential.fuzz_seed is None:
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires fuzz_seed"
            )
        if self.differential.fuzz_iterations <= 0:
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

    def _has_fact(self, fact: ValueTestFact) -> bool:
        checks = {
            ValueTestFact.RESULT_KIND: self.invocation.result_kind is not None,
            ValueTestFact.SCALAR_INPUT: self.inputs.scalar is not None,
            ValueTestFact.IMMEDIATE: self.invocation.immediate is not None,
            ValueTestFact.TARGET_LAYOUT: (
                self.target is not None and self.target.has_layout
            ),
            ValueTestFact.TARGET_LANES: (
                self.target is not None and self.target.lanes is not None
            ),
            ValueTestFact.INDEX_VALUE: (
                self.index is not None and self.index.value is not None
            ),
            ValueTestFact.MEMORY_LENGTH: (
                self.memory is not None and self.memory.buffer_length is not None
            ),
            ValueTestFact.TEXT_EXPECTED: self.expectation.text is not None,
            ValueTestFact.REPRESENTATION: (
                self.representation is not None
                and self.representation.round_trip_ready
            ),
            ValueTestFact.SCALABLE_RUNTIME: self.scalable is not None,
            ValueTestFact.SCALABLE_VALUE_HARNESS: (
                self.scalable is not None and self.scalable.value_harness_ready
            ),
            ValueTestFact.SCALABLE_MASK_CHECK: (
                self.scalable is not None and self.scalable.mask_check_expr is not None
            ),
            ValueTestFact.SCALABLE_MASK_INPUTS: (
                self.scalable is not None
                and bool(self.scalable.mask_from_bits_exprs)
            ),
            ValueTestFact.SCALABLE_LOAD: (
                self.scalable is not None and self.scalable.load_name is not None
            ),
            ValueTestFact.DIFFERENTIAL: self.differential is not None,
        }
        return checks[fact]

    def _expected_error(self, expectation: str) -> str:
        return (
            f"value-test case {self.function_name!r} kind {self.kind!r} "
            f"requires expected to contain {expectation}"
        )

    # Renderers consume these projections; builders construct the typed
    # components above, so related facts retain one owner.
    @property
    def vector_inputs(self) -> tuple[tuple[str, ...], ...]:
        return self.inputs.vectors

    @property
    def mask_inputs(self) -> tuple[str, ...]:
        return self.inputs.masks

    @property
    def scalar_input(self) -> str | None:
        return self.inputs.scalar

    @property
    def scalar_inputs(self) -> tuple[str, ...]:
        return self.inputs.scalars

    @property
    def expected(self) -> tuple[str, ...]:
        return self.expectation.values

    @property
    def text_expected(self) -> str | None:
        return self.expectation.text

    @property
    def result_kind(self) -> str | None:
        return self.invocation.result_kind

    @property
    def param_kinds(self) -> tuple[str, ...]:
        return self.invocation.param_kinds

    @property
    def axis_args(self) -> tuple[str, ...]:
        return self.invocation.axis_args

    @property
    def immediate_value(self) -> str | None:
        return self.invocation.immediate

    @property
    def generic_defaults(self) -> tuple[str, ...]:
        return self.invocation.generic_defaults

    @property
    def expected_type_tag(self) -> str | None:
        return self.target.type_tag if self.target is not None else None

    @property
    def target_base_spelling(self) -> str | None:
        return self.target.base_spelling if self.target is not None else None

    @property
    def target_lanes(self) -> int | None:
        return self.target.lanes if self.target is not None else None

    @property
    def index_value(self) -> str | None:
        return self.index.value if self.index is not None else None

    @property
    def index_type_tag(self) -> str | None:
        return self.index.type_tag if self.index is not None else None

    @property
    def index_base_spelling(self) -> str | None:
        return self.index.base_spelling if self.index is not None else None

    @property
    def index_lanes(self) -> int | None:
        return self.index.lanes if self.index is not None else None

    @property
    def buffer_offset(self) -> int:
        return self.memory.buffer_offset if self.memory is not None else 0

    @property
    def buffer_length(self) -> int | None:
        return self.memory.buffer_length if self.memory is not None else None

    @property
    def source_offset(self) -> int:
        return self.memory.source_offset if self.memory is not None else 0

    @property
    def alignment(self) -> int | None:
        return self.memory.alignment if self.memory is not None else None

    @property
    def source_extension(self) -> str | None:
        if self.scalable is not None:
            return self.scalable.source_extension
        if self.representation is not None:
            return self.representation.source_extension
        return None

    @property
    def target_extension(self) -> str | None:
        return (
            self.representation.target_extension
            if self.representation is not None
            else None
        )

    @property
    def from_array_name(self) -> str | None:
        if self.differential is not None:
            return self.differential.from_array_name
        if self.representation is not None:
            return self.representation.from_array_name
        return None

    @property
    def to_array_name(self) -> str | None:
        if self.differential is not None:
            return self.differential.to_array_name
        if self.representation is not None:
            return self.representation.to_array_name
        return None

    @property
    def to_integral_name(self) -> str | None:
        return self.differential.to_integral_name if self.differential else None

    @property
    def hardware_extension(self) -> str | None:
        return self.differential.hardware_extension if self.differential else None

    @property
    def runtime_lanes_expr(self) -> str | None:
        return self.scalable.runtime_lanes_expr if self.scalable is not None else None

    @property
    def mask_from_bits_exprs(self) -> tuple[str, ...]:
        return self.scalable.mask_from_bits_exprs if self.scalable is not None else ()

    @property
    def mask_check_expr(self) -> str | None:
        return self.scalable.mask_check_expr if self.scalable is not None else None

    @property
    def load_name(self) -> str | None:
        return self.scalable.load_name if self.scalable is not None else None

    @property
    def store_name(self) -> str | None:
        return self.scalable.store_name if self.scalable is not None else None

    @property
    def fuzz_seed(self) -> int | None:
        return self.differential.fuzz_seed if self.differential is not None else None

    @property
    def fuzz_iterations(self) -> int:
        return self.differential.fuzz_iterations if self.differential is not None else 0

