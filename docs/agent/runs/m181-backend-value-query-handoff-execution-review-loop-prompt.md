# M181 Backend Value Query Handoff Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M180 as accepted and post-M180 lowering planning as accepted.

You are executing and reviewing:

```text
Milestone 181: Exact Backend Value Query Semantic Handoff
```

Milestones 1 through 180 are accepted. M164 added exact
`value<backend>(...)` request-island discovery over source-owned text and
implementation body raw-token text. M180 closed the sibling
`type<backend>(...)` discovery-to-semantic-request gap by handing exact M179
islands to existing typed backend type-spelling requests without backend
rendering. M181 does the corresponding semantic request handoff for the
currently observed backend-value payload families.

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
- `docs/redesign/design-decisions.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/generation-value-query-inventory.md`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m164_backend_value_queries.py`
- `tsldata/**/*.tsl` only as corpus evidence for exact
  `value<backend>(...)` source forms.

## Goal

Consume exact M164 `BackendValueQueryRequest` segments and hand their payloads
to one typed backend-value semantic request boundary while preserving opaque
surrounding text/tokens.

M181 covers all five currently observed top-level backend-value payload
families:

- `intrin::suffix` and `intrin::suffix(...)`;
- `intrin::prefix`;
- `uninit::array`;
- `uninit::scalar`;
- `x86::mm_fround_to_zero`.

This milestone produces typed unresolved backend-value requests only. It is
not backend value translation, intrinsic rendering, declaration rendering, or
C++/Rust output.

## Required Executor Task

Run exactly one write-capable executor for M181. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused handoff API for M164 backend value query discovery results.
3. Consume only `BackendValueQueryRequest` values from accepted M164 discovery
   output. Raw M164 request islands must remain distinct from semantic
   backend-value request facts until the handoff API is explicitly invoked.
4. Add one durable typed backend-value request boundary with variants for the
   five observed payload families above. Do not add a separate handoff/result
   family for each spelling.
5. Preserve complete source-island text, payload text, source locations,
   opaque text segments, opaque token segments, raw token identity, and source
   order.
6. Parse only the accepted backend-value payload heads:
   - `intrin::suffix` with no explicit argument;
   - `intrin::suffix(ARG_TEXT)` where `ARG_TEXT` is kept as a typed suffix
     operand using existing type lowering when it is an accepted type
     expression, exact observed quoted literal handling for `"stream"`, or a
     source-owned unresolved symbol/literal operand when it is backend-owned;
   - `intrin::prefix` with no arguments;
   - `uninit::array`;
   - `uninit::scalar`;
   - `x86::mm_fround_to_zero`.
7. Reuse existing selected-context type lowering for supported suffix
   argument type expressions. Do not invent a second type language.
8. Treat unsupported payload heads, malformed payload arity, malformed
   string/literal forms, and unsupported nested forms as deterministic
   backend-value-query diagnostics.
9. Preserve M164 discovery diagnostics: malformed outer
   `value<backend>(...)` islands remain discovery diagnostics; unsupported
   semantic payloads are M181 handoff diagnostics.
10. Add focused tests for:
    - positive text-fragment handoff covering all five observed payload
      families;
    - positive implementation-body handoff with opaque text/token
      preservation;
    - multiple islands in source order;
    - `intrin::suffix` no-argument, accepted type-expression argument,
      exact observed quoted-string argument `"stream"`, backend-owned symbol such as
      `ToBase`, and exact observed literal/tag operands such as `si32`,
      `si64`, or `si?`;
    - `intrin::prefix`, `uninit::array`, `uninit::scalar`, and
      `x86::mm_fround_to_zero`;
    - unsupported payload heads and malformed payload arity diagnostics;
    - raw M164 requests remain distinct from semantic request facts until the
      handoff API is invoked;
    - no backend maps, backend value translation, rendering, source repair, or
      recursive arbitrary-payload lowering.
11. Update redesign docs only if implementation reveals a sharper boundary or
    unavoidable follow-up.
12. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is a semantic request handoff slice, not backend value translation.
- Consume only exact M164 `BackendValueQueryRequest` segments.
- Keep all five selected payload families in one backend-value semantic
  boundary with shared provenance and ordered segment preservation.
- Do not recursively scan arbitrary directive payloads, primitive-call
  selectors, intrinsic modifiers, source-operation payloads, declaration
  payloads, branch bodies, loop bodies, or other opaque text carriers.
- Do not parse casts, declarations, assignments, array indexing, primitive
  calls, intrinsic arguments, branch bodies, loops, or target-language
  expressions around the island.
- Do not evaluate backend suffix/prefix/uninit/constant values or make
  C++/Rust spelling decisions.
- Do not read backend language maps, backend translation maps, manifests,
  `tsldata`, `frozen`, or `tslgenold` at runtime from lowering.
- Do not introduce a broad TSIL grammar, expression interpreter, source
  rewriter, dependency scheduler, registry, dispatcher, plugin map, worklist,
  or per-spelling request/result stack.

## Must Preserve

- M164 backend value query discovery behavior and diagnostics.
- M178 source-island helper behavior.
- M180 backend type query handoff behavior.
- Existing selected-context type-query lowering behavior.
- Existing primitive-call, backend-intrinsic, backend-control,
  source-operation, generation-variable, generation-loop, mask-lane-constant,
  and backend-type-query public APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Backend value translation results; backend maps, manifests, or language maps;
generated output; C++/Rust rendering; intrinsic modifier evaluation beyond
typed request construction; intrinsic call rendering; source-operation
translation; declaration rendering; loop execution; primitive-call rendering;
body-token rendering policy; recursive body lowering; recursive discovery
through arbitrary payload contexts; broad TSIL expression parsing;
target-language expression parsing; source repair; dependency scheduling;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; registries,
dispatchers, plugin maps, worklists, or per-payload-family pipelines.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M181 stays a handoff from discovered
   `value<backend>(...)` islands to typed unresolved backend-value requests
   and does not add backend translation, rendering, parser, registry,
   dispatcher, worklist, or per-spelling pipelines.
2. Boundary auditor: verify M181 covers exactly the five selected observed
   payload families, preserves opaque surroundings, does not recursively lower
   arbitrary payload carriers, and does not alter M164, M178, M180, or
   existing type-query behavior.
3. Evidence auditor: verify representative corpus forms and counts remain
   accurately cited and no non-corpus source form is treated as required.
4. Test auditor: verify tests cover all five families, suffix argument
   variants, text and body-token handoff, multiple islands, diagnostics, raw
   request distinction, and no rendering/source repair.
5. Documentation auditor: verify roadmap, current state, inventories if
   touched, and next prompt are coherent after acceptance.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m181_backend_value_query_handoff.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m181_backend_value_query_handoff.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M181 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M181 accepted in `docs/redesign/implementation-roadmap.md`;
- update inventories or design docs only for accepted behavior or unavoidable
  follow-ups;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 182 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
