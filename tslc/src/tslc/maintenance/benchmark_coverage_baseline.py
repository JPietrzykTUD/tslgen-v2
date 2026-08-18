"""Deterministic benchmark-coverage baseline serialization and comparison."""

from __future__ import annotations

import json
from typing import Any, cast

from tslc.benchmark.identity import is_sha256_digest
from tslc.catalog.model import PrimitiveMaskMode
from tslc.maintenance.benchmark_coverage_model import (
    BenchmarkCoverageAudit,
    BenchmarkCoverageIssue,
    BenchmarkIssueBaseline,
    BenchmarkIssueDiff,
    BenchmarkIssueKey,
    BenchmarkIssueKind,
    BenchmarkSlotKey,
    RustBenchmarkCoverageBaseline,
    RustBenchmarkCoverageDiff,
)
from tslc.maintenance.benchmark_inventory import SourceShapeKey
from tslc.maintenance.rust_benchmark_evidence import (
    deserialize_rust_benchmark_evidence,
)

_BASELINE_VERSION = 1
_RUST_BASELINE_VERSION = 1
_CPP_ISSUE_KINDS = frozenset(
    (
        "coverage-gap",
        "inactive-authored-shape",
        "selected-slot-skipped",
        "selected-slot-missing-planner",
        "emitted-without-candidates",
        "candidate-without-coverage",
    )
)
_RUST_ISSUE_KINDS = _CPP_ISSUE_KINDS | {
    "planner-slot-without-selection",
    "policy-supported-without-report",
}


def benchmark_issue_baseline(
    issues: tuple[BenchmarkCoverageIssue, ...],
) -> BenchmarkIssueBaseline:
    """Collapse current issues to their stable, reason-independent identities."""

    keys = {BenchmarkIssueKey.from_issue(issue) for issue in issues}
    return BenchmarkIssueBaseline(tuple(sorted(keys, key=BenchmarkIssueKey.sort_key)))


def diff_benchmark_issues(
    baseline: BenchmarkIssueBaseline,
    current: tuple[BenchmarkCoverageIssue, ...],
) -> BenchmarkIssueDiff:
    """Report newly introduced and resolved strict issue identities."""

    baseline_keys = frozenset(baseline.issues)
    current_by_key = {
        BenchmarkIssueKey.from_issue(issue): issue for issue in current
    }
    new_issues = tuple(
        sorted(
            (
                issue
                for key, issue in current_by_key.items()
                if key not in baseline_keys
            ),
            key=BenchmarkCoverageIssue.sort_key,
        )
    )
    resolved_issues = tuple(
        sorted(
            baseline_keys - current_by_key.keys(),
            key=BenchmarkIssueKey.sort_key,
        )
    )
    return BenchmarkIssueDiff(new_issues, resolved_issues)


def rust_benchmark_coverage_baseline(
    audit: BenchmarkCoverageAudit,
) -> RustBenchmarkCoverageBaseline:
    """Freeze exact Rust issue and successful report/policy evidence."""

    if audit.backend_id != "rust" or audit.rust_evidence is None:
        raise ValueError("Rust benchmark baselines require a Rust coverage audit")
    issues = benchmark_issue_baseline(audit.issues).issues
    return RustBenchmarkCoverageBaseline(issues, audit.rust_evidence)


def diff_rust_benchmark_coverage(
    baseline: RustBenchmarkCoverageBaseline,
    audit: BenchmarkCoverageAudit,
) -> RustBenchmarkCoverageDiff:
    """Reject new gaps and any drift in exact successful Rust evidence."""

    current = rust_benchmark_coverage_baseline(audit)
    return RustBenchmarkCoverageDiff(
        issue_diff=diff_benchmark_issues(
            BenchmarkIssueBaseline(baseline.issues), audit.issues
        ),
        evidence_changed=baseline.evidence != current.evidence,
    )


def serialize_issue_baseline(baseline: BenchmarkIssueBaseline) -> str:
    """Render one compact JSON record per stable issue for reviewable diffs."""

    records = [
        json.dumps(_issue_key_record(issue), separators=(",", ":"))
        for issue in sorted(baseline.issues, key=BenchmarkIssueKey.sort_key)
    ]
    lines = ["{", f'  "version": {_BASELINE_VERSION},', '  "issues": [']
    for index, record in enumerate(records):
        comma = "," if index + 1 < len(records) else ""
        lines.append(f"    {record}{comma}")
    lines.extend(("  ]", "}"))
    return "\n".join(lines) + "\n"


