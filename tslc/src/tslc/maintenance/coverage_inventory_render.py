"""Deterministic text, Markdown, and JSON coverage-inventory rendering."""

from __future__ import annotations

from collections.abc import Callable
import json

from tslc.maintenance.coverage_inventory_report import (
    BackendProfileInventory,
    CoverageInventory,
)


_CATEGORY_NOTES = {
    "pruned (closure)": (
        "Dependency-closure dropped a body whose callee is unavailable in that "
        "profile. **Structural, not a defect** — expected behavior."
    ),
    "generic-vector repr-change (deferred)": (
        "`cast`/`reinterpret` on the `simd<T, generic<LANES>>` vector "
        "(LANES-sized target). Known deferred slice."
    ),
    "unresolved type query": (
        "A `type(...)` query is not yet evaluated (e.g. "
        "`vector::offset_base`, `vector::mask_underlying_t`, `vector::transform(...)`). "
        "See the per-primitive table for current owners."
    ),
    "unresolved value query": (
        "A `value(...)` query is not yet evaluated (e.g. "
        "`type::size_bytes(...)`). Blocks to_integral/to_mask generic paths "
        "and arithmetic fallback bodies."
    ),
    "unresolved cast type": (
        "A typed cast target could not be resolved before backend rendering."
    ),
    "no top-level complete": (
        "Body has no top-level `complete(...)` (where-clause / switch-bodied "
        "forms) — not lowerable yet; see the per-primitive table for current "
        "owners."
    ),
    "call type-args (bare-ext/index)": (
        "Unsupported `call<primitive=...>[...]` type-argument shape. Simple vector "
        "aliases, extension names, and decimal index constants are supported."
    ),
    "unsupported mask<test>": (
        "`mask<test>` on the `native_predicate_by_lanes` (avx512 `__mmaskN`) "
        "representation."
    ),
    "unsupported signature kind": (
        "Unsupported signature kind: variadic `set` (`v:=s...`) and `to_ostream` "
        "(`o:=(o,v,s)`)."
    ),
    "policy-deferred scalable signature": (
        "Selected scalable-vector slot whose fixed-lane `s[]` or `lanes<s>` "
        "signature is intentionally deferred until the typed scalable array/"
        "lane-list contract is designed."
    ),
}


def render_text(inventory: CoverageInventory) -> str:
    lines = [
        "TSLC coverage inventory",
        "",
        f"Profiles: {', '.join(inventory.profiles)}",
        f"Backends: {', '.join(inventory.backends)}",
        f"Types: {', '.join(inventory.type_tags)}",
        "",
        f"Distinct primitives: {inventory.primitive_count}",
        f"Primitive declarations: {inventory.primitive_declarations}",
        f"Distinct primitive signatures: {inventory.signature_count}",
        f"Catalog implementation leaves: {inventory.implementation_count}",
        f"Emitted specializations: {inventory.emitted_specializations}",
        (
            "Average emitted specializations / primitive: "
            f"{inventory.average_specializations_per_primitive:.2f}"
        ),
        f"Aggregate specialization coverage: {inventory.aggregate_coverage_percent:.1f}%",
        f"Mean primitive coverage: {inventory.mean_primitive_coverage_percent:.1f}%",
        f"Coverage-gap slots: {inventory.coverage_gaps}",
        f"Policy-deferred slots: {inventory.policy_deferred}",
        f"Build-verified primitives: {inventory.build_verified_primitives}",
        (
            "Backend specialization parity: "
            f"{'exact' if inventory.backend_parity else 'not exact'}"
        ),
        "",
        "Profile/backend specialization coverage",
        (
            "Each cell is emitted/shared candidates. The denominator is the profile-wide "
            "union across selected backends; — means the backend attempted no slot."
        ),
        "",
    ]
    headers = ("profile", *(_backend_label(item) for item in inventory.backends))
    rows = tuple(
        (profile.profile, *(_cell_text(cell) for cell in profile.backends))
        for profile in inventory.profile_inventory
    )
    lines.extend(_text_table(headers, rows))
    return "\n".join(lines) + "\n"


