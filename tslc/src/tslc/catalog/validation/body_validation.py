"""Validate syntax-only TSIL body region shapes before lowering."""

from __future__ import annotations

import re

from collections.abc import Callable

from tslc.catalog.validation.source_spans import source_span
from tslc.diagnostics import Diagnostic, diagnostic_at
from tslc.ir.region_registry import DEFAULT_TSIL_REGION_DESCRIPTORS, region_shell_validator
from tslc.ir.region_syntax import (
    IntrinsicSelector,
    parse_call_selector,
    parse_cast_selector,
    parse_mask_selector,
    parse_var_selector,
    split_arg_groups,
)
from tslc.ir.scan import find_malformed_regions, scan
from tslc.ir.segments import RawText, Region, Segment
from tslc.ir.text import split_selector_terms, split_top_level
from tslc.syntax.ast import OuterTslParseResult, ParsedImplementationBodyEnvelope

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_body_regions(
    parsed: OuterTslParseResult,
    diagnostics: list[Diagnostic],
) -> None:
    """Validate source-owned TSIL region shells without backend semantics."""

    for document in parsed.documents:
        for primitive in document.primitives:
            for envelope in _implementation_body_envelopes(primitive.impl_entries):
                _validate_envelope(primitive.name, envelope, diagnostics)


def _implementation_body_envelopes(entries):
    for entry in entries:
        yield from entry.body_envelopes
        for variant in entry.variants:
            yield from variant.body_envelopes
        yield from _implementation_body_envelopes(entry.children)


def _validate_envelope(
    primitive_name: str,
    envelope: ParsedImplementationBodyEnvelope,
    diagnostics: list[Diagnostic],
) -> None:
    source = source_span(envelope.payload_source)
    for malformed in find_malformed_regions(envelope.payload_text, source=source):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-BODY-MALFORMED-REGION",
                message=(
                    f"primitive {primitive_name!r}: malformed TSIL region "
                    f"{malformed.keyword!r}: {malformed.reason}"
                ),
                source=malformed.source,
            )
        )
    segments = scan(envelope.payload_text, source=source)
    _validate_segments(primitive_name, segments, diagnostics)


def _validate_segments(
    primitive_name: str,
    segments: tuple[Segment, ...] | None,
    diagnostics: list[Diagnostic],
) -> None:
    if segments is None:
        return
    for segment in segments:
        if isinstance(segment, RawText):
            continue
        _validate_region(primitive_name, segment, diagnostics)
        _validate_segments(primitive_name, segment.body, diagnostics)
        _validate_segments(primitive_name, segment.block, diagnostics)
        _validate_segments(primitive_name, segment.else_block, diagnostics)
        if segment.arms is not None:
            for _label, body in segment.arms:
                _validate_segments(primitive_name, body, diagnostics)


def _validate_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    validator_id = region_shell_validator(region.keyword)
    if validator_id is None:
        return
    validator = _SHELL_VALIDATORS.get(validator_id)
    if validator is None:
        raise ValueError(f"unknown TSIL shell validator {validator_id!r}")
    validator(primitive_name, region, diagnostics)


def _validate_call_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    if parse_call_selector(region.selector_text) is not None:
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-CALL-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed call selector "
                f"{region.selector_text!r}"
            ),
            source=region.source,
        )
    )


def _validate_let_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    groups = split_top_level(_segments_text(region.body))
    if (
        region.selector_text.strip() == "type"
        and len(groups) == 2
        and _IDENTIFIER.fullmatch(groups[0].strip()) is not None
    ):
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-LET",
            message=(
                f"primitive {primitive_name!r}: let<type> must be "
                "`let<type>(Name, type-expression)`"
            ),
            source=region.source,
        )
    )


def _validate_intrin_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    selector = IntrinsicSelector.parse(region.selector_text)
    if selector.name is not None and not selector.unsupported_terms:
        return
    detail = (
        "missing intrinsic name"
        if selector.name is None
        else "selector modifiers must be inside build[...]"
    )
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-INTRIN-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed intrin selector "
                f"{region.selector_text!r}: {detail}"
            ),
            source=region.source,
        )
    )


def _validate_helper_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    terms = split_selector_terms(region.selector_text)
    if terms and _IDENTIFIER.fullmatch(terms[0].strip()) is not None:
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-HELPER-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed helper selector "
                f"{region.selector_text!r}; expected `helper<name>(args)`"
            ),
            source=region.source,
        )
    )


def _validate_mask_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    arity = len(split_top_level(_segments_text(region.body)))
    if parse_mask_selector(region.selector_text, arity) is not None:
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-MASK-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: malformed mask selector "
                f"{region.selector_text!r}; expected one of "
                "`mask<lane_true>()`, `mask<lane_false>()`, `mask<zero>()`, "
                "`mask<all>()`, `mask<test>(mask, index)`, "
                "`mask<test, imask>(imask, index)`, "
                "`mask<set>(mask, index)`, `mask<clear>(mask, index)`, or "
                "`mask<set_to>(mask, index, value)`"
            ),
            source=region.source,
        )
    )


