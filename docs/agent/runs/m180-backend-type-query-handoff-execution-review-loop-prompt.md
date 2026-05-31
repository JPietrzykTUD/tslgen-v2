# M180 Backend Type Query Handoff Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M179 as accepted and post-M179 lowering planning as accepted.

You are executing and reviewing:

```text
Milestone 180: Exact Backend Type Query Island Semantic Handoff
```

Milestones 1 through 179 are accepted. M179 added exact
`type<backend>(...)` request-island discovery over source-owned text and
implementation body raw-token text. M143 already accepts selected-context
semantic lowering for the observed `type<backend>(...)` forms through
`lower_backend_type_query(...)`, producing `BackendTypeSpellingRequest`
values. M180 connects those two accepted boundaries without backend rendering.

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
- `docs/redesign/tsil-type-query-inventory.md`
- `tslgen/src/tslgen/lowering/backend_type_queries.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m179_backend_type_queries.py`
- `tsldata/**/*.tsl` only as corpus evidence for exact
  `type<backend>(...)` source forms.

## Goal

Consume exact M179 `BackendTypeQueryRequestIsland` segments and hand them to
the existing selected-context `lower_backend_type_query(...)` semantic
boundary, producing existing `BackendTypeSpellingRequest` values while
preserving opaque surrounding text/tokens.

This milestone is a handoff from raw discovered source islands to already
accepted typed backend type-spelling requests. It is not backend type spelling
translation or rendering.

## Required Executor Task

Run exactly one write-capable executor for M180. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused handoff API for M179 backend type query discovery results.
3. Lower only `BackendTypeQueryRequestIsland` values by passing each island's
   complete `source_text` and source location to existing
   `lower_backend_type_query(...)` semantics. Do not pass only
   `payload_text`.
4. Produce existing `BackendTypeSpellingRequest` values for successful
   handoffs; do not add a second backend type semantic model.
5. Preserve opaque text segments, opaque token segments, raw token identity,
   source order, and raw island provenance.
6. Reuse existing selected type environment behavior when an explicit
   environment is supplied. Do not infer `let<type>` ordering or alias scope
   from surrounding opaque raw text.
7. Propagate diagnostics from the existing semantic type-query path with
   source locations tied to the discovered island.
8. Preserve M179 discovery behavior and the existing
   `lower_backend_type_query(...)` API behavior.
9. Add focused tests for:
   - positive text-fragment handoff from discovered island to
     `BackendTypeSpellingRequest`;
   - positive implementation-body handoff with opaque text/token preservation;
   - multiple islands in source order;
   - representative accepted corpus forms:
     `type<backend>(size_t)`, scalar backend requests,
     `type<backend>(intrin::vector::imask)`, and
     `type<backend>(vector::as_extension(...))`;
   - explicit alias environment success and unbound alias diagnostics without
     inferring aliases from raw surroundings;
   - malformed discovery diagnostics remain discovery diagnostics;
   - unsupported semantic payloads remain type-query diagnostics;
   - raw M179 islands remain distinct from `BackendTypeSpellingRequest` until
     the handoff API is explicitly invoked;
   - no backend spelling translation/rendering/source repair.
10. Update redesign docs only if implementation reveals a sharper boundary or
    an unavoidable follow-up.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is a semantic handoff slice, not backend type translation.
- Consume only exact M179 `BackendTypeQueryRequestIsland` segments.
- Do not recursively scan arbitrary directive payloads, primitive-call
  selectors, intrinsic modifiers, source-operation payloads, declaration
  payloads, branch bodies, loop bodies, or other opaque text carriers.
- Do not parse casts, declarations, assignments, array indexing, primitive
  calls, intrinsic payloads, branch bodies, loops, or target-language
  expressions around the island.
- Do not evaluate backend type spelling text or make C++/Rust spelling
  decisions.
- Do not read backend language maps, backend translation maps, manifests,
  `tsldata`, `frozen`, or `tslgenold` at runtime from lowering.
- Do not introduce a broad TSIL grammar, expression interpreter, source
  rewriter, dependency scheduler, registry, dispatcher, plugin map, worklist,
  or new backend type model.
- If a small ordered result/segment wrapper is needed to preserve opaque
  segments plus lowered requests, keep it narrowly owned by this handoff and
  avoid a general body-composition framework.

## Must Preserve

- M179 backend type query discovery behavior and diagnostics.
- Existing selected-context `lower_backend_type_query(...)` behavior.
- Existing `BackendTypeSpellingRequest` semantics for lowered backend type
  values.
- M164 backend value query discovery behavior.
- M178 source-island helper behavior.
- Public imports and `Lowerer` method behavior for accepted lowering APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Backend type spelling translation; backend maps, manifests, or language type
maps; generated output; C++/Rust rendering; backend value query evaluation;
intrinsic/source-operation/declaration/backend-control payload lowering;
recursive body lowering; recursive discovery through arbitrary payload
contexts; broad TSIL expression parsing; target-language expression parsing;
source repair; dependency scheduling; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, plugin maps, worklists, or
a new backend type model.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M180 stays a handoff from discovered
   `type<backend>(...)` islands to existing typed backend type-spelling
   requests and does not add backend translation, rendering, parser, registry,
   dispatcher, or worklist behavior.
2. Boundary auditor: verify M180 consumes complete island `source_text`,
   preserves opaque surroundings, does not infer aliases from raw surrounding
   text, and does not alter M164, M178, M179, or existing
   `lower_backend_type_query(...)` behavior.
3. Evidence auditor: verify representative corpus forms and counts remain
   accurately cited and no non-corpus source form is treated as required.
4. Test auditor: verify tests cover text and body-token handoff, multiple
   islands, representative accepted type forms, alias environment behavior,
   diagnostics, and no rendering/source repair.
5. Documentation auditor: verify roadmap, current state, inventories if
   touched, and next prompt are coherent after acceptance.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m179_backend_type_queries.py tslgen/tests/test_m180_backend_type_query_handoff.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m179_backend_type_queries.py tslgen/tests/test_m180_backend_type_query_handoff.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M180 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M180 accepted in `docs/redesign/implementation-roadmap.md`;
- update inventories or design docs only for accepted behavior or unavoidable
  follow-ups;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 181 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
