"""Lazy repository-checkout context for maintenance commands.

Maintenance tools operate on the source checkout (tsldata/, supplementary/,
coverage evidence). Discovery is lazy: importing a maintenance module — e.g.
from an installed wheel outside a checkout — never probes the filesystem and
never raises. Repo-only commands resolve this context inside main() and turn a
missing checkout into an argparse error (exit code 2).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepoContext:
    """Well-known paths of one repository checkout."""

    root: Path

    @property
    def data_root(self) -> Path:
        return self.root / "tsldata"

    @property
    def machine_profiles_path(self) -> Path:
        return self.root / "supplementary" / "buildsystem" / "machine_profiles.json"

    @property
    def coverage_root(self) -> Path:
        return self.root / "coverage"

    @property
    def scratch_root(self) -> Path:
        return self.root / "tslctmp"


def find_repo_context(start: Path | None = None) -> RepoContext | None:
    """The enclosing checkout, or None when running outside one."""

    origin = start if start is not None else Path(__file__).resolve()
    for candidate in (origin, *origin.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return RepoContext(candidate)
    return None


def require_repo_context(parser: argparse.ArgumentParser) -> RepoContext:
    """The enclosing checkout, or a readable argparse error (exit code 2)."""

    context = find_repo_context()
    if context is None:
        parser.error(
            "this command needs a tslgen repository checkout "
            "(tsldata/ and tslc/src/ were not found above the installed package); "
            "run it from the repository or pass explicit paths"
        )
    return context


def resolve_corpus_paths(
    parser: argparse.ArgumentParser,
    sources: str | None,
    machine_profiles: str | None,
) -> tuple[Path, Path]:
    """Resolve --sources/--machine-profiles CLI values against the checkout.

    Explicit values always win; the checkout is required (argparse error,
    exit code 2) only for values the command line left unset.
    """

    if sources is not None and machine_profiles is not None:
        return Path(sources), Path(machine_profiles)
    context = require_repo_context(parser)
    return (
        Path(sources) if sources is not None else context.data_root,
        Path(machine_profiles)
        if machine_profiles is not None
        else context.machine_profiles_path,
    )


__all__ = (
    "RepoContext",
    "find_repo_context",
    "require_repo_context",
    "resolve_corpus_paths",
)
