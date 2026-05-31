# M187 Backend/Output Source-Island Discovery Execution-Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records post-M186 lowering completion gate planning as accepted.

This prompt explicitly selects one write-capable executor task. Implement
Milestone 187, then run the required read-only review/audit subagents before
updating state and creating the next prompt.

## Accepted State

Accepted through:

```text
Milestone 186: Typed Generation Boolean Condition Grammar Boundary
```

Post-M186 lowering completion gate planning selected:

```text
Milestone 187: Exact Backend/Output Source-Island Discovery Boundary
```

The selected M187 gap is request-island identity, not semantic evaluation.
Backend/output stages need to distinguish `assume_aligned<...>(...)`,
`array_type<...>`, and `pack<...>(...)` from arbitrary raw helper text, but
lowering must not resolve their backend semantics.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- Existing source-island discovery code, especially:
  - `tslgen/src/tslgen/lowering/_source_islands.py`
  - `tslgen/src/tslgen/lowering/source_operations.py`
  - `tslgen/src/tslgen/lowering/backend_intrinsics.py`
  - `tslgen/src/tslgen/lowering/mask_keywords.py`

## Goal

Add exact backend/output source-island discovery for all three current
backend/output request forms:

```text
assume_aligned<...>(...)
array_type<...>
pack<...>(...)
```

These islands are unresolved backend/output requests. They must carry enough
typed identity and source-owned payload text for a later backend/rendering
milestone to consume them without rescanning raw text.

## Scope

- Discover exact islands in one raw text fragment.
- Discover exact islands across contiguous `RawStringToken` runs in an
  `ImplementationBody`, preserving non-raw body tokens as opaque token spans.
- Preserve deterministic segment order with opaque text/token segments around
  request segments.
- Preserve request kind, angle payload text/source, complete source text,
  request source, and source locations.
- Preserve optional argument payload text/source for call-shaped forms:
  - `assume_aligned<...>(...)`
  - `pack<...>(...)`
- Treat `array_type<...>` as angle-only with no argument payload.
- Diagnose malformed islands deterministically:
  - missing or mismatched angle close;
  - empty angle payload;
  - missing or mismatched argument delimiters for call-shaped forms;
  - unexpected call delimiters for `array_type<...>(...)`, if encountered as
    one contiguous island.
- Reuse the shared source-island scanner utilities where they fit.
- Add focused tests with corpus-shaped examples for:
  - `assume_aligned<value<generation>(vector::alignment)>(ptr)`;
  - `array_type<type<generation>(base::in), value<generation>(vector::length)>`;
  - `pack<first>(args...)`;
  - multiple islands with surrounding opaque text;
  - contiguous raw-token runs;
  - non-raw tokens preserved as opaque token spans;
  - malformed diagnostics and determinism.

## Out Of Scope

- Resolving alignment values or pointer semantics.
- Resolving array layout, element types, lengths, alignment, allocation, or
  declaration semantics.
- Resolving pack semantics.
- Splitting arbitrary argument lists.
- Lowering nested payloads such as `value<generation>(...)`,
  `type<generation>(...)`, `type<backend>(...)`, or `call<primitive=...>(...)`
  inside these islands.
- Recursive discovery inside every opaque payload carrier.
- Parsing target-language expressions, statements, assignments, indexing,
  casts, helper calls, or operators.
- Translating backend helper calls or rendering C++/Rust.
- Source repair.
- Runtime reads from `tsldata`, `frozen`, or `tslgenold`.
- Registries, dispatchers, worklists, recursive payload walkers, or
  per-keyword frameworks.

## Required Implementation Shape

Use a narrow, typed request/discovery boundary analogous to accepted
source-island discovery modules. Keep names domain-oriented, for example
`BackendOutputRequestKind`, `BackendOutputRequest`,
`BackendOutputDiscovery`, and segment types, unless a clearer local naming
pattern emerges.

The model may store raw source text fields when they are source-owned payloads
or opaque surrounding text. Do not add raw strings as semantic substitutes for
alignment, array, or pack meaning.

If the implementation touches `model.py` or `__init__.py`, keep the additions
minimal and focused. Do not use this milestone to split model files or
refactor unrelated request families.

## Required Review/Audit Subagents

After implementation and local validation, run read-only subagents:

1. Architecture reviewer.
2. Boundary/simplicity auditor.
3. Evidence auditor.
4. Test auditor.
5. Documentation auditor.
6. Validation auditor.

All reviewers/auditors are read-only. If any returns `Needs Revision`, make
only focused fixes for blocking issues and re-run the relevant focused
review. If any returns `Return To Planner` or `Reject`, stop implementation
and create the appropriate next prompt.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m187_backend_output_source_islands.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m187_backend_output_source_islands.py
find tslgen -type d -name __pycache__ -print
```

If `compileall` or pytest creates `__pycache__`, remove validation-created
cache directories before the final `find` check and report both the cleanup
and final `find` result.

## Completion Rules

If M187 is accepted:

- update `docs/agent/current-redesign-state.md`;
- record the accepted behavior in `docs/redesign/implementation-roadmap.md`;
- update behavioral/domain/inventory docs as needed;
- create the next concrete run prompt under `docs/agent/runs/`;
- do not start the next milestone.

## Final Report

Report:

1. Implementation summary.
2. Whether M187 was accepted or needs revision.
3. Review/audit verdicts.
4. Validation commands and exact results.
5. Next active prompt path.
