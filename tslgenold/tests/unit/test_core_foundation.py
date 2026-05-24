from __future__ import annotations

import unittest
from pathlib import Path

from _helpers import assert_diagnostic
from tslgen.core.diagnostics import Diagnostic, SourceLocation, has_errors, sort_diagnostics
from tslgen.core.frozen_map import FrozenMap
from tslgen.core.ordering import stable_sort_key, stable_sorted
from tslgen.core.result import Result, ResultError


class DiagnosticTests(unittest.TestCase):
    def test_diagnostic_construction_preserves_public_fields(self) -> None:
        location = SourceLocation(Path("data/example.tsl"), line=3, column=5)
        diagnostic = Diagnostic.error(
            "TSL001",
            "invalid field 'mask'; expected one of zero, pass_through",
            location=location,
            notes=("primitive add",),
        )

        assert_diagnostic(
            self,
            diagnostic,
            code="TSL001",
            severity="error",
            path="data/example.tsl",
            line=3,
            column=5,
        )
        self.assertEqual(diagnostic.message, "invalid field 'mask'; expected one of zero, pass_through")
        self.assertEqual(diagnostic.notes, ("primitive add",))

    def test_source_location_is_one_based(self) -> None:
        with self.assertRaises(ValueError):
            SourceLocation(Path("bad.tsl"), line=0, column=1)
        with self.assertRaises(ValueError):
            SourceLocation(Path("bad.tsl"), line=1, column=0)

    def test_diagnostics_sort_by_location_severity_and_code(self) -> None:
        diagnostics = (
            Diagnostic.warning("W002", "unlocated warning"),
            Diagnostic.warning(
                "W001",
                "later location",
                location=SourceLocation(Path("b.tsl"), line=1, column=1),
            ),
            Diagnostic.info(
                "I001",
                "first location",
                location=SourceLocation(Path("a.tsl"), line=1, column=2),
            ),
            Diagnostic.error(
                "E001",
                "same location before warning",
                location=SourceLocation(Path("a.tsl"), line=1, column=2),
            ),
        )

        ordered = sort_diagnostics(diagnostics)

        self.assertEqual([diagnostic.code for diagnostic in ordered], ["E001", "I001", "W001", "W002"])
        self.assertTrue(has_errors(ordered))


class ResultTests(unittest.TestCase):
    def test_successful_result_contains_value_and_warning_diagnostics(self) -> None:
        warning = Diagnostic.warning("W001", "kept as non-fatal context")
        result = Result.ok("catalog", diagnostics=(warning,))

        self.assertTrue(result.is_ok)
        self.assertFalse(result.is_error)
        self.assertEqual(result.unwrap(), "catalog")
        self.assertEqual(result.map(str.upper).unwrap(), "CATALOG")

    def test_successful_result_rejects_error_diagnostics(self) -> None:
        with self.assertRaises(ValueError):
            Result.ok("catalog", diagnostics=(Diagnostic.error("E001", "fatal"),))

    def test_failed_result_requires_error_and_raises_on_unwrap(self) -> None:
        error = Diagnostic.error("E001", "fatal")
        result: Result[str] = Result.failure((error,))

        self.assertFalse(result.is_ok)
        self.assertTrue(result.is_error)
        self.assertFalse(result.has_value)
        self.assertEqual(result.value_or("fallback"), "fallback")
        with self.assertRaises(ResultError) as raised:
            result.unwrap()
        self.assertEqual(raised.exception.diagnostics, (error,))

    def test_failed_result_rejects_warning_only_diagnostics(self) -> None:
        with self.assertRaises(ValueError):
            Result.failure((Diagnostic.warning("W001", "not fatal"),))


class FrozenMapTests(unittest.TestCase):
    def test_frozen_map_iteration_is_deterministic(self) -> None:
        first = FrozenMap([("b", 2), ("a", 1), ("c", 3)])
        second = FrozenMap([("c", 3), ("b", 2), ("a", 1)])

        self.assertEqual(tuple(first.items()), (("a", 1), ("b", 2), ("c", 3)))
        self.assertEqual(tuple(first.items()), tuple(second.items()))
        self.assertEqual(first, second)

    def test_frozen_map_is_immutable(self) -> None:
        mapping = FrozenMap({"a": 1})

        with self.assertRaises(TypeError):
            mapping["b"] = 2  # type: ignore[index]
        with self.assertRaises(AttributeError):
            mapping._items = ()  # type: ignore[misc]

    def test_frozen_map_rejects_duplicate_keys(self) -> None:
        with self.assertRaises(ValueError):
            FrozenMap([("a", 1), ("a", 2)])

    def test_frozen_map_hashes_when_values_are_hashable(self) -> None:
        self.assertEqual(hash(FrozenMap({"a": 1})), hash(FrozenMap({"a": 1})))


class OrderingTests(unittest.TestCase):
    def test_stable_sorted_returns_tuple_with_common_value_ordering(self) -> None:
        values = (Path("b.tsl"), None, "x", Path("a.tsl"), 2, False, True)

        ordered = stable_sorted(values)

        self.assertEqual(ordered, (None, False, True, 2, "x", Path("a.tsl"), Path("b.tsl")))

    def test_stable_sort_key_rejects_unsupported_objects(self) -> None:
        class Unsupported:
            pass

        with self.assertRaisesRegex(TypeError, "unsupported stable sort key type"):
            stable_sort_key(Unsupported())


if __name__ == "__main__":
    unittest.main()
