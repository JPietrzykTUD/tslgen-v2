from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from tslgen.analysis.candidates import (
    CandidateSelection,
    ImplementationCandidate,
)
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.result import Result
from tslgen.domain.catalog import Catalog
from tslgen.domain.values import CatalogValue


_CALL_MARKER = "call<primitive="


@dataclass(frozen=True, slots=True)
class DependencyReference:
    source_candidate_id: str
    raw_target: str
    target_primitive_name: str
    type_arguments: tuple[str, ...] = ()
    attributes: FrozenMap[str, CatalogValue] = field(default_factory=FrozenMap.empty)
    is_self_reference: bool = False

    def __post_init__(self) -> None:
        if not self.source_candidate_id:
            raise ValueError("dependency source candidate id must be non-empty")
        if not self.raw_target:
            raise ValueError("dependency raw target must be non-empty")
        if not self.target_primitive_name:
            raise ValueError("dependency target primitive name must be non-empty")
        object.__setattr__(self, "type_arguments", tuple(self.type_arguments))

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.source_candidate_id,
            self.target_primitive_name,
            self.raw_target,
            self.type_arguments,
            tuple(self.attributes.items()),
            self.is_self_reference,
        )


@dataclass(frozen=True, slots=True)
class CandidateDependencies:
    candidate: ImplementationCandidate
    references: tuple[DependencyReference, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "references",
            tuple(sorted(self.references, key=lambda reference: reference.key)),
        )

    @property
    def direct_primitive_names(self) -> tuple[str, ...]:
        seen: set[str] = set()
        names: list[str] = []
        for reference in self.references:
            if reference.target_primitive_name in seen:
                continue
            seen.add(reference.target_primitive_name)
            names.append(reference.target_primitive_name)
        return tuple(names)


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    selection: CandidateSelection
    candidate_dependencies: tuple[CandidateDependencies, ...]
    dependencies_by_candidate_id: FrozenMap[str, CandidateDependencies] = field(
        init=False
    )
    candidate_ids_by_primitive_name: FrozenMap[str, tuple[str, ...]] = field(
        init=False
    )
    direct_primitive_dependencies: FrozenMap[str, tuple[str, ...]] = field(init=False)

    def __post_init__(self) -> None:
        dependencies = tuple(
            sorted(
                self.candidate_dependencies,
                key=lambda item: item.candidate.candidate_id,
            )
        )
        object.__setattr__(self, "candidate_dependencies", dependencies)
        object.__setattr__(
            self,
            "dependencies_by_candidate_id",
            FrozenMap(
                (item.candidate.candidate_id, item)
                for item in dependencies
            ),
        )
        object.__setattr__(
            self,
            "candidate_ids_by_primitive_name",
            _candidate_ids_by_primitive_name(self.selection.candidates),
        )
        object.__setattr__(
            self,
            "direct_primitive_dependencies",
            _direct_primitive_dependencies(dependencies),
        )


@dataclass(frozen=True, slots=True)
class DependencyClosure:
    graph: DependencyGraph
    root_candidate_ids: tuple[str, ...]
    required_primitive_names: tuple[str, ...]
    required_candidate_ids: tuple[str, ...]
    unplanned_primitive_names: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_candidate_ids", tuple(self.root_candidate_ids))
        object.__setattr__(
            self,
            "required_primitive_names",
            tuple(self.required_primitive_names),
        )
        object.__setattr__(
            self,
            "required_candidate_ids",
            tuple(self.required_candidate_ids),
        )
        object.__setattr__(
            self,
            "unplanned_primitive_names",
            tuple(self.unplanned_primitive_names),
        )


def discover_dependency_graph(
    selection: CandidateSelection,
    catalog: Catalog,
) -> Result[DependencyGraph]:
    diagnostics: list[Diagnostic] = []
    dependencies: list[CandidateDependencies] = []
    for candidate in selection.candidates:
        discovered = _dependencies_for_candidate(candidate, catalog)
        diagnostics.extend(discovered.diagnostics)
        if discovered.is_ok:
            dependencies.append(discovered.unwrap())

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        DependencyGraph(
            selection=selection,
            candidate_dependencies=tuple(dependencies),
        ),
        diagnostics=ordered,
    )


