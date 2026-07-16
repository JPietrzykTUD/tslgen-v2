#!/usr/bin/env python3
"""Dump one pipeline stage's output as pretty text or JSON — `clang -emit-ast` for tslc.

The pipeline is a chain of pure, immutable values, so any intermediate can be printed without
running the rest. Where ``explain`` tells the *narrative* of one slot across all stages, this dumps
*one stage* broadly, for reading, scripting, or diffing across a refactor:

  --stage catalog     the typed model the builder produced — primitives (signature, attrs, impls),
                      extensions (isa/family/inherits/bits/activation/supersedes),
                      type-groups. "Did my primitive parse the way I think?"
  --stage segments    the scanned TSIL segment tree of a primitive's bodies (RawText vs Region).
                      "Did `loop<…>` get captured, or leak through as raw text?"
  --stage selection   the slots a profile selects (primitive × extension × type [× target]) and the
                      chosen body's source. "What does profile X actually emit for primitive Y?"
  --stage lowered     the resolved ``LoweredSpecialization`` — register/type spellings, intrinsic
                      names in the body, mask policy, required features — before the backend wraps
                      it. "Did `base::signed_of(base::in)` resolve to the right suffix?"

Run from the repository with ``tslc/src`` on ``PYTHONPATH``:

    PYTHONPATH=tslc/src python -m tslc.maintenance.stage_dump --stage segments --primitive add
    PYTHONPATH=tslc/src python -m tslc.maintenance.stage_dump --stage lowered \\
        --profile avx2 --backend cpp --primitive add --type si32 --format json
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import sys
from pathlib import Path

from tslc.api import _ARITH_TYPE_TAGS, _expand_sources
from tslc.backend.registry import create_backend_dialect, registered_backend_ids
from tslc.catalog.machine_profiles import MachineProfile
from tslc.catalog.model import Catalog, Extension, Primitive
from tslc.diagnostics import SourceSpan
from tslc.ir.scan import scan
from tslc.maintenance._segments_view import format_segment_tree, segment_to_json
from tslc.maintenance import _repo_context
from tslc.lower.lowerer import LoweredSpecialization, Lowerer
from tslc.pipeline import GenerationRequest, _load_inputs
from tslc.select.selector import SelectedImplementation, Selector

_STAGES = ("catalog", "segments", "selection", "lowered")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc inspect",
        description="Dump one pipeline stage (catalog/segments/selection/lowered) as text or JSON.",
    )
    parser.add_argument("--stage", required=True, choices=_STAGES)
    parser.add_argument("--primitive", default=None, help="restrict to this primitive name")
    parser.add_argument("--profile", default=None, help="machine profile (selection/lowered)")
    parser.add_argument("--backend", default="cpp", choices=registered_backend_ids())
    parser.add_argument("--type", default=None, dest="type_tag", help="restrict to this type tag")
    parser.add_argument("--extension", default=None, help="restrict to this simd<> extension tag")
    parser.add_argument("--format", default="text", choices=("text", "json"))
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

    if args.stage in ("selection", "lowered") and args.profile is None:
        parser.error(f"--stage {args.stage} requires --profile")
    if args.stage in ("segments", "lowered") and args.primitive is None:
        parser.error(f"--stage {args.stage} requires --primitive (output would be unbounded)")

    sources, machine_profiles = _repo_context.resolve_corpus_paths(
        parser, args.sources, args.machine_profiles
    )
    text, payload, errors = run(
        stage=args.stage,
        sources=sources,
        machine_profiles=machine_profiles,
        primitive=args.primitive,
        profile=args.profile,
        backend=args.backend,
        type_tag=args.type_tag,
        extension=args.extension,
    )
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2) if args.format == "json" else text)
    return 0


def run(
    *,
    stage: str,
    sources: Path,
    machine_profiles: Path,
    primitive: str | None,
    profile: str | None,
    backend: str,
    type_tag: str | None,
    extension: str | None,
) -> tuple[str, object, list[str]]:
    """Return ``(pretty_text, json_payload, errors)`` for the requested stage."""

    request = GenerationRequest(
        source_paths=_expand_sources((sources,)),
        machine_profiles_path=machine_profiles,
        primitives=(primitive,) if primitive is not None else None,
        profiles=(profile,) if profile is not None else None,
        type_tags=(type_tag,) if type_tag is not None else _ARITH_TYPE_TAGS,
        backends=(backend,),
    )
    inputs, diagnostics = _load_inputs(request)
    if inputs is None:
        return "", {}, [f"[{d.severity}] {d.code}: {d.message}" for d in diagnostics]
    catalog = inputs.catalog
    types = (type_tag,) if type_tag is not None else _ARITH_TYPE_TAGS

    if stage == "catalog":
        return _dump_catalog(catalog, primitive)
    if stage == "segments":
        if primitive is None:
            return "", {}, ["segments stage requires a primitive"]
        return _dump_segments(catalog, primitive, extension)

    if profile is None:
        return "", {}, [f"{stage} stage requires a machine profile"]
    machine_profile = inputs.machine_profiles.get(profile)
    if machine_profile is None:
        known = ", ".join(sorted(inputs.machine_profiles)) or "(none)"
        return "", {}, [f"no machine profile named {profile!r}. Known: {known}"]
    primitive_names = (
        [primitive]
        if primitive is not None
        else sorted({p.name for p in catalog.primitives})
    )
    if stage == "selection":
        return _dump_selection(
            catalog,
            machine_profile,
            backend,
            primitive_names,
            types,
            extension,
        )
    return _dump_lowered(
        catalog, machine_profile, backend, primitive_names, types, extension
    )


# --------------------------------------------------------------------------- catalog


def _dump_catalog(catalog: Catalog, primitive: str | None) -> tuple[str, object, list[str]]:
    primitives = [
        p for p in catalog.primitives if primitive is None or p.name == primitive
    ]
    if primitive is not None and not primitives:
        return "", {}, [f"no primitive named {primitive!r}"]
    lines: list[str] = []
    prim_json: list[dict] = []
    for prim in sorted(primitives, key=lambda p: (p.name, p.signature)):
        attrs = ", ".join(f"{k}={v}" for k, v in sorted(prim.attributes.items())) or "-"
        lines.append(
            f"primitive {prim.name}  sig={prim.signature}  "
            f"params=({', '.join(prim.parameters)})  attrs={{{attrs}}}  "
            f"impls={len(prim.implementations)}  tests={len(prim.tests)}"
        )
        if prim.result_target is not None:
            lines.append(f"    result_target: {prim.result_target}")
        for impl in prim.implementations:
            lines.append(
                f"    [{impl.extension} / {impl.type_group}"
                + (f" -> {impl.to_target_group}" if impl.to_target_group else "")
                + f"]  src={_src(impl.selector_source or impl.source)}"
            )
        prim_json.append(_primitive_json(prim))

    if primitive is None:
        lines.append("")
        lines.append("extensions:")
        for ext in sorted(catalog.extensions.values(), key=lambda e: e.name):
            lines.append("    " + _extension_line(ext))
        lines.append("")
        lines.append("type-groups:")
        for name in sorted(catalog.type_groups):
            members = ", ".join(catalog.type_groups[name])
            lines.append(f"    {name}: {members}")

    payload = {
        "stage": "catalog",
        "primitives": prim_json,
        "extensions": [_extension_json(e) for e in sorted(catalog.extensions.values(), key=lambda e: e.name)]
        if primitive is None
        else [],
        "type_groups": {k: list(catalog.type_groups[k]) for k in sorted(catalog.type_groups)}
        if primitive is None
        else {},
    }
    return "\n".join(lines), payload, []


def _primitive_json(prim: Primitive) -> dict:
    return {
        "name": prim.name,
        "signature": prim.signature,
        "parameters": list(prim.parameters),
        "attributes": dict(prim.attributes),
        "result_target": list(prim.result_target) if prim.result_target else None,
        "tests": len(prim.tests),
        "implementations": [
            {
                "extension": impl.extension,
                "type_group": impl.type_group,
                "to_target_group": impl.to_target_group,
                "selector_path": list(impl.selector_path),
                "source": _src(impl.selector_source or impl.source),
            }
            for impl in prim.implementations
        ],
    }


def _extension_line(ext: Extension) -> str:
    activation = ", ".join(sorted(ext.active_when.target_features))
    compile_modes = ", ".join(sorted(ext.active_when.compile_modes))
    supersedes = ", ".join(sorted(ext.supersedes))
    return (
        f"extension {ext.name}  isa={ext.isa_name}  family={ext.family}  "
        f"inherits={ext.inherits or '-'}  vector_bits={ext.vector_bits}  "
        f"active_when=[{activation}]  compile_modes=[{compile_modes}]  "
        f"supersedes=[{supersedes}]"
    )


def _extension_json(ext: Extension) -> dict:
    return {
        "name": ext.name,
        "isa": ext.isa_name,
        "family": ext.family,
        "inherits": ext.inherits,
        "vector_bits": ext.vector_bits,
        "active_when": {
            "target_features": sorted(ext.active_when.target_features),
            "compile_modes": sorted(ext.active_when.compile_modes),
        },
        "supersedes": sorted(ext.supersedes),
    }


# --------------------------------------------------------------------------- segments


def _dump_segments(
    catalog: Catalog, primitive: str, extension: str | None
) -> tuple[str, object, list[str]]:
    variants = catalog.primitives_named(primitive, unmasked=False)
    if not variants:
        return "", {}, [f"no primitive named {primitive!r}"]
    lines: list[str] = []
    variants_json: list[dict] = []
    for prim in variants:
        attrs = ", ".join(f"{k}={v}" for k, v in sorted(prim.attributes.items())) or "-"
        impls = [
            impl
            for impl in prim.implementations
            if extension is None or impl.extension == extension
        ]
        if not impls:
            continue
        lines.append(f"# {prim.name}  sig={prim.signature}  attrs={{{attrs}}}")
        impls_json: list[dict] = []
        for impl in impls:
            segments = scan(impl.body_text, source=impl.body_source)
            target = f" -> {impl.to_target_group}" if impl.to_target_group else ""
            lines.append(f"  [{impl.extension} / {impl.type_group}{target}]  src={_src(impl.body_source)}")
            lines.extend("    " + line for line in format_segment_tree(segments, indent=0))
            impls_json.append(
                {
                    "extension": impl.extension,
                    "type_group": impl.type_group,
                    "to_target_group": impl.to_target_group,
                    "source": _src(impl.body_source),
                    "tree": [segment_to_json(s) for s in segments],
                }
            )
        variants_json.append(
            {"signature": prim.signature, "attributes": dict(prim.attributes), "implementations": impls_json}
        )
    if not lines:
        return "", {}, [
            f"no implementations for {primitive!r}"
            + (f" on extension {extension!r}" if extension else "")
        ]
    return "\n".join(lines), {"stage": "segments", "primitive": primitive, "variants": variants_json}, []


# --------------------------------------------------------------------------- selection


def _dump_selection(
    catalog: Catalog,
    machine_profile: MachineProfile,
    backend: str,
    primitive_names: Sequence[str],
    types: tuple[str, ...],
    extension: str | None,
) -> tuple[str, object, list[str]]:
    selector = Selector()
    lines: list[str] = [f"# selection for profile {machine_profile.name}"]
    slots_json: list[dict] = []
    for name in primitive_names:
        selection = selector.select_profile(
            catalog,
            machine_profile,
            name,
            types,
            backend_id=backend,
        )
        for slot in selection.selected:
            if extension is not None and slot.extension.isa_name != extension:
                continue
            lines.append("  " + _selection_line(slot))
            slots_json.append(_selection_json(slot))
    return "\n".join(lines), {"stage": "selection", "profile": machine_profile.name, "slots": slots_json}, []


def _selection_line(slot: SelectedImplementation) -> str:
    impl = slot.implementation
    attrs = "".join(f" [{k}={v}]" for k, v in sorted(slot.primitive.attributes.items()))
    target = f" -> {slot.to_target}" if slot.to_target is not None else ""
    return (
        f"{slot.primitive.name}<{slot.extension.isa_name}, {slot.type_tag}{target}>{attrs}  "
        f"body=[{impl.extension} / {impl.type_group}]  "
        f"requires=[{', '.join(sorted(slot.required_features))}]  src={_src(impl.selector_source or impl.source)}"
    )


def _selection_json(slot: SelectedImplementation) -> dict:
    impl = slot.implementation
    return {
        "primitive": slot.primitive.name,
        "extension": slot.extension.isa_name,
        "type": slot.type_tag,
        "to_target": slot.to_target,
        "attributes": dict(slot.primitive.attributes),
        "body": {"extension": impl.extension, "type_group": impl.type_group},
        "required_features": sorted(slot.required_features),
        "source": _src(impl.selector_source or impl.source),
    }


# --------------------------------------------------------------------------- lowered


def _dump_lowered(
    catalog: Catalog,
    machine_profile: MachineProfile,
    backend: str,
    primitive_names: Sequence[str],
    types: tuple[str, ...],
    extension: str | None,
) -> tuple[str, object, list[str]]:
    selector = Selector()
    lowerer = Lowerer()
    dialect = create_backend_dialect(catalog, backend)
    lines: list[str] = [f"# lowered for {machine_profile.name} / {backend}"]
    specs_json: list[dict] = []
    for name in primitive_names:
        selection = selector.select_profile(
            catalog,
            machine_profile,
            name,
            types,
            backend_id=backend,
        )
        for slot in selection.selected:
            if extension is not None and slot.extension.isa_name != extension:
                continue
            segments = scan(slot.implementation.body_text, source=slot.implementation.body_source)
            lowered = lowerer.lower(slot, catalog, dialect, body_segments=segments)
            header = _slot_header(slot)
            if lowered.specialization is None:
                reason = next((d.message for d in lowered.diagnostics), "unsupported body")
                lines.append(f"  {header}: NOT lowered — {reason}")
                specs_json.append({"slot": header, "lowered": False, "reason": reason})
                continue
            lines.extend(_lowered_text(header, lowered.specialization))
            specs_json.append({"slot": header, "lowered": True, **_lowered_json(lowered.specialization)})
    return "\n".join(lines), {"stage": "lowered", "profile": machine_profile.name, "backend": backend, "specializations": specs_json}, []


def _slot_header(slot: SelectedImplementation) -> str:
    attrs = "".join(f" [{k}={v}]" for k, v in sorted(slot.primitive.attributes.items()))
    target = f" -> {slot.to_target}" if slot.to_target is not None else ""
    return f"{slot.primitive.name}<{slot.extension.isa_name}, {slot.type_tag}{target}>{attrs}"


def _lowered_text(header: str, spec: LoweredSpecialization) -> list[str]:
    lines = [f"  {header}:"]
    lines.append(f"      register={spec.register_spelling}  base={spec.base_type_spelling}")
    lines.append(f"      result={spec.result_kind}  params=({', '.join(spec.param_kinds)})")
    if spec.mask_policy is not None:
        lines.append(f"      mask_policy={spec.mask_policy}")
    if spec.immediate is not None:
        lines.append(f"      immediate={spec.immediate}")
    if spec.required_features:
        lines.append(f"      requires=[{', '.join(sorted(spec.required_features))}]")
    if spec.safety.internal_unsafe or spec.safety.caller_unsafe:
        lines.append(
            f"      safety=internal:{spec.safety.internal_unsafe} caller:{spec.safety.caller_unsafe}"
        )
    body = spec.body_text.strip()
    lines.append("      body:")
    lines.extend(f"        {line}" for line in (body.splitlines() or [""]))
    return lines


def _lowered_json(spec: LoweredSpecialization) -> dict:
    return {
        "register": spec.register_spelling,
        "base_type": spec.base_type_spelling,
        "result_kind": spec.result_kind,
        "param_kinds": list(spec.param_kinds),
        "mask_policy": spec.mask_policy,
        "immediate": list(spec.immediate) if spec.immediate else None,
        "required_features": sorted(spec.required_features),
        "internal_unsafe": spec.safety.internal_unsafe,
        "caller_unsafe": spec.safety.caller_unsafe,
        "body": spec.body_text.strip(),
    }


def _src(source: SourceSpan | None) -> str:
    return f"{source.path}:{source.line}" if source is not None else "-"


if __name__ == "__main__":
    raise SystemExit(main())