def serialize_rust_benchmark_baseline(
    baseline: RustBenchmarkCoverageBaseline,
) -> str:
    """Render Rust issues and exact report/policy facts as line-diffable JSON."""

    sections: tuple[tuple[str, list[list[object]]], ...] = (
        (
            "issues",
            [
                _rust_issue_key_record(issue)
                for issue in sorted(
                    baseline.issues, key=BenchmarkIssueKey.sort_key
                )
            ],
        ),
        (
            "profiles",
            [
                cast(list[object], profile.record())
                for profile in baseline.evidence.profiles
            ],
        ),
        (
            "candidates",
            [candidate.record() for candidate in baseline.evidence.candidates],
        ),
        (
            "policies",
            [policy.record() for policy in baseline.evidence.policies],
        ),
    )
    lines = [
        "{",
        f'  "version": {_RUST_BASELINE_VERSION},',
        '  "backend": "rust",',
    ]
    for section_index, (name, records) in enumerate(sections):
        lines.append(f'  "{name}": [')
        for index, record in enumerate(records):
            comma = "," if index + 1 < len(records) else ""
            encoded = json.dumps(record, separators=(",", ":"))
            lines.append(f"    {encoded}{comma}")
        section_comma = "," if section_index + 1 < len(sections) else ""
        lines.append(f"  ]{section_comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def deserialize_issue_baseline(text: str) -> BenchmarkIssueBaseline:
    """Load and validate the deterministic benchmark issue baseline."""

    payload: Any = json.loads(text)
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != _BASELINE_VERSION
        or payload.get("backend") not in (None, "cpp")
    ):
        raise ValueError(
            f"expected benchmark baseline version {_BASELINE_VERSION}"
        )
    records = payload.get("issues")
    if not isinstance(records, list):
        raise ValueError("benchmark baseline issues must be a list")
    issues = tuple(
        _issue_key_from_record(
            record,
            expected_backend="cpp",
            allowed_kinds=_CPP_ISSUE_KINDS,
        )
        for record in records
    )
    if len(frozenset(issues)) != len(issues):
        raise ValueError("benchmark baseline contains duplicate issue identities")
    return BenchmarkIssueBaseline(
        tuple(sorted(issues, key=BenchmarkIssueKey.sort_key))
    )


def deserialize_rust_benchmark_baseline(
    text: str,
) -> RustBenchmarkCoverageBaseline:
    """Load and validate the backend-separated exact Rust baseline."""

    payload: Any = json.loads(text)
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != _RUST_BASELINE_VERSION
        or payload.get("backend") != "rust"
    ):
        raise ValueError(
            f"expected Rust benchmark baseline version {_RUST_BASELINE_VERSION}"
        )
    issue_records = payload.get("issues")
    if not isinstance(issue_records, list):
        raise ValueError("Rust benchmark baseline issues must be a list")
    issues = tuple(_rust_issue_key_from_record(record) for record in issue_records)
    if len(frozenset(issues)) != len(issues):
        raise ValueError("Rust benchmark baseline contains duplicate issue identities")
    evidence = deserialize_rust_benchmark_evidence(
        payload.get("profiles"),
        payload.get("candidates"),
        payload.get("policies"),
    )
    return RustBenchmarkCoverageBaseline(
        issues=tuple(sorted(issues, key=BenchmarkIssueKey.sort_key)),
        evidence=evidence,
    )


def _issue_key_record(issue: BenchmarkIssueKey) -> list[object]:
    shape = issue.source_shape
    shape_record: list[object] = [
        shape.primitive_name,
        shape.result_kind,
        list(shape.param_kinds),
        shape.mask_policy,
    ]
    slot = issue.slot
    slot_record: list[object] | None = None
    if slot is not None:
        slot_record = [
            slot.backend_id,
            slot.profile_name,
            slot.extension_name,
            slot.type_tag,
            [list(pair) for pair in slot.axis],
            list(slot.variant_names),
        ]
    return [issue.kind, shape_record, slot_record]


def _rust_issue_key_record(issue: BenchmarkIssueKey) -> list[object]:
    record = _issue_key_record(issue)
    slot_record = record[2]
    if isinstance(slot_record, list) and issue.slot is not None:
        slot_record.extend(
            (
                issue.slot.primitive_name,
                issue.slot.membership,
                issue.slot.specialization_hash,
            )
        )
    return record


def _rust_issue_key_from_record(record: object) -> BenchmarkIssueKey:
    return _issue_key_from_record(
        record,
        rust=True,
        expected_backend="rust",
        allowed_kinds=_RUST_ISSUE_KINDS,
    )


