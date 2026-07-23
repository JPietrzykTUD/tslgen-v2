"""Repository-local defaults for the installed ``tslc`` command."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
import tomllib

from tslc.output.verify_model import BackendToolchain
from tslc.backend.rust_package import (
    DEFAULT_RUST_PACKAGE_CONFIG,
    RustPackageConfig,
)

CONFIG_NAME = "tslc.toml"


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    path: Path
    sources: tuple[Path, ...]
    machine_profiles: Path
    backends: tuple[str, ...]
    authoring_profiles: tuple[str, ...] = ()
    output_root: Path | None = None
    toolchains: Mapping[str, BackendToolchain] = field(default_factory=dict)
    runner_paths: Mapping[str, str] = field(default_factory=dict)
    tool_paths: Mapping[str, str] = field(default_factory=dict)
    rust_package: RustPackageConfig = DEFAULT_RUST_PACKAGE_CONFIG

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "toolchains", MappingProxyType(dict(sorted(self.toolchains.items())))
        )
        object.__setattr__(
            self, "runner_paths", MappingProxyType(dict(sorted(self.runner_paths.items())))
        )
        object.__setattr__(
            self, "tool_paths", MappingProxyType(dict(sorted(self.tool_paths.items())))
        )


def discover_config(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        path = candidate / CONFIG_NAME
        if path.is_file():
            return path
    return None


def load_project_config(path: Path | str | None = None) -> ProjectConfig | None:
    selected = Path(path).resolve() if path is not None else discover_config()
    if selected is None:
        return None
    if not selected.is_file():
        raise ValueError(f"configuration file {selected} does not exist")
    try:
        data = tomllib.loads(selected.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"could not read {selected}: {exc}") from exc
    root = data.get("tslc")
    if not isinstance(root, dict):
        raise ValueError(f"{selected} must contain a [tslc] table")
    base = selected.parent
    sources = _string_list(root, "sources", required=True)
    profiles = _string(root, "machine_profiles", required=True)
    backends = _string_list(root, "backends", required=True)
    authoring_profiles = _optional_string_list(root, "authoring_profiles")
    output = _string(root, "output_root", required=False)
    toolchain_table = root.get("toolchains", {})
    if not isinstance(toolchain_table, dict):
        raise ValueError(f"{selected}: tslc.toolchains must be a table")
    toolchains: dict[str, BackendToolchain] = {}
    for backend_id, raw in toolchain_table.items():
        if not isinstance(raw, dict):
            raise ValueError(
                f"{selected}: tslc.toolchains.{backend_id} must be a table"
            )
        toolchains[str(backend_id)] = BackendToolchain.create(
            compiler=_optional_table_string(selected, raw, "compiler", backend_id),
            target=_optional_table_string(selected, raw, "target", backend_id),
            linker=_optional_table_string(selected, raw, "linker", backend_id),
        )
    runners = root.get("runners", {})
    if not isinstance(runners, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in runners.items()
    ):
        raise ValueError(f"{selected}: tslc.runners must map names to strings")
    tools = root.get("tools", {})
    if not isinstance(tools, dict) or not all(
        isinstance(key, str) and isinstance(value, str) and value.strip()
        for key, value in tools.items()
    ):
        raise ValueError(f"{selected}: tslc.tools must map names to non-empty strings")
    rust_package = _rust_package_config(selected, root.get("rust_package"))
    assert profiles is not None
    return ProjectConfig(
        path=selected,
        sources=tuple(_resolve(base, value) for value in sources),
        machine_profiles=_resolve(base, profiles),
        backends=tuple(backends),
        authoring_profiles=authoring_profiles,
        output_root=_resolve(base, output) if output is not None else None,
        toolchains=toolchains,
        runner_paths={str(key): str(value) for key, value in runners.items()},
        tool_paths={str(key): str(value) for key, value in tools.items()},
        rust_package=rust_package,
    )


def _rust_package_config(path: Path, value: object) -> RustPackageConfig:
    if value is None:
        return DEFAULT_RUST_PACKAGE_CONFIG
    if not isinstance(value, dict):
        raise ValueError(f"{path}: tslc.rust_package must be a table")
    keys = {
        "name",
        "version",
        "edition",
        "rust_version",
        "license",
        "repository",
        "documentation",
        "readme",
    }
    unknown = sorted(set(value) - keys)
    if unknown:
        raise ValueError(
            f"{path}: unknown tslc.rust_package field(s): {', '.join(unknown)}"
        )
    fields = {}
    for key in sorted(keys):
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


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _string(
    table: dict[str, object], key: str, *, required: bool
) -> str | None:
    value = table.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        suffix = " is required" if required else " must be a non-empty string"
        raise ValueError(f"tslc.{key}{suffix}")
    return value


def _string_list(
    table: dict[str, object], key: str, *, required: bool
) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        suffix = " is required" if required else " must be a non-empty string array"
        raise ValueError(f"tslc.{key}{suffix}")
    return tuple(value)


def _optional_table_string(
    path: Path, table: dict[str, object], key: str, backend_id: str
) -> str | None:
    value = table.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{path}: tslc.toolchains.{backend_id}.{key} must be a non-empty string"
        )
    return value


def _optional_string_list(table: dict[str, object], key: str) -> tuple[str, ...]:
    value = table.get(key)
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"tslc.{key} must be a string array")
    return tuple(value)


__all__ = ("CONFIG_NAME", "ProjectConfig", "discover_config", "load_project_config")
