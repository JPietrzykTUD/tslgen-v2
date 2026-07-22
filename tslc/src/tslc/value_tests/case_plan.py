"""Validated generated value-test case plan."""

from __future__ import annotations

from dataclasses import dataclass, field

from tslc.value_tests.case_capabilities import DEFAULT_VALUE_TEST_CASE_REQUIREMENTS
from tslc.value_tests.case_components import (
    InputArity,
    ValueTestCaseRequirements,
    ValueTestDifferential,
    ValueTestExpectation,
    ValueTestFailure,
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
    failure: ValueTestFailure | None = None
    # Optional generated C++ header group needed by this case (for example
    # ``clang`` for compiler-builtin overlay extensions). The runner guards
    # such cases and the build emits a matching opt-in value-test target.
    header_group: str | None = None
    # Backend compiler capabilities required by this case. C++ renders these
    # through feature-test guards so an optional extension representation does
    # not disable other cases in the same header group.
    required_compiler_features: tuple[str, ...] = ()

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
        self._validate_differential_helpers(requirements)

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
        if self.header_group is not None and not self.header_group:
            raise ValueError(
                f"value-test case {self.function_name!r} header_group must be non-empty"
            )
        if any(not feature for feature in self.required_compiler_features):
            raise ValueError(
                f"value-test case {self.function_name!r} compiler features must be non-empty"
            )
        if tuple(sorted(set(self.required_compiler_features))) != (
            self.required_compiler_features
        ):
            raise ValueError(
                f"value-test case {self.function_name!r} compiler features must be "
                "sorted and unique"
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
        expected_len = len(self.expectation.values)
        if requirements.expected == "optional":
            return
        if requirements.expected == "non_empty" and expected_len == 0:
            raise ValueError(self._expected_error("at least one value"))
        if requirements.expected == "one" and expected_len != 1:
            raise ValueError(self._expected_error("exactly one value"))
        if requirements.expected == "lanes" and expected_len != self.lanes:
            raise ValueError(self._expected_error(f"{self.lanes} lane values"))
        if requirements.expected == "target_lanes":
            target_lanes = self.target.lanes if self.target is not None else None
            if target_lanes is None:
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    "requires target_lanes"
                )
            if expected_len != target_lanes:
                raise ValueError(
                    self._expected_error(f"{target_lanes} target lane values")
                )

    def _validate_inputs(self, requirements: ValueTestCaseRequirements) -> None:
        self._validate_tuple_arity("vector_inputs", requirements.vector_inputs)
        self._validate_tuple_arity("mask_inputs", requirements.mask_inputs)
        self._validate_tuple_arity("scalar_inputs", requirements.scalar_inputs)
        if requirements.vector_inputs_match_lanes:
            for index, values in enumerate(self.inputs.vectors):
                if len(values) != self.lanes:
                    raise ValueError(
                        f"value-test case {self.function_name!r} kind {self.kind!r} "
                        f"requires vector_inputs[{index}] to have {self.lanes} values"
                    )
        mask_bits = self.scalable.mask_bits if self.scalable else ()
        if (
            mask_bits
            and self.inputs.masks
            and len(mask_bits) != len(self.inputs.masks)
        ):
            raise ValueError(
                f"value-test case {self.function_name!r} kind {self.kind!r} "
                "requires one mask-bits value per mask input"
            )

    def _validate_tuple_arity(self, field_name: str, arity: InputArity) -> None:
        values = {
            "vector_inputs": self.inputs.vectors,
            "mask_inputs": self.inputs.masks,
            "scalar_inputs": self.inputs.scalars,
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

    def _validate_differential_helpers(
        self,
        requirements: ValueTestCaseRequirements,
    ) -> None:
        if ValueTestFact.DIFFERENTIAL not in requirements.required_facts:
            return
        differential = self.differential
        if differential is None:
            return
        if self.invocation.result_kind == "m":
            if differential.to_integral_name is None:
                raise ValueError(
                    f"value-test case {self.function_name!r} kind {self.kind!r} "
                    "requires to_integral_name for mask results"
                )
            return
        if differential.to_array_name is None:
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
            ValueTestFact.INDEX_STYLE: (
                self.index is not None and self.index.style is not None
            ),
            ValueTestFact.INDEX_LANES: (
                self.index is not None and self.index.lanes is not None
            ),
            ValueTestFact.MEMORY_LENGTH: (
                self.memory is not None and self.memory.buffer_length is not None
            ),
            ValueTestFact.MEMORY_STORAGE: (
                self.memory is not None and self.memory.storage is not None
            ),
            ValueTestFact.TEXT_EXPECTED: self.expectation.text is not None,
            ValueTestFact.REPRESENTATION: (
                self.representation is not None
                and self.representation.round_trip_ready
            ),
            ValueTestFact.REPRESENTATION_LAYOUT: (
                self.representation is not None
                and self.representation.has_layout
            ),
            ValueTestFact.SCALABLE_RUNTIME: self.scalable is not None,
            ValueTestFact.SCALABLE_VALUE_HARNESS: (
                self.scalable is not None and self.scalable.value_harness_ready
            ),
            ValueTestFact.SCALABLE_MASK_CHECK: (
                self.scalable is not None
                and self.scalable.mask_check_template is not None
            ),
            ValueTestFact.SCALABLE_MASK_INPUTS: (
                self.scalable is not None and bool(self.scalable.mask_bits)
            ),
            ValueTestFact.SCALABLE_LOAD: (
                self.scalable is not None and self.scalable.load_name is not None
            ),
            ValueTestFact.DIFFERENTIAL: self.differential is not None,
            ValueTestFact.FAILURE: self.failure is not None,
        }
        return checks[fact]

    def _expected_error(self, expectation: str) -> str:
        return (
            f"value-test case {self.function_name!r} kind {self.kind!r} "
            f"requires expected to contain {expectation}"
        )
