# M182 Intrinsic Modifier Handoff Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M181 as accepted and post-M181 lowering planning as accepted.

You are executing and reviewing:

```text
Milestone 182: Exact Intrinsic Modifier Semantic Handoff
```

Milestones 1 through 181 are accepted. M166 added exact backend intrinsic
request-island discovery for `intrin<...>(...)` and
`intrin_compose<...>(...)` over source-owned text and contiguous raw body-token
runs. M181 added typed unresolved backend-value requests for the currently
observed `value<backend>(...)` payload families. M182 joins those boundaries
only for top-level intrinsic-compose modifiers.

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
- `tslgen/src/tslgen/lowering/backend_intrinsics.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m166_backend_intrinsics.py`
- `tslgen/tests/test_m181_backend_value_query_handoff.py`
- `tsldata/**/*.tsl` only as corpus evidence for exact intrinsic modifier
  source forms.

## Goal

Consume exact M166 `BackendIntrinsicRequest` discovery segments and hand
top-level `intrin_compose<...>(...)` modifier fields to one typed unresolved
intrinsic-modifier semantic boundary while preserving opaque surrounding
text/tokens and intrinsic argument payloads.

This milestone produces typed unresolved intrinsic modifier facts only. It is
not intrinsic translation, backend value translation, intrinsic rendering, or
C++/Rust output.

## Required Executor Task

Run exactly one write-capable executor for M182. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused handoff API for M166 backend intrinsic discovery results.
3. Consume only `BackendIntrinsicRequest` values from accepted M166 discovery
   output. Raw M166 request islands must remain distinct from semantic
   intrinsic-modifier facts until the handoff API is explicitly invoked.
4. Add one durable typed intrinsic-modifier handoff boundary that can carry:
   - preserved direct `intrin<...>(...)` requests with opaque angle payloads;
   - parsed `intrin_compose<...>(...)` base tokens;
   - source-ordered top-level modifier fields;
   - unresolved modifier operands;
   - existing M181 `BackendValueRequest` values when a modifier value is
     exactly one `value<backend>(...)` island.
5. Preserve complete source-island text, angle payload text, argument payload
   text, source locations, opaque text segments, opaque token segments, raw
   token identity, raw M166 request identity, and source order.
6. Keep direct `intrin<...>(...)` angle payloads opaque as direct intrinsic
   names. Do not parse direct intrinsic modifiers, direct intrinsic name
   templates, or `value<backend>(...)` text embedded inside a direct intrinsic
   name.
7. Parse only top-level `intrin_compose<...>(...)` angle payload fields:
   - base token first;
   - `suffix=...`;
   - `prefix=...`;
   - `post=...`;
   - `infix=...`;
   - `infix_sep=...`;
   - `immediate(N)=...`.
8. Make the top-level field parser delimiter-aware and quote-aware. It must
   support comma-separated modifier fields and observed whitespace-separated
   modifier fields such as
   `vgetq_lane suffix=value<backend>(intrin::suffix) immediate(1)=Index`.
   It must not scan nested payloads or the intrinsic argument payload.
9. Reuse the accepted M181 backend-value handoff only when a modifier value is
   exactly one balanced `value<backend>(...)` island. Do not run broad
   backend-value discovery over the whole angle payload.
10. Preserve accepted literal, symbol, numeric, and quoted modifier operands
    as typed unresolved modifier operands with source text and provenance.
    Examples include `post=x`, `post=mask`, `suffix=si128`,
    `suffix="epi64x"`, `infix=to_type_suffix`, `infix_sep=""`,
    `immediate(2)=4`, and `immediate(1)=Index`.
11. Diagnose malformed modifier fields, malformed `immediate(...)`, duplicate
    or ambiguous fields, unsupported nested modifier values, and malformed
    backend-value modifier islands deterministically.
12. Preserve M166 discovery diagnostics: malformed outer intrinsic islands
    remain discovery diagnostics; unsupported semantic modifier payloads are
    M182 handoff diagnostics.
