from __future__ import annotations

from pathlib import Path
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.core.diagnostics import SourceLocation, SourceSpan
from tslgen.core.frozen_map import FrozenMap
from tslgen.domain.catalog import Catalog, build_catalog
from tslgen.domain.generation_rules import (
    SELECTED_SCALAR_SIZE_BYTES_GENERATION_TYPE_TAGS,
    ScalarSizeBytesGenerationRule,
    build_scalar_size_bytes_generation_rule_set,
    build_scalar_size_bytes_generation_rule_set_from_catalog,
)
from tslgen.domain.types import TypeGroup
from tslgen.io.sources import load_sources
from tslgen.syntax.parser import parse_sources


EXPECTED_SIZE_RULES = (
    ScalarSizeBytesGenerationRule("si8", 1),
    ScalarSizeBytesGenerationRule("ui8", 1),
    ScalarSizeBytesGenerationRule("si16", 2),
    ScalarSizeBytesGenerationRule("ui16", 2),
    ScalarSizeBytesGenerationRule("si32", 4),
    ScalarSizeBytesGenerationRule("ui32", 4),
    ScalarSizeBytesGenerationRule("f32", 4),
    ScalarSizeBytesGenerationRule("si64", 8),
    ScalarSizeBytesGenerationRule("ui64", 8),
    ScalarSizeBytesGenerationRule("f64", 8),
)


def source_span(line: int = 1) -> SourceSpan:
    return SourceSpan(SourceLocation(Path("scalar-size-rule-fixture.tsl"), line, 3))


def type_group(
    name: str,
    members: tuple[str, ...] | None = None,
    *,
    line: int = 1,
) -> TypeGroup:
    group_members = (name,) if members is None else members
    return TypeGroup(
        name=name,
        members=group_members,
        fields=FrozenMap({"types": group_members}),
        source_span=source_span(line),
    )


def accepted_singleton_groups() -> tuple[TypeGroup, ...]:
    return tuple(
        type_group(type_tag, line=index)
        for index, type_tag in enumerate(
            SELECTED_SCALAR_SIZE_BYTES_GENERATION_TYPE_TAGS,
            start=2,
        )
    )


def catalog_type_groups_from_tsldata() -> tuple[TypeGroup, ...]:
    return catalog_from_tsldata_types().type_groups


