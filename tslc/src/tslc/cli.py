"""Thin CLI: parse options, run the pipeline, write, optionally verify, exit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tslc", description="Compile TSL data to C++/Rust.")
    parser.add_argument(
        "--sources",
        nargs="+",
        required=True,
        help="explicit .tsl source paths or directories (dirs load all .tsl beneath them)",
    )
    parser.add_argument(
        "--machine-profiles",
        required=True,
        help="path to machine_profiles.json",
    )
    parser.add_argument("--primitives", default="add,hadd", help="comma-separated primitive names")
    parser.add_argument(
        "--profiles",
        default="scalar,sse2,avx,avx2,skylake",
        help="comma-separated machine profiles",
    )
    parser.add_argument(
        "--types",
        default="si8,si16,si32,si64,ui8,ui16,ui32,ui64,f32,f64",
        help="comma-separated type tags",
    )
    parser.add_argument("--backends", default="cpp,rust", help="comma-separated backends")
    parser.add_argument("--output-root", default=None, help="write artifacts under this root")
    parser.add_argument("--verify", action="store_true", help="build-verify after writing")
    parser.add_argument(
        "--cpp-compiler",
        default=None,
        help="C++ compiler command for build verification, e.g. /usr/bin/c++",
    )
    parser.add_argument(
        "--rust-compiler",
        default=None,
        help="Rust compiler executable for build verification, e.g. rustc",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="print a behavior-coverage report"
    )
    args = parser.parse_args(argv)

    result = generate_project(
        [Path(path) for path in args.sources],
        machine_profiles_path=args.machine_profiles,
        primitives=_split(args.primitives),
        profiles=_split(args.profiles),
        type_tags=_split(args.types),
        backends=_split(args.backends),
    )

    for diagnostic in result.diagnostics:
        location = f" {diagnostic.location.path}:{diagnostic.location.line}" if diagnostic.location else ""
        print(f"[{diagnostic.severity}] {diagnostic.code}{location}: {diagnostic.message}", file=sys.stderr)

    print(
        f"generated {len(result.coverage)} specializations across "
        f"{len(result.artifacts.artifacts)} artifacts"
    )

    if args.coverage:
        from tslc.coverage import format_coverage_report

        print(format_coverage_report(result))

    if has_errors(result.diagnostics):
        return 1

    if args.output_root is not None:
        write_report = write_artifacts(result.artifacts, args.output_root)
        for diagnostic in write_report.diagnostics:
            print(f"[write] {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
        if has_errors(write_report.diagnostics):
            return 1
        print(f"wrote {len(write_report.written)} files under {write_report.output_root}")

        if args.verify and result.rendered is not None:
            verify_report = verify_project(
                args.output_root,
                result.rendered.verify,
                cpp_compiler=args.cpp_compiler,
                rust_compiler=args.rust_compiler,
            )
            for note in verify_report.skipped:
                print(f"[verify-skip] {note}", file=sys.stderr)
            for diagnostic in verify_report.diagnostics:
                print(f"[verify] {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
            if has_errors(verify_report.diagnostics):
                return 1
            print(f"build-verified {len(verify_report.commands)} commands")

    return 0


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
