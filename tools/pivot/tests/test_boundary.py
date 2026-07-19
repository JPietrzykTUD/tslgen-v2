"""The standalone exporter depends on tslc without leaking back into it."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pytest

from tslc import cli as tslc_cli

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CORE_ROOT = _REPO_ROOT / "tslc"
_TOOL_ROOT = _REPO_ROOT / "tools" / "pivot"
_WHEEL_INSPECTOR = _TOOL_ROOT / "scripts" / "check_wheel_isolation.py"

_EXPECTED_COMPILER_IMPORTS = (
    ("tslc._pipeline_inputs", ("load_catalog_inputs",)),
    ("tslc.api", ("write_artifacts",)),
    ("tslc.backend.cpp_profile", ("cpp_dataparallel_fixed_lane_count",)),
    ("tslc.backend.registry", ("create_backend_dialect",)),
    (
        "tslc.backend.rust_algorithm",
        ("rust_dataparallel_fixed_lane_count", "rust_fixed_vector_spelling"),
    ),
    ("tslc.backend.rust_translation", ("rust_raw_identifier",)),
    (
        "tslc.backend.signature_types",
        ("BackendSignatureTypes", "CPP_SIGNATURE_TYPES", "RUST_SIGNATURE_TYPES"),
    ),
    ("tslc.backend.translation", ("BackendDialect",)),
    (
        "tslc.catalog.machine_profiles",
        ("MachineProfile", "load_machine_profiles_checked"),
    ),
    ("tslc.catalog.model", ("BOOLEAN_WILDCARD_ATTRIBUTES", "Catalog")),
    (
        "tslc.catalog.scalar_types",
        (
            "DEFAULT_SCALAR_TYPE_TAGS",
            "SCALAR_TYPE_ORDER",
            "scalar_bit_width_or_default",
        ),
    ),
    ("tslc.catalog.signatures", ("SignatureShape", "parse_signature")),
    (
        "tslc.diagnostics",
        (
            "Diagnostic",
            "SourceSpan",
            "format_diagnostic",
            "has_errors",
            "sort_diagnostics",
        ),
    ),
    (
        "tslc.ir.region_syntax",
        (
            "ParsedCallSelector",
            "parse_call_selector",
            "parse_var_selector",
            "split_arg_groups",
        ),
    ),
    ("tslc.ir.scan", ("scan",)),
    ("tslc.ir.segments", ("Region",)),
    ("tslc.lower.context", ("LoweringSession",)),
    (
        "tslc.lower.dependencies",
        (
            "CallDependency",
            "CallDependencyOrigin",
            "VectorIdentity",
            "resolve_lowered_call_dependency",
            "resolve_lowered_call_vector",
        ),
    ),
    ("tslc.lower.lowerer", ("LoweredSpecialization", "Lowerer")),
    ("tslc.lower.queries", ("BoolValue", "QueryEvaluator", "TextValue")),
    (
        "tslc.lower.region_handlers",
        ("DEFAULT_REGION_LOWERERS", "RegionLowerer"),
    ),
    ("tslc.lower.region_handlers.protocol", ("RenderBody",)),
    ("tslc.output.artifacts", ("Artifact", "ArtifactSet")),
    (
        "tslc.project_config",
        ("ProjectConfig", "discover_config", "load_project_config"),
    ),
    ("tslc.select.selector", ("SelectedImplementation", "Selector")),
    ("tslc.sources", ("expand_source_paths",)),
    ("tslc.support_policy", ("DEFAULT_SUPPORT_POLICY",)),
    (
        "tslc.target_text",
        (
            "LiteralText",
            "LoweredBody",
            "RenderContext",
            "RenderField",
            "RenderPlaceholder",
            "RenderSequence",
            "RenderText",
            "TemplateApplication",
            "TemplateRenderError",
            "TrimmedText",
            "UnsafeBlockText",
            "render_text",
            "unsafe_block",
        ),
    ),
)


def test_core_package_has_no_pivot_module_or_reverse_import() -> None:
    assert not (_CORE_ROOT / "src" / "tslc" / "pivot").exists()
    assert importlib.util.find_spec("tslc.pivot") is None

    offenders: list[str] = []
    for path in sorted(_CORE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names = (node.module or "",)
            else:
                continue
            if any(
                name == "tslc_pivot"
                or name.startswith("tslc_pivot.")
                or name == "tslc.pivot"
                or name.startswith("tslc.pivot.")
                for name in names
            ):
                offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
    assert offenders == []


def test_core_cli_has_no_export_group(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as help_exit:
        tslc_cli.main(["--help"])
    assert help_exit.value.code == 0
    help_text = capsys.readouterr().out
    assert "pivot" not in help_text.lower()
    assert "export" not in help_text.lower()

    with pytest.raises(SystemExit) as command_exit:
        tslc_cli.main(["export", "pivot"])
    assert command_exit.value.code == 2
    assert "unknown command 'export'" in capsys.readouterr().err


def test_tool_pins_the_matching_compiler_version() -> None:
    core_config = tomllib.loads(
        (_CORE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    tool_config = tomllib.loads(
        (_TOOL_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    compiler_version = core_config["project"]["version"]
    assert tool_config["project"]["version"] == compiler_version
    assert tool_config["project"]["dependencies"] == [
        f"tslc=={compiler_version}"
    ]


def test_compiler_imports_are_an_explicit_lockstep_inventory() -> None:
    imports: dict[str, set[str]] = {}
    for path in sorted((_TOOL_ROOT / "src" / "tslc_pivot").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                module = ""
                names = tuple(alias.name for alias in node.names)
            else:
                continue
            if module == "tslc" or module.startswith("tslc."):
                imports.setdefault(module, set()).update(names)
            for name in names if not module else ():
                if name == "tslc" or name.startswith("tslc."):
                    imports.setdefault(name, set()).add("*")

    actual = tuple(
        (module, tuple(sorted(names))) for module, names in sorted(imports.items())
    )
    assert actual == _EXPECTED_COMPILER_IMPORTS
    assert tuple(
        module
        for module, _names in actual
        if any(part.startswith("_") for part in module.split("."))
    ) == ("tslc._pipeline_inputs",)


def test_import_does_not_mutate_compiler_registries_or_defaults() -> None:
    script = """
