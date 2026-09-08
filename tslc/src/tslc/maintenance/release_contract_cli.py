"""Command-line interface for the generated-library release contract."""

from __future__ import annotations

import argparse
import json
import sys

from tslc.maintenance import _repo_context
from tslc.maintenance.release_contract import (
    build_release_contract,
    canonical_json_path,
    canonical_markdown_path,
)
from tslc.maintenance.release_contract_render import render_markdown, serialize_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render, check, or update the TSL v1 release support contract."
    )
    parser.add_argument(
        "--format", choices=("text", "json", "markdown"), default="text"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    context = _repo_context.require_repo_context(parser)
    try:
        contract = build_release_contract(context)
        json_text = serialize_json(contract)
        markdown_text = render_markdown(contract)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"release contract failed: {error}", file=sys.stderr)
        return 2
    if args.update:
        json_path = canonical_json_path(context)
        markdown_path = canonical_markdown_path(context)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json_text, encoding="utf-8")
        markdown_path.write_text(markdown_text, encoding="utf-8")
        print(f"wrote {json_path}")
        print(f"wrote {markdown_path}")
        return 0
    if args.check:
        mismatches = [
            path
            for path, expected in (
                (canonical_json_path(context), json_text),
                (canonical_markdown_path(context), markdown_text),
            )
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if mismatches:
            print(
                "release support projections differ; review and run with --update: "
                + ", ".join(str(path) for path in mismatches),
                file=sys.stderr,
            )
            return 1
        print(
            "TSL v1 release contract OK: "
            f"{len(contract.callable_families)} primitive families, "
            f"{len(contract.algorithms)} algorithms"
        )
        return 0
    if args.format == "json":
        print(json_text, end="")
    elif args.format == "markdown":
        print(markdown_text, end="")
    else:
        for backend in contract.backends:
            profiles = ",".join(profile.name for profile in backend.profiles)
            print(f"{backend.backend_id}: {profiles}")
    return 0


__all__ = ("main",)
