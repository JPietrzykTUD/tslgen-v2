# M183 Source-Operation Selector Handoff Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M182 as accepted and post-M182 lowering planning as accepted.

You are executing and reviewing:

```text
Milestone 183: Exact Source-Operation Selector Semantic Handoff
```

Milestones 1 through 182 are accepted. M167 added exact source-operation
request-island discovery for `cast<...>(...)`, `mem<...>(...)`, and
`io<...>(...)` over source-owned text and contiguous raw body-token runs. M183
must consume those already discovered request islands and classify only the
top-level selector payload into typed finite selector values.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/source_operations.py`
- `tslgen/tests/test_m167_source_operations.py`
- `tsldata/**/*.tsl` only as corpus evidence for source-operation selector
  forms. Filter to exact source-operation keyword heads so target-language
  substrings such as `static_cast<...>` and `bit_cast<...>` are not counted
  as TSIL source-operation selectors.

## Goal

Add a focused semantic handoff for M167 source-operation discovery results.
The handoff should turn exact source-operation selector payloads into typed
finite selector facts while preserving the original M167 island as the
source-owned opaque carrier for arguments and provenance.

M183 covers all three M167 source-operation families in one slice:

```text
cast<...>(...)
mem<...>(...)
io<...>(...)
```

## Required Executor Task

Run exactly one write-capable executor for M183. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused handoff API for M167 source-operation discovery results.
3. Consume only `SourceOperationRequest` values from accepted M167 discovery
   output. Raw M167 request islands must remain distinct from semantic
   source-operation selector facts until the handoff API is explicitly
   invoked.
4. Add typed selector values for all currently observed primitive-body
   selector payloads:
   - cast selectors: `static`, `reinterpret`, `bitcast`, `saturating`;
   - memory selectors: `copy`, `alloc`, `alloc_aligned`, `free`;
   - I/O selectors: `write`, `write_base`, `write_bin`, `endl`.
5. Represent selector semantics with typed values such as `Literal` aliases,
   enums, or focused frozen dataclasses. Do not represent the accepted selector
   as a generic raw string field in the new semantic handoff request.
6. Preserve complete source-island text, angle payload text, argument payload
   text, source locations, opaque text segments, opaque token segments, raw
   token identity, raw M167 request identity, and source order by carrying the
   original M167 request island/provenance through the handoff segment.
7. Keep source-operation argument payloads opaque. Do not split arguments,
   lower `type<generation>(...)`, discover nested `cast`/`mem`/`io`,
   discover nested `intrin`, discover nested backend/generation queries, or
   parse target-language expressions inside the arguments.
8. Diagnose unsupported selector payloads deterministically, including
   unknown selectors, selector payloads with surrounding whitespace, empty
   selector payloads reaching handoff, template placeholders such as `{type}`,
   and expression-like selector payloads such as
   `mode=value<backend>(...)`.
9. Preserve M167 discovery diagnostics: malformed outer source-operation
   islands remain discovery diagnostics; unsupported selector payloads are
   M183 handoff diagnostics.
10. Add focused tests for:
    - positive text-fragment handoff for every accepted cast, memory, and I/O
      selector;
    - positive implementation-body handoff with opaque text/token preservation
      and raw request identity;
    - source-order preservation across mixed `cast`, `mem`, and `io` islands;
    - raw M167 requests remaining distinct from semantic handoff facts until
      the handoff API is invoked;
    - unsupported selector diagnostics for unknown, whitespace-padded,
      placeholder, expression-like, and wrong-family selector payloads;
    - argument opacity/no nested scans with arguments containing nested
      `type<generation>`, `value<generation>`, `value<backend>`,
      `intrin_compose`, `cast`, `mem`, `io`, raw operators, quoted delimiters,
      and target-language-like text.
11. Update redesign docs only if implementation reveals a sharper boundary or
    unavoidable follow-up.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Raw String / Opaque Text Guardrail

M183 must not add raw string fields to new semantic dataclasses unless the
field is explicitly source-owned opaque text required for diagnostics or
provenance. Prefer carrying the original M167 `SourceOperationRequest` island
on the handoff segment rather than duplicating `angle_payload_text`,
`argument_text`, or `source_text` on the new semantic request value.

Typed facts should carry typed selector values and source/provenance only.
Raw text may remain in the accepted M167 discovery request and opaque segment
types because those are source-owned intake/provenance boundaries.

## Design Guardrails

- This is a selector semantic handoff slice, not source-operation translation.
- Consume only exact M167 `SourceOperationRequest` segments.
- Classify only the top-level selector payload inside `<...>`.
- Keep source-operation argument payloads opaque.
- Do not translate cast, memory, or I/O operations.
- Do not read backend language maps, translation maps, manifests, `tsldata`,
  `frozen`, or `tslgenold` at runtime from lowering.
- Do not introduce a broad TSIL grammar, expression interpreter, source
  rewriter, dependency scheduler, registry, dispatcher, plugin map, worklist,
  argument AST, or per-selector pipeline.
- Backend translation map placeholders such as `cast<{type}>` are backend
  metadata evidence for later rendering work, not accepted primitive-body
  selector payloads for M183.

## Must Preserve

- M167 source-operation discovery behavior and diagnostics.
- M178 source-island helper behavior.
- Existing selected-context type-query, generation-value, backend-value,
  backend-type, backend-control, backend-intrinsic, primitive-call,
  generation-loop, generation-variable, mask-lane-constant, and source
  operation public APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Cast translation/results; memory translation/results; I/O translation/results;
backend maps, manifests, or language maps; generated output; C++/Rust
rendering; argument splitting; type lowering inside arguments; pointer
semantics; allocation/free ownership semantics; stream formatting semantics;
nested source-operation lowering; backend/generation query evaluation;
intrinsic rendering; primitive-call rendering; declaration rendering; loop
execution; body-token rendering policy; recursive discovery through arbitrary
payload contexts; broad TSIL expression parsing; target-language expression
parsing; source repair; dependency scheduling; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, plugin maps, worklists, or
per-selector pipelines.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M183 stays a handoff from discovered
   source-operation islands to typed selector facts and does not add backend
   translation, rendering, parser, registry, dispatcher, worklist, or
   per-selector pipelines.
2. Boundary auditor: verify M183 classifies only top-level selector payloads,
   preserves arguments opaque, preserves M167 raw islands distinct until
   handoff, and avoids recursive/nested payload discovery.
3. Evidence auditor: verify accepted selector sets match current
   `tsldata/**/*.tsl` exact source-operation-head evidence and that backend
   translation map placeholders or target-language substrings are not treated
   as TSIL source-operation selectors.
4. Test auditor: verify tests cover all accepted selector families, unsupported
   selector diagnostics, opaque argument payloads, body-token/text
   preservation, raw request distinction, and no rendering/source repair.
5. Documentation auditor: verify roadmap, current state, inventories if
   touched, and next prompt are coherent after acceptance, and that raw-string
   guardrails are represented accurately.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m167_source_operations.py tslgen/tests/test_m183_source_operation_selector_handoff.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m167_source_operations.py tslgen/tests/test_m183_source_operation_selector_handoff.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M183 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M183 accepted in `docs/redesign/implementation-roadmap.md`;
- update inventories or design docs only for accepted behavior or unavoidable
  follow-ups;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 184 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
