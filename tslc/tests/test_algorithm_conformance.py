"""Completeness ratchets for executable whole-array algorithm evidence."""

from __future__ import annotations

from pathlib import Path

from tslc.backend.algorithm_surface import (
    ALGORITHM_CALLABLE_FORMS,
    AlgorithmArity,
    AlgorithmMaskForm,
    AlgorithmResultKind,
    AlgorithmSemanticFamily,
    AlgorithmShape,
    AlgorithmSurfaceFamily,
)

from algorithm_conformance import (
    ALGORITHM_CONFORMANCE_CASES,
    SHARED_ALGORITHM_BEHAVIOR_CASE,
    AlgorithmConformanceAxis,
    conformance_issues,
)
from algorithm_conformance_cpp import (
    cpp_algorithm_compile_identities,
    render_cpp_algorithm_behavior,
    render_cpp_algorithm_compile_witness,
)
from algorithm_conformance_rust import (
    render_rust_algorithm_behavior,
    render_rust_algorithm_compile_witness,
    rust_algorithm_compile_identities,
)


def test_conformance_inventory_covers_every_shared_form_exactly() -> None:
    assert conformance_issues(
        ALGORITHM_CONFORMANCE_CASES,
        ALGORITHM_CALLABLE_FORMS,
    ) == ()


def test_synthetic_stable_form_reports_its_exact_missing_case() -> None:
    synthetic = AlgorithmSurfaceFamily(
        "synthetic_transform_extra_unary",
        AlgorithmSemanticFamily.TRANSFORM,
        AlgorithmArity.UNARY,
        AlgorithmShape.PLAIN,
        AlgorithmResultKind.VOID,
        has_contract=True,
    ).callable_forms[0]

    rust_witnessed = rust_algorithm_compile_identities()
    synthetic_identity = (
        "crate::profile::algo::synthetic_transform_extra_unary#algorithm"
    )
    issues = conformance_issues(
        ALGORITHM_CONFORMANCE_CASES,
        (*ALGORITHM_CALLABLE_FORMS, synthetic),
        rust_expected=rust_witnessed | {synthetic_identity},
        rust_witnessed=rust_witnessed,
    )

    assert "missing-form:synthetic_transform_extra_unary" in issues
    assert f"missing-witness:rust:{synthetic_identity}" in issues


def test_critical_case_deletions_report_the_exact_uncovered_axis() -> None:
    representatives = {
        "integral_mask_chunk_count": AlgorithmConformanceAxis.EMPTY_RANGE,
        "for_each_chunk": AlgorithmConformanceAxis.MULTI_VECTOR_TAIL,
        "mask_chunk_count": AlgorithmConformanceAxis.MASK_LAYOUTS,
        "transform_unary": AlgorithmConformanceAxis.ORDINARY_CHECKED_PAIR,
        "transform_binary": AlgorithmConformanceAxis.CHECKED_FAILURE,
        "select_indices_unary": AlgorithmConformanceAxis.INDEX_FORM,
        "transform_selected_unary": AlgorithmConformanceAxis.SCALED_FORM,
    }

    for form_name, axis in representatives.items():
        cases = tuple(
            case
            for case in ALGORITHM_CONFORMANCE_CASES
            if case.form_name != form_name
        )
        issues = conformance_issues(cases, ALGORITHM_CALLABLE_FORMS)
        assert f"missing-form:{form_name}" in issues
        assert f"missing-axis:{axis.value}" in issues


def test_every_case_names_a_paired_cpp_and_rust_example() -> None:
    root = Path(__file__).parents[2]
    for case in ALGORITHM_CONFORMANCE_CASES:
        assert case.expected_exit_code == 0
        assert (root / "examples" / "cpp" / f"{case.example_name}.cpp").is_file()
        assert (
            root
            / "examples"
            / "rust"
            / "src"
            / "bin"
            / f"{case.example_name}.rs"
        ).is_file()


def test_paired_examples_are_wired_into_the_executable_consumer_gate() -> None:
    root = Path(__file__).parents[2]
    cpp_project = (root / "examples" / "cpp" / "CMakeLists.txt").read_text(
        encoding="utf-8"
    )
    rust_project = (root / "examples" / "rust" / "Cargo.toml").read_text(
        encoding="utf-8"
    )
    consumer_gate = (
        root / "supplementary" / "ci" / "verify_generated_consumers.sh"
    ).read_text(encoding="utf-8")

    for example_name in {
        case.example_name for case in ALGORITHM_CONFORMANCE_CASES
    }:
        assert f"add_test(NAME {example_name} COMMAND {example_name})" in cpp_project
        assert f'name = "{example_name}"' in rust_project
        assert f"--bin {example_name}" in consumer_gate


def test_backend_adapters_witness_every_exact_stable_algorithm_identity() -> None:
    cpp_source, cpp_witnessed = render_cpp_algorithm_compile_witness()
    rust_source, rust_witnessed = render_rust_algorithm_compile_witness()
    cpp_expected = cpp_algorithm_compile_identities()
    rust_expected = rust_algorithm_compile_identities()
    assert len(cpp_witnessed) == len(
        cpp_source.split("// witness: ")
    ) - 1
    assert len(rust_witnessed) == len(
        rust_source.split("// witness: ")
    ) - 1

    assert conformance_issues(
        ALGORITHM_CONFORMANCE_CASES,
        ALGORITHM_CALLABLE_FORMS,
        cpp_expected=cpp_expected,
        cpp_witnessed=cpp_witnessed,
        rust_expected=rust_expected,
        rust_witnessed=rust_witnessed,
    ) == ()
    assert cpp_source.count("// witness: ") == len(cpp_expected)
    assert rust_source.count("// witness: ") == len(rust_expected)
    assert "profile::algo::mask_chunk_count::<_, " in rust_source
    for name in ("transform_unary", "transform_unary_raw"):
        assert f"unsafe {{ profile::algo::{name}::<" in rust_source


def test_deleting_an_exact_backend_witness_reports_its_identity() -> None:
    expected = cpp_algorithm_compile_identities()
    missing = "tsl::algo::transform_unary_checked#policy"
    assert missing in expected

    issues = conformance_issues(
        ALGORITHM_CONFORMANCE_CASES,
        ALGORITHM_CALLABLE_FORMS,
        cpp_expected=expected,
        cpp_witnessed=expected - {missing},
    )

    assert f"missing-witness:cpp:{missing}" in issues


def test_behavior_adapters_consume_one_shared_expected_result() -> None:
    case = SHARED_ALGORITHM_BEHAVIOR_CASE
    cpp = render_cpp_algorithm_behavior(case)
    rust = render_rust_algorithm_behavior(case)

    assert case.lengths == (0, 3, 4, 10)
    assert case.expected_report.endswith(
        "failure=insufficient_input;unchanged=true;failure_calls=0"
    )
    assert cpp == render_cpp_algorithm_behavior(case)
    assert rust == render_rust_algorithm_behavior(case)
    assert "transform_unary_checked" in cpp
    assert "transform_unary_checked" in rust
    assert "unsafe {\n        profile::algo::transform_unary(" in rust