from tslc.backend.registry import BACKEND_CAPABILITIES
from tslc.catalog.scalar_types import DEFAULT_SCALAR_TYPE_TAGS
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS
from tslc.lower.region_handlers import DEFAULT_REGION_LOWERERS
from tslc.support_policy import DEFAULT_SUPPORT_POLICY

def snapshot():
    return (
        (id(BACKEND_CAPABILITIES), tuple((id(item), item.backend_id) for item in BACKEND_CAPABILITIES)),
        (id(DEFAULT_SCALAR_TYPE_TAGS), DEFAULT_SCALAR_TYPE_TAGS),
        (id(DEFAULT_TSIL_REGION_DESCRIPTORS), tuple((id(item), item.keyword) for item in DEFAULT_TSIL_REGION_DESCRIPTORS)),
        (id(DEFAULT_REGION_LOWERERS), tuple((id(item), item.keyword) for item in DEFAULT_REGION_LOWERERS)),
        (id(DEFAULT_SUPPORT_POLICY), repr(DEFAULT_SUPPORT_POLICY)),
    )

before = snapshot()
import tslc_pivot
after = snapshot()
assert before == after, (before, after)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_core_and_tool_wheels_preserve_the_package_boundary(tmp_path: Path) -> None:
    core_wheel = _build_wheel(_CORE_ROOT, tmp_path / "core")
    tool_wheel = _build_wheel(_TOOL_ROOT, tmp_path / "tool")
    result = subprocess.run(
        [
            sys.executable,
            str(_WHEEL_INSPECTOR),
            "--core-wheel",
            str(core_wheel),
            "--tool-wheel",
            str(tool_wheel),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "wheel isolation verified" in result.stdout


def test_pivot_planner_uses_direct_typed_access() -> None:
    path = _TOOL_ROOT / "src" / "tslc_pivot" / "planner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
    ]
    assert offenders == []


def _build_wheel(source: Path, scratch: Path) -> Path:
    copied_source = scratch / "source"
    wheel_dir = scratch / "wheel"
    shutil.copytree(
        source,
        copied_source,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.egg-info", ".mypy_cache", "tslctmp"
        ),
    )
    wheel_dir.mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(copied_source),
        ],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    wheels = tuple(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]
