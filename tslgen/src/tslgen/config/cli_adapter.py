from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from tslgen.analysis.selection import SelectionRequest
from tslgen.api import PipelineConfig
from tslgen.config.hardware import HardwareFlagProvider, detect_proc_cpuinfo_flags
from tslgen.config.model import SourceConfig
from tslgen.core.diagnostics import Diagnostic
from tslgen.core.result import Result


def parse_cli_config(
    argv: Sequence[str],
    *,
    hardware_flags_provider: HardwareFlagProvider = detect_proc_cpuinfo_flags,
) -> Result[PipelineConfig]:
    parser = _argument_parser()
    try:
        namespace, unknown = parser.parse_known_args(argv)
    except argparse.ArgumentError as exc:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CLI-ARGUMENTS",
                    f"invalid command line arguments: {exc}",
                ),
            )
        )

    if unknown:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CLI-ARGUMENTS",
                    f"unknown command line argument(s): {' '.join(unknown)}",
                ),
            )
        )

    explicit_flags = tuple(namespace.cpu_flag)
    if namespace.hardware_auto and explicit_flags:
        return Result.failure(
            (
                Diagnostic.error(
                    "TSL-CLI-HARDWARE-CONFLICT",
                    "--hardware-auto cannot be combined with explicit --cpu-flag "
                    "values",
                ),
            )
        )

    cpu_flags = (
        tuple(hardware_flags_provider())
        if namespace.hardware_auto
        else explicit_flags
    )
    config = PipelineConfig(
        source_config=SourceConfig(
            explicit_paths=tuple(Path(path) for path in namespace.source),
            include_standard_library=namespace.include_standard_library,
            standard_library_root=Path(namespace.standard_library_root),
        ),
        selection_request=SelectionRequest(
            backend=namespace.backend,
            primitive_names=tuple(namespace.primitive),
            template_names=tuple(namespace.template),
            extension_names=tuple(namespace.extension),
            cpu_flags=cpu_flags,
            include_support_extensions=not namespace.no_support_extensions,
        ),
        backend_manifest_paths=tuple(Path(path) for path in namespace.manifest),
        render_backend=namespace.render_backend,
    )
    return Result.ok(config)


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tslgen",
        description="Run the redesigned TSL generation pipeline.",
        exit_on_error=False,
    )
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--include-standard-library", action="store_true")
    parser.add_argument("--standard-library-root", default="tsldata")
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--backend", default="cpp")
    parser.add_argument("--render-backend")
    parser.add_argument("--primitive", action="append", default=[])
    parser.add_argument("--template", action="append", default=[])
    parser.add_argument("--extension", action="append", default=[])
    parser.add_argument("--cpu-flag", action="append", default=[])
    parser.add_argument("--hardware-auto", action="store_true")
    parser.add_argument("--no-support-extensions", action="store_true")
    return parser
