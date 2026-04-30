from __future__ import annotations

from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
import unittest

from _helpers import assert_diagnostic
from tslgen.io.artifact_writer import (
    plan_artifact_writes,
    resolve_artifact_target,
    write_artifacts,
)
from tslgen.io.artifacts import Artifact, ArtifactSet, artifact_set_from_artifacts
from tslgen.io.write_report import ArtifactWriteOptions


def artifact(logical_path: str, content: str) -> Artifact:
    return Artifact(logical_path=PurePosixPath(logical_path), content=content)


def artifact_set(*items: Artifact) -> ArtifactSet:
    result = artifact_set_from_artifacts(items)
    if not result.is_ok:
        raise AssertionError(result.diagnostics)
    return result.unwrap()


class ArtifactWriterTests(unittest.TestCase):
    def test_resolves_targets_and_rejects_unsafe_paths(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            safe = resolve_artifact_target(root, PurePosixPath("nested/generated.hpp"))
            absolute = resolve_artifact_target(root, PurePosixPath("/escape.hpp"))
            parent = resolve_artifact_target(root, PurePosixPath("../escape.hpp"))

            self.assertTrue(safe.is_ok, safe.diagnostics)
            self.assertEqual(
                safe.unwrap(),
                root.resolve(strict=False) / "nested" / "generated.hpp",
            )
            self.assertFalse(absolute.is_ok)
            self.assertFalse(parent.is_ok)
            assert_diagnostic(
                self,
                absolute.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-UNSAFE-PATH",
                severity="error",
                path=root.resolve(strict=False).as_posix(),
            )
            self.assertIn("cannot be resolved safely", parent.diagnostics[0].message)

    def test_first_write_creates_parent_directories_and_reports_written(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = artifact_set(artifact("nested/generated.hpp", "hello\n"))

            report = write_artifacts(artifacts, ArtifactWriteOptions(root))

            target = root / "nested" / "generated.hpp"
            self.assertTrue(report.is_ok, report.diagnostics)
            self.assertEqual(target.read_text(encoding="utf-8"), "hello\n")
            self.assertEqual(report.written_paths, ("nested/generated.hpp",))
            self.assertEqual(report.skipped_paths, ())
            self.assertEqual(report.records[0].status, "written")
            self.assertEqual(report.digest_map["nested/generated.hpp"], artifacts.artifacts[0].content_digest)

    def test_repeated_write_skips_unchanged_content(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = artifact_set(artifact("generated.hpp", "same\n"))
            first = write_artifacts(artifacts, ArtifactWriteOptions(root))
            second = write_artifacts(artifacts, ArtifactWriteOptions(root))

            self.assertTrue(first.is_ok, first.diagnostics)
            self.assertTrue(second.is_ok, second.diagnostics)
            self.assertEqual(first.written_paths, ("generated.hpp",))
            self.assertEqual(second.skipped_paths, ("generated.hpp",))
            self.assertEqual(second.records[0].status, "skipped_unchanged")

    def test_changed_content_rewrites_file_and_updates_digest(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            old = artifact_set(artifact("generated.hpp", "old\n"))
            new = artifact_set(artifact("generated.hpp", "new\n"))
            old_report = write_artifacts(old, ArtifactWriteOptions(root))
            new_report = write_artifacts(new, ArtifactWriteOptions(root))

            self.assertTrue(old_report.is_ok, old_report.diagnostics)
            self.assertTrue(new_report.is_ok, new_report.diagnostics)
            self.assertEqual((root / "generated.hpp").read_text(encoding="utf-8"), "new\n")
            self.assertEqual(new_report.records[0].status, "written")
            self.assertNotEqual(
                old_report.digest_map["generated.hpp"],
                new_report.digest_map["generated.hpp"],
            )

    def test_dry_run_reports_would_write_without_mutation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = artifact_set(artifact("generated.hpp", "dry\n"))

            report = write_artifacts(
                artifacts,
                ArtifactWriteOptions(root, dry_run=True),
            )

            self.assertTrue(report.is_ok, report.diagnostics)
            self.assertEqual(report.would_write_paths, ("generated.hpp",))
            self.assertFalse((root / "generated.hpp").exists())

    def test_duplicate_targets_are_failed_before_writing(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = artifact("generated.hpp", "first\n")
            second = artifact("generated.hpp", "second\n")

            report = write_artifacts((first, second), ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            self.assertEqual(len(report.diagnostics), 2)
            self.assertEqual(
                tuple(diagnostic.code for diagnostic in report.diagnostics),
                (
                    "TSL-ARTIFACT-WRITE-DUPLICATE-TARGET",
                    "TSL-ARTIFACT-WRITE-DUPLICATE-TARGET",
                ),
            )
            self.assertEqual(report.failed_paths, ("generated.hpp", "generated.hpp"))
            self.assertFalse((root / "generated.hpp").exists())
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-DUPLICATE-TARGET",
                severity="error",
                path=(root.resolve(strict=False) / "generated.hpp").as_posix(),
            )

    def test_identical_duplicate_targets_are_failed_before_writing(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = artifact("generated.hpp", "same\n")
            second = artifact("generated.hpp", "same\n")

            report = write_artifacts((first, second), ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            self.assertEqual(len(report.diagnostics), 2)
            self.assertEqual(report.failed_paths, ("generated.hpp", "generated.hpp"))
            self.assertFalse((root / "generated.hpp").exists())
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-DUPLICATE-TARGET",
                severity="error",
            )

    def test_directory_conflict_fails_without_partial_write(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "generated.hpp").mkdir()
            artifacts = artifact_set(
                artifact("a.hpp", "safe\n"),
                artifact("generated.hpp", "conflict\n"),
            )

            report = write_artifacts(artifacts, ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            self.assertFalse((root / "a.hpp").exists())
            self.assertEqual(report.failed_paths, ("a.hpp", "generated.hpp"))
            self.assertEqual(report.would_write_paths, ())
            self.assertEqual(
                tuple(diagnostic.code for diagnostic in report.diagnostics),
                (
                    "TSL-ARTIFACT-WRITE-ABORTED",
                    "TSL-ARTIFACT-WRITE-TARGET-CONFLICT",
                ),
            )
            self.assertIn("is a directory", report.diagnostics[1].message)

    def test_existing_parent_file_conflict_is_reported(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "nested").write_text("not a directory", encoding="utf-8")
            artifacts = artifact_set(artifact("nested/generated.hpp", "content\n"))

            report = write_artifacts(artifacts, ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            self.assertEqual(len(report.diagnostics), 1)
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-TARGET-CONFLICT",
                severity="error",
                path=(root.resolve(strict=False) / "nested").as_posix(),
            )

    def test_output_root_file_conflict_is_reported(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp) / "not-a-directory"
            root.write_text("conflict", encoding="utf-8")
            artifacts = artifact_set(artifact("generated.hpp", "content\n"))

            report = write_artifacts(artifacts, ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-ROOT-CONFLICT",
                severity="error",
                path=root.resolve(strict=False).as_posix(),
            )
            self.assertIn("output root", report.diagnostics[0].message)

    def test_report_level_diagnostic_is_included_once(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp) / "not-a-directory"
            root.write_text("conflict", encoding="utf-8")

            report = write_artifacts((), ArtifactWriteOptions(root))

            self.assertFalse(report.is_ok)
            self.assertEqual(len(report.report_diagnostics), 1)
            self.assertEqual(len(report.diagnostics), 1)
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-ROOT-CONFLICT",
                severity="error",
                path=root.resolve(strict=False).as_posix(),
            )

    def test_symlink_escape_is_rejected_without_writing_outside_root(self) -> None:
        with TemporaryDirectory() as temp:
            temp_path = Path(temp)
            root = temp_path / "root"
            outside = temp_path / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                (root / "link").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink setup is unavailable: {exc}")

            report = write_artifacts(
                artifact_set(artifact("link/generated.hpp", "escape\n")),
                ArtifactWriteOptions(root),
            )

            self.assertFalse(report.is_ok)
            self.assertFalse((outside / "generated.hpp").exists())
            assert_diagnostic(
                self,
                report.diagnostics[0],
                code="TSL-ARTIFACT-WRITE-UNSAFE-PATH",
                severity="error",
            )

    def test_write_plans_are_deterministic(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            artifacts = artifact_set(
                artifact("b.hpp", "b\n"),
                artifact("a.hpp", "a\n"),
            )
            options = ArtifactWriteOptions(root, dry_run=True)

            first = plan_artifact_writes(artifacts, options)
            second = plan_artifact_writes(artifacts, options)

            self.assertEqual(first, second)
            self.assertEqual(
                tuple(record.logical_path.as_posix() for record in first.records),
                ("a.hpp", "b.hpp"),
            )


if __name__ == "__main__":
    unittest.main()
