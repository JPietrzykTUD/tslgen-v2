"""Focused tests for explicit lowered-slot analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from tslc._pipeline_closure import LoweringTrace, LoweringTraceSlot
from tslc.concrete_analysis import (
    ConcreteAnalysis,
    ConcreteAnalysisContext,
    _analysis_roots,
    analyze_concrete_specialization,
)
from tslc.lower.dependencies import (
    CallDependency,
    CallDependencyOrigin,
    GenericVectorReference,
    VectorIdentity,
)
from tslc.lower.implementation_state import ImplementationState
from tslc.lower.lowerer import LoweredSpecialization
from tslc.maintenance.analyze_specialization import format_analysis_text
from tslc.target_text import LoweredBody


@pytest.mark.parametrize("state", tuple(ImplementationState))
def test_analysis_preserves_all_compiler_owned_implementation_states(
    state: ImplementationState,
) -> None:
    slot = _trace_slot("root", state=state)

    roots = _analysis_roots(
        LoweringTrace(frozenset(), (slot,)), _context("root"), ()
    )

    assert len(roots) == 1
    assert roots[0].status == "resolved"
    assert roots[0].implementation_state is state


def test_analysis_marks_cycles_deterministically() -> None:
    a_to_b = _dependency("b")
    b_to_a = _dependency("a")
    trace = LoweringTrace(
        frozenset(),
        (
            _trace_slot("a", callees=(a_to_b,)),
            _trace_slot("b", callees=(b_to_a,)),
        ),
    )

    first = _analysis_roots(trace, _context("a"), ())
    second = _analysis_roots(trace, _context("a"), ())

    cycle = first[0].dependencies[0].dependencies[0]
    assert cycle.status == "cycle"
    assert cycle.primitive == "a"
    assert cycle.dependencies == ()
    assert first == second


def test_analysis_keeps_an_actionable_unresolved_edge() -> None:
    dependency = _dependency("missing")
    trace = LoweringTrace(
        frozenset(), (_trace_slot("root", callees=(dependency,)),)
    )

    root = _analysis_roots(trace, _context("root"), ())[0]

    unresolved = root.dependencies[0]
    assert unresolved.status == "unresolved"
    assert unresolved.origin == "implementation"
    assert unresolved.reason is not None
    assert "missing<scalar, si32>" in unresolved.reason


def test_analysis_keeps_symbolic_dependencies_visible_and_deterministic() -> None:
    dependency = CallDependency(
        "to_array",
        None,
        GenericVectorReference("Dst", "f64"),
    )
    trace = LoweringTrace(
        frozenset(),
        (_trace_slot("root", callees=(dependency,)),),
    )

    first = _analysis_roots(trace, _context("root"), ())
    second = _analysis_roots(trace, _context("root"), ())

    symbolic = first[0].dependencies[0]
    assert first == second
    assert symbolic.status == "symbolic"
    assert symbolic.extension is None
    assert symbolic.type_tag == "f64"
    assert symbolic.vector_reference == "Dst[base=f64]"
    analysis = ConcreteAnalysis(
        status="analyzed",
        input_digest="demo",
        context=_context("root"),
        implementation_state=ImplementationState.COMPOSED,
        roots=first,
    )
    rendered = format_analysis_text(analysis)
    assert "to_array<Dst[base=f64]>" in rendered
    assert "avx2" not in rendered


def test_real_corpus_analysis_reuses_pipeline_lowering_without_rendering(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    analysis, diagnostics = analyze_concrete_specialization(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="set_zero",
        profile="avx2",
        backend="cpp",
        extension="avx2",
        type_tag="si32",
    )

    assert diagnostics == ()
    assert analysis is not None
    assert analysis.status == "analyzed"
    assert analysis.implementation_state is ImplementationState.NATIVE
    assert analysis.input_digest
    assert analysis.roots[0].source is not None


def test_real_corpus_analysis_selects_one_representation_target(
    data_root: Path,
    machine_profiles_path: Path,
) -> None:
    analysis, diagnostics = analyze_concrete_specialization(
        sources=data_root,
        machine_profiles=machine_profiles_path,
        primitive="insert_imask",
        profile="avx2",
        backend="cpp",
        extension="sse",
        type_tag="si64",
        to_target="avx2",
    )

    assert diagnostics == ()
    assert analysis is not None
    assert analysis.context.to_target == "avx2"
    assert len(analysis.roots) == 1
    assert analysis.roots[0].target_extension == "avx2"
    assert analysis.roots[0].target_type == "si64"
    rendered = format_analysis_text(analysis)
    assert "insert_imask<si64 -> avx2>" in rendered
    assert "-> si64<avx2>" in rendered


def _context(primitive: str) -> ConcreteAnalysisContext:
    return ConcreteAnalysisContext(
        primitive=primitive,
        profile="test",
        backend="cpp",
        extension="scalar",
        type_tag="si32",
    )


def _dependency(primitive: str) -> CallDependency:
    return CallDependency(
        primitive=primitive,
        mask_policy=None,
        source=VectorIdentity("si32", "scalar"),
    )


def _trace_slot(
    primitive: str,
    *,
    state: ImplementationState = ImplementationState.COMPOSED,
    callees: tuple[CallDependency, ...] = (),
) -> LoweringTraceSlot:
    origins = tuple(
        CallDependencyOrigin(dependency, "implementation")
        for dependency in callees
    )
    return LoweringTraceSlot(
        profile="test",
        backend="cpp",
        specialization=LoweredSpecialization(
            backend_id="cpp",
            primitive_name=primitive,
            source_primitive_name=primitive,
            extension_name="scalar",
            type_tag="si32",
            base_type_spelling="std::int32_t",
            register_spelling="std::int32_t",
            result_kind="v",
            param_names=("data",),
            param_kinds=("v",),
            body=LoweredBody.from_text("return data;"),
            register_is_base=True,
            call_dependency_origins=origins,
            implementation_state=state,
        ),
        callees=callees,
        callee_origins=origins,
        emitted=True,
    )
