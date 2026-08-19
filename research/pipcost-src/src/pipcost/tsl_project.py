"""Generated TSL consumption pinned to an exact repository release."""

from __future__ import annotations

from dataclasses import dataclass
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from typing import Any, cast

from pipcost.records import digest_file, digest_json, read_json, write_json
from pipcost.workspace import WorkspacePaths

DEFAULT_TSL_REF = "v0.2.7"
REQUIRED_PRIMITIVES = (
    "hadd",
    "less_than",
    "load",
    "mask_binary_and",
    "select",
    "set1",
)


@dataclass(frozen=True, slots=True)
class TslSourceEvidence:
    requested_ref: str
    commit: str
    snapshot_root: Path
    manifest: dict[str, Any]


@dataclass(frozen=True, slots=True)
class GenerationEvidence:
    generation_id: str
    output_root: Path
    profile: str
    simd_lanes: int
    tsl_ref: str
    tsl_commit: str
    manifest: dict[str, Any]

    @property
    def cpp_root(self) -> Path:
        return self.output_root / "cpp"


def _git(paths: WorkspacePaths, arguments: list[str], *, binary: bool = False) -> Any:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=paths.root,
        check=False,
        capture_output=True,
        text=not binary,
    )
    if completed.returncode != 0:
        stderr = completed.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: {str(stderr).strip()}"
        )
    return completed.stdout


def _validate_archive_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"unsafe path in TSL source archive: {member.name}")
    if not (member.isdir() or member.isfile()):
        raise RuntimeError(
            f"unsupported entry in TSL source archive: {member.name}"
        )


def _source_digest(root: Path) -> tuple[str, tuple[tuple[str, str], ...]]:
    entries = tuple(
        (path.relative_to(root).as_posix(), digest_file(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "pipcost-tsl-source.json"
    )
    return digest_json(entries), entries


def resolve_tsl_source(
    paths: WorkspacePaths,
    tsl_ref: str = DEFAULT_TSL_REF,
) -> TslSourceEvidence:
    if not tsl_ref.strip():
        raise ValueError("TSL ref must not be empty")
    commit = str(
        _git(paths, ["rev-parse", "--verify", f"{tsl_ref}^{{commit}}"])
    ).strip()
    snapshot_root = paths.output_path("tsl-sources", commit)
    manifest_path = snapshot_root / "pipcost-tsl-source.json"
    if not manifest_path.is_file():
        archive = cast(
            bytes,
            _git(
                paths,
                [
                    "archive",
                    "--format=tar",
                    commit,
                    "--",
                    "tslc",
                    "tsldata",
                    "supplementary/buildsystem/machine_profiles.json",
                ],
                binary=True,
            ),
        )
        snapshot_root.mkdir(parents=True, exist_ok=False)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            members = source.getmembers()
            for member in members:
                _validate_archive_member(member)
            source.extractall(snapshot_root, members=members)
        source_digest, source_files = _source_digest(snapshot_root)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "requested_ref": tsl_ref,
            "commit": commit,
            "source_digest": source_digest,
            "source_files": [
                {"path": path, "sha256": digest}
                for path, digest in source_files
            ],
        }
        write_json(manifest_path, manifest)
    else:
        manifest = read_json(manifest_path)
        if manifest.get("commit") != commit:
            raise RuntimeError("TSL source snapshot commit does not match its manifest")
        source_digest, source_files = _source_digest(snapshot_root)
        recorded_files = tuple(
            (str(item["path"]), str(item["sha256"]))
            for item in manifest["source_files"]
        )
        if (
            source_digest != manifest.get("source_digest")
            or source_files != recorded_files
        ):
            raise RuntimeError("TSL source snapshot differs from its manifest")
    return TslSourceEvidence(
        requested_ref=tsl_ref,
        commit=commit,
        snapshot_root=snapshot_root,
        manifest=manifest,
    )


def generation_identity(
    profile: str,
    simd_lanes: int,
    tsl_commit: str,
) -> str:
    request = {
        "schema_version": 2,
        "backend": "cpp",
        "profile": profile,
        "simd_lanes": simd_lanes,
        "tsl_commit": tsl_commit,
        "type_tags": ["si32"],
        "primitives": list(REQUIRED_PRIMITIVES),
    }
    return f"cpp-{profile}-{simd_lanes}-{tsl_commit[:10]}-{digest_json(request)[:12]}"


def _worker(
    paths: WorkspacePaths,
    source: TslSourceEvidence,
    *,
    output_root: Path,
    profile: str,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(paths.prototype_root / "src" / "pipcost" / "generate_worker.py"),
        "--source-root",
        str(source.snapshot_root),
        "--output-root",
        str(output_root),
        "--profile",
        profile,
    ]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(source.snapshot_root / "tslc" / "src"),
            str(paths.prototype_root / "src"),
        ]
    )
    completed = subprocess.run(
        command,
        cwd=paths.root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        value = cast(dict[str, Any], json.loads(completed.stdout))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "stable TSL generator did not return JSON: "
            + (completed.stderr or completed.stdout).strip()
        ) from exc
    if completed.returncode != 0 or value.get("status") != "ok":
        raise RuntimeError(
            "stable TSL generation failed: "
            + str(value.get("message", completed.stderr.strip()))
        )
    value["command"] = command
    return value