def plan_dependency_closure(
    selection: CandidateSelection,
    catalog: Catalog,
    *,
    root_candidate_ids: Iterable[str] = (),
) -> Result[DependencyClosure]:
    graph_result = discover_dependency_graph(selection, catalog)
    if not graph_result.is_ok:
        return Result.failure(graph_result.diagnostics)
    return compute_dependency_closure(
        graph_result.unwrap(),
        root_candidate_ids=root_candidate_ids,
    )


def compute_dependency_closure(
    graph: DependencyGraph,
    *,
    root_candidate_ids: Iterable[str] = (),
) -> Result[DependencyClosure]:
    requested_roots = tuple(root_candidate_ids)
    roots = requested_roots or tuple(
        candidate.candidate_id for candidate in graph.selection.candidates
    )
    diagnostics: list[Diagnostic] = []
    for root in roots:
        if root not in graph.dependencies_by_candidate_id:
            diagnostics.append(
                Diagnostic.error(
                    "TSL-DEPENDENCY-UNKNOWN-ROOT",
                    f"dependency closure root candidate {root!r} is not in the "
                    "candidate selection",
                )
            )

    if not diagnostics:
        diagnostics.extend(_cycle_diagnostics(graph, roots))

    if has_errors(diagnostics):
        return Result.failure(sort_diagnostics(diagnostics))

    required_names = _required_primitive_names(graph, roots)
    candidate_ids = tuple(
        candidate.candidate_id
        for candidate in graph.selection.candidates
        if candidate.source_primitive_name in required_names
    )
    unplanned_names = tuple(
        name
        for name in required_names
        if name not in graph.candidate_ids_by_primitive_name
    )
    return Result.ok(
        DependencyClosure(
            graph=graph,
            root_candidate_ids=roots,
            required_primitive_names=required_names,
            required_candidate_ids=candidate_ids,
            unplanned_primitive_names=unplanned_names,
        )
    )


def _dependencies_for_candidate(
    candidate: ImplementationCandidate,
    catalog: Catalog,
) -> Result[CandidateDependencies]:
    body = candidate.implementation.body
    if body.kind != "tsil":
        return Result.ok(CandidateDependencies(candidate=candidate, references=()))
    if not isinstance(body.payload, str):
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-DEPENDENCY-BODY-SHAPE",
                    f"candidate {candidate.candidate_id!r} has a TSIL body that is "
                    "not text",
                    location=candidate.variant.source.declaration.source_span.location,
                ),
            )
        )

    diagnostics: list[Diagnostic] = []
    references: list[DependencyReference] = []
    for segment in _primitive_call_segments(body.payload):
        parsed = _parse_dependency_reference(candidate, segment)
        diagnostics.extend(parsed.diagnostics)
        if not parsed.is_ok:
            continue
        reference = parsed.unwrap()
        if not catalog.primitive_declarations(reference.target_primitive_name):
            diagnostics.append(_unknown_dependency_diagnostic(candidate, reference))
            continue
        references.append(reference)

    ordered = sort_diagnostics(diagnostics)
    if has_errors(ordered):
        return Result.failure(ordered)
    return Result.ok(
        CandidateDependencies(
            candidate=candidate,
            references=_unique_references(references),
        ),
        diagnostics=ordered,
    )


def _primitive_call_segments(payload: str) -> tuple[str, ...]:
    segments: list[str] = []
    cursor = 0
    while True:
        start = payload.find(_CALL_MARKER, cursor)
        if start == -1:
            return tuple(segments)
        spec_start = start + len(_CALL_MARKER)
        spec_end = _find_call_spec_end(payload, spec_start)
        if spec_end is None:
            cursor = spec_start
            continue
        segments.append(payload[spec_start:spec_end].strip())
        cursor = spec_end + 1


def _find_call_spec_end(payload: str, spec_start: int) -> int | None:
    angle_depth = 0
    for index in range(spec_start, len(payload)):
        char = payload[index]
        if char == "<":
            angle_depth += 1
        elif char == ">":
            if angle_depth == 0:
                return index
            angle_depth -= 1
    return None


