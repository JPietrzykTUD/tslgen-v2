"""Format a behavior-coverage report over a generation result.

This operationalizes the charter's "track delivered behavior": for each primitive
it shows how many selected `(profile, backend, extension, type)` slots were emitted
vs. skipped, and the distinct reasons bodies were skipped — i.e. exactly what works
and what is left to support, with the actionable gaps.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from tslc.pipeline import GenerationResult


@dataclass(frozen=True, slots=True)
class PrimitiveCoverage:
    primitive: str
    emitted: int
    skipped: int
    policy_deferred: int = 0

    @property
    def attempted(self) -> int:
        return self.emitted + self.skipped


def coverage_by_primitive(result: GenerationResult) -> tuple[PrimitiveCoverage, ...]:
    emitted = Counter(entry.primitive for entry in result.coverage)
    skipped = Counter(
        entry.primitive for entry in result.skipped if entry.status == "coverage_gap"
    )
    policy_deferred = Counter(
        entry.primitive for entry in result.skipped if entry.status == "policy_deferred"
    )
    names = sorted(set(emitted) | set(skipped) | set(policy_deferred))
    return tuple(
        PrimitiveCoverage(
            primitive=name,
            emitted=emitted[name],
            skipped=skipped[name],
            policy_deferred=policy_deferred[name],
        )
        for name in names
    )


def format_coverage_report(result: GenerationResult) -> str:
    rows = coverage_by_primitive(result)
    total_emitted = sum(row.emitted for row in rows)
    total_skipped = sum(row.skipped for row in rows)
    total_deferred = sum(row.policy_deferred for row in rows)
    deferred_note = (
        f", {total_deferred} policy-deferred slots" if total_deferred else ""
    )
    lines = [
        f"coverage: {total_emitted} emitted / "
        f"{total_emitted + total_skipped} attempted slots "
        f"(profile x backend x ext x type){deferred_note}",
        "",
    ]
    width = max((len(row.primitive) for row in rows), default=1)
    for row in rows:
        notes: list[str] = []
        if row.skipped:
            notes.append(f"{row.skipped} skipped")
        if row.policy_deferred:
            notes.append(f"{row.policy_deferred} policy-deferred")
        note = f", {', '.join(notes)}" if notes else ""
        lines.append(f"  {row.primitive:<{width}}  {row.emitted}/{row.attempted} emitted{note}")

    reasons = Counter(
        entry.reason for entry in result.skipped if entry.status == "coverage_gap"
    )
    if reasons:
        lines.append("")
        lines.append("skipped because (count):")
        for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  ({count}) {reason}")
    deferred_reasons = Counter(
        entry.reason for entry in result.skipped if entry.status == "policy_deferred"
    )
    if deferred_reasons:
        lines.append("")
        lines.append("policy-deferred because (count):")
        for reason, count in sorted(
            deferred_reasons.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"  ({count}) {reason}")
    return "\n".join(lines) + "\n"
