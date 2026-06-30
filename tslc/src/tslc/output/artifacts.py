"""In-memory artifact values."""

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class Artifact:
    logical_path: str
    content: str
    media_type: str
    metadata: tuple[ArtifactMetadata, ...] = ()

    @property
    def digest(self) -> str:
        return sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactSet:
    artifacts: tuple[Artifact, ...]

    @classmethod
    def create(cls, artifacts: tuple[Artifact, ...]) -> "ArtifactSet":
        return cls(artifacts=tuple(sorted(artifacts, key=lambda item: item.logical_path)))

    def digest_manifest(self) -> tuple[tuple[str, str], ...]:
        return tuple((artifact.logical_path, artifact.digest) for artifact in self.artifacts)
