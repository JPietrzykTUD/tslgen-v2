"""Generated documentation maintenance tool."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from tslc.backend.capability import (
    DocumentationSiteInput,
    GeneratedDocumentationBuilder,
    GeneratedDocumentationSpec,
)
from tslc.backend.rust_capability import RUST_BACKEND
from tslc.maintenance.documentation import _run_subprocess, document_generated


def test_document_generated_writes_assets_and_runs_tools(
    monkeypatch, tmp_path
) -> None:
    output_root = _generated_project(tmp_path / "generated")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "doc-tools.log"
    monkeypatch.setenv("TSLC_DOC_FAKE_LOG", str(log))

    doxygen = _fake_tool(fake_bin / "doxygen")
    sphinx = _fake_tool(fake_bin / "sphinx-build")
    cargo = _fake_tool(fake_bin / "cargo")
    npm = _fake_tool(fake_bin / "npm")

    report = document_generated(
        output_root,
        ("cpp", "rust"),
        project_name="Tiny API",
        doxygen=str(doxygen),
        sphinx_build=str(sphinx),
        cargo=str(cargo),
        npm=str(npm),
    )

    assert report.errors == ()
    assert [(c.backend_id, c.step) for c in report.commands] == [
        ("cpp", "doxygen"),
        ("rust", "rustdoc"),
        ("site", "npm-ci"),
        ("site", "npm-build"),
        ("site", "sphinx"),
    ]
    assert output_root / "cpp/docs/doxygen/xml" in report.outputs
    assert output_root / "rust/docs/target/doc" in report.outputs
    assert output_root / "docs/site" in report.outputs
    assert output_root / "docs/site/specializations" in report.outputs
    assert output_root / "docs/site/rust" in report.outputs

    doxyfile = output_root / "cpp/docs/doxygen/Doxyfile"
    assert 'PROJECT_NAME           = "Tiny API"' in doxyfile.read_text()
    assert str((output_root / "cpp/docs/input/tsl_api_docs.hpp").resolve()) in (
        doxyfile.read_text()
    )
    assert str((output_root / "cpp/include").resolve()) not in doxyfile.read_text()
    assert "GENERATE_HTML          = NO" in doxyfile.read_text()
    assert "GENERATE_XML           = YES" in doxyfile.read_text()

    site_source = output_root / "docs/sphinx-src"
    assert (site_source / "conf.py").is_file()
    assert "extensions = ['breathe']" in (site_source / "conf.py").read_text()
    assert 'html_logo = "_static/tsl_repo_logo_wide.png"' in (
        site_source / "conf.py"
    ).read_text()
    assert 'html_favicon = "_static/tsl_logo_small.png"' in (
        site_source / "conf.py"
    ).read_text()
    assert str((output_root / "cpp/docs/doxygen/xml").resolve()) in (
        site_source / "conf.py"
    ).read_text()
    assert "Tiny API" in (site_source / "index.rst").read_text()
    assert (site_source / "cpp_api.rst").is_file()
    assert (site_source / "rust_api.rst").is_file()
    assert (site_source / "specializations.rst").is_file()
    assert (site_source / "_static/tslc.css").is_file()
    assert (site_source / "_static/tsl_logo_small.png").is_file()
    assert (site_source / "_static/tsl_repo_logo_wide.png").is_file()

    assert (output_root / "cpp/docs/doxygen/xml/index.xml").is_file()
    assert (output_root / "docs/site/index.html").is_file()
    assert (output_root / "docs/site/specializations/index.html").is_file()
    assert (output_root / "docs/site/specializations/assets/app.js").is_file()
    assert (output_root / "docs/site/specializations/specializations.json").is_file()
    assert (output_root / "rust/docs/target/doc/tsl_doc_fake/index.html").is_file()
    assert (output_root / "docs/site/rust/index.html").is_file()
    assert "tsl_doc_fake/index.html" in (
        output_root / "docs/site/rust/index.html"
    ).read_text()
    log_text = log.read_text()
    assert "doxygen" in log_text
    assert "sphinx-build" in log_text
    assert "cargo doc --no-deps --no-default-features" in log_text
    assert "npm ci --no-audit --no-fund" in log_text
    assert "npm run build" in log_text
    assert "VITE_TSLC_GIT_BRANCH=" in log_text
    assert "VITE_TSLC_GIT_HASH=" in log_text


def test_runner_receives_command_environment_without_mutating_os_environ(
    monkeypatch, tmp_path
) -> None:
    """Git provenance flows to the runner as data, never through os.environ."""

    monkeypatch.delenv("VITE_TSLC_GIT_BRANCH", raising=False)
    monkeypatch.delenv("VITE_TSLC_GIT_HASH", raising=False)
    output_root = _generated_project(tmp_path / "generated")
    tools = tmp_path / "bin"
    tools.mkdir()
    for name in ("doxygen", "sphinx-build", "npm"):
        (tools / name).write_text("", encoding="utf-8")

    calls: list[tuple[str, dict[str, str] | None, bool]] = []

    def runner(argv, cwd, extra_env):
        tool = Path(argv[0]).name
        step = tool + ("-" + argv[1] if tool == "npm" else "")
        leaked = any(key.startswith("VITE_TSLC_GIT_") for key in os.environ)
        calls.append((step, dict(extra_env) if extra_env else None, leaked))
        if tool == "doxygen":
            (output_root / "cpp/docs/doxygen/xml").mkdir(parents=True, exist_ok=True)
        elif tool == "sphinx-build":
            Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(list(argv), 0, "", "")

    report = document_generated(
        output_root,
        ("cpp",),
        doxygen=str(tools / "doxygen"),
        sphinx_build=str(tools / "sphinx-build"),
        npm=str(tools / "npm"),
        runner=runner,
    )

    assert report.errors == ()
    by_step = {step: env for step, env, _ in calls}
    assert set(by_step) == {"doxygen", "npm-ci", "npm-run", "sphinx-build"}
    assert by_step["doxygen"] is None
    assert by_step["npm-ci"] is None
    build_env = by_step["npm-run"]
    assert build_env is not None
    assert build_env["VITE_TSLC_GIT_BRANCH"]
    assert build_env["VITE_TSLC_GIT_HASH"]
    assert all(not leaked for _, _, leaked in calls)
    assert "VITE_TSLC_GIT_BRANCH" not in os.environ
    assert "VITE_TSLC_GIT_HASH" not in os.environ


def test_document_generated_site_only_skips_backend_docs_and_npm_ci(tmp_path) -> None:
    output_root = _generated_project(tmp_path / "generated")

    report = document_generated(
        output_root,
        ("cpp", "rust"),
        site_only=True,
        npm_ci=False,
        dry_run=True,
    )

    assert report.errors == ()
    assert [(c.backend_id, c.step) for c in report.commands] == [
        ("site", "npm-build"),
        ("site", "sphinx"),
    ]
    assert output_root / "docs/site" in report.outputs
    assert output_root / "docs/site/specializations" in report.outputs
    assert output_root / "docs/site/rust" in report.outputs
    assert not (output_root / "cpp/docs/doxygen/Doxyfile").exists()


def test_document_generated_reports_missing_generated_projects(tmp_path) -> None:
    report = document_generated(
        tmp_path / "missing",
        ("cpp", "rust"),
        dry_run=True,
    )

    assert not report.ok
    assert report.commands == ()
    assert any("C++ documentation facade not found" in error for error in report.errors)
    assert any("Rust Cargo.toml not found" in error for error in report.errors)


def test_fake_backend_drives_generated_documentation(monkeypatch, tmp_path) -> None:
    from tslc.backend import registry

    root = tmp_path / "generated"
    project = root / "fake-language"
    project.mkdir(parents=True)
    (project / "Cargo.toml").write_text("[package]\nname='fake'\n", encoding="utf-8")
    fake = replace(
        RUST_BACKEND,
        backend_id="fake",
        root_path="fake-language",
        generated_documentation=GeneratedDocumentationSpec(
            builder=GeneratedDocumentationBuilder.RUSTDOC,
            project_path="fake-language",
            output_path="fake-language/docs/target/doc",
            site_input=DocumentationSiteInput.RUSTDOC,
        ),
    )
    monkeypatch.setattr(registry, "BACKEND_CAPABILITIES", (fake,))
    monkeypatch.setattr(registry, "_BY_ID", {"fake": fake})

    report = document_generated(root, ("fake",), dry_run=True)

    assert report.errors == ()
    assert [(command.backend_id, command.step) for command in report.commands] == [
        ("fake", "rustdoc"),
        ("site", "sphinx"),
    ]
    assert report.commands[0].cwd == project
    assert "--no-default-features" not in report.commands[0].argv
    assert root / "fake-language/docs/target/doc" in report.outputs


def test_document_generated_reports_command_traceback_tail(tmp_path) -> None:
    output_root = _generated_project(tmp_path / "generated")
    failing_doxygen = _failing_tool(tmp_path / "doxygen")

    report = document_generated(
        output_root,
        ("cpp",),
        doxygen=str(failing_doxygen),
    )

    assert not report.ok
    assert len(report.errors) == 1
    assert "cpp doxygen failed with exit code 1" in report.errors[0]
    assert "Traceback (most recent call last):" in report.errors[0]
    assert "RuntimeError: documentation tool exploded" in report.errors[0]


def test_documentation_tools_run_with_stable_utf8_locale(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LC_ALL", "definitely_not_a_real_locale")
    monkeypatch.setenv("LANG", "also_not_a_real_locale")
    probe = tmp_path / "probe_locale.py"
    probe.write_text(
        """
