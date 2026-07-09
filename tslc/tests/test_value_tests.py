"""The generated value-correctness tests build and pass (opt-in `run_value_tests`).

Separate from `test_build_verify` (which only compiles the substrate): value testing builds
and runs the extra `tsl_values` binary, so it is gated behind ``run_value_tests=True`` and kept
to a focused primitive/profile set to bound its cost.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import shutil

import pytest

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.catalog.builder import CatalogBuilder
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import has_errors
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser
from tslc.value_tests.coverage import parity_gaps

pytestmark = pytest.mark.generated_build


def _assert_value_tests_ran(report, *, backends: tuple[str, ...]) -> None:
    assert report.skipped == (), report.skipped
    assert report.diagnostics == (), report.diagnostics
    steps = {
        (command.command.backend_id, command.command.profile_name, command.command.step)
        for command in report.commands
    }
    missing = [
        backend
        for backend in backends
        if not any(step_backend == backend and step == "test" for step_backend, _, step in steps)
    ]
    assert not missing, (missing, steps)


def test_golden_value_tests_build_and_pass(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Golden cases run against the generic software reference: vector results (`add`/`sub`/the
    # cross-lane `conflict`) read back as arrays, a mask result (`equal`) read as the reference's
    # integer-bitset mask.
    # `test_harness` also pulls in the vector<->array round-trip so the differential cases
    # (hardware avx2 vs the generic reference at the same lane count) are emitted and run.
    # This focused gate stays C++ only to keep the inner value-test smoke cheap; full-corpus Rust
    # value execution is covered below.
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=[
            "add",
            "sub",
            "conflict",
            "equal",
            "store",
            "hadd",
            "shift_left",
            "shift_left_imask",
        ],
        profiles=["avx2"],
        backends=("cpp",),
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    _assert_value_tests_ran(report, backends=("cpp",))


def test_neon_native_arithmetic_bitwise_extract_and_cast_value_tests_build_and_pass(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    """Native ARM coverage beyond `add`: arithmetic, bitwise, extract, and cast tests run."""

    zig = Path("/opt/zig/zig")
    qemu = shutil.which("qemu-aarch64")
    assert zig.exists(), "C++/Rust NEON QEMU value-test gate needs /opt/zig/zig"
    assert qemu is not None, "C++/Rust NEON QEMU value-test gate needs qemu-aarch64"

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["sub", "mul", "binary_and", "extract_value", "cast", "shift_left_imask"],
        profiles=["neon"],
        backends=("cpp", "rust"),
        test_harness=True,
        value_test_warnings=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None

    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(
        tmp_path,
        result.rendered.verify,
        cpp_compiler=(str(zig), "c++"),
        cpp_target="aarch64-linux-musl",
        qemu_aarch64_path=qemu,
        run_value_tests=True,
    )
    _assert_value_tests_ran(report, backends=("cpp", "rust"))


def test_shift_left_imask_value_tests_cover_x86_arm_and_oneapi(
    data_root: Path,
    machine_profiles_path: Path,
    tmp_path: Path,
) -> None:
    """`shift_left_imask` authored cases run on SDE/QEMU and build under icpx OneAPI."""

    zig = Path("/opt/zig/zig")
    qemu = shutil.which("qemu-aarch64")
    sde = Path("/opt/intel-sde/sde64")
    icpx = Path("/opt/intel/oneapi/compiler/2025.0/bin/icpx")
    assert sde.exists(), "x86 value-test gate needs /opt/intel-sde/sde64"
    assert zig.exists(), "ARM value-test gate needs /opt/zig/zig"
    assert qemu is not None, "ARM value-test gate needs qemu-aarch64"
    assert icpx.exists(), "OneAPI FPGA compile-mode gate needs icpx"

    x86_result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left_imask"],
        profiles=["avx2", "skylake-oneapi"],
        backends=("cpp",),
        test_harness=True,
        value_test_warnings=True,
    )
    assert x86_result.diagnostics == (), x86_result.diagnostics
    assert x86_result.rendered is not None
    coverage = x86_result.rendered.value_tests.coverage
    blocking = [
        entry
        for entry in coverage
        if entry.status
        in {"missing_authored_tests", "authored_unplanned", "backend_unsupported"}
    ]
    assert not blocking
    assert {
        (entry.backend_id, entry.profile_name, entry.case_name)
        for entry in coverage
        if entry.status == "emitted"
    } >= {
        ("cpp", "avx2", "shift_left_imask_ui32_basic"),
        ("cpp", "skylake-oneapi", "shift_left_imask_ui32_basic"),
        ("cpp", "avx2", "shift_left_imask_ui32_width"),
        ("cpp", "skylake-oneapi", "shift_left_imask_ui32_width"),
    }

    x86_root = tmp_path / "x86"
    write_report = write_artifacts(x86_result.artifacts, x86_root)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    x86_report = verify_project(
        x86_root,
        x86_result.rendered.verify,
        sde_path=str(sde),
        run_value_tests=True,
    )
    _assert_value_tests_ran(x86_report, backends=("cpp",))

    neon_result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["shift_left_imask"],
        profiles=["neon"],
        backends=("cpp",),
        test_harness=True,
        value_test_warnings=True,
    )
    assert neon_result.diagnostics == (), neon_result.diagnostics
    assert neon_result.rendered is not None
    neon_coverage = neon_result.rendered.value_tests.coverage
    blocking = [
        entry
        for entry in neon_coverage
        if entry.status
        in {"missing_authored_tests", "authored_unplanned", "backend_unsupported"}
    ]
    assert not blocking
    assert {
        (entry.backend_id, entry.profile_name, entry.case_name)
        for entry in neon_coverage
        if entry.status == "emitted"
    } >= {
        ("cpp", "neon", "shift_left_imask_ui32_basic"),
        ("cpp", "neon", "shift_left_imask_ui32_width"),
    }

    neon_root = tmp_path / "neon"
    write_report = write_artifacts(neon_result.artifacts, neon_root)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    neon_report = verify_project(
        neon_root,
        neon_result.rendered.verify,
        cpp_compiler=(str(zig), "c++"),
        cpp_target="aarch64-linux-musl",
        qemu_aarch64_path=qemu,
        run_value_tests=True,
    )
    _assert_value_tests_ran(neon_report, backends=("cpp",))


def test_value_full_corpus_avx2_coverage_is_complete(
    data_root: Path, machine_profiles_path: Path
) -> None:
    """Every planned full-corpus C++ AVX2 value case is emitted or compile-only."""

    result = _full_corpus_cpp_avx2(data_root, machine_profiles_path)
    assert result.rendered is not None
    plan = result.rendered.value_tests
    blocking = [
        entry
        for entry in plan.coverage
        if entry.status
        in {"missing_authored_tests", "authored_unplanned", "backend_unsupported"}
    ]
    assert not blocking
    store_mask_repr_unpacked = {
        entry.case_name
        for entry in plan.coverage
        if entry.primitive_name == "store_mask_repr"
        and entry.status == "emitted"
        and entry.case_name is not None
        and "_packed_false_" in entry.case_name
    }
    assert {
        "store_mask_repr_ui32_aligned_true_packed_false_mask_unpacked",
        "store_mask_repr_ui32_aligned_false_packed_false_mask_unpacked",
        "store_mask_repr_f32_aligned_true_packed_false_mask_unpacked",
    } <= store_mask_repr_unpacked
    unpacked_cases = {
        case.case_name: case
        for profile in plan.profiles
        for case in profile.cases
        if case.call_name == "store_mask_repr" and "_packed_false_" in case.case_name
    }
    assert unpacked_cases[
        "store_mask_repr_f32_aligned_true_packed_false_mask_unpacked"
    ].expected_type_tag == "ui32"
    assert any(entry.status == "compile_only_emitted" for entry in plan.coverage)
    assert len(plan.coverage) >= 1000


def test_value_full_corpus_avx2_rust_parity_inventory_is_explicit(
    data_root: Path, machine_profiles_path: Path
) -> None:
    """Rust and C++ full-corpus AVX2 value-test inventories are in parity."""

    result = _full_corpus_avx2(data_root, machine_profiles_path, backends=("cpp", "rust"))
    assert result.rendered is not None
    plan = result.rendered.value_tests
    status_counts = Counter((entry.backend_id, entry.status) for entry in plan.coverage)

    assert status_counts[("cpp", "missing_authored_tests")] == 0
    assert status_counts[("cpp", "authored_unplanned")] == 0
    assert status_counts[("cpp", "backend_unsupported")] == 0
    assert status_counts[("rust", "missing_authored_tests")] == 0
    assert status_counts[("rust", "authored_unplanned")] == 0
    assert status_counts[("rust", "backend_unsupported")] == 0
    assert status_counts[("rust", "compile_only_emitted")] == 1
    assert status_counts[("rust", "emitted")] == status_counts[("cpp", "emitted")]
    assert parity_gaps(plan.coverage, ("cpp", "rust")) == ()
    assert Counter(diagnostic.code for diagnostic in plan.diagnostics) == {}


def test_value_full_corpus_avx2_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    """Promoted value gate: the WHOLE corpus' golden + differential value tests pass on avx2
    (C++). A failure here is a real value regression (a lane mismatch) — or, rarely, a transient
    compiler failure under host load."""

    result = _full_corpus_cpp_avx2(data_root, machine_profiles_path)
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    # Fully green: no compile/configure errors and no value-test (ctest) warnings.
    assert report.diagnostics == (), report.diagnostics


def test_value_full_corpus_avx2_rust_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    """Rust runs the same full-corpus AVX2 authored value-test inventory as C++."""

    result = _full_corpus_avx2(data_root, machine_profiles_path, backends=("rust",))
    assert result.diagnostics == (), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    assert report.diagnostics == (), report.diagnostics


def _full_corpus_cpp_avx2(data_root: Path, machine_profiles_path: Path):
    result = _full_corpus_avx2(data_root, machine_profiles_path, backends=("cpp",))
    assert result.diagnostics == (), result.diagnostics
    return result


def _full_corpus_avx2(
    data_root: Path,
    machine_profiles_path: Path,
    *,
    backends: tuple[str, ...],
    ):
    documents = SourceLoader().load(tuple(sorted(data_root.rglob("*.tsl"))))
    catalog = CatalogBuilder().build(
        TslParser(load_default_tsl_grammar()).parse(documents.documents)
    ).catalog
    assert catalog is not None
    names = sorted({primitive.name for primitive in catalog.primitives})
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=names,
        profiles=["avx2"],
        backends=backends,
        test_harness=True,
        value_test_warnings=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    return result
