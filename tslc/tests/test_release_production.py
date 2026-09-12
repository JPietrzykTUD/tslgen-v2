"""Deterministic, fail-closed generated-library release production."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
from types import ModuleType
from zipfile import ZipFile

import pytest


_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / ".github/scripts/release_production.py"


def _load_release_production() -> ModuleType:
    script_root = str(_SCRIPT.parent)
    if script_root not in sys.path:
        sys.path.insert(0, script_root)
    spec = importlib.util.spec_from_file_location("release_production", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_production = _load_release_production()
release_bundle_package = sys.modules["release_bundle_package"]


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


def _native_evidence_payload(
    *,
    evidence_id: str,
    target: str,
    product_version: str = "1.0.0",
    compiler_input_sha256: str = "b" * 64,
    generated_bundle_index_sha256: str = "c" * 64,
    generated_bundle_manifest_sha256: str = "e" * 64,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "id": evidence_id,
        "target": target,
        "product_version": product_version,
        "compiler_input_sha256": compiler_input_sha256,
        "generated_bundle_index_sha256": generated_bundle_index_sha256,
        "generated_bundle_id": f"cpp-{target}",
        "generated_bundle_manifest_sha256": generated_bundle_manifest_sha256,
        "result": "passed",
        "skips": [],
        "reviewer": "TSL release reviewer",
        "machine": {
            "manufacturer": "Example Systems",
            "model": "Native target",
            "architecture": "aarch64" if target == "sve" else "riscv64",
            "feature_report": "native scalable vector extension present",
        },
        "software": {
            "operating_system": "Example Linux 1",
            "compiler": {
                "executable": "g++",
                "version": "g++ 15.2",
                "flags": ["-O2"],
            },
        },
        "runtime_vector_bits": [128, 256],
        "suites": {
            "generated_values": {
                "result": "passed",
                "planned_cases": 10,
                "passed_cases": 10,
                "failed_cases": 0,
                "skipped_cases": 0,
                "commands": ["./dev.sh test --profiles scalable"],
            },
            "differential_values": {
                "result": "passed",
                "planned_cases": 4,
                "passed_cases": 4,
                "failed_cases": 0,
                "skipped_cases": 0,
                "commands": ["./tsl_values --differential"],
            },
            "scalable_showcase": {
                "result": "passed",
                "same_binary": True,
                "binary_sha256": "d" * 64,
                "scalar_oracle": True,
                "canaries_preserved": True,
                "runs": [
                    {
                        "vector_bits": bits,
                        "runtime_lanes": bits // 32,
                        "input_count": bits // 32 * 3 + 2,
                        "selected": bits // 32 * 2 + 1,
                        "tail": 1,
                        "output_digest": bits + 1,
                        "command": f"./scalable-showcase --vector-bits {bits}",
                    }
                    for bits in (128, 256)
                ],
            },
        },
    }
    return payload


def _native_bundle(
    target: str, *, manifest_sha256: str = "e" * 64
) -> object:
    return release_bundle_package.GeneratedBundleRecord(
        bundle_id=f"cpp-{target}",
        backend_id="cpp",
        profiles=(target,),
        generated_scope=(target,),
        relative_path=PurePosixPath("bundles") / f"cpp-{target}",
        artifact_manifest_sha256=manifest_sha256,
    )


def _write_generated_package(
    root: Path, *, config: object, version: str = "1.0.0", rust_msrv: str = "1.89"
) -> None:
    root.mkdir()
    contract = release_production._read_json(
        config.generated_bundles.release_contract
    )
    records: list[dict[str, object]] = []
    for expected in release_bundle_package.expected_generated_bundles(
        contract, config.generated_bundles
    ):
        bundle_root = root / Path(expected.relative_path)
        backend_root = bundle_root / expected.backend_id
        backend_root.mkdir(parents=True)
        if expected.backend_id == "cpp":
            product_file = backend_root / "CMakeLists.txt"
            product_file.write_text(
                "cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8"
            )
        else:
            product_file = backend_root / "Cargo.toml"
            product_file.write_text(
                "[package]\n"
                f'version = "{version}"\n'
                f'rust-version = "{rust_msrv}"\n',
                encoding="utf-8",
            )
        public_api = backend_root / "public-api.json"
        public_api.write_text(
            json.dumps(
                {
                    "backend": expected.backend_id,
                    "scope": list(expected.generated_scope),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        artifact_manifest = bundle_root / ".tslc-manifest.json"
        artifact_manifest.write_text(
            json.dumps(
                {
                    "artifacts": [
                        {
                            "logical_path": (
                                f"{expected.backend_id}/{product_file.name}"
                            ),
                            "digest": release_production._file_sha256(
                                product_file
                            ),
                        },
                        {
                            "logical_path": f"{expected.backend_id}/public-api.json",
                            "digest": release_production._file_sha256(public_api),
                        }
                    ],
                    "version": 1,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        records.append(
            {
                "id": expected.bundle_id,
                "backend": expected.backend_id,
                "profiles": list(expected.profiles),
                "generated_scope": list(expected.generated_scope),
                "path": expected.relative_path.as_posix(),
                "artifact_manifest_sha256": release_production._file_sha256(
                    artifact_manifest
                ),
                "extracted_size_bytes": sum(
                    path.stat().st_size
                    for path in bundle_root.rglob("*")
                    if path.is_file()
                ),
            }
        )
    (root / ".tsl-release-bundles.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": {
                    "id": "tsl-generated-library",
                    "version": version,
                },
                "release_contract_sha256": release_bundle_package.json_sha256(
                    contract
                ),
                "layout": config.generated_bundles.layout_id,
                "bundles": records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("generated bundles\n", encoding="utf-8")


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


def test_generated_package_index_is_exact_and_detects_stale_bundle_data(
    tmp_path: Path,
) -> None:
    config = release_production.load_config()
    metadata = release_production.release_metadata("v1.0.0-rc.1", config=config)
    source = tmp_path / "generated"
    _write_generated_package(source, config=config)
    archive = tmp_path / "generated.tar.gz"
    release_production.write_deterministic_archive(
        source, archive, prefix="tsl-generated-1.0.0", epoch=1
    )

    index = release_production._verify_generated_package_metadata(
        archive, metadata, config
    )

    contract = release_production._read_json(
        config.generated_bundles.release_contract
    )
    assert len(index.bundles) == sum(
        len(backend["profiles"]) if backend["id"] == "cpp" else 1
        for backend in contract["backends"]
    )
    assert index.exact_bundle("cpp", ("sve",)).bundle_id == "cpp-sve"
    assert index.exact_bundle("cpp", ("rvv",)).bundle_id == "cpp-rvv"

    scalar_cmake = source / "bundles/cpp-scalar/cpp/CMakeLists.txt"
    scalar_cmake.write_text(
        "cmake_minimum_required(VERSION 3.15)\n", encoding="utf-8"
    )
    tampered_archive = tmp_path / "tampered.tar.gz"
    release_production.write_deterministic_archive(
        source, tampered_archive, prefix="tsl-generated-1.0.0", epoch=1
    )
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="stale artifact digest",
    ):
        release_production._verify_generated_package_metadata(
            tampered_archive, metadata, config
        )
    scalar_cmake.write_text(
        "cmake_minimum_required(VERSION 3.16)\n", encoding="utf-8"
    )

    manifest_path = source / ".tsl-release-bundles.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundles"][0]["extracted_size_bytes"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    stale_archive = tmp_path / "stale.tar.gz"
    release_production.write_deterministic_archive(
        source, stale_archive, prefix="tsl-generated-1.0.0", epoch=1
    )
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="extracted size is stale",
    ):
        release_production._verify_generated_package_metadata(
            stale_archive, metadata, config
        )


def test_generated_package_verifier_follows_configured_rust_grouping(
    tmp_path: Path,
) -> None:
    config = release_production.load_config()
    config = replace(
        config,
        generated_bundles=replace(
            config.generated_bundles,
            backend_grouping=(
                ("cpp", "per_profile"),
                ("rust", "per_profile"),
            ),
        ),
    )
    metadata = release_production.release_metadata("v1.0.0-rc.1", config=config)
    source = tmp_path / "generated"
    _write_generated_package(source, config=config)
    archive = tmp_path / "generated.tar.gz"
    release_production.write_deterministic_archive(
        source, archive, prefix="tsl-generated-1.0.0", epoch=1
    )

    index = release_production._verify_generated_package_metadata(
        archive, metadata, config
    )

    rust_bundles = [item for item in index.bundles if item.backend_id == "rust"]
    assert len(rust_bundles) > 1
    assert all(len(item.profiles) == 1 for item in rust_bundles)


def test_release_assembly_is_exact_verified_and_never_replaced(tmp_path: Path) -> None:
    config = release_production.load_config()
    metadata = release_production.release_metadata("v1.0.0-rc.1", config=config)
    epoch = 1_700_000_000
    generated_source = tmp_path / "generated"
    _write_generated_package(generated_source, config=config)
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
    policy = json.loads(config.release_policy.read_text(encoding="utf-8"))
    policy["product"]["status"] = "stable"
    stable_policy = tmp_path / "stable-policy.json"
    stable_policy.write_text(json.dumps(policy), encoding="utf-8")
    config = replace(config, release_policy=stable_policy)
    final = release_production.release_metadata(
        "v1.0.0",
        config=config,
    )
    generated_source = tmp_path / "generated"
    _write_generated_package(generated_source, config=config)
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

    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    generated_package = release_production._verify_generated_package_metadata(
        generated_archive, final, config
    )
    generated_bundle_index_sha256 = generated_package.manifest_sha256
    for spec in config.native_evidence:
        bundle = generated_package.exact_bundle("cpp", (spec.target,))
        payload = _native_evidence_payload(
            evidence_id=spec.evidence_id,
            target=spec.target,
            generated_bundle_index_sha256=generated_bundle_index_sha256,
            generated_bundle_manifest_sha256=(
                bundle.artifact_manifest_sha256
            ),
        )
        (evidence_dir / spec.filename).write_text(
            json.dumps(payload), encoding="utf-8"
        )
    complete = tmp_path / "complete-final"
    release_production.assemble_release(
        metadata=final,
        config=config,
        commit="a" * 40,
        epoch=1,
        generated_archive=generated_archive,
        docs_archive=docs_archive,
        editor_assets=editor,
        evidence_dir=evidence_dir,
        output_dir=complete,
    )
    release_production.verify_release_assets(
        complete, tag="v1.0.0", config=config
    )
    manifest = json.loads(
        (complete / "release-manifest.json").read_text(encoding="utf-8")
    )
    assert [item["target"] for item in manifest["native_evidence"]] == [
        "sve",
        "rvv",
    ]


def test_native_evidence_requires_reproducible_suites_for_each_target(
    tmp_path: Path,
) -> None:
    config = release_production.load_config()
    metadata = replace(
        release_production.release_metadata("v1.0.0-rc.1", config=config),
        tag="v1.0.0",
        release_kind="final",
        product_status="stable",
    )
    records: list[dict[str, object]] = []
    for spec in config.native_evidence:
        path = tmp_path / spec.filename
        payload = _native_evidence_payload(
            evidence_id=spec.evidence_id,
            target=spec.target,
        )
        path.write_text(json.dumps(payload), encoding="utf-8")
        records.append(
            release_production._validate_native_evidence(
                path,
                spec=spec,
                metadata=metadata,
                generated_bundle_index_sha256="c" * 64,
                generated_bundle=_native_bundle(spec.target),
            )
        )

    release_production._verify_shared_native_input_identity(records)
    assert [record["target"] for record in records] == ["sve", "rvv"]


def test_native_evidence_must_share_compiler_input_identity() -> None:
    with pytest.raises(
        release_production.ReleaseProductionError,
        match="do not share one compiler-input identity",
    ):
        release_production._verify_shared_native_input_identity(
            [
                {"compiler_input_sha256": "a" * 64},
                {"compiler_input_sha256": "b" * 64},
            ]
        )


@pytest.mark.parametrize(
    ("failure", "message"),
    (
        ("architecture", "architecture must be"),
        ("vector_bits", "runtime_vector_bits"),
        ("skipped_case", "generated_values suite"),
        ("showcase_binary", "scalable_showcase result"),
        ("showcase_shape", "scalable_showcase run"),
        ("bundle", "generated_bundle_id"),
        ("placeholder", "invalid reviewer"),
    ),
)
def test_native_evidence_rejects_incomplete_or_placeholder_claims(
    failure: str, message: str, tmp_path: Path
) -> None:
    config = release_production.load_config()
    metadata = replace(
        release_production.release_metadata("v1.0.0-rc.1", config=config),
        tag="v1.0.0",
        release_kind="final",
        product_status="stable",
    )
    spec = next(spec for spec in config.native_evidence if spec.target == "sve")
    payload = _native_evidence_payload(
        evidence_id=spec.evidence_id,
        target=spec.target,
    )
    machine = payload["machine"]
    suites = payload["suites"]
    assert isinstance(machine, dict)
    assert isinstance(suites, dict)
    generated = suites["generated_values"]
    showcase = suites["scalable_showcase"]
    assert isinstance(generated, dict)
    assert isinstance(showcase, dict)
    runs = showcase["runs"]
    assert isinstance(runs, list) and isinstance(runs[0], dict)
    if failure == "architecture":
        machine["architecture"] = "x86_64"
    elif failure == "vector_bits":
        payload["runtime_vector_bits"] = [192]
    elif failure == "skipped_case":
        generated["skipped_cases"] = 1
    elif failure == "showcase_binary":
        showcase["binary_sha256"] = "not-a-digest"
    elif failure == "showcase_shape":
        runs[0]["tail"] = 2
    elif failure == "bundle":
        payload["generated_bundle_id"] = "cpp-rvv"
    else:
        payload["reviewer"] = "REPLACE_WITH_REVIEWER"
    path = tmp_path / f"invalid-{failure}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(release_production.ReleaseProductionError, match=message):
        release_production._validate_native_evidence(
            path,
            spec=spec,
            metadata=metadata,
            generated_bundle_index_sha256="c" * 64,
            generated_bundle=_native_bundle(spec.target),
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
