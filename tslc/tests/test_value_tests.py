"""The generated value-correctness tests build and pass (opt-in `run_value_tests`).

Separate from `test_build_verify` (which only compiles the substrate): value testing builds
and runs the extra `tsl_values` binary, so it is gated behind ``run_value_tests=True`` and kept
to a focused primitive/profile set to bound its cost.
"""

from __future__ import annotations

from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.model import Catalog
from tslc.catalog.signatures import parse_signature
from tslc.diagnostics import has_errors
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser


def _value_test_shape_handled(signature: str) -> bool:
    """Whether the value-test generator emits cases for a primitive of this signature today:
    a vector/mask result with all-vector params (golden + differential), a masked value op
    (one mask param + vectors), or a `store(ptr, v)`."""

    shape = parse_signature(signature)
    if shape is None:
        return False
    result, params = shape.result_kind, tuple(shape.param_kinds)
    if result in ("v", "m") and all(kind == "v" for kind in params):
        return True
    if result == "v" and params.count("m") == 1 and all(k in ("m", "v") for k in params):
        return True
    if result == "s" and params == ("v",):  # horizontal reduction
        return True
    if result == "v" and params == ("ptr",):  # load
        return True
    if result == "m" and len(params) >= 1 and all(k == "m" for k in params):  # mask logic
        return True
    if result == "s[]" and params == ("v",):  # to_array
        return True
    if result == "v" and params == ("s",):  # set1 broadcast
        return True
    if result == "v" and params == ("lanes<s>",):  # set lane-list construction
        return True
    if result == "v" and "sImm" in params and all(k in ("v", "sImm") for k in params):
        return True  # immediate op (mul_imm / shift-imm)
    if result == "v" and params == ("m",):  # to_vector (mask -> vector)
        return True
    return result == "void" and params == ("ptr", "v")


def test_golden_value_tests_build_and_pass(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    # Golden cases run against the generic software reference: vector results (`add`/`sub`/the
    # cross-lane `conflict`) read back as arrays, a mask result (`equal`) read as the reference's
    # integer-bitset mask.
    # `test_harness` also pulls in the vector<->array round-trip so the differential cases
    # (hardware avx2 vs the generic reference at the same lane count) are emitted and run.
    # C++ only: Rust value verification is deferred (host-flaky toolchain, and Rust debug builds
    # panic on integer overflow where C++ wraps — a parity finding still to resolve).
    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=["add", "sub", "conflict", "equal", "store", "hadd", "shift_left"],
        profiles=["avx2"],
        backends=("cpp",),
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    # No compile/configure errors, and (since the golden tests pass) no value-test warnings.
    assert report.diagnostics == (), report.diagnostics
    # The value tests actually ran (the ctest step is present), so a green result is meaningful
    # rather than vacuous.
    cpp_steps = {c.command.step for c in report.commands if c.command.backend_id == "cpp"}
    if cpp_steps:  # cpp toolchain available (else the backend was skipped)
        assert "test" in cpp_steps, cpp_steps
        assert "build-values" in cpp_steps, cpp_steps


def test_value_test_coverage_gaps(catalog: Catalog) -> None:
    """Coverage diagnostic: which primitives carry authored `tests` but no value test is yet
    generated (an unhandled shape — gather/scatter, conversions, reductions, variadic, …). The
    list is printed so gaps stay visible; the covered baseline guards against regressions."""

    with_tests: set[str] = set()
    covered: set[str] = set()
    for primitive in catalog.primitives:
        if not primitive.tests:
            continue
        with_tests.add(primitive.name)
        if primitive.result_target is None and _value_test_shape_handled(primitive.signature):
            covered.add(primitive.name)  # a name is covered if any variant's shape is handled
        elif primitive.result_target is not None:
            # Every representation change now has a value-test handler:
            #  - BASE-dim against the generic reference: `convert_up`/`convert_down`
            #    (monomorphized, windowed) and `cast`/`reinterpret` (lane-preserving cases).
            #  - EXTENSION-dim golden vs the hardware spec via the round-trip harness:
            #    `extract`/`insert` (emitted where both extensions' harness is present).
            covered.add(primitive.name)
    gaps = with_tests - covered
    print(f"\nvalue-test coverage: {len(covered)}/{len(with_tests)} primitives covered; "
          f"{len(gaps)} not yet generated (unhandled shapes): {sorted(gaps)}")
    # Regression guard: the shapes we implemented stay covered.
    assert {
        "add", "equal", "conflict", "store",
        "set",
        "convert_up", "convert_down", "cast", "reinterpret", "extract", "insert",
    } <= covered
    assert len(covered) >= 20, sorted(covered)


def test_value_full_corpus_avx2_builds(
    data_root: Path, machine_profiles_path: Path, tmp_path: Path
) -> None:
    """Promoted value gate: the WHOLE corpus' golden + differential value tests pass on avx2
    (C++). Rust is omitted while its toolchain is host-flaky. A failure here is a real value
    regression (a lane mismatch) — or, rarely, a transient compiler failure under host load."""

    documents = SourceLoader().load(tuple(sorted(data_root.rglob("*.tsl"))))
    catalog = CatalogBuilder().build(TslParser().parse(documents.documents)).catalog
    assert catalog is not None
    names = sorted({primitive.name for primitive in catalog.primitives})

    result = generate_project(
        [data_root],
        machine_profiles_path=machine_profiles_path,
        primitives=names,
        profiles=["avx2"],
        backends=("cpp",),
        test_harness=True,
    )
    assert not has_errors(result.diagnostics), result.diagnostics
    assert result.rendered is not None
    write_report = write_artifacts(result.artifacts, tmp_path)
    assert not has_errors(write_report.diagnostics), write_report.diagnostics

    report = verify_project(tmp_path, result.rendered.verify, run_value_tests=True)
    # Fully green: no compile/configure errors and no value-test (ctest) warnings.
    assert report.diagnostics == (), report.diagnostics
