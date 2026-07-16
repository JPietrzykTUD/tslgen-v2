"""Lazy repository-context discovery rules for maintenance modules.

Convention: maintenance modules resolve the checkout by calling through the
``_repo_context`` module attribute (``_repo_context.find_repo_context`` /
``_repo_context.require_repo_context``), and ``require_repo_context`` looks up
``find_repo_context`` in its module globals at call time. Monkeypatching
``tslc.maintenance._repo_context.find_repo_context`` therefore intercepts every
consumer, which is what the SystemExit tests below rely on.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tslc.maintenance import (
    _repo_context,
    benchmark_coverage,
    coverage_inventory,
    coverage_ratchet,
    generation_snapshot,
    performance_benchmark,
    stage_dump,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAINTENANCE_ROOT = _REPO_ROOT / "tslc" / "src" / "tslc" / "maintenance"
_FORBIDDEN_CALL_NAMES = ("find_repo_context", "require_repo_context", "_find_repo_root")


def _called_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        target = call.func
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            names.append(target.attr)
    return names


def test_no_maintenance_module_probes_the_checkout_at_import_time() -> None:
    offenders: list[str] = []
    for path in sorted(_MAINTENANCE_ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for statement in tree.body:
            if isinstance(
                statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            for name in _called_names(statement):
                if any(forbidden in name for forbidden in _FORBIDDEN_CALL_NAMES):
                    offenders.append(f"{path.name}:{statement.lineno}: calls {name}")
        if path.name != "_repo_context.py":
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "_find_repo_root"
                ):
                    offenders.append(
                        f"{path.name}:{node.lineno}: defines _find_repo_root"
                    )
    assert offenders == []


@pytest.mark.parametrize(
    ("module", "argv"),
    (
        pytest.param(coverage_inventory, ["--check"], id="coverage_inventory"),
        pytest.param(stage_dump, ["--stage", "catalog"], id="stage_dump"),
        pytest.param(coverage_ratchet, [], id="coverage_ratchet"),
        pytest.param(benchmark_coverage, [], id="benchmark_coverage"),
        pytest.param(
            generation_snapshot,
            ["capture", "--case", "focused", "--output", "tslctmp/never-written"],
            id="generation_snapshot",
        ),
        pytest.param(
            performance_benchmark,
            ["run", "--case", "check", "--samples", "1"],
            id="performance_benchmark",
        ),
    ),
)
def test_repo_only_commands_fail_with_argparse_error_outside_a_checkout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: object,
    argv: list[str],
) -> None:
    monkeypatch.setattr(_repo_context, "find_repo_context", lambda start=None: None)

    with pytest.raises(SystemExit) as exc:
        module.main(argv)  # type: ignore[attr-defined]

    assert exc.value.code == 2
    assert "repository checkout" in capsys.readouterr().err


def test_find_repo_context_locates_this_checkout() -> None:
    context = _repo_context.find_repo_context()

    assert context is not None
    assert context.root == _REPO_ROOT
    assert context.data_root.is_dir()
    assert context.machine_profiles_path.is_file()