def _parse_dependency_reference(
    candidate: ImplementationCandidate,
    segment: str,
) -> Result[DependencyReference]:
    if not segment:
        return Result.failure((_call_shape_diagnostic(candidate, segment),))

    name, rest = _take_target_name(segment)
    if not name:
        return Result.failure((_call_shape_diagnostic(candidate, segment),))

    rest = rest.lstrip()
    type_arguments: tuple[str, ...] = ()
    if rest.startswith("["):
        bracket = _take_bracket_content(rest)
        if bracket is None:
            return Result.failure((_call_shape_diagnostic(candidate, segment),))
        type_arguments = _split_top_level_items(bracket[0])
        rest = bracket[1].lstrip()

    attributes: FrozenMap[str, CatalogValue] = FrozenMap.empty()
    if rest:
        if not rest.startswith("attrs["):
            return Result.failure((_call_shape_diagnostic(candidate, segment),))
        bracket = _take_bracket_content(rest.removeprefix("attrs"))
        if bracket is None or bracket[1].strip():
            return Result.failure((_call_shape_diagnostic(candidate, segment),))
        parsed_attributes = _parse_attribute_arguments(bracket[0])
        if parsed_attributes is None:
            return Result.failure((_call_shape_diagnostic(candidate, segment),))
        attributes = parsed_attributes

    is_self_reference = name == "@self"
    target_name = candidate.source_primitive_name if is_self_reference else name
    return Result.ok(
        DependencyReference(
            source_candidate_id=candidate.candidate_id,
            raw_target=name,
            target_primitive_name=target_name,
            type_arguments=type_arguments,
            attributes=attributes,
            is_self_reference=is_self_reference,
        )
    )


def _take_target_name(segment: str) -> tuple[str, str]:
    for index, char in enumerate(segment):
        if char.isspace() or char == "[":
            return segment[:index], segment[index:]
    return segment, ""


def _take_bracket_content(text: str) -> tuple[str, str] | None:
    if not text.startswith("["):
        return None
    square_depth = 0
    angle_depth = 0
    paren_depth = 0
    for index, char in enumerate(text):
        if char == "[":
            square_depth += 1
        elif char == "]":
            square_depth -= 1
            if square_depth == 0:
                return text[1:index], text[index + 1 :]
        elif char == "<":
            angle_depth += 1
        elif char == ">" and angle_depth > 0:
            angle_depth -= 1
        elif char == "(":
            paren_depth += 1
        elif char == ")" and paren_depth > 0:
            paren_depth -= 1
    return None


def _split_top_level_items(text: str) -> tuple[str, ...]:
    items: list[str] = []
    start = 0
    square_depth = 0
    angle_depth = 0
    paren_depth = 0
    for index, char in enumerate(text):
        if char == "[":
            square_depth += 1
        elif char == "]" and square_depth > 0:
            square_depth -= 1
        elif char == "<":
            angle_depth += 1
        elif char == ">" and angle_depth > 0:
            angle_depth -= 1
        elif char == "(":
            paren_depth += 1
        elif char == ")" and paren_depth > 0:
            paren_depth -= 1
        elif (
            char == ","
            and square_depth == 0
            and angle_depth == 0
            and paren_depth == 0
        ):
            item = text[start:index].strip()
            if item:
                items.append(item)
            start = index + 1

    final_item = text[start:].strip()
    if final_item:
        items.append(final_item)
    return tuple(items)


def _parse_attribute_arguments(text: str) -> FrozenMap[str, CatalogValue] | None:
    attributes: dict[str, CatalogValue] = {}
    for item in _split_top_level_items(text):
        name, separator, value = item.partition("=")
        name = name.strip()
        value = value.strip()
        if not separator or not name or not value:
            return None
        if name in attributes:
            return None
        attributes[name] = _attribute_value(value)
    return FrozenMap(attributes)


def _attribute_value(value: str) -> CatalogValue:
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value


def _unique_references(
    references: Iterable[DependencyReference],
) -> tuple[DependencyReference, ...]:
    by_key: dict[tuple[object, ...], DependencyReference] = {}
    for reference in references:
        by_key.setdefault(reference.key, reference)
    return tuple(sorted(by_key.values(), key=lambda reference: reference.key))