from __future__ import annotations

import os

print(os.environ.get("LC_ALL", ""))
print(os.environ.get("LANG", ""))
""".lstrip(),
        encoding="utf-8",
    )

    completed = _run_subprocess((sys.executable, str(probe)), tmp_path)

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == ["C.UTF-8", "C.UTF-8"]


def _generated_project(root: Path) -> Path:
    (root / "cpp/include").mkdir(parents=True)
    (root / "cpp/include/tsl.hpp").write_text(
        """
/**
 * @brief Tiny generated API.
 */
inline int add(int left, int right) { return left + right; }
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "cpp/docs/input").mkdir(parents=True)
    (root / "cpp/docs/input/tsl_api_docs.hpp").write_text(
        """
#pragma once

namespace tsl {
/**
 * @brief Tiny generated API.
 */
int add(int left, int right);
}
""".lstrip(),
        encoding="utf-8",
    )
    (root / "rust/src").mkdir(parents=True)
    (root / "rust/Cargo.toml").write_text(
        """
[package]
name = "tsl_doc_fake"
version = "0.1.0"
edition = "2021"
""".lstrip(),
        encoding="utf-8",
    )
    (root / "rust/src/lib.rs").write_text(
        "/// Tiny generated API.\npub fn add(left: i32, right: i32) -> i32 { left + right }\n",
        encoding="utf-8",
    )
    (root / "docs/specializations").mkdir(parents=True)
    (root / "docs/specializations/specializations.json").write_text(
        '{"schema_version": 1, "primitives": [], "specializations": []}\n',
        encoding="utf-8",
    )
    return root


