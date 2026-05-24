from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from tslgen.analysis.candidates import CandidateSelection, ImplementationCandidate
from tslgen.analysis.dependencies import (
    DependencyGraph,
    DependencyReference,
    discover_dependency_graph,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.values import CatalogValue


type CandidateDependencyIssueReason = Literal["ambiguous", "missing", "unsupported"]


@dataclass(frozen=True, slots=True)
class CandidateDependencyEdge:
    source_candidate_id: str
    target_candidate_id: str
    reference: DependencyReference

    def __post_init__(self) -> None:
        if not self.source_candidate_id:
            raise ValueError("candidate dependency source id must be non-empty")
        if not self.target_candidate_id:
            raise ValueError("candidate dependency target id must be non-empty")

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_candidate_id,
            self.target_candidate_id,
            self.reference.key,
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencyIssue:
    source_candidate_id: str
    target_primitive_name: str
    reference: DependencyReference
    reason: CandidateDependencyIssueReason
    candidate_ids: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.source_candidate_id:
            raise ValueError("candidate dependency issue source id must be non-empty")
        if not self.target_primitive_name:
            raise ValueError("candidate dependency issue target must be non-empty")
        object.__setattr__(self, "candidate_ids", tuple(sorted(self.candidate_ids)))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_candidate_id,
            self.target_primitive_name,
            self.reason,
            self.reference.key,
            self.candidate_ids,
            self.detail,
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencyGraph:
    primitive_graph: DependencyGraph
    edges: tuple[CandidateDependencyEdge, ...]
    issues: tuple[CandidateDependencyIssue, ...] = ()
    edges_by_source_candidate_id: FrozenMap[
        str,
        tuple[CandidateDependencyEdge, ...],
    ] = field(init=False)
    issues_by_source_candidate_id: FrozenMap[
        str,
        tuple[CandidateDependencyIssue, ...],
    ] = field(init=False)

    def __post_init__(self) -> None:
        edges = tuple(sorted(self.edges, key=lambda edge: edge.key))
        issues = tuple(sorted(self.issues, key=lambda issue: issue.key))
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "issues", issues)
        object.__setattr__(
            self,
            "edges_by_source_candidate_id",
            _group_edges_by_source(edges),
        )
        object.__setattr__(
            self,
            "issues_by_source_candidate_id",
            _group_issues_by_source(issues),
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencyClosure:
    graph: CandidateDependencyGraph
    root_candidate_ids: tuple[str, ...]
    required_candidate_ids: tuple[str, ...]
    required_primitive_names: tuple[str, ...]
    fallback_primitive_names: tuple[str, ...] = ()
    ambiguous_primitive_names: tuple[str, ...] = ()
    unresolved_primitive_names: tuple[str, ...] = ()
    unsupported_primitive_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_candidate_ids", tuple(self.root_candidate_ids))
        object.__setattr__(
            self,
            "required_candidate_ids",
            tuple(self.required_candidate_ids),
        )
        object.__setattr__(
            self,
            "required_primitive_names",
            tuple(sorted(frozenset(self.required_primitive_names))),
        )
        object.__setattr__(
            self,
            "fallback_primitive_names",
            tuple(sorted(frozenset(self.fallback_primitive_names))),
        )
        object.__setattr__(
            self,
            "ambiguous_primitive_names",
            tuple(sorted(frozenset(self.ambiguous_primitive_names))),
        )
        object.__setattr__(
            self,
            "unresolved_primitive_names",
            tuple(sorted(frozenset(self.unresolved_primitive_names))),
        )
        object.__setattr__(
            self,
            "unsupported_primitive_names",
            tuple(sorted(frozenset(self.unsupported_primitive_names))),
        )


def discover_candidate_dependency_graph(
    selection: CandidateSelection,
    catalog: Catalog,
) -> Result[CandidateDependencyGraph]:
    primitive_result = discover_dependency_graph(selection, catalog)
    if not primitive_result.is_ok:
        return Result.failure(primitive_result.diagnostics)
    graph = candidate_dependency_graph_from_primitive_graph(primitive_result.unwrap())
    diagnostics = sort_diagnostics((*primitive_result.diagnostics, *graph.diagnostics))
    if has_errors(diagnostics):
        return Result.failure(diagnostics)
    return Result.ok(graph.unwrap(), diagnostics=diagnostics)


def candidate_dependency_graph_from_primitive_graph(
    primitive_graph: DependencyGraph,
) -> Result[CandidateDependencyGraph]:
    edges: list[CandidateDependencyEdge] = []
    issues: list[CandidateDependencyIssue] = []
    for dependency in primitive_graph.candidate_dependencies:
        for reference in dependency.references:
            resolved = _resolve_reference(primitive_graph, dependency.candidate, reference)
            if isinstance(resolved, CandidateDependencyEdge):
                edges.append(resolved)
            else:
                issues.append(resolved)

    candidate_graph = CandidateDependencyGraph(
        primitive_graph=primitive_graph,
        edges=tuple(edges),
        issues=tuple(issues),
    )
    diagnostics = tuple(_issue_diagnostic(candidate_graph, issue) for issue in issues)
    return Result.ok(candidate_graph, diagnostics=diagnostics)


def plan_candidate_dependency_closure(
    selection: CandidateSelection,
    catalog: Catalog,
    *,
    root_candidate_ids: Iterable[str] = (),
) -> Result[CandidateDependencyClosure]:
    graph = discover_candidate_dependency_graph(selection, catalog)
    if not graph.is_ok:
        return Result.failure(graph.diagnostics)
    closure = compute_candidate_dependency_closure(
        graph.unwrap(),
        root_candidate_ids=root_candidate_ids,
    )
    diagnostics = sort_diagnostics((*graph.diagnostics, *closure.diagnostics))
    if closure.is_ok:
        return Result.ok(closure.unwrap(), diagnostics=diagnostics)
    return Result.failure(diagnostics)


def compute_candidate_dependency_closure(
    graph: CandidateDependencyGraph,
    *,
    root_candidate_ids: Iterable[str] = (),
) -> Result[CandidateDependencyClosure]:
    requested_roots = tuple(root_candidate_ids)
    roots = requested_roots or tuple(
        candidate.candidate_id for candidate in graph.primitive_graph.selection.candidates
    )
    diagnostics: list[Diagnostic] = []
    for root in roots:
        if root not in graph.primitive_graph.selection.candidates_by_id:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-CANDIDATE-DEPENDENCY-UNKNOWN-ROOT",
                    f"candidate dependency closure root {root!r} is not in the "
                    "candidate selection",
                )
            )

    if not diagnostics:
        diagnostics.extend(_cycle_diagnostics(graph, roots))

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)

    required_candidate_ids = _required_candidate_ids(graph, roots)
    reachable_issues = _reachable_issues(graph, required_candidate_ids)
    candidate_primitive_names = tuple(
        graph.primitive_graph.selection.candidates_by_id[candidate_id].source_primitive_name
        for candidate_id in required_candidate_ids
    )
    fallback_names = tuple(issue.target_primitive_name for issue in reachable_issues)
    return Result.ok(
        CandidateDependencyClosure(
            graph=graph,
            root_candidate_ids=roots,
            required_candidate_ids=required_candidate_ids,
            required_primitive_names=(*candidate_primitive_names, *fallback_names),
            fallback_primitive_names=fallback_names,
            ambiguous_primitive_names=tuple(
                issue.target_primitive_name
                for issue in reachable_issues
                if issue.reason == "ambiguous"
            ),
            unresolved_primitive_names=tuple(
                issue.target_primitive_name
                for issue in reachable_issues
                if issue.reason == "missing"
            ),
            unsupported_primitive_names=tuple(
                issue.target_primitive_name
                for issue in reachable_issues
                if issue.reason == "unsupported"
            ),
        )
    )