def catalog_from_tsldata_types() -> Catalog:
    sources = load_sources(
        SourceConfig(
            explicit_paths=(Path("tsldata/detail/types.tsl"),),
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


class ScalarSizeBytesGenerationRuleSourceTests(unittest.TestCase):
    def test_builds_accepted_rule_set_from_tsldata_type_groups(self) -> None:
        result = build_scalar_size_bytes_generation_rule_set(
            catalog_type_groups_from_tsldata()
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        rule_set = result.unwrap()
        self.assertEqual(rule_set.rules, EXPECTED_SIZE_RULES)
        self.assertEqual(
            rule_set.supported_type_tags,
            SELECTED_SCALAR_SIZE_BYTES_GENERATION_TYPE_TAGS,
        )

    def test_builds_accepted_rule_set_from_catalog(self) -> None:
        result = build_scalar_size_bytes_generation_rule_set_from_catalog(
            catalog_from_tsldata_types()
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(result.unwrap().rules, EXPECTED_SIZE_RULES)

    def test_catalog_rule_set_construction_is_deterministic(self) -> None:
        catalog = catalog_from_tsldata_types()

        first = build_scalar_size_bytes_generation_rule_set_from_catalog(catalog)
        second = build_scalar_size_bytes_generation_rule_set_from_catalog(catalog)

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_rule_ordering_is_deterministic_from_unsorted_type_groups(self) -> None:
        first = build_scalar_size_bytes_generation_rule_set(
            tuple(reversed(accepted_singleton_groups()))
        )
        second = build_scalar_size_bytes_generation_rule_set(
            accepted_singleton_groups()
        )

        self.assertTrue(first.is_ok, first.diagnostics)
        self.assertTrue(second.is_ok, second.diagnostics)
        self.assertEqual(first.unwrap().rules, EXPECTED_SIZE_RULES)
        self.assertEqual(first.unwrap(), second.unwrap())

    def test_reports_missing_singleton_tags(self) -> None:
        groups = tuple(
            group for group in accepted_singleton_groups() if group.name != "f64"
        )

        result = build_scalar_size_bytes_generation_rule_set(groups)

        self.assertFalse(result.is_ok)
        self.assertIn(
            "TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-MISSING",
            {diagnostic.code for diagnostic in result.diagnostics},
        )
        self.assertTrue(
            any("f64" in diagnostic.message for diagnostic in result.diagnostics)
        )

    def test_reports_inconsistent_singleton_rule_data(self) -> None:
        groups = tuple(
            type_group("f32", ("f64",), line=7)
            if group.name == "f32"
            else group
            for group in accepted_singleton_groups()
        )

        result = build_scalar_size_bytes_generation_rule_set(groups)

        self.assertFalse(result.is_ok)
        diagnostic = next(
            diagnostic
            for diagnostic in result.diagnostics
            if diagnostic.code == "TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-INCONSISTENT"
        )
        assert_diagnostic(
            self,
            diagnostic,
            code="TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-INCONSISTENT",
            severity="error",
            path="scalar-size-rule-fixture.tsl",
            line=7,
            column=3,
        )
        self.assertIn("f32", diagnostic.message)

    def test_rejects_wildcard_and_group_selectors_as_selected_tags(self) -> None:
        groups = accepted_singleton_groups() + (
            type_group("?i?", ("si8", "ui8")),
            type_group("f?", ("f32", "f64")),
            type_group("arith", ("si32", "ui32", "f32", "f64")),
            type_group("dword", ("si32", "ui32", "f32")),
        )

        for type_tag in ("?i?", "f?", "arith", "dword"):
            with self.subTest(type_tag=type_tag):
                result = build_scalar_size_bytes_generation_rule_set(
                    groups,
                    selected_type_tags=(type_tag,),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-DOMAIN-GEN-SIZE-RULE-TAG-UNSUPPORTED",
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

    def test_rejects_unsupported_pointer_mask_and_concrete_looking_tags(self) -> None:
        for type_tag in ("ptr", "mask", "imask", "si128", "f128"):
            with self.subTest(type_tag=type_tag):
                result = build_scalar_size_bytes_generation_rule_set(
                    accepted_singleton_groups() + (type_group(type_tag),),
                    selected_type_tags=(type_tag,),
                )

                self.assertFalse(result.is_ok)
                assert_diagnostic(
                    self,
                    result.diagnostics[0],
                    code="TSL-DOMAIN-GEN-SIZE-RULE-TAG-UNSUPPORTED",
                    severity="error",
                )
                self.assertIn(type_tag, result.diagnostics[0].message)

    def test_rejects_unknown_selected_tags(self) -> None:
        result = build_scalar_size_bytes_generation_rule_set(
            accepted_singleton_groups(),
            selected_type_tags=("mystery",),
        )

        self.assertFalse(result.is_ok)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-DOMAIN-GEN-SIZE-RULE-TAG-UNKNOWN",
            severity="error",
        )
        self.assertIn("mystery", result.diagnostics[0].message)

    def test_subset_rule_set_does_not_include_default_floats(self) -> None:
        result = build_scalar_size_bytes_generation_rule_set(
            accepted_singleton_groups(),
            selected_type_tags=("si32",),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertEqual(
            result.unwrap().rules,
            (ScalarSizeBytesGenerationRule("si32", 4),),
        )

    def test_concrete_looking_unselected_catalog_tags_do_not_become_rules(
        self,
    ) -> None:
        result = build_scalar_size_bytes_generation_rule_set(
            accepted_singleton_groups() + (type_group("si128"), type_group("f128")),
        )

        self.assertTrue(result.is_ok, result.diagnostics)
        self.assertNotIn("si128", result.unwrap().supported_type_tags)
        self.assertNotIn("f128", result.unwrap().supported_type_tags)


if __name__ == "__main__":
    unittest.main()
