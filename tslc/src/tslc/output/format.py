"""Best-effort post-generation formatting of the written C++/Rust artifacts.

Runs `clang-format`/`rustfmt` in place over the generated tree. Cosmetic only: a missing
formatter or a formatter error is reported as a note, never a hard failure — generation must not
depend on a formatter being installed. Each tool discovers its style from the config shipped into
the generated project (`cpp/.clang-format`, `rust/rustfmt.toml`)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FormatReport:
    formatted: tuple[str, ...]  # e.g. ("cpp:42 files", "rust:30 files")
    notes: tuple[str, ...]  # skip/failure notes (tool missing, formatter error)


@dataclass(frozen=True, slots=True)
class _FormatBackendDriver:
    backend_id: str
    label: str
    patterns: tuple[str, ...]
    args: tuple[str, ...]


def format_generated(
    output_root: str | Path,
    backends: tuple[str, ...],
    *,
    clang_format: str = "clang-format",
    rustfmt: str = "rustfmt",
) -> FormatReport:
    root = Path(output_root)
    formatted: list[str] = []
    notes: list[str] = []
    tools = {"cpp": clang_format, "rust": rustfmt}
    requested = set(backends)
    for driver in _FORMAT_BACKEND_DRIVERS:
        if driver.backend_id not in requested:
            continue
        files = [
            path
            for pattern in driver.patterns
            for path in sorted(root.glob(pattern))
        ]
        _run(
            driver.label,
            tools[driver.backend_id],
            list(driver.args),
            files,
            formatted,
            notes,
        )
    return FormatReport(formatted=tuple(formatted), notes=tuple(notes))


def _run(
    label: str,
    tool: str,
    args: list[str],
    files: list[Path],
    formatted: list[str],
    notes: list[str],
) -> None:
    if not files:
        return
    executable = shutil.which(tool)
    if executable is None:
        notes.append(f"{tool} not found; skipped {label} formatting ({len(files)} files)")
        return
    completed = subprocess.run(
        [executable, *args, *(str(f) for f in files)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        first = (completed.stderr or completed.stdout).strip().splitlines()
        detail = f": {first[0]}" if first else ""
        notes.append(f"{tool} failed on {label}; left unformatted{detail}")
        return
    formatted.append(f"{label}:{len(files)} files")


_FORMAT_BACKEND_DRIVERS: tuple[_FormatBackendDriver, ...] = (
    _FormatBackendDriver(
        backend_id="cpp",
        label="cpp",
        patterns=("cpp/**/*.hpp", "cpp/**/*.cpp"),
        args=("-i",),
    ),
    _FormatBackendDriver(
        backend_id="rust",
        label="rust",
        patterns=("rust/**/*.rs",),
        args=("--edition", "2021"),
    ),
)
