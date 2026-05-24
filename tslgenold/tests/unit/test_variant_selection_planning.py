from __future__ import annotations

from pathlib import Path, PurePosixPath
import unittest

from _helpers import assert_diagnostic
from tslgen.analysis.expansion import PrimitiveVariant, expand_variants
from tslgen.analysis.requirements import normalize_flags
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.io.sources import SourceDocument, SourceKind, load_sources
from tslgen.syntax.ast import ParsedDocumentSet
from tslgen.syntax.parser import parse_document, parse_sources
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import ReferenceValidatedCatalog, validate_references


def source_document(text: str, *, path: str = "fixture.tsl") -> SourceDocument:
    return SourceDocument(
        path=Path(path),
        logical_path=PurePosixPath(path),
        text=text,
        digest="fixture",
        kind=SourceKind.TSL,
    )


def parse_text(text: str, *, path: str = "fixture.tsl") -> ParsedDocumentSet:
    parsed = parse_document(source_document(text, path=path))
    if not parsed.is_ok:
        raise AssertionError(parsed.diagnostics)
    return ParsedDocumentSet((parsed.unwrap(),))


def catalog_from_text(text: str, *, path: str = "fixture.tsl") -> Catalog:
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


def reference_validated(catalog: Catalog) -> ReferenceValidatedCatalog:
    validated = validate_catalog(catalog)
    if not validated.is_ok:
        raise AssertionError(validated.diagnostics)
    referenced = validate_references(validated.unwrap())
    if not referenced.is_ok:
        raise AssertionError(referenced.diagnostics)
    return referenced.unwrap()


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


def variant_values(
    variants: tuple[PrimitiveVariant, ...],
    primitive_name: str,
    template_name: str,
    *attribute_names: str,
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(variant.attributes[name] for name in attribute_names)
        for variant in variants
        if variant.primitive_name == primitive_name
        and variant.template_name == template_name
    )


