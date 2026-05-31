# M178 Source-Owned Request Island Scanner Consolidation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M177 as accepted.

You are executing and reviewing:

```text
Milestone 178: Source-Owned Request Island Scanner Consolidation
```

Milestones 1 through 177 are accepted. M164, M166, M167, and M177 now contain
several exact request-island discoverers with repeated balanced-delimiter,
source-location, and raw-token-run mechanics. M178 should consolidate those
mechanics without adding new lowering semantics.

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
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/backend_intrinsics.py`
- `tslgen/src/tslgen/lowering/source_operations.py`
- `tslgen/src/tslgen/lowering/mask_lane_constants.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m164_backend_value_queries.py`
- `tslgen/tests/test_m166_backend_intrinsics.py`
- `tslgen/tests/test_m167_source_operations.py`
- `tslgen/tests/test_m177_mask_lane_constant_requests.py`

## Goal

Extract one small, lowering-owned source-island scanner utility for the shared
mechanics behind accepted exact request-island discovery:

- quote/escape-aware balanced delimiter matching;
- source-at-offset mapping;
- contiguous `RawStringToken` run joining with per-character source mapping;
- stable opaque text/token preservation around typed request segments.

This is a behavior-preserving lowering refactor. It should make future exact
keyword/request slices less copy-heavy while preserving every accepted
diagnostic and boundary.

## Required Executor Task

Run exactly one write-capable executor for M178. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add a focused private helper module or class for source-island scanning
   mechanics. Keep it concrete and small; do not add a registry, plugin map,
   dispatcher framework, callback system, worklist, or generic TSIL parser.
3. Refactor the already accepted discoverers to use the helper where behavior
   remains identical:
   - `value<backend>(...)` backend value queries from M164;
   - `intrin<...>(...)` and `intrin_compose<...>(...)` backend intrinsic
     requests from M166;
   - `cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)` source-operation
     requests from M167;
   - exact mask lane constant requests from M177.
4. Leave each domain-specific module responsible for its own accepted head
   names, payload validation, typed request object construction, and
   diagnostic codes/messages.
5. Preserve public imports and `Lowerer` method behavior.
6. Preserve accepted source behavior exactly: no new keyword forms, no broader
   whitespace acceptance, no source repair, no renderer-ready IR, no backend
   translation, no backend helper text, and no expression parsing.
7. Add or update focused tests only as needed to prove the refactor did not
   change behavior and that the shared helper is covered at its boundary.
8. Update redesign docs only if implementation reveals a sharper
   maintainability boundary or a deliberately unmigrated discoverer.
9. Leave final accepted-state updates to the orchestrator after read-only
   review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- This is lowering infrastructure cleanup, not new semantics.
- The helper must own mechanics, not meaning. It must not know what
  `value<backend>`, `intrin`, `cast`, `mem`, `io`, or `mask::lane` mean.
- Do not centralize request construction into a registry or generic rule
  engine.
- Do not parse surrounding primitive calls, declarations, assignments, loops,
  branch bodies, or target-language expressions.
- Do not change `.tsl` source conventions.
- Do not make `frozen`, `tslgenold`, or runtime `tsldata` a runtime
  dependency.

## Must Preserve

- M164 backend value query request discovery behavior and diagnostics.
- M166 backend intrinsic request discovery behavior and diagnostics.
- M167 source-operation request discovery behavior and diagnostics.
- M177 mask lane constant request discovery behavior and diagnostics.
- Existing source-owned raw token preservation and no source repair.
- Existing materialized generation value behavior.

## Out Of Scope

New TSIL keywords; broad TSIL grammar; operator parsing; primitive-call
rendering; declaration rendering; backend helper rendering; backend value/type
translation; branch selection; loop execution; source replacement; output
writing; dependency scheduling; runtime `tsldata`, `frozen`, or `tslgenold`
dependencies; registries, dispatchers, callback maps, hidden backfeeds, or
worklists.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M178 is behavior-preserving lowering
   infrastructure cleanup and does not create a generic parser/registry.
2. Boundary auditor: verify M164/M166/M167/M177 source behavior, diagnostics,
   public imports, and typed request boundaries are preserved.
3. Test auditor: verify regression tests cover all migrated discoverers and
   the shared helper boundary without adding new semantics.
4. Documentation auditor: verify docs, roadmap, current state, and next prompt
   are coherent.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m167_source_operations.py tslgen/tests/test_m177_mask_lane_constant_requests.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m167_source_operations.py tslgen/tests/test_m177_mask_lane_constant_requests.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before the final cache
check if any are created.

## Completion Rules

If M178 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M178 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt.

Do not start Milestone 179 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