def _resolve_reference(
    primitive_graph: DependencyGraph,
    source_candidate: ImplementationCandidate,
    reference: DependencyReference,
) -> CandidateDependencyEdge | CandidateDependencyIssue:
    candidate_ids = primitive_graph.candidate_ids_by_primitive_name.get(
        reference.target_primitive_name,
        (),
    )
    candidates = tuple(
        primitive_graph.selection.candidates_by_id[candidate_id]
        for candidate_id in candidate_ids
    )
    if not candidates:
        return _issue(
            reference,
            "missing",
            detail="target primitive has no candidate in the current selection",
        )

    candidates = tuple(
        candidate
        for candidate in candidates
        if _backend_compatible(source_candidate, candidate)
    )
    if not candidates:
        return _issue(
            reference,
            "missing",
            detail="target primitive has no candidate for the source backend context",
        )

    if reference.type_arguments:
        typed = _filter_by_type_argument(reference, candidates)
        if isinstance(typed, CandidateDependencyIssue):
            return typed
        candidates = typed

    candidates = _filter_by_attributes(reference, candidates)
    if not candidates:
        return _issue(
            reference,
            "missing",
            detail="target primitive has no candidate matching dependency attributes",
        )
    if len(candidates) > 1:
        return _issue(
            reference,
            "ambiguous",
            candidate_ids=tuple(candidate.candidate_id for candidate in candidates),
            detail="dependency selectors match multiple implementation candidates",
        )
    target = candidates[0]
    return CandidateDependencyEdge(
        source_candidate_id=reference.source_candidate_id,
        target_candidate_id=target.candidate_id,
        reference=reference,
    )


