"""Loaded static compiler resources.

The package ships a grammar and render templates as resources, but parser and
render stages consume already-loaded values so they remain replayable from
explicit inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
import string

_GRAMMAR_PACKAGE = "tslc.syntax.grammar"
_GRAMMAR_FILE = "tsl_data.lark"
_RENDER_ASSETS_PACKAGE = "tslc.backend.assets"


class _AtTemplate(string.Template):
    # Generated build files / sources use `${VAR}` (CMake) and `{ }`
    # (C++/Rust) natively, so the substitution delimiter is `@`.
    delimiter = "@"


@dataclass(frozen=True, slots=True)
class RenderAssets:
    files: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "files",
            MappingProxyType(dict(sorted(self.files.items()))),
        )

    def text(self, asset_name: str) -> str:
        try:
            return self.files[asset_name]
        except KeyError as error:
            raise KeyError(f"render asset {asset_name!r} was not loaded") from error

    def fill(self, asset_name: str, **holes: str) -> str:
        return _AtTemplate(self.text(asset_name)).substitute(holes)


def load_default_tsl_grammar() -> str:
    return (
        resources.files(_GRAMMAR_PACKAGE)
        .joinpath(_GRAMMAR_FILE)
        .read_text(encoding="utf-8")
    )


def load_default_render_assets() -> RenderAssets:
    root = resources.files(_RENDER_ASSETS_PACKAGE)
    files = {
        entry.name: entry.read_text(encoding="utf-8")
        for entry in sorted(root.iterdir(), key=lambda item: item.name)
        if entry.is_file()
    }
    return RenderAssets(files)


__all__ = [
    "RenderAssets",
    "load_default_render_assets",
    "load_default_tsl_grammar",
]
