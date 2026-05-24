from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import unittest

from _helpers import SRC_ROOT  # noqa: F401
from tslgen.analysis.candidates import select_implementation_candidates
from tslgen.analysis.selection import SelectionRequest, plan_selection
from tslgen.config.model import SourceConfig
from tslgen.domain.catalog import build_catalog
from tslgen.io.sources import load_sources
from tslgen.syntax.parser import parse_sources
from tslgen.tooling.validation import redesign_validation_profile
from tslgen.validation.catalog_validator import validate_catalog
from tslgen.validation.reference_rules import validate_references


REPO_ROOT = Path(__file__).resolve().parents[3]
QUARANTINED_PREFIXES = (
    "tslgen.frontend",
    "tslgen.ir",
    "tslgen.middle_end",
    "tslgen.utils",
)


def run_validation_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "tslgen/src"
    return subprocess.run(
        (sys.executable, "-m", "tslgen.tooling.validation", *args),
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class ValidationBaselineTests(unittest.TestCase):
    def test_profile_declares_existing_accepted_paths_and_quarantine(self) -> None:
        profile = redesign_validation_profile()

        for path in (*profile.accepted_source_paths, *profile.accepted_test_paths):
            self.assertTrue((REPO_ROOT / path).exists(), path)

        quarantined_paths = {entry.path for entry in profile.quarantined_paths}
        self.assertIn("tslgen/src/tslgen/middle_end", quarantined_paths)
        self.assertIn("tslgen/src/tslgen/core/passes.py", quarantined_paths)
        self.assertIn("frozen", quarantined_paths)
        self.assertNotIn("tslgen/src/tslgen", profile.accepted_source_paths)

    def test_profile_commands_cover_required_checks(self) -> None:
        profile = redesign_validation_profile()
        command_names = tuple(command.name for command in profile.commands)

        self.assertEqual(
            command_names,
            (
                "current-corpus-probes",
                "unit-discovery",
                "compileall",
                "ruff",
                "mypy",
                "diff-check",
            ),
        )
        self.assertIn(
            "test_scalar_blend_selection_ignores_unselected_current_corpus_shapes",
            " ".join(profile.command_by_name("current-corpus-probes").argv),
        )
        self.assertEqual(
            profile.command_by_name("mypy").env,
            (("MYPYPATH", "tslgen/src:tslgen/tests/unit"),),
        )

    def test_only_runs_single_named_command(self) -> None:
        completed = run_validation_cli("--only", "diff-check")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("==> diff-check:", completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)

    def test_only_runs_multiple_named_commands_in_order(self) -> None:
        completed = run_validation_cli(
            "--only",
            "diff-check",
            "--only",
            "diff-check",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.count("==> diff-check:"), 2)
        self.assertNotIn("Traceback", completed.stderr)

    def test_only_unknown_command_is_clean_cli_error(self) -> None:
        completed = run_validation_cli("--only", "not-a-command")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("unknown validation command(s): not-a-command", completed.stderr)
        self.assertIn("available:", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_public_entry_points_do_not_import_quarantined_modules(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = "tslgen/src"
        script = (
            "import sys; "
            "import tslgen.api, tslgen.cli; "
            f"prefixes={QUARANTINED_PREFIXES!r}; "
            "loaded=sorted(name for name in sys.modules "
            "if name.startswith(prefixes)); "
            "print('\\n'.join(loaded)); "
            "raise SystemExit(1 if loaded else 0)"
        )

        completed = subprocess.run(
            (sys.executable, "-c", script),
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_scalar_blend_current_corpus_probe(self) -> None:
        sources = load_sources(
            SourceConfig(
                explicit_paths=(
                    Path("tsldata/detail/flags.tsl"),
                    Path("tsldata/detail/types.tsl"),
                    Path("tsldata/detail/lane_sets.tsl"),
                    Path("tsldata/extensions/extension.tsl"),
                    Path("tsldata/detail/templates.tsl"),
                    Path("tsldata/primitives/misc/blend.tsl"),
                ),
                include_standard_library=False,
            )
        )
        self.assertTrue(sources.is_ok, sources.diagnostics)
        parsed = parse_sources(sources.unwrap())
        self.assertTrue(parsed.is_ok, parsed.diagnostics)
        catalog = build_catalog(parsed.unwrap())
        self.assertTrue(catalog.is_ok, catalog.diagnostics)
        validated = validate_catalog(catalog.unwrap())
        self.assertTrue(validated.is_ok, validated.diagnostics)
        referenced = validate_references(validated.unwrap())
        self.assertTrue(referenced.is_ok, referenced.diagnostics)

        plan = plan_selection(
            referenced.unwrap(),
            SelectionRequest(
                primitive_names=("blend",),
                extension_names=("scalar",),
                include_support_extensions=False,
            ),
        )
        self.assertTrue(plan.is_ok, plan.diagnostics)
        candidates = select_implementation_candidates(
            plan.unwrap(),
            referenced.unwrap().catalog,
        )

        self.assertTrue(candidates.is_ok, candidates.diagnostics)
        self.assertGreater(len(candidates.unwrap().candidates), 0)
        self.assertEqual(
            {candidate.source_extension for candidate in candidates.unwrap().candidates},
            {"scalar"},
        )


if __name__ == "__main__":
    unittest.main()
