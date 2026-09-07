#!/usr/bin/env python3
"""Freeze the TSL v1 checked-API policy and its current safety evidence.

This is a repository maintenance projection.  Runtime-failure spellings in
render assets are scanned only to make existing generated behavior reviewable;
they are never used by selection, lowering, or backend API planning.  Public
caller-safety paths come from the typed catalog.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from tslc.backend.rust_facade_public_declarations import (
    rust_facade_core_declaration_owners,
)
from tslc.catalog.model import Catalog, Primitive
from tslc.diagnostics import format_diagnostic, has_errors
from tslc.maintenance import _repo_context
from tslc.maintenance._catalog import load_repository_catalog
from tslc.maintenance._repo_context import RepoContext
from tslc.maintenance.checked_api_census_policy import (
    ABI_EVIDENCE,
    BASELINE_VERSION,
    CPP_DECLARATIONS,
    FAMILIES,
    FAMILY_BY_ID,
    POLICY,
    RUST_DECLARATIONS,
    VALIDATION_LIMITS,
)
from tslc.maintenance.metadata_audit import audit_metadata


_RUNTIME_PATTERN = re.compile(
    r"(?P<debug_assert>\bdebug_assert!\s*\()"
    r"|(?P<assert_eq>\bassert_eq!\s*\()"
    r"|(?P<assert>\bassert!\s*\()"
    r"|(?P<panic>\bpanic!\s*\()"
    r"|(?P<unreachable>\bunreachable!\s*\()"
    r"|(?P<unimplemented>\bunimplemented!\s*\()"
    r"|(?P<expect>\.expect\s*\()"
    r"|(?P<unwrap>\.unwrap\s*\()"
    r"|(?P<trap>\b__builtin_trap\s*\()"
    r"|(?P<throw>\bthrow\b)"
)
_TOOLING_PATH_MARKERS = (
    "benchmark",
    "value_tests",
    "rust_build.rs",
    "rust_dispatch_external_test",
    "rust_smoke.rs",
    "tsl_rust_policy",
    "tsl_rust_variant_policy_validation",
    "rust_documentation_api.py",
)


@dataclass(frozen=True, slots=True)
class RuntimeSite:
    identity: str
    path: str
    owner: str
    line: int
    kind: str
    excerpt: str
    family_id: str


@dataclass(frozen=True, slots=True)
class CallerUnsafePath:
    identity: str
    name: str
    signature: str
    attributes: tuple[tuple[str, str], ...]
    result_target: tuple[str, ...]
    reasons: tuple[str, ...]
    implementation_count: int
    family_id: str
    checked_source_status: str
    preconditions: tuple[str, ...]
    checked_coverage_reason: str


@dataclass(frozen=True, slots=True)
class MetadataGap:
    identity: str
    path: str
    line: int
    subject: str
    caller_unsafe_required: bool
    after: str


@dataclass(frozen=True, slots=True)
class Census:
    runtime_sites: tuple[RuntimeSite, ...]
    caller_unsafe_paths: tuple[CallerUnsafePath, ...]
    metadata_gaps: tuple[MetadataGap, ...]
    declaration_digests: tuple[tuple[str, str], ...]


def canonical_baseline_path(context: RepoContext) -> Path:
    return context.coverage_root / "checked-api-census.json"


def canonical_report_path(context: RepoContext) -> Path:
    return context.root / "research" / "tsl-v1-checked-api-census.md"


def build_census(context: RepoContext) -> Census:
    catalog = load_repository_catalog(context, purpose="checked-API census")
    return Census(
        runtime_sites=_runtime_sites(context),
        caller_unsafe_paths=_caller_unsafe_paths(catalog),
        metadata_gaps=_metadata_gaps(context),
        declaration_digests=tuple(
            (path.as_posix(), _digest_file(context.root / path))
            for path in (CPP_DECLARATIONS, RUST_DECLARATIONS)
        ),
    )

def _runtime_sites(context: RepoContext) -> tuple[RuntimeSite, ...]:
    source_root = context.root / "tslc" / "src" / "tslc"
    paths = tuple(
        sorted(
            (
                *(
                    path
                    for path in (source_root / "backend" / "assets").iterdir()
                    if path.is_file()
                ),
                *(
                    path
                    for directory in ("backend", "render", "benchmark", "value_tests")
                    for path in (source_root / directory).rglob("*.py")
                ),
                *context.data_root.rglob("*.tsl"),
            ),
            key=lambda path: path.as_posix(),
        )
    )
    sites: list[RuntimeSite] = []
    ordinals: Counter[tuple[str, str, str, str]] = Counter()
    rust_facade_owners = dict(rust_facade_core_declaration_owners())
    for path in paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(context.root).as_posix()
        for match in _RUNTIME_PATTERN.finditer(text):
            kind = match.lastgroup
            if kind is None:
                raise AssertionError("runtime evidence token has no kind")
            statement = _runtime_statement(text, match, python_source=path.suffix == ".py")
            normalized = " ".join(statement.split())
            owner = _nearest_owner(
                text,
                match.start(),
                python_source=path.suffix == ".py",
                template_owners=(
                    rust_facade_owners
                    if relative.endswith("backend/assets/rust_facade.rs.tmpl")
                    else None
                ),
            )
            context_start = max(0, match.start() - 320)
            context_end = min(len(text), match.end() + 320)
            classification_context = " ".join(
                text[context_start:context_end].split()
            )
            family_id = _classify_runtime_site(
                relative,
                kind,
                normalized,
                classification_context,
            )
            ordinal_key = (relative, owner, kind, normalized)
            ordinal = ordinals[ordinal_key]
            ordinals[ordinal_key] += 1
            digest = sha256(normalized.encode("utf-8")).hexdigest()[:16]
            identity = f"{relative}|{owner}|{kind}|{digest}|{ordinal}"
            sites.append(
                RuntimeSite(
                    identity=identity,
                    path=relative,
                    owner=owner,
                    line=text.count("\n", 0, match.start()) + 1,
                    kind=kind,
                    excerpt=normalized[:240],
                    family_id=family_id,
                )
            )
    return tuple(sorted(sites, key=lambda site: site.identity))


def _nearest_owner(
    text: str,
    position: int,
    *,
    python_source: bool,
    template_owners: Mapping[str, str] | None = None,
) -> str:
    prefix = text[:position]
    if python_source:
        pattern = re.compile(r"(?m)^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
        candidates = [
            (match.start(), match.group(1)) for match in pattern.finditer(prefix)
        ]
    else:
        rust_pattern = re.compile(
            r"(?m)^\s*(?:pub(?:\([^)]*\))?\s+)?(?:unsafe\s+)?"
            r"(?:const\s+)?fn\s+([A-Za-z_]\w*)\s*(?:<[^\n{]*>)?\s*\("
        )
        cpp_pattern = re.compile(
            r"(?m)^\s*(?:\[\[[^\n]+\]\]\s*)?"
            r"(?:(?:extern|inline|static|constexpr|consteval|constinit)\s+)*"
            r"(?:auto|void|bool|int|std::[A-Za-z_]\w*|[A-Za-z_]\w*(?:::\w+)*(?:<[^\n>]+>)?)"
            r"(?:\s*[*&])?\s+([A-Za-z_]\w*)\s*\("
        )
        candidates = [
            (match.start(), match.group(1))
            for match in (*rust_pattern.finditer(prefix), *cpp_pattern.finditer(prefix))
        ]
        if template_owners:
            hole_pattern = re.compile(r"@\{([A-Za-z_]\w*)\}")
            candidates.extend(
                (match.start(), template_owners[match.group(1)])
                for match in hole_pattern.finditer(prefix)
                if match.group(1) in template_owners
            )
    return max(candidates, default=(-1, "file_scope"))[1]


def _runtime_statement(text: str, match: re.Match[str], *, python_source: bool) -> str:
    if python_source:
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        return text[line_start : len(text) if line_end < 0 else line_end]
    if match.lastgroup == "throw":
        end = text.find(";", match.end())
        return text[match.start() : len(text) if end < 0 else end + 1]
    opening = text.find("(", match.start(), match.end() + 1)
    if opening < 0:
        return text[match.start() : match.end()]
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in ('"', "'"):
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                end = index + 1
                if end < len(text) and text[end] == ";":
                    end += 1
                return text[match.start() : end]
    return text[match.start() : match.end()]


def _classify_runtime_site(
    path: str,
    kind: str,
    statement: str,
    context: str,
) -> str:
    lowered_path = path.lower()
    lowered = statement.lower()
    if any(marker in lowered_path for marker in _TOOLING_PATH_MARKERS):
        return "tooling_only"
    if path.endswith("render/rust_dispatch.py"):
        return "tooling_only"
    if (
        "size_of::<from>()" in lowered
        or "lane-preserving conversion" in lowered
        or (kind == "trap" and "require_same_lanes" in context.lower())
        or "requires a vector with at least one lane" in lowered
        or "requires an integral mask storage type" in lowered
    ):
        return "static_representation_or_lane_shape"
    if "tsl_arith_integer_immediate_nonzero" in lowered or (
        path.endswith("backend/rust_signatures.py") and "const {{ assert!" in lowered
    ):
        return "static_immediate_nonzero"
    if "selected-row scale must be nonzero" in lowered:
        return "static_immediate_nonzero"
    if "unsupported scalar-as cast" in lowered or "unsupported saturating cast" in lowered:
        return "implementation_exhaustiveness"
    if kind in ("debug_assert", "unwrap", "expect"):
        return "implementation_invariant"
    if "selected row ids to be valid element indexes" in lowered:
        return "algorithm_selected_index"
    if "enough mask" in lowered:
        return "algorithm_mask_capacity"
    if "enough output" in lowered or "output slots" in lowered:
        return "algorithm_output_capacity"
    if (
        "equal length" in lowered
        or "equally sized" in lowered
        or "input and output slices" in lowered
    ):
        return "algorithm_equal_extents"
    if "source slice" in lowered or "destination slice" in lowered:
        return "contiguous_extent"
    if (
        "lane index" in lowered
        or "mask index" in lowered
        or path.endswith("render/rust_facade_comprehensive.py")
    ):
        return "lane_index"
    raise ValueError(
        f"unreviewed generated runtime failure site: {path} ({kind}): {statement[:160]}"
    )


def _caller_unsafe_paths(catalog: Catalog) -> tuple[CallerUnsafePath, ...]:
    records: list[CallerUnsafePath] = []
    for primitive in catalog.primitives:
        unsafe = tuple(
            implementation
            for implementation in primitive.implementations
            if implementation.safety.caller_unsafe
        )
        if not unsafe:
            continue
        attributes = tuple(sorted(primitive.attributes.items()))
        result_target = tuple(primitive.result_target or ())
        reasons = tuple(
            sorted(
                {
                    reason
                    for implementation in unsafe
                    for reason in implementation.safety.reasons
                }
            )
        )
        identity_payload = {
            "name": primitive.name,
            "signature": primitive.signature,
            "attributes": attributes,
            "result_target": result_target,
        }
        identity = json.dumps(identity_payload, separators=(",", ":"), sort_keys=True)
        family_id = _classify_caller_unsafe_path(primitive)
        preconditions = tuple(
            sorted(precondition.kind.value for precondition in primitive.preconditions)
        )
        records.append(
            CallerUnsafePath(
                identity=identity,
                name=primitive.name,
                signature=primitive.signature,
                attributes=attributes,
                result_target=result_target,
                reasons=reasons,
                implementation_count=len(unsafe),
                family_id=family_id,
                checked_source_status=(
                    "declared" if preconditions else "coverage_gap"
                ),
                preconditions=preconditions,
                checked_coverage_reason=(
                    "source preconditions are available for backend check planning"
                    if preconditions
                    else FAMILY_BY_ID[family_id].checked_feasibility
                ),
            )
        )
    return tuple(sorted(records, key=lambda record: record.identity))


def _classify_caller_unsafe_path(primitive: Primitive) -> str:
    name = primitive.name
    if name == "deallocate":
        return "deallocation_provenance"
    if name == "random_step":
        return "random_output_contract"
    if name == "memory_cp":
        return "raw_copy_contract"
    if name == "load_convert_up":
        return "conversion_input_contract"
    if name in ("gather", "gather_narrow", "gather_narrow_partial", "scatter"):
        return "indexed_memory_contract"
    if name in ("expand_load", "compress_store"):
        return "selected_memory_contract"
    if name in ("load_mask_repr", "store_mask_repr"):
        return "mask_memory_contract"
    if name in ("load", "load_scalar", "store"):
        return "contiguous_memory_contract"
    raise ValueError(f"unreviewed caller-unsafe public path: {name} {primitive.signature}")


def _metadata_gaps(context: RepoContext) -> tuple[MetadataGap, ...]:
    result = audit_metadata(
        (context.data_root,),
        checks=("safety",),
        machine_profiles_path=None,
        backends=("cpp", "rust"),
    )
    if has_errors(result.diagnostics):
        rendered = "\n".join(format_diagnostic(item) for item in result.diagnostics)
        raise RuntimeError(f"cannot audit safety metadata:\n{rendered}")
    gaps: list[MetadataGap] = []
    for suggestion in result.suggestions:
        if not suggestion.applicable:
            continue
        relative = suggestion.path.resolve().relative_to(context.root.resolve()).as_posix()
        after = " ".join(suggestion.after.split())
        payload = f"{relative}|{suggestion.subject}|{after}"
        gaps.append(
            MetadataGap(
                identity=sha256(payload.encode("utf-8")).hexdigest()[:20],
                path=relative,
                line=suggestion.line,
                subject=suggestion.subject,
                caller_unsafe_required="caller_unsafe true" in after,
                after=after,
            )
        )
    return tuple(sorted(gaps, key=lambda gap: (gap.path, gap.line, gap.identity)))


def serialize(census: Census) -> str:
    payload = {
        "version": BASELINE_VERSION,
        "policy": POLICY,
        "abi_evidence": ABI_EVIDENCE,
        "validation_limits": VALIDATION_LIMITS,
        "families": [
            {
                "id": family.family_id,
                "classification": family.classification,
                "backend_consequence": family.backend_consequence,
                "checked_feasibility": family.checked_feasibility,
                "review": family.review,
            }
            for family in FAMILIES
        ],
        "declaration_digests": dict(census.declaration_digests),
        "runtime_sites": [
            {
                "id": site.identity,
                "path": site.path,
                "owner": site.owner,
                "kind": site.kind,
                "excerpt": site.excerpt,
                "family": site.family_id,
            }
            for site in census.runtime_sites
        ],
        "caller_unsafe_paths": [
            {
                "id": record.identity,
                "name": record.name,
                "signature": record.signature,
                "attributes": dict(record.attributes),
                "result_target": list(record.result_target),
                "reasons": list(record.reasons),
                "implementation_count": record.implementation_count,
                "family": record.family_id,
                "checked_source_status": record.checked_source_status,
                "preconditions": list(record.preconditions),
                "checked_coverage_reason": record.checked_coverage_reason,
            }
            for record in census.caller_unsafe_paths
        ],
        "metadata_safety_gaps": [
            {
                "id": gap.identity,
                "path": gap.path,
                "subject": gap.subject,
                "caller_unsafe_required": gap.caller_unsafe_required,
                "after": gap.after,
            }
            for gap in census.metadata_gaps
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def render_markdown(census: Census, context: RepoContext) -> str:
    runtime_by_family: dict[str, list[RuntimeSite]] = defaultdict(list)
    for site in census.runtime_sites:
        runtime_by_family[site.family_id].append(site)
    unsafe_by_family: dict[str, list[CallerUnsafePath]] = defaultdict(list)
    for record in census.caller_unsafe_paths:
        unsafe_by_family[record.family_id].append(record)
    classification_counts = Counter(
        FAMILY_BY_ID[site.family_id].classification for site in census.runtime_sites
    )
    lines = [
        "# TSL v1 checked-API baseline census",
        "",
        "This generated maintenance report tracks reviewed evidence for the implemented direct TSL v1 checked-API contract. "
        "Its lexical runtime-site scan is tooling evidence only; production semantics must come from typed "
        "source/catalog facts and finalized backend plans.",
        "",
        "## Frozen public policy",
        "",
        f"- Public suffix: `{POLICY['checked_suffix']}`",
        f"- Eligibility: {POLICY['eligibility']}.",
        f"- C++ value result: {POLICY['cpp_value_result']}.",
        f"- C++ void result: {POLICY['cpp_void_result']}.",
        f"- Rust value result: `{POLICY['rust_value_result']}`.",
        f"- Rust void result: `{POLICY['rust_void_result']}`.",
        f"- Unchecked Rust: `{POLICY['unchecked_rust']}`.",
        f"- Failed C++ value result: {POLICY['failure_value']}.",
        "",
        "## Inventory summary",
        "",
        f"- Exact generated runtime-failure sites: {len(census.runtime_sites)}",
        f"- Exact typed public callable identities with at least one `caller_unsafe` implementation: {len(census.caller_unsafe_paths)}",
        "- Checked source-contract coverage gaps among those identities: "
        f"{sum(record.checked_source_status == 'coverage_gap' for record in census.caller_unsafe_paths)}",
        f"- Applicable source safety-metadata gaps: {len(census.metadata_gaps)} "
        f"({sum(gap.caller_unsafe_required for gap in census.metadata_gaps)} require caller unsafety)",
        "",
        "Runtime sites by classification:",
        "",
        *(
            f"- {classification}: {count}"
            for classification, count in sorted(classification_counts.items())
        ),
        "",
        "## Reviewed semantic families",
        "",
        "| Family | Classification | Backend consequence | Complete-check feasibility |",
        "| --- | --- | --- | --- |",
        *(
            f"| `{family.family_id}` | {family.classification} | {family.backend_consequence} | {family.checked_feasibility} |"
            for family in FAMILIES
        ),
        "",
        "## Exact generated runtime sites",
        "",
    ]
    for family in FAMILIES:
        sites = runtime_by_family.get(family.family_id, [])
        if not sites:
            continue
        lines.extend(
            (
                f"### `{family.family_id}` ({len(sites)})",
                "",
                family.review,
                "",
            )
        )
        lines.extend(
            f"- `{site.path}:{site.line}` — owner `{site.owner}` — `{site.kind}` — `{site.excerpt}`"
            for site in sites
        )
        lines.append("")
    lines.extend(
        (
            "## Typed `caller_unsafe` public paths",
            "",
            "These identities come from `Catalog` and `ImplementationSafety`, not target-text inspection. "
            "A family records whether a future checked form can be honest; it does not itself authorize generation.",
            "",
        )
    )
    for family in FAMILIES:
        records = unsafe_by_family.get(family.family_id, [])
        if not records:
            continue
        lines.extend((f"### `{family.family_id}` ({len(records)})", ""))
        for record in records:
            attrs = ", ".join(f"{key}={value}" for key, value in record.attributes) or "none"
            target = ",".join(record.result_target) or "none"
            lines.append(
                f"- `{record.name} {record.signature}`; attributes `{attrs}`; result target `{target}`; "
                f"reasons `{', '.join(record.reasons)}`; caller-unsafe implementations {record.implementation_count}; "
                f"checked source status `{record.checked_source_status}`; preconditions "
                f"`{', '.join(record.preconditions) or 'none'}`; coverage: {record.checked_coverage_reason}"
            )
        lines.extend(("", f"Review: {family.review}", ""))
    caller_gaps = tuple(gap for gap in census.metadata_gaps if gap.caller_unsafe_required)
    lines.extend(
        (
            "## Source safety-metadata completeness caveat",
            "",
            "The existing typed metadata audit finds additional direct body/signature facts whose source-owned "
            "safety metadata is incomplete. Applying those suggestions can change generated Rust safety and remains "
            "a separately reviewed corpus-hardening task. The exact gap set is locked in the JSON baseline.",
            "",
            f"The {len(caller_gaps)} caller-visible gaps are:",
            "",
            *(
                f"- `{gap.path}:{gap.line}` — {gap.subject}"
                for gap in caller_gaps
            ),
            "",
            "## Reviewed declaration-shape examples",
            "",
            "These examples record reviewed C++ and Rust contract shapes. They are not an exhaustive "
            "serialization of the emitted public surface and therefore are not an exact compatibility ratchet.",
            "",
            "### C++",
            "",
            "```cpp",
            (context.root / CPP_DECLARATIONS).read_text(encoding="utf-8").rstrip(),
            "```",
            "",
            "### Rust",
            "",
            "```rust",
            (context.root / RUST_DECLARATIONS).read_text(encoding="utf-8").rstrip(),
            "```",
            "",
            "## C++ ABI evidence",
            "",
            "The maintained probe is `tslc/tests/fixtures/checked_api/abi_probe.cpp`. It compiles "
            "with warnings as errors and its tests inspect out-of-line and optimized call-site assembly.",
            "",
            f"- Environment: {ABI_EVIDENCE['environment']}",
            f"- Compilers observed: {ABI_EVIDENCE['gcc']}; {ABI_EVIDENCE['clang']}",
            f"- MSVC: {ABI_EVIDENCE['msvc']}",
            f"- Raw return: {ABI_EVIDENCE['raw_return']}",
            f"- Chosen value-plus-error-out: {ABI_EVIDENCE['chosen_return']}",
            f"- Rejected value-owning aggregate: {ABI_EVIDENCE['aggregate_return']}",
            f"- Rejected status-plus-value-output: {ABI_EVIDENCE['status_with_value_output']}",
            f"- Optimized call site: {ABI_EVIDENCE['optimized_inline_call']}",
            "",
            "## Validation limits",
            "",
            f"- All-profile Rust render: {VALIDATION_LIMITS['all_profile_rust_render']}.",
            f"- Census strategy: {VALIDATION_LIMITS['census_strategy']}.",
            "",
            "## Maintenance",
            "",
            "Run `PYTHONPATH=tslc/src python -m tslc.maintenance.checked_api_census` to check the exact baseline and report. "
            "After reviewing an intended evidence change, pass `--update` to accept it.",
        )
    )
    return "\n".join(lines) + "\n"


def _digest_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _changed_ids(expected: Mapping[str, object], actual: Mapping[str, object], key: str) -> str:
    expected_items = expected.get(key, [])
    actual_items = actual.get(key, [])
    if not isinstance(expected_items, list) or not isinstance(actual_items, list):
        return f"{key}: malformed baseline section"
    expected_ids = {str(item.get("id")) for item in expected_items if isinstance(item, dict)}
    actual_ids = {str(item.get("id")) for item in actual_items if isinstance(item, dict)}
    added = sorted(actual_ids - expected_ids)
    removed = sorted(expected_ids - actual_ids)
    details = []
    if added:
        details.append(f"added={len(added)} ({', '.join(added[:3])})")
    if removed:
        details.append(f"removed={len(removed)} ({', '.join(removed[:3])})")
    return f"{key}: " + (", ".join(details) if details else "records changed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tslc.maintenance.checked_api_census",
        description="Check or update the frozen TSL v1 checked-API safety census.",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="baseline JSON path (default: coverage/checked-api-census.json)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Markdown report path (default: research/tsl-v1-checked-api-census.md)",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="write the reviewed current census and report",
    )
    args = parser.parse_args(argv)
    context = _repo_context.require_repo_context(parser)
    baseline_path = Path(args.baseline) if args.baseline else canonical_baseline_path(context)
    report_path = Path(args.report) if args.report else canonical_report_path(context)
    try:
        census = build_census(context)
    except (RuntimeError, ValueError) as error:
        print(f"checked-API census failed: {error}", file=sys.stderr)
        return 2
    baseline_text = serialize(census)
    report_text = render_markdown(census, context)
    if args.update:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(baseline_text, encoding="utf-8")
        report_path.write_text(report_text, encoding="utf-8")
        print(f"wrote {baseline_path}")
        print(f"wrote {report_path}")
        return 0
    if not baseline_path.is_file() or not report_path.is_file():
        print("checked-API census baseline/report is missing; review and run with --update", file=sys.stderr)
        return 2
    expected_text = baseline_path.read_text(encoding="utf-8")
    expected_report = report_path.read_text(encoding="utf-8")
    if expected_text != baseline_text or expected_report != report_text:
        print("checked-API census differs from the reviewed baseline:", file=sys.stderr)
        if expected_text != baseline_text:
            try:
                expected = json.loads(expected_text)
                actual = json.loads(baseline_text)
                for key in ("runtime_sites", "caller_unsafe_paths", "metadata_safety_gaps"):
                    if expected.get(key) != actual.get(key):
                        print(f"  {_changed_ids(expected, actual, key)}", file=sys.stderr)
            except json.JSONDecodeError:
                print("  baseline JSON is malformed", file=sys.stderr)
        if expected_report != report_text:
            print("  Markdown report changed", file=sys.stderr)
        print("review the change, then accept it with --update", file=sys.stderr)
        return 1
    print(
        "checked-API census OK: "
        f"{len(census.runtime_sites)} runtime sites, "
        f"{len(census.caller_unsafe_paths)} caller-unsafe paths, "
        f"{len(census.metadata_gaps)} metadata gaps"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
