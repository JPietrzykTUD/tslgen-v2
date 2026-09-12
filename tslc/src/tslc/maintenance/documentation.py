#!/usr/bin/env python3
"""Build documentation for an already generated TSLc project.

This is a maintenance/output tool, not a compiler stage. It consumes the
written generated project, copies documentation assets, and invokes external
documentation tools:

- C++: Doxygen XML consumed by Breathe inside Sphinx.
- Rust: ``cargo doc --no-deps``, copied under the same Sphinx site.

Run from the repository with ``tslc/src`` on ``PYTHONPATH``:

    PYTHONPATH=tslc/src python -m tslc.maintenance.documentation \
      --output-root ./tslctmp/verify --backends cpp,rust
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from tslc._cli_options import split_csv
from tslc.backend.capability import (
    DocumentationSiteInput,
    GeneratedDocumentationBuilder,
    GeneratedDocumentationSpec,
)
from tslc.backend.algorithm_contracts import ALGORITHM_PUBLIC_FAMILIES
from tslc.backend.cpp_algorithm_contracts import cpp_checked_algorithm_families
from tslc.backend.registry import backend_capability
from tslc.maintenance import _repo_context

CommandRunner = Callable[
    [Sequence[str], Path, Mapping[str, str] | None],
    subprocess.CompletedProcess[str],
]

_CPP_PUBLIC_DOCUMENTATION_HEADERS = (
    "tsl_core.hpp",
    "tsl_dataparallel.hpp",
    "tsl_algorithm_tags.hpp",
    "tsl_algorithm.hpp",
    "tsl_algorithm_checked.hpp",
)


def _required_repo_root(explicit: Path | None) -> Path:
    """An explicit or lazily discovered checkout root for documentation assets."""

    if explicit is not None:
        return explicit
    context = _repo_context.find_repo_context()
    if context is None:
        raise RuntimeError(
            "generated-documentation assets need a tslgen repository checkout "
            "(tsldata/ and tslc/src/ were not found above the installed package)"
        )
    return context.root


@dataclass(frozen=True, slots=True)
class DocumentationCommand:
    backend_id: str
    step: str
    argv: tuple[str, ...]
    cwd: Path


@dataclass(frozen=True, slots=True)
class DocumentationReport:
    commands: tuple[DocumentationCommand, ...]
    outputs: tuple[Path, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class GeneratedDocumentationContext:
    backend_id: str
    spec: GeneratedDocumentationSpec
    root: Path
    project_name: str
    tools: Mapping[str, str]
    dry_run: bool
    runner: CommandRunner
    commands: list[DocumentationCommand]
    outputs: list[Path]
    errors: list[str]
    site_links: tuple[tuple[str, str], ...]
    repo_root: Path | None = None


DocumentationBuilder = Callable[[GeneratedDocumentationContext], Path | None]


def document_generated(
    output_root: str | Path,
    backends: Sequence[str],
    *,
    project_name: str = "TSL Generated API",
    doxygen: str = "doxygen",
    sphinx_build: str = "sphinx-build",
    cargo: str = "cargo",
    npm: str = "npm",
    site_only: bool = False,
    npm_ci: bool = True,
    dry_run: bool = False,
    runner: CommandRunner | None = None,
    documentation_tools: Mapping[str, str] | None = None,
    repo_root: Path | None = None,
) -> DocumentationReport:
    """Build docs for selected backends in an already-written generated project.

    ``repo_root`` locates the checkout's documentation assets; when omitted,
    the enclosing checkout is discovered lazily at first use.
    """

    root = Path(output_root).resolve()
    requested = tuple(dict.fromkeys(backends))
    commands: list[DocumentationCommand] = []
    outputs: list[Path] = []
    errors: list[str] = []
    run = runner or _run_subprocess
    tools = {
        "doxygen": doxygen,
        "cargo": cargo,
        **(documentation_tools or {}),
    }
    capabilities = []
    for backend_id in requested:
        try:
            capability = backend_capability(backend_id)
        except ValueError:
            errors.append(f"unsupported documentation backend: {backend_id}")
            continue
        if capability.generated_documentation is None:
            errors.append(f"unsupported documentation backend: {backend_id}")
            continue
        capabilities.append(capability)
    if not requested:
        errors.append("no documentation backends requested")

    site_links = _site_navigation_links(
        include_cpp=any(
            capability.generated_documentation is not None
            and capability.generated_documentation.site_input
            is DocumentationSiteInput.DOXYGEN_XML
            for capability in capabilities
        ),
        include_rust=any(
            capability.generated_documentation is not None
            and capability.generated_documentation.site_input
            is DocumentationSiteInput.RUSTDOC
            for capability in capabilities
        ),
        include_specializations=(
            root / "docs" / "specializations" / "specializations.json"
        ).is_file(),
    )
    site_inputs: dict[DocumentationSiteInput, Path] = {}
    for capability in capabilities:
        spec = capability.generated_documentation
        assert spec is not None
        if site_only:
            output = _optional_existing_output(
                root / spec.output_path, dry_run=dry_run
            )
        else:
            builder = _DOCUMENTATION_BUILDERS.get(spec.builder)
            if builder is None:
                errors.append(
                    f"unsupported documentation builder {spec.builder.value!r} "
                    f"for backend {capability.backend_id}"
                )
                continue
            output = builder(
                GeneratedDocumentationContext(
                    backend_id=capability.backend_id,
                    spec=spec,
                    root=root,
                    project_name=project_name,
                    tools=tools,
                    dry_run=dry_run,
                    runner=run,
                    commands=commands,
                    outputs=outputs,
                    errors=errors,
                    site_links=site_links,
                    repo_root=repo_root,
                )
            )
        if output is not None:
            site_inputs[spec.site_input] = output
    if not errors and (site_only or site_inputs):
        _document_site(
            root,
            repo_root=repo_root,
            project_name=project_name,
            doxygen_xml=site_inputs.get(DocumentationSiteInput.DOXYGEN_XML),
            rust_doc=site_inputs.get(DocumentationSiteInput.RUSTDOC),
            sphinx_build=sphinx_build,
            npm=npm,
            npm_ci=npm_ci,
            dry_run=dry_run,
            runner=run,
            commands=commands,
            outputs=outputs,
            errors=errors,
        )

    return DocumentationReport(
        commands=tuple(commands),
        outputs=tuple(outputs),
        errors=tuple(errors),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc.maintenance.documentation",
        description="Build generated C++/Rust API documentation.",
    )
    parser.add_argument("--output-root", required=True, help="generated project root")
    parser.add_argument(
        "--backends",
        default="cpp,rust",
        help="comma-separated backends to document",
    )
    parser.add_argument(
        "--project-name",
        default="TSL Generated API",
        help="human-readable documentation title",
    )
    parser.add_argument("--doxygen", default="doxygen", help="Doxygen executable")
    parser.add_argument(
        "--sphinx-build",
        default="sphinx-build",
        help="sphinx-build executable",
    )
    parser.add_argument("--cargo", default="cargo", help="Cargo executable")
    parser.add_argument("--npm", default="npm", help="npm executable")
    parser.add_argument(
        "--site-only",
        action="store_true",
        help="rebuild only the Sphinx/specialization site from existing docs",
    )
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="skip npm ci before rebuilding the specialization explorer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="write assets and print commands without running external tools",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="validate the generated C++ public identity/documentation boundary",
    )
    args = parser.parse_args(argv)

    context = _repo_context.require_repo_context(parser)
    report = document_generated(
        args.output_root,
        split_csv(args.backends),
        repo_root=context.root,
        project_name=args.project_name,
        doxygen=args.doxygen,
        sphinx_build=args.sphinx_build,
        cargo=args.cargo,
        npm=args.npm,
        site_only=args.site_only,
        npm_ci=not args.skip_npm_ci,
        dry_run=args.dry_run,
    )
    if (
        args.strict
        and not args.dry_run
        and "cpp" in split_csv(args.backends)
        and not report.errors
    ):
        strict_errors = validate_cpp_documentation(
            Path(args.output_root) / "cpp/docs/doxygen/xml"
        )
        report = DocumentationReport(
            report.commands,
            report.outputs,
            (*report.errors, *strict_errors),
        )
    for command in report.commands:
        print(
            f"[document] {command.backend_id} {command.step}: "
            + " ".join(command.argv)
        )
    for output in report.outputs:
        print(f"[document-output] {output}")
    for error in report.errors:
        print(f"[document-error] {error}", file=sys.stderr)
    return 0 if report.ok else 1


def validate_cpp_documentation(xml_root: Path) -> tuple[str, ...]:
    """Validate Doxygen coverage against compiler-owned public family manifests."""

    index_path = xml_root / "index.xml"
    namespace_path = xml_root / "namespacetsl.xml"
    try:
        index = ET.parse(index_path).getroot()
        namespace = ET.parse(namespace_path).getroot()
    except (ET.ParseError, OSError) as error:
        return (f"cannot read C++ documentation XML: {error}",)

    compounds = {
        compound.findtext("name", default="")
        for compound in index.findall("compound")
    }
    required_compounds = {
        "tsl::dataparallel::fixed",
        "tsl::dataparallel::generic",
        "tsl::dataparallel::native",
        "tsl::simd",
        "tsl::span",
    }
    errors: list[str] = []
    missing_compounds = sorted(required_compounds - compounds)
    if missing_compounds:
        errors.append(
            "C++ documentation omits public type identities: "
            + ", ".join(missing_compounds)
        )

    algorithm_names = {
        member.findtext("name", default="")
        for compound in index.findall("compound")
        if compound.findtext("name") == "tsl::algo"
        for member in compound.findall("member")
        if member.get("kind") == "function"
    }
    expected_algorithms = set(ALGORITHM_PUBLIC_FAMILIES) | {
        f"{name}_checked" for name in cpp_checked_algorithm_families()
    }
    missing_algorithms = sorted(expected_algorithms - algorithm_names)
    if missing_algorithms:
        errors.append(
            "C++ documentation omits public algorithm families: "
            + ", ".join(missing_algorithms)
        )

    facade_members = tuple(
        member
        for member in namespace.findall(".//memberdef")
        if (
            (location := member.find("location")) is not None
            and (location.get("declfile") or location.get("file") or "")
            .replace("\\", "/")
            .endswith("docs/input/tsl_api_docs.hpp")
        )
    )
    if not facade_members:
        errors.append("C++ documentation contains no primitive callable identities")
        return tuple(errors)
    identities: set[tuple[str, str, bytes]] = set()
    names: set[str] = set()
    for member in facade_members:
        name = member.findtext("name", default="")
        names.add(name)
        template = member.find("templateparamlist")
        identity = (
            name,
            member.findtext("argsstring", default=""),
            b"" if template is None else ET.tostring(template),
        )
        if identity in identities:
            errors.append(f"C++ documentation duplicates callable identity: {name}")
        identities.add(identity)
        prose_parts: list[str] = []
        for element_name in ("briefdescription", "detaileddescription"):
            element = member.find(element_name)
            if element is not None:
                prose_parts.extend(element.itertext())
        prose = "".join(prose_parts)
        if not prose.strip():
            errors.append(f"C++ documentation has no prose for callable: {name}")
    for name in sorted(item for item in names if item.endswith("_checked")):
        if name.removesuffix("_checked") not in names:
            errors.append(f"C++ checked callable has no ordinary twin: {name}")
    return tuple(errors)


def _document_cpp(
    root: Path,
    *,
    backend_id: str,
    project_path: str,
    project_name: str,
    doxygen: str,
    dry_run: bool,
    runner: CommandRunner,
    commands: list[DocumentationCommand],
    outputs: list[Path],
    errors: list[str],
    repo_root: Path | None,
) -> Path | None:
    cpp_root = root / project_path
    facade_header = cpp_root / "docs" / "input" / "tsl_api_docs.hpp"
    public_headers = tuple(
        cpp_root / "include" / name for name in _CPP_PUBLIC_DOCUMENTATION_HEADERS
    )
    docs_root = cpp_root / "docs"
    doxygen_root = docs_root / "doxygen"

    if not facade_header.is_file():
        errors.append(f"C++ documentation facade not found: {facade_header}")
        return None
    missing_headers = tuple(path for path in public_headers if not path.is_file())
    if missing_headers:
        errors.append(
            "C++ public documentation input(s) not found: "
            + ", ".join(str(path) for path in missing_headers)
        )
        return None

    doxygen_root.mkdir(parents=True, exist_ok=True)
    _render_cpp_assets(
        project_name=project_name,
        facade_header=facade_header,
        public_headers=public_headers,
        doxygen_root=doxygen_root,
        repo_root=repo_root,
    )

    doxygen_command = _command(
        backend_id,
        "doxygen",
        doxygen,
        (str(doxygen_root / "Doxyfile"),),
        cwd=cpp_root,
        dry_run=dry_run,
        commands=commands,
        errors=errors,
    )
    if doxygen_command is None or not _execute(doxygen_command, runner, dry_run, errors):
        return None

    doxygen_xml = doxygen_root / "xml"
    error_count = len(errors)
    _record_outputs(
        (doxygen_xml,),
        dry_run=dry_run,
        outputs=outputs,
        errors=errors,
    )
    return doxygen_xml if len(errors) == error_count else None


def _document_rust(
    root: Path,
    *,
    backend_id: str,
    project_path: str,
    cargo: str,
    rustdoc_args: Sequence[str],
    site_links: tuple[tuple[str, str], ...],
    dry_run: bool,
    runner: CommandRunner,
    commands: list[DocumentationCommand],
    outputs: list[Path],
    errors: list[str],
    repo_root: Path | None,
) -> Path | None:
    rust_root = root / project_path
    manifest = rust_root / "Cargo.toml"
    docs_target = rust_root / "docs" / "target"
    if not manifest.is_file():
        errors.append(f"Rust Cargo.toml not found: {manifest}")
        return None
    docs_target.mkdir(parents=True, exist_ok=True)
    rustdoc_header, rustdoc_css = _render_rustdoc_assets(
        rust_root=rust_root,
        site_links=site_links,
        repo_root=repo_root,
    )
    cargo_command = _command(
        backend_id,
        "rustdoc",
        cargo,
        (
            "doc",
            "--no-deps",
            *rustdoc_args,
            "--target-dir",
            str(docs_target),
        ),
        cwd=rust_root,
        dry_run=dry_run,
        commands=commands,
        errors=errors,
    )
    if cargo_command is None or not _execute(
        cargo_command,
        runner,
        dry_run,
        errors,
        extra_env={
            "CARGO_ENCODED_RUSTDOCFLAGS": "\x1f".join(
                (
                    "--html-before-content",
                    str(rustdoc_header),
                    "--extend-css",
                    str(rustdoc_css),
                )
            )
        },
    ):
        return None
    rust_doc = docs_target / "doc"
    error_count = len(errors)
    _record_outputs(
        (rust_doc,),
        dry_run=dry_run,
        outputs=outputs,
        errors=errors,
    )
    return rust_doc if len(errors) == error_count else None


def _build_cpp_documentation(context: GeneratedDocumentationContext) -> Path | None:
    return _document_cpp(
        context.root,
        backend_id=context.backend_id,
        project_path=context.spec.project_path,
        project_name=context.project_name,
        doxygen=context.tools["doxygen"],
        dry_run=context.dry_run,
        runner=context.runner,
        commands=context.commands,
        outputs=context.outputs,
        errors=context.errors,
        repo_root=context.repo_root,
    )


def _build_rust_documentation(context: GeneratedDocumentationContext) -> Path | None:
    return _document_rust(
        context.root,
        backend_id=context.backend_id,
        project_path=context.spec.project_path,
        cargo=context.tools["cargo"],
        rustdoc_args=context.spec.args,
        site_links=context.site_links,
        dry_run=context.dry_run,
        runner=context.runner,
        commands=context.commands,
        outputs=context.outputs,
        errors=context.errors,
        repo_root=context.repo_root,
    )


_DOCUMENTATION_BUILDERS: Mapping[
    GeneratedDocumentationBuilder, DocumentationBuilder
] = {
    GeneratedDocumentationBuilder.DOXYGEN: _build_cpp_documentation,
    GeneratedDocumentationBuilder.RUSTDOC: _build_rust_documentation,
}


def _document_site(
    root: Path,
    *,
    repo_root: Path | None,
    project_name: str,
    doxygen_xml: Path | None,
    rust_doc: Path | None,
    sphinx_build: str,
    npm: str,
    npm_ci: bool,
    dry_run: bool,
    runner: CommandRunner,
    commands: list[DocumentationCommand],
    outputs: list[Path],
    errors: list[str],
) -> None:
    docs_root = root / "docs"
    sphinx_source = docs_root / "sphinx-src"
    sphinx_html = docs_root / "site"
    specializations_source = docs_root / "specializations"
    specializations_json = specializations_source / "specializations.json"
    specializations_dist: Path | None = None
    include_specializations = specializations_json.is_file()
    if include_specializations:
        specializations_dist = _document_specializations_app(
            root,
            repo_root=repo_root,
            site_links=_site_navigation_links(
                include_cpp=doxygen_xml is not None,
                include_rust=rust_doc is not None,
                include_specializations=True,
            ),
            npm=npm,
            npm_ci=npm_ci,
            dry_run=dry_run,
            runner=runner,
            commands=commands,
            errors=errors,
        )
        if specializations_dist is None:
            return
    sphinx_source.mkdir(parents=True, exist_ok=True)
    (sphinx_source / "_static").mkdir(parents=True, exist_ok=True)
    _render_site_assets(
        project_name=project_name,
        sphinx_source=sphinx_source,
        doxygen_xml=doxygen_xml,
        include_rust=rust_doc is not None,
        include_specializations=include_specializations,
        repo_root=repo_root,
    )

    sphinx_command = _command(
        "site",
        "sphinx",
        sphinx_build,
        ("-b", "html", str(sphinx_source), str(sphinx_html)),
        cwd=root,
        dry_run=dry_run,
        commands=commands,
        errors=errors,
    )
    if sphinx_command is None or not _execute(sphinx_command, runner, dry_run, errors):
        return

    doc_outputs = [sphinx_html]
    if include_specializations and specializations_dist is not None:
        specializations_site = sphinx_html / "specializations"
        if not dry_run:
            vite_assets = sphinx_html / "assets"
            if vite_assets.exists():
                shutil.rmtree(vite_assets)
            if specializations_site.exists():
                shutil.rmtree(specializations_site)
            shutil.copytree(specializations_dist, sphinx_html, dirs_exist_ok=True)
            shutil.copyfile(
                specializations_json,
                sphinx_html / "specializations.json",
            )
            specializations_site.mkdir(parents=True)
            _write_redirect_page(
                specializations_site / "index.html",
                target="../",
                title="TSL Specialization Explorer",
            )
            shutil.copyfile(
                specializations_json,
                specializations_site / "specializations.json",
            )
        doc_outputs.append(specializations_site)
    if rust_doc is not None:
        rust_site = sphinx_html / "rust"
        if not dry_run:
            shutil.copytree(rust_doc, rust_site, dirs_exist_ok=True)
            _ensure_rustdoc_landing(rust_site)
        doc_outputs.append(rust_site)
    _record_outputs(
        tuple(doc_outputs),
        dry_run=dry_run,
        outputs=outputs,
        errors=errors,
    )


def _document_specializations_app(
    root: Path,
    *,
    repo_root: Path | None,
    site_links: tuple[tuple[str, str], ...],
    npm: str,
    npm_ci: bool,
    dry_run: bool,
    runner: CommandRunner,
    commands: list[DocumentationCommand],
    errors: list[str],
) -> Path | None:
    checkout_root = _required_repo_root(repo_root)
    react_root = (
        checkout_root / "supplementary" / "docs" / "site" / "specializations" / "react"
    )
    package_lock = react_root / "package-lock.json"
    if not package_lock.is_file():
        errors.append(f"React specialization explorer lockfile not found: {package_lock}")
        return None
    dist = root / "docs" / "specializations" / "react-dist"
    dist.mkdir(parents=True, exist_ok=True)
    if npm_ci:
        install_command = _command(
            "site",
            "npm-ci",
            npm,
            ("ci", "--no-audit", "--no-fund"),
            cwd=react_root,
            dry_run=dry_run,
            commands=commands,
            errors=errors,
        )
        if install_command is None or not _execute(
            install_command, runner, dry_run, errors
        ):
            return None
    elif not dry_run and not (react_root / "node_modules").is_dir():
        errors.append(
            "React specialization explorer dependencies not found: "
            f"{react_root / 'node_modules'}; run './dev.sh document' once "
            "or omit --skip-npm-ci"
        )
        return None
    build_command = _command(
        "site",
        "npm-build",
        npm,
        (
            "run",
            "build",
            "--",
            "--outDir",
            str(dist),
            "--emptyOutDir",
        ),
        cwd=react_root,
        dry_run=dry_run,
        commands=commands,
        errors=errors,
    )
    if build_command is None or not _execute(
        build_command,
        runner,
        dry_run,
        errors,
        extra_env=_specialization_build_env(checkout_root, site_links=site_links),
    ):
        return None
    return dist


def _site_navigation_links(
    *, include_cpp: bool, include_rust: bool, include_specializations: bool
) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = [
        ("Specializations" if include_specializations else "Overview", "./")
    ]
    if include_cpp:
        links.append(("C++ API", "./cpp_api.html"))
    if include_rust:
        links.append(("Rust API", "./rust/"))
    links.append(("Safety contract", "./checked_api_contract.html"))
    return tuple(links)


def _render_rustdoc_assets(
    *,
    rust_root: Path,
    site_links: tuple[tuple[str, str], ...],
    repo_root: Path | None,
) -> tuple[Path, Path]:
    asset_root = (
        _required_repo_root(repo_root)
        / "supplementary"
        / "docs"
        / "site"
        / "rustdoc"
    )
    output_root = rust_root / "docs" / "rustdoc-site"
    output_root.mkdir(parents=True, exist_ok=True)
    header = output_root / "header.html"
    css = output_root / "header.css"
    header.write_text(
        _template(
            asset_root / "header.html.in",
            {"SITE_NAV_LINKS": _rustdoc_navigation_html(site_links)},
        ),
        encoding="utf-8",
    )
    shared_css = asset_root.parent / "_static" / "site-header.css"
    css.write_text(
        shared_css.read_text(encoding="utf-8")
        + "\n"
        + (asset_root / "header.css").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return header, css


def _rustdoc_navigation_html(site_links: tuple[tuple[str, str], ...]) -> str:
    anchors = []
    for label, href in site_links:
        target = href.removeprefix("./")
        active = ' class="active" aria-current="page"' if href == "./rust/" else ""
        anchors.append(
            f'<a{active} data-tslc-site-path="{html.escape(target, quote=True)}">'
            f"{html.escape(label)}</a>"
        )
    return "\n        ".join(anchors)


def _optional_existing_output(path: Path, *, dry_run: bool) -> Path | None:
    return path if dry_run or path.exists() else None


def _render_cpp_assets(
    *,
    project_name: str,
    facade_header: Path,
    public_headers: tuple[Path, ...],
    doxygen_root: Path,
    repo_root: Path | None,
) -> None:
    asset_root = _required_repo_root(repo_root) / "supplementary" / "docs" / "cpp"
    doxygen_text = _template(
        asset_root / "Doxyfile.in",
        _cpp_asset_values(
            project_name=project_name,
            facade_header=facade_header,
            public_headers=public_headers,
            doxygen_root=doxygen_root,
        ),
    )
    (doxygen_root / "Doxyfile").write_text(doxygen_text, encoding="utf-8")


def _render_site_assets(
    *,
    project_name: str,
    sphinx_source: Path,
    doxygen_xml: Path | None,
    include_rust: bool,
    include_specializations: bool,
    repo_root: Path | None,
) -> None:
    asset_root = _required_repo_root(repo_root) / "supplementary" / "docs" / "site"
    values = _site_asset_values(
        project_name=project_name,
        doxygen_xml=doxygen_xml,
        include_rust=include_rust,
        include_specializations=include_specializations,
    )
    (sphinx_source / "_templates").mkdir(parents=True, exist_ok=True)
    (sphinx_source / "conf.py").write_text(
        _template(asset_root / "conf.py.in", values),
        encoding="utf-8",
    )
    (sphinx_source / "index.rst").write_text(
        _template(asset_root / "index.rst.in", values),
        encoding="utf-8",
    )
    (sphinx_source / "checked_api_contract.rst").write_text(
        _template(asset_root / "checked_api_contract.rst.in", values),
        encoding="utf-8",
    )
    (sphinx_source / "_templates" / "layout.html").write_text(
        _template(asset_root / "_templates" / "layout.html.in", values),
        encoding="utf-8",
    )
    shutil.copyfile(
        asset_root / "checked_api_example.cpp",
        sphinx_source / "checked_api_example.cpp",
    )
    if doxygen_xml is not None:
        (sphinx_source / "cpp_api.rst").write_text(
            _template(asset_root / "cpp_api.rst.in", values),
            encoding="utf-8",
        )
    if include_rust:
        (sphinx_source / "rust_api.rst").write_text(
            _template(asset_root / "rust_api.rst.in", values),
            encoding="utf-8",
        )
    if include_specializations:
        (sphinx_source / "specializations.rst").write_text(
            _template(asset_root / "specializations.rst.in", values),
            encoding="utf-8",
        )
    _copy_static_assets(asset_root / "_static", sphinx_source / "_static")


def _copy_static_assets(source: Path, target: Path) -> None:
    for path in sorted(source.iterdir(), key=lambda item: item.name):
        if path.is_file():
            shutil.copyfile(path, target / path.name)


def _cpp_asset_values(
    *,
    project_name: str,
    facade_header: Path,
    public_headers: tuple[Path, ...],
    doxygen_root: Path,
) -> dict[str, str]:
    return {
        "PROJECT_NAME": project_name,
        "TITLE_UNDERLINE": "=" * len(project_name),
        "INPUTS": " \\\n                         ".join(
            f'"{path.resolve()}"' for path in (facade_header, *public_headers)
        ),
        "OUTPUT_DIR": str(doxygen_root.resolve()),
    }


def _site_asset_values(
    *,
    project_name: str,
    doxygen_xml: Path | None,
    include_rust: bool,
    include_specializations: bool,
) -> dict[str, str]:
    entries: list[str] = ["   checked_api_contract"]
    if doxygen_xml is not None:
        entries.append("   cpp_api")
    site_links = _site_navigation_links(
        include_cpp=doxygen_xml is not None,
        include_rust=include_rust,
        include_specializations=include_specializations,
    )
    return {
        "PROJECT_NAME": project_name,
        "TITLE_UNDERLINE": "=" * len(project_name),
        "SPHINX_EXTENSIONS": repr(["breathe"] if doxygen_xml is not None else []),
        "BREATHE_PROJECTS": repr(
            {"TSL": str(doxygen_xml.resolve())} if doxygen_xml is not None else {}
        ),
        "TOCTREE_ENTRIES": "\n".join(entries),
        "SITE_NAV_LINKS": _sphinx_navigation_html(site_links),
    }


def _sphinx_navigation_html(site_links: tuple[tuple[str, str], ...]) -> str:
    active_pages = {
        "./": "index",
        "./cpp_api.html": "cpp_api",
        "./rust/": "rust_api",
        "./checked_api_contract.html": "checked_api_contract",
    }
    anchors = []
    for label, href in site_links:
        page = active_pages[href]
        anchors.append(
            f'<a href="{html.escape(href, quote=True)}"'
            f' class="{{% if pagename == {page!r} %}}active{{% endif %}}"'
            f'{{% if pagename == {page!r} %}} aria-current="page"{{% endif %}}>'
            f"{html.escape(label)}</a>"
        )
    return "\n        ".join(anchors)


def _ensure_rustdoc_landing(rust_site: Path) -> None:
    index = rust_site / "index.html"
    if index.exists():
        return
    crate_indexes = sorted(
        path
        for path in rust_site.iterdir()
        if path.is_dir() and (path / "index.html").is_file()
    )
    target = f"{crate_indexes[0].name}/index.html" if crate_indexes else "help.html"
    _write_redirect_page(index, target=target, title="Rust API")


def _write_redirect_page(index: Path, *, target: str, title: str) -> None:
    index.write_text(
        "\n".join(
            (
                "<!doctype html>",
                "<html>",
                '<head><meta charset="utf-8">',
                f'<meta http-equiv="refresh" content="0; url={target}">',
                f"<title>{title}</title></head>",
                f'<body><p><a href="{target}">Open {title}</a></p></body>',
                "</html>",
            )
        )
        + "\n",
        encoding="utf-8",
    )


def _command(
    backend_id: str,
    step: str,
    tool: str,
    args: tuple[str, ...],
    *,
    cwd: Path,
    dry_run: bool,
    commands: list[DocumentationCommand],
    errors: list[str],
) -> DocumentationCommand | None:
    resolved = tool if dry_run else _resolve_tool(tool)
    if resolved is None:
        errors.append(f"{tool} not found; cannot build {backend_id} {step} docs")
        return None
    command = DocumentationCommand(
        backend_id=backend_id,
        step=step,
        argv=(resolved, *args),
        cwd=cwd,
    )
    commands.append(command)
    return command


def _execute(
    command: DocumentationCommand,
    runner: CommandRunner,
    dry_run: bool,
    errors: list[str],
    *,
    extra_env: Mapping[str, str] | None = None,
) -> bool:
    if dry_run:
        return True
    completed = runner(command.argv, command.cwd, extra_env)
    if completed.returncode == 0:
        return True
    errors.append(
        f"{command.backend_id} {command.step} failed with exit code "
        f"{completed.returncode}{_failure_detail(completed)}"
    )
    return False


def _failure_detail(completed: subprocess.CompletedProcess[str]) -> str:
    text = (completed.stderr or completed.stdout).strip()
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) > 14:
        lines = [lines[0], "...", *lines[-12:]]
    return ":\n" + "\n".join(f"  {line}" for line in lines)


def _record_outputs(
    paths: tuple[Path, ...],
    *,
    dry_run: bool,
    outputs: list[Path],
    errors: list[str],
) -> None:
    for path in paths:
        if dry_run or path.exists():
            outputs.append(path)
        else:
            errors.append(f"expected documentation output was not created: {path}")


def _run_subprocess(
    argv: Sequence[str],
    cwd: Path,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        list(argv),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _specialization_build_env(
    repo_root: Path, *, site_links: tuple[tuple[str, str], ...]
) -> dict[str, str]:
    branch = _git_output(repo_root, ("rev-parse", "--abbrev-ref", "HEAD"))
    if branch == "HEAD":
        branch = _git_output(repo_root, ("branch", "--show-current")) or "detached"
    short_hash = _git_output(repo_root, ("rev-parse", "--short=12", "HEAD"))
    return {
        "VITE_TSLC_GIT_BRANCH": branch or "unknown",
        "VITE_TSLC_GIT_HASH": short_hash or "unknown",
        "VITE_TSLC_SITE_LINKS": json.dumps(
            [
                {"label": label, "href": href}
                for label, href in site_links
            ],
            separators=(",", ":"),
        ),
    }


def _git_output(repo_root: Path, args: tuple[str, ...]) -> str:
    git = shutil.which("git")
    if git is None:
        return ""
    completed = subprocess.run(
        [git, *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _template(path: Path, values: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"@{key}@", value)
    return text


def _resolve_tool(tool: str) -> str | None:
    candidate = Path(tool)
    if candidate.parent != Path("."):
        return str(candidate) if candidate.exists() else None
    return shutil.which(tool)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = (
    "DocumentationCommand",
    "DocumentationReport",
    "document_generated",
    "main",
    "validate_cpp_documentation",
)
