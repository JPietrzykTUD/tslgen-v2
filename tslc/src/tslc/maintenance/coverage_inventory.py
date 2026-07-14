#!/usr/bin/env python3
"""Regenerate coverage/primitive-coverage-inventory.md.

Drives the compiler over every primitive in ``tsldata/`` across the canonical
profile set and registered backends, cross-references the build-verified set parsed
from ``tslc/tests/test_build_verify.py``, and writes the coverage table.

Run from the repository with ``tslc/src`` on ``PYTHONPATH``:

    PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_inventory

Lowering-only (no compilation); takes ~1 minute. "lowers" is NOT a compile
guarantee — only build-verified primitives are confirmed to compile.
"""

from __future__ import annotations

import ast
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

from tslc.api import generate_project
from tslc.backend.registry import registered_backend_ids
from tslc.catalog.builder import CatalogBuilder
from tslc.compiler_assets import load_default_tsl_grammar
from tslc.diagnostics import has_errors
from tslc.pipeline import SkippedEntry
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser

PROFILES = ("scalar", "sse2", "avx", "avx2", "skylake", "icelake_rockerlake")


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "tsldata").is_dir() and (candidate / "tslc" / "src").is_dir():
            return candidate
    raise RuntimeError(f"could not find repository root from {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve())
_DATA_ROOT = _REPO_ROOT / "tsldata"
_PROFILES_PATH = _REPO_ROOT / "supplementary" / "buildsystem" / "machine_profiles.json"
_BUILD_TEST = _REPO_ROOT / "tslc" / "tests" / "test_build_verify.py"
_OUT = _REPO_ROOT / "coverage" / "primitive-coverage-inventory.md"


def _has_skip_decorator(fn: ast.FunctionDef) -> bool:
    """True if the test is decorated `@pytest.mark.skip[(...)]` (so it does not verify)."""

    for decorator in fn.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        while isinstance(target, ast.Attribute):
            if target.attr == "skip":
                return True
            target = target.value
    return False


def _build_verified_primitives() -> set[str]:
    """Primitives named in a ``primitives=[...]`` list of a NON-skipped build-verify test."""

    tree = ast.parse(_BUILD_TEST.read_text())
    verified: set[str] = set()
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef) or _has_skip_decorator(fn):
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "primitives"
                and isinstance(node.value, ast.List)
            ):
                verified |= {
                    el.value
                    for el in node.value.elts
                    if isinstance(el, ast.Constant)
                    and isinstance(el.value, str)
                }
    return verified


_CATEGORY_BY_CODE = {
    "TSL-PIPELINE-PRUNED-SPECIALIZATION": "pruned (closure)",
    "TSL-LOWER-SIZED-WIDTH-CHANGE": "generic-vector repr-change (deferred)",
    "TSL-LOWER-UNRESOLVED-TYPE-QUERY": "unresolved type query",
    "TSL-LOWER-UNRESOLVED-VALUE-QUERY": "unresolved value query",
    "TSL-LOWER-UNRESOLVED-CAST-TYPE": "unresolved cast type",
    "TSL-LOWER-POLICY-DEFERRED-SIGNATURE": "policy-deferred scalable signature",
    "TSL-LOWER-UNSUPPORTED-KIND": "unsupported signature kind",
    "TSL-LOWER-NO-COMPLETE": "no top-level complete",
    "TSL-LOWER-VARIANT-NO-COMPLETE": "no top-level complete",
    "TSL-LOWER-UNSUPPORTED-CALL-TYPEARGS": "call type-args (bare-ext/index)",
    "TSL-LOWER-UNSUPPORTED-MASK": "unsupported mask region",
}