def _filter_by_type_argument(
    reference: DependencyReference,
    candidates: tuple[ImplementationCandidate, ...],
) -> tuple[ImplementationCandidate, ...] | CandidateDependencyIssue:
    if len(reference.type_arguments) != 1:
        return _issue(
            reference,
            "unsupported",
            detail="multiple dependency type arguments need TSIL lowering",
        )
    type_argument = reference.type_arguments[0]
    available_type_tags = frozenset(candidate.type_tag for candidate in candidates)
    if type_argument not in available_type_tags:
        return _issue(
            reference,
            "unsupported",
            detail=(
                f"type argument {type_argument!r} is not a concrete selected "
                "candidate type tag"
            ),
        )
    return tuple(candidate for candidate in candidates if candidate.type_tag == type_argument)


def _filter_by_attributes(
    reference: DependencyReference,
    candidates: tuple[ImplementationCandidate, ...],
) -> tuple[ImplementationCandidate, ...]:
    if not reference.attributes:
        return candidates
    return tuple(
        candidate
        for candidate in candidates
        if _candidate_attributes_match(candidate, reference.attributes)
    )


def _candidate_attributes_match(
    candidate: ImplementationCandidate,
    attributes: FrozenMap[str, CatalogValue],
) -> bool:
    return all(candidate.variant.attributes.get(key) == value for key, value in attributes.items())


def _backend_compatible(
    source: ImplementationCandidate,
    target: ImplementationCandidate,
) -> bool:
    return (
        source.backend is None
        or target.backend is None
        or source.backend == target.backend
    )


def _issue(
    reference: DependencyReference,
    reason: CandidateDependencyIssueReason,
    *,
    candidate_ids: tuple[str, ...] = (),
    detail: str,
) -> CandidateDependencyIssue:
    return CandidateDependencyIssue(
        source_candidate_id=reference.source_candidate_id,
        target_primitive_name=reference.target_primitive_name,
        reference=reference,
        reason=reason,
        candidate_ids=candidate_ids,
        detail=detail,
    )


def _issue_diagnostic(
    graph: CandidateDependencyGraph,
    issue: CandidateDependencyIssue,
) -> Diagnostic:
    candidate = graph.primitive_graph.selection.candidates_by_id[issue.source_candidate_id]
    code = {
        "ambiguous": "TSL-CANDIDATE-DEPENDENCY-AMBIGUOUS",
        "missing": "TSL-CANDIDATE-DEPENDENCY-MISSING",
        "unsupported": "TSL-CANDIDATE-DEPENDENCY-UNSUPPORTED",
    }[issue.reason]
    message = _issue_message(issue)
    return Diagnostic.warning(
        code,
        message,
        location=candidate.variant.source.declaration.source_span.location,
    )


def _issue_message(issue: CandidateDependencyIssue) -> str:
    base = (
        f"candidate {issue.source_candidate_id!r} dependency on primitive "
        f"{issue.target_primitive_name!r} cannot be resolved to a candidate"
    )
    if issue.reason == "ambiguous":
        candidates = ", ".join(issue.candidate_ids)
        return f"{base}: {issue.detail}; matched candidates: {candidates}"
    return f"{base}: {issue.detail}; primitive-level fallback is retained"


