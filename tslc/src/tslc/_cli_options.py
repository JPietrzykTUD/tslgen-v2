"""Shared CLI option parsing: CSV lists and NAME=VALUE toolchain overrides."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tslc.output.verify_model import BackendToolchain


def split_csv(value: str) -> tuple[str, ...]:
    """Split one comma-separated option value into stripped, non-empty items."""
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_assignments(values: Sequence[str], option: str) -> dict[str, str]:
    """Parse repeated ``NAME=VALUE`` option values, rejecting repeats and blanks."""
    assignments: dict[str, str] = {}
    for value in values:
        name, separator, setting = value.partition("=")
        name = name.strip()
        setting = setting.strip()
        if not separator or not name or not setting:
            raise ValueError(f"{option} expects NAME=VALUE, got {value!r}")
        if name in assignments:
            raise ValueError(f"{option} repeats name {name!r}")
        assignments[name] = setting
    return assignments


def merge_toolchains(
    configured: Mapping[str, BackendToolchain],
    compilers: Mapping[str, str],
    targets: Mapping[str, str],
    linkers: Mapping[str, str],
    compiler_capabilities: Mapping[str, str] | None = None,
) -> dict[str, BackendToolchain]:
    """Overlay per-backend toolchain and compiler capability overrides."""

    capabilities = compiler_capabilities or {}
    merged = dict(configured)
    overridden = (
        compilers.keys()
        | targets.keys()
        | linkers.keys()
        | capabilities.keys()
    )
    for backend_id in sorted(overridden):
        previous = merged.get(backend_id, BackendToolchain())
        merged[backend_id] = BackendToolchain.create(
            compiler=compilers.get(backend_id) or previous.compiler,
            target=targets.get(backend_id) or previous.target,
            linker=linkers.get(backend_id) or previous.linker,
            compiler_capabilities=(
                split_csv(capabilities[backend_id])
                if backend_id in capabilities
                else previous.compiler_capabilities
            ),
        )
    return merged
