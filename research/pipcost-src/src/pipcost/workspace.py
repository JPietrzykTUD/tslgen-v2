"""Workspace and scratch-path ownership."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def discover_workspace(start: Path | None = None) -> Path:
    candidate = (start or Path(__file__)).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (
            (parent / "CHARTER.md").is_file()
            and (parent / "tslc").is_dir()
            and (parent / "tsldata").is_dir()
        ):
            return parent
    raise RuntimeError("could not locate repository workspace")


def require_below(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.resolve()
    allowed = root.resolve()
    if resolved == allowed or allowed in resolved.parents:
        return resolved
    raise ValueError(f"{label} must remain below {allowed}, got {resolved}")


@dataclass(frozen=True, slots=True)
class WorkspacePaths:
    root: Path
    prototype_root: Path
    scratch_root: Path

    @classmethod
    def create(cls, scratch_root: Path | str | None = None) -> "WorkspacePaths":
        root = discover_workspace()
        allowed = root / "tslctmp" / "pipcost"
        chosen = allowed if scratch_root is None else Path(scratch_root)
        if not chosen.is_absolute():
            chosen = root / chosen
        return cls(
            root=root,
            prototype_root=root / "research" / "pipcost-src",
            scratch_root=require_below(chosen, allowed, label="scratch root"),
        )

    def output_path(self, *parts: str) -> Path:
        return require_below(
            self.scratch_root.joinpath(*parts),
            self.scratch_root,
            label="output path",
        )