def _fake_tool(path: Path) -> Path:
    path.write_text(
        f"""#!{sys.executable}
from __future__ import annotations

import os
import sys
from pathlib import Path

log = Path(os.environ["TSLC_DOC_FAKE_LOG"])
env_note = ""
if Path(sys.argv[0]).name == "npm" and sys.argv[1:3] == ["run", "build"]:
    env_note = (
        " VITE_TSLC_GIT_BRANCH="
        + os.environ.get("VITE_TSLC_GIT_BRANCH", "")
        + " VITE_TSLC_GIT_HASH="
        + os.environ.get("VITE_TSLC_GIT_HASH", "")
    )
line = Path(sys.argv[0]).name + " " + " ".join(sys.argv[1:]) + env_note + "\\n"
log.write_text(log.read_text() + line if log.exists() else line)
name = Path(sys.argv[0]).name
if name == "doxygen":
    doxyfile = Path(sys.argv[1])
    output = None
    for line in doxyfile.read_text().splitlines():
        if line.startswith("OUTPUT_DIRECTORY"):
            output = Path(line.split("=", 1)[1].strip().strip('"'))
    assert output is not None
    (output / "xml").mkdir(parents=True, exist_ok=True)
    (output / "xml" / "index.xml").write_text("doxygen")
elif name == "sphinx-build":
    output = Path(sys.argv[-1])
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text("sphinx")
elif name == "cargo":
    target = Path(sys.argv[sys.argv.index("--target-dir") + 1])
    (target / "doc" / "tsl_doc_fake").mkdir(parents=True, exist_ok=True)
    (target / "doc" / "tsl_doc_fake" / "index.html").write_text("rustdoc")
elif name == "npm":
    if sys.argv[1:3] == ["run", "build"]:
        output = Path(sys.argv[sys.argv.index("--outDir") + 1])
        (output / "assets").mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text("react")
        (output / "assets" / "app.js").write_text("react")
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _failing_tool(path: Path) -> Path:
    path.write_text(
        f"""#!{sys.executable}
from __future__ import annotations

import sys

print("Traceback (most recent call last):", file=sys.stderr)
print("  File \\"fake_tool.py\\", line 1, in <module>", file=sys.stderr)
print("RuntimeError: documentation tool exploded", file=sys.stderr)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path
