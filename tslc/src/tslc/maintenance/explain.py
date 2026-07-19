#!/usr/bin/env python3
"""Explain why one ``(primitive, profile, backend, extension, type)`` slot compiles or not.

This is a diagnostic tool, not part of the compiler pipeline. It re-drives the same pure
stages the pipeline uses — selection, body scan, lowering, dependency closure — for a *single*
slot and narrates each decision, so the daily "why doesn't ``X<neon, si64>`` compile yet?"
question has a precise, sourced answer instead of one collapsed skip string.

It prints four sections:

  1. SELECTION   which implementation body won the slot, the ranked candidate field with the
                 four principled keys, the decisive tiebreak over the runner-up, and — when no
                 body is usable — why each on-chain candidate was rejected (or why the extension
                 is not emitted for the profile at all).
  2. BODY        the scanned TSIL segment tree (RawText vs Region keyword islands).
  3. LOWERING    the resolved ``LoweredSpecialization`` summary, or the skip/unsupported
                 diagnostics (with source spans) that stopped it.
  4. DEPENDENCIES the ``call<…>`` callees, and the authoritative pipeline verdict (emitted /
                 skipped / pruned) — with the missing callee surfaced for a pruned slot.

Run from anywhere in the repo (paths default to the repo's ``tsldata`` and machine profiles):

    PYTHONPATH=tslc/src python -m tslc.maintenance.explain \\
        --primitive add --profile avx2 --type si32 --backend cpp

    PYTHONPATH=tslc/src python -m tslc.maintenance.explain \\
        --primitive add --profile skylake --type f64 --backend rust --extension avx512
"""

from __future__ import annotations

import argparse
from collections.abc import Collection, Sequence
from pathlib import Path

from tslc.api import _expand_sources
from tslc.backend.registry import create_backend_dialect, registered_backend_ids
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog
from tslc.diagnostics import Diagnostic, SourceLocation, SourceSpan
from tslc.ir.scan import scan
from tslc.maintenance import _repo_context
from tslc.maintenance._segments_view import format_segment_tree
from tslc.lower.dependencies import CallDependency
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.pipeline import (
    GenerationRequest,
    GenerationResult,
    _generate_loaded,
    _load_inputs,
)
from tslc.select.selector import (
    CandidateEvaluation,
    RANKING_KEYS,
    RankedCandidate,
    SelectedImplementation,
    Selector,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc explain",
        description="Explain why one primitive/profile/backend/extension/type slot compiles.",
    )
    parser.add_argument("--primitive", required=True, help="primitive name, e.g. add")
    parser.add_argument("--profile", required=True, help="machine profile name, e.g. avx2")
    parser.add_argument("--type", required=True, dest="type_tag", help="scalar type tag, e.g. si32")
    parser.add_argument("--backend", default="cpp", choices=registered_backend_ids())
    parser.add_argument(
        "--extension",
        default=None,
        help="restrict to one simd<> extension tag (e.g. avx2); omit to explain every "
        "extension the profile selects for this primitive/type",
    )
    parser.add_argument(
        "--to-target",
        default=None,
        help="for a representation-change primitive, the concrete target type/extension",
    )
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

    sources, machine_profiles = _repo_context.resolve_corpus_paths(
        parser, args.sources, args.machine_profiles
    )
    report = explain(
        sources=sources,
        machine_profiles=machine_profiles,
        primitive=args.primitive,
        profile=args.profile,
        type_tag=args.type_tag,
        backend=args.backend,
        extension=args.extension,
        to_target=args.to_target,
    )
    print(report)
    return 0


