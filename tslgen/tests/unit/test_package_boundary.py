from __future__ import annotations

import email
from email.message import Message
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from typing import ClassVar
import unittest
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "tslgen"

FORBIDDEN_PACKAGE_PREFIXES = (
    "tslgen/frontend/",
    "tslgen/ir/",
    "tslgen/middle_end/",
    "tslgen/utils/",
)
FORBIDDEN_FILES = (
    "tslgen/core/context.py",
    "tslgen/core/passes.py",
    "tslgen/core/types.py",
    "tests/test_timing.py",
)
REQUIRED_WHEEL_FILES = (
    "tslgen/__main__.py",
    "tslgen/api.py",
    "tslgen/cli.py",
    "tslgen/core/__init__.py",
    "tslgen/core/diagnostics.py",
    "tslgen/core/frozen_map.py",
    "tslgen/core/ordering.py",
    "tslgen/core/result.py",
    "tslgen/syntax/grammar/tsl_data.lark",
)


class PackageBoundaryTests(unittest.TestCase):
    wheel_names: ClassVar[tuple[str, ...]]
    sdist_names: ClassVar[tuple[str, ...]]
    metadata: ClassVar[Message]
    entry_points: ClassVar[str]

    @classmethod
    def setUpClass(cls) -> None:
        if importlib.util.find_spec("build") is None:
            raise unittest.SkipTest("python build module is not installed")
        _remove_build_outputs()
        with TemporaryDirectory() as temp:
            command = (
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--outdir",
                temp,
                str(PACKAGE_ROOT),
            )
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            try:
                if completed.returncode != 0:
                    raise AssertionError(
                        "package build failed\n"
                        f"stdout:\n{completed.stdout}\n"
                        f"stderr:\n{completed.stderr}"
                    )
                wheel = next(Path(temp).glob("*.whl"))
                sdist = next(Path(temp).glob("*.tar.gz"))
                cls.wheel_names, cls.metadata, cls.entry_points = _read_wheel(wheel)
                cls.sdist_names = _read_sdist(sdist)
            finally:
                _remove_build_outputs()

    def test_wheel_excludes_quarantined_modules(self) -> None:
        self.assertEqual(_forbidden_archive_entries(self.wheel_names), ())

    def test_sdist_excludes_quarantined_modules(self) -> None:
        self.assertEqual(_forbidden_archive_entries(self.sdist_names), ())

    def test_wheel_contains_required_production_files(self) -> None:
        for required_file in REQUIRED_WHEEL_FILES:
            self.assertIn(required_file, self.wheel_names)

    def test_sdist_contains_required_production_files(self) -> None:
        relative_names = {_archive_relative_name(name) for name in self.sdist_names}

        for required_file in REQUIRED_WHEEL_FILES:
            self.assertIn(f"src/{required_file}", relative_names)

    def test_wheel_metadata_keeps_runtime_contract(self) -> None:
        self.assertEqual(self.metadata.get("Name"), "tslgen")
        self.assertEqual(self.metadata.get("Version"), "0.1.0a1")
        self.assertEqual(self.metadata.get("Requires-Python"), ">=3.14")
        self.assertEqual(
            self.metadata.get_all("Requires-Dist"),
            ["lark>=1.3", "PyYAML>=6"],
        )

    def test_wheel_contains_console_script(self) -> None:
        self.assertIn("[console_scripts]", self.entry_points)
        self.assertIn("tslgen = tslgen.cli:run", self.entry_points)


def _read_wheel(path: Path) -> tuple[tuple[str, ...], Message, str]:
    with zipfile.ZipFile(path) as archive:
        names = tuple(sorted(archive.namelist()))
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))
        entry_name = next(
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        )
        entry_points = archive.read(entry_name).decode()
    return names, metadata, entry_points


def _read_sdist(path: Path) -> tuple[str, ...]:
    with tarfile.open(path) as archive:
        return tuple(sorted(archive.getnames()))


def _forbidden_archive_entries(names: tuple[str, ...]) -> tuple[str, ...]:
    forbidden: list[str] = []
    for name in names:
        relative = _package_relative_name(name)
        archive_relative = _archive_relative_name(name)
        if relative.startswith(FORBIDDEN_PACKAGE_PREFIXES):
            forbidden.append(name)
        elif relative in FORBIDDEN_FILES:
            forbidden.append(name)
        elif archive_relative.startswith("tests/backend/"):
            forbidden.append(name)
        elif archive_relative in FORBIDDEN_FILES:
            forbidden.append(name)
    return tuple(forbidden)


def _package_relative_name(name: str) -> str:
    archive_relative = _archive_relative_name(name)
    if archive_relative.startswith("src/"):
        return archive_relative.removeprefix("src/")
    return archive_relative


def _archive_relative_name(name: str) -> str:
    first, separator, rest = name.partition("/")
    if separator and first.startswith("tslgen-"):
        return rest
    return name


def _remove_build_outputs() -> None:
    shutil.rmtree(PACKAGE_ROOT / "build", ignore_errors=True)
    shutil.rmtree(PACKAGE_ROOT / "dist", ignore_errors=True)
    for path in PACKAGE_ROOT.glob("*.egg-info"):
        shutil.rmtree(path, ignore_errors=True)
    for path in (PACKAGE_ROOT / "src").glob("*.egg-info"):
        shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
