"""Build one native, self-contained tslc runtime and its release manifest."""

from __future__ import annotations

import argparse
from hashlib import sha256
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tomllib
from typing import Any


EDITOR_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_ROOT = EDITOR_ROOT.parent.parent
SERVER_ROOT = EDITOR_ROOT / "server"
SCRATCH_ROOT = REPOSITORY_ROOT / "tslctmp" / "editor-runtime"
SUPPORTED_TARGETS = frozenset(
    {
        "linux-x64",
        "linux-arm64",
        "win32-x64",
        "darwin-x64",
        "darwin-arm64",
    }
)
RUNTIME_DISTRIBUTIONS = (
    "tslc",
    "lark",
    "pygls",
    "lsprotocol",
    "attrs",
    "cattrs",
    "typing-extensions",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "packaging",
    "setuptools",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze tslc and stage one platform-specific VS Code runtime."
    )
    parser.add_argument("--target", choices=sorted(SUPPORTED_TARGETS))
    args = parser.parse_args(argv)
    target = args.target or host_target()
    actual = host_target()
    if target != actual:
        parser.error(
            f"PyInstaller is not a cross-compiler: requested {target}, host is {actual}"
        )

    compiler_version = _compiler_version()
    extension_version = _extension_version()
    scratch = SCRATCH_ROOT / target
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    _freeze(scratch, target)

    executable_name = "tslc.exe" if target.startswith("win32-") else "tslc"
    staged_runtime = scratch / "dist" / "tslc"
    executable = staged_runtime / executable_name
    if not executable.is_file():
        raise RuntimeError(f"PyInstaller did not produce {executable}")
    if not target.startswith("win32-"):
        executable.chmod(executable.stat().st_mode | 0o755)

    licenses = _collect_licenses(staged_runtime)
    checksums = _checksums(staged_runtime)
    commit, dirty = _source_provenance()
    manifest = {
        "schema_version": 1,
        "target": target,
        "compiler_version": compiler_version,
        "extension_version": extension_version,
        "source_commit": commit,
        "source_dirty": dirty,
        "executable": f"server/{target}/{executable_name}",
        "build": {
            "python": platform.python_version(),
            "pyinstaller": metadata.version("pyinstaller"),
        },
        "licenses": licenses,
        "checksums": checksums,
    }

    staged_server = scratch / "staged-server"
    target_output = staged_server / target
    shutil.copytree(staged_runtime, target_output)
    _write_json(staged_server / "release-manifest.json", manifest)
    if SERVER_ROOT.exists():
        shutil.rmtree(SERVER_ROOT)
    shutil.copytree(staged_server, SERVER_ROOT)
    print(
        f"staged {target}: tslc {compiler_version}, "
        f"{len(checksums)} files, {_tree_size(staged_runtime)} bytes"
    )
    return 0


def host_target() -> str:
    system = {
        "linux": "linux",
        "darwin": "darwin",
        "win32": "win32",
    }.get(sys.platform)
    machine = platform.machine().lower()
    architecture = {
        "x86_64": "x64",
        "amd64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine)
    target = f"{system}-{architecture}" if system and architecture else ""
    if target not in SUPPORTED_TARGETS:
        raise RuntimeError(
            f"unsupported runtime build host: platform={sys.platform}, machine={machine}"
        )
    return target


def _freeze(scratch: Path, target: str) -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "tslc",
        "--log-level",
        "WARN",
        "--distpath",
        str(scratch / "dist"),
        "--workpath",
        str(scratch / "build"),
        "--specpath",
        str(scratch / "spec"),
        "--collect-submodules",
        "tslc",
        "--collect-data",
        "tslc",
        "--collect-submodules",
        "lark",
        "--collect-submodules",
        "pygls",
        "--collect-submodules",
        "lsprotocol",
        "--copy-metadata",
        "tslc",
        "--copy-metadata",
        "lark",
        "--copy-metadata",
        "pygls",
        "--copy-metadata",
        "lsprotocol",
        "--exclude-module",
        "mypy",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "sphinx",
    ]
    if target.startswith("darwin-"):
        command.extend(
            [
                "--target-architecture",
                "arm64" if target.endswith("-arm64") else "x86_64",
                "--codesign-identity",
                "-",
            ]
        )
    command.append(str(EDITOR_ROOT / "scripts" / "tslc_entrypoint.py"))
    subprocess.run(command, cwd=REPOSITORY_ROOT, check=True)


def _compiler_version() -> str:
    configured = tomllib.loads(
        (REPOSITORY_ROOT / "tslc" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    installed = metadata.version("tslc")
    if configured != installed:
        raise RuntimeError(
            f"installed tslc version {installed} does not match pyproject {configured}"
        )
    return installed


def _extension_version() -> str:
    package = json.loads((EDITOR_ROOT / "package.json").read_text(encoding="utf-8"))
    version = package.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("extension package.json has no version")
    return version


def _collect_licenses(runtime: Path) -> list[dict[str, Any]]:
    license_root = runtime / "licenses"
    python_license = _python_license()
    python_destination = license_root / "Python" / "LICENSE.txt"
    python_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(python_license, python_destination)
    inventory: list[dict[str, Any]] = [
        {
            "name": "Python",
            "version": platform.python_version(),
            "license": "PSF-2.0",
            "files": [python_destination.relative_to(runtime).as_posix()],
            "project_url": "https://www.python.org/",
        }
    ]
    for name in RUNTIME_DISTRIBUTIONS:
        distribution = metadata.distribution(name)
        canonical = distribution.metadata.get("Name", name)
        destination = license_root / _safe_name(canonical)
        copied: list[str] = []
        for item in sorted(distribution.files or (), key=str):
            filename = item.name.lower()
            if not any(term in filename for term in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file():
                continue
            destination.mkdir(parents=True, exist_ok=True)
            selected = destination / item.name
            suffix = 1
            while selected.exists():
                selected = destination / f"{item.stem}-{suffix}{item.suffix}"
                suffix += 1
            shutil.copy2(source, selected)
            copied.append(selected.relative_to(runtime).as_posix())
        if name == "tslc" and not copied:
            destination.mkdir(parents=True, exist_ok=True)
            selected = destination / "LICENSE.txt"
            shutil.copy2(REPOSITORY_ROOT / "tslc" / "LICENSE", selected)
            copied.append(selected.relative_to(runtime).as_posix())
        inventory.append(
            {
                "name": canonical,
                "version": distribution.version,
                "license": (
                    "Apache-2.0"
                    if name == "tslc"
                    else distribution.metadata.get("License-Expression")
                    or distribution.metadata.get("License")
                    or "See bundled license files"
                ),
                "files": sorted(copied),
                "project_url": distribution.metadata.get("Home-page", ""),
            }
        )
    return sorted(inventory, key=lambda item: item["name"].lower())


def _checksums(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
        for path in sorted(
            (candidate for candidate in root.rglob("*") if candidate.is_file()),
            key=lambda item: item.relative_to(root).as_posix(),
        )
    ]


def _source_provenance() -> tuple[str, bool]:
    commit = os.environ.get("GITHUB_SHA") or _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain"))
    return commit, dirty


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in value)


def _python_license() -> Path:
    candidates = (
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError("could not locate the Python runtime license")


def _tree_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
