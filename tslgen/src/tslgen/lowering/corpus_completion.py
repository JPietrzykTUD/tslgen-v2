"""Real-corpus lowering completion characterization.

This module is an audit boundary, not a generation pipeline stage. It consumes
already-loaded source documents, reuses the accepted outer parser and recursive
source-body fragment lowering, and reports deterministic corpus facts.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from tslgen.core.diagnostics import Diagnostic, SourceLocation
from tslgen.domain.catalog import LowerableDirective
from tslgen.io.sources import SourceDocument
from tslgen.lowering.backend_intrinsics import discover_backend_intrinsic_requests_in_text
from tslgen.lowering.backend_output_source_islands import (
    discover_backend_output_requests_in_text,
)
from tslgen.lowering.backend_type_queries import discover_backend_type_queries_in_text
from tslgen.lowering.backend_value_queries import discover_backend_value_queries_in_text
from tslgen.lowering.mask_keywords import discover_mask_keyword_requests_in_text
from tslgen.lowering.mask_lane_constants import (
    discover_mask_lane_constant_requests_in_text,
)
from tslgen.lowering.source_operation_handoff import lower_source_operation_discovery
from tslgen.lowering.source_operations import discover_source_operation_requests_in_text
from tslgen.lowering.source_body_fragments import (
    KeywordRegionFragment,
    RawSourceFragment,
    SourceBodyFragmentSequence,
    extract_intrin_compose_requests,
    extract_primitive_call_directives,
    lower_source_body_fragments,
)
from tslgen.lowering.type_syntax import parse_type_syntax
from tslgen.pipeline._tsil_directives import classify_tsil_directive_line
from tslgen.syntax.ast import ParsedRawStringLine
from tslgen.syntax.outer_ast import ParsedImplementationBodyEnvelope
from tslgen.syntax.outer_parser import OuterTslParser
from tslgen.syntax.source_body_regions import (
    SourceBodyKeyword,
    SourceBodyText,
)
from tslgen.syntax.tsil_lexical import (
    ANGLE_DELIMITER,
    PAREN_DELIMITER,
    matching_close_lexical,
    matching_quote_close,
    starts_quoted_text,
)


class CorpusLoweringStatus(Enum):
    ACCEPTED_LOWERING = "accepted_lowering"
    ACCEPTED_HANDOFF = "accepted_handoff"
    DEFERRED_BACKEND_ONLY = "deferred_backend_only"
    SOURCE_DATA_FLAW = "source_data_flaw"
    UNSUPPORTED_GENERATION_RELEVANT = "unsupported_generation_relevant"


@dataclass(frozen=True, slots=True)
class CorpusLoweringFamilyCount:
    family: str
    status: CorpusLoweringStatus
    count: int


@dataclass(frozen=True, slots=True)
class CorpusLoweringRepresentative:
    family: str
    status: CorpusLoweringStatus
    source: SourceLocation
    source_text: str


@dataclass(frozen=True, slots=True)
class CorpusLoweringCharacterization:
    primitive_file_count: int
    parsed_document_count: int
    primitive_count: int
    body_envelope_count: int
    observed_families: tuple[CorpusLoweringFamilyCount, ...]
    validated_families: tuple[CorpusLoweringFamilyCount, ...]
    recursive_keyword_families: tuple[CorpusLoweringFamilyCount, ...]
    representatives: tuple[CorpusLoweringRepresentative, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def unsupported_generation_relevant(self) -> tuple[CorpusLoweringFamilyCount, ...]:
        return tuple(
            item
            for item in self.observed_families
            if item.status is CorpusLoweringStatus.UNSUPPORTED_GENERATION_RELEVANT
        )

    @property
    def is_complete_for_backend_rendering(self) -> bool:
        return (
            not self.diagnostics
            and not self.unsupported_generation_relevant
            and _counts_by_family(self.observed_families)
            == _counts_by_family(self.validated_families)
        )


@dataclass(frozen=True, slots=True)
class _Occurrence:
    family: str
    source: SourceLocation
    source_text: str


_ANGLE_CALL_HEADS: tuple[str, ...] = (
    "assume_aligned",
    "call",
    "cast",
    "if",
    "intrin_compose",
    "intrin",
    "io",
    "let",
    "loop",
    "mask",
    "mem",
    "pack",
    "switch",
    "type",
    "value",
    "var",
)
_ANGLE_ONLY_HEADS: tuple[str, ...] = ("array_type", "else")
_PAREN_HEADS: tuple[str, ...] = ("emit_return",)
_GENERIC_PREFIX = "generic::"
_MASK_LANE_PREFIX = "mask::lane::"
_IDENTIFIER_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)

_FAMILY_STATUS: dict[str, CorpusLoweringStatus] = {
    "array_type": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "assume_aligned": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "call<primitive>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "cast<bitcast>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "cast<reinterpret>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "cast<saturating>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "cast<static>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "else<compile>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "else<generation>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "emit_return": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "generic::length": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "generic::runtime_length": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "if<compile>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "if<generation>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "intrin": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "intrin_compose": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "io<endl>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "io<write>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "io<write_base>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "io<write_bin>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "let<type>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "loop<range>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "loop<unroll>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "mask<set:1>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mask<set>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mask<test>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mask<zero>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mask::lane::all_false": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "mask::lane::all_true": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "mem<alloc>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mem<alloc_aligned>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mem<copy>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "mem<free>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "pack": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "switch<compile>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "type<backend>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "type<generation>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "value<backend>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "value<generation>": CorpusLoweringStatus.ACCEPTED_LOWERING,
    "var<const_infer>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "var<infer>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "var<init_register>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
    "var<typed>": CorpusLoweringStatus.ACCEPTED_HANDOFF,
}


def characterize_primitive_corpus_lowering(
    documents: tuple[SourceDocument, ...],
) -> CorpusLoweringCharacterization:
    """Characterize observed primitive-body TSIL lowering coverage."""

    parsed = OuterTslParser().parse(documents)
    diagnostics: list[Diagnostic] = list(parsed.diagnostics)
    primitives = tuple(
        primitive
        for document in parsed.documents
        for primitive in document.primitives
    )
    envelopes = tuple(
        envelope for primitive in primitives for envelope in primitive.body_envelopes
    )

    observed: list[_Occurrence] = []
    recursive_counts: Counter[str] = Counter()

    for primitive in primitives:
        for envelope in primitive.body_envelopes:
            source_text = SourceBodyText.from_envelope(envelope)
            fragment_result = lower_source_body_fragments(source_text)
            diagnostics.extend(fragment_result.diagnostics)
            diagnostics.extend(
                extract_intrin_compose_requests(fragment_result.sequence).diagnostics
            )
            diagnostics.extend(
                extract_primitive_call_directives(fragment_result.sequence).diagnostics
            )
            recursive_counts.update(
                _recursive_keyword_family_counts(fragment_result.sequence)
            )
            envelope_occurrences = _scan_observed_keyword_islands(envelope)
            observed.extend(envelope_occurrences)

    family_counts = _family_counts(observed)
    representatives = _representatives(observed)
    validated_counts, validation_diagnostics = _validated_family_counts(
        observed,
        recursive_counts,
    )
    diagnostics.extend(validation_diagnostics)
    return CorpusLoweringCharacterization(
        primitive_file_count=len(documents),
        parsed_document_count=len(parsed.documents),
        primitive_count=len(primitives),
        body_envelope_count=len(envelopes),
        observed_families=family_counts,
        validated_families=validated_counts,
        recursive_keyword_families=_counter_family_counts(recursive_counts),
        representatives=representatives,
        diagnostics=tuple(diagnostics),
    )


def _recursive_keyword_family_counts(
    sequence: SourceBodyFragmentSequence,
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for fragment in sequence.fragments:
        if isinstance(fragment, RawSourceFragment):
            continue

        family = _recursive_family(fragment)
        if family is not None:
            counts[family] += 1

        for child in (
            fragment.selector_fragments,
            fragment.payload_fragments,
            fragment.body_fragments,
        ):
            if child is not None:
                counts.update(_recursive_keyword_family_counts(child))
    return counts


def _recursive_family(fragment: KeywordRegionFragment) -> str | None:
    keyword = fragment.source_region.head.keyword
    if keyword is SourceBodyKeyword.CALL:
        return "call<primitive>"
    if keyword is SourceBodyKeyword.EMIT_RETURN:
        return "emit_return"
    if keyword is SourceBodyKeyword.ELSE:
        return "else<generation>"
    if keyword is SourceBodyKeyword.IF:
        return "if<generation>"
    if keyword is SourceBodyKeyword.INTRIN_COMPOSE:
        return "intrin_compose"
    if keyword is SourceBodyKeyword.LOOP:
        selector = _fragment_selector_text(fragment)
        if selector in {"range", "unroll"}:
            return f"loop<{selector}>"
        return None
    if keyword is SourceBodyKeyword.SWITCH:
        return "switch<compile>"
    if keyword is SourceBodyKeyword.TYPE and _fragment_selector_text(fragment) == "backend":
        return "type<backend>"
    if keyword is SourceBodyKeyword.VALUE and _fragment_selector_text(fragment) == "generation":
        return "value<generation>"
    if keyword is SourceBodyKeyword.VAR and _fragment_selector_text(fragment) == "init_register":
        return "var<init_register>"
    return None


def _fragment_selector_text(fragment: KeywordRegionFragment) -> str | None:
    selector = fragment.source_region.selector
    if selector is None:
        return None
    return selector.payload_span.text.strip()


def _scan_observed_keyword_islands(
    envelope: ParsedImplementationBodyEnvelope,
) -> tuple[_Occurrence, ...]:
    source_text = SourceBodyText.from_envelope(envelope)
    text = source_text.text
    occurrences: list[_Occurrence] = []
    index = 0

    while index < len(text):
        if starts_quoted_text(text, index):
            quote_close = matching_quote_close(text, index)
            if quote_close is None:
                break
            index = quote_close + 1
            continue

        occurrence = _match_occurrence(source_text, index)
        if occurrence is not None:
            occurrences.append(occurrence)

        index += 1

    return tuple(occurrences)


def _match_occurrence(
    source_text: SourceBodyText,
    start: int,
) -> _Occurrence | None:
    text = source_text.text

    for head in sorted(_ANGLE_CALL_HEADS, key=lambda item: -len(item)):
        if not _head_starts(text, start, head, "<"):
            continue
        close_angle = matching_close_lexical(
            text,
            start + len(head),
            ANGLE_DELIMITER,
        )
        if close_angle is None:
            return None
        payload_start = start + len(head) + 1
        selector = text[payload_start:close_angle]
        cursor = _skip_whitespace(text, close_angle + 1)
        if cursor >= len(text) or text[cursor] != "(":
            continue
        close_paren = matching_close_lexical(text, cursor, PAREN_DELIMITER)
        if close_paren is None:
            return None
        return _Occurrence(
            family=_family_for_angle_call(head, selector),
            source=source_text.source_at(start),
            source_text=text[start : close_paren + 1],
        )

    for head in sorted(_ANGLE_ONLY_HEADS, key=lambda item: -len(item)):
        if not _head_starts(text, start, head, "<"):
            continue
        close_angle = matching_close_lexical(
            text,
            start + len(head),
            ANGLE_DELIMITER,
        )
        if close_angle is None:
            return None
        selector = text[start + len(head) + 1 : close_angle]
        return _Occurrence(
            family=_family_for_angle_only(head, selector),
            source=source_text.source_at(start),
            source_text=text[start : close_angle + 1],
        )

    for head in _PAREN_HEADS:
        if not _head_starts(text, start, head, "("):
            continue
        close_paren = matching_close_lexical(
            text,
            start + len(head),
            PAREN_DELIMITER,
        )
        if close_paren is None:
            return None
        return _Occurrence(
            family=head,
            source=source_text.source_at(start),
            source_text=text[start : close_paren + 1],
        )

    generic = _match_prefixed_identifier(
        source_text,
        start,
        _GENERIC_PREFIX,
        require_call=True,
    )
    if generic is not None:
        return generic

    mask_lane = _match_prefixed_identifier(
        source_text,
        start,
        _MASK_LANE_PREFIX,
        require_call=False,
    )
    if mask_lane is not None:
        return mask_lane

    return None


def _family_for_angle_call(head: str, selector: str) -> str:
    selector = selector.strip()
    if head == "call":
        return "call<primitive>" if selector.startswith("primitive=") else f"call<{selector}>"
    if head == "intrin_compose":
        return "intrin_compose"
    if head == "intrin":
        return "intrin"
    if head == "assume_aligned":
        return "assume_aligned"
    if head in {"type", "value"}:
        return f"{head}<{selector}>"
    if head == "pack":
        return "pack"
    return f"{head}<{selector}>"


def _family_for_angle_only(head: str, selector: str) -> str:
    selector = selector.strip()
    if head == "array_type":
        return "array_type"
    return f"{head}<{selector}>"


def _match_prefixed_identifier(
    source_text: SourceBodyText,
    start: int,
    prefix: str,
    *,
    require_call: bool,
) -> _Occurrence | None:
    text = source_text.text
    if not text.startswith(prefix, start) or not _has_identifier_boundary_before(
        text,
        start,
    ):
        return None
    end = start + len(prefix)
    while end < len(text) and text[end] in _IDENTIFIER_CHARS:
        end += 1
    if end == start + len(prefix):
        return None
    if require_call:
        if end >= len(text) or text[end] != "(":
            return None
        close_paren = matching_close_lexical(text, end, PAREN_DELIMITER)
        if close_paren is None:
            return None
        end = close_paren + 1
    return _Occurrence(
        family=_generic_family(text[start:end]) if require_call else text[start:end],
        source=source_text.source_at(start),
        source_text=text[start:end],
    )


def _head_starts(text: str, start: int, head: str, delimiter: str) -> bool:
    return (
        text.startswith(f"{head}{delimiter}", start)
        and _has_identifier_boundary_before(text, start)
    )


def _has_identifier_boundary_before(text: str, start: int) -> bool:
    return start == 0 or text[start - 1] not in _IDENTIFIER_CHARS


def _skip_whitespace(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _family_counts(
    occurrences: Iterable[_Occurrence],
) -> tuple[CorpusLoweringFamilyCount, ...]:
    counts = Counter(occurrence.family for occurrence in occurrences)
    return _counter_family_counts(counts)


def _counter_family_counts(
    counts: Counter[str],
) -> tuple[CorpusLoweringFamilyCount, ...]:
    return tuple(
        CorpusLoweringFamilyCount(
            family=family,
            status=_status_for_family(family),
            count=count,
        )
        for family, count in sorted(counts.items())
    )


def _counts_by_family(
    counts: tuple[CorpusLoweringFamilyCount, ...],
) -> dict[str, int]:
    return {item.family: item.count for item in counts}


def _representatives(
    occurrences: Iterable[_Occurrence],
) -> tuple[CorpusLoweringRepresentative, ...]:
    first_by_family: dict[str, _Occurrence] = {}
    for occurrence in sorted(
        occurrences,
        key=lambda item: (
            item.family,
            item.source.path.as_posix(),
            item.source.line,
            item.source.column,
        ),
    ):
        first_by_family.setdefault(occurrence.family, occurrence)
    return tuple(
        CorpusLoweringRepresentative(
            family=family,
            status=_status_for_family(family),
            source=occurrence.source,
            source_text=occurrence.source_text,
        )
        for family, occurrence in sorted(first_by_family.items())
    )


def _representative_occurrences(
    occurrences: Iterable[_Occurrence],
) -> tuple[_Occurrence, ...]:
    first_by_family: dict[str, _Occurrence] = {}
    for occurrence in sorted(
        occurrences,
        key=lambda item: (
            item.family,
            item.source.path.as_posix(),
            item.source.line,
            item.source.column,
        ),
    ):
        first_by_family.setdefault(occurrence.family, occurrence)
    return tuple(occurrence for _, occurrence in sorted(first_by_family.items()))


def _status_for_family(family: str) -> CorpusLoweringStatus:
    return _FAMILY_STATUS.get(
        family,
        CorpusLoweringStatus.UNSUPPORTED_GENERATION_RELEVANT,
    )


def _validated_family_counts(
    occurrences: tuple[_Occurrence, ...],
    recursive_counts: Counter[str],
) -> tuple[tuple[CorpusLoweringFamilyCount, ...], tuple[Diagnostic, ...]]:
    observed_counts = Counter(occurrence.family for occurrence in occurrences)
    validated_counts: Counter[str] = Counter()
    diagnostics: list[Diagnostic] = []

    for occurrence in _representative_occurrences(occurrences):
        family = occurrence.family
        if recursive_counts.get(family, 0) == observed_counts[family]:
            validated_counts[family] = observed_counts[family]
            continue

        diagnostic = _validation_diagnostic(occurrence)
        if diagnostic is None:
            validated_counts[family] = observed_counts[family]
        else:
            diagnostics.append(diagnostic)

    return (_counter_family_counts(validated_counts), tuple(diagnostics))


def _generic_family(source_text: str) -> str:
    open_index = source_text.find("(")
    return source_text[:open_index] if open_index != -1 else source_text


def _validation_diagnostic(occurrence: _Occurrence) -> Diagnostic | None:
    family = occurrence.family
    if _status_for_family(family) is CorpusLoweringStatus.UNSUPPORTED_GENERATION_RELEVANT:
        return _unvalidated_diagnostic(occurrence, "unknown generation-relevant family")

    if family in {
        "emit_return",
        "else<compile>",
        "else<generation>",
        "if<compile>",
        "if<generation>",
        "let<type>",
        "loop<range>",
        "loop<unroll>",
        "switch<compile>",
        "var<const_infer>",
        "var<infer>",
        "var<init_register>",
        "var<typed>",
    }:
        return _directive_validation_diagnostic(occurrence)

    if family in {"intrin", "intrin_compose"}:
        return _discovery_validation_diagnostic(
            occurrence,
            discover_backend_intrinsic_requests_in_text(
                occurrence.source_text,
                occurrence.source,
            ),
        )

    if family == "type<backend>":
        return _discovery_validation_diagnostic(
            occurrence,
            discover_backend_type_queries_in_text(
                occurrence.source_text,
                occurrence.source,
            ),
        )

    if family == "value<backend>":
        return _discovery_validation_diagnostic(
            occurrence,
            discover_backend_value_queries_in_text(
                occurrence.source_text,
                occurrence.source,
            ),
        )

    if family in {"type<generation>", "value<generation>"} or family.startswith(
        "generic::"
    ):
        if parse_type_syntax(occurrence.source_text) is None:
            return _unvalidated_diagnostic(
                occurrence,
                "accepted type/generation syntax parser did not parse the island",
            )
        return None

    if family.startswith(("cast<", "io<", "mem<")):
        discovery_result = discover_source_operation_requests_in_text(
            occurrence.source_text,
            occurrence.source,
        )
        if discovery_result.discovery is None or discovery_result.diagnostics:
            return _discovery_validation_diagnostic(occurrence, discovery_result)
        handoff_result = lower_source_operation_discovery(
            None,  # type: ignore[arg-type]
            discovery_result.discovery,
        )
        if handoff_result.diagnostics:
            return _unvalidated_diagnostic(
                occurrence,
                handoff_result.diagnostics[0].message,
            )
        return None

    if family.startswith("mask<"):
        return _discovery_validation_diagnostic(
            occurrence,
            discover_mask_keyword_requests_in_text(
                occurrence.source_text,
                occurrence.source,
            ),
        )

    if family.startswith("mask::lane::"):
        wrapped_source_text = f"value<generation>({occurrence.source_text})"
        return _discovery_validation_diagnostic(
            occurrence,
            discover_mask_lane_constant_requests_in_text(
                wrapped_source_text,
                occurrence.source,
            ),
        )

    if family in {"array_type", "assume_aligned", "pack"}:
        return _discovery_validation_diagnostic(
            occurrence,
            discover_backend_output_requests_in_text(
                occurrence.source_text,
                occurrence.source,
            ),
        )

    return _unvalidated_diagnostic(occurrence, "no accepted validation path selected")


def _directive_validation_diagnostic(occurrence: _Occurrence) -> Diagnostic | None:
    tokens = classify_tsil_directive_line(
        ParsedRawStringLine(text=occurrence.source_text, source=occurrence.source)
    )
    directives = tuple(
        token for token in tokens or () if isinstance(token, LowerableDirective)
    )
    if len(directives) != 1:
        return _unvalidated_diagnostic(
            occurrence,
            "accepted TSIL directive classifier did not find one directive",
        )
    family = _family_for_directive(directives[0])
    if family != occurrence.family:
        return _unvalidated_diagnostic(
            occurrence,
            f"accepted TSIL directive classifier produced {family!r}",
        )
    return None


def _family_for_directive(directive: LowerableDirective) -> str:
    if directive.name == "emit_return":
        return "emit_return"
    if directive.name == "else" and directive.arguments:
        return f"else<{directive.arguments[0]}>"
    if directive.name in {"if", "let", "loop", "switch", "var"} and directive.arguments:
        return f"{directive.name}<{directive.arguments[0]}>"
    return directive.name


def _discovery_validation_diagnostic(
    occurrence: _Occurrence,
    result: object,
) -> Diagnostic | None:
    diagnostics = getattr(result, "diagnostics", ())
    if diagnostics:
        return _unvalidated_diagnostic(occurrence, diagnostics[0].message)
    if getattr(result, "discovery", None) is None:
        return _unvalidated_diagnostic(
            occurrence,
            "accepted discovery boundary did not find the island",
        )
    return None


def _unvalidated_diagnostic(occurrence: _Occurrence, reason: str) -> Diagnostic:
    return Diagnostic(
        severity="error",
        code="TSL-CORPUS-LOWERING-UNVALIDATED-FAMILY",
        message=(
            f"observed TSIL/source island family {occurrence.family!r} was not "
            f"validated through an accepted lowering boundary: {reason}"
        ),
        location=occurrence.source,
    )
