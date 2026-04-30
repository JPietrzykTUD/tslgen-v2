from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest import TestCase

from _helpers import fixture_path
from tslgen.core.frozen_map import FrozenMap
from tslgen.io.artifacts import Artifact, ArtifactSet, artifact_digest_map


@dataclass(frozen=True, slots=True)
class GoldenArtifact:
    logical_path: str
    fixture_parts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.logical_path:
            raise ValueError("golden artifact logical path must be non-empty")
        if not self.fixture_parts:
            raise ValueError("golden artifact fixture path must be non-empty")

    @property
    def fixture_path(self) -> Path:
        return fixture_path(*self.fixture_parts)

    def read_expected(self) -> str:
        return self.fixture_path.read_text(encoding="utf-8")


def golden_artifact(logical_path: str, *fixture_parts: str) -> GoldenArtifact:
    return GoldenArtifact(logical_path=logical_path, fixture_parts=fixture_parts)


def assert_artifact_matches_golden(
    test_case: TestCase,
    artifact_set: ArtifactSet,
    golden: GoldenArtifact,
) -> Artifact:
    test_case.assertIn(golden.logical_path, artifact_set.artifacts_by_path)
    artifact = artifact_set.artifacts_by_path[golden.logical_path]
    test_case.assertEqual(artifact.content, golden.read_expected())
    return artifact


def assert_artifact_set_matches_golden(
    test_case: TestCase,
    artifact_set: ArtifactSet,
    goldens: tuple[GoldenArtifact, ...],
) -> None:
    expected_paths = tuple(sorted(golden.logical_path for golden in goldens))
    actual_paths = tuple(
        artifact.logical_path.as_posix() for artifact in artifact_set.artifacts
    )
    test_case.assertEqual(actual_paths, expected_paths)
    for golden in goldens:
        assert_artifact_matches_golden(test_case, artifact_set, golden)


def assert_artifact_digest_map_stable(
    test_case: TestCase,
    first: ArtifactSet,
    second: ArtifactSet,
) -> FrozenMap[str, str]:
    first_digests = artifact_digest_map(first)
    second_digests = artifact_digest_map(second)
    test_case.assertEqual(first_digests, second_digests)
    return first_digests
