"""Explicit compiler-owned analysis of one concrete specialization slot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tslc._pipeline_closure import (
    LoweringTrace,
    LoweringTraceSlot,
    dependency_label,
    lowering_trace_dependency_key,
    lowering_trace_slot_key,
    unresolved_trace_reason,
)
from tslc._pipeline_inputs import _load_inputs
from tslc.api import _expand_sources
from tslc.diagnostics import Diagnostic, SourceSpan
from tslc.lower.dependencies import CallDependency, dependency_sort_key
from tslc.lower.implementation_state import (
    ImplementationState,
    combine_implementation_states,
)
from tslc.pipeline import GenerationRequest, SkippedEntry, _generate_loaded

AnalysisNodeStatus = Literal["resolved", "unresolved", "cycle"]


@dataclass(frozen=True, slots=True)
class ConcreteAnalysisContext:
    primitive: str
    profile: str
    backend: str
    extension: str
    type_tag: str


@dataclass(frozen=True, slots=True)
class ConcreteAnalysisNode:
    """One active lowered specialization or unresolved call edge."""

    status: AnalysisNodeStatus
    primitive: str
    backend: str
    extension: str
    type_tag: str
    implementation_state: ImplementationState
    origin: str | None = None
    reason: str | None = None
    source: SourceSpan | None = None
    param_names: tuple[str, ...] = ()
    param_kinds: tuple[str, ...] = ()
    target_extension: str | None = None
    target_type: str | None = None
    dependencies: tuple["ConcreteAnalysisNode", ...] = ()


@dataclass(frozen=True, slots=True)
class ConcreteAnalysis:
    """An immutable, input-identified result for one explorer slot."""

    status: Literal["analyzed"]
    input_digest: str
    context: ConcreteAnalysisContext
    implementation_state: ImplementationState
    roots: tuple[ConcreteAnalysisNode, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


def analyze_concrete_specialization(
    *,
    sources: Path,
    machine_profiles: Path,
    primitive: str,
    profile: str,
    backend: str,
    extension: str,
    type_tag: str,
) -> tuple[ConcreteAnalysis | None, tuple[Diagnostic, ...]]:
    """Load one saved corpus and analyze an exact lowered specialization."""

    request = GenerationRequest(
        source_paths=_expand_sources((sources,)),
        machine_profiles_path=machine_profiles,
        primitives=(primitive,),
        profiles=(profile,),
        type_tags=(type_tag,),
        extensions=(extension,),
        backends=(backend,),
        render_artifacts=False,
        collect_lowering_trace=True,
    )
    inputs, load_diagnostics = _load_inputs(request)
    if inputs is None:
        return None, tuple(load_diagnostics)
    result = _generate_loaded(request, inputs, load_diagnostics)
    context = ConcreteAnalysisContext(
        primitive=primitive,
        profile=profile,
        backend=backend,
        extension=extension,
        type_tag=type_tag,
    )
    trace = result.lowering_trace
    roots = (
        _analysis_roots(trace, context, result.skipped)
        if trace is not None
        else (_missing_root(context, result.skipped),)
    )
    state = combine_implementation_states(
        [root.implementation_state for root in roots]
    )
    return (
        ConcreteAnalysis(
            status="analyzed",
            input_digest=inputs.input_digest,
            context=context,
            implementation_state=state,
            roots=roots,
            diagnostics=result.diagnostics,
        ),
        result.diagnostics,
    )


def _analysis_roots(
    trace: LoweringTrace,
    context: ConcreteAnalysisContext,
    skipped: tuple[SkippedEntry, ...],
) -> tuple[ConcreteAnalysisNode, ...]:
    candidates = tuple(
        slot
        for slot in trace.slots
        if _matches_context(slot, context)
    )
    if not candidates:
        return (_missing_root(context, skipped),)
    by_key: dict[object, tuple[LoweringTraceSlot, ...]] = {}
    mutable: dict[object, list[LoweringTraceSlot]] = {}
    for slot in trace.slots:
        slot_key = lowering_trace_slot_key(slot, trace.split_names)
        mutable.setdefault(slot_key, []).append(slot)
    for trace_key, slots in mutable.items():
        emitted = tuple(slot for slot in slots if slot.emitted)
        by_key[trace_key] = emitted or tuple(slots)
    return tuple(
        _node_from_slot(slot, trace, by_key, (), origin=None)
        for slot in candidates
    )


def _matches_context(
    slot: LoweringTraceSlot,
    context: ConcreteAnalysisContext,
) -> bool:
    spec = slot.specialization
    return (
        slot.profile == context.profile
        and slot.backend == context.backend
        and context.primitive in {spec.primitive_name, spec.source_primitive_name}
        and spec.extension_name == context.extension
        and spec.type_tag == context.type_tag
    )


def _node_from_slot(
    slot: LoweringTraceSlot,
    trace: LoweringTrace,
    by_key: dict[object, tuple[LoweringTraceSlot, ...]],
    stack: tuple[tuple[object, ...], ...],
    *,
    origin: str | None,
) -> ConcreteAnalysisNode:
    identity = _analysis_slot_identity(slot, trace)
    spec = slot.specialization
    if identity in stack:
        return _slot_node(
            slot,
            status="cycle",
            state=spec.implementation_state,
            origin=origin,
            reason="cycle: this specialization is already active in the call path",
        )

    origins = {item.dependency: item.origin for item in slot.callee_origins}
    dependencies: list[ConcreteAnalysisNode] = []
    for dependency in sorted(slot.callees, key=dependency_sort_key):
        edge_origin = origins.get(dependency, "implementation")
        key = lowering_trace_dependency_key(slot, dependency, trace.split_names)
        targets = by_key.get(key, ())
        if not targets:
            dependencies.append(
                _missing_dependency_node(slot.backend, dependency, edge_origin)
            )
            continue
        dependencies.extend(
            _node_from_slot(
                target,
                trace,
                by_key,
                (*stack, identity),
                origin=edge_origin,
            )
            for target in targets
        )

    return _slot_node(
        slot,
        status="resolved" if slot.emitted else "unresolved",
        state=(
            spec.implementation_state
            if slot.emitted
            else ImplementationState.UNKNOWN
        ),
        origin=origin,
        reason=None if slot.emitted else unresolved_trace_reason(slot),
        dependencies=tuple(dependencies),
    )


def _analysis_slot_identity(
    slot: LoweringTraceSlot,
    trace: LoweringTrace,
) -> tuple[object, ...]:
    spec = slot.specialization
    source = spec.source
    return (
        lowering_trace_slot_key(slot, trace.split_names),
        spec.source_primitive_name,
        spec.param_kinds,
        spec.axis,
        spec.variant_names,
        source.path.as_posix() if source is not None else "",
        source.line if source is not None else 0,
        source.column if source is not None else 0,
    )


def _slot_node(
    slot: LoweringTraceSlot,
    *,
    status: AnalysisNodeStatus,
    state: ImplementationState,
    origin: str | None,
    reason: str | None,
    dependencies: tuple[ConcreteAnalysisNode, ...] = (),
) -> ConcreteAnalysisNode:
    spec = slot.specialization
    target = spec.target
    return ConcreteAnalysisNode(
        status=status,
        primitive=spec.primitive_name,
        backend=slot.backend,
        extension=spec.extension_name,
        type_tag=spec.type_tag,
        implementation_state=state,
        origin=origin,
        reason=reason,
        source=spec.source,
        param_names=spec.param_names,
        param_kinds=spec.param_kinds,
        target_extension=target.extension_isa if target is not None else None,
        target_type=target.base_tag if target is not None else None,
        dependencies=dependencies,
    )


def _missing_dependency_node(
    backend: str,
    dependency: CallDependency,
    origin: str,
) -> ConcreteAnalysisNode:
    target = dependency.target
    return ConcreteAnalysisNode(
        status="unresolved",
        primitive=dependency.primitive,
        backend=backend,
        extension=dependency.source.extension_isa,
        type_tag=dependency.source.base_tag,
        implementation_state=ImplementationState.UNKNOWN,
        origin=origin,
        reason=(
            f"unresolved: {origin} calls {dependency_label(dependency)}, but no "
            "lowered specialization satisfies that dependency"
        ),
        target_extension=target.extension_isa if target is not None else None,
        target_type=target.base_tag if target is not None else None,
    )


def _missing_root(
    context: ConcreteAnalysisContext,
    skipped: tuple[SkippedEntry, ...],
) -> ConcreteAnalysisNode:
    reasons = tuple(
        sorted(
            {
                item.reason
                for item in skipped
                if item.profile == context.profile
                and item.backend == context.backend
                and item.primitive == context.primitive
                and item.extension == context.extension
                and item.type_tag == context.type_tag
            }
        )
    )
    reason = (
        "; ".join(reasons)
        if reasons
        else "no selected implementation lowered for this concrete context"
    )
    return ConcreteAnalysisNode(
        status="unresolved",
        primitive=context.primitive,
        backend=context.backend,
        extension=context.extension,
        type_tag=context.type_tag,
        implementation_state=ImplementationState.UNKNOWN,
        reason=reason,
    )


__all__ = (
    "AnalysisNodeStatus",
    "ConcreteAnalysis",
    "ConcreteAnalysisContext",
    "ConcreteAnalysisNode",
    "analyze_concrete_specialization",
)
