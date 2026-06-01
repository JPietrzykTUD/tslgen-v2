# M202 Stream Intrinsic Suffix Translation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M201 as accepted.

This is an execution milestone. Use the executor-review loop from `PLANS.md`:
one write-capable executor, then read-only reviewer/auditor subagents, then a
focused revision executor only if review returns `Needs Revision`. The
orchestrator owns final verdict consolidation, state updates, and next-prompt
creation.

## Accepted State

Accepted through:

```text
M201: Post-Current-Suffix Intrinsic Modifier Planning
```

Selected milestone:

```text
Milestone 202: Stream Intrinsic Suffix Translation
```

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/flaws-to-fix.md`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/src/tslgen/backends/__init__.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/extensions/extension.tsl`
- representative `tsldata/primitives/**/*.tsl` occurrences from the M201
  inventory

## Goal

Translate the exact named stream suffix policy from accepted
`intrin_compose` handoff modifier fields:

```text
suffix=value<backend>(intrin::suffix("stream"))
```

`"stream"` is a named backend suffix policy. It is not emitted raw text, and
it is not general quoted-string suffix support.

## Scope

- Consume only `BackendIntrinsicModifierField` values whose field name is
  `suffix` and whose value carries
  `BackendIntrinsicSuffixValueRequest(argument=BackendValueStringLiteralOperand("stream"))`.
- Use typed backend modifier context, especially selected backend and selected
  extension. Do not infer from intrinsic base names or surrounding source text.
- Support the active x86-family extension names already represented in
  `tsldata/extensions/extension.tsl`: `sse`, `sse_vl`, `avx2`, `avx2_vl`, and
  `avx512`.
- Add active C++ and Rust backend metadata entries for the emitted suffix
  fragments. Python may carry typed rule records mapping
  `(policy="stream", selected_extension)` to backend metadata keys, but the
  fragment text itself must come from `translate_cpp.tsl` and
  `translate_rust.tsl`.
- Expected metadata-backed fragments, based on current extension evidence and
  legacy behavior, are:

```text
sse      -> si128
sse_vl   -> si128
avx2     -> si256
avx2_vl  -> si256
avx512   -> si512
```

- Preserve modifier order, field/request provenance, metadata key/source
  provenance, and all accepted M195, M197, M198, and M200 behavior.
- Keep the shared metadata-backed modifier evaluator small. A focused refactor
  is allowed if it avoids duplication, but do not add a broad registry,
  dispatcher, worklist, new request/result family, or renderer.
- Add focused tests for:
  - C++ stream suffix translation for representative `sse`, `avx2`, and
    `avx512` contexts;
  - Rust stream suffix translation for at least one representative x86
    context, proving the modifier remains only a name fragment and does not
    include `core::arch::*`;
  - exact field boundary: `suffix` is supported, quoted-string `infix` remains
    unsupported unless a future milestone selects it;
  - unsupported quoted suffix names;
  - unsupported non-x86 or missing-extension policies;
  - missing backend metadata and missing metadata-entry diagnostics;
  - no source-text parsing of the surrounding intrinsic name;
  - corpus characterization showing the 21 accepted balanced stream suffix
    fields newly translate after M202.

## Required Corpus Accounting

Using the same accepted discovery/lowering path as M195-M200, characterize
`tsldata/primitives/**/*.tsl` after M202:

```text
643 total modifier fields
587 translated after M202:
  335 literal modifiers
  181 type-derived suffix modifiers
  9 prefix modifiers
  41 current-type no-argument suffix modifiers
  21 stream named suffix modifiers

56 still unsupported:
  20 suffix=value<backend>(intrin::suffix(SYMBOL))
     - 19 actionable ToBase cases
     - 1 FTF-002 intrin::suffix(si?) source-data flaw
  13 infix=value<backend>(intrin::suffix(ToBase))
  4  infix=to_type_suffix
  19 immediate(N)=symbol
```

If implementation evidence changes these counts, stop and explain whether the
source corpus changed, a matcher bug was found, or M201's inventory was wrong.

Raw source evidence note:

The raw `.tsl` corpus also contains two escaped `"stream"` spellings in quoted
TSIL bodies in `tsldata/primitives/conversion/cast.tsl`. The accepted
M195-M200 balanced `intrin_compose` discovery/lowering path does not currently
classify those escaped spellings as modifier fields. Do not broaden lowering,
source-island discovery, or quoted-TSIL handling in M202.

## Out Of Scope

- Arbitrary quoted suffix names.
- Quoted-string `infix` suffix support.
- Symbol suffixes such as `intrin::suffix(ToBase)`.
- FTF-002 `intrin::suffix(si?)`.
- Destination, return-type, or alias binding.
- `infix=to_type_suffix`.
- Symbol immediate resolution.
- Intrinsic-name assembly.
- Rendering or generated output.
- Rust `core::arch::*` qualification.
- Import-based Rust intrinsic rendering.
- Direct `intrin<...>(...)` parsing.
- Intrinsic argument payload parsing.
- Dependency closure.
- Source repair.
- Broad TSIL or target-language parsing.
- Lowering changes. If accepted typed handoff values cannot represent this
  family, stop and return to planner.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Packet

After implementation and validation, provide reviewers:

- changed files;
- the accepted `"stream"` named suffix rule and where it is encoded;
- the backend metadata entries added for C++ and Rust;
- corpus accounting before/after M202;
- diagnostics added or reused;
- confirmation that arbitrary quoted suffix names and quoted-string `infix`
  remain unsupported;
- confirmation that no renderer, source repair, dependency closure, lowering,
  or Rust module qualification work was added.

## Reviewer Focus

Reviewers must use `docs/agent/review-checklist.md` and focus on:

- whether M202 consumes typed handoff/context values rather than raw source;
- whether `"stream"` is modeled as a named policy rather than literal
  passthrough;
- whether suffix fragment text comes from backend metadata;
- whether rule records stay typed and narrow;
- whether ADR-056, ADR-057, ADR-058, and FTF-002 remain intact;
- whether remaining families stay explicitly unsupported;
- whether tests prove corpus counts and diagnostics.

## Next Prompt Requirement

Before finishing, update `docs/agent/current-redesign-state.md` and create the
next concrete prompt under `docs/agent/runs/`, unless the accepted review
records an explicit stop condition.