def explain(
    *,
    sources: Path,
    machine_profiles: Path,
    primitive: str,
    profile: str,
    type_tag: str,
    backend: str,
    extension: str | None = None,
    to_target: str | None = None,
) -> str:
    """Return the human-readable explanation for the requested slot (the testable core)."""

    request = GenerationRequest(
        source_paths=_expand_sources((sources,)),
        machine_profiles_path=machine_profiles,
        primitives=(primitive,),
        profiles=(profile,),
        type_tags=(type_tag,),
        backends=(backend,),
        render_artifacts=False,
    )
    inputs, diagnostics = _load_inputs(request)
    if inputs is None:
        return _format_load_failure(diagnostics)

    catalog = inputs.catalog
    machine_profile = inputs.machine_profiles.get(profile)
    if machine_profile is None:
        known = ", ".join(sorted(inputs.machine_profiles)) or "(none loaded)"
        return f"no machine profile named {profile!r}. Known profiles: {known}"

    out = _Writer()
    out.line(
        f"# explain  {primitive}<{extension or '*'}, {type_tag}>  "
        f"profile={profile}  backend={backend}"
    )
    out.line(f"  input snapshot: sha256:{inputs.input_digest}")
    out.line(
        "  selection: "
        f"primitive={primitive} profile={profile} type={type_tag} backend={backend} "
        f"extension={extension or '*'} to_target={to_target or '*'}"
    )
    out.line(f"  profile target features: {_format_flags(machine_profile.features)}")
    if machine_profile.compile_modes:
        out.line(f"  profile compile modes: {_format_flags(machine_profile.compile_modes)}")
    out.blank()

    selector = Selector()
    selection = selector.select_profile(
        catalog,
        machine_profile,
        primitive,
        (type_tag,),
        backend_id=backend,
    )
    for warning in selection.diagnostics:
        out.line(f"  selection note [{warning.code}]: {warning.message}")
    if selection.diagnostics:
        out.blank()

    # The extensions actually emitted for this profile (and the requested filter, if any).
    emitted_extensions = list(
        selector.emitted_extensions(catalog, machine_profile, backend_id=backend)
    )
    selected_slots = [
        slot
        for slot in selection.selected
        if (extension is None or slot.extension.isa_name == extension)
        and (to_target is None or slot.to_target == to_target)
    ]

    # Authoritative outcome from the real pipeline (its dependency closure + prune fixpoint).
    pipeline_result = _generate_loaded(request, inputs, diagnostics)
    verdicts = _PipelineVerdicts.from_result(pipeline_result, primitive, backend)

    if selected_slots:
        for slot in selected_slots:
            _explain_selected_slot(
                out, selector, catalog, machine_profile, backend, slot, verdicts
            )
    else:
        _explain_no_slot(
            out,
            selector,
            catalog,
            machine_profile,
            primitive,
            type_tag,
            to_target,
            extension,
            emitted_extensions,
        )

    return out.text()


# --------------------------------------------------------------------------- selected slot


def _explain_selected_slot(
    out: "_Writer",
    selector: Selector,
    catalog: Catalog,
    machine_profile: MachineProfile,
    backend: str,
    slot: SelectedImplementation,
    verdicts: "_PipelineVerdicts",
) -> None:
    extension_tag = slot.extension.isa_name
    target_suffix = f" -> {slot.to_target}" if slot.to_target is not None else ""
    attrs = "".join(f" [{key}={value}]" for key, value in sorted(slot.primitive.attributes.items()))
    out.rule(
        f"{slot.primitive.name}<{extension_tag}, {slot.type_tag}{target_suffix}>{attrs}"
    )

    # 1. SELECTION ----------------------------------------------------------------
    out.line("[1] SELECTION")
    evaluation = selector.evaluate_candidates(
        catalog,
        machine_profile,
        slot.primitive,
        extension_tag,
        slot.type_tag,
        slot.to_target,
    )
    _print_ranking(out, evaluation)
    out.blank()

    # 2. BODY ---------------------------------------------------------------------
    impl = slot.implementation
    segments = scan(impl.body_text, source=impl.body_source)
    out.line("[2] BODY  (TSIL segment tree)")
    out.line(f"    selector path: {' / '.join(impl.selector_path)}")
    out.line(f"    {_format_source(impl.body_source)}")
    for line in format_segment_tree(segments, indent=2):
        out.line(line)
    out.blank()

    # 3. LOWERING -----------------------------------------------------------------
    out.line(f"[3] LOWERING  (backend={backend})")
    dialect = create_backend_dialect(catalog, backend)
    lowered = Lowerer().lower(slot, catalog, dialect, body_segments=segments)
    if lowered.specialization is not None:
        _print_specialization(out, lowered.specialization)
    else:
        out.line("    not lowered — body unsupported in this slice:")
        for diagnostic in lowered.diagnostics:
            out.line(
                f"      [{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}"
            )
            if diagnostic.location is not None:
                out.line(f"        at {_format_location(diagnostic.location)}")
    for diagnostic in lowered.diagnostics:
        if diagnostic.severity == "info" and lowered.specialization is not None:
            out.line(f"    coverage note [{diagnostic.code}]: {diagnostic.message}")
    out.blank()

    # 4. DEPENDENCIES & PRUNING ---------------------------------------------------
    out.line("[4] DEPENDENCIES & VERDICT")
    callees = frozenset(
        origin.dependency
        for origin in (
            lowered.specialization.call_dependency_origins
            if lowered.specialization is not None
            else ()
        )
    )
    _print_dependencies(out, callees, verdicts)
    out.blank()
    _print_verdict(out, verdicts, extension_tag, slot.type_tag)


