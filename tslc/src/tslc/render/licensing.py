"""License notices for generated project artifacts."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.backend.capability import BackendCapability
from tslc.compiler_assets import RenderAssets
from tslc.output.artifacts import Artifact

GENERATED_COPYRIGHT = "Copyright 2026 Johannes Pietrzyk and TSL(c) contributors"

_SHORT_NOTICE_LINES = (
    GENERATED_COPYRIGHT,
    "",
    'Licensed under the Apache License, Version 2.0 (the "License");',
    "you may not use this file except in compliance with the License.",
    "You may obtain a copy of the License at",
    "",
    "    http://www.apache.org/licenses/LICENSE-2.0",
    "",
    "Unless required by applicable law or agreed to in writing, software",
    'distributed under the License is distributed on an "AS IS" BASIS,',
    "WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.",
    "See the License for the specific language governing permissions and",
    "limitations under the License.",
)

_C_STYLE_SUFFIXES = (".cpp", ".hpp", ".h", ".c")
_HASH_STYLE_SUFFIXES = (".cmake", ".toml", ".clang-format")
_RUST_STYLE_SUFFIXES = (".rs",)


def generated_license_artifacts(
    backends: Iterable[BackendCapability],
    assets: RenderAssets,
) -> tuple[Artifact, ...]:
    license_text = assets.text("apache-2.0.txt")
    return tuple(
        Artifact(f"{backend.root_path}/LICENSE", license_text, "text/plain")
        for backend in backends
    )


def add_generated_license_notice(artifact: Artifact) -> Artifact:
    notice = _notice_for_path(artifact.logical_path)
    if notice is None or artifact.content.startswith(notice):
        return artifact
    if _must_preserve_leading_guard(artifact):
        content = f"{artifact.content.rstrip()}\n\n{notice}"
    else:
        content = f"{notice}{artifact.content}"
    return Artifact(
        logical_path=artifact.logical_path,
        content=content,
        media_type=artifact.media_type,
        metadata=artifact.metadata,
    )


def _notice_for_path(path: str) -> str | None:
    if path.endswith(_C_STYLE_SUFFIXES):
        return _c_style_notice()
    if path.endswith(_RUST_STYLE_SUFFIXES):
        return _line_notice("//")
    if path.endswith(_HASH_STYLE_SUFFIXES) or path == "cpp/CMakeLists.txt":
        return _line_notice("#")
    return None


def _must_preserve_leading_guard(artifact: Artifact) -> bool:
    return artifact.logical_path.endswith(_C_STYLE_SUFFIXES) and artifact.content.startswith(
        "#if "
    )


def _c_style_notice() -> str:
    body = "\n".join(f" * {line}" if line else " *" for line in _SHORT_NOTICE_LINES)
    return f"/*\n{body}\n */\n\n"


def _line_notice(prefix: str) -> str:
    lines = (f"{prefix} {line}" if line else prefix for line in _SHORT_NOTICE_LINES)
    return "\n".join(lines) + "\n\n"


__all__ = [
    "GENERATED_COPYRIGHT",
    "add_generated_license_notice",
    "generated_license_artifacts",
]
