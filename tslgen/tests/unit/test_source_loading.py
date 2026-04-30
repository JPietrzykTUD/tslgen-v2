from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _helpers import assert_diagnostic
from tslgen.config.model import SourceConfig
from tslgen.io.sources import SourceKind, load_sources


class SourceLoadingTests(unittest.TestCase):
    def test_loads_explicit_source_file_without_parsing(self) -> None:
        with TemporaryDirectory() as directory:
            source_path = Path(directory) / "one.tsl"
            source_text = "not parsed yet\nprim<v:=()> noop():\n"
            source_path.write_text(source_text, encoding="utf-8")

            result = load_sources(SourceConfig.explicit((source_path,)))

        self.assertTrue(result.is_ok)
        source_set = result.unwrap()
        self.assertEqual(len(source_set.documents), 1)
        document = source_set.documents[0]
        self.assertEqual(document.path, source_path.resolve())
        self.assertEqual(document.text, source_text)
        self.assertEqual(document.digest, sha256(source_text.encode("utf-8")).hexdigest())
        self.assertEqual(document.kind, SourceKind.TSL)
        self.assertEqual(tuple(source_set), (document,))
        with self.assertRaises(AttributeError):
            document.text = "changed"  # type: ignore[misc]

    def test_loads_standard_tsldata_tree_in_deterministic_order(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "tsldata"
            files = {
                "primitives/z/math.tsl": "prim\n",
                "extensions/extension.tsl": "extension\n",
                "detail/types.tsl": "types\n",
                "detail/lane_sets.tsl": "lanes\n",
                "detail/flags.tsl": "flags\n",
                "detail/templates.tsl": "templates\n",
                "detail/lang/types/types_cpp.tsl": "types cpp\n",
                "detail/lang/translate_cpp.tsl": "translate cpp\n",
            }
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            result = load_sources(SourceConfig.standard_library(root))

        self.assertTrue(result.is_ok)
        source_set = result.unwrap()
        self.assertEqual(
            [document.logical_path.as_posix() for document in source_set.documents],
            sorted(files),
        )
        self.assertEqual(
            [document.kind for document in source_set.documents],
            [
                SourceKind.FLAGS,
                SourceKind.LANE_SETS,
                SourceKind.TRANSLATION,
                SourceKind.LANGUAGE_TYPES,
                SourceKind.TEMPLATES,
                SourceKind.TYPE_GROUPS,
                SourceKind.EXTENSION,
                SourceKind.PRIMITIVE,
            ],
        )

    def test_orders_explicit_source_files_deterministically(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "a.tsl"
            second = root / "b.tsl"
            first.write_text("a\n", encoding="utf-8")
            second.write_text("b\n", encoding="utf-8")

            result = load_sources(SourceConfig.explicit((second, first)))

        self.assertTrue(result.is_ok)
        self.assertEqual(
            [document.path.name for document in result.unwrap().documents],
            ["a.tsl", "b.tsl"],
        )

    def test_reports_missing_explicit_file(self) -> None:
        missing_path = Path("/tmp/tslgen-missing-source.tsl")

        result = load_sources(SourceConfig.explicit((missing_path,)))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-SRC-MISSING",
            severity="error",
            path=missing_path.as_posix(),
            line=1,
            column=1,
        )
        self.assertIn("does not exist", result.diagnostics[0].message)

    def test_reports_missing_standard_source_directory(self) -> None:
        missing_root = Path("/tmp/tslgen-missing-standard-root")

        result = load_sources(SourceConfig.standard_library(missing_root))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-SRC-STANDARD-DIR-MISSING",
            severity="error",
            path=missing_root.as_posix(),
            line=1,
            column=1,
        )

    def test_reports_duplicate_logical_source_path(self) -> None:
        with TemporaryDirectory() as directory:
            source_path = Path(directory) / "dupe.tsl"
            source_path.write_text("duplicate\n", encoding="utf-8")

            result = load_sources(SourceConfig.explicit((source_path, source_path.resolve())))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-SRC-DUPLICATE",
            severity="error",
            path=source_path.resolve().as_posix(),
            line=1,
            column=1,
        )
        self.assertIn("first loaded", result.diagnostics[0].message)

    def test_reports_unsupported_explicit_file_extension(self) -> None:
        with TemporaryDirectory() as directory:
            source_path = Path(directory) / "not-source.txt"
            source_path.write_text("nope\n", encoding="utf-8")

            result = load_sources(SourceConfig.explicit((source_path,)))

        self.assertFalse(result.is_ok)
        self.assertEqual(len(result.diagnostics), 1)
        assert_diagnostic(
            self,
            result.diagnostics[0],
            code="TSL-SRC-UNSUPPORTED-EXTENSION",
            severity="error",
            path=source_path.resolve().as_posix(),
            line=1,
            column=1,
        )


if __name__ == "__main__":
    unittest.main()
