from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.candidates import CandidateSelection, select_implementation_candidates
from tslgen.analysis.dependencies import (
    discover_dependency_graph,
    plan_dependency_closure,
)
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "dependency-fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "dependency-fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "dependency-fixture.tsl") -> Catalog:
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


def planning_catalog(*primitive_paths: str) -> ReferenceValidatedCatalog:
    return reference_validated(
        catalog_from_paths(
            "tsldata/detail/flags.tsl",
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
            *primitive_paths,
        )
    )


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


class DependencyClosureTests(unittest.TestCase):
    def test_discovers_call_dependency_with_attributes(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=mov attrs[mask=zero]>(left, right));"
prim<v:=(v,v)> mov(left, right):
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

        graph = discover_dependency_graph(selection, referenced.catalog)

        self.assertTrue(graph.is_ok, graph.diagnostics)
        dependencies = graph.unwrap().candidate_dependencies[0]
        self.assertEqual(dependencies.direct_primitive_names, ("mov",))
        reference = dependencies.references[0]
        self.assertEqual(reference.target_primitive_name, "mov")
        self.assertEqual(reference.attributes.to_dict(), {"mask": "zero"})

    def test_resolves_self_reference_to_source_primitive(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> self_root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=@self[GenericVec]>(left, right));"
"""
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("self_root",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_dependency_closure(selection, referenced.catalog)

        self.assertTrue(closure.is_ok, closure.diagnostics)
        graph = closure.unwrap().graph
        reference = graph.candidate_dependencies[0].references[0]
        self.assertEqual(reference.raw_target, "@self")
        self.assertEqual(reference.target_primitive_name, "self_root")
        self.assertTrue(reference.is_self_reference)
        self.assertEqual(closure.unwrap().required_primitive_names, ("self_root",))

    def test_targeted_closure_records_unplanned_support_primitives(self) -> None:
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

        closure = plan_dependency_closure(selection, referenced.catalog)

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(closure.unwrap().required_primitive_names, ("helper", "root"))
        self.assertEqual(closure.unwrap().unplanned_primitive_names, ("helper",))

    def test_transitive_closure_uses_available_dependency_candidates(self) -> None:
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
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        root_ids = tuple(
            candidate.candidate_id
            for candidate in selection.candidates
            if candidate.source_primitive_name == "root"
        )

        closure = plan_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=root_ids,
        )

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertEqual(
            closure.unwrap().required_primitive_names,
            ("leaf", "middle", "root"),
        )
        self.assertEqual(closure.unwrap().unplanned_primitive_names, ())
        self.assertEqual(len(closure.unwrap().required_candidate_ids), 3)

    def test_unknown_dependency_is_diagnostic(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=missing_helper>(left, right));"
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

        closure = plan_dependency_closure(selection, referenced.catalog)

        self.assertFalse(closure.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-DEPENDENCY-UNKNOWN-PRIMITIVE"],
        )
        assert_diagnostic(
            self,
            closure.diagnostics[0],
            code="TSL-DEPENDENCY-UNKNOWN-PRIMITIVE",
            severity="error",
            path="dependency-fixture.tsl",
            line=1,
            column=1,
        )

    def test_dependency_cycle_is_diagnostic(self) -> None:
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
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        root_ids = tuple(
            candidate.candidate_id
            for candidate in selection.candidates
            if candidate.source_primitive_name == "root"
        )

        closure = plan_dependency_closure(
            selection,
            referenced.catalog,
            root_candidate_ids=root_ids,
        )

        self.assertFalse(closure.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in closure.diagnostics],
            ["TSL-DEPENDENCY-CYCLE"],
        )
        self.assertIn("root -> middle -> root", closure.diagnostics[0].message)

    def test_repository_masked_add_dependencies_are_discovered(self) -> None:
        referenced = planning_catalog(
            "tsldata/primitives/arithmetic/fundamental.tsl",
            "tsldata/primitives/load_store/construct.tsl",
        )
        selection = candidate_selection_for(
            referenced,
            SelectionRequest(
                primitive_names=("add",),
                template_names=("masked_binary",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        closure = plan_dependency_closure(selection, referenced.catalog)

        self.assertTrue(closure.is_ok, closure.diagnostics)
        self.assertIn("set_zero", closure.unwrap().required_primitive_names)

    def test_dependency_closure_output_is_deterministic(self) -> None:
        referenced = catalog_with_primitives(
            """prim<v:=(v,v)> root(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(call<primitive=middle>(call<primitive=leaf>(left, right), right));"
prim<v:=(v,v)> middle(left, right):
  tests []
  impls:
    scalar:
      si32:
        requires []
        implementation:
          tsil "emit_return(left);"
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
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )

        first = plan_dependency_closure(selection, referenced.catalog)
        second = plan_dependency_closure(selection, referenced.catalog)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            first.unwrap().required_primitive_names,
            second.unwrap().required_primitive_names,
        )
        self.assertEqual(
            tuple(
                reference.key
                for dependency in first.unwrap().graph.candidate_dependencies
                for reference in dependency.references
            ),
            tuple(
                reference.key
                for dependency in second.unwrap().graph.candidate_dependencies
                for reference in dependency.references
            ),
        )


if __name__ == "__main__":
    unittest.main()
