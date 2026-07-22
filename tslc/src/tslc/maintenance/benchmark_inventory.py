"""Deterministic corpus-shape inventory for implementation-variant benchmarks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tslc.catalog.model import (
    BOOLEAN_WILDCARD_ATTRIBUTES,
    Catalog,
    Primitive,
)
from tslc.catalog.signatures import parse_signature

if TYPE_CHECKING:
    from tslc.maintenance.benchmark_coverage import BenchmarkCoverageAudit

BenchmarkInventoryStatus = Literal["benchmarked", "gap", "not applicable"]


@dataclass(frozen=True, slots=True)
class SourceShapeKey:
    """Structural identity shared by authored and lowered primitive shapes."""

    primitive_name: str
    result_kind: str
    param_kinds: tuple[str, ...]
    mask_policy: str | None

    def sort_key(self) -> tuple[object, ...]:
        return (
            self.primitive_name,
            self.result_kind,
            self.param_kinds,
            self.mask_policy or "",
        )


@dataclass(frozen=True, slots=True)
class BenchmarkShapeInventoryEntry:
    signature: str
    declarations: int
    variant_declarations: int
    variant_implementation_leaves: int
    authored_variants: int
    selected_slots: int
    candidate_sets: int
    status: BenchmarkInventoryStatus
    policy_supported_reports: int = 0
    policy_report_only_reports: int = 0


@dataclass(frozen=True, slots=True)
class BenchmarkSpecialCaseInventoryEntry:
    name: str
    declarations: int
    variant_declarations: int
    selected_slots: int
    candidate_sets: int
    status: BenchmarkInventoryStatus


def build_shape_inventory(
    primitives: tuple[Primitive, ...],
    selected_by_shape: dict[SourceShapeKey, int],
    candidates_by_shape: dict[SourceShapeKey, int],
    issue_shapes: set[SourceShapeKey],
    *,
    policy_supported_by_shape: dict[SourceShapeKey, int] | None = None,
    policy_report_only_by_shape: dict[SourceShapeKey, int] | None = None,
) -> tuple[BenchmarkShapeInventoryEntry, ...]:
    supported = {} if policy_supported_by_shape is None else policy_supported_by_shape
    report_only = (
        {} if policy_report_only_by_shape is None else policy_report_only_by_shape
    )
    by_signature: dict[str, list[Primitive]] = defaultdict(list)
    for primitive in primitives:
        by_signature[primitive.signature].append(primitive)
    entries: list[BenchmarkShapeInventoryEntry] = []
    for signature in sorted(by_signature):
        declarations = by_signature[signature]
        variant_declarations = tuple(
            primitive for primitive in declarations if has_variants(primitive)
        )
        variant_shapes = {
            source_shape(primitive) for primitive in variant_declarations
        }
        entries.append(
            BenchmarkShapeInventoryEntry(
                signature=signature,
                declarations=len(declarations),
                variant_declarations=len(variant_declarations),
                variant_implementation_leaves=sum(
                    sum(
                        bool(implementation.variants)
                        for implementation in primitive.implementations
                    )
                    for primitive in variant_declarations
                ),
                authored_variants=sum(
                    sum(
                        len(implementation.variants)
                        for implementation in primitive.implementations
                    )
                    for primitive in variant_declarations
                ),
                selected_slots=sum(
                    selected_by_shape[shape] for shape in variant_shapes
                ),
                candidate_sets=sum(
                    candidates_by_shape[shape] for shape in variant_shapes
                ),
                status=_inventory_status(variant_shapes, issue_shapes),
                policy_supported_reports=sum(
                    supported.get(shape, 0) for shape in variant_shapes
                ),
                policy_report_only_reports=sum(
                    report_only.get(shape, 0) for shape in variant_shapes
                ),
            )
        )
    return tuple(entries)


def build_special_case_inventory(
    catalog: Catalog,
    primitives: tuple[Primitive, ...],
    selected_by_shape: dict[SourceShapeKey, int],
    candidates_by_shape: dict[SourceShapeKey, int],
    issue_shapes: set[SourceShapeKey],
    *,
    backend_id: str = "cpp",
) -> tuple[BenchmarkSpecialCaseInventoryEntry, ...]:
    masked = lambda primitive: "mask" in primitive.attribute_keys
    representation_change = lambda primitive: primitive.result_target is not None
    cross_lane = lambda primitive: primitive.cross_lane
    caller_unsafe = lambda primitive: any(
        implementation.safety.caller_unsafe
        for implementation in primitive.implementations
    )
    immediate = lambda primitive: (
        (shape := parse_signature(primitive.signature)) is not None
        and "sImm" in shape.param_kinds
    )
    lane_list = lambda primitive: (
        (shape := parse_signature(primitive.signature)) is not None
        and any(kind.startswith("lanes<") for kind in shape.param_kinds)
    )
    generic_simd_type = lambda primitive: any(
        parameter.kind == "simd_type" for parameter in primitive.generic_params
    )
    boolean_axis = lambda primitive: bool(
        set(primitive.attribute_keys) & BOOLEAN_WILDCARD_ATTRIBUTES
    )
    opt_in_header = lambda primitive: _uses_opt_in_header(
        catalog, primitive, backend_id=backend_id
    )
    cases: tuple[
        tuple[
            str,
            Callable[[Primitive], bool],
            Callable[[Primitive], bool],
        ],
        ...,
    ] = (
        ("masked primitive", masked, _with_variants(masked)),
        (
            "representation-changing result",
            representation_change,
            _with_variants(representation_change),
        ),
        ("cross-lane semantics", cross_lane, _with_variants(cross_lane)),
        (
            "caller-unsafe implementation",
            caller_unsafe,
            lambda primitive: any(
                implementation.variants
                and implementation.safety.caller_unsafe
                for implementation in primitive.implementations
            ),
        ),
        (
            "compile-time immediate operand",
            immediate,
            _with_variants(immediate),
        ),
        ("lane-list operand", lane_list, _with_variants(lane_list)),
        (
            "generic SIMD-type parameter",
            generic_simd_type,
            _with_variants(generic_simd_type),
        ),
        (
            "boolean attribute axis",
            boolean_axis,
            _with_variants(boolean_axis),
        ),
        (
            "sized-vector implementation",
            lambda primitive: _uses_extension_kind(catalog, primitive, "sized"),
            lambda primitive: _uses_extension_kind(
                catalog,
                primitive,
                "sized",
                variants_only=True,
            ),
        ),
        (
            "scalable-vector implementation",
            lambda primitive: _uses_extension_kind(
                catalog,
                primitive,
                "scalable",
            ),
            lambda primitive: _uses_extension_kind(
                catalog,
                primitive,
                "scalable",
                variants_only=True,
            ),
        ),
        (
            "opt-in compiler header implementation",
            opt_in_header,
            lambda primitive: _uses_opt_in_header(
                catalog,
                primitive,
                backend_id=backend_id,
                variants_only=True,
            ),
        ),
    )
    entries: list[BenchmarkSpecialCaseInventoryEntry] = []
    for name, declaration_predicate, variant_predicate in cases:
        declarations = tuple(
            primitive
            for primitive in primitives
            if declaration_predicate(primitive)
        )
        variant_declarations = tuple(
            primitive for primitive in declarations if variant_predicate(primitive)
        )
        shapes = {
            source_shape(primitive) for primitive in variant_declarations
        }
        entries.append(
            BenchmarkSpecialCaseInventoryEntry(
                name=name,
                declarations=len(declarations),
                variant_declarations=len(variant_declarations),
                selected_slots=sum(selected_by_shape[shape] for shape in shapes),
                candidate_sets=sum(candidates_by_shape[shape] for shape in shapes),
                status=_inventory_status(shapes, issue_shapes),
            )
        )
    return tuple(entries)


def render_benchmark_shape_inventory(audit: BenchmarkCoverageAudit) -> str:
    """Render deterministic backend-scoped aggregate coverage evidence."""

    if audit.backend_id == "cpp":
        return _render_cpp_benchmark_shape_inventory(audit)
    return _render_backend_benchmark_shape_inventory(audit)


def _render_cpp_benchmark_shape_inventory(audit: BenchmarkCoverageAudit) -> str:
    """Keep the committed C++ inventory byte-compatible."""

    shape_counts = {
        status: 0 for status in ("benchmarked", "gap", "not applicable")
    }
    for shape_entry in audit.shapes:
        shape_counts[shape_entry.status] += 1
    lines = [
        "# Benchmark Shape Inventory",
        "",
        "Generated by `tslc.maintenance.benchmark_coverage`. **Regenerate** with",
        "`./dev.sh benchmark-ratchet --update`; do not hand-edit.",
        "",
        "This inventory is holistic over the current TSL corpus without inventing",
        "timing semantics for default-only primitives. Every authored",
        "implementation-variant shape is tracked through the selected-slot →",
        "correctness → typed-scenario → emitted-candidate funnel. The committed",
        "issue baseline rejects newly introduced gaps while known gaps can be closed",
        "incrementally. Shapes with no authored variants are explicitly **not",
        "applicable**.",
        "",
        "## Summary",
        "",
        f"- **{len(audit.profiles)} C++ machine profiles** are probed.",
        f"- **{audit.selected_slots} selected variant slots** are accounted for.",
        f"- **{audit.candidate_sets} candidate sets** are emitted; compile-time "
        "immediate cases may fan one slot out into several sets.",
        f"- **{shape_counts['benchmarked']} signature shapes benchmarked**, "
        f"**{shape_counts['not applicable']} not applicable**, "
        f"**{shape_counts['gap']} gaps**.",
        f"- **{len(audit.issues)} strict audit issues**.",
        "",
        "## Signature shapes",
        "",
        "| Signature | Declarations | Variant declarations | Variant impl leaves | "
        "Authored variants | Selected slots | Candidate sets | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for shape_entry in audit.shapes:
        lines.append(
            f"| `{shape_entry.signature}` | {shape_entry.declarations} | "
            f"{shape_entry.variant_declarations} | "
            f"{shape_entry.variant_implementation_leaves} | "
            f"{shape_entry.authored_variants} | {shape_entry.selected_slots} | "
            f"{shape_entry.candidate_sets} | {shape_entry.status} |"
        )
    lines.extend(
        (
            "",
            "## Special cases",
            "",
            "These rows make planner-sensitive corpus facts visible even when the",
            "current special case has no authored variants and therefore needs no",
            "benchmark workload.",
            "",
            "| Special case | Declarations | Variant declarations | Selected slots | "
            "Candidate sets | Status |",
            "|---|---:|---:|---:|---:|---|",
        )
    )
    for special_case_entry in audit.special_cases:
        lines.append(
            f"| {special_case_entry.name} | {special_case_entry.declarations} | "
            f"{special_case_entry.variant_declarations} | "
            f"{special_case_entry.selected_slots} | "
            f"{special_case_entry.candidate_sets} | {special_case_entry.status} |"
        )
    if audit.issues:
        issue_counts: dict[str, int] = defaultdict(int)
        for issue in audit.issues:
            issue_counts[issue.kind] += 1
        lines.extend(
            (
                "",
                "## Audit issue counts",
                "",
                "Exact stable issue identities are stored in",
                "`coverage/benchmark-baseline.json`.",
                "",
                "| Kind | Count |",
                "|---|---:|",
            )
        )
        for kind, count in sorted(issue_counts.items()):
            lines.append(f"| `{kind}` | {count} |")
    return "\n".join(lines) + "\n"


def _render_backend_benchmark_shape_inventory(
    audit: BenchmarkCoverageAudit,
) -> str:
    shape_counts = {
        status: 0 for status in ("benchmarked", "gap", "not applicable")
    }
    for shape_entry in audit.shapes:
        shape_counts[shape_entry.status] += 1
    backend_label = "Rust" if audit.backend_id == "rust" else audit.backend_id
    baseline_name = f"benchmark-{audit.backend_id}-baseline.json"
    update_command = (
        f"./dev.sh benchmark-ratchet --backend {audit.backend_id} --update"
    )
    lines = [
        f"# {backend_label} Benchmark Shape Inventory",
        "",
        "Generated by `tslc.maintenance.benchmark_coverage`. **Regenerate** with",
        f"`{update_command}`; do not hand-edit.",
        "",
        f"This inventory is scoped only to the **{backend_label}** backend. Report",
        "coverage and compile-time policy eligibility are independent: an emitted",
        "report may remain intentionally report-only. Exact gap memberships, profile",
        "manifest hashes, candidate IDs/body hashes, and policy mapping hashes live in",
        f"`coverage/{baseline_name}`.",
        "",
        "## Summary",
        "",
        f"- **{len(audit.profiles)} {backend_label} machine profiles** are probed.",
        f"- **{audit.selected_slots} selected variant slots** are accounted for.",
        f"- **{audit.candidate_sets} benchmark reports** are emitted.",
        f"- **Policy-mapped reports: {audit.policy_supported_reports}**; "
        f"**report-only: {audit.policy_report_only_reports}**.",
        f"- **{shape_counts['benchmarked']} signature shapes benchmarked**, "
        f"**{shape_counts['not applicable']} not applicable**, "
        f"**{shape_counts['gap']} gaps**.",
        f"- **{len(audit.issues)} strict audit issues**.",
        "",
        "## Signature shapes",
        "",
        "| Signature | Declarations | Variant declarations | Variant impl leaves | "
        "Authored variants | Selected slots | Reports | Policy mapped | "
        "Report-only | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for entry in audit.shapes:
        lines.append(
            f"| `{entry.signature}` | {entry.declarations} | "
            f"{entry.variant_declarations} | "
            f"{entry.variant_implementation_leaves} | "
            f"{entry.authored_variants} | {entry.selected_slots} | "
            f"{entry.candidate_sets} | {entry.policy_supported_reports} | "
            f"{entry.policy_report_only_reports} | {entry.status} |"
        )
    lines.extend(
        (
            "",
            "## Special cases",
            "",
            "| Special case | Declarations | Variant declarations | Selected slots | "
            "Reports | Status |",
            "|---|---:|---:|---:|---:|---|",
        )
    )
    for special_case in audit.special_cases:
        lines.append(
            f"| {special_case.name} | {special_case.declarations} | "
            f"{special_case.variant_declarations} | {special_case.selected_slots} | "
            f"{special_case.candidate_sets} | {special_case.status} |"
        )
    if audit.issues:
        issue_counts: dict[str, int] = defaultdict(int)
        for issue in audit.issues:
            issue_counts[issue.kind] += 1
        lines.extend(
            (
                "",
                "## Audit issue counts",
                "",
                "| Kind | Count |",
                "|---|---:|",
            )
        )
        for kind, count in sorted(issue_counts.items()):
            lines.append(f"| `{kind}` | {count} |")
    return "\n".join(lines) + "\n"


def has_variants(primitive: Primitive) -> bool:
    return any(implementation.variants for implementation in primitive.implementations)


def source_shape(primitive: Primitive) -> SourceShapeKey:
    shape = parse_signature(primitive.signature)
    if shape is None:
        raise ValueError(
            f"catalog primitive {primitive.name!r} has invalid signature "
            f"{primitive.signature!r}"
        )
    return SourceShapeKey(
        primitive_name=primitive.name,
        result_kind=shape.result_kind,
        param_kinds=shape.param_kinds,
        mask_policy=primitive.attributes.get("mask"),
    )


def shape_label(shape: SourceShapeKey) -> str:
    params = ",".join(shape.param_kinds)
    signature = (
        f"{shape.result_kind}:={params}"
        if len(shape.param_kinds) == 1
        else f"{shape.result_kind}:=({params})"
    )
    mask = "" if shape.mask_policy is None else f" [mask={shape.mask_policy}]"
    return f"{shape.primitive_name} {signature}{mask}"


def _inventory_status(
    variant_shapes: set[SourceShapeKey],
    issue_shapes: set[SourceShapeKey],
) -> BenchmarkInventoryStatus:
    if not variant_shapes:
        return "not applicable"
    if variant_shapes & issue_shapes:
        return "gap"
    return "benchmarked"


def _uses_extension_kind(
    catalog: Catalog,
    primitive: Primitive,
    vector_bits_kind: str,
    *,
    variants_only: bool = False,
) -> bool:
    return any(
        (not variants_only or implementation.variants)
        and (extension := catalog.extensions.get(implementation.extension)) is not None
        and extension.vector_bits_kind == vector_bits_kind
        for implementation in primitive.implementations
    )


def _uses_opt_in_header(
    catalog: Catalog,
    primitive: Primitive,
    *,
    backend_id: str = "cpp",
    variants_only: bool = False,
) -> bool:
    return any(
        (not variants_only or implementation.variants)
        and (extension := catalog.extensions.get(implementation.extension)) is not None
        and extension.header_group_for_backend(backend_id) is not None
        for implementation in primitive.implementations
    )


def _with_variants(
    predicate: Callable[[Primitive], bool],
) -> Callable[[Primitive], bool]:
    return lambda primitive: predicate(primitive) and has_variants(primitive)


__all__ = (
    "BenchmarkInventoryStatus",
    "BenchmarkShapeInventoryEntry",
    "BenchmarkSpecialCaseInventoryEntry",
    "SourceShapeKey",
    "build_shape_inventory",
    "build_special_case_inventory",
    "has_variants",
    "render_benchmark_shape_inventory",
    "shape_label",
    "source_shape",
)
