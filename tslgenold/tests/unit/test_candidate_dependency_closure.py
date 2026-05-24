from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.candidate_dependencies import (
    CandidateDependencyClosure,
    discover_candidate_dependency_graph,
    plan_candidate_dependency_closure,
)
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(
    text: str,
    *,
    path: str = "candidate-dependencies-fixture.tsl",
) -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(
    text: str,
    *,
    path: str = "candidate-dependencies-fixture.tsl",
) -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(
    text: str,
    *,
    path: str = "candidate-dependencies-fixture.tsl",
) -> Catalog:
    catalog = build_catalog(parse_text(text, path=path))
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


def catalog_from_paths(*paths: str) -> Catalog:
    sources = load_sources(
        SourceConfig(
            explicit_paths=tuple(Path(path) for path in paths),
            include_standard_library=False,
        )
    )
    if not sources.is_ok:
        raise AssertionError(sources.diagnostics)
    parsed = parse_sources(sources.unwrap())
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    catalog = build_catalog(parsed.unwrap())
    if not catalog.is_ok:
        raise AssertionError(catalog.diagnostics)
    return catalog.unwrap()


def base_catalog() -> Catalog:
    return catalog_from_paths(
        "tsldata/detail/flags.tsl",
        "tsldata/detail/types.tsl",
        "tsldata/detail/lane_sets.tsl",
        "tsldata/extensions/extension.tsl",
        "tsldata/detail/templates.tsl",
    )


def catalog_with_primitives(text: str) -> ReferenceValidatedCatalog:
    base = base_catalog()
    primitive_catalog = catalog_from_text(text)
    catalog = Catalog(
        type_groups=base.type_groups,
        lane_sets=base.lane_sets,
        extensions=base.extensions,
        templates=base.templates,
        primitives=primitive_catalog.primitives,
        entries=base.entries,
    )
    return reference_validated(catalog)


def reference_validated(catalog: Catalog) -> ReferenceValidatedCatalog:
    validated = validate_catalog(catalog)
    if not validated.is_ok:
        raise AssertionError(validated.diagnostics)
    referenced = validate_references(validated.unwrap())
    if not referenced.is_ok:
        raise AssertionError(referenced.diagnostics)
    return referenced.unwrap()


def candidate_selection_for(
    referenced: ReferenceValidatedCatalog,
    request: SelectionRequest,
) -> CandidateSelection:
    plan = plan_selection(referenced, request)
    if not plan.is_ok:
        raise AssertionError(plan.diagnostics)
    candidates = select_implementation_candidates(plan.unwrap(), referenced.catalog)
    if not candidates.is_ok:
        raise AssertionError(candidates.diagnostics)
    return candidates.unwrap()


def candidate_ids_for(
    selection: CandidateSelection,
    primitive_name: str,
) -> tuple[str, ...]:
    return tuple(
        candidate.candidate_id
        for candidate in selection.candidates
        if candidate.source_primitive_name == primitive_name
    )


def primitive_names_for(
    selection: CandidateSelection,
    candidate_ids: tuple[str, ...],
) -> tuple[str, ...]:
    by_id = selection.candidates_by_id
    return tuple(by_id[candidate_id].source_primitive_name for candidate_id in candidate_ids)