def _validate_var_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    groups = split_top_level(_segments_text(region.body))
    selector = parse_var_selector(region.selector_text, len(groups))
    if selector is not None and (
        selector.kind != "runtime_array"
        or _IDENTIFIER.fullmatch(groups[1].strip()) is not None
    ):
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-VAR",
            message=(
                f"primitive {primitive_name!r}: malformed var declaration; "
                "expected `var<infer>(name, value)`, "
                "`var<const_infer>(name, value)`, "
                "`var<typed>(type, name, value)`, "
                "`var<const_typed>(type, name, value)`, "
                "`var<init_register>(name)`, "
                "`var<const_init_register>(name)`, or "
                "`var<runtime_array>(element_type, name, count)`"
            ),
            source=region.source,
        )
    )


def _validate_cast_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    selector = parse_cast_selector(region.selector_text)
    if not selector.is_valid:
        unsupported = (
            f": unsupported selector terms {selector.unsupported_terms!r}"
            if selector.unsupported_terms
            else ""
        )
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-BODY-BAD-CAST-SELECTOR",
                message=(
                    f"primitive {primitive_name!r}: malformed cast selector "
                    f"{region.selector_text!r}{unsupported}"
                ),
                source=region.source,
            )
        )
        return

    args = split_top_level(_segments_text(region.body))
    if len(args) != 2:
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-BODY-BAD-CAST",
                message=(
                    f"primitive {primitive_name!r}: cast must be "
                    "`cast<variant[, type=value|ptr|const_ptr]>(Type, expr)`"
                ),
                source=region.source,
            )
        )
        return

    target_type = args[0].strip()
    if selector.type_kind in {"ptr", "const_ptr"}:
        if selector.variant != "reinterpret":
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BODY-BAD-CAST",
                    message=(
                        f"primitive {primitive_name!r}: pointer casts must use "
                        "`cast<reinterpret, type=ptr|const_ptr>(Type, expr)`"
                    ),
                    source=region.source,
                )
            )
        if target_type.rstrip().endswith("*"):
            diagnostics.append(
                diagnostic_at(
                    severity="error",
                    code="TSL-BODY-BAD-CAST",
                    message=(
                        f"primitive {primitive_name!r}: pointer cast type "
                        "selectors own pointer-ness; omit trailing `*` from the "
                        "target type"
                    ),
                    source=region.source,
                )
            )
        return

    if target_type.rstrip().endswith("*"):
        diagnostics.append(
            diagnostic_at(
                severity="error",
                code="TSL-BODY-BAD-CAST",
                message=(
                    f"primitive {primitive_name!r}: pointer casts must use "
                    "`cast<reinterpret, type=ptr|const_ptr>(Type, expr)` "
                    "instead of a trailing `*` target type"
                ),
                source=region.source,
            )
        )


def _validate_no_selector_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    if not region.selector_text.strip():
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-QUERY-SELECTOR",
            message=(
                f"primitive {primitive_name!r}: {region.keyword} regions do "
                f"not take selectors; use `{region.keyword}(query)`"
            ),
            source=region.source,
        )
    )


def _validate_select_expr_region(
    primitive_name: str,
    region: Region,
    diagnostics: list[Diagnostic],
) -> None:
    if not region.selector_text.strip() and len(split_arg_groups(region.body)) == 3:
        return
    diagnostics.append(
        diagnostic_at(
            severity="error",
            code="TSL-BODY-BAD-SELECT-EXPR",
            message=(
                f"primitive {primitive_name!r}: select_expr must be "
                "`select_expr(condition, if_true, if_false)`"
            ),
            source=region.source,
        )
    )


def _segments_text(segments: tuple[Segment, ...]) -> str:
    return "".join(
        segment.text if isinstance(segment, RawText) else segment.full_text
        for segment in segments
    )


ShellValidator = Callable[[str, Region, list[Diagnostic]], None]

_SHELL_VALIDATORS: dict[str, ShellValidator] = {
    "call_selector": _validate_call_region,
    "cast_selector": _validate_cast_region,
    "helper_selector": _validate_helper_region,
    "let_type": _validate_let_region,
    "intrin_selector": _validate_intrin_region,
    "mask_selector": _validate_mask_region,
    "no_selector": _validate_no_selector_region,
    "select_expr": _validate_select_expr_region,
    "var_selector": _validate_var_region,
}


def _validate_shell_validator_registry() -> None:
    declared = {
        descriptor.shell_validator
        for descriptor in DEFAULT_TSIL_REGION_DESCRIPTORS
        if descriptor.shell_validator is not None
    }
    missing = declared - set(_SHELL_VALIDATORS)
    if missing:
        names = ", ".join(repr(name) for name in sorted(missing))
        raise ValueError(f"unknown TSIL shell validator id(s): {names}")


_validate_shell_validator_registry()


__all__ = ("validate_body_regions",)