def skip_category(entry: SkippedEntry) -> str:
    """Return a stable category from structured diagnostic identity, never prose."""

    if not entry.diagnostics:
        return f"unclassified {entry.status}"
    diagnostic = next(
        (
            diagnostic
            for diagnostic in entry.diagnostics
            if diagnostic.severity == "error"
        ),
        entry.diagnostics[0],
    )
    code = diagnostic.code
    return _CATEGORY_BY_CODE.get(code, code)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tslc coverage inventory",
        description="Regenerate the tracked primitive coverage inventory.",
    )
    parser.add_argument("--output", default=str(_OUT))
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the report is stale instead of rewriting it",
    )
    args = parser.parse_args(argv)
    output_path = Path(args.output)
    catalog = CatalogBuilder().build(
        TslParser(load_default_tsl_grammar()).parse(SourceLoader().load_dir(_DATA_ROOT).documents)
    ).catalog
    if catalog is None:
        print("ERROR: catalog promotion failed", file=sys.stderr)
        return 1
    names = sorted({p.name for p in catalog.primitives})
    backend_ids = registered_backend_ids()
    sigs: dict[str, set[str]] = defaultdict(set)
    for primitive in catalog.primitives:
        sigs[primitive.name].add(primitive.signature)

    verified = _build_verified_primitives()
    result = generate_project(
        [_DATA_ROOT],
        machine_profiles_path=_PROFILES_PATH,
        primitives=names,
        profiles=list(PROFILES),
        backends=backend_ids,
    )
    if has_errors(result.diagnostics):
        for diagnostic in result.diagnostics:
            if diagnostic.severity == "error":
                print(f"ERROR {diagnostic.code}: {diagnostic.message}", file=sys.stderr)
        return 1

    coverage_by_backend: dict[str, dict[str, set[str]]] = {
        backend_id: defaultdict(set) for backend_id in backend_ids
    }
    skips: Counter[str] = Counter()
    categories: dict[str, Counter[str]] = defaultdict(Counter)
    for coverage_entry in result.coverage:
        coverage_by_backend[coverage_entry.backend][coverage_entry.primitive].add(
            coverage_entry.extension
        )
    for skipped_entry in result.skipped:
        skips[skipped_entry.primitive] += 1
        categories[skipped_entry.primitive][skip_category(skipped_entry)] += 1

    def status(name: str) -> str:
        emitted = any(coverage[name] for coverage in coverage_by_backend.values())
        if name in verified:
            return "VERIFIED"
        if emitted and skips[name] == 0:
            return "lowers"
        if emitted:
            return "partial"
        return "NONE"

    tier = {s: [n for n in names if status(n) == s] for s in ("VERIFIED", "lowers", "partial", "NONE")}
    total_emitted = len(result.coverage)
    total_skipped = len(result.skipped)
    histogram: Counter[str] = Counter()
    for skipped_entry in result.skipped:
        histogram[skip_category(skipped_entry)] += 1
    backend_label = "/".join(backend_ids)
    parity = all(
        len({frozenset(coverage[name]) for coverage in coverage_by_backend.values()}) <= 1
        for name in names
    )

    out: list[str] = []
    w = out.append
    w("# Primitive Coverage Inventory\n")
    w("Generated by `tslc.maintenance.coverage_inventory`. **Regenerate** with")
    w(
        "`PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_inventory`; "
        "do not hand-edit (it rewrites this file).\n"
    )
    w("## Summary\n")
    w(f"- **{len(names)} distinct primitives** in `tsldata/`.")
    w(f"- **{len(tier['VERIFIED'])} build-verified** (compile in {backend_label} via "
      "`tslc/tests/test_build_verify.py`).")
    w(f"- **{len(tier['lowers'])} lower cleanly but are not build-verified** "
      "(codegen succeeds, 0 skips; compilation unconfirmed).")
    w(f"- **{len(tier['partial'])} partial** (emit for some extension/type slots, skip others).")
    w(f"- **{len(tier['NONE'])} emit nothing** under the probed profiles.")
    w(f"- **{total_emitted} / {total_emitted + total_skipped} "
      "(profile×backend×ext×type) slots lower**; **0 errors**.")
    if parity:
        w(f"- **{backend_label} parity is exact**: every primitive emits the identical "
          "extension set for every registered backend.\n")
    else:
        w(f"- **{backend_label} parity differs** for at least one primitive.\n")
    w("Status legend: **VERIFIED** = has a passing build test; **lowers** = codegen "
      "clean, 0 skips, no build test; **partial** = some slots lower, some skip; "
      "**NONE** = nothing emitted.\n")
    w(f"> Caveat: \"lowers\" means the generator produced {backend_label} text without "
      "diagnostics — it is *not* a compile guarantee. Only **VERIFIED** primitives are "
      "confirmed to compile. The probe uses the 10 arith type tags (si/ui 8-64, "
      f"f32/f64) across profiles `{', '.join(PROFILES)}`.\n")

    w("## Tiers\n")
    w(f"### Build-verified ({len(tier['VERIFIED'])}) — compile in {backend_label}\n")
    w(", ".join(f"`{n}`" for n in tier["VERIFIED"]) + "\n")
    w(f"### Lower but not build-verified ({len(tier['lowers'])}) — codegen clean, "
      "compilation unconfirmed\n")
    w(", ".join(f"`{n}`" for n in tier["lowers"]) + "\n")
    w(f"### Partial ({len(tier['partial'])}) — some slots lower, some skip\n")
    w(", ".join(f"`{n}`" for n in tier["partial"]) + "\n")
    w(f"### Emit nothing ({len(tier['NONE'])})\n")
    w(", ".join(f"`{n}`" for n in tier["NONE"]) + "\n")

    w("## Per-primitive table\n")
    w("| primitive | signatures | status | extensions by backend | skipped slots | dominant gap |")
    w("|---|---|---|---|--:|---|")
    for name in names:
        exts = "; ".join(
            f"{backend_id}="
            + ("/".join(sorted(coverage_by_backend[backend_id][name])) or "—")
            for backend_id in backend_ids
        )
        signatures = " ".join(f"`{s}`" for s in sorted(sigs[name]))
        dominant = (
            categories[name].most_common(1)[0][0] if categories[name] else "—"
        )
        w(f"| `{name}` | {signatures} | {status(name)} | {exts} | {skips[name]} | {dominant} |")
    w("")

    w("## Skip-reason taxonomy (what blocks the gaps)\n")
    w("> Skip counts are candidate specialization slots "
      "(`profile×backend×extension×type`), not primitives. A primitive can be "
      "**VERIFIED** while still listing skipped slots when another profile/type/"
      "extension variant is deliberately pruned or deferred.\n")
    w("| skips | category | meaning / action |")
    w("|--:|---|---|")
    for category, count in histogram.most_common():
        w(f"| {count} | {category} | {_CATEGORY_NOTES.get(category, '')} |")
    w("")
    w("### NONE primitives — why nothing emits\n")
    if not tier["NONE"]:
        w("No primitives are currently in the NONE tier; every primitive emits at "
          "least one slot under the probed profiles.\n")
    else:
        for name in tier["NONE"]:
            signatures = " ".join(f"`{s}`" for s in sorted(sigs[name]))
            if categories[name]:
                category = categories[name].most_common(1)[0][0]
                note = _CATEGORY_NOTES.get(category, "")
                suffix = f": {category}. {note}" if note else f": {category}."
            else:
                suffix = "."
            w(f"- `{name}` ({signatures}){suffix}")
        w("")

    rendered = "\n".join(out)
    if args.check:
        current = output_path.read_text(encoding="utf-8") if output_path.is_file() else None
        if current != rendered:
            print(f"coverage inventory is stale: {output_path}", file=sys.stderr)
            return 1
        print(f"coverage inventory is current: {output_path}")
        return 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    try:
        display_path = output_path.relative_to(_REPO_ROOT)
    except ValueError:
        display_path = output_path
    print(f"wrote {display_path}")
    print(
        f"  {len(names)} primitives: {len(tier['VERIFIED'])} verified, "
        f"{len(tier['lowers'])} lowers, {len(tier['partial'])} partial, "
        f"{len(tier['NONE'])} none; {total_emitted}/{total_emitted + total_skipped} slots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