13. Add focused tests for:
    - positive text-fragment handoff covering `intrin_compose` without
      modifiers, one modifier, multiple source-ordered modifiers,
      comma-separated fields, and observed whitespace-separated fields;
    - positive implementation-body handoff with opaque text/token
      preservation and raw request identity;
    - modifier values that are exact M181 backend-value islands;
    - unresolved symbol/literal operands, integer immediates, quoted string
      operands, and empty quoted `infix_sep`;
    - direct `intrin<...>(...)` preservation as opaque direct intrinsic facts,
      including direct angle text containing `value<backend>(...)`;
    - unsupported/malformed modifier diagnostics;
    - raw M166 requests remain distinct from semantic handoff facts until the
      handoff API is invoked;
    - no backend maps, backend translation, rendering, source repair,
      argument splitting, or recursive arbitrary-payload lowering.
14. Update redesign docs only if implementation reveals a sharper boundary or
    unavoidable follow-up.
15. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is a semantic modifier handoff slice, not backend intrinsic
  translation.
- Consume only exact M166 `BackendIntrinsicRequest` segments.
- Parse modifiers only from top-level `intrin_compose<...>(...)` angle
  payloads.
- Keep direct `intrin<...>(...)` angle payloads opaque.
- Keep intrinsic argument payloads opaque.
- Reuse M181 only for modifier values that are exactly one
  `value<backend>(...)` island.
- Do not translate backend values, intrinsic names, prefixes, suffixes, posts,
  infixes, immediates, or direct intrinsic names.
- Do not read backend language maps, backend translation maps, manifests,
  `tsldata`, `frozen`, or `tslgenold` at runtime from lowering.
- Do not introduce a broad TSIL grammar, expression interpreter, source
  rewriter, dependency scheduler, registry, dispatcher, plugin map, worklist,
  or per-modifier request/result stack.

## Must Preserve

- M166 backend intrinsic discovery behavior and diagnostics.
- M178 source-island helper behavior.
- M181 backend value query handoff behavior.
- Existing selected-context type-query and generation-value lowering behavior.
- Existing primitive-call, backend-control, source-operation,
  generation-variable, generation-loop, mask-lane-constant, backend-value, and
  backend-type public APIs.
- Source-owned raw token preservation and no source repair.

## Out Of Scope

Backend intrinsic translation results; backend modifier value translation;
backend maps, manifests, or language maps; generated output; C++/Rust
rendering; intrinsic-name validation; direct intrinsic name-template lowering;
direct intrinsic modifier parsing; intrinsic argument splitting; intrinsic
argument payload lowering; backend-control translation; source-operation
translation; declaration rendering; loop execution; primitive-call rendering;
body-token rendering policy; recursive discovery through arbitrary payload
contexts; broad TSIL expression parsing; target-language expression parsing;
source repair; dependency scheduling; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, plugin maps, worklists, or
per-modifier pipelines.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M182 stays a handoff from discovered
   intrinsic islands to typed unresolved intrinsic-modifier facts and does not
   add backend translation, rendering, parser, registry, dispatcher,
   worklist, or per-modifier pipelines.
2. Boundary auditor: verify M182 parses only top-level
   `intrin_compose<...>(...)` angle payload modifiers, preserves direct
   `intrin<...>(...)` names and argument payloads opaque, and reuses M181 only
   for exact single backend-value modifier values.
3. Evidence auditor: verify representative corpus forms and counts remain
   accurately cited and no non-corpus source form is treated as required.
4. Test auditor: verify tests cover modifier field forms, backend-value
   handoff values, unresolved operands, direct intrinsic preservation, body
   token/text preservation, diagnostics, raw request distinction, and no
   rendering/source repair.
5. Documentation auditor: verify roadmap, current state, inventories if
   touched, and next prompt are coherent after acceptance.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m181_backend_value_query_handoff.py tslgen/tests/test_m182_intrinsic_modifier_handoff.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m181_backend_value_query_handoff.py tslgen/tests/test_m182_intrinsic_modifier_handoff.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M182 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M182 accepted in `docs/redesign/implementation-roadmap.md`;
- update inventories or design docs only for accepted behavior or unavoidable
  follow-ups;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 183 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
