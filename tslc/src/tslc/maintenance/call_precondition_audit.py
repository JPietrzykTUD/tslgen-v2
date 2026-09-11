"""Deterministic audit report for authored primitive-call proof dispositions."""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Literal

from tslc._cli_options import split_csv
from tslc.authoring import check_catalog
from tslc.backend.registry import registered_backend_ids
from tslc.catalog_index_model import CatalogIndex
from tslc.diagnostics import Diagnostic, format_diagnostic, has_errors

CallDisposition = Literal["forward", "discharge"]
CALL_PRECONDITION_AUDIT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CallPreconditionAuditEntry:
    """One validated source-authored call disposition."""

    caller: str
    callee: str
    condition: str
    disposition: CallDisposition
    path: Path
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class CallPreconditionAudit:
    """Validated call-proof inventory; an invalid corpus produces no report."""

    entries: tuple[CallPreconditionAuditEntry, ...]

    @property
    def disposition_counts(self) -> dict[CallDisposition, int]:
        counts = Counter(entry.disposition for entry in self.entries)
        return {
            "forward": counts["forward"],
            "discharge": counts["discharge"],
        }


def build_call_precondition_audit(index: CatalogIndex) -> CallPreconditionAudit:
    """Project already-validated compiler index facts into a stable inventory."""

    entries = tuple(
        sorted(
            (
                CallPreconditionAuditEntry(
                    caller=item.caller,
                    callee=item.callee,
                    condition=item.condition,
                    disposition=item.disposition,
                    path=item.span.path,
                    line=item.span.line,
                    column=item.span.column,
                )
                for items in index.primitive_call_preconditions.values()
                for item in items
            ),
            key=_entry_sort_key,
        )
    )
    return CallPreconditionAudit(entries)


def audit_call_preconditions(
    source_paths: Iterable[Path | str],
    *,
    backends: Iterable[str] | None = None,
) -> tuple[CallPreconditionAudit | None, tuple[Diagnostic, ...]]:
    """Validate a corpus and return its exact authored call-proof inventory."""

    checked = check_catalog(
        source_paths,
        backends=(
            tuple(backends) if backends is not None else registered_backend_ids()
        ),
    )
    if checked.index is None or has_errors(checked.diagnostics):
        return None, checked.diagnostics
    return build_call_precondition_audit(checked.index), checked.diagnostics


def serialize_call_precondition_audit(
    audit: CallPreconditionAudit,
    *,
    root: Path | None = None,
) -> str:
    """Serialize a portable, versioned JSON report without re-deriving facts."""

    display_root = (root or Path.cwd()).resolve()
    counts = audit.disposition_counts
    payload = {
        "schema_version": CALL_PRECONDITION_AUDIT_SCHEMA_VERSION,
        "summary": {
            "dispositions": len(audit.entries),
            "forward": counts["forward"],
            "discharge": counts["discharge"],
            "unresolved": 0,
        },
        "entries": [
            {
                "caller": entry.caller,
                "callee": entry.callee,
                "condition": entry.condition,
                "disposition": entry.disposition,
                "source": {
                    "path": _display_path(entry.path, display_root),
                    "line": entry.line,
                    "column": entry.column,
                },
            }
            for entry in audit.entries
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def render_call_precondition_audit(
    audit: CallPreconditionAudit,
    *,
    root: Path | None = None,
) -> str:
    """Render a concise source-located human-readable report."""

    display_root = (root or Path.cwd()).resolve()
    counts = audit.disposition_counts
    lines = [
        f"call-precondition audit schema {CALL_PRECONDITION_AUDIT_SCHEMA_VERSION}",
        f"dispositions: {len(audit.entries)}",
        f"forward: {counts['forward']}",
        f"discharge: {counts['discharge']}",
        "unresolved: 0",
    ]
    lines.extend(
        (
            f"{entry.caller} -> {entry.callee}.{entry.condition}: "
            f"{entry.disposition} "
            f"({_display_path(entry.path, display_root)}:{entry.line}:{entry.column})"
        )
        for entry in audit.entries
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc audit call-preconditions",
        description=(
            "Validate and report source-authored primitive-call precondition proofs."
        ),
    )
    parser.add_argument("--sources", nargs="+", required=True)
    parser.add_argument("--backends", default=None)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    audit, diagnostics = audit_call_preconditions(
        tuple(Path(value) for value in args.sources),
        backends=(
            tuple(split_csv(args.backends)) if args.backends is not None else None
        ),
    )
    for diagnostic in diagnostics:
        print(format_diagnostic(diagnostic), file=sys.stderr)
    if audit is None:
        return 1
    rendered = (
        serialize_call_precondition_audit(audit)
        if args.format == "json"
        else render_call_precondition_audit(audit)
    )
    print(rendered, end="")
    return 0


def _entry_sort_key(
    entry: CallPreconditionAuditEntry,
) -> tuple[str, str, str, str, str, int, int]:
    return (
        entry.caller,
        entry.callee,
        entry.condition,
        entry.disposition,
        entry.path.as_posix(),
        entry.line,
        entry.column,
    )


def _display_path(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


__all__ = (
    "CALL_PRECONDITION_AUDIT_SCHEMA_VERSION",
    "CallPreconditionAudit",
    "CallPreconditionAuditEntry",
    "audit_call_preconditions",
    "build_call_precondition_audit",
    "render_call_precondition_audit",
    "serialize_call_precondition_audit",
)


if __name__ == "__main__":
    raise SystemExit(main())
