#!/usr/bin/env python3
"""Build and verify immutable TSL generated-library release assets."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tomllib
from typing import Any, Mapping, Sequence
from zipfile import BadZipFile, ZipFile

from release_bundle_package import (
    GeneratedBundleConfig,
    GeneratedBundleRecord,
    GeneratedPackageIndex,
    ReleaseBundleError,
    load_generated_bundle_config,
    verify_generated_package,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "supplementary/release/tsl-v1-production.json"
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")


class ReleaseProductionError(RuntimeError):
    """A release input or artifact violates the production contract."""


@dataclass(frozen=True, slots=True)
class NativeEvidenceSpec:
    evidence_id: str
    filename: str
    target: str
    requires_chorys: bool


@dataclass(frozen=True, slots=True)
class ReleaseProductionConfig:
    release_policy: Path
    generated_config: Path
    compiler_project: Path
    editor_package: Path
    changelog: Path
    generated_bundles: GeneratedBundleConfig
    editor_targets: tuple[str, ...]
    native_evidence: tuple[NativeEvidenceSpec, ...]


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    product_id: str
    product_version: str
    product_status: str
    tag: str
    release_kind: str
    compiler_version: str
    editor_version: str
    rust_msrv: str


def load_config(
    path: Path = DEFAULT_CONFIG,
    *,
    root: Path = REPO_ROOT,
) -> ReleaseProductionConfig:
    payload = _read_json(path)
    if payload.get("schema_version") != 1:
        raise ReleaseProductionError(
            "release-production config requires schema_version 1"
        )
    targets = _string_tuple(payload.get("editor_targets"), "editor_targets")
    if not targets or len(targets) != len(set(targets)):
        raise ReleaseProductionError("editor_targets must be non-empty and unique")
    evidence_payload = payload.get("native_evidence")
    if not isinstance(evidence_payload, list) or not evidence_payload:
        raise ReleaseProductionError("native_evidence must be a non-empty list")
    evidence: list[NativeEvidenceSpec] = []
    for item in evidence_payload:
        if not isinstance(item, dict):
            raise ReleaseProductionError("native_evidence entries must be objects")
        evidence_id = _required_string(item, "id")
        filename = _required_string(item, "filename")
        target = _required_string(item, "target")
        requires_chorys = item.get("requires_chorys")
        if Path(filename).name != filename:
            raise ReleaseProductionError("native evidence filenames must be basenames")
        if target not in {"sve", "rvv"}:
            raise ReleaseProductionError(
                "native evidence target must be 'sve' or 'rvv'"
            )
        if not isinstance(requires_chorys, bool):
            raise ReleaseProductionError(
                "native evidence requires_chorys must be a boolean"
            )
        if requires_chorys and target != "rvv":
            raise ReleaseProductionError(
                "only RVV native evidence may require CHORYS integration"
            )
        evidence.append(
            NativeEvidenceSpec(evidence_id, filename, target, requires_chorys)
        )
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise ReleaseProductionError("native evidence IDs must be unique")
    if len({item.filename for item in evidence}) != len(evidence):
        raise ReleaseProductionError("native evidence filenames must be unique")
    if len({item.target for item in evidence}) != len(evidence):
        raise ReleaseProductionError("native evidence targets must be unique")
    if {item.target: item.requires_chorys for item in evidence} != {
        "sve": False,
        "rvv": True,
    }:
        raise ReleaseProductionError(
            "native evidence must require exactly SVE and RVV/CHORYS targets"
        )
    try:
        generated_bundles = load_generated_bundle_config(payload, root=root)
    except ReleaseBundleError as error:
        raise ReleaseProductionError(str(error)) from error
    return ReleaseProductionConfig(
        release_policy=_rooted(root, payload, "release_policy"),
        generated_config=_rooted(root, payload, "generated_config"),
        compiler_project=_rooted(root, payload, "compiler_project"),
        editor_package=_rooted(root, payload, "editor_package"),
        changelog=_rooted(root, payload, "changelog"),
        generated_bundles=generated_bundles,
        editor_targets=targets,
        native_evidence=tuple(evidence),
    )


def release_metadata(
    tag: str,
    *,
    config: ReleaseProductionConfig,
) -> ReleaseMetadata:
    policy = _read_json(config.release_policy)
    product = policy.get("product")
    if not isinstance(product, dict):
        raise ReleaseProductionError("release policy has no product object")
    product_id = _required_string(product, "id")
    product_version = _required_string(product, "version")
    product_status = _required_string(product, "status")
    escaped_version = re.escape(product_version)
    rc_match = re.fullmatch(rf"v{escaped_version}-rc\.([1-9][0-9]*)", tag)
    final_match = re.fullmatch(rf"v{escaped_version}", tag)
    if rc_match is None and final_match is None:
        raise ReleaseProductionError(
            f"tag {tag!r} must be v{product_version} or v{product_version}-rc.N"
        )
    release_kind = "candidate" if rc_match is not None else "final"
    expected_status = "release-candidate" if release_kind == "candidate" else "stable"
    if product_status != expected_status:
        raise ReleaseProductionError(
            f"{tag} requires product status {expected_status!r}, got {product_status!r}"
        )

    generated = tomllib.loads(config.generated_config.read_text(encoding="utf-8"))
    tslc_config = generated.get("tslc")
    if not isinstance(tslc_config, dict):
        raise ReleaseProductionError("tslc.toml has no [tslc] table")
    rust_package = tslc_config.get("rust_package")
    if not isinstance(rust_package, dict):
        raise ReleaseProductionError("tslc.toml has no [tslc.rust_package] table")
    generated_version = _required_string(rust_package, "version")
    if generated_version != product_version:
        raise ReleaseProductionError(
            "generated Rust package version does not match the release product"
        )
    rust_msrv = _required_string(rust_package, "rust_version")

    compiler = tomllib.loads(config.compiler_project.read_text(encoding="utf-8"))
    compiler_project = compiler.get("project", {})
    if not isinstance(compiler_project, dict):
        raise ReleaseProductionError("compiler pyproject has no [project] table")
    compiler_version = _required_string(compiler_project, "version")
    editor = _read_json(config.editor_package)
    editor_version = _required_string(editor, "version")
    component_majors = {
        item.get("id"): item.get("required_major")
        for item in policy.get("components", ())
        if isinstance(item, dict)
    }
    _require_major("tslc", compiler_version, component_majors)
    _require_major("vscode-tsl", editor_version, component_majors)

    changelog = config.changelog.read_text(encoding="utf-8")
    if f"## {product_version}" not in changelog:
        raise ReleaseProductionError(
            f"changelog has no {product_version} release heading"
        )
    return ReleaseMetadata(
        product_id=product_id,
        product_version=product_version,
        product_status=product_status,
        tag=tag,
        release_kind=release_kind,
        compiler_version=compiler_version,
        editor_version=editor_version,
        rust_msrv=rust_msrv,
    )


def verify_tag_commit(tag: str, commit: str, *, root: Path = REPO_ROOT) -> None:
    if COMMIT_ID.fullmatch(commit) is None:
        raise ReleaseProductionError("source commit must be a full lowercase SHA-1")
    resolved = _git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
    head = _git(root, "rev-parse", "HEAD^{commit}")
    if resolved != commit or head != commit:
        raise ReleaseProductionError(
            "tag, requested source commit, and checkout must agree: "
            f"{resolved}, {commit}, {head}"
        )


def write_deterministic_archive(
    source: Path,
    output: Path,
    *,
    prefix: str,
    epoch: int,
) -> None:
    if not source.is_dir():
        raise ReleaseProductionError(f"archive source is not a directory: {source}")
    if epoch < 0:
        raise ReleaseProductionError("archive epoch must be non-negative")
    if not prefix or PurePosixPath(prefix).name != prefix:
        raise ReleaseProductionError("archive prefix must be one path component")
    if epoch > 0xFFFFFFFF:
        raise ReleaseProductionError("archive epoch does not fit the gzip header")
    if output.exists():
        raise ReleaseProductionError(f"refusing to replace archive: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = tuple(
        sorted(
            source.rglob("*"),
            key=lambda path: path.relative_to(source).as_posix(),
        )
    )
    with output.open("xb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=epoch
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                archive.addfile(
                    _tar_info(prefix, is_dir=True, executable=True, epoch=epoch)
                )
                for path in entries:
                    relative = path.relative_to(source)
                    archive_name = (
                        PurePosixPath(prefix) / PurePosixPath(relative.as_posix())
                    ).as_posix()
                    if path.is_symlink():
                        raise ReleaseProductionError(
                            f"release archives do not accept symbolic links: {path}"
                        )
                    if path.is_dir():
                        archive.addfile(
                            _tar_info(
                                archive_name,
                                is_dir=True,
                                executable=True,
                                epoch=epoch,
                            )
                        )
                        continue
                    if not path.is_file():
                        raise ReleaseProductionError(
                            "release archives accept only files and directories: "
                            f"{path}"
                        )
                    executable = bool(path.stat().st_mode & stat.S_IXUSR)
                    info = _tar_info(
                        archive_name,
                        is_dir=False,
                        executable=executable,
                        epoch=epoch,
                    )
                    info.size = path.stat().st_size
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)


def verify_deterministic_archive(
    path: Path,
    *,
    epoch: int,
    expected_root: str | None = None,
) -> None:
    header = path.read_bytes()[:10]
    if (
        len(header) != 10
        or header[:2] != b"\x1f\x8b"
        or int.from_bytes(header[4:8], "little") != epoch
    ):
        raise ReleaseProductionError(f"gzip timestamp is not normalized: {path.name}")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if not members or names != sorted(names):
            raise ReleaseProductionError(
                f"archive entries are not ordered: {path.name}"
            )
        if len(names) != len(set(names)):
            raise ReleaseProductionError(f"archive entries are not unique: {path.name}")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ReleaseProductionError(
                f"archive must contain one root directory: {path.name}"
            )
        if expected_root is not None and roots != {expected_root}:
            raise ReleaseProductionError(
                f"archive root must be {expected_root!r}: {path.name}"
            )
        for member in members:
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts:
                raise ReleaseProductionError(f"unsafe archive path: {member.name}")
            if not member.isdir() and not member.isfile():
                raise ReleaseProductionError(
                    "archive contains a link or special file: "
                    f"{path.name}:{member.name}"
                )
            expected_mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
            if (
                member.mtime != epoch
                or member.uid != 0
                or member.gid != 0
                or member.uname != "root"
                or member.gname != "root"
                or member.mode != expected_mode
            ):
                raise ReleaseProductionError(
                    f"archive metadata is not normalized: {path.name}:{member.name}"
                )


def assemble_release(
    *,
    metadata: ReleaseMetadata,
    config: ReleaseProductionConfig,
    commit: str,
    epoch: int,
    generated_archive: Path,
    docs_archive: Path,
    editor_assets: Path,
    evidence_dir: Path | None,
    output_dir: Path,
) -> Path:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ReleaseProductionError(
            f"release staging directory is not empty: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_name = f"tsl-generated-{metadata.tag}.tar.gz"
    docs_name = f"tsl-docs-{metadata.tag}.tar.gz"
    _copy_new(generated_archive, output_dir / generated_name)
    _copy_new(docs_archive, output_dir / docs_name)
    verify_deterministic_archive(
        output_dir / generated_name,
        epoch=epoch,
        expected_root=f"tsl-generated-{metadata.product_version}",
    )
    verify_deterministic_archive(
        output_dir / docs_name,
        epoch=epoch,
        expected_root=f"tsl-docs-{metadata.product_version}",
    )
    generated_package = _verify_generated_package_metadata(
        output_dir / generated_name, metadata, config
    )

    payloads: list[tuple[str, str, str]] = [
        ("generated-library", generated_name, "application/gzip"),
        ("generated-documentation", docs_name, "application/gzip"),
    ]
    for target in config.editor_targets:
        filename = f"tsl-language-support-{target}.vsix"
        source = editor_assets / filename
        checksum = editor_assets / f"{filename}.sha256"
        _verify_sidecar(source, checksum)
        _verify_vsix_identity(source, target=target, metadata=metadata, commit=commit)
        _copy_new(source, output_dir / filename)
        payloads.append((f"vscode-{target}", filename, "application/vsix"))

    generated_bundle_index_sha256 = generated_package.manifest_sha256
    evidence_records: list[dict[str, object]] = []
    require_evidence = metadata.release_kind == "final"
    for spec in config.native_evidence:
        source = evidence_dir / spec.filename if evidence_dir is not None else None
        if source is None or not source.is_file():
            if require_evidence:
                raise ReleaseProductionError(
                    f"final release requires native evidence {spec.filename}"
                )
            continue
        evidence = _validate_native_evidence(
            source,
            spec=spec,
            metadata=metadata,
            generated_bundle_index_sha256=generated_bundle_index_sha256,
            generated_bundle=_native_target_bundle(generated_package, spec),
        )
        _copy_new(source, output_dir / spec.filename)
        payloads.append((spec.evidence_id, spec.filename, "application/json"))
        evidence_records.append(evidence)
    _verify_shared_native_input_identity(evidence_records)

    artifact_records = [
        {
            "id": artifact_id,
            "filename": filename,
            "media_type": media_type,
            "size": (output_dir / filename).stat().st_size,
            "sha256": _file_sha256(output_dir / filename),
        }
        for artifact_id, filename, media_type in payloads
    ]
    manifest = {
        "schema_version": 1,
        "product": {
            "id": metadata.product_id,
            "version": metadata.product_version,
            "status": metadata.product_status,
            "tag": metadata.tag,
            "release_kind": metadata.release_kind,
        },
        "source": {
            "commit": commit,
            "source_date_epoch": epoch,
            "created_utc": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
        },
        "components": {
            "tslc": metadata.compiler_version,
            "vscode-tsl": metadata.editor_version,
            "rust_msrv": metadata.rust_msrv,
        },
        "generated_bundle_index_sha256": generated_bundle_index_sha256,
        "native_evidence": evidence_records,
        "artifacts": artifact_records,
    }
    manifest_path = output_dir / "release-manifest.json"
    manifest_path.write_text(_canonical_json(manifest), encoding="utf-8")
    checksum_path = output_dir / "SHA256SUMS"
    checksum_path.write_text(
        "".join(f"{item['sha256']}  {item['filename']}\n" for item in artifact_records),
        encoding="utf-8",
    )
    return manifest_path


def verify_release_assets(
    directory: Path,
    *,
    tag: str,
    config: ReleaseProductionConfig,
) -> None:
    metadata = release_metadata(tag, config=config)
    manifest_path = directory / "release-manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ReleaseProductionError("release manifest requires schema_version 1")
    product = manifest.get("product")
    source = manifest.get("source")
    artifacts = manifest.get("artifacts")
    if (
        not isinstance(product, dict)
        or not isinstance(source, dict)
        or not isinstance(artifacts, list)
    ):
        raise ReleaseProductionError("release manifest has incomplete top-level fields")
    if (
        product.get("id") != metadata.product_id
        or product.get("version") != metadata.product_version
        or product.get("status") != metadata.product_status
        or product.get("tag") != tag
        or product.get("release_kind") != metadata.release_kind
    ):
        raise ReleaseProductionError("release manifest product metadata is stale")
    if manifest.get("components") != {
        "tslc": metadata.compiler_version,
        "vscode-tsl": metadata.editor_version,
        "rust_msrv": metadata.rust_msrv,
    }:
        raise ReleaseProductionError("release manifest component metadata is stale")
    epoch = source.get("source_date_epoch")
    if not isinstance(epoch, int) or epoch < 0:
        raise ReleaseProductionError(
            "release manifest has an invalid source_date_epoch"
        )
    commit = source.get("commit")
    if not isinstance(commit, str) or COMMIT_ID.fullmatch(commit) is None:
        raise ReleaseProductionError("release manifest has an invalid source commit")
    filenames: list[str] = []
    artifact_ids: list[str] = []
    checksum_lines: list[str] = []
    generated_bundle_index_sha256: str | None = None
    generated_package: GeneratedPackageIndex | None = None
    evidence_paths: dict[str, Path] = {}
    expected_artifacts = {
        "generated-library": (
            f"tsl-generated-{tag}.tar.gz",
            "application/gzip",
        ),
        "generated-documentation": (
            f"tsl-docs-{tag}.tar.gz",
            "application/gzip",
        ),
        **{
            f"vscode-{target}": (
                f"tsl-language-support-{target}.vsix",
                "application/vsix",
            )
            for target in config.editor_targets
        },
        **{
            item.evidence_id: (item.filename, "application/json")
            for item in config.native_evidence
        },
    }
    for item in artifacts:
        if not isinstance(item, dict):
            raise ReleaseProductionError("release artifact records must be objects")
        artifact_id = _required_string(item, "id")
        filename = _required_string(item, "filename")
        digest = _required_string(item, "sha256")
        media_type = _required_string(item, "media_type")
        size = item.get("size")
        if expected_artifacts.get(artifact_id) != (filename, media_type):
            raise ReleaseProductionError(
                f"release artifact identity is invalid: {artifact_id}"
            )
        if Path(filename).name != filename or HEX_DIGEST.fullmatch(digest) is None:
            raise ReleaseProductionError(f"invalid release artifact record: {filename}")
        path = directory / filename
        if (
            not path.is_file()
            or path.stat().st_size != size
            or _file_sha256(path) != digest
        ):
            raise ReleaseProductionError(
                f"release artifact does not match manifest: {filename}"
            )
        filenames.append(filename)
        artifact_ids.append(artifact_id)
        checksum_lines.append(f"{digest}  {filename}\n")
        if filename.endswith(".tar.gz"):
            kind = "generated" if artifact_id == "generated-library" else "docs"
            verify_deterministic_archive(
                path,
                epoch=epoch,
                expected_root=f"tsl-{kind}-{metadata.product_version}",
            )
            if kind == "generated":
                generated_package = _verify_generated_package_metadata(
                    path, metadata, config
                )
                generated_bundle_index_sha256 = generated_package.manifest_sha256
        elif artifact_id.startswith("vscode-"):
            _verify_vsix_identity(
                path,
                target=artifact_id.removeprefix("vscode-"),
                metadata=metadata,
                commit=commit,
            )
        elif artifact_id in {item.evidence_id for item in config.native_evidence}:
            evidence_paths[artifact_id] = path
    if len(filenames) != len(set(filenames)):
        raise ReleaseProductionError("release manifest contains duplicate filenames")
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ReleaseProductionError("release manifest contains duplicate artifact IDs")
    required_ids = {
        "generated-library",
        "generated-documentation",
        *(f"vscode-{target}" for target in config.editor_targets),
    }
    permitted_ids = required_ids | {
        item.evidence_id for item in config.native_evidence
    }
    if not required_ids.issubset(artifact_ids) or not set(artifact_ids).issubset(
        permitted_ids
    ):
        raise ReleaseProductionError(
            "release manifest artifact identity set is invalid"
        )
    if (
        generated_bundle_index_sha256 is None
        or generated_package is None
        or manifest.get("generated_bundle_index_sha256")
        != generated_bundle_index_sha256
    ):
        raise ReleaseProductionError("release generated bundle-index identity is stale")
    expected_evidence: list[dict[str, object]] = []
    for spec in config.native_evidence:
        path = evidence_paths.get(spec.evidence_id)
        if path is None:
            continue
        expected_evidence.append(
            _validate_native_evidence(
                path,
                spec=spec,
                metadata=metadata,
                generated_bundle_index_sha256=generated_bundle_index_sha256,
                generated_bundle=_native_target_bundle(generated_package, spec),
            )
        )
    _verify_shared_native_input_identity(expected_evidence)
    if manifest.get("native_evidence") != expected_evidence:
        raise ReleaseProductionError("release native-evidence records are stale")
    expected_files = set(filenames) | {"release-manifest.json", "SHA256SUMS"}
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    if actual_files != expected_files:
        raise ReleaseProductionError(
            "release asset set mismatch: "
            f"expected {sorted(expected_files)}, got {sorted(actual_files)}"
        )
    if (directory / "SHA256SUMS").read_text(encoding="utf-8") != "".join(
        checksum_lines
    ):
        raise ReleaseProductionError("SHA256SUMS does not match the release manifest")
    if metadata.release_kind == "final":
        if set(evidence_paths) != {
            item.evidence_id for item in config.native_evidence
        }:
            raise ReleaseProductionError("final release native evidence is incomplete")


def _validate_native_evidence(
    path: Path,
    *,
    spec: NativeEvidenceSpec,
    metadata: ReleaseMetadata,
    generated_bundle_index_sha256: str,
    generated_bundle: GeneratedBundleRecord,
) -> dict[str, object]:
    payload = _read_json(path)
    required = {
        "schema_version": 1,
        "id": spec.evidence_id,
        "target": spec.target,
        "product_version": metadata.product_version,
        "generated_bundle_index_sha256": generated_bundle_index_sha256,
        "generated_bundle_id": generated_bundle.bundle_id,
        "generated_bundle_manifest_sha256": (
            generated_bundle.artifact_manifest_sha256
        ),
        "result": "passed",
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ReleaseProductionError(
                f"native evidence {path.name} has invalid {key!r}"
            )
    input_digest = payload.get("compiler_input_sha256")
    if not isinstance(input_digest, str) or HEX_DIGEST.fullmatch(input_digest) is None:
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid compiler_input_sha256"
        )
    skips = payload.get("skips")
    if skips != []:
        raise ReleaseProductionError(f"native evidence {path.name} contains skips")
    reviewer = _evidence_string(payload, "reviewer", path)

    machine = _evidence_object(payload, "machine", path)
    for field in ("manufacturer", "model", "architecture", "feature_report"):
        _evidence_string(machine, field, path)
    expected_architecture = "aarch64" if spec.target == "sve" else "riscv64"
    if machine.get("architecture") != expected_architecture:
        raise ReleaseProductionError(
            f"native evidence {path.name} architecture must be "
            f"{expected_architecture!r}"
        )
    software = _evidence_object(payload, "software", path)
    _evidence_string(software, "operating_system", path)
    compiler = _evidence_object(software, "compiler", path)
    for field in ("executable", "version"):
        _evidence_string(compiler, field, path)
    compiler_flags = compiler.get("flags")
    if not isinstance(compiler_flags, list) or any(
        not _valid_evidence_text(flag) for flag in compiler_flags
    ):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid compiler flags"
        )

    vector_bits = payload.get("runtime_vector_bits")
    if (
        not isinstance(vector_bits, list)
        or not vector_bits
        or any(
            isinstance(bits, bool)
            or not isinstance(bits, int)
            or bits <= 0
            or not _valid_native_vector_bits(spec.target, bits)
            for bits in vector_bits
        )
        or vector_bits != sorted(set(vector_bits))
    ):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid runtime_vector_bits"
        )

    suites = _evidence_object(payload, "suites", path)
    for suite_name in ("generated_values", "differential_values"):
        _validate_native_value_suite(
            _evidence_object(suites, suite_name, path),
            suite_name=suite_name,
            path=path,
        )
    showcase = _evidence_object(suites, "scalable_showcase", path)
    showcase_binary = showcase.get("binary_sha256")
    if (
        showcase.get("result") != "passed"
        or showcase.get("same_binary") is not True
        or showcase.get("scalar_oracle") is not True
        or showcase.get("canaries_preserved") is not True
        or not isinstance(showcase_binary, str)
        or HEX_DIGEST.fullmatch(showcase_binary) is None
    ):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid scalable_showcase result"
        )
    _validate_native_showcase_runs(
        showcase.get("runs"), vector_bits=vector_bits, path=path
    )

    chorys_revision: str | None = None
    if spec.requires_chorys:
        chorys = _evidence_object(suites, "chorys_integration", path)
        if (
            chorys.get("result") != "passed"
            or chorys.get("actual_project") is not True
            or chorys.get("scalar_oracle") is not True
            or chorys.get("canaries_preserved") is not True
        ):
            raise ReleaseProductionError(
                f"native evidence {path.name} has invalid CHORYS integration result"
            )
        _evidence_string(chorys, "source_repository", path)
        chorys_revision = _evidence_string(chorys, "source_revision", path)
        _evidence_string(chorys, "command", path)

    return {
        "id": spec.evidence_id,
        "filename": spec.filename,
        "sha256": _file_sha256(path),
        "target": spec.target,
        "compiler_input_sha256": input_digest,
        "generated_bundle_index_sha256": generated_bundle_index_sha256,
        "generated_bundle_id": generated_bundle.bundle_id,
        "generated_bundle_manifest_sha256": (
            generated_bundle.artifact_manifest_sha256
        ),
        "runtime_vector_bits": vector_bits,
        "showcase_binary_sha256": showcase_binary,
        **(
            {"chorys_source_revision": chorys_revision}
            if chorys_revision is not None
            else {}
        ),
        "reviewer": reviewer,
    }


def _validate_native_value_suite(
    suite: Mapping[str, Any], *, suite_name: str, path: Path
) -> None:
    counts = {
        field: suite.get(field)
        for field in ("planned_cases", "passed_cases", "failed_cases", "skipped_cases")
    }
    commands = suite.get("commands")
    if (
        suite.get("result") != "passed"
        or any(
            isinstance(count, bool) or not isinstance(count, int)
            for count in counts.values()
        )
        or counts["planned_cases"] <= 0
        or counts["passed_cases"] != counts["planned_cases"]
        or counts["failed_cases"] != 0
        or counts["skipped_cases"] != 0
        or not isinstance(commands, list)
        or not commands
        or any(not _valid_evidence_text(command) for command in commands)
    ):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid {suite_name} suite"
        )


def _validate_native_showcase_runs(
    value: object, *, vector_bits: list[int], path: Path
) -> None:
    if not isinstance(value, list) or len(value) != len(vector_bits):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid scalable_showcase runs"
        )
    observed_bits: list[int] = []
    for run in value:
        if not isinstance(run, dict):
            raise ReleaseProductionError(
                f"native evidence {path.name} has invalid scalable_showcase run"
            )
        bits = run.get("vector_bits")
        lanes = run.get("runtime_lanes")
        count_values = tuple(
            run.get(field) for field in ("input_count", "selected", "tail")
        )
        if (
            isinstance(bits, bool)
            or not isinstance(bits, int)
            or isinstance(lanes, bool)
            or not isinstance(lanes, int)
            or any(
                isinstance(count, bool) or not isinstance(count, int)
                for count in count_values
            )
            or lanes != bits // 32
            or run.get("input_count") != lanes * 3 + 2
            or run.get("selected") != lanes * 2 + 1
            or run.get("tail") != 1
            or isinstance(run.get("output_digest"), bool)
            or not isinstance(run.get("output_digest"), int)
            or run["output_digest"] <= 0
            or not _valid_evidence_text(run.get("command"))
        ):
            raise ReleaseProductionError(
                f"native evidence {path.name} has invalid scalable_showcase run"
            )
        observed_bits.append(bits)
    if observed_bits != vector_bits:
        raise ReleaseProductionError(
            f"native evidence {path.name} showcase vector lengths do not match"
        )


def _evidence_object(
    payload: Mapping[str, Any], field: str, path: Path
) -> Mapping[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid {field} object"
        )
    return value


def _evidence_string(payload: Mapping[str, Any], field: str, path: Path) -> str:
    value = payload.get(field)
    if not _valid_evidence_text(value):
        raise ReleaseProductionError(
            f"native evidence {path.name} has invalid {field}"
        )
    assert isinstance(value, str)
    return value


def _valid_evidence_text(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and "REPLACE_WITH" not in value
    )


def _valid_native_vector_bits(target: str, bits: int) -> bool:
    if target == "sve":
        return 128 <= bits <= 2048 and bits % 128 == 0
    return 128 <= bits <= 65536 and bits & (bits - 1) == 0


def _verify_shared_native_input_identity(
    records: Sequence[Mapping[str, object]],
) -> None:
    if len({record["compiler_input_sha256"] for record in records}) > 1:
        raise ReleaseProductionError(
            "native evidence records do not share one compiler-input identity"
        )


def _verify_generated_package_metadata(
    archive_path: Path,
    metadata: ReleaseMetadata,
    config: ReleaseProductionConfig,
) -> GeneratedPackageIndex:
    try:
        return verify_generated_package(
            archive_path,
            product_id=metadata.product_id,
            product_version=metadata.product_version,
            rust_msrv=metadata.rust_msrv,
            config=config.generated_bundles,
        )
    except ReleaseBundleError as error:
        raise ReleaseProductionError(str(error)) from error


def _native_target_bundle(
    package: GeneratedPackageIndex,
    spec: NativeEvidenceSpec,
) -> GeneratedBundleRecord:
    try:
        return package.exact_bundle("cpp", (spec.target,))
    except ReleaseBundleError as error:
        raise ReleaseProductionError(
            f"native evidence target {spec.target!r} has no exact C++ bundle"
        ) from error


def _verify_vsix_identity(
    path: Path,
    *,
    target: str,
    metadata: ReleaseMetadata,
    commit: str,
) -> None:
    try:
        with ZipFile(path) as archive:
            package = json.loads(archive.read("extension/package.json"))
            runtime = json.loads(
                archive.read("extension/server/release-manifest.json")
            )
    except (BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise ReleaseProductionError(
            f"cannot inspect VSIX identity: {path.name}"
        ) from exc
    if not isinstance(package, dict) or not isinstance(runtime, dict):
        raise ReleaseProductionError(f"VSIX {path.name} has invalid JSON manifests")
    expected = {
        "target": target,
        "compiler_version": metadata.compiler_version,
        "extension_version": metadata.editor_version,
        "source_commit": commit,
        "source_dirty": False,
    }
    for key, value in expected.items():
        if runtime.get(key) != value:
            raise ReleaseProductionError(
                f"VSIX {path.name} has invalid runtime identity {key!r}"
            )
    if package.get("version") != metadata.editor_version:
        raise ReleaseProductionError(f"VSIX {path.name} has a stale extension version")


def _verify_sidecar(path: Path, checksum_path: Path) -> None:
    if not path.is_file() or not checksum_path.is_file():
        raise ReleaseProductionError(f"missing editor asset or checksum: {path.name}")
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1].lstrip("*") != path.name:
        raise ReleaseProductionError(
            f"invalid editor checksum sidecar: {checksum_path.name}"
        )
    if fields[0] != _file_sha256(path):
        raise ReleaseProductionError(f"editor checksum mismatch: {path.name}")


def _tar_info(
    name: str,
    *,
    is_dir: bool,
    executable: bool,
    epoch: int,
) -> tarfile.TarInfo:
    normalized = name.rstrip("/") + ("/" if is_dir else "")
    info = tarfile.TarInfo(normalized)
    info.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    info.mode = 0o755 if is_dir or executable else 0o644
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = epoch
    return info


def _copy_new(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ReleaseProductionError(f"release input is missing: {source}")
    if destination.exists():
        raise ReleaseProductionError(
            f"refusing to replace release asset: {destination}"
        )
    shutil.copyfile(source, destination)


def _require_major(
    component: str,
    version: str,
    majors: Mapping[object, object],
) -> None:
    required = majors.get(component)
    try:
        actual = int(version.split(".", 1)[0])
    except ValueError as exc:
        raise ReleaseProductionError(
            f"invalid {component} version {version!r}"
        ) from exc
    if not isinstance(required, int) or actual != required:
        raise ReleaseProductionError(
            f"{component} version {version!r} does not satisfy "
            f"required major {required!r}"
        )


def _rooted(root: Path, payload: Mapping[str, object], key: str) -> Path:
    value = _required_string(payload, key)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ReleaseProductionError(f"{key} must be a repository-relative path")
    return root / path


def _required_string(payload: Mapping[object, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ReleaseProductionError(f"{key} must be a non-empty string")
    return value


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ReleaseProductionError(f"{field} must be a list of non-empty strings")
    return tuple(value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseProductionError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseProductionError(f"JSON root must be an object: {path}")
    return payload


def _canonical_json(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args), cwd=root, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    metadata = subparsers.add_parser(
        "metadata", help="validate and print release metadata"
    )
    metadata.add_argument("--tag", required=True)
    metadata.add_argument("--commit")
    metadata.add_argument("--verify-tag", action="store_true")

    archive = subparsers.add_parser(
        "archive", help="write one normalized tar.gz archive"
    )
    archive.add_argument("--kind", choices=("generated", "docs"), required=True)
    archive.add_argument("--source", type=Path, required=True)
    archive.add_argument("--output", type=Path, required=True)
    archive.add_argument("--epoch", type=int, required=True)

    assemble = subparsers.add_parser(
        "assemble", help="stage the exact release asset set"
    )
    assemble.add_argument("--tag", required=True)
    assemble.add_argument("--commit", required=True)
    assemble.add_argument("--epoch", type=int, required=True)
    assemble.add_argument("--generated-archive", type=Path, required=True)
    assemble.add_argument("--docs-archive", type=Path, required=True)
    assemble.add_argument("--editor-assets", type=Path, required=True)
    assemble.add_argument("--evidence-dir", type=Path)
    assemble.add_argument("--output-dir", type=Path, required=True)

    verify = subparsers.add_parser(
        "verify-assets", help="verify a staged/downloaded release"
    )
    verify.add_argument("--tag", required=True)
    verify.add_argument("--directory", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = (
            args.config.resolve().parents[2]
            if args.config != DEFAULT_CONFIG
            else REPO_ROOT
        )
        config = load_config(args.config, root=root)
        if args.command == "metadata":
            metadata = release_metadata(args.tag, config=config)
            if args.verify_tag:
                if args.commit is None:
                    raise ReleaseProductionError("--verify-tag requires --commit")
                verify_tag_commit(args.tag, args.commit, root=root)
            print(_canonical_json(asdict(metadata)), end="")
        elif args.command == "archive":
            policy = _read_json(config.release_policy)
            product = policy.get("product")
            if not isinstance(product, dict):
                raise ReleaseProductionError("release policy has no product object")
            version = _required_string(product, "version")
            write_deterministic_archive(
                args.source,
                args.output,
                prefix=f"tsl-{args.kind}-{version}",
                epoch=args.epoch,
            )
            verify_deterministic_archive(args.output, epoch=args.epoch)
        elif args.command == "assemble":
            metadata = release_metadata(args.tag, config=config)
            assemble_release(
                metadata=metadata,
                config=config,
                commit=args.commit,
                epoch=args.epoch,
                generated_archive=args.generated_archive,
                docs_archive=args.docs_archive,
                editor_assets=args.editor_assets,
                evidence_dir=args.evidence_dir,
                output_dir=args.output_dir,
            )
            verify_release_assets(args.output_dir, tag=args.tag, config=config)
        else:
            verify_release_assets(args.directory, tag=args.tag, config=config)
    except (
        OSError,
        ReleaseProductionError,
        subprocess.CalledProcessError,
        tarfile.TarError,
        tomllib.TOMLDecodeError,
        UnicodeDecodeError,
    ) as exc:
        print(f"release production failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