def simple_call_fixture(target: str) -> str:
    return f"""prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive={target}>(left, right));"
prim<v:=(v,v)> leaf(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""


class CandidateDependencyClosureTests(unittest.TestCase):
    def test_creates_candidate_edge_for_unambiguous_dependency(self) -> None:
        referenced = catalog_with_primitives(simple_call_fixture("leaf"))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        graph = discover_candidate_dependency_graph(selection, referenced.catalog)

        self.assertTrue(graph.is_ok, graph.diagnostics)
        candidate_graph = graph.unwrap()
        self.assertEqual(len(candidate_graph.edges), 1)
        edge = candidate_graph.edges[0]
        self.assertEqual(edge.source_candidate_id, candidate_ids_for(selection, "root")[0])
        self.assertEqual(edge.target_candidate_id, candidate_ids_for(selection, "leaf")[0])
        self.assertEqual(edge.reference.target_primitive_name, "leaf")

    def test_transitive_candidate_closure_is_candidate_precise(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=middle>(left, right));"
prim<v:=(v,v)> middle(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=leaf>(left, right));"
prim<v:=(v,v)> leaf(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "middle", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(
            primitive_names_for(selection, closure.unwrap().required_candidate_ids),
            ("leaf", "middle", "root"),
        )
        self.assertEqual(closure.unwrap().fallback_primitive_names, ())

    def test_exact_type_argument_resolves_one_target_candidate(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=leaf[si32]>(left, right));"
prim<v:=(v,v)> leaf(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        graph = discover_candidate_dependency_graph(selection, referenced.catalog)

        self.assertTrue(graph.is_ok, graph.diagnostics)
        edge = graph.unwrap().edges[0]
        target = selection.candidates_by_id[edge.target_candidate_id]
        self.assertEqual(target.type_tag, "si32")

    def test_ambiguous_target_candidates_are_preserved_as_fallback(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=leaf>(left, right));"
prim<v:=(v,v)> leaf(left, right):
  tests []
  impls:
    scalar:
      ?i32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-CANDIDATE-DEPENDENCY-AMBIGUOUS"],
        )
        assert_diagnostic(
            self,
            closure.diagnostics[0],
            code="TSL-CANDIDATE-DEPENDENCY-AMBIGUOUS",
            severity="warning",
            path="candidate-dependencies-fixture.tsl",
            line=1,
            column=1,
        )
        planned = closure.unwrap()
        self.assertEqual(planned.ambiguous_primitive_names, ("leaf",))
        self.assertEqual(planned.fallback_primitive_names, ("leaf",))
        self.assertEqual(
            primitive_names_for(selection, planned.required_candidate_ids),
            ("root",),
        )

    def test_missing_selected_candidate_is_preserved_as_unresolved(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=helper>(left, right));"
prim<v:=(v,v)> helper(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-CANDIDATE-DEPENDENCY-MISSING"],
        )
        self.assertEqual(closure.unwrap().unresolved_primitive_names, ("helper",))
        self.assertEqual(closure.unwrap().fallback_primitive_names, ("helper",))

    def test_unsupported_type_argument_keeps_primitive_fallback(self) -> None:
        referenced = catalog_with_primitives(simple_call_fixture("leaf[Vec]"))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-CANDIDATE-DEPENDENCY-UNSUPPORTED"],
        )
        self.assertEqual(closure.unwrap().unsupported_primitive_names, ("leaf",))
        self.assertEqual(closure.unwrap().fallback_primitive_names, ("leaf",))

    def test_candidate_specific_cycle_is_diagnostic(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=middle>(left, right));"
prim<v:=(v,v)> middle(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=root>(left, right));"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "middle"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertFalse(closure.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-CANDIDATE-DEPENDENCY-CYCLE"],
        )
        self.assertIn("candidate dependency cycle detected", closure.diagnostics[0].message)

    def test_candidate_specific_closure_output_is_deterministic(self) -> None:
        referenced = catalog_with_primitives(simple_call_fixture("leaf"))
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("root", "leaf"),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        first = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )
        second = plan_candidate_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=candidate_ids_for(selection, "root"),
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        first_closure: CandidateDependencyClosure = first.unwrap()
        second_closure = second.unwrap()
        self.assertEqual(
            tuple(edge.key for edge in first_closure.graph.edges),
            tuple(edge.key for edge in second_closure.graph.edges),
        )
        self.assertEqual(
            first_closure.required_candidate_ids,
            second_closure.required_candidate_ids,
        )
        self.assertEqual(
            first_closure.required_primitive_names,
            second_closure.required_primitive_names,
        )


if __name__ == "__main__":
    unittest.main()
