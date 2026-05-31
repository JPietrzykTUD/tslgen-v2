# M179 Backend Type Query Discovery Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M178 as accepted and post-M178 planning as accepted.

You are executing and reviewing:

```text
Milestone 179: Exact Backend Type Query Request-Island Discovery
```

Milestones 1 through 178 are accepted. M164 accepts exact
`value<backend>(...)` request-island discovery. M178 consolidated the shared
source-owned scanner mechanics used by request-island discoverers. M179 adds
the missing sibling discovery path for exact `type<backend>(...)` islands.

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
- `tslgen/src/tslgen/lowering/_source_islands.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m164_backend_value_queries.py`
- `tslgen/tests/test_m178_source_island_scanner.py`
- `tsldata/**/*.tsl` only as corpus evidence for exact `type<backend>(...)`
  source forms.

## Goal

Discover exact `type<backend>(...)` request islands inside source-owned text
and implementation body raw-token text, preserving surrounding text/tokens as
opaque source-owned segments.

This milestone records backend type queries as unresolved backend-owned
requests. It does not translate them to backend type spellings.

## Required Executor Task

Run exactly one write-capable executor for M179. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused lowering-owned discovery path for exact `type<backend>(...)`
   islands, analogous in source behavior to M164 `value<backend>(...)`
   discovery.
3. Use the M178 source-island scanner helper for delimiter matching and source
   mapping where it applies.
4. Discover islands in one text fragment and in `ImplementationBody` raw body
   tokens.
5. Preserve surrounding raw text and non-raw body tokens as opaque segments.
6. Preserve the complete source island text, payload text, payload source, and
   island source location.
7. Keep payload text backend-owned and unresolved in this milestone. Do not
   call backend language maps, render type spellings, or evaluate backend
   translation rules.
8. Preserve the existing `lower_backend_type_query(...)` selected-context
   semantic lowering behavior and the existing `BackendTypeSpellingRequest`
   contract. A raw discovered island must not masquerade as an already-lowered
   `BackendTypeSpellingRequest` unless the existing semantic type-query
   boundary is intentionally called and succeeds. If new records are needed
   for raw islands, keep them explicitly named as discovery/unresolved
   request-island records, not backend spelling requests.
9. Add focused tests for:
   - positive discovery in a source text fragment;
   - positive discovery in implementation body raw tokens;
   - multiple islands in one fragment;
   - nested balanced forms such as
     `type<backend>(vector::as_extension(scalar))`;
   - preservation of raw text/tokens around islands;
   - malformed unbalanced outer payload diagnostics;
   - no-match diagnostics;
   - no backend translation/rendering/source repair.
10. Update redesign docs only if implementation reveals a sharper boundary or
    an unavoidable follow-up.
11. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is request-island discovery, not backend type translation.
- Do not parse casts, declarations, assignments, array indexing, primitive
  calls, intrinsic payloads, branch bodies, loops, or target-language
  expressions around the island.
- Do not evaluate the `type<backend>(...)` payload into a backend spelling.
- Do not recursively lower nested type/generation payloads merely because the
  island was discovered. Nested payload semantics remain governed by the
  already accepted type-query lowering API when a later consumer explicitly
  calls it with selected context.
- Do not read backend language maps, backend translation maps, `tsldata`,
  `frozen`, or `tslgenold` at runtime from lowering.
- Do not introduce a broad TSIL grammar, expression interpreter, source
  rewriter, dependency scheduler, registry, dispatcher, plugin map, or
  worklist.
- If the executor needs new typed records, keep them as the narrow stable
  backend-type-query discovery surface and avoid refactoring accepted M164
  behavior unless the change is strictly behavior-preserving and well tested.

## Must Preserve

- M164 backend value query discovery behavior and diagnostics.
- Existing selected-context `lower_backend_type_query(...)` behavior.
- Existing `BackendTypeSpellingRequest` semantics for already-lowered backend
  type values.
- M178 source-island helper behavior and tests.
- Public imports and `Lowerer` method behavior for accepted lowering APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Backend type spelling translation; backend maps; rendering; generated output;
Rust/C++ language spelling decisions; backend control flow; intrinsic
translation; cast/memory/I/O translation; primitive-call rendering; loop
execution; declaration rendering; recursive body lowering; broad TSIL
expression parsing; dependency scheduling; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M179 stays a request-island discovery slice
   and does not add backend translation, rendering, parser, registry, or
   dispatcher behavior.
2. Boundary auditor: verify `type<backend>(...)` discovery preserves opaque
   payloads/surroundings and does not alter M164 or
   `lower_backend_type_query(...)` behavior.
3. Test auditor: verify tests cover source text, body raw tokens, multiple
   islands, nested balanced payloads, malformed/no-match diagnostics, and
   preservation behavior.
4. Documentation auditor: verify roadmap, current state, and next prompt are
   coherent after acceptance.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m178_source_island_scanner.py tslgen/tests/test_m179_backend_type_queries.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m178_source_island_scanner.py tslgen/tests/test_m179_backend_type_queries.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M179 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M179 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 180 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
