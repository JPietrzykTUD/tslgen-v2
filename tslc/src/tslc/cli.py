"""Thin CLI: parse options, run the pipeline, write, optionally verify, exit."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from tslc.api import generate_project, verify_project, write_artifacts
from tslc.diagnostics import has_errors
from tslc.output.verify import BuildVerificationReport


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
    parser.add_argument(
        "--primitives",
        default=None,
        help="comma-separated primitive names; omit to generate every catalog primitive",
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help=(
            "comma-separated machine profile names; omit to generate every "
            "loaded machine profile"
        ),
    )
    parser.add_argument(
        "--types",
        default="si8,si16,si32,si64,ui8,ui16,ui32,ui64,f32,f64",
        help="comma-separated type tags",
    )
    parser.add_argument("--backends", default="cpp,rust", help="comma-separated backends")
    parser.add_argument(
        "--generation-mode",
        choices=("partial", "strict"),
        default="partial",
        help="partial records unsupported selected slots as coverage skips; strict fails on them",
    )
    parser.add_argument("--output-root", default=None, help="write artifacts under this root")
    parser.add_argument("--verify", action="store_true", help="build-verify after writing")
    parser.add_argument(
        "--test",
        action="store_true",
        help="build and run generated value tests (implies --verify)",
    )
    parser.add_argument(
        "--fuzz",
        action="store_true",
        help="emit and run differential-fuzz value tests (hardware vs the generic scalar "
        "reference over random inputs); implies --test",
    )
    parser.add_argument(
        "--sde",
        nargs="?",
        const="/opt/intel-sde/sde64",
        default=None,
        help=(
            "run value-test executables for SDE-annotated profiles through Intel SDE; "
            "optionally pass the SDE executable path"
        ),
    )
    parser.add_argument(
        "--qemu-aarch64",
        nargs="?",
        const="/usr/bin/qemu-aarch64",
        default=None,
        help=(
            "run value-test executables for qemu-aarch64-annotated profiles "
            "through QEMU user-mode; optionally pass the executable path"
        ),
    )
    parser.add_argument(
        "--wasmtime",
        nargs="?",
        const="wasmtime",
        default=None,
        help=(
            "run value-test executables for Wasm/WASI profiles through Wasmtime; "
            "optionally pass the executable path"
        ),
    )
    parser.add_argument(
        "--cpp-compiler",
        default=None,
        help="C++ compiler command for build verification, e.g. /usr/bin/c++",
    )
    parser.add_argument(
        "--cpp-target",
        default=None,
        help="optional C++ target triple override for build verification",
    )
    parser.add_argument(
        "--rust-compiler",
        default=None,
        help="Rust compiler executable for build verification, e.g. rustc",
    )
    parser.add_argument(
        "--rust-target",
        default=None,
        help="optional Rust target triple override for build verification",
    )
    parser.add_argument(
        "--rust-linker",
        default=None,
        help="optional Rust target linker override for build verification",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="print a behavior-coverage report"
    )
    parser.add_argument(
        "--value-test-warnings",
        action="store_true",
        help="warn when authored value-test cases cannot be planned for a backend/profile",
    )
    parser.add_argument(
        "--format",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="run clang-format/rustfmt over the written artifacts (best-effort; "
        "skipped if the formatter is unavailable). Use --no-format to disable.",
    )
    args = parser.parse_args(argv)

    # Fuzzing only matters once the value tests are built and run, and it needs the test harness
    # (round-trip primitives) pulled into the closure — so --fuzz implies --test.
    if args.fuzz:
        args.test = True

    if args.test and args.output_root is None:
        print(
            "[error] --test requires --output-root so generated artifacts can "
            "be written before value-test verification",
            file=sys.stderr,
        )
        return 1

    generate_kwargs = {
        "machine_profiles_path": args.machine_profiles,
        "type_tags": _split(args.types),
        "backends": _split(args.backends),
        "generation_mode": args.generation_mode,
        "test_harness": args.test,
        "value_test_warnings": args.value_test_warnings or args.test,
        "value_test_fuzz": args.fuzz,
    }
    if args.profiles is not None:
        generate_kwargs["profiles"] = _split(args.profiles)
    if args.primitives is not None:
        generate_kwargs["primitives"] = _split(args.primitives)

    result = generate_project(
        [Path(path) for path in args.sources],
        **generate_kwargs,
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

        if args.format:
            from tslc.output.format import format_generated

            format_report = format_generated(args.output_root, tuple(_split(args.backends)))
            for note in format_report.notes:
                print(f"[format-skip] {note}", file=sys.stderr)
            if format_report.formatted:
                print(f"formatted {', '.join(format_report.formatted)}")

        if (args.verify or args.test) and result.rendered is not None:
            if args.test:
                runners = _configured_runner_labels(
                    args.sde, args.qemu_aarch64, args.wasmtime
                )
                if runners:
                    print(
                        "building and running generated value tests through "
                        + ", ".join(runners)
                    )
                else:
                    print("building and running generated value tests")
            verify_report = verify_project(
                args.output_root,
                result.rendered.verify,
                cpp_compiler=args.cpp_compiler,
                rust_compiler=args.rust_compiler,
                run_value_tests=args.test,
                sde_path=args.sde,
                qemu_aarch64_path=args.qemu_aarch64,
                wasmtime_path=args.wasmtime,
                cpp_target=args.cpp_target,
                rust_target=args.rust_target,
                rust_linker=args.rust_linker,
            )
            for note in verify_report.skipped:
                print(f"[verify-skip] {note}", file=sys.stderr)
            for diagnostic in verify_report.diagnostics:
                print(f"[verify] {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
            if args.test:
                _print_test_output(verify_report)
            if has_errors(verify_report.diagnostics) or (
                args.test and verify_report.diagnostics
            ):
                return 1
            verified = "build/test-verified" if args.test else "build-verified"
            print(f"{verified} {len(verify_report.commands)} commands")

    return 0


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _configured_runner_labels(
    sde: str | None,
    qemu_aarch64: str | None,
    wasmtime: str | None,
) -> list[str]:
    labels: list[str] = []
    if sde:
        labels.append(f"Intel SDE: {sde}")
    if qemu_aarch64:
        labels.append(f"qemu-aarch64: {qemu_aarch64}")
    if wasmtime:
        labels.append(f"Wasmtime: {wasmtime}")
    return labels


def _print_test_output(report: BuildVerificationReport) -> None:
    for result in report.commands:
        if result.command.step != "test":
            continue
        command = result.command
        print(
            f"[test-output] {command.backend_id} {command.profile_name}: "
            f"{shlex.join(command.argv)}"
        )
        _print_captured_stream("stdout", result.stdout)
        _print_captured_stream("stderr", result.stderr)


def _print_captured_stream(label: str, text: str) -> None:
    stripped = text.strip()
    if stripped:
        print(f"[{label}]")
        print(stripped)


if __name__ == "__main__":
    raise SystemExit(main())