def _print_ranking(out: "_Writer", evaluation: CandidateEvaluation) -> None:
    ranked = evaluation.ranked
    if not ranked:
        out.line("    no usable body — every on-chain candidate was rejected:")
        _print_rejections(out, evaluation)
        return
    out.line(
        "    ranked candidates "
        "(winner first; keys = distance, specificity, target_features, order):"
    )
    for index, candidate in enumerate(ranked):
        marker = "==>" if index == 0 else "   "
        impl = candidate.implementation
        out.line(
            f"    {marker} #{index} {impl.extension}:{impl.type_group}  "
            f"keys=(dist={candidate.distance}, spec={candidate.specificity}, "
            f"target_features={candidate.flag_count}, order={candidate.source_order})  "
            f"requires={_format_flags(candidate.required_features)}"
        )
        out.line(f"          {_format_source(impl.selector_source or impl.source)}")
    if len(ranked) >= 2:
        out.line(f"    tiebreak: {_decisive_tiebreak(ranked[0], ranked[1])}")
    else:
        out.line("    tiebreak: only one usable body — chosen unconditionally")
    if evaluation.rejected:
        out.line("    rejected on-chain candidates:")
        _print_rejections(out, evaluation)


def _decisive_tiebreak(
    winner: RankedCandidate,
    runner_up: RankedCandidate,
) -> str:
    """Name the first ranking key on which the winner beats the runner-up."""

    for attribute, description in RANKING_KEYS:
        win = getattr(winner, attribute)
        lose = getattr(runner_up, attribute)
        if win != lose:
            better = "more" if attribute == "flag_count" else "lower"
            return (
                f"won on {attribute} ({description}): "
                f"winner {win} {'>' if attribute == 'flag_count' else '<'} {lose} "
                f"[{better} wins]"
            )
    return "winner and runner-up tie on every key (selection is arbitrary)"


def _print_rejections(out: "_Writer", evaluation: CandidateEvaluation) -> None:
    for rejection in evaluation.rejected:
        impl = rejection.implementation
        out.line(f"      - {impl.extension}:{impl.type_group}: {rejection.reason}")


# --------------------------------------------------------------------------- no slot


def _explain_no_slot(
    out: "_Writer",
    selector: Selector,
    catalog: Catalog,
    machine_profile: MachineProfile,
    primitive: str,
    type_tag: str,
    to_target: str | None,
    requested_extension: str | None,
    emitted_extensions: list[str],
) -> None:
    out.rule(f"{primitive}<{requested_extension or '*'}, {type_tag}> — NOT selected")
    out.line("[1] SELECTION")

    primitive_obj = catalog.primitive(primitive, unmasked=False) or catalog.primitive(primitive)
    if primitive_obj is None:
        out.line(f"    no primitive named {primitive!r} in the catalog")
        return

    target_extensions = (
        [requested_extension] if requested_extension is not None else emitted_extensions
    )
    out.line(f"    profile emits extensions: {', '.join(emitted_extensions) or '(none)'}")
    out.blank()

    for extension_tag in target_extensions:
        if extension_tag not in emitted_extensions:
            out.line(
                f"    {extension_tag!r}: not emitted for this profile "
                f"(unsupported in this slice, wrong ISA family, superseded by a derived "
                f"extension, or an inactive derived extension)."
            )
            continue
        if extension_tag not in catalog.extensions:
            out.line(f"    {extension_tag!r}: unknown extension")
            continue
        evaluation = selector.evaluate_candidates(
            catalog, machine_profile, primitive_obj, extension_tag, type_tag, to_target
        )
        out.line(f"    {extension_tag}: no body selected. Candidate rejections:")
        if evaluation.rejected:
            _print_rejections(out, evaluation)
        else:
            out.line(
                f"      - the primitive declares no implementation on the {extension_tag!r} "
                f"chain at all"
            )


# --------------------------------------------------------------------------- formatting


def _print_specialization(out: "_Writer", spec: LoweredSpecialization) -> None:
    out.line("    lowered OK:")
    out.line(f"      register   : {spec.register_spelling}")
    out.line(f"      base type  : {spec.base_type_spelling}")
    out.line(f"      result kind: {spec.result_kind}   params: {', '.join(spec.param_kinds) or '(none)'}")
    if spec.mask_policy is not None:
        out.line(f"      mask policy: {spec.mask_policy}")
    if spec.target is not None:
        out.line(f"      target vec : {spec.target}")
    if spec.required_features:
        out.line(f"      requires   : {_format_flags(spec.required_features)}")
    safety = spec.safety
    if safety.internal_unsafe or safety.caller_unsafe:
        out.line(
            f"      safety     : internal_unsafe={safety.internal_unsafe} "
            f"caller_unsafe={safety.caller_unsafe} reasons={_format_flags(safety.reasons)}"
        )
    body_text = spec.body_text.strip()
    out.line("      body:")
    for body_line in body_text.splitlines() or [""]:
        out.line(f"        {body_line}")


