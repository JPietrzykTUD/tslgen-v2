"""Deterministic, fail-closed generated-library release production."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
from types import ModuleType
from zipfile import ZipFile

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / ".github/scripts/release_production.py"


def _load_release_production() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_production", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_production = _load_release_production()


def _write_vsix(path: Path, *, target: str, commit: str) -> None:
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "extension/package.json",
            json.dumps({"version": "0.1.1"}),
        )
        archive.writestr(
            "extension/server/release-manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "target": target,
                    "compiler_version": "0.1.0a1",
                    "extension_version": "0.1.1",
                    "source_commit": commit,
                    "source_dirty": False,
                }
            ),
        )


def test_release_metadata_keeps_product_and_component_versions_distinct() -> None:
    config = release_production.load_config()

    metadata = release_production.release_metadata("v1.0.0-rc.1", config=config)

    assert metadata.product_version == "1.0.0"
    assert metadata.product_status == "release-candidate"
    assert metadata.compiler_version == "0.1.0a1"
    assert metadata.editor_version == "0.1.1"
    assert metadata.rust_msrv == "1.89"
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="requires product status 'stable'",
    ):
        release_production.release_metadata("v1.0.0", config=config)


def test_normalized_archives_are_byte_reproducible(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    executable = source / "bin" / "tool"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o751)
    regular = source / "README.md"
    regular.write_text("stable bytes\n", encoding="utf-8")
    regular.chmod(0o600)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    release_production.write_deterministic_archive(
        source, first, prefix="tsl-generated-1.0.0", epoch=1_700_000_000
    )
    executable.touch()
    regular.touch()
    release_production.write_deterministic_archive(
        source, second, prefix="tsl-generated-1.0.0", epoch=1_700_000_000
    )

    assert first.read_bytes() == second.read_bytes()
    release_production.verify_deterministic_archive(first, epoch=1_700_000_000)
    with tarfile.open(first, "r:gz") as archive:
        modes = {member.name: member.mode for member in archive.getmembers()}
    assert modes["tsl-generated-1.0.0/README.md"] == 0o644
    assert modes["tsl-generated-1.0.0/bin/tool"] == 0o755


def test_release_assembly_is_exact_verified_and_never_replaced(tmp_path: Path) -> None:
    config = release_production.load_config()
    metadata = release_production.release_metadata("v1.0.0-rc.1", config=config)
    epoch = 1_700_000_000
    generated_source = tmp_path / "generated"
    generated_source.mkdir()
    (generated_source / ".tslc-manifest.json").write_text(
        '{"schema_version":1}\n', encoding="utf-8"
    )
    cargo = generated_source / "rust" / "Cargo.toml"
    cargo.parent.mkdir()
    cargo.write_text(
        '[package]\nversion = "1.0.0"\nrust-version = "1.89"\n',
        encoding="utf-8",
    )
    (generated_source / "README.md").write_text("generated\n", encoding="utf-8")
    docs_source = tmp_path / "docs"
    docs_source.mkdir()
    (docs_source / "index.html").write_text("<h1>TSL</h1>\n", encoding="utf-8")
    generated_archive = tmp_path / "generated.tar.gz"
    docs_archive = tmp_path / "docs.tar.gz"
    release_production.write_deterministic_archive(
        generated_source,
        generated_archive,
        prefix="tsl-generated-1.0.0",
        epoch=epoch,
    )
    release_production.write_deterministic_archive(
        docs_source,
        docs_archive,
        prefix="tsl-docs-1.0.0",
        epoch=epoch,
    )
    editor = tmp_path / "editor"
    editor.mkdir()
    for target in config.editor_targets:
        asset = editor / f"tsl-language-support-{target}.vsix"
        _write_vsix(asset, target=target, commit="a" * 40)
        digest = release_production._file_sha256(asset)
        (editor / f"{asset.name}.sha256").write_text(
            f"{digest}  {asset.name}\n", encoding="utf-8"
        )
    staged = tmp_path / "staged"

    release_production.assemble_release(
        metadata=metadata,
        config=config,
        commit="a" * 40,
        epoch=epoch,
        generated_archive=generated_archive,
        docs_archive=docs_archive,
        editor_assets=editor,
        evidence_dir=None,
        output_dir=staged,
    )
    release_production.verify_release_assets(
        staged, tag="v1.0.0-rc.1", config=config
    )
    assert {path.name for path in staged.iterdir()} == {
        "SHA256SUMS",
        "release-manifest.json",
        "tsl-generated-v1.0.0-rc.1.tar.gz",
        "tsl-docs-v1.0.0-rc.1.tar.gz",
        *(f"tsl-language-support-{target}.vsix" for target in config.editor_targets),
    }
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="staging directory is not empty",
    ):
        release_production.assemble_release(
            metadata=metadata,
            config=config,
            commit="a" * 40,
            epoch=epoch,
            generated_archive=generated_archive,
            docs_archive=docs_archive,
            editor_assets=editor,
            evidence_dir=None,
            output_dir=staged,
        )

    payload = next(path for path in staged.iterdir() if path.suffix == ".vsix")
    payload.write_bytes(b"tampered")
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="does not match manifest",
    ):
        release_production.verify_release_assets(
            staged, tag="v1.0.0-rc.1", config=config
        )


def test_final_release_fails_closed_without_native_evidence(tmp_path: Path) -> None:
    config = release_production.load_config()
    candidate = release_production.release_metadata("v1.0.0-rc.1", config=config)
    final = replace(
        candidate,
        tag="v1.0.0",
        release_kind="final",
        product_status="stable",
    )
    generated_source = tmp_path / "generated"
    generated_source.mkdir()
    (generated_source / ".tslc-manifest.json").write_text("{}\n", encoding="utf-8")
    cargo = generated_source / "rust" / "Cargo.toml"
    cargo.parent.mkdir()
    cargo.write_text(
        '[package]\nversion = "1.0.0"\nrust-version = "1.89"\n',
        encoding="utf-8",
    )
    docs_source = tmp_path / "docs"
    docs_source.mkdir()
    (docs_source / "index.html").write_text("docs\n", encoding="utf-8")
    generated_archive = tmp_path / "generated.tar.gz"
    docs_archive = tmp_path / "docs.tar.gz"
    for source, output, prefix in (
        (generated_source, generated_archive, "tsl-generated-1.0.0"),
        (docs_source, docs_archive, "tsl-docs-1.0.0"),
    ):
        release_production.write_deterministic_archive(
            source, output, prefix=prefix, epoch=1
        )
    editor = tmp_path / "editor"
    editor.mkdir()
    for target in config.editor_targets:
        asset = editor / f"tsl-language-support-{target}.vsix"
        _write_vsix(asset, target=target, commit="a" * 40)
        (editor / f"{asset.name}.sha256").write_text(
            f"{release_production._file_sha256(asset)}  {asset.name}\n",
            encoding="utf-8",
        )

    with pytest.raises(
        release_production.ReleaseProductionError,
        match="final release requires native evidence",
    ):
        release_production.assemble_release(
            metadata=final,
            config=config,
            commit="a" * 40,
            epoch=1,
            generated_archive=generated_archive,
            docs_archive=docs_archive,
            editor_assets=editor,
            evidence_dir=None,
            output_dir=tmp_path / "final",
        )


def test_release_workflow_is_the_only_tag_publication_path() -> None:
    release = (_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    for name in (
        "python.yml",
        "coverage-ratchet.yml",
        "generated-values.yml",
        "generated-package.yml",
        "editor.yml",
    ):
        component = (_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        assert "workflow_call:" in component
        assert '      - "v*"' not in component
        assert f"uses: ./.github/workflows/{name}" in release
    assert "--clobber" not in release
    assert "gh release create" in release
    assert "--draft" in release
    assert "gh release download" in release
    assert "diff --recursive" in release
    assert "gh release edit" in release
    assert "needs:" in release
