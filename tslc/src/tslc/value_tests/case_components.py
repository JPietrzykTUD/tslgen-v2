"""Typed components and case-kind requirements for generated value tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Literal

ExpectedArity = Literal["optional", "non_empty", "one", "lanes", "target_lanes"]
InputArity = Literal["optional", "non_empty", "one"]
MemoryStorage = Literal["packed", "unpacked"]
IndexStyle = Literal["register", "pointer"]


class ValueTestFact(Enum):
    """Typed facts a case renderer may require from a plan."""

    RESULT_KIND = auto()
    SCALAR_INPUT = auto()
    IMMEDIATE = auto()
    TARGET_LAYOUT = auto()
    TARGET_LANES = auto()
    INDEX_VALUE = auto()
    INDEX_STYLE = auto()
    INDEX_LANES = auto()
    MEMORY_LENGTH = auto()
    MEMORY_STORAGE = auto()
    TEXT_EXPECTED = auto()
    REPRESENTATION = auto()
    SCALABLE_RUNTIME = auto()
    SCALABLE_VALUE_HARNESS = auto()
    SCALABLE_MASK_CHECK = auto()
    SCALABLE_MASK_INPUTS = auto()
    SCALABLE_LOAD = auto()
    DIFFERENTIAL = auto()


@dataclass(frozen=True, slots=True)
class ValueTestCaseRequirements:
    """Typed renderer requirements for one value-test case kind."""

    expected: ExpectedArity = "optional"
    vector_inputs: InputArity = "optional"
    mask_inputs: InputArity = "optional"
    scalar_inputs: InputArity = "optional"
    required_facts: frozenset[ValueTestFact] = frozenset()
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
class ValueTestInputs:
    """Authored operands for one generated case."""

    vectors: tuple[tuple[str, ...], ...] = ()
    masks: tuple[str, ...] = ()
    scalar: str | None = None
    scalars: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValueTestExpectation:
    """Authored expected values or text output."""

    values: tuple[str, ...] = ()
    text: str | None = None


@dataclass(frozen=True, slots=True)
class ValueTestInvocation:
    """Facts needed to spell the primitive invocation."""

    result_kind: str | None = None
    param_kinds: tuple[str, ...] = ()
    axis_args: tuple[str, ...] = ()
    immediate: str | None = None
    generic_defaults: tuple[str, ...] = ()
    inferred_type_args: int = 0


@dataclass(frozen=True, slots=True)
class ValueTestTarget:
    """Optional result/storage type and lane layout."""

    type_tag: str | None = None
    base_spelling: str | None = None
    lanes: int | None = None

    def __post_init__(self) -> None:
        if (self.type_tag is None) != (self.base_spelling is None):
            raise ValueError(
                "value-test target type tag and spelling must be provided together"
            )
        if self.lanes is not None and self.lanes <= 0:
            raise ValueError("value-test target requires positive lanes")

    @property
    def has_layout(self) -> bool:
        return self.type_tag is not None and self.base_spelling is not None


@dataclass(frozen=True, slots=True)
class ValueTestIndex:
    """Immediate index and optional index-vector layout and call style."""

    value: str | None = None
    type_tag: str | None = None
    base_spelling: str | None = None
    lanes: int | None = None
    # How indexed-memory calls pass the index operand: loaded into an index
    # register or forwarded as a raw pointer. Decided once at planning.
    style: IndexStyle | None = None

    def __post_init__(self) -> None:
        if (self.type_tag is None) != (self.base_spelling is None):
            raise ValueError(
                "value-test index type tag and spelling must be provided together"
            )
        if self.lanes is not None and self.lanes <= 0:
            raise ValueError("value-test index requires positive lanes")
        if self.style is not None and self.style not in ("register", "pointer"):
            raise ValueError(
                "value-test index style must be 'register' or 'pointer'"
            )


@dataclass(frozen=True, slots=True)
class ValueTestMemory:
    """Buffer layout for memory-oriented cases."""

    buffer_offset: int = 0
    buffer_length: int | None = None
    source_offset: int = 0
    alignment: int | None = None
    # Whether the stored bytes are the packed integral-mask representation or
    # unpacked per-lane values. Decided once at planning; the primitive's real
    # result kind stays on the invocation.
    storage: MemoryStorage | None = None

    def __post_init__(self) -> None:
        if self.buffer_offset < 0 or self.source_offset < 0:
            raise ValueError("value-test memory offsets must be non-negative")
        if self.buffer_length is not None and self.buffer_length <= 0:
            raise ValueError("value-test memory buffer length must be positive")
        if self.alignment is not None and self.alignment <= 0:
            raise ValueError("value-test memory alignment must be positive")
        if self.storage is not None and self.storage not in ("packed", "unpacked"):
            raise ValueError(
                "value-test memory storage must be 'packed' or 'unpacked'"
            )


@dataclass(frozen=True, slots=True)
class ValueTestRepresentation:
    """Fixed-width extension representation and round-trip helpers."""

    source_extension: str
    target_extension: str | None = None
    from_array_name: str | None = None
    to_array_name: str | None = None

    def __post_init__(self) -> None:
        if not self.source_extension:
            raise ValueError("value-test representation requires source extension")

    @property
    def round_trip_ready(self) -> bool:
        return (
            self.target_extension is not None
            and self.from_array_name is not None
            and self.to_array_name is not None
        )


@dataclass(frozen=True, slots=True)
class ValueTestScalable:
    """Scalable-extension runtime and harness expressions."""

    source_extension: str
    runtime_lanes_expr: str
    mask_from_bits_exprs: tuple[str, ...] = ()
    mask_check_expr: str | None = None
    load_name: str | None = None
    store_name: str | None = None

    def __post_init__(self) -> None:
        if not self.source_extension or not self.runtime_lanes_expr:
            raise ValueError(
                "scalable value-test plan requires extension and runtime lanes"
            )

    @property
    def value_harness_ready(self) -> bool:
        return self.load_name is not None and self.store_name is not None


@dataclass(frozen=True, slots=True)
class ValueTestDifferential:
    """Hardware-vs-generic comparison harness, optionally with runtime fuzzing."""

    hardware_extension: str
    from_array_name: str
    to_array_name: str | None = None
    to_integral_name: str | None = None
    fuzz_seed: int | None = None
    fuzz_iterations: int = 0

    def __post_init__(self) -> None:
        if not self.hardware_extension or not self.from_array_name:
            raise ValueError(
                "differential value-test plan requires extension and from-array helper"
            )
        if self.fuzz_iterations < 0:
            raise ValueError(
                "differential value-test fuzz iterations must be non-negative"
            )
