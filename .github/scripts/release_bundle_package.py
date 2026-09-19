"""Typed layout, source inspection, and archive verification for release bundles."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tomllib
from typing import Mapping


HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ReleaseBundleError(RuntimeError):
    """A release bundle config, generated root, or archive is invalid."""


@dataclass(frozen=True, slots=True)
class GeneratedBundleConfig:
    layout_id: str
    release_contract: Path
    backend_grouping: tuple[tuple[str, str], ...]
    backend_product_markers: tuple[tuple[str, str], ...]
    generated_scope_additions: tuple[tuple[str, tuple[str, ...]], ...]
    generated_scope_omissions: tuple[tuple[str, tuple[str, ...]], ...]
    shared_artifact_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedBundleSpec:
    bundle_id: str
    backend_id: str
    profiles: tuple[str, ...]
    generated_scope: tuple[str, ...]

    @property
    def relative_path(self) -> PurePosixPath:
        return PurePosixPath("bundles") / self.bundle_id


@dataclass(frozen=True, slots=True)
class GeneratedBundleArtifact:
    spec: GeneratedBundleSpec
    artifact_manifest_sha256: str
    extracted_size_bytes: int


@dataclass(frozen=True, slots=True)
class GeneratedBundleRecord:
    bundle_id: str
    backend_id: str
    profiles: tuple[str, ...]
    generated_scope: tuple[str, ...]
    relative_path: PurePosixPath
    artifact_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class GeneratedPackageIndex:
    manifest_sha256: str
    bundles: tuple[GeneratedBundleRecord, ...]

    def exact_bundle(
        self, backend_id: str, profiles: tuple[str, ...]
    ) -> GeneratedBundleRecord:
        matches = tuple(
            bundle
            for bundle in self.bundles
            if bundle.backend_id == backend_id and bundle.profiles == profiles
        )
        if len(matches) != 1:
            raise ReleaseBundleError(
                f"generated package has no exact {backend_id} bundle for "
                + ",".join(profiles)
            )
        return matches[0]


def load_generated_bundle_config(
    payload: Mapping[str, object], *, root: Path
) -> GeneratedBundleConfig:
    raw = payload.get("generated_bundles")
    if not isinstance(raw, dict):
        raise ReleaseBundleError("generated_bundles must be an object")
    layout_id = _required_safe_id(raw, "layout", owner="generated_bundles")
    contract_value = _required_string(
        raw, "release_contract", owner="generated_bundles"
    )
    contract_path = Path(contract_value)
    if contract_path.is_absolute() or ".." in contract_path.parts:
        raise ReleaseBundleError(
            "generated_bundles release_contract must be repository-relative"
        )

    raw_grouping = raw.get("backend_grouping")
    if not isinstance(raw_grouping, dict) or not raw_grouping:
        raise ReleaseBundleError(
            "generated_bundles backend_grouping must be a non-empty object"
        )
    grouping: list[tuple[str, str]] = []
    for backend_id, mode in raw_grouping.items():
        if (
            not isinstance(backend_id, str)
            or SAFE_ID.fullmatch(backend_id) is None
            or mode not in {"per_profile", "combined"}
        ):
            raise ReleaseBundleError(
                "generated_bundles backend_grouping is invalid"
            )
        grouping.append((backend_id, mode))

    raw_markers = raw.get("backend_product_markers")
    if not isinstance(raw_markers, dict) or set(raw_markers) != set(raw_grouping):
        raise ReleaseBundleError(
            "generated_bundles backend_product_markers must cover every backend"
        )
    markers: list[tuple[str, str]] = []
    for backend_id, marker in raw_markers.items():
        if (
            not isinstance(backend_id, str)
            or not isinstance(marker, str)
            or not marker
            or marker in {".", ".."}
            or PurePosixPath(marker).name != marker
        ):
            raise ReleaseBundleError(
                "generated_bundles backend_product_markers is invalid"
            )
        markers.append((backend_id, marker))

    additions = _scope_adjustments(
        raw,
        "generated_scope_additions",
        backend_ids=frozenset(raw_grouping),
    )
    omissions = _scope_adjustments(
        raw,
        "generated_scope_omissions",
        backend_ids=frozenset(raw_grouping),
    )
    additions_by_backend = dict(additions)
    omissions_by_backend = dict(omissions)
    overlapping_adjustments = tuple(
        sorted(
            backend_id
            for backend_id in raw_grouping
            if set(additions_by_backend.get(backend_id, ()))
            & set(omissions_by_backend.get(backend_id, ()))
        )
    )
    if overlapping_adjustments:
        raise ReleaseBundleError(
            "generated_bundles scope additions and omissions overlap for: "
            + ", ".join(overlapping_adjustments)
        )
    shared_roots_value = raw.get("shared_artifact_roots", [])
    if (
        not isinstance(shared_roots_value, list)
        or any(
            not isinstance(value, str) or SAFE_ID.fullmatch(value) is None
            for value in shared_roots_value
        )
        or len(shared_roots_value) != len(set(shared_roots_value))
        or any(value in raw_grouping for value in shared_roots_value)
    ):
        raise ReleaseBundleError(
            "generated_bundles shared_artifact_roots is invalid"
        )
    return GeneratedBundleConfig(
        layout_id=layout_id,
        release_contract=root / contract_path,
        backend_grouping=tuple(grouping),
        backend_product_markers=tuple(markers),
        generated_scope_additions=tuple(additions),
        generated_scope_omissions=tuple(omissions),
        shared_artifact_roots=tuple(shared_roots_value),
    )


def _scope_adjustments(
    raw: Mapping[str, object],
    field: str,
    *,
    backend_ids: frozenset[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    value = raw.get(field, {})
    if not isinstance(value, dict):
        raise ReleaseBundleError(f"generated_bundles {field} must be an object")
    adjustments: list[tuple[str, tuple[str, ...]]] = []
    for backend_id, names in value.items():
        if (
            not isinstance(backend_id, str)
            or backend_id not in backend_ids
            or not isinstance(names, list)
            or any(
                not isinstance(name, str) or SAFE_ID.fullmatch(name) is None
                for name in names
            )
            or len(names) != len(set(names))
        ):
            raise ReleaseBundleError(f"generated_bundles {field} is invalid")
        adjustments.append((backend_id, tuple(names)))
    return tuple(adjustments)


def expected_generated_bundles(
    contract: Mapping[str, object], config: GeneratedBundleConfig
) -> tuple[GeneratedBundleSpec, ...]:
    raw_backends = contract.get("backends")
    if not isinstance(raw_backends, list):
        raise ReleaseBundleError("release contract has no backends array")
    grouping = dict(config.backend_grouping)
    additions = dict(config.generated_scope_additions)
    omissions = dict(config.generated_scope_omissions)
    seen: set[str] = set()
    result: list[GeneratedBundleSpec] = []
    for raw_backend in raw_backends:
        if not isinstance(raw_backend, dict):
            raise ReleaseBundleError("release contract backends must be objects")
        backend_id = _required_safe_id(
            raw_backend, "id", owner="release backend"
        )
        if backend_id in seen:
            raise ReleaseBundleError(f"duplicate release backend {backend_id!r}")
        seen.add(backend_id)
        profiles = _release_profiles(raw_backend, backend_id=backend_id)
        unknown_omissions = tuple(
            sorted(set(omissions.get(backend_id, ())) - set(profiles))
        )
        if unknown_omissions:
            raise ReleaseBundleError(
                f"release backend {backend_id!r} has generated-scope omissions "
                "outside its profiles: "
                + ", ".join(unknown_omissions)
            )
        mode = grouping.get(backend_id)
        groups: tuple[tuple[str, ...], ...]
        if mode == "per_profile":
            groups = tuple((profile,) for profile in profiles)
        elif mode == "combined":
            groups = (profiles,)
        else:
            raise ReleaseBundleError(
                f"release backend {backend_id!r} has no release packaging policy"
            )
        for group in groups:
            suffix = group[0] if mode == "per_profile" else "release"
            result.append(
                GeneratedBundleSpec(
                    bundle_id=f"{backend_id}-{suffix}",
                    backend_id=backend_id,
                    profiles=group,
                    generated_scope=tuple(
                        sorted(
                            (set(group) - set(omissions.get(backend_id, ())))
                            | set(additions.get(backend_id, ()))
                        )
                    ),
                )
            )
    if seen != set(grouping):
        raise ReleaseBundleError(
            "release contract and generated bundle backend policies disagree"
        )
    bundle_ids = tuple(bundle.bundle_id for bundle in result)
    if len(bundle_ids) != len(set(bundle_ids)):
        raise ReleaseBundleError("release bundle IDs are not unique")
    return tuple(result)


def validate_release_contract_baseline(
    contract: Mapping[str, object], baseline_path: Path
) -> None:
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseBundleError(
            f"cannot load release contract baseline: {baseline_path}"
        ) from error
    if not isinstance(baseline, dict) or json_sha256(baseline) != json_sha256(contract):
        raise ReleaseBundleError(
            "release contract does not match its checked-in support baseline"
        )


def inspect_generated_bundle(
    spec: GeneratedBundleSpec, root: Path, config: GeneratedBundleConfig
) -> GeneratedBundleArtifact:
    manifest_path = root / ".tslc-manifest.json"
    backend_root = root / spec.backend_id
    if not manifest_path.is_file() or not backend_root.is_dir():
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} is missing its manifest or backend"
        )
    public_api_path = backend_root / "public-api.json"
    public_api = _read_json(
        public_api_path,
        message=f"generated bundle {spec.bundle_id!r} has no valid public API manifest",
    )
    if (
        public_api.get("backend") != spec.backend_id
        or public_api.get("scope") != list(spec.generated_scope)
    ):
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} has the wrong public API scope"
        )
    artifact_manifest = _read_json(
        manifest_path,
        message=f"generated bundle {spec.bundle_id!r} has an invalid artifact manifest",
    )
    artifacts = artifact_manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} has no artifact inventory"
        )
    inventory = _artifact_inventory(
        artifacts, owner=f"generated bundle {spec.bundle_id!r}"
    )
    _require_bundle_artifact_roots(
        inventory,
        backend_id=spec.backend_id,
        shared_roots=config.shared_artifact_roots,
        owner=f"generated bundle {spec.bundle_id!r}",
    )
    actual_files = {
        PurePosixPath(path.relative_to(root).as_posix()): path
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(inventory) != set(actual_files):
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} artifact inventory is not exact"
        )
    for relative, path in actual_files.items():
        if sha256(path.read_bytes()).hexdigest() != inventory[relative]:
            raise ReleaseBundleError(
                f"generated bundle {spec.bundle_id!r} has stale artifact digest: "
                f"{relative}"
            )
    _require_public_api_binding(
        inventory,
        backend_id=spec.backend_id,
        owner=f"generated bundle {spec.bundle_id!r}",
    )
    other_backends = tuple(
        backend_id
        for backend_id, _marker in config.backend_product_markers
        if backend_id != spec.backend_id and (root / backend_id).exists()
    )
    if other_backends:
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} contains unexpected backends: "
            + ", ".join(other_backends)
        )
    marker = dict(config.backend_product_markers)[spec.backend_id]
    if not (backend_root / marker).is_file():
        raise ReleaseBundleError(
            f"generated bundle {spec.bundle_id!r} is missing its backend product"
        )
    return GeneratedBundleArtifact(
        spec=spec,
        artifact_manifest_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
        extracted_size_bytes=sum(
            path.stat().st_size for path in root.rglob("*") if path.is_file()
        ),
    )


def verify_generated_package(
    archive_path: Path,
    *,
    product_id: str,
    product_version: str,
    rust_msrv: str,
    config: GeneratedBundleConfig,
) -> GeneratedPackageIndex:
    contract = _read_json(config.release_contract, message="invalid release contract")
    expected = expected_generated_bundles(contract, config)
    files, sizes, digests = _generated_archive_inventory(
        archive_path,
        product_markers=tuple(
            marker for _backend, marker in config.backend_product_markers
        ),
    )
    manifest_bytes = files.get(PurePosixPath(".tsl-release-bundles.json"))
    if manifest_bytes is None:
        raise ReleaseBundleError(
            "generated archive has no .tsl-release-bundles.json"
        )
    if PurePosixPath("README.md") not in sizes:
        raise ReleaseBundleError("generated archive has no bundle README.md")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise ReleaseBundleError(
            "generated release bundle manifest is invalid JSON"
        ) from error
    if not isinstance(manifest, dict) or (
        manifest.get("schema_version") != 1
        or manifest.get("layout") != config.layout_id
        or manifest.get("release_contract_sha256") != json_sha256(contract)
        or manifest.get("product")
        != {"id": product_id, "version": product_version}
    ):
        raise ReleaseBundleError(
            "generated release bundle manifest does not match the release contract"
        )
    raw_records = manifest.get("bundles")
    if not isinstance(raw_records, list) or len(raw_records) != len(expected):
        raise ReleaseBundleError(
            "generated release bundle set does not match the release contract"
        )

    records = tuple(
        _verify_archive_bundle(
            raw,
            spec,
            config=config,
            files=files,
            sizes=sizes,
            digests=digests,
        )
        for raw, spec in zip(raw_records, expected, strict=True)
    )
    _verify_archive_paths(sizes, expected)
    for rust_bundle in (item for item in records if item.backend_id == "rust"):
        cargo_path = rust_bundle.relative_path / "rust" / "Cargo.toml"
        cargo_bytes = files[cargo_path]
        try:
            cargo = tomllib.loads(cargo_bytes.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise ReleaseBundleError(
                f"generated Cargo.toml is invalid: {rust_bundle.bundle_id}"
            ) from error
        package = cargo.get("package")
        if not isinstance(package, dict):
            raise ReleaseBundleError(
                f"generated Cargo.toml has no [package] table: "
                f"{rust_bundle.bundle_id}"
            )
        if package.get("version") != product_version:
            raise ReleaseBundleError(
                "generated Cargo version does not match release product: "
                f"{rust_bundle.bundle_id}"
            )
        if package.get("rust-version") != rust_msrv:
            raise ReleaseBundleError(
                "generated Cargo MSRV does not match release metadata: "
                f"{rust_bundle.bundle_id}"
            )
    return GeneratedPackageIndex(
        manifest_sha256=sha256(manifest_bytes).hexdigest(), bundles=records
    )


def json_sha256(payload: object) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _verify_archive_bundle(
    raw: object,
    expected: GeneratedBundleSpec,
    *,
    config: GeneratedBundleConfig,
    files: Mapping[PurePosixPath, bytes],
    sizes: Mapping[PurePosixPath, int],
    digests: Mapping[PurePosixPath, str],
) -> GeneratedBundleRecord:
    artifact_digest = (
        raw.get("artifact_manifest_sha256") if isinstance(raw, dict) else None
    )
    extracted_size = raw.get("extracted_size_bytes") if isinstance(raw, dict) else None
    if not isinstance(raw, dict) or (
        raw.get("id") != expected.bundle_id
        or raw.get("backend") != expected.backend_id
        or raw.get("profiles") != list(expected.profiles)
        or raw.get("generated_scope") != list(expected.generated_scope)
        or raw.get("path") != expected.relative_path.as_posix()
        or not isinstance(artifact_digest, str)
        or HEX_DIGEST.fullmatch(artifact_digest) is None
        or isinstance(extracted_size, bool)
        or not isinstance(extracted_size, int)
        or extracted_size <= 0
    ):
        raise ReleaseBundleError(
            f"generated release bundle record is invalid: {expected.bundle_id}"
        )
    inner_path = expected.relative_path / ".tslc-manifest.json"
    inner_bytes = files.get(inner_path)
    if inner_bytes is None or sha256(inner_bytes).hexdigest() != artifact_digest:
        raise ReleaseBundleError(
            f"generated bundle manifest digest is stale: {expected.bundle_id}"
        )
    try:
        inner = json.loads(inner_bytes)
    except json.JSONDecodeError as error:
        raise ReleaseBundleError(
            f"generated bundle has invalid artifact manifest: {expected.bundle_id}"
        ) from error
    artifacts = inner.get("artifacts") if isinstance(inner, dict) else None
    if not isinstance(artifacts, list):
        raise ReleaseBundleError(
            f"generated bundle has no artifact inventory: {expected.bundle_id}"
        )
    inventory = _artifact_inventory(
        artifacts, owner=f"generated bundle {expected.bundle_id!r}"
    )
    _require_bundle_artifact_roots(
        inventory,
        backend_id=expected.backend_id,
        shared_roots=config.shared_artifact_roots,
        owner=f"generated bundle {expected.bundle_id!r}",
    )
    actual_files = {
        PurePosixPath(*path.parts[len(expected.relative_path.parts) :])
        for path in sizes
        if expected.relative_path in path.parents
        and path != expected.relative_path / ".tslc-manifest.json"
    }
    if set(inventory) != actual_files:
        raise ReleaseBundleError(
            f"generated bundle artifact inventory is not exact: {expected.bundle_id}"
        )
    for relative, declared_digest in inventory.items():
        archive_path = expected.relative_path / relative
        if digests.get(archive_path) != declared_digest:
            raise ReleaseBundleError(
                f"generated bundle has stale artifact digest: "
                f"{expected.bundle_id}:{relative}"
            )
    public_path = expected.relative_path / expected.backend_id / "public-api.json"
    public_bytes = files.get(public_path)
    if public_bytes is None:
        raise ReleaseBundleError(
            f"generated bundle has no public API manifest: {expected.bundle_id}"
        )
    try:
        public_api = json.loads(public_bytes)
    except json.JSONDecodeError as error:
        raise ReleaseBundleError(
            f"generated bundle has invalid public API manifest: {expected.bundle_id}"
        ) from error
    if not isinstance(public_api, dict) or (
        public_api.get("backend") != expected.backend_id
        or public_api.get("scope") != list(expected.generated_scope)
    ):
        raise ReleaseBundleError(
            f"generated bundle has the wrong public API scope: {expected.bundle_id}"
        )
    _require_public_api_binding(
        inventory,
        backend_id=expected.backend_id,
        owner=f"generated bundle {expected.bundle_id!r}",
    )
    actual_size = sum(
        size for path, size in sizes.items() if expected.relative_path in path.parents
    )
    if actual_size != extracted_size:
        raise ReleaseBundleError(
            f"generated bundle extracted size is stale: {expected.bundle_id}"
        )
    marker = dict(config.backend_product_markers)[expected.backend_id]
    if expected.relative_path / expected.backend_id / marker not in files:
        raise ReleaseBundleError(
            f"generated bundle is missing its {expected.backend_id} product: "
            f"{expected.bundle_id}"
        )
    return GeneratedBundleRecord(
        bundle_id=expected.bundle_id,
        backend_id=expected.backend_id,
        profiles=expected.profiles,
        generated_scope=expected.generated_scope,
        relative_path=expected.relative_path,
        artifact_manifest_sha256=artifact_digest,
    )


def _artifact_inventory(
    artifacts: list[object], *, owner: str
) -> dict[PurePosixPath, str]:
    result: dict[PurePosixPath, str] = {}
    for item in artifacts:
        if not isinstance(item, dict):
            raise ReleaseBundleError(f"{owner} has an invalid artifact record")
        logical_path = item.get("logical_path")
        digest = item.get("digest")
        if (
            not isinstance(logical_path, str)
            or not logical_path
            or PurePosixPath(logical_path).is_absolute()
            or ".." in PurePosixPath(logical_path).parts
            or not isinstance(digest, str)
            or HEX_DIGEST.fullmatch(digest) is None
        ):
            raise ReleaseBundleError(f"{owner} has an invalid artifact record")
        path = PurePosixPath(logical_path)
        if path in result:
            raise ReleaseBundleError(f"{owner} has duplicate artifact paths")
        result[path] = digest
    return result


def _require_public_api_binding(
    inventory: Mapping[PurePosixPath, str],
    *,
    backend_id: str,
    owner: str,
) -> None:
    if PurePosixPath(backend_id) / "public-api.json" not in inventory:
        raise ReleaseBundleError(f"{owner} does not bind its public API scope")


def _require_bundle_artifact_roots(
    inventory: Mapping[PurePosixPath, str],
    *,
    backend_id: str,
    shared_roots: tuple[str, ...],
    owner: str,
) -> None:
    allowed = {backend_id, *shared_roots}
    if any(not path.parts or path.parts[0] not in allowed for path in inventory):
        raise ReleaseBundleError(
            f"{owner} contains artifacts outside its declared roots"
        )


def _verify_archive_paths(
    sizes: Mapping[PurePosixPath, int], expected: tuple[GeneratedBundleSpec, ...]
) -> None:
    permitted = tuple(item.relative_path for item in expected)
    for path in sizes:
        if path in {
            PurePosixPath(".tsl-release-bundles.json"),
            PurePosixPath("README.md"),
        }:
            continue
        if not any(root in path.parents for root in permitted):
            raise ReleaseBundleError(
                f"generated archive has an undeclared bundle path: {path}"
            )


def _generated_archive_inventory(
    archive_path: Path,
    *,
    product_markers: tuple[str, ...],
) -> tuple[
    dict[PurePosixPath, bytes],
    dict[PurePosixPath, int],
    dict[PurePosixPath, str],
]:
    selected: dict[PurePosixPath, bytes] = {}
    sizes: dict[PurePosixPath, int] = {}
    digests: dict[PurePosixPath, str] = {}
    archive_root: str | None = None
    with tarfile.open(archive_path, "r|gz") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ReleaseBundleError(
                    f"generated archive has unsafe path: {member.name}"
                )
            if archive_root is None:
                archive_root = path.parts[0]
            elif path.parts[0] != archive_root:
                raise ReleaseBundleError(
                    "generated archive must contain exactly one versioned root"
                )
            if not member.isfile() and not member.isdir():
                raise ReleaseBundleError(
                    f"generated archive contains a link or special file: {member.name}"
                )
            if member.isdir():
                continue
            if len(path.parts) < 2:
                raise ReleaseBundleError(
                    f"generated archive file has no versioned root: {member.name}"
                )
            relative = PurePosixPath(*path.parts[1:])
            if relative in sizes:
                raise ReleaseBundleError(
                    f"generated archive has duplicate file: {relative}"
                )
            sizes[relative] = member.size
            retain = (
                relative == PurePosixPath(".tsl-release-bundles.json")
                or relative.name
                in {
                    ".tslc-manifest.json",
                    "public-api.json",
                    *product_markers,
                }
            )
            handle = archive.extractfile(member)
            if handle is None:
                raise ReleaseBundleError(
                    f"generated archive member is unreadable: {member.name}"
                )
            digest = sha256()
            retained = bytearray() if retain else None
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                if retained is not None:
                    retained.extend(chunk)
            digests[relative] = digest.hexdigest()
            if retained is not None:
                selected[relative] = bytes(retained)
    return selected, sizes, digests


def _release_profiles(
    backend: Mapping[str, object], *, backend_id: str
) -> tuple[str, ...]:
    raw_profiles = backend.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ReleaseBundleError(f"release backend {backend_id!r} has no profiles")
    profiles: list[str] = []
    for item in raw_profiles:
        if not isinstance(item, dict):
            raise ReleaseBundleError(
                f"release backend {backend_id!r} profiles must be objects"
            )
        profiles.append(
            _required_safe_id(
                item, "name", owner=f"release backend {backend_id!r}"
            )
        )
    if len(profiles) != len(set(profiles)):
        raise ReleaseBundleError(
            f"release backend {backend_id!r} contains duplicate profiles"
        )
    return tuple(profiles)


def _required_safe_id(
    payload: Mapping[str, object], field: str, *, owner: str
) -> str:
    value = _required_string(payload, field, owner=owner)
    if SAFE_ID.fullmatch(value) is None:
        raise ReleaseBundleError(f"{owner} has unsafe {field} {value!r}")
    return value


def _required_string(
    payload: Mapping[str, object], field: str, *, owner: str
) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ReleaseBundleError(f"{owner} has invalid {field}")
    return value


def _read_json(path: Path, *, message: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseBundleError(f"{message}: {path}") from error
    if not isinstance(payload, dict):
        raise ReleaseBundleError(f"{message}: {path}")
    return payload


__all__ = (
    "GeneratedBundleArtifact",
    "GeneratedBundleConfig",
    "GeneratedBundleRecord",
    "GeneratedBundleSpec",
    "GeneratedPackageIndex",
    "ReleaseBundleError",
    "expected_generated_bundles",
    "inspect_generated_bundle",
    "json_sha256",
    "load_generated_bundle_config",
    "validate_release_contract_baseline",
    "verify_generated_package",
)
