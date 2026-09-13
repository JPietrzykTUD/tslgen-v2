"""Typed release metadata for the generated Rust package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

from tslc.project_render import BackendRenderInput

_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_VERSION = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_RUST_VERSION = re.compile(r"^1\.[0-9]+(?:\.[0-9]+)?$")


@dataclass(frozen=True, slots=True)
class RustPackageConfig(BackendRenderInput):
    name: str
    version: str
    description: str
    edition: str
    rust_version: str
    license: str
    repository: str
    documentation: str
    readme: str

    def __post_init__(self) -> None:
        if not _PACKAGE_NAME.fullmatch(self.name) or len(self.name) > 64:
            raise ValueError("Rust package name is not a valid Cargo package name")
        if not _valid_version(self.version):
            raise ValueError("Rust package version must be a three-part release version")
        if not _single_line(self.description):
            raise ValueError("Rust package description cannot be empty")
        if self.edition not in {"2015", "2018", "2021", "2024"}:
            raise ValueError("Rust package edition is not supported")
        if not _RUST_VERSION.fullmatch(self.rust_version):
            raise ValueError("Rust package rust-version must name a stable 1.x release")
        if not _single_line(self.license):
            raise ValueError("Rust package license cannot be empty")
        if not _absolute_url(self.repository) or not _absolute_url(self.documentation):
            raise ValueError("Rust package repository and documentation URLs are required")
        readme_path = PurePosixPath(self.readme)
        if (
            not _single_line(self.readme)
            or readme_path.is_absolute()
            or ".." in readme_path.parts
            or readme_path.name != self.readme
            or "\\" in self.readme
        ):
            raise ValueError("Rust package README must be one crate-root file name")


def _single_line(value: str) -> bool:
    return bool(value.strip()) and "\n" not in value and "\r" not in value


def _valid_version(value: str) -> bool:
    if not _VERSION.fullmatch(value):
        return False
    release = value.split("+", 1)[0]
    if "-" not in release:
        return True
    prerelease = release.split("-", 1)[1]
    return all(
        not (identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"))
        for identifier in prerelease.split(".")
    )


def _absolute_url(value: str) -> bool:
    if not _single_line(value) or any(character.isspace() for character in value):
        return False
    parsed = urlsplit(value)
    return bool(parsed.scheme and parsed.netloc)


DEFAULT_RUST_PACKAGE_CONFIG = RustPackageConfig(
    name="tsl",
    version="1.0.0",
    description="Generated cross-platform SIMD primitives and data-parallel algorithms",
    edition="2021",
    rust_version="1.89",
    license="Apache-2.0",
    repository="https://github.com/JPietrzykTUD/tslgen-v2",
    documentation="https://docs.rs/tsl",
    readme="README.md",
)

_RUST_PACKAGE_FIELDS = frozenset(
    {
        "name",
        "version",
        "description",
        "edition",
        "rust_version",
        "license",
        "repository",
        "documentation",
        "readme",
    }
)


def parse_rust_package_config(path: Path, value: object) -> RustPackageConfig:
    """Promote the optional ``[tslc.rust_package]`` table."""

    if value is None:
        return DEFAULT_RUST_PACKAGE_CONFIG
    if not isinstance(value, dict):
        raise ValueError(f"{path}: tslc.rust_package must be a table")
    unknown = sorted(set(value) - _RUST_PACKAGE_FIELDS)
    if unknown:
        raise ValueError(
            f"{path}: unknown tslc.rust_package field(s): {', '.join(unknown)}"
        )
    fields: dict[str, str] = {}
    for key in sorted(_RUST_PACKAGE_FIELDS):
        field_value = value.get(key)
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(
                f"{path}: tslc.rust_package.{key} must be a non-empty string"
            )
        fields[key] = field_value
    try:
        return RustPackageConfig(**fields)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


__all__ = (
    "DEFAULT_RUST_PACKAGE_CONFIG",
    "RustPackageConfig",
    "parse_rust_package_config",
)
