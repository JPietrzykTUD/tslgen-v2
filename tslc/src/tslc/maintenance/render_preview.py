"""Render one concrete specialization with the registered backend renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tslc.api import _expand_sources
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capability, registered_backend_ids
from tslc.diagnostics import (
    Diagnostic,
    SourceLocation,
    SourceSpan,
    format_diagnostic,
    has_errors,
)
from tslc.lower.lowerer import LoweredSpecialization
from tslc.maintenance import _repo_context
from tslc.pipeline import GenerationRequest, SkippedEntry, _generate_loaded, _load_inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc preview",
        description=(
            "Render one primitive/profile/backend/extension/type specialization "
            "fragment without writing a generated project."
        ),
    )
    parser.add_argument("--primitive", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--type", required=True, dest="type_tag")
    parser.add_argument(
        "--backend", default="cpp", choices=registered_backend_ids()
    )
    parser.add_argument("--extension", default=None)
    parser.add_argument("--to-target", default=None)
    parser.add_argument(
        "--implementation-file",
        default=None,
        help="restrict output to the implementation selector at this source point",
    )
    parser.add_argument("--implementation-line", type=_positive_int, default=None)
    parser.add_argument("--implementation-column", type=_positive_int, default=None)
    parser.add_argument(
        "--sources",
        default=None,
        help="corpus root (default: the checkout's tsldata/)",
    )
    parser.add_argument(
        "--machine-profiles",
        default=None,
        help="machine profile catalog (default: the checkout's "
        "supplementary/buildsystem/machine_profiles.json)",
    )
    args = parser.parse_args(argv)
    implementation_source = _implementation_source(parser, args)

    sources, machine_profiles = _repo_context.resolve_corpus_paths(
        parser, args.sources, args.machine_profiles
    )
    rendered, diagnostics = render_preview(
        sources=sources,
        machine_profiles=machine_profiles,
        primitive=args.primitive,
        profile=args.profile,
        type_tag=args.type_tag,
        backend=args.backend,
        extension=args.extension,
        to_target=args.to_target,
        implementation_source=implementation_source,
    )
    for diagnostic in diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if rendered is None:
        return 1
    print(rendered)
    return 0


def render_preview(
    *,
    sources: Path,
    machine_profiles: Path,
    primitive: str,
    profile: str,
    type_tag: str,
    backend: str,
    extension: str | None = None,
    to_target: str | None = None,
    implementation_source: SourceLocation | None = None,
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    """Return a rendered backend fragment and all diagnostics for one saved slot."""

    request = GenerationRequest(
        source_paths=_expand_sources((sources,)),
        machine_profiles_path=machine_profiles,
        primitives=(primitive,),
        profiles=(profile,),
        type_tags=(type_tag,),
        extensions=(extension,) if extension is not None else None,
        backends=(backend,),
        render_artifacts=False,
    )
    inputs, load_diagnostics = _load_inputs(request)
    if inputs is None:
        return None, tuple(load_diagnostics)
    result = _generate_loaded(request, inputs, load_diagnostics)
    if has_errors(result.diagnostics):
        return None, result.diagnostics

    emitted = next(
        (item for item in result.emitted_profiles if item.profile.name == profile),
        None,
    )
    if emitted is None:
        return None, (
            *result.diagnostics,
            _not_emitted_diagnostic(
                primitive,
                profile,
                type_tag,
                backend,
                extension,
                result.skipped,
                implementation_source,
            ),
        )

    matching = _matching_specializations(
        emitted,
        primitive=primitive,
        type_tag=type_tag,
        backend=backend,
        extension=extension,
        to_target=to_target,
        implementation_source=implementation_source,
    )
    if not matching:
        return None, (
            *result.diagnostics,
            _not_emitted_diagnostic(
                primitive,
                profile,
                type_tag,
                backend,
                extension,
                result.skipped,
                implementation_source,
            ),
        )

    capability = backend_capability(backend)
    parts: list[str] = []
    try:
        for emitted_name, specializations in matching:
            parts.append(
                capability.render_primitive_preview(
                    emitted, emitted_name, specializations
                ).rstrip()
            )
    except ValueError as exc:
        return None, (
            *result.diagnostics,
            Diagnostic(
                severity="error",
                code="TSL-PREVIEW-UNSUPPORTED-BACKEND",
                message=str(exc),
            ),
        )

    selection = (
        f"primitive={primitive} profile={profile} type={type_tag} backend={backend} "
        f"extension={extension or '*'} to_target={to_target or '*'}"
    )
    if implementation_source is not None:
        selection += (
            " implementation="
            f"{implementation_source.path}:{implementation_source.line}:"
            f"{implementation_source.column}"
        )
    header = (
        "// tslc rendered specialization preview\n"
        f"// input snapshot: sha256:{inputs.input_digest}\n"
        f"// selection: {selection}\n"
        "// This fragment uses the normal backend primitive renderer; no project "
        "was written or built."
    )
    body = "\n\n".join(parts)
    return f"{header}\n\n{body}\n", result.diagnostics


def _matching_specializations(
    emitted: EmittedProfile,
    *,
    primitive: str,
    type_tag: str,
    backend: str,
    extension: str | None,
    to_target: str | None,
    implementation_source: SourceLocation | None,
) -> tuple[tuple[str, tuple[LoweredSpecialization, ...]], ...]:
    matching: list[tuple[str, tuple[LoweredSpecialization, ...]]] = []
    for emitted_name, specializations in sorted(
        emitted.specializations(backend).items()
    ):
        selected = tuple(
            spec
            for spec in specializations
            if (
                spec.source_primitive_name == primitive
                or spec.primitive_name == primitive
            )
            and spec.type_tag == type_tag
            and (extension is None or spec.extension_name == extension)
            and _matches_target(spec, to_target)
            and _matches_implementation_source(spec.source, implementation_source)
        )
        if selected:
            matching.append((emitted_name, selected))
    return tuple(matching)


def _matches_target(spec: LoweredSpecialization, to_target: str | None) -> bool:
    if to_target is None:
        return True
    return spec.target is not None and to_target in {
        spec.target.base_tag,
        spec.target.extension_isa,
    }


def _matches_implementation_source(
    span: SourceSpan | None,
    location: SourceLocation | None,
) -> bool:
    if location is None:
        return True
    if span is None or span.path.resolve() != location.path.resolve():
        return False
    return (span.line, span.column) == (location.line, location.column)


def _implementation_source(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> SourceLocation | None:
    values = (
        args.implementation_file,
        args.implementation_line,
        args.implementation_column,
    )
    if not any(value is not None for value in values):
        return None
    if not all(value is not None for value in values):
        parser.error(
            "--implementation-file, --implementation-line, and "
            "--implementation-column must be provided together"
        )
    return SourceLocation(
        Path(args.implementation_file).resolve(),
        args.implementation_line,
        args.implementation_column,
    )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _not_emitted_diagnostic(
    primitive: str,
    profile: str,
    type_tag: str,
    backend: str,
    extension: str | None,
    skipped: tuple[SkippedEntry, ...],
    implementation_source: SourceLocation | None,
) -> Diagnostic:
    reasons = (
        []
        if implementation_source is not None
        else sorted(
            {
                item.reason
                for item in skipped
                if item.primitive == primitive
                and item.profile == profile
                and item.type_tag == type_tag
                and item.backend == backend
                and (extension is None or item.extension == extension)
            }
        )
    )
    suffix = f" Reasons: {'; '.join(reasons)}" if reasons else ""
    source = (
        ""
        if implementation_source is None
        else (
            ", implementation "
            f"{implementation_source.path}:{implementation_source.line}:"
            f"{implementation_source.column}"
        )
    )
    return Diagnostic(
        severity="error",
        code="TSL-PREVIEW-NOT-EMITTED",
        message=(
            f"no rendered specialization for primitive {primitive!r}, profile "
            f"{profile!r}, type {type_tag!r}, backend {backend!r}, extension "
            f"{extension or '*'}{source}{suffix}"
        ),
    )


__all__ = ("render_preview",)