class VariantSelectionPlanningTests(unittest.TestCase):
    def test_expands_aligned_wildcard_in_stable_order(self) -> None:
        expanded = expand_variants(
            planning_catalog("tsldata/primitives/load_store/load.tsl")
        )

        self.assertTrue(expanded.is_ok, expanded.diagnostics)
        self.assertEqual(
            variant_values(expanded.unwrap().variants, "load", "load", "aligned"),
            ((True,), (False,)),
        )

    def test_expands_two_boolean_wildcards_in_stable_cartesian_order(self) -> None:
        expanded = expand_variants(
            planning_catalog("tsldata/primitives/load_store/store.tsl")
        )

        self.assertTrue(expanded.is_ok, expanded.diagnostics)
        self.assertEqual(
            variant_values(
                expanded.unwrap().variants,
                "store_mask",
                "store_mask",
                "aligned",
                "packed",
            ),
            (
                (True, True),
                (True, False),
                (False, True),
                (False, False),
            ),
        )

    def test_normalizes_flag_aliases_and_already_normalized_names(self) -> None:
        catalog = catalog_from_paths("tsldata/detail/flags.tsl")

        result = normalize_flags(catalog, ("sse4.2", "avx3f", "avx512f"))

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            tuple(flag.name for flag in result.unwrap()),
            ("avx512f", "sse4_2"),
        )

    def test_selection_plan_uses_explicit_extensions_and_forced_support_extensions(
        self,
    ) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                template_names=("load",),
                extension_names=("avx2",),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().allowed_extensions, ("avx2", "generic", "scalar"))
        self.assertEqual(len(result.unwrap().variants), 2)
        implementation_extensions = {
            plan.extension_selector.names for plan in result.unwrap().implementation_plans
        }
        self.assertIn(("avx512", "avx2", "sse"), implementation_extensions)
        self.assertIn(("generic", "oneAPIfpga"), implementation_extensions)
        self.assertIn(("scalar",), implementation_extensions)

    def test_selection_plan_autodetects_extensions_from_normalized_flags(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                template_names=("load",),
                cpu_flags=("sse2", "avx2", "avx512f", "avx512vl"),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().allowed_extensions,
            ("avx2", "avx2_vl", "avx512", "generic", "scalar", "sse", "sse_vl"),
        )

    def test_empty_allowed_extensions_allow_no_implementation_plans(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                template_names=("load",),
                include_support_extensions=False,
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().allowed_extensions, ())
        self.assertEqual(len(result.unwrap().variants), 2)
        self.assertEqual(result.unwrap().implementation_plans, ())

    def test_unknown_requested_primitive_is_diagnostic(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(primitive_names=("not_a_primitive",)),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-SELECT-UNKNOWN-PRIMITIVE"],
        )

    def test_unknown_requested_template_is_diagnostic(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                template_names=("not_a_template",),
            ),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-SELECT-UNKNOWN-TEMPLATE"],
        )

    def test_unknown_requested_extension_is_diagnostic(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                extension_names=("not_an_extension",),
            ),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-SELECT-UNKNOWN-EXTENSION"],
        )

    def test_unknown_requested_flag_is_diagnostic(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                cpu_flags=("not_a_flag",),
            ),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["TSL-FLAG-UNKNOWN"],
        )

    def test_plans_requirements_without_selecting_concrete_implementation(self) -> None:
        result = plan_selection(
            planning_catalog("tsldata/primitives/load_store/load.tsl"),
            SelectionRequest(
                primitive_names=("load",),
                template_names=("load",),
                extension_names=("avx2",),
            ),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        matching = [
            plan
            for plan in result.unwrap().implementation_plans
            if plan.extension_selector.names == ("avx512", "avx2", "sse")
            and plan.type_selector.names == ("?i?",)
        ]
        self.assertEqual(len(matching), 2)
        requirement_keys = {
            (
                requirement.extension_names,
                requirement.type_group_names,
                tuple(flag.name for flag in requirement.required_flags),
            )
            for plan in matching
            for requirement in plan.requirements
        }
        self.assertIn((("avx2",), ("?i?",), ("avx",)), requirement_keys)

    def test_all_unknown_extension_keyed_requires_selectors_are_diagnostics(self) -> None:
        base = catalog_from_paths(
            "tsldata/detail/flags.tsl",
            "tsldata/detail/types.tsl",
            "tsldata/detail/lane_sets.tsl",
            "tsldata/extensions/extension.tsl",
            "tsldata/detail/templates.tsl",
        )
        invalid = catalog_from_text(
            """prim<v:=(v,v)> bad_requires(left, right):
  tests []
  impls:
    [sse, avx2]:
      arith:
        requires:
          typo [avx]
          nope [sse]
        implementation:
          tsil "emit_return(left);"
""",
            path="bad-requires-plan.tsl",
        )
        catalog = Catalog(
            type_groups=base.type_groups,
            lane_sets=base.lane_sets,
            extensions=base.extensions,
            templates=base.templates,
            primitives=invalid.primitives,
            entries=base.entries,
        )
        referenced = reference_validated(catalog)

        result = plan_selection(
            referenced,
            SelectionRequest(
                primitive_names=("bad_requires",),
                extension_names=("sse",),
            ),
        )

        self.assertFalse(result.is_ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            [
                "TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
                "TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
            ],
        )
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-PLAN-REQUIRES-UNKNOWN-EXTENSION-SELECTOR",
            severity="error",
            path="bad-requires-plan.tsl",
            line=1,
            column=1,
        )

    def test_selection_plan_output_is_deterministic(self) -> None:
        catalog = planning_catalog("tsldata/primitives/load_store/load.tsl")
        request = SelectionRequest(
            primitive_names=("load",),
            template_names=("load",),
            extension_names=("avx2",),
        )

        first = plan_selection(catalog, request)
        second = plan_selection(catalog, request)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(
            tuple(variant.variant_id for variant in first.unwrap().variants),
            tuple(variant.variant_id for variant in second.unwrap().variants),
        )
        self.assertEqual(
            tuple(plan.key for plan in first.unwrap().implementation_plans),
            tuple(plan.key for plan in second.unwrap().implementation_plans),
        )


if __name__ == "__main__":
    unittest.main()
