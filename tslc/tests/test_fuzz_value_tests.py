"""Tests for differential-fuzz value-test generation (the generic-oracle fuzzer)."""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project
from tslc.value_tests._case_conversion import FUZZ_ITERATIONS, _fuzz_seed
from tslc.value_tests._render_cpp_conversion import _differential_fuzz
from tslc.value_tests.model import ValueTestCasePlan


def _plan(**kwargs) -> ValueTestCasePlan:
    base = dict(
        kind="differential_fuzz",
        function_name="fuzz_diff_avx2_add_si32",
        case_name="add:fuzz",
        call_name="add",
        type_tag="si32",
        base_spelling="int32_t",
        lanes=8,
        result_kind="v",
        param_kinds=("v", "v"),
        hardware_extension="avx2",
        from_array_name="from_array",
        to_array_name="to_array",
        to_integral_name="to_integral",
        fuzz_seed=12345,
        fuzz_iterations=256,
    )
    base.update(kwargs)
    return ValueTestCasePlan(**base)


# --------------------------------------------------------------------------- seed


def test_fuzz_seed_is_stable_nonzero_and_distinct() -> None:
    assert _fuzz_seed("fuzz_diff_avx2_add_si32") == _fuzz_seed("fuzz_diff_avx2_add_si32")
    assert _fuzz_seed("a") != _fuzz_seed("b")
    assert _fuzz_seed("a") != 0  # xorshift must not start at zero


# --------------------------------------------------------------------------- renderer


def test_fuzz_renderer_wires_oracle_and_detector() -> None:
    code = _differential_fuzz(_plan())
    # hardware path and generic oracle, same inputs
    assert "using Hw = tsl::simd<int32_t, tsl::avx2>;" in code
    assert "using Ref = tsl::simd<int32_t, tsl::generic<8>>;" in code
    assert "tsl::add<Hw>(" in code and "tsl::add<Ref>(" in code
    # runtime PRNG loop feeding both paths
    assert "for (std::size_t iter = 0; iter < 256" in code
    assert "tsl::test::fuzz_next<int32_t>(rng)" in code
    # the detector and a failing return that prints a reproducer
    assert 'tsl::test::check_match<int32_t>("fuzz_diff_avx2_add_si32"' in code
    assert "reproduce: fuzz iter" in code
    assert "return 1;" in code and "return 0;" in code


def test_fuzz_renderer_mask_result_uses_to_integral() -> None:
    code = _differential_fuzz(_plan(result_kind="m", call_name="equal", param_kinds=("v", "v")))
    assert "tsl::to_integral<Hw>(" in code
    assert "tsl::test::check_mask_match_for<Hw>(" in code
    assert "typename Ref::mask_type ref =" in code


def test_fuzz_renderer_handles_unary_arity() -> None:
    code = _differential_fuzz(_plan(call_name="abs", param_kinds=("v",)))
    assert "hin0" in code and "hin1" not in code  # exactly one input array


# --------------------------------------------------------------------------- integration


def _values_source(data_root: Path, machine_profiles_path: Path, *, fuzz: bool) -> str:
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add"],
        profiles=["avx2"],
        backends=["cpp"],
        test_harness=True,
        value_test_fuzz=fuzz,
    )
    assert not [d for d in result.diagnostics if d.severity == "error"]
    values = [
        a.content
        for a in result.artifacts.artifacts
        if a.logical_path.endswith(".cpp") and "values" in a.logical_path
    ]
    assert values
    return values[0]


def test_fuzz_cases_emitted_only_when_enabled(
    data_root: Path, machine_profiles_path: Path
) -> None:
    with_fuzz = _values_source(data_root, machine_profiles_path, fuzz=True)
    without_fuzz = _values_source(data_root, machine_profiles_path, fuzz=False)
    assert "fuzz_diff_avx2_add_si32" in with_fuzz
    assert "fuzz_next" in with_fuzz
    # default value-test generation is unchanged — no fuzz leaks in
    assert "fuzz_diff" not in without_fuzz
    assert "fuzz_next" not in without_fuzz


def test_fuzz_covers_every_arith_type(data_root: Path, machine_profiles_path: Path) -> None:
    source = _values_source(data_root, machine_profiles_path, fuzz=True)
    for tag in ("si8", "si16", "si32", "si64", "ui8", "ui16", "ui32", "ui64", "f32", "f64"):
        assert f"fuzz_diff_avx2_add_{tag}" in source


def test_fuzz_iterations_constant_is_reasonable() -> None:
    assert FUZZ_ITERATIONS >= 64
