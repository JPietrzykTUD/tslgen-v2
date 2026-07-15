"""Render one concrete specialization with the registered backend renderer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tslc.api import _expand_sources
from tslc.backend.emitted_profile import EmittedProfile
from tslc.backend.registry import backend_capability, registered_backend_ids
from tslc.diagnostics import Diagnostic, format_diagnostic, has_errors
from tslc.lower.lowerer import LoweredSpecialization
from tslc.pipeline import GenerationRequest, SkippedEntry, _generate_loaded, _load_inputs


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return candidate
    return start


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_DEFAULT_SOURCES = _REPO_ROOT / "tsldata"
_DEFAULT_PROFILES = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"


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
    parser.add_argument("--sources", default=str(_DEFAULT_SOURCES))
    parser.add_argument("--machine-profiles", default=str(_DEFAULT_PROFILES))
    args = parser.parse_args(argv)

    rendered, diagnostics = render_preview(
        sources=Path(args.sources),
        machine_profiles=Path(args.machine_profiles),
        primitive=args.primitive,
        profile=args.profile,
        type_tag=args.type_tag,
        backend=args.backend,
        extension=args.extension,
        to_target=args.to_target,
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
) -> tuple[str | None, tuple[Diagnostic, ...]]:
    """Return a rendered backend fragment and all diagnostics for one saved slot."""

    request = GenerationRequest(
        source_paths=_expand_sources((sources,)),
        machine_profiles_path=machine_profiles,
        primitives=(primitive,),
        profiles=(profile,),
        type_tags=(type_tag,),
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
                primitive, profile, type_tag, backend, extension, result.skipped
            ),
        )

    matching = _matching_specializations(
        emitted,
        primitive=primitive,
        type_tag=type_tag,
        backend=backend,
        extension=extension,
        to_target=to_target,
    )
    if not matching:
        return None, (
            *result.diagnostics,
            _not_emitted_diagnostic(
                primitive, profile, type_tag, backend, extension, result.skipped
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


def _not_emitted_diagnostic(
    primitive: str,
    profile: str,
    type_tag: str,
    backend: str,
    extension: str | None,
    skipped: tuple[SkippedEntry, ...],
) -> Diagnostic:
    reasons = sorted(
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
    suffix = f" Reasons: {'; '.join(reasons)}" if reasons else ""
    return Diagnostic(
        severity="error",
        code="TSL-PREVIEW-NOT-EMITTED",
        message=(
            f"no rendered specialization for primitive {primitive!r}, profile "
            f"{profile!r}, type {type_tag!r}, backend {backend!r}, extension "
            f"{extension or '*'}{suffix}"
        ),
    )


__all__ = ("render_preview",)