def _candidate_ids_by_primitive_name(
    candidates: tuple[ImplementationCandidate, ...],
) -> FrozenMap[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source_primitive_name, []).append(
            candidate.candidate_id
        )
    return FrozenMap(
        (name, tuple(sorted(candidate_ids)))
        for name, candidate_ids in grouped.items()
    )


def _direct_primitive_dependencies(
    dependencies: tuple[CandidateDependencies, ...],
) -> FrozenMap[str, tuple[str, ...]]:
    grouped: dict[str, set[str]] = {}
    for item in dependencies:
        source_name = item.candidate.source_primitive_name
        grouped.setdefault(source_name, set()).update(item.direct_primitive_names)
    return FrozenMap(
        (source_name, tuple(sorted(dependency_names)))
        for source_name, dependency_names in grouped.items()
    )


def _required_primitive_names(
    graph: DependencyGraph,
    root_candidate_ids: tuple[str, ...],
) -> tuple[str, ...]:
    required: set[str] = set()
    stack: list[str] = []
    for candidate_id in reversed(root_candidate_ids):
        candidate = graph.dependencies_by_candidate_id[candidate_id].candidate
        stack.append(candidate.source_primitive_name)

    while stack:
        primitive_name = stack.pop()
        if primitive_name in required:
            continue
        required.add(primitive_name)
        for dependency_name in reversed(
            graph.direct_primitive_dependencies.get(primitive_name, ())
        ):
            if dependency_name == primitive_name:
                continue
            stack.append(dependency_name)
    return tuple(sorted(required))


def _cycle_diagnostics(
    graph: DependencyGraph,
    root_candidate_ids: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_cycles: set[tuple[str, ...]] = set()
    for candidate_id in root_candidate_ids:
        root_name = graph.dependencies_by_candidate_id[candidate_id].candidate.source_primitive_name
        _visit_cycles(
            graph,
            root_name,
            path=(),
            diagnostics=diagnostics,
            seen_cycles=seen_cycles,
        )
    return tuple(diagnostics)


def _visit_cycles(
    graph: DependencyGraph,
    primitive_name: str,
    *,
    path: tuple[str, ...],
    diagnostics: list[Diagnostic],
    seen_cycles: set[tuple[str, ...]],
) -> None:
    if primitive_name in path:
        cycle = (*path[path.index(primitive_name) :], primitive_name)
        if len(cycle) <= 2:
            return
        key = _canonical_cycle_key(cycle)
        if key not in seen_cycles:
            seen_cycles.add(key)
            diagnostics.append(_cycle_diagnostic(graph, cycle))
        return

    next_path = (*path, primitive_name)
    for dependency_name in graph.direct_primitive_dependencies.get(primitive_name, ()):
        if dependency_name == primitive_name:
            continue
        _visit_cycles(
            graph,
            dependency_name,
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
    graph: DependencyGraph,
    cycle: tuple[str, ...],
) -> Diagnostic:
    location = _primitive_location(graph, cycle[0])
    path = " -> ".join(cycle)
    return Diagnostic.error(
        "TSL-DEPENDENCY-CYCLE",
        f"primitive dependency cycle detected: {path}",
        location=location,
    )


def _primitive_location(
    graph: DependencyGraph,
    primitive_name: str,
) -> SourceLocation | None:
    for candidate in graph.selection.candidates:
        if candidate.source_primitive_name == primitive_name:
            return candidate.variant.source.declaration.source_span.location
    return None


def _unknown_dependency_diagnostic(
    candidate: ImplementationCandidate,
    reference: DependencyReference,
) -> Diagnostic:
    return Diagnostic.error(
        "TSL-DEPENDENCY-UNKNOWN-PRIMITIVE",
        f"candidate {candidate.candidate_id!r} references unknown primitive "
        f"{reference.target_primitive_name!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )


def _call_shape_diagnostic(
    candidate: ImplementationCandidate,
    segment: str,
) -> Diagnostic:
    rendered = segment or "<empty>"
    return Diagnostic.error(
        "TSL-DEPENDENCY-CALL-SHAPE",
        f"candidate {candidate.candidate_id!r} has unsupported primitive call "
        f"dependency syntax {rendered!r}",
        location=candidate.variant.source.declaration.source_span.location,
    )