def render_json(inventory: CoverageInventory) -> str:
    payload = {
        "scope": {
            "profiles": list(inventory.profiles),
            "backends": list(inventory.backends),
            "types": list(inventory.type_tags),
        },
        "corpus": {
            "primitives": inventory.primitive_count,
            "primitive_declarations": inventory.primitive_declarations,
            "primitive_signatures": inventory.signature_count,
            "implementation_leaves": inventory.implementation_count,
        },
        "specializations": {
            "emitted": inventory.emitted_specializations,
            "average_per_primitive": round(
                inventory.average_specializations_per_primitive, 6
            ),
            "aggregate_coverage_percent": round(
                inventory.aggregate_coverage_percent, 6
            ),
            "mean_primitive_coverage_percent": round(
                inventory.mean_primitive_coverage_percent, 6
            ),
            "coverage_gaps": inventory.coverage_gaps,
            "policy_deferred": inventory.policy_deferred,
        },
        "build_verified_primitives": inventory.build_verified_primitives,
        "backend_parity": inventory.backend_parity,
        "profiles": [
            {
                "profile": profile.profile,
                "shared_candidates": profile.shared_candidates,
                "backends": [
                    {
                        "backend": cell.backend,
                        "emitted": cell.emitted,
                        "attempted": cell.attempted,
                        "shared_candidates": cell.shared_candidates,
                        "coverage_gaps": cell.coverage_gaps,
                        "policy_deferred": cell.policy_deferred,
                        "coverage_percent": _rounded(cell.coverage_percent),
                        "lowering_success_percent": _rounded(
                            cell.lowering_success_percent
                        ),
                    }
                    for cell in profile.backends
                ],
            }
            for profile in inventory.profile_inventory
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(
    inventory: CoverageInventory, *, tracked: bool = False
) -> str:
    by_status = {
        status: tuple(
            primitive.name
            for primitive in inventory.primitives
            if primitive.status == status
        )
        for status in ("VERIFIED", "lowers", "partial", "NONE")
    }
    backend_label = "/".join(_backend_label(item) for item in inventory.backends)
    lines: list[str] = []
    write = lines.append
    write("# Primitive Coverage Inventory\n")
    if tracked:
        write("Generated by `tslc coverage inventory --update`; do not hand-edit.\n")
    else:
        write("Generated by `tslc coverage inventory --format markdown`.\n")
    write("## Summary\n")
    write(f"- **{inventory.primitive_count} distinct primitives** in the corpus.")
    write(
        f"- **{inventory.primitive_declarations} primitive declarations**, "
        f"**{inventory.signature_count} distinct primitive signatures**, and "
        f"**{inventory.implementation_count} catalog implementation leaves**."
    )
    write(
        f"- **{inventory.emitted_specializations} emitted specializations**; "
        f"**{inventory.average_specializations_per_primitive:.2f} per primitive** "
        "on average."
    )
    write(
        f"- **{inventory.aggregate_coverage_percent:.1f}% aggregate specialization "
        f"coverage**; **{inventory.mean_primitive_coverage_percent:.1f}% mean "
        "primitive coverage**."
    )
    write(
        f"- **{inventory.build_verified_primitives} build-verified** "
        f"(compile in {backend_label} via `tslc/tests/test_build_verify.py`)."
    )
    write(
        f"- **{len(by_status['lowers'])} lower cleanly but are not build-verified**, "
        f"**{len(by_status['partial'])} partial**, and **{len(by_status['NONE'])} "
        "emit nothing** under the probed profiles."
    )
    write(
        f"- **{inventory.coverage_gaps} coverage-gap slots** and "
        f"**{inventory.policy_deferred} policy-deferred slots**."
    )
    parity = "exact" if inventory.backend_parity else "not exact"
    write(
        f"- **{backend_label} specialization parity is {parity}** across the "
        "probed profiles.\n"
    )
    write(
        "Coverage percentages use the profile-wide union of logical specialization "
        "candidates across selected backends. This makes backend availability "
        "differences visible instead of giving each backend a smaller private denominator.\n"
    )
    write(
        "Aggregate coverage weights every shared candidate; mean primitive coverage "
        "weights every distinct corpus primitive equally.\n"
    )
    write(
        "> Caveat: emitted means selection, lowering, dependency closure, and emitted-name "
        "finalization succeeded; it is *not* a compile guarantee. Only **VERIFIED** "
        "primitives are confirmed to compile. The probe uses types "
        f"`{', '.join(inventory.type_tags)}` across profiles "
        f"`{', '.join(inventory.profiles)}`.\n"
    )

    write("## Profile/backend specialization coverage\n")
    write(
        "Each cell is `emitted / shared candidates (coverage)`. `—` means that "
        "backend attempted no specialization for the profile. Candidates deferred by "
        "every selected backend are excluded; deferred counts remain separately visible.\n"
    )
    write(
        "| profile | "
        + " | ".join(_backend_label(item) for item in inventory.backends)
        + " |"
    )
    write("|---|" + "---:|" * len(inventory.backends))
    for profile in inventory.profile_inventory:
        write(
            f"| `{profile.profile}` | "
            + " | ".join(_cell_text(cell) for cell in profile.backends)
            + " |"
        )
    write("")

    write("## Tiers\n")
    _write_tier(
        write,
        "Build-verified",
        by_status["VERIFIED"],
        f"compile in {backend_label}",
    )
    _write_tier(
        write,
        "Lower but not build-verified",
        by_status["lowers"],
        "lowering clean, compilation unconfirmed",
    )
    _write_tier(
        write,
        "Partial",
        by_status["partial"],
        "some slots lower, some skip",
    )
    _write_tier(write, "Emit nothing", by_status["NONE"], "no emitted slots")

    write("## Per-primitive table\n")
    write(
        "| primitive | signatures | status | coverage | emitted | extensions by "
        "backend | skipped slots | dominant gap |"
    )
    write("|---|---|---|---:|---:|---|---:|---|")
    for primitive in inventory.primitives:
        signatures = " ".join(f"`{item}`" for item in primitive.signatures)
        extensions = "; ".join(
            f"{backend}=" + ("/".join(names) or "—")
            for backend, names in primitive.extensions_by_backend
        )
        write(
            f"| `{primitive.name}` | {signatures} | {primitive.status} | "
            f"{primitive.coverage_percent:.1f}% | {primitive.emitted} | {extensions} | "
            f"{primitive.skipped} | {primitive.dominant_gap or '—'} |"
        )
    write("")

    write("## Skip-reason taxonomy (what blocks the gaps)\n")
    write(
        "> Skip counts are candidate specialization slots, not primitives. A primitive "
        "can be **VERIFIED** while another profile/type/extension variant is pruned or "
        "deferred.\n"
    )
    write("| skips | category | meaning / action |")
    write("|--:|---|---|")
    for category, count in inventory.skip_reasons:
        write(f"| {count} | {category} | {_CATEGORY_NOTES.get(category, '')} |")
    write("")
    write("### NONE primitives — why nothing emits\n")
    none = tuple(
        primitive for primitive in inventory.primitives if primitive.status == "NONE"
    )
    if not none:
        write(
            "No primitives are currently in the NONE tier; every primitive emits at "
            "least one slot under the probed profiles.\n"
        )
    else:
        for primitive in none:
            signatures = " ".join(f"`{item}`" for item in primitive.signatures)
            suffix = (
                f": {primitive.dominant_gap}."
                if primitive.dominant_gap is not None
                else "."
            )
            write(f"- `{primitive.name}` ({signatures}){suffix}")
        write("")
    return "\n".join(lines)


def _backend_label(backend: str) -> str:
    return {"cpp": "C++", "rust": "Rust"}.get(backend, backend)


def _cell_text(cell: BackendProfileInventory) -> str:
    if not cell.applicable:
        suffix = f" ({cell.policy_deferred} deferred)" if cell.policy_deferred else ""
        return f"—{suffix}"
    assert cell.coverage_percent is not None
    return (
        f"{cell.emitted} / {cell.shared_candidates} "
        f"({cell.coverage_percent:.1f}%)"
    )


def _text_table(
    headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]
) -> tuple[str, ...]:
    widths = tuple(
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    )

    def line(row: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(row)
        ).rstrip()

    separator = tuple("-" * width for width in widths)
    return (line(headers), line(separator), *(line(row) for row in rows))


def _write_tier(
    write: Callable[[str], None],
    title: str,
    names: tuple[str, ...],
    note: str,
) -> None:
    write(f"### {title} ({len(names)}) — {note}\n")
    write(", ".join(f"`{name}`" for name in names) + "\n")


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


__all__ = ("render_json", "render_markdown", "render_text")
