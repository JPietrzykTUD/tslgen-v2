# M139 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M138:

```text
Milestone 139: Unspecialized Primitive Call Implementation Candidate Diagnostic Boundary Slice
```

Milestones 1 through 138 are accepted. M135 gives recognized
`call<primitive=...>(...)` tokens structured selector data, M136 adds
structured raw argument records, M137 reports unsupported primitive-call
diagnostics from that structured context, and M138 classifies base target
references against the already built clean restart catalog. M139 should perform
only the next narrow candidate-existence step for calls whose target selector
has no specialization and no `attrs[...]`.

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
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/pipeline/generator.py`
- `tslgen/src/tslgen/pipeline/_tsil_primitive_calls.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/primitive_call_diagnostics.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognized primitive-call tokens should distinguish one more boundary without
starting dependency closure:

- `call<primitive=NAME>(...)` with no specialization and no `attrs[...]`
  checks whether the already known base target primitive has an implementation
  candidate matching the currently selected implementation's extension and
  type tag;
- `call<primitive=@self>(...)` with no specialization and no `attrs[...]`
  identifies the current selected implementation as the candidate boundary;
- if a candidate exists, the diagnostic remains
  `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL`, but it should say that the
  dependency implementation candidate exists and that dependency call
  lowering/rendering is not implemented yet;
- if a named base target exists but has no matching implementation candidate,
  produce a precise diagnostic at the primitive-call source;
- unknown named base targets keep the M138
  `TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET` behavior;
- calls with specialization and/or `attrs[...]` keep the M138 unresolved
  target-reference-dimension behavior and must not run the candidate lookup.

This is still a lowering diagnostic boundary. Candidate lookup means an exact
catalog inspection for the current selected context, not dependency closure,
not dependency implementation selection into the generation plan, not
dependency body lowering, and not backend call rendering.

## Required Executor Task

Run exactly one write-capable executor for M139. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 call-island
   recognition, M134 emit-return payload-token behavior, M135 selector
   representation, M136 argument-list representation, M137 diagnostic context,
   M138 target-reference classification, and M133/M134 exact add-call lowering
   stable unless a focused test exposes a defect.
3. Use only the clean restart catalog and selected implementation context.
   Prefer a small direct helper or focused module over a new
   request/result/worklist family.
4. For known named primitive calls with no specialization and no attrs, check
   candidate existence by exact base primitive name, current selected
   implementation extension, and current selected implementation type tag.
   Do not consider backend maps, flags, hardware, dependency closure, or
   argument payloads.
5. For `@self` calls with no specialization and no attrs, report the current
   selected implementation as the candidate identity without expanding `@self`
   into a recursive dependency.
6. For known base targets with specialization and/or attrs, preserve the M138
   unresolved specialization-specific and/or attribute-specific
   target-reference diagnostic behavior. Do not attempt a candidate lookup for
   those calls.
7. For unknown named base targets, preserve the M138
   `TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET` diagnostic and structured
   context.
8. Add a stable diagnostic code for known target but missing implementation
   candidate, expected to be
   `TSL-LOWER-NO-PRIMITIVE-CALL-IMPLEMENTATION` unless a focused
   implementation reason justifies a different code.
9. Preserve structured context in diagnostics: target kind, target name where
   applicable, selector source text, optional opaque specialization and attrs
   payloads, raw argument count/payloads, opaque original payload, and the
   candidate lookup coordinate when candidate lookup is attempted.
10. Apply the candidate diagnostic boundary to both standalone primitive-call
    body tokens and `emit_return(...)` payload primitive-call tokens.
11. Preserve existing diagnostics for raw `emit_return(left)`, raw-plus-call
    payloads, malformed call selectors, malformed call arguments, non-call raw
    bodies, non-call directives, exact add-call artifacts, direct lowerer calls
    without catalog context, unknown named targets, and specialized/attrs
    target-reference diagnostics.
12. Add focused tests for:
    - known named unspecialized target with a matching candidate;
    - known named unspecialized target with no matching candidate;
    - `@self` unspecialized candidate identity;
    - candidate diagnostics inside `emit_return(call<primitive=...>(...));`;
    - exact source locations for candidate-exists and missing-candidate paths;
    - preservation of M138 unknown-target diagnostics;
    - preservation of M138 specialization-only, attrs-only, and combined
      specialization-plus-attrs diagnostics;
    - direct lowerer no-catalog fallback;
    - exact add-call artifact stability.
13. Update redesign docs if diagnostic behavior, pipeline context, or
    boundaries are clarified.

## Out Of Scope

Primitive dependency closure; adding dependency implementations to the selected
generation plan; lowering dependency bodies; rendering backend call text;
expanding `@self` beyond current candidate identity; interpreting selector
specialization or `attrs[...]`; resolving argument identifiers; recursively
lowering argument expressions; expression parsing; assignment or array-access
lowering; source repair; complete TSIL grammar; runtime `tsldata` semantic
lookup; `frozen` or `tslgenold` runtime dependency; registries; dispatchers;
hidden backfeeds; fixpoint mechanisms; or new request/result/worklist
families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M139 changes only the unspecialized
   primitive-call implementation-candidate diagnostic boundary and preserves
   M133/M134 exact add-call lowering plus M135-M138 representation/diagnostic
   behavior. It must not introduce dependency closure, selected dependency
   worklists, dependency body lowering, `@self` expansion beyond current
   candidate identity, expression parsing, recursive argument lowering,
   backend call rendering, renderer inference, or broad IR machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify candidate lookup is exact by base primitive name,
   current selected extension, and current selected implementation type tag
   only; verify specialization, attrs, arguments, nested calls, and payload
   text remain opaque and are not interpreted.
3. Documentation auditor: verify behavior docs, roadmap, and state accurately
   describe M139 and preserve M128-M138 boundaries.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M139 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M139 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M139 is accepted. Select exactly one concrete M140 task focused on
lowering from recognized TSIL body-token islands and grounded in the M127
inventory plus the M128-M139 body-intake/body-token/lowering results. Do not
create a separate post-M139 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 140 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