def generate_tsl_project(
    paths: WorkspacePaths,
    *,
    profile: str,
    simd_lanes: int,
    tsl_ref: str = DEFAULT_TSL_REF,
) -> GenerationEvidence:
    source = resolve_tsl_source(paths, tsl_ref)
    generation_id = generation_identity(profile, simd_lanes, source.commit)
    output_root = paths.output_path("generated", generation_id)
    worker = _worker(paths, source, output_root=output_root, profile=profile)
    artifact_manifest = worker["artifact_manifest"]
    request = {
        "backend": "cpp",
        "profile": profile,
        "simd_lanes": simd_lanes,
        "type_tags": ["si32"],
        "primitives": list(REQUIRED_PRIMITIVES),
    }
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "tsl_release": {
            "requested_ref": tsl_ref,
            "commit": source.commit,
            "source_digest": source.manifest["source_digest"],
        },
        "tslc_version": worker["tslc_version"],
        "generation_id": generation_id,
        "request": request,
        "generator_command": worker["command"],
        "artifact_manifest": artifact_manifest,
        "artifact_manifest_digest": digest_json([
            (item["logical_path"], item["sha256"])
            for item in artifact_manifest
        ]),
        "diagnostics": worker["diagnostics"],
        "coverage": worker["coverage"],
        "skipped": worker["skipped"],
        "emitted_profiles": worker["emitted_profiles"],
    }
    write_json(output_root / "pipcost-generation.json", manifest)
    return GenerationEvidence(
        generation_id=generation_id,
        output_root=output_root,
        profile=profile,
        simd_lanes=simd_lanes,
        tsl_ref=tsl_ref,
        tsl_commit=source.commit,
        manifest=manifest,
    )


def load_generation(
    paths: WorkspacePaths,
    *,
    profile: str,
    simd_lanes: int,
    tsl_ref: str = DEFAULT_TSL_REF,
) -> GenerationEvidence:
    source = resolve_tsl_source(paths, tsl_ref)
    generation_id = generation_identity(profile, simd_lanes, source.commit)
    output_root = paths.output_path("generated", generation_id)
    manifest_path = output_root / "pipcost-generation.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"generated TSL evidence does not exist: {manifest_path}"
        )
    value = read_json(manifest_path)
    release = value.get("tsl_release", {})
    if release.get("commit") != source.commit:
        raise RuntimeError("generated TSL evidence names a different release commit")
    return GenerationEvidence(
        generation_id=generation_id,
        output_root=output_root,
        profile=profile,
        simd_lanes=simd_lanes,
        tsl_ref=tsl_ref,
        tsl_commit=source.commit,
        manifest=value,
    )