def _print_dependencies(
    out: "_Writer", callees: frozenset[CallDependency], verdicts: "_PipelineVerdicts"
) -> None:
    if not callees:
        out.line("    no call<…> callees (leaf primitive)")
        return
    out.line("    call<…> callees (✓ = emitted for this profile in the closure):")
    for dependency in sorted(
        callees, key=lambda d: (d.primitive, d.source.base_tag, d.source.extension_isa)
    ):
        emitted = verdicts.is_emitted(
            dependency.primitive, dependency.source.extension_isa, dependency.source.base_tag
        )
        mark = "✓" if emitted else "✗"
        policy = f" [{dependency.mask_policy}]" if dependency.mask_policy else ""
        target = (
            f" -> {dependency.target.base_tag}<{dependency.target.extension_isa}>"
            if dependency.target is not None
            else ""
        )
        out.line(
            f"      {mark} {dependency.primitive}{policy} "
            f"<{dependency.source.extension_isa}, {dependency.source.base_tag}>{target}"
        )
    missing = verdicts.missing_callees(callees)
    if missing:
        out.line(
            "    missing callees (would dangle this slot at link time -> prune): "
            + ", ".join(missing)
        )


def _print_verdict(
    out: "_Writer", verdicts: "_PipelineVerdicts", extension_tag: str, type_tag: str
) -> None:
    if verdicts.is_emitted(verdicts.primitive, extension_tag, type_tag):
        out.line("    VERDICT: COMPILES — emitted in the generated project for this profile.")
        return
    reason = verdicts.skip_reason(extension_tag, type_tag)
    if reason is not None:
        out.line(f"    VERDICT: SKIPPED — {reason}")
    else:
        out.line(
            "    VERDICT: not present in pipeline coverage or skips for this profile "
            "(it may have been pruned as an unreferenced dependency, or filtered upstream)."
        )


def _format_flags(flags: Collection[str]) -> str:
    items = sorted(flags)
    return f"[{', '.join(items)}]" if items else "[]"


def _format_source(source: SourceSpan | None) -> str:
    if source is None:
        return "(no source span)"
    return f"at {source.path}:{source.line}"


def _format_location(location: SourceLocation) -> str:
    return f"{location.path}:{location.line}:{location.column}"


def _format_load_failure(diagnostics: Sequence[Diagnostic]) -> str:
    lines = ["failed to load inputs:"]
    for diagnostic in diagnostics:
        lines.append(f"  [{diagnostic.severity}] {diagnostic.code}: {diagnostic.message}")
    return "\n".join(lines)


class _PipelineVerdicts:
    """The authoritative emitted/skipped facts for one primitive+backend from a real run."""

    def __init__(
        self,
        primitive: str,
        emitted: set[tuple[str, str, str]],
        skips: dict[tuple[str, str], str],
    ) -> None:
        self.primitive = primitive
        self._emitted = emitted  # (primitive, extension, type_tag)
        self._skips = skips  # (extension, type_tag) -> reason, for this primitive

    @classmethod
    def from_result(
        cls,
        result: GenerationResult,
        primitive: str,
        backend: str,
    ) -> "_PipelineVerdicts":
        emitted = {
            (entry.primitive, entry.extension, entry.type_tag)
            for entry in result.coverage
            if entry.backend == backend
        }
        skips = {
            (entry.extension, entry.type_tag): entry.reason
            for entry in result.skipped
            if entry.backend == backend and entry.primitive == primitive
        }
        return cls(primitive, emitted, skips)

    def is_emitted(self, primitive: str, extension: str, type_tag: str) -> bool:
        return (primitive, extension, type_tag) in self._emitted

    def skip_reason(self, extension: str, type_tag: str) -> str | None:
        return self._skips.get((extension, type_tag))

    def missing_callees(self, callees: frozenset[CallDependency]) -> list[str]:
        missing: list[str] = []
        for dependency in sorted(callees, key=lambda d: d.primitive):
            if not self.is_emitted(
                dependency.primitive,
                dependency.source.extension_isa,
                dependency.source.base_tag,
            ):
                label = f"{dependency.primitive}<{dependency.source.extension_isa}, {dependency.source.base_tag}>"
                if label not in missing:
                    missing.append(label)
        return missing


class _Writer:
    def __init__(self) -> None:
        self._lines: list[str] = []

    def line(self, text: str) -> None:
        self._lines.append(text)

    def blank(self) -> None:
        self._lines.append("")

    def rule(self, label: str) -> None:
        self._lines.append(f"{'─' * 4} {label} {'─' * max(4, 70 - len(label))}")

    def text(self) -> str:
        return "\n".join(self._lines)


if __name__ == "__main__":
    raise SystemExit(main())