def _issue_key_from_record(
    record: object,
    *,
    rust: bool = False,
    expected_backend: str,
    allowed_kinds: frozenset[str] | set[str],
) -> BenchmarkIssueKey:
    if not isinstance(record, list) or len(record) != 3:
        raise ValueError("benchmark issue record must contain kind, shape, and slot")
    kind_value, shape_value, slot_value = record
    if not isinstance(kind_value, str) or kind_value not in allowed_kinds:
        raise ValueError(f"unknown benchmark issue kind: {kind_value!r}")
    if not isinstance(shape_value, list) or len(shape_value) != 4:
        raise ValueError("benchmark issue shape must contain four fields")
    primitive_name, result_kind, param_kinds_value, mask_policy = shape_value
    if (
        not isinstance(primitive_name, str)
        or not isinstance(result_kind, str)
        or not isinstance(param_kinds_value, list)
        or not all(isinstance(value, str) for value in param_kinds_value)
        or (mask_policy is not None and not isinstance(mask_policy, str))
    ):
        raise ValueError("benchmark issue shape contains invalid field types")
    try:
        mask_mode = (
            None
            if mask_policy is None
            else PrimitiveMaskMode(mask_policy)
        )
    except ValueError as error:
        raise ValueError("benchmark issue shape has an unknown mask mode") from error
    source_shape = SourceShapeKey(
        primitive_name,
        result_kind,
        tuple(cast(list[str], param_kinds_value)),
        mask_mode,
    )
    slot: BenchmarkSlotKey | None = None
    if slot_value is not None:
        expected_fields = 9 if rust else 6
        if not isinstance(slot_value, list) or len(slot_value) != expected_fields:
            raise ValueError(
                f"benchmark issue slot must contain {expected_fields} fields"
            )
        (
            backend_id,
            profile_name,
            extension_name,
            type_tag,
            axis_value,
            variants_value,
            *rust_values,
        ) = slot_value
        scalar_values = (backend_id, profile_name, extension_name, type_tag)
        if not all(isinstance(value, str) for value in scalar_values):
            raise ValueError("benchmark issue slot contains invalid scalar fields")
        if backend_id != expected_backend:
            raise ValueError(
                f"benchmark issue slot backend must be {expected_backend!r}"
            )
        if not isinstance(axis_value, list):
            raise ValueError("benchmark issue slot axis must be a list")
        axis: list[tuple[str, str]] = []
        for pair in axis_value:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(value, str) for value in pair)
            ):
                raise ValueError("benchmark issue slot contains an invalid axis")
            axis.append((cast(str, pair[0]), cast(str, pair[1])))
        if not isinstance(variants_value, list) or not all(
            isinstance(value, str) for value in variants_value
        ):
            raise ValueError("benchmark issue slot variants must be strings")
        membership: int | None = None
        specialization_hash: str | None = None
        slot_primitive_name: str | None = None
        if rust:
            (
                primitive_name_value,
                membership_value,
                specialization_hash_value,
            ) = rust_values
            if not isinstance(primitive_name_value, str) or not primitive_name_value:
                raise ValueError(
                    "Rust benchmark issue primitive name must be a non-empty string"
                )
            if membership_value is not None and (
                type(membership_value) is not int or membership_value < 0
            ):
                raise ValueError(
                    "Rust benchmark issue membership must be a non-negative integer"
                )
            if specialization_hash_value is not None and not is_sha256_digest(
                specialization_hash_value
            ):
                raise ValueError(
                    "Rust benchmark issue specialization hash must be a "
                    "canonical SHA-256 digest"
                )
            membership = membership_value
            specialization_hash = specialization_hash_value
            slot_primitive_name = primitive_name_value
        slot = BenchmarkSlotKey(
            backend_id=cast(str, backend_id),
            profile_name=cast(str, profile_name),
            source_shape=source_shape,
            extension_name=cast(str, extension_name),
            type_tag=cast(str, type_tag),
            axis=tuple(axis),
            variant_names=tuple(cast(list[str], variants_value)),
            primitive_name=slot_primitive_name,
            membership=membership,
            specialization_hash=specialization_hash,
        )
    return BenchmarkIssueKey(
        cast(BenchmarkIssueKind, kind_value), source_shape, slot
    )



__all__ = (
    "benchmark_issue_baseline",
    "deserialize_issue_baseline",
    "deserialize_rust_benchmark_baseline",
    "diff_benchmark_issues",
    "diff_rust_benchmark_coverage",
    "rust_benchmark_coverage_baseline",
    "serialize_issue_baseline",
    "serialize_rust_benchmark_baseline",
)
