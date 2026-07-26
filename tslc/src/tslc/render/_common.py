"""Shared helpers for generated-project rendering."""

from __future__ import annotations

from tslc.names import identifier_slug
from tslc.output.artifacts import Artifact


def slug(profile_name: str) -> str:
    """A safe C++/Rust/CMake identifier for a profile."""

    return identifier_slug(profile_name)


def text(logical_path: str, content: str, *, media_type: str) -> Artifact:
    return Artifact(
        logical_path=logical_path,
        content=content,
        media_type=media_type,
    )
