"""Catalog-wide validation of authored primitive-call precondition proofs."""

from __future__ import annotations

from collections.abc import Iterable

from tslc.catalog.call_preconditions import (
    CallArgumentBinding,
    CallPreconditionDisposition,
    CallPreconditionDispositionKind,
    CallPreconditionObligationStatus,
    call_precondition_candidates,
    resolve_call_preconditions,
)
from tslc.catalog.model import Catalog, Primitive, PrimitiveMaskMode
from tslc.catalog.preconditions import PreconditionKind
from tslc.diagnostics import Diagnostic, SourceSpan, diagnostic_at, source_subspan
from tslc.ir.region_syntax import (
    call_precondition_syntax_occurrences,
    parse_call_selector,
    segments_text,
    split_arg_groups,
)
from tslc.ir.scan import scan
from tslc.ir.segments import Region, Segment


def validate_call_precondition_dispositions(
    catalog: Catalog,
    diagnostics: list[Diagnostic],
) -> None:
    """Require every source call edge to account for catastrophic conditions."""

    emitted: set[tuple[object, ...]] = set()
    visited_regions: set[tuple[object, str, str]] = set()
    for caller in catalog.primitives:
        for body_text, body_source in _implementation_bodies(caller):
            for region in _regions(scan(body_text, source=body_source)):
                if region.keyword != "call":
                    continue
                key = (region.source, caller.name, caller.signature)
                if key in visited_regions:
                    continue
                visited_regions.add(key)
                _validate_call(catalog, caller, region, diagnostics, emitted)


def _validate_call(
    catalog: Catalog,
    caller: Primitive,
    region: Region,
    diagnostics: list[Diagnostic],
    emitted: set[tuple[object, ...]],
) -> None:
    parsed = parse_call_selector(region.selector_text)
    if parsed is None:
        return
    selector_offset = region.full_text.find(region.selector_text)
    disposition_sources = {
        (item.disposition, item.condition): (
            source_subspan(
                region.source,
                region.full_text,
                selector_offset + item.start,
                selector_offset + item.end,
            )
            if region.source is not None and selector_offset >= 0
            else region.source
        )
        for item in call_precondition_syntax_occurrences(
            region.selector_text, parsed
        )
    }
    try:
        mask_policy = (
            None
            if dict(parsed.attrs).get("mask") is None
            else PrimitiveMaskMode(dict(parsed.attrs)["mask"])
        )
        dispositions = tuple(
            CallPreconditionDisposition(
                condition=PreconditionKind(value),
                kind=kind,
                source=disposition_sources.get((kind.value, value), region.source),
                forwarded_root=(
                    PreconditionKind(value)
                    if kind is CallPreconditionDispositionKind.FORWARD
                    else None
                ),
            )
            for kind, values in (
                (
                    CallPreconditionDispositionKind.FORWARD,
                    parsed.forwarded_preconditions,
                ),
                (
                    CallPreconditionDispositionKind.DISCHARGE,
                    parsed.discharged_preconditions,
                ),
            )
            for value in values
        )
    except ValueError:
        # Shell validation owns unknown masks/preconditions and duplicates.
        return
    groups = split_arg_groups(region.body)
    positions = {name: index for index, name in enumerate(caller.parameters)}
    argument_bindings = tuple(
        CallArgumentBinding(callee_index, caller_index)
        for callee_index, group in enumerate(groups)
        if (caller_index := positions.get(segments_text(group))) is not None
    )
    callee_name = caller.name if parsed.primitive_ref == "@self" else parsed.primitive_ref
    attrs = dict(parsed.attrs)
    candidates = call_precondition_candidates(
        catalog,
        callee_name,
        mask_policy=mask_policy,
        attributes=attrs,
        argument_count=len(groups),
    )
    resolution = resolve_call_preconditions(
        caller,
        candidates,
        dispositions,
        argument_bindings,
        same_vector=not parsed.type_args or parsed.type_args[0] == "Vec",
        type_tag=None,
        attributes=attrs,
        source=region.source,
    )
    for obligation in resolution.unresolved:
        code = (
            "TSL-CATALOG-MISSING-CALL-PRECONDITION"
            if obligation.status is CallPreconditionObligationStatus.MISSING
            else "TSL-CATALOG-INVALID-CALL-PRECONDITION-FORWARD"
        )
        _append_once(
            diagnostics,
            emitted,
            diagnostic_at(
                severity="error",
                code=code,
                message=f"call to {callee_name!r}: {obligation.reason}",
                source=obligation.source,
            ),
        )
    for stale in resolution.stale_dispositions:
        _append_once(
            diagnostics,
            emitted,
            diagnostic_at(
                severity="error",
                code="TSL-CATALOG-STALE-CALL-PRECONDITION",
                message=(
                    f"call to {callee_name!r}: {stale.kind.value} disposition for "
                    f"{stale.condition.value!r} matches no callee condition"
                ),
                source=stale.source,
            ),
        )


def _implementation_bodies(
    primitive: Primitive,
) -> Iterable[tuple[str, SourceSpan | None]]:
    for implementation in primitive.implementations:
        yield implementation.body_text, implementation.body_source
        for variant in implementation.variants:
            yield variant.body_text, variant.body_source


def _regions(segments: Iterable[Segment]) -> Iterable[Region]:
    for segment in segments:
        if not isinstance(segment, Region):
            continue
        yield segment
        for children in segment.child_sequences():
            yield from _regions(children)


def _append_once(
    diagnostics: list[Diagnostic],
    emitted: set[tuple[object, ...]],
    diagnostic: Diagnostic,
) -> None:
    key = (diagnostic.code, diagnostic.message, diagnostic.span)
    if key not in emitted:
        emitted.add(key)
        diagnostics.append(diagnostic)


__all__ = ("validate_call_precondition_dispositions",)
