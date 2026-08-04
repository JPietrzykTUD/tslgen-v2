"""Isolated generation worker loaded from an exact TSL source snapshot."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import tomllib

from tslc.api import generate_project, write_artifacts

REQUIRED_PRIMITIVES = (
    "hadd",
    "less_than",
    "load",
    "mask_binary_and",
    "select",
    "set1",
)


def _diagnostic_record(diagnostic: object) -> dict[str, object]:
    return {
        "severity": str(getattr(diagnostic, "severity", "unknown")),
        "code": str(getattr(diagnostic, "code", "")),
        "message": str(getattr(diagnostic, "message", diagnostic)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()

    result = generate_project(
        [args.source_root / "tsldata"],
        machine_profiles_path=(
            args.source_root
            / "supplementary"
            / "buildsystem"
            / "machine_profiles.json"
        ),
        primitives=REQUIRED_PRIMITIVES,
        profiles=(args.profile,),
        type_tags=("si32",),
        backends=("cpp",),
        generation_mode="partial",
        test_harness=False,
    )
    errors = [
        item
        for item in result.diagnostics
        if getattr(item, "severity", "") == "error"
    ]
    if errors:
        print(json.dumps({
            "status": "error",
            "message": "; ".join(
                f"{getattr(item, 'code', 'error')}: "
                f"{getattr(item, 'message', item)}"
                for item in errors
            ),
        }))
        return 2

    emitted_roots = {
        entry.primitive
        for entry in result.coverage
        if entry.profile == args.profile
        and entry.backend == "cpp"
        and entry.type_tag == "si32"
    }
    missing = sorted(set(REQUIRED_PRIMITIVES) - emitted_roots)
    if missing:
        print(json.dumps({
            "status": "error",
            "message": "required generated primitive coverage is missing: "
            + ", ".join(missing),
        }))
        return 2

    report = write_artifacts(
        result.artifacts,
        args.output_root,
        mode="manifest-clean",
    )
    if report.diagnostics:
        print(json.dumps({
            "status": "error",
            "message": "; ".join(
                f"{item.code}: {item.message}" for item in report.diagnostics
            ),
        }))
        return 2

    project = tomllib.loads(
        (args.source_root / "tslc" / "pyproject.toml").read_text(encoding="utf-8")
    )
    print(json.dumps({
        "status": "ok",
        "tslc_version": str(project["project"]["version"]),
        "artifact_manifest": [
            {"logical_path": path, "sha256": digest}
            for path, digest in result.artifacts.digest_manifest()
        ],
        "diagnostics": [
            _diagnostic_record(item) for item in result.diagnostics
        ],
        "coverage": [
            asdict(item)
            for item in result.coverage
            if item.profile == args.profile
            and item.backend == "cpp"
            and item.type_tag == "si32"
        ],
        "skipped": [
            {
                "profile": item.profile,
                "backend": item.backend,
                "primitive": item.primitive,
                "extension": item.extension,
                "type_tag": item.type_tag,
                "status": item.status,
                "reason": item.reason,
            }
            for item in result.skipped
            if item.profile == args.profile
            and item.backend == "cpp"
            and item.type_tag == "si32"
        ],
        "emitted_profiles": sorted({
            item.profile.name
            for item in result.emitted_profiles
            if item.supports_backend("cpp")
        }),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
