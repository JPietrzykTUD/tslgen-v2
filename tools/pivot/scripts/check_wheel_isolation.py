#!/usr/bin/env python3
"""Verify the one-way packaging boundary between tslc and tslc-pivot."""

from __future__ import annotations

import argparse
from configparser import ConfigParser
from dataclasses import dataclass
from email.message import Message
from email.parser import BytesParser
from email.policy import compat32
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import BadZipFile, ZipFile


class WheelIsolationError(ValueError):
    """A built distribution violates the required PIVOT package boundary."""


class _CaseSensitiveConfigParser(ConfigParser):
    def optionxform(self, optionstr: str) -> str:
        return optionstr


@dataclass(frozen=True, slots=True)
class _Wheel:
    path: Path
    members: dict[str, bytes]
    metadata: Message
    console_scripts: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> _Wheel:
        try:
            with ZipFile(path) as archive:
                members = {
                    name: archive.read(name)
                    for name in sorted(archive.namelist())
                    if not name.endswith("/")
                }
        except (BadZipFile, OSError) as exc:
            raise WheelIsolationError(f"cannot read wheel {path}: {exc}") from exc

        metadata_name = _single_member(path, members, ".dist-info/METADATA")
        entry_points_name = _single_member(
            path,
            members,
            ".dist-info/entry_points.txt",
        )
        metadata = BytesParser(policy=compat32).parsebytes(members[metadata_name])
        parser = _CaseSensitiveConfigParser(interpolation=None)
        try:
            parser.read_string(members[entry_points_name].decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise WheelIsolationError(
                f"invalid entry_points.txt in {path}: {exc}"
            ) from exc
        console_scripts = (
            dict(parser.items("console_scripts"))
            if parser.has_section("console_scripts")
            else {}
        )
        return cls(path, members, metadata, console_scripts)

    @property
    def name(self) -> str:
        value = self.metadata.get("Name")
        if value is None:
            raise WheelIsolationError(f"wheel {self.path} has no project name")
        return value

    @property
    def version(self) -> str:
        value = self.metadata.get("Version")
        if value is None:
            raise WheelIsolationError(f"wheel {self.path} has no version")
        return value

    @property
    def requirements(self) -> tuple[str, ...]:
        return tuple(self.metadata.get_all("Requires-Dist", []))


def inspect_wheels(core_path: Path, tool_path: Path) -> None:
    """Raise when the two wheels do not enforce the downstream-tool boundary."""

    core = _Wheel.load(core_path)
    tool = _Wheel.load(tool_path)
    _inspect_core(core)
    _inspect_tool(tool, compiler_version=core.version)


def _inspect_core(wheel: _Wheel) -> None:
    _require(
        _normalize_project_name(wheel.name) == "tslc",
        f"expected core project 'tslc', found {wheel.name!r}",
    )
    pivot_members = [
        name for name in wheel.members if _is_pivot_package_member(name)
    ]
    _require(
        not pivot_members,
        "core wheel contains PIVOT package members: " + ", ".join(pivot_members),
    )

    pivot_commands = [
        f"{name} = {target}"
        for name, target in sorted(wheel.console_scripts.items())
        if "pivot" in name.lower()
        or target.startswith("tslc_pivot.")
        or target.startswith("tslc.pivot.")
    ]
    _require(
        not pivot_commands,
        "core wheel exposes a PIVOT command: " + ", ".join(pivot_commands),
    )
    cli_source = wheel.members.get("tslc/cli.py")
    if cli_source is None:
        raise WheelIsolationError("core wheel is missing tslc/cli.py")
    _require(
        b"pivot" not in cli_source.lower(),
        "core wheel CLI still contains PIVOT routing text",
    )

    pivot_requirements = [
        requirement
        for requirement in wheel.requirements
        if _requirement_project_name(requirement) == "tslc-pivot"
    ]
    _require(
        not pivot_requirements,
        "core wheel depends on PIVOT: " + ", ".join(pivot_requirements),
    )


def _inspect_tool(wheel: _Wheel, *, compiler_version: str) -> None:
    _require(
        _normalize_project_name(wheel.name) == "tslc-pivot",
        f"expected tool project 'tslc-pivot', found {wheel.name!r}",
    )
    _require(
        "tslc_pivot/__init__.py" in wheel.members
        and "tslc_pivot/cli.py" in wheel.members,
        "tool wheel is missing the tslc_pivot package or CLI",
    )
    bundled_compiler_members = [
        name for name in wheel.members if PurePosixPath(name).parts[:1] == ("tslc",)
    ]
    _require(
        not bundled_compiler_members,
        "tool wheel bundles compiler package members: "
        + ", ".join(bundled_compiler_members),
    )
    _require(
        wheel.console_scripts == {"tslc-pivot": "tslc_pivot.cli:main"},
        "tool wheel must expose only 'tslc-pivot = tslc_pivot.cli:main'; "
        f"found {wheel.console_scripts!r}",
    )
    expected_requirement = f"tslc=={compiler_version}"
    compiler_requirements = tuple(
        requirement
        for requirement in wheel.requirements
        if _requirement_project_name(requirement) == "tslc"
    )
    _require(
        compiler_requirements == (expected_requirement,),
        "tool wheel must have the exact compiler pin "
        f"{expected_requirement!r}; found {compiler_requirements!r}",
    )


def _single_member(
    wheel_path: Path,
    members: dict[str, bytes],
    suffix: str,
) -> str:
    matches = [name for name in members if name.endswith(suffix)]
    if len(matches) != 1:
        raise WheelIsolationError(
            f"wheel {wheel_path} must contain exactly one {suffix}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _is_pivot_package_member(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (
        bool(parts)
        and (parts[0] == "tslc_pivot" or parts[0] == "tslc_pivot.py")
    ) or (len(parts) >= 2 and parts[:2] == ("tslc", "pivot"))


def _normalize_project_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirement_project_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return "" if match is None else _normalize_project_name(match.group(1))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WheelIsolationError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="check tslc and tslc-pivot wheel isolation",
    )
    parser.add_argument("--core-wheel", type=Path, required=True)
    parser.add_argument("--tool-wheel", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inspect_wheels(args.core_wheel, args.tool_wheel)
    except WheelIsolationError as exc:
        print(f"wheel isolation check failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"wheel isolation verified: {args.core_wheel.name}, "
        f"{args.tool_wheel.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
