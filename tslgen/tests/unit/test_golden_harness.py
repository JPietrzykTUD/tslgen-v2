from __future__ import annotations

from pathlib import PurePosixPath
import unittest

from _golden import (
    assert_artifact_digest_map_stable,
    assert_artifact_matches_golden,
    assert_artifact_set_matches_golden,
    golden_artifact,
)
from tslgen.io.artifacts import Artifact, ArtifactSet


class GoldenHarnessTests(unittest.TestCase):
    def test_asserts_artifact_matches_golden_exactly(self) -> None:
        golden = golden_artifact(
            "generated.hpp",
            "golden",
            "cpp",
            "minimal_generated.hpp",
        )
        artifact_set = ArtifactSet(
            (
                Artifact(
                    logical_path=PurePosixPath("generated.hpp"),
                    content=golden.read_expected(),
                ),
            )
        )

        artifact = assert_artifact_matches_golden(self, artifact_set, golden)

        self.assertEqual(artifact.logical_path.as_posix(), "generated.hpp")

    def test_golden_comparison_does_not_normalize_content(self) -> None:
        golden = golden_artifact(
            "generated.hpp",
            "golden",
            "cpp",
            "minimal_generated.hpp",
        )
        artifact_set = ArtifactSet(
            (
                Artifact(
                    logical_path=PurePosixPath("generated.hpp"),
                    content=f"{golden.read_expected()} ",
                ),
            )
        )

        with self.assertRaises(AssertionError):
            assert_artifact_matches_golden(self, artifact_set, golden)

    def test_asserts_artifact_set_paths_and_digest_determinism(self) -> None:
        golden = golden_artifact(
            "generated.hpp",
            "golden",
            "cpp",
            "minimal_generated.hpp",
        )
        first = ArtifactSet(
            (
                Artifact(
                    logical_path=PurePosixPath("generated.hpp"),
                    content=golden.read_expected(),
                ),
            )
        )
        second = ArtifactSet(
            (
                Artifact(
                    logical_path=PurePosixPath("generated.hpp"),
                    content=golden.read_expected(),
                ),
            )
        )

        assert_artifact_set_matches_golden(self, first, (golden,))
        digests = assert_artifact_digest_map_stable(self, first, second)

        self.assertIn("generated.hpp", digests)


if __name__ == "__main__":
    unittest.main()
