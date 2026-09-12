"""Test-owned semantic inventory for whole-array algorithm conformance."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from tslc.backend.algorithm_surface import AlgorithmCallableForm


class AlgorithmConformanceAxis(StrEnum):
    EMPTY_RANGE = "empty_range"
    SUBVECTOR_RANGE = "subvector_range"
    EXACT_VECTOR_RANGE = "exact_vector_range"
    MULTI_VECTOR_TAIL = "multi_vector_tail"
    ORDINARY_CHECKED_PAIR = "ordinary_checked_pair"
    PERMITTED_ALIAS = "permitted_alias"
    REJECTED_ALIAS = "rejected_alias"
    CHECKED_FAILURE = "checked_failure"
    UNCHANGED_OUTPUT = "unchanged_output"
    ZERO_KERNEL_INVOCATIONS = "zero_kernel_invocations"
    MASK_LAYOUTS = "mask_layouts"
    SELECTED_FORM = "selected_form"
    INDEX_FORM = "index_form"
    SCALED_FORM = "scaled_form"
    RUST_UNSAFE_CALL = "rust_unsafe_call"


REQUIRED_CONFORMANCE_AXES = frozenset(AlgorithmConformanceAxis)


@dataclass(frozen=True, slots=True)
class AlgorithmConformanceCase:
    """One target-neutral behavior case keyed by a shared callable form."""

    form_name: str
    example_name: str
    expected_exit_code: int = 0
    axes: frozenset[AlgorithmConformanceAxis] = frozenset()

    def __post_init__(self) -> None:
        if not self.form_name or not self.example_name:
            raise ValueError("algorithm conformance cases require exact identities")
        if self.expected_exit_code != 0:
            raise ValueError("algorithm conformance examples must succeed")


@dataclass(frozen=True, slots=True)
class AlgorithmBehaviorCase:
    """Shared inputs and expected report for paired backend adapters."""

    form_name: str
    lengths: tuple[int, ...]
    input_values: tuple[int, ...]
    sentinel: int
    expected_error: str

    def __post_init__(self) -> None:
        if not self.form_name or not self.lengths or not self.input_values:
            raise ValueError("algorithm behavior cases require complete inputs")
        if self.lengths[-1] != len(self.input_values):
            raise ValueError("the final behavior length must cover every input")
        if any(length < 0 or length > len(self.input_values) for length in self.lengths):
            raise ValueError("algorithm behavior lengths must be represented")

    @property
    def expected_report(self) -> str:
        values = ",".join(str(value) for value in self.input_values)
        return (
            f"values={values};alias={values};failure={self.expected_error};"
            f"unchanged=true;failure_calls=0"
        )


def _case(
    form_name: str,
    example_name: str,
    *axes: AlgorithmConformanceAxis,
) -> AlgorithmConformanceCase:
    return AlgorithmConformanceCase(
        form_name,
        example_name,
        axes=frozenset(axes),
    )


ALGORITHM_CONFORMANCE_CASES = (
    _case(
        "integral_mask_chunk_count",
        "predicate_operator",
        AlgorithmConformanceAxis.EMPTY_RANGE,
    ),
    _case("native_mask_chunk_count", "native_mask_operator"),
    _case(
        "mask_chunk_count",
        "masked_selection_operator",
        AlgorithmConformanceAxis.MASK_LAYOUTS,
    ),
    _case("byte_mask_count", "byte_mask_operator"),
    _case("bit_mask_count", "bit_mask_operator"),
    _case(
        "for_each_chunk",
        "chunk_operator",
        AlgorithmConformanceAxis.SUBVECTOR_RANGE,
        AlgorithmConformanceAxis.EXACT_VECTOR_RANGE,
        AlgorithmConformanceAxis.MULTI_VECTOR_TAIL,
    ),
    _case("predicate_unary", "predicate_operator"),
    _case("predicate_unary_mask_layout", "predicate_operator"),
    _case("predicate_binary", "predicate_operator"),
    _case("predicate_binary_mask_layout", "native_mask_operator"),
    _case("count_unary", "count_operator"),
    _case("count_binary", "count_operator"),
    _case("count_masked_unary", "count_operator"),
    _case("count_masked_unary_mask_layout", "count_operator"),
    _case("count_masked_binary", "count_operator"),
    _case("count_masked_binary_mask_layout", "count_operator"),
    _case("count_selected_unary", "count_operator"),
    _case("count_selected_binary", "count_operator"),
    _case("select_unary", "selection_operator"),
    _case("select_binary", "selection_operator"),
    _case("select_masked_unary", "masked_selection_operator"),
    _case("select_masked_unary_mask_layout", "masked_selection_operator"),
    _case("select_masked_binary", "masked_selection_operator"),
    _case("select_masked_binary_mask_layout", "masked_selection_operator"),
    _case(
        "select_indices_unary",
        "selection_vector_operator",
        AlgorithmConformanceAxis.INDEX_FORM,
    ),
    _case("select_indices_binary", "selection_vector_operator"),
    _case("select_masked_indices_unary", "selection_vector_operator"),
    _case("select_masked_indices_unary_mask_layout", "selection_vector_operator"),
    _case("select_masked_indices_binary", "selection_vector_operator"),
    _case("select_masked_indices_binary_mask_layout", "selection_vector_operator"),
    _case("select_selected_indices_unary", "selected_refinement_operator"),
    _case("select_selected_indices_binary", "selected_refinement_operator"),
    _case(
        "transform_unary",
        "unary_operator",
        AlgorithmConformanceAxis.ORDINARY_CHECKED_PAIR,
        AlgorithmConformanceAxis.PERMITTED_ALIAS,
    ),
    _case(
        "transform_binary",
        "binary_operator",
        AlgorithmConformanceAxis.REJECTED_ALIAS,
        AlgorithmConformanceAxis.CHECKED_FAILURE,
        AlgorithmConformanceAxis.UNCHANGED_OUTPUT,
        AlgorithmConformanceAxis.ZERO_KERNEL_INVOCATIONS,
    ),
    _case(
        "transform_selected_unary",
        "selected_transform_operator",
        AlgorithmConformanceAxis.SELECTED_FORM,
        AlgorithmConformanceAxis.SCALED_FORM,
        AlgorithmConformanceAxis.RUST_UNSAFE_CALL,
    ),
    _case("transform_selected_binary", "selected_transform_operator"),
    _case("transform_where_unary", "where_operator"),
    _case("transform_where_unary_mask_layout", "where_operator"),
    _case("transform_where_binary", "where_operator"),
    _case("transform_where_binary_mask_layout", "where_operator"),
    _case("transform_masked_unary", "masked_operator"),
    _case("transform_masked_unary_mask_layout", "masked_operator"),
    _case("transform_masked_binary", "masked_operator"),
    _case("transform_masked_binary_mask_layout", "native_mask_operator"),
    _case("consume_unary", "consume_operator"),
    _case("consume_binary", "consume_operator"),
    _case("consume_masked_unary", "masked_consume_operator"),
    _case("consume_masked_binary", "masked_consume_operator"),
    _case("consume_selected_unary", "selected_aggregate_consume_operator"),
    _case("consume_selected_binary", "selected_aggregate_consume_operator"),
    _case("aggregate_unary", "aggregation_operator"),
    _case("aggregate_binary", "aggregation_operator"),
    _case("aggregate_masked_unary", "masked_aggregation_operator"),
    _case("aggregate_masked_binary", "masked_aggregation_operator"),
    _case("aggregate_selected_unary", "selected_aggregate_consume_operator"),
    _case("aggregate_selected_binary", "selected_aggregate_consume_operator"),
)


SHARED_ALGORITHM_BEHAVIOR_CASE = AlgorithmBehaviorCase(
    form_name="transform_unary",
    lengths=(0, 3, 4, 10),
    input_values=(2, -1, 4, 7, -3, 8, 0, 5, -6, 9),
    sentinel=8675309,
    expected_error="insufficient_input",
)


def conformance_issues(
    cases: Sequence[AlgorithmConformanceCase],
    forms: Sequence[AlgorithmCallableForm],
    *,
    cpp_expected: Iterable[str] = (),
    cpp_witnessed: Iterable[str] = (),
    rust_expected: Iterable[str] = (),
    rust_witnessed: Iterable[str] = (),
) -> tuple[str, ...]:
    """Report exact missing/extra form, axis, and backend witness identities."""

    case_names = tuple(case.form_name for case in cases)
    expected_names = {form.name for form in forms}
    issues = {
        *(f"duplicate-form:{name}" for name in case_names if case_names.count(name) > 1),
        *(f"missing-form:{name}" for name in expected_names - set(case_names)),
        *(f"unknown-form:{name}" for name in set(case_names) - expected_names),
    }
    covered_axes = frozenset(axis for case in cases for axis in case.axes)
    issues.update(
        f"missing-axis:{axis.value}"
        for axis in REQUIRED_CONFORMANCE_AXES - covered_axes
    )
    for backend, expected, witnessed in (
        ("cpp", set(cpp_expected), set(cpp_witnessed)),
        ("rust", set(rust_expected), set(rust_witnessed)),
    ):
        issues.update(
            f"missing-witness:{backend}:{identity}"
            for identity in expected - witnessed
        )
        issues.update(
            f"unknown-witness:{backend}:{identity}"
            for identity in witnessed - expected
        )
    return tuple(sorted(issues))


__all__ = (
    "ALGORITHM_CONFORMANCE_CASES",
    "REQUIRED_CONFORMANCE_AXES",
    "SHARED_ALGORITHM_BEHAVIOR_CASE",
    "AlgorithmBehaviorCase",
    "AlgorithmConformanceAxis",
    "AlgorithmConformanceCase",
    "conformance_issues",
)