def _required_candidate_ids(
    graph: CandidateDependencyGraph,
    root_candidate_ids: tuple[str, ...],
) -> tuple[str, ...]:
    required: set[str] = set()
    stack = list(reversed(root_candidate_ids))
    while stack:
        candidate_id = stack.pop()
        if candidate_id in required:
            continue
        required.add(candidate_id)
        for edge in reversed(graph.edges_by_source_candidate_id.get(candidate_id, ())):
            if edge.target_candidate_id != candidate_id:
                stack.append(edge.target_candidate_id)
    return _ordered_candidate_ids(graph, required)


def _reachable_issues(
    graph: CandidateDependencyGraph,
    required_candidate_ids: tuple[str, ...],
) -> tuple[CandidateDependencyIssue, ...]:
    issues = [
        issue
        for candidate_id in required_candidate_ids
        for issue in graph.issues_by_source_candidate_id.get(candidate_id, ())
    ]
    return tuple(sorted(issues, key=lambda issue: issue.key))


def _ordered_candidate_ids(
    graph: CandidateDependencyGraph,
    candidate_ids: Iterable[str],
) -> tuple[str, ...]:
    order = {
        candidate.candidate_id: index
        for index, candidate in enumerate(graph.primitive_graph.selection.candidates)
    }
    return tuple(sorted(candidate_ids, key=lambda candidate_id: order[candidate_id]))


def _cycle_diagnostics(
    graph: CandidateDependencyGraph,
    root_candidate_ids: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_cycles: set[tuple[str, ...]] = set()
    for candidate_id in root_candidate_ids:
        _visit_cycles(
            graph,
            candidate_id,
            path=(),
            diagnostics=diagnostics,
            seen_cycles=seen_cycles,
        )
    return tuple(diagnostics)


def _visit_cycles(
    graph: CandidateDependencyGraph,
    candidate_id: str,
    *,
    path: tuple[str, ...],
    diagnostics: list[Diagnostic],
    seen_cycles: set[tuple[str, ...]],
) -> None:
    if candidate_id in path:
        cycle = (*path[path.index(candidate_id) :], candidate_id)
        if len(cycle) <= 2:
            return
        key = _canonical_cycle_key(cycle)
        if key not in seen_cycles:
            seen_cycles.add(key)
            diagnostics.append(_cycle_diagnostic(graph, cycle))
        return

    next_path = (*path, candidate_id)
    for edge in graph.edges_by_source_candidate_id.get(candidate_id, ()):
        if edge.target_candidate_id == candidate_id:
            continue
        _visit_cycles(
            graph,
            edge.target_candidate_id,
            path=next_path,
            diagnostics=diagnostics,
            seen_cycles=seen_cycles,
        )


def _canonical_cycle_key(cycle: tuple[str, ...]) -> tuple[str, ...]:
    body = cycle[:-1]
    rotations = tuple(body[index:] + body[:index] for index in range(len(body)))
    canonical = min(rotations)
    return (*canonical, canonical[0])


def _cycle_diagnostic(
    graph: CandidateDependencyGraph,
    cycle: tuple[str, ...],
) -> Diagnostic:
    location = _candidate_location(graph, cycle[0])
    return Diagnostic.error(
        "TSL-CANDIDATE-DEPENDENCY-CYCLE",
        f"candidate dependency cycle detected: {' -> '.join(cycle)}",
        location=location,
    )


def _candidate_location(
    graph: CandidateDependencyGraph,
    candidate_id: str,
) -> SourceLocation | None:
    candidate = graph.primitive_graph.selection.candidates_by_id.get(candidate_id)
    if candidate is None:
        return None
    return candidate.variant.source.declaration.source_span.location


def _group_edges_by_source(
    edges: tuple[CandidateDependencyEdge, ...],
) -> FrozenMap[str, tuple[CandidateDependencyEdge, ...]]:
    grouped: dict[str, list[CandidateDependencyEdge]] = {}
    for edge in edges:
        grouped.setdefault(edge.source_candidate_id, []).append(edge)
    return FrozenMap(
        (source, tuple(sorted(items, key=lambda edge: edge.key)))
        for source, items in grouped.items()
    )


def _group_issues_by_source(
    issues: tuple[CandidateDependencyIssue, ...],
) -> FrozenMap[str, tuple[CandidateDependencyIssue, ...]]:
    grouped: dict[str, list[CandidateDependencyIssue]] = {}
    for issue in issues:
        grouped.setdefault(issue.source_candidate_id, []).append(issue)
    return FrozenMap(
        (source, tuple(sorted(items, key=lambda issue: issue.key)))
        for source, items in grouped.items()
    )
