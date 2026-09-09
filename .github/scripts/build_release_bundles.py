#!/usr/bin/env python3
"""Build the generated-library release as independently consumable bundles."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Sequence

from release_bundle_package import (
    GeneratedBundleConfig,
    GeneratedBundleSpec,
    ReleaseBundleError,
    expected_generated_bundles,
    inspect_generated_bundle,
    json_sha256,
    load_generated_bundle_config,
    validate_release_contract_baseline,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MACHINE_PROFILES = Path("supplementary/buildsystem/machine_profiles.json")
DEFAULT_PRODUCTION_CONFIG = Path("supplementary/release/tsl-v1-production.json")
Generate = Callable[[GeneratedBundleSpec, Path], None]


def build_release_bundles(
    contract: Mapping[str, object],
    config: GeneratedBundleConfig,
    output_root: Path,
    *,
    generate: Generate,
) -> dict[str, object]:
    """Generate every bundle and write its deterministic root manifest."""
    if output_root.exists() and any(output_root.iterdir()):
        raise ReleaseBundleError(
            f"release bundle output directory is not empty: {output_root}"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    specs = expected_generated_bundles(contract, config)
    built = []
    for spec in specs:
        bundle_root = output_root / Path(spec.relative_path)
        generate(spec, bundle_root)
        built.append(inspect_generated_bundle(spec, bundle_root, config))

    product = contract.get("product")
    if not isinstance(product, dict):
        raise ReleaseBundleError("release contract has no product object")
    product_id = product.get("id")
    product_version = product.get("version")
    if not isinstance(product_id, str) or not isinstance(product_version, str):
        raise ReleaseBundleError("release contract has invalid product identity")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "product": {"id": product_id, "version": product_version},
        "release_contract_sha256": json_sha256(contract),
        "layout": config.layout_id,
        "bundles": [
            {
                "id": item.spec.bundle_id,
                "backend": item.spec.backend_id,
                "profiles": list(item.spec.profiles),
                "generated_scope": list(item.spec.generated_scope),
                "path": item.spec.relative_path.as_posix(),
                "artifact_manifest_sha256": item.artifact_manifest_sha256,
                "extracted_size_bytes": item.extracted_size_bytes,
            }
            for item in built
        ],
    }
    (output_root / ".tsl-release-bundles.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output_root / "README.md").write_text(
        _bundle_readme(product_version=product_version, bundles=specs),
        encoding="utf-8",
    )
    return manifest


def _load_release_contract() -> dict[str, object]:
    environment = os.environ.copy()
    source_root = str(REPO_ROOT / "tslc" / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing}" if existing else source_root
    )
    completed = subprocess.run(
        [sys.executable, "-m", "tslc", "release", "contract", "--format", "json"],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ReleaseBundleError(f"release contract command failed: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseBundleError(
            "release contract command returned invalid JSON"
        ) from error
    if not isinstance(payload, dict):
        raise ReleaseBundleError("release contract command did not return an object")
    return payload


def _generator(machine_profiles: Path) -> Generate:
    def generate(spec: GeneratedBundleSpec, output_root: Path) -> None:
        profiles = ",".join(spec.profiles)
        command = [
            str(REPO_ROOT / "dev.sh"),
            "generate",
            "--machine-profiles",
            str(machine_profiles),
            "--profiles",
            profiles,
            "--backend-profiles",
            f"{spec.backend_id}={profiles}",
            "--backends",
            spec.backend_id,
            "--output-root",
            str(output_root),
        ]
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if completed.returncode != 0:
            raise ReleaseBundleError(
                f"generation failed for release bundle {spec.bundle_id!r}"
            )

    return generate


def _bundle_readme(
    *, product_version: str, bundles: Sequence[GeneratedBundleSpec]
) -> str:
    rows = "\n".join(
        f"| `{bundle.bundle_id}` | `{bundle.backend_id}` | "
        f"`{','.join(bundle.profiles)}` | `{bundle.relative_path.as_posix()}` |"
        for bundle in bundles
    )
    return f"""# TSL {product_version} generated-library bundles

This archive contains independently consumable generated projects. Extract only
the bundle needed by the deployment; extracting every bundle recreates the
all-profile stress footprint and is not the normal installation path.

| Bundle | Backend | Profiles | Path |
| --- | --- | --- | --- |
{rows}

Each bundle is a normal generated root with its own `.tslc-manifest.json` and
one backend directory. For C++, point CMake at `<path>/cpp`. For Rust, use
`bundles/rust-release/rust` as the Cargo path dependency. The root
`.tsl-release-bundles.json` binds this table to the exact release contract and
artifact manifests.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--machine-profiles", type=Path, default=DEFAULT_MACHINE_PROFILES
    )
    parser.add_argument(
        "--production-config", type=Path, default=DEFAULT_PRODUCTION_CONFIG
    )
    args = parser.parse_args(argv)
    machine_profiles = args.machine_profiles
    if not machine_profiles.is_absolute():
        machine_profiles = REPO_ROOT / machine_profiles
    production_config = args.production_config
    if not production_config.is_absolute():
        production_config = REPO_ROOT / production_config
    try:
        production_payload = json.loads(
            production_config.read_text(encoding="utf-8")
        )
        if not isinstance(production_payload, dict):
            raise ReleaseBundleError("release production config must be an object")
        config = load_generated_bundle_config(production_payload, root=REPO_ROOT)
        contract = _load_release_contract()
        validate_release_contract_baseline(contract, config.release_contract)
        manifest = build_release_bundles(
            contract,
            config,
            args.output_root,
            generate=_generator(machine_profiles),
        )
    except (OSError, json.JSONDecodeError, ReleaseBundleError) as error:
        print(f"release bundle build failed: {error}", file=sys.stderr)
        return 1
    print(
        f"built {len(manifest['bundles'])} release bundles in {args.output_root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
