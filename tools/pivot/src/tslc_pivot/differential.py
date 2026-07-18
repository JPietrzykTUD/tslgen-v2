"""Exact comparison between legacy and structured PIVOT projections."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc_pivot.model import (
    PivotDefinition,
    PivotDifferentialDifference,
    PivotDifferentialKind,
    PivotDifferentialReport,
    PivotDocument,
    PivotLanguage,
    PivotSkip,
)
from tslc_pivot.render_yaml import render_pivot_yaml


type _DocumentedDefinition = tuple[str, PivotDefinition]


def compare_pivot_projections(
    language: PivotLanguage,
    legacy_documents: tuple[PivotDocument, ...],
    legacy_skipped: tuple[PivotSkip, ...],
    structured_documents: tuple[PivotDocument, ...],
    structured_skipped: tuple[PivotSkip, ...],
) -> PivotDifferentialReport:
    legacy = _flatten(legacy_documents)
    structured = _flatten(structured_documents)
    exact, legacy_unmatched, structured_unmatched = _remove_exact_matches(
        legacy, structured
    )
    legacy_by_nominal = _by_nominal_identity(legacy_unmatched)
    structured_by_nominal = _by_nominal_identity(structured_unmatched)
    differences: list[PivotDifferentialDifference] = []
    direct_mismatch_count = 0
    legacy_only_count = 0
    structured_only_count = 0
    for identity in sorted(set(legacy_by_nominal) | set(structured_by_nominal)):
        legacy_items = sorted(
            legacy_by_nominal.get(identity, ()), key=lambda item: item[1].direct
        )
        structured_items = sorted(
            structured_by_nominal.get(identity, ()), key=lambda item: item[1].direct
        )
        paired = min(len(legacy_items), len(structured_items))
        for index in range(paired):
            document, legacy_definition = legacy_items[index]
            _structured_document, structured_definition = structured_items[index]
            direct_mismatch_count += 1
            differences.append(
                PivotDifferentialDifference(
                    PivotDifferentialKind.DIRECT_MISMATCH,
                    document,
                    "shared nominal definition has different direct instructions",
                    legacy_definition=legacy_definition,
                    structured_definition=structured_definition,
                )
            )
        for document, definition in legacy_items[paired:]:
            legacy_only_count += 1
            differences.append(
                PivotDifferentialDifference(
                    PivotDifferentialKind.LEGACY_ONLY_DEFINITION,
                    document,
                    "legacy projection emitted a definition the structured path skipped",
                    legacy_definition=definition,
                )
            )
        for document, definition in structured_items[paired:]:
            structured_only_count += 1
            differences.append(
                PivotDifferentialDifference(
                    PivotDifferentialKind.STRUCTURED_ONLY_DEFINITION,
                    document,
                    "structured projection safely emitted a definition absent from legacy",
                    structured_definition=definition,
                )
            )

    document_order_equal = _document_order(legacy_documents) == _document_order(
        structured_documents
    )
    if not document_order_equal:
        differences.append(
            PivotDifferentialDifference(
                PivotDifferentialKind.DOCUMENT_ORDER,
                None,
                "legacy and structured document/definition identity order differs",
            )
        )

    legacy_artifacts = _rendered_artifacts(legacy_documents)
    structured_artifacts = _rendered_artifacts(structured_documents)
    yaml_artifacts_equal = legacy_artifacts == structured_artifacts
    if not yaml_artifacts_equal:
        for path in sorted(set(legacy_artifacts) | set(structured_artifacts)):
            if legacy_artifacts.get(path) == structured_artifacts.get(path):
                continue
            differences.append(
                PivotDifferentialDifference(
                    PivotDifferentialKind.YAML_ARTIFACT,
                    path.removesuffix(".yaml"),
                    "legacy and structured YAML artifact bytes differ",
                )
            )

    (
        exact_skips,
        skip_source_mismatches,
        skip_reason_mismatches,
        legacy_only_skips,
        structured_only_skips,
    ) = _compare_skips(legacy_skipped, structured_skipped)
    differences.extend(
        PivotDifferentialDifference(
            PivotDifferentialKind.SKIP_SOURCE_MISMATCH,
            None,
            "the same unsupported specialization and reason has a different source span",
            legacy_skip=legacy_skip,
            structured_skip=structured_skip,
        )
        for legacy_skip, structured_skip in skip_source_mismatches
    )
    differences.extend(
        PivotDifferentialDifference(
            PivotDifferentialKind.SKIP_REASON_MISMATCH,
            None,
            "the same unsupported specialization has a different skip reason",
            legacy_skip=legacy_skip,
            structured_skip=structured_skip,
        )
        for legacy_skip, structured_skip in skip_reason_mismatches
    )
    differences.extend(
        PivotDifferentialDifference(
            PivotDifferentialKind.LEGACY_ONLY_SKIP,
            None,
            "legacy projection recorded a skip absent from the structured path",
            legacy_skip=skip,
        )
        for skip in legacy_only_skips
    )
    differences.extend(
        PivotDifferentialDifference(
            PivotDifferentialKind.STRUCTURED_ONLY_SKIP,
            None,
            "structured projection recorded a skip absent from the legacy path",
            structured_skip=skip,
        )
        for skip in structured_only_skips
    )

    return PivotDifferentialReport(
        language=language,
        structured_documents=structured_documents,
        structured_skipped=structured_skipped,
        legacy_definition_count=len(legacy),
        structured_definition_count=len(structured),
        exact_shared_definition_count=exact,
        direct_mismatch_count=direct_mismatch_count,
        legacy_only_definition_count=legacy_only_count,
        structured_only_definition_count=structured_only_count,
        exact_shared_skip_count=exact_skips,
        skip_source_mismatch_count=len(skip_source_mismatches),
        skip_reason_mismatch_count=len(skip_reason_mismatches),
        legacy_only_skip_count=len(legacy_only_skips),
        structured_only_skip_count=len(structured_only_skips),
        document_order_equal=document_order_equal,
        yaml_artifacts_equal=yaml_artifacts_equal,
        differences=tuple(differences),
    )


def pivot_differential_digest(
    reports: tuple[PivotDifferentialReport, ...],
    *,
    source_root: Path,
) -> str:
    """Hash the complete structured projection and its classified comparison."""

    payload = [
        {
            "language": report.language.value,
            "summary": {
                "legacy_definitions": report.legacy_definition_count,
                "structured_definitions": report.structured_definition_count,
                "exact_shared_definitions": report.exact_shared_definition_count,
                "direct_mismatches": report.direct_mismatch_count,
                "legacy_only_definitions": report.legacy_only_definition_count,
                "structured_only_definitions": report.structured_only_definition_count,
                "exact_shared_skips": report.exact_shared_skip_count,
                "skip_source_mismatches": report.skip_source_mismatch_count,
                "skip_reason_mismatches": report.skip_reason_mismatch_count,
                "legacy_only_skips": report.legacy_only_skip_count,
                "structured_only_skips": report.structured_only_skip_count,
                "document_order_equal": report.document_order_equal,
                "yaml_artifacts_equal": report.yaml_artifacts_equal,
            },
            "documents": [
                [
                    document.name,
                    list(document.inputs),
                    document.output,
                    [
                        [
                            definition.isa,
                            definition.dtype,
                            [list(item) for item in definition.signature],
                            list(definition.direct),
                        ]
                        for definition in document.definitions
                    ],
                ]
                for document in report.structured_documents
            ],
            "skips": [
                [
                    skip.profile,
                    skip.primitive,
                    skip.extension,
                    skip.type_tag,
                    skip.reason,
                    _source_record(skip.source, source_root),
                ]
                for skip in report.structured_skipped
            ],
            "differences": [
                [
                    difference.kind.value,
                    difference.document,
                    difference.detail,
                    None
                    if difference.legacy_definition is None
                    else list(difference.legacy_definition.direct),
                    None
                    if difference.structured_definition is None
                    else list(difference.structured_definition.direct),
                    None
                    if difference.legacy_skip is None
                    else [
                        difference.legacy_skip.reason,
                        _source_record(difference.legacy_skip.source, source_root),
                    ],
                    None
                    if difference.structured_skip is None
                    else [
                        difference.structured_skip.reason,
                        _source_record(
                            difference.structured_skip.source, source_root
                        ),
                    ],
                ]
                for difference in report.differences
            ],
        }
        for report in reports
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _flatten(
    documents: tuple[PivotDocument, ...],
) -> tuple[_DocumentedDefinition, ...]:
    return tuple(
        (document.name, definition)
        for document in documents
        for definition in document.definitions
    )


def _remove_exact_matches(
    legacy: tuple[_DocumentedDefinition, ...],
    structured: tuple[_DocumentedDefinition, ...],
) -> tuple[
    int,
    tuple[_DocumentedDefinition, ...],
    tuple[_DocumentedDefinition, ...],
]:
    exact_counts = Counter(legacy) & Counter(structured)
    exact = sum(exact_counts.values())
    return (
        exact,
        _subtract_occurrences(legacy, exact_counts),
        _subtract_occurrences(structured, exact_counts),
    )


def _by_nominal_identity(
    items: tuple[_DocumentedDefinition, ...],
) -> dict[tuple[object, ...], tuple[_DocumentedDefinition, ...]]:
    grouped: defaultdict[
        tuple[object, ...], list[_DocumentedDefinition]
    ] = defaultdict(list)
    for document, definition in items:
        grouped[
            (
                document,
                definition.isa,
                definition.dtype,
                definition.signature,
            )
        ].append((document, definition))
    return {key: tuple(value) for key, value in grouped.items()}


def _document_order(
    documents: tuple[PivotDocument, ...],
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            document.name,
            document.inputs,
            document.output,
            tuple(
                (
                    definition.isa,
                    definition.dtype,
                    definition.signature,
                    definition.direct,
                )
                for definition in document.definitions
            ),
        )
        for document in documents
    )


def _rendered_artifacts(
    documents: tuple[PivotDocument, ...],
) -> dict[str, str]:
    return {
        f"{document.name}.yaml": render_pivot_yaml(document)
        for document in documents
    }


def _compare_skips(
    legacy: tuple[PivotSkip, ...],
    structured: tuple[PivotSkip, ...],
) -> tuple[
    int,
    tuple[tuple[PivotSkip, PivotSkip], ...],
    tuple[tuple[PivotSkip, PivotSkip], ...],
    tuple[PivotSkip, ...],
    tuple[PivotSkip, ...],
]:
    exact_counts = Counter(legacy) & Counter(structured)
    exact = sum(exact_counts.values())
    legacy_unmatched = _subtract_occurrences(legacy, exact_counts)
    structured_unmatched = _subtract_occurrences(structured, exact_counts)
    legacy_by_slot = _skips_by_slot(legacy_unmatched)
    structured_by_slot = _skips_by_slot(structured_unmatched)
    source_mismatches: list[tuple[PivotSkip, PivotSkip]] = []
    reason_mismatches: list[tuple[PivotSkip, PivotSkip]] = []
    legacy_only: list[PivotSkip] = []
    structured_only: list[PivotSkip] = []
    for identity in sorted(set(legacy_by_slot) | set(structured_by_slot)):
        pairs, legacy_remaining, structured_remaining = _pair_nearest_skips(
            legacy_by_slot.get(identity, ()),
            structured_by_slot.get(identity, ()),
        )
        for legacy_skip, structured_skip in pairs:
            target = (
                source_mismatches
                if legacy_skip.reason == structured_skip.reason
                else reason_mismatches
            )
            target.append((legacy_skip, structured_skip))
        legacy_only.extend(legacy_remaining)
        structured_only.extend(structured_remaining)
    return (
        exact,
        tuple(source_mismatches),
        tuple(reason_mismatches),
        tuple(legacy_only),
        tuple(structured_only),
    )


def _subtract_occurrences[T](
    items: tuple[T, ...], counts: Counter[T]
) -> tuple[T, ...]:
    remaining = counts.copy()
    result: list[T] = []
    for item in items:
        if remaining[item]:
            remaining[item] -= 1
        else:
            result.append(item)
    return tuple(result)


def _skips_by_slot(
    skips: tuple[PivotSkip, ...],
) -> dict[tuple[str, ...], tuple[PivotSkip, ...]]:
    grouped: defaultdict[tuple[str, ...], list[PivotSkip]] = defaultdict(list)
    for skip in skips:
        grouped[
            (
                skip.language.value,
                skip.profile,
                skip.primitive,
                skip.extension,
                skip.type_tag,
                "" if skip.source is None else skip.source.path.as_posix(),
            )
        ].append(skip)
    return {key: tuple(value) for key, value in grouped.items()}


def _skip_sort_key(skip: PivotSkip) -> tuple[object, ...]:
    source = skip.source
    return (
        skip.reason,
        "" if source is None else source.path.as_posix(),
        0 if source is None else source.line,
        0 if source is None else source.column,
    )


def _pair_nearest_skips(
    legacy: tuple[PivotSkip, ...],
    structured: tuple[PivotSkip, ...],
) -> tuple[
    tuple[tuple[PivotSkip, PivotSkip], ...],
    tuple[PivotSkip, ...],
    tuple[PivotSkip, ...],
]:
    legacy_remaining = list(legacy)
    structured_remaining = list(structured)
    pairs: list[tuple[PivotSkip, PivotSkip]] = []
    while legacy_remaining and structured_remaining:
        legacy_index, structured_index = min(
            (
                (legacy_index, structured_index)
                for legacy_index in range(len(legacy_remaining))
                for structured_index in range(len(structured_remaining))
            ),
            key=lambda indexes: (
                _skip_pair_key(
                    legacy_remaining[indexes[0]],
                    structured_remaining[indexes[1]],
                ),
                _skip_sort_key(legacy_remaining[indexes[0]]),
                _skip_sort_key(structured_remaining[indexes[1]]),
            ),
        )
        pairs.append(
            (
                legacy_remaining.pop(legacy_index),
                structured_remaining.pop(structured_index),
            )
        )
    return (
        tuple(pairs),
        tuple(sorted(legacy_remaining, key=_skip_sort_key)),
        tuple(sorted(structured_remaining, key=_skip_sort_key)),
    )


def _skip_pair_key(
    legacy: PivotSkip,
    structured: PivotSkip,
) -> tuple[object, ...]:
    legacy_source = legacy.source
    structured_source = structured.source
    if legacy_source is None or structured_source is None:
        return (
            legacy_source is None,
            structured_source is None,
            legacy.reason != structured.reason,
        )
    return (
        abs(legacy_source.line - structured_source.line),
        abs(legacy_source.column - structured_source.column),
        abs(legacy_source.end_line - structured_source.end_line),
        legacy.reason != structured.reason,
    )


def _source_record(
    source: SourceSpan | None,
    source_root: Path,
) -> list[object] | None:
    if source is None:
        return None
    try:
        relative = source.path.resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"PIVOT differential source {source.path} is outside digest root "
            f"{source_root}"
        ) from exc
    return [
        relative.as_posix(),
        source.line,
        source.column,
        source.end_line,
        source.end_column,
    ]


__all__ = ("compare_pivot_projections", "pivot_differential_digest")
