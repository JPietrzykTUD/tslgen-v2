"""Durable full-corpus evidence for the PIVOT coverage ratchet."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

from tslc.diagnostics import SourceSpan
from tslc_pivot.body_ir import pivot_shadow_census_digest
from tslc_pivot.cli import (
    PivotCliInvocation,
    render_cli_command,
    resolve_cli_invocation,
)
from tslc_pivot.differential import pivot_differential_digest
from tslc_pivot.exporter import PivotExportRequest
from tslc_pivot.model import PivotExportResult


CANONICAL_FULL_EXPORT_ARGV = (
    "--config",
    "tslc.toml",
    "--language",
    "cpp,rust",
    "--output-root",
    "tslctmp/pivot-rework/full-export",
    "--show-skips",
)
CANONICAL_FULL_EXPORT_COMMAND = render_cli_command(CANONICAL_FULL_EXPORT_ARGV)
_SKIP_CATEGORY_SCHEME = "reason-prefix-v1"

type _DefinitionIdentity = tuple[
    str,
    str,
    str,
    str,
    tuple[tuple[str, str], ...],
]


@dataclass(frozen=True, slots=True)
class _FileEvidence:
    path: str
    sha256: str

    def manifest_record(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True, slots=True)
class _FullExportInputEvidence:
    config: _FileEvidence
    source_roots: tuple[str, ...]
    source_files: tuple[_FileEvidence, ...]
    machine_profiles: _FileEvidence
    languages: tuple[str, ...]
    primitives: tuple[str, ...] | None
    profiles: tuple[str, ...] | None
    type_tags: tuple[str, ...]

    def manifest_record(self) -> dict[str, object]:
        request: dict[str, object] = {
            "languages": list(self.languages),
            "primitives": self.primitives,
            "profiles": self.profiles,
            "type_tags": list(self.type_tags),
            "profile_cover": "distinct-feature-sets",
        }
        source_files = [item.manifest_record() for item in self.source_files]
        digest_payload = {
            "config": self.config.manifest_record(),
            "source_files": source_files,
            "machine_profiles": self.machine_profiles.manifest_record(),
            "request": request,
        }
        return {
            "portable_sha256": _canonical_sha256(digest_payload),
            "digest_scheme": "sha256-canonical-json-v2",
            "config": self.config.manifest_record(),
            "source_roots": list(self.source_roots),
            "source_files": source_files,
            "source_corpus_sha256": _canonical_sha256(source_files),
            "machine_profiles": self.machine_profiles.manifest_record(),
            "request": request,
        }


@dataclass(frozen=True, slots=True)
class CanonicalFullExport:
    """Resolved invocation plus its immutable pre-export input evidence."""

    repository_root: Path
    invocation: PivotCliInvocation
    input_evidence: _FullExportInputEvidence

    @property
    def request(self) -> PivotExportRequest:
        return self.invocation.request

    @property
    def argv(self) -> tuple[str, ...]:
        return self.invocation.argv

    @property
    def command(self) -> str:
        return self.invocation.command


def canonical_full_export(repository_root: Path) -> CanonicalFullExport:
    """Resolve canonical argv and snapshot every portable input before export."""

    root = repository_root.resolve()
    invocation = resolve_cli_invocation(
        CANONICAL_FULL_EXPORT_ARGV,
        working_directory=root,
    )
    if not invocation.request.source_paths:
        raise ValueError("canonical PIVOT export has no TSL source files")
    return CanonicalFullExport(
        repository_root=root,
        invocation=invocation,
        input_evidence=_capture_input_evidence(root, invocation),
    )


def build_full_export_manifest(
    run: CanonicalFullExport,
    result: PivotExportResult,
) -> dict[str, object]:
    """Build the exact identity, content, skip, and provenance ratchet."""

    current_inputs = _capture_input_evidence(
        run.repository_root,
        run.invocation,
    )
    if current_inputs != run.input_evidence:
        raise ValueError(
            "canonical PIVOT inputs changed after the pre-export snapshot"
        )

    definitions, definition_counts, definition_collisions = _definition_records(
        result
    )
    artifact_records = [
        {"path": artifact.logical_path, "sha256": artifact.digest}
        for artifact in result.artifacts.artifacts
    ]
    ordered_content = sha256()
    for artifact in result.artifacts.artifacts:
        ordered_content.update(artifact.content.encode("utf-8"))

    language_summaries: dict[str, object] = {}
    for projection in result.projections:
        language = projection.language.value
        if language in language_summaries:
            raise ValueError(f"duplicate PIVOT projection for language {language!r}")
        language_summaries[language] = {
            "documents": len(projection.documents),
            "definitions": definition_counts[language],
            "skips": len(projection.skipped),
        }

    skip_counts: Counter[tuple[str, str]] = Counter(
        (skip.language.value, skip.reason) for skip in result.skipped
    )
    skip_records = [
        {"language": language, "reason": reason, "count": count}
        for (language, reason), count in sorted(skip_counts.items())
    ]
    skip_category_counts: Counter[tuple[str, str]] = Counter(
        (skip.language.value, classify_skip_reason(skip.reason))
        for skip in result.skipped
    )
    skip_category_records = [
        {"language": language, "category": category, "count": count}
        for (language, category), count in sorted(skip_category_counts.items())
    ]
    raw_skip_records, grouped_skip_records = _skip_inventory_records(run, result)
    return {
        "schema": "tslc-pivot-full-export-v3",
        "provenance": {
            "command": run.command,
            "argv": list(run.argv),
            "working_directory": "<repository-root>",
            "inputs": run.input_evidence.manifest_record(),
        },
        "summary": {
            "documents": sum(
                len(projection.documents) for projection in result.projections
            ),
            "definitions": len(definitions),
            "skips": len(result.skipped),
            "languages": dict(sorted(language_summaries.items())),
            "nominal_definition_identities": (
                len(definitions)
                - sum(
                    _collision_multiplicity(collision) - 1
                    for collision in definition_collisions
                )
            ),
            "definition_identity_collisions": {
                "groups": len(definition_collisions),
                "entries": sum(
                    _collision_multiplicity(collision)
                    for collision in definition_collisions
                ),
                "extra_entries": sum(
                    _collision_multiplicity(collision) - 1
                    for collision in definition_collisions
                ),
                "conflicting_groups": sum(
                    _collision_direct_hash_count(collision) > 1
                    for collision in definition_collisions
                ),
                "exact_duplicate_only_groups": sum(
                    _collision_direct_hash_count(collision) == 1
                    for collision in definition_collisions
                ),
            },
        },
        "definition_fields": [
            "language",
            "document",
            "isa",
            "dtype",
            "signature",
            "direct_sha256",
        ],
        "skips_by_language_and_reason": skip_records,
        "skip_category_scheme": _SKIP_CATEGORY_SCHEME,
        "unclassified_skip_count": sum(
            count
            for (_, category), count in skip_category_counts.items()
            if category == "unclassified"
        ),
        "skips_by_language_and_category": skip_category_records,
        "skip_fields": [
            "language",
            "profile",
            "primitive",
            "extension",
            "type",
            "reason",
            "source",
            "count",
        ],
        "skips": grouped_skip_records,
        "skip_inventory_sha256": _canonical_sha256(raw_skip_records),
        "diagnostics": _diagnostic_records(run, result),
        "definitions": definitions,
        "definition_identity_collision_fields": [
            "language",
            "document",
            "isa",
            "dtype",
            "signature",
            "multiplicity",
            "direct_hash_counts",
        ],
        "definition_identity_collisions": definition_collisions,
        "artifacts": {
            "count": len(artifact_records),
            "ordered_content_sha256": ordered_content.hexdigest(),
            "ordered_path_digest_sha256": _canonical_sha256(artifact_records),
            "items": artifact_records,
        },
    }


def render_full_export_manifest(manifest: dict[str, object]) -> str:
    """Render metadata readably and large inventories one record per diff line."""

    definitions = manifest.get("definitions")
    if not isinstance(definitions, list):
        raise ValueError("full-export manifest definitions must be a list")
    keys = sorted(manifest)
    lines = ["{"]
    for key_index, key in enumerate(keys):
        trailing = "," if key_index + 1 < len(keys) else ""
        if key in {"definitions", "definition_identity_collisions", "skips"}:
            records = manifest[key]
            if not isinstance(records, list):
                raise ValueError(f"full-export manifest {key} must be a list")
            lines.append(f"  {json.dumps(key)}: [")
            for record_index, record in enumerate(records):
                record_trailing = "," if record_index + 1 < len(records) else ""
                lines.append(
                    f"    {_canonical_json(record)}{record_trailing}"
                )
            lines.append(f"  ]{trailing}")
            continue
        rendered = json.dumps(
            manifest[key],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        chunk = f"{json.dumps(key)}: {rendered}".splitlines()
        chunk[-1] += trailing
        lines.extend(f"  {line}" for line in chunk)
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_shadow_census_manifest(
    result: PivotExportResult,
    *,
    source_root: Path,
) -> dict[str, object]:
    """Build the durable 27B typed-body census from one canonical export."""

    nominal_identities = Counter(
        (
            census.language.value,
            entry.document,
            entry.definition.isa,
            entry.definition.dtype,
            entry.definition.signature,
        )
        for census in result.shadow_censuses
        for entry in census.entries
    )
    collisions = tuple(count for count in nominal_identities.values() if count > 1)
    return {
        "schema": "tslc-pivot-shadow-census-v1",
        "digest": pivot_shadow_census_digest(
            result.shadow_censuses,
            source_root=source_root,
        ),
        "summary": {
            "entries": sum(
                len(census.entries) for census in result.shadow_censuses
            ),
            "failures": sum(
                len(census.failures) for census in result.shadow_censuses
            ),
            "multi_statement": sum(
                census.multi_statement_count for census in result.shadow_censuses
            ),
            "fixed_wrappers": sum(
                dict(census.origin_counts).get("fixed_wrapper", 0)
                for census in result.shadow_censuses
            ),
            "nominal_collision_groups": len(collisions),
            "nominal_collision_entries": sum(collisions),
        },
        "languages": {
            census.language.value: {
                "entries": len(census.entries),
                "failures": len(census.failures),
                "multi_statement": census.multi_statement_count,
                "categories": dict(census.category_counts),
                "origins": dict(census.origin_counts),
                "features": dict(census.feature_counts),
                "feature_combinations": [
                    {"features": list(features), "count": count}
                    for features, count in census.feature_combination_counts
                ],
            }
            for census in result.shadow_censuses
        },
    }


def render_shadow_census_manifest(manifest: Mapping[str, object]) -> str:
    _validate_shadow_census_manifest(manifest)
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def build_differential_census_manifest(
    result: PivotExportResult,
    *,
    source_root: Path,
) -> dict[str, object]:
    """Build the durable 27C structured-vs-legacy differential census."""

    transitions: Counter[tuple[str, str, str, str]] = Counter()
    for report in result.differentials:
        for difference in report.differences:
            if difference.legacy_skip is None or difference.structured_skip is None:
                continue
            transitions[
                (
                    report.language.value,
                    difference.kind.value,
                    difference.legacy_skip.reason,
                    difference.structured_skip.reason,
                )
            ] += 1
    return {
        "schema": "tslc-pivot-differential-census-v1",
        "digest": pivot_differential_digest(
            result.differentials,
            source_root=source_root,
        ),
        "summary": {
            "legacy_definitions": sum(
                report.legacy_definition_count for report in result.differentials
            ),
            "structured_definitions": sum(
                report.structured_definition_count for report in result.differentials
            ),
            "exact_shared_definitions": sum(
                report.exact_shared_definition_count
                for report in result.differentials
            ),
            "direct_mismatches": sum(
                report.direct_mismatch_count for report in result.differentials
            ),
            "legacy_only_definitions": sum(
                report.legacy_only_definition_count
                for report in result.differentials
            ),
            "structured_only_definitions": sum(
                report.structured_only_definition_count
                for report in result.differentials
            ),
            "exact_shared_skips": sum(
                report.exact_shared_skip_count for report in result.differentials
            ),
            "skip_reason_mismatches": sum(
                report.skip_reason_mismatch_count
                for report in result.differentials
            ),
            "skip_source_mismatches": sum(
                report.skip_source_mismatch_count
                for report in result.differentials
            ),
            "legacy_only_skips": sum(
                report.legacy_only_skip_count for report in result.differentials
            ),
            "structured_only_skips": sum(
                report.structured_only_skip_count
                for report in result.differentials
            ),
        },
        "languages": {
            report.language.value: {
                "legacy_definitions": report.legacy_definition_count,
                "structured_definitions": report.structured_definition_count,
                "exact_shared_definitions": report.exact_shared_definition_count,
                "direct_mismatches": report.direct_mismatch_count,
                "legacy_only_definitions": report.legacy_only_definition_count,
                "structured_only_definitions": report.structured_only_definition_count,
                "legacy_skips": len(
                    next(
                        projection.skipped
                        for projection in result.projections
                        if projection.language is report.language
                    )
                ),
                "structured_skips": len(report.structured_skipped),
                "exact_shared_skips": report.exact_shared_skip_count,
                "skip_source_mismatches": report.skip_source_mismatch_count,
                "skip_reason_mismatches": report.skip_reason_mismatch_count,
                "legacy_only_skips": report.legacy_only_skip_count,
                "structured_only_skips": report.structured_only_skip_count,
                "document_order_equal": report.document_order_equal,
                "yaml_artifacts_equal": report.yaml_artifacts_equal,
            }
            for report in result.differentials
        },
        "skip_fact_transitions": [
            {
                "language": language,
                "kind": kind,
                "legacy": legacy,
                "structured": structured,
                "count": count,
            }
            for (language, kind, legacy, structured), count in sorted(
                transitions.items()
            )
        ],
    }


def render_differential_census_manifest(manifest: Mapping[str, object]) -> str:
    _validate_differential_census_manifest(manifest)
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _definition_records(
    result: PivotExportResult,
) -> tuple[
    list[list[object]],
    Counter[str],
    list[list[object]],
]:
    entries: list[tuple[_DefinitionIdentity, str, list[object]]] = []
    by_identity: dict[_DefinitionIdentity, Counter[str]] = {}
    counts: Counter[str] = Counter()
    for projection in result.projections:
        language = projection.language.value
        for document in projection.documents:
            for definition in document.definitions:
                identity: _DefinitionIdentity = (
                    language,
                    document.name,
                    definition.isa,
                    definition.dtype,
                    definition.signature,
                )
                direct_sha256 = _canonical_sha256(list(definition.direct))
                by_identity.setdefault(identity, Counter())[direct_sha256] += 1
                counts[language] += 1
                entries.append(
                    (
                        identity,
                        direct_sha256,
                        [
                            language,
                            document.name,
                            definition.isa,
                            definition.dtype,
                            [list(item) for item in definition.signature],
                            direct_sha256,
                        ],
                    )
                )
    records = [
        record
        for _, _, record in sorted(entries, key=lambda item: (item[0], item[1]))
    ]
    collisions = [
        [
            *identity[:4],
            [list(item) for item in identity[4]],
            sum(direct_hashes.values()),
            [list(item) for item in sorted(direct_hashes.items())],
        ]
        for identity, direct_hashes in sorted(by_identity.items())
        if sum(direct_hashes.values()) > 1
    ]
    if sum(counts.values()) != len(records):
        raise ValueError("PIVOT definition inventory did not account for every entry")
    return records, counts, collisions


def _collision_multiplicity(record: list[object]) -> int:
    value = record[5]
    if not isinstance(value, int):
        raise ValueError("PIVOT collision multiplicity is not an integer")
    return value


def _collision_direct_hash_count(record: list[object]) -> int:
    value = record[6]
    if not isinstance(value, list):
        raise ValueError("PIVOT collision direct-hash counts are not a list")
    return len(value)


def _skip_inventory_records(
    run: CanonicalFullExport,
    result: PivotExportResult,
) -> tuple[list[list[object]], list[list[object]]]:
    root = run.repository_root.resolve()
    records: list[list[object]] = []
    for skip in result.skipped:
        source: list[object] | None = None
        if skip.source is not None:
            source = [
                _portable_path(skip.source.path, root),
                skip.source.line,
                skip.source.column,
                skip.source.end_line,
                skip.source.end_column,
            ]
        records.append(
            [
                skip.language.value,
                skip.profile,
                skip.primitive,
                skip.extension,
                skip.type_tag,
                skip.reason,
                source,
            ]
        )
    records.sort(key=_canonical_json)
    grouped: list[list[object]] = []
    for record in records:
        if grouped and grouped[-1][:-1] == record:
            count = grouped[-1][-1]
            if not isinstance(count, int):
                raise ValueError("PIVOT skip inventory count is not an integer")
            grouped[-1][-1] = count + 1
        else:
            grouped.append([*record, 1])
    return records, grouped


def _diagnostic_records(
    run: CanonicalFullExport,
    result: PivotExportResult,
) -> list[dict[str, object]]:
    root = run.repository_root.resolve()
    records: list[dict[str, object]] = []
    for diagnostic in result.diagnostics:
        records.append(
            {
                "severity": diagnostic.severity,
                "code": diagnostic.code,
                "message": diagnostic.message,
                "span": _span_record(diagnostic.span, root),
                "related": [
                    {
                        "message": related.message,
                        "span": _span_record(related.span, root),
                    }
                    for related in diagnostic.related
                ],
                "help": diagnostic.help,
            }
        )
    return records


def _span_record(
    span: SourceSpan | None,
    repository_root: Path,
) -> list[object] | None:
    if span is None:
        return None
    return [
        _portable_path(span.path, repository_root),
        span.line,
        span.column,
        span.end_line,
        span.end_column,
    ]


def _capture_input_evidence(
    repository_root: Path,
    invocation: PivotCliInvocation,
) -> _FullExportInputEvidence:
    root = repository_root.resolve()
    config_path = invocation.project_config_path
    if config_path is None:
        raise ValueError("canonical PIVOT export must resolve a project config")
    source_paths = sorted(
        invocation.request.source_paths,
        key=lambda item: _portable_path(item, root),
    )
    return _FullExportInputEvidence(
        config=_file_evidence(config_path, root),
        source_roots=tuple(
            _portable_path(path, root) for path in invocation.source_roots
        ),
        source_files=tuple(_file_evidence(path, root) for path in source_paths),
        machine_profiles=_file_evidence(
            invocation.request.machine_profiles_path,
            root,
        ),
        languages=tuple(item.value for item in invocation.request.languages),
        primitives=invocation.request.primitives,
        profiles=invocation.request.profiles,
        type_tags=invocation.request.type_tags,
    )


def _file_evidence(path: Path, repository_root: Path) -> _FileEvidence:
    portable = _portable_path(path, repository_root)
    try:
        digest = sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(
            f"could not snapshot canonical PIVOT input {path}: {exc}"
        ) from exc
    return _FileEvidence(path=portable, sha256=digest)


def classify_skip_reason(reason: str) -> str:
    """Group current planner reason families without discarding raw evidence."""

    if reason.startswith("PIVOT body "):
        return "residual_target_text"
    if reason.startswith(
        "PIVOT call inlining does not support forwarded immediate or generic arguments:"
    ):
        return "forwarded_call_arguments"
    if (
        reason in {
            "PIVOT does not support generic or immediate parameters",
            "PIVOT does not support representation-change result axes",
            "PIVOT schema requires a value result",
        }
        or reason.startswith("PIVOT does not support signature kind(s):")
    ):
        return "signature_admissibility"
    if reason in {
        "PIVOT does not support compiler boolean-vector masks",
        "PIVOT requires a concrete fixed-width or scalar specialization",
    }:
        return "specialization_admissibility"
    if reason == (
        "PIVOT schema cannot combine callable overloads with different input names"
    ):
        return "schema_conflict"
    if "PIVOT supports only var<infer> and var<const_infer> locals:" in reason:
        return "local_declaration"
    if reason.startswith(
        ("no exact specialization found", "multiple exact specializations found")
    ):
        return "callee_resolution"
    return "unclassified"


def validate_full_export_baseline_update(
    previous: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    allow_reviewed_incompatible_baseline: bool = False,
) -> None:
    """Reject coverage loss unless a reviewer explicitly accepts incompatibility."""

    candidate_inventory = _manifest_definition_inventory(candidate)
    if allow_reviewed_incompatible_baseline:
        return
    previous_inventory = _manifest_definition_inventory(previous)
    removed = previous_inventory - candidate_inventory
    if not removed:
        return
    record, missing_count = sorted(removed.items())[0]
    raise ValueError(
        "full-export baseline update would remove or replace "
        f"{sum(removed.values())} definition occurrence(s); first missing "
        f"record ({missing_count}x): {record}. Pass "
        "--allow-reviewed-incompatible-baseline only after an explicit "
        "product or correctness review."
    )


def update_full_export_baseline(
    path: Path,
    candidate: dict[str, object],
    *,
    allow_reviewed_incompatible_baseline: bool = False,
) -> None:
    """Validate the prior manifest before replacing it with a candidate."""

    _manifest_definition_inventory(candidate)
    if path.exists():
        previous = _load_manifest(path)
        validate_full_export_baseline_update(
            previous,
            candidate,
            allow_reviewed_incompatible_baseline=(
                allow_reviewed_incompatible_baseline
            ),
        )
    rendered = render_full_export_manifest(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


def validate_shadow_census_baseline_update(
    previous: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    allow_reviewed_incompatible_baseline: bool = False,
) -> None:
    """Require explicit review for every typed-body evidence change."""

    _validate_shadow_census_manifest(previous)
    _validate_shadow_census_manifest(candidate)
    if allow_reviewed_incompatible_baseline or previous == candidate:
        return
    raise ValueError(
        "shadow-census baseline facts changed. Pass "
        "--allow-reviewed-incompatible-baseline only after an explicit "
        "typed-body semantics or corpus review."
    )


def validate_differential_census_baseline_update(
    previous: Mapping[str, object],
    candidate: Mapping[str, object],
    *,
    allow_reviewed_incompatible_baseline: bool = False,
) -> None:
    """Require review for every structured differential evidence change."""

    _validate_differential_census_manifest(previous)
    _validate_differential_census_manifest(candidate)
    if allow_reviewed_incompatible_baseline or previous == candidate:
        return
    raise ValueError(
        "differential-census baseline facts changed. Pass "
        "--allow-reviewed-incompatible-baseline only after an explicit "
        "parser, inliner, coverage, or corpus review."
    )


def update_pivot_baselines(
    full_export_path: Path,
    full_export_candidate: dict[str, object],
    shadow_census_path: Path,
    shadow_census_candidate: dict[str, object],
    differential_census_path: Path,
    differential_census_candidate: dict[str, object],
    *,
    allow_reviewed_incompatible_baseline: bool = False,
) -> None:
    """Validate all durable manifests before writing any candidate."""

    _manifest_definition_inventory(full_export_candidate)
    _validate_shadow_census_manifest(shadow_census_candidate)
    _validate_differential_census_manifest(differential_census_candidate)
    if full_export_path.exists():
        validate_full_export_baseline_update(
            _load_manifest(full_export_path),
            full_export_candidate,
            allow_reviewed_incompatible_baseline=(
                allow_reviewed_incompatible_baseline
            ),
        )
    if shadow_census_path.exists():
        validate_shadow_census_baseline_update(
            _load_manifest(shadow_census_path),
            shadow_census_candidate,
            allow_reviewed_incompatible_baseline=(
                allow_reviewed_incompatible_baseline
            ),
        )
    if differential_census_path.exists():
        validate_differential_census_baseline_update(
            _load_manifest(differential_census_path),
            differential_census_candidate,
            allow_reviewed_incompatible_baseline=(
                allow_reviewed_incompatible_baseline
            ),
        )

    full_export_rendered = render_full_export_manifest(full_export_candidate)
    shadow_census_rendered = render_shadow_census_manifest(
        shadow_census_candidate
    )
    differential_census_rendered = render_differential_census_manifest(
        differential_census_candidate
    )
    full_export_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_census_path.parent.mkdir(parents=True, exist_ok=True)
    differential_census_path.parent.mkdir(parents=True, exist_ok=True)
    full_export_path.write_text(full_export_rendered, encoding="utf-8")
    shadow_census_path.write_text(shadow_census_rendered, encoding="utf-8")
    differential_census_path.write_text(
        differential_census_rendered, encoding="utf-8"
    )


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read prior PIVOT baseline {path}: {exc}") from exc
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"prior PIVOT baseline {path} must be a JSON object")
    return value


def _manifest_definition_inventory(
    manifest: Mapping[str, object],
) -> Counter[str]:
    fields = manifest.get("definition_fields")
    expected_fields = [
        "language",
        "document",
        "isa",
        "dtype",
        "signature",
        "direct_sha256",
    ]
    if fields != expected_fields:
        raise ValueError("full-export baseline has unsupported definition fields")
    definitions = manifest.get("definitions")
    if not isinstance(definitions, list):
        raise ValueError("full-export baseline definitions must be a list")
    inventory: Counter[str] = Counter()
    for record in definitions:
        if not isinstance(record, list) or len(record) != len(expected_fields):
            raise ValueError("full-export baseline contains a malformed definition")
        direct_hash = record[-1]
        if (
            not isinstance(direct_hash, str)
            or len(direct_hash) != 64
            or any(character not in "0123456789abcdef" for character in direct_hash)
        ):
            raise ValueError("full-export baseline contains an invalid direct hash")
        inventory[_canonical_json(record)] += 1
    return inventory


def _validate_shadow_census_manifest(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema") != "tslc-pivot-shadow-census-v1":
        raise ValueError("shadow-census baseline has an unsupported schema")
    digest = manifest.get("digest")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("shadow-census baseline has an invalid digest")
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("shadow-census baseline summary must be an object")
    failures = summary.get("failures")
    if failures != 0:
        raise ValueError(
            "shadow-census baseline cannot record hidden construction failures"
        )
    if not isinstance(manifest.get("languages"), dict):
        raise ValueError("shadow-census baseline languages must be an object")


def _validate_differential_census_manifest(
    manifest: Mapping[str, object],
) -> None:
    if manifest.get("schema") != "tslc-pivot-differential-census-v1":
        raise ValueError("differential-census baseline has an unsupported schema")
    digest = manifest.get("digest")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError("differential-census baseline has an invalid digest")
    summary = manifest.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("differential-census baseline summary must be an object")
    if summary.get("direct_mismatches") != 0:
        raise ValueError(
            "differential-census baseline cannot record shared direct mismatches"
        )
    if summary.get("legacy_only_definitions") != 0:
        raise ValueError(
            "differential-census baseline cannot lose legacy definition occurrences"
        )
    legacy = summary.get("legacy_definitions")
    structured = summary.get("structured_definitions")
    exact = summary.get("exact_shared_definitions")
    if (
        not isinstance(legacy, int)
        or legacy < 0
        or not isinstance(structured, int)
        or structured < legacy
        or exact != legacy
    ):
        raise ValueError(
            "differential-census baseline must reproduce every legacy definition"
        )
    count_fields = (
        "structured_only_definitions",
        "exact_shared_skips",
        "skip_source_mismatches",
        "skip_reason_mismatches",
        "legacy_only_skips",
        "structured_only_skips",
    )
    if any(
        not isinstance(summary.get(field), int) or summary[field] < 0
        for field in count_fields
    ):
        raise ValueError(
            "differential-census baseline summary has an invalid count"
        )
    if not isinstance(manifest.get("languages"), dict):
        raise ValueError("differential-census baseline languages must be an object")
    if not isinstance(manifest.get("skip_fact_transitions"), list):
        raise ValueError(
            "differential-census baseline skip transitions must be a list"
        )


def _portable_path(path: Path, repository_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repository_root).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"canonical PIVOT input {resolved} is outside {repository_root}"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = (
    "CANONICAL_FULL_EXPORT_ARGV",
    "CANONICAL_FULL_EXPORT_COMMAND",
    "CanonicalFullExport",
    "build_differential_census_manifest",
    "build_shadow_census_manifest",
    "build_full_export_manifest",
    "canonical_full_export",
    "classify_skip_reason",
    "render_full_export_manifest",
    "render_differential_census_manifest",
    "render_shadow_census_manifest",
    "update_full_export_baseline",
    "update_pivot_baselines",
    "validate_full_export_baseline_update",
    "validate_differential_census_baseline_update",
    "validate_shadow_census_baseline_update",
)
