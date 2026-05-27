# M138 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M137:

```text
Milestone 138: Primitive Call Target Reference Diagnostic Boundary Slice
```

Milestones 1 through 137 are accepted. M135 gives recognized
`call<primitive=...>(...)` tokens structured selector data, M136 adds
structured raw argument records, and M137 makes unsupported primitive-call
diagnostics report that structured context plus the missing primitive-call
dependency-resolution capability. M138 should perform only the next narrow
reference-classification step: identify whether the base call target names a
catalog primitive or the currently selected primitive via `@self`, while
treating specialization and `attrs[...]` as target-reference dimensions that
remain unresolved unless a later milestone explicitly evaluates them.

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
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Recognized primitive-call tokens should distinguish these cases without
starting dependency closure:

- `call<primitive=@self>(...)` identifies the currently selected primitive as
  the base target;
- `call<primitive=NAME>(...)` checks whether `NAME` exists as a primitive in
  the already built catalog;
- `call<primitive=@self[...]>(...)`, `call<primitive=NAME[...]>(...)`,
  `call<primitive=@self attrs[...]>(...)`, `call<primitive=NAME attrs[...]>(...)`,
  and the combined specialization-plus-attrs forms classify the base target
  and report that specialization-specific and/or attribute-specific target
  reference resolution is not implemented yet;
- unknown named base targets produce a precise diagnostic at the
  primitive-call source, while still preserving specialization and attrs as
  opaque diagnostic context;
- known base targets and `@self` targets remain unsupported until a later
  dependency implementation selection/lowering slice, and their diagnostic
  should distinguish base-target identity from unresolved specialization,
  unresolved attrs, and the missing dependency implementation
  selection/lowering capability.

This is still a lowering diagnostic boundary. It must not choose dependency
implementations, lower dependency bodies, expand dependency closure, interpret
attributes, interpret specialization, interpret arguments, recursively lower
nested calls, or render backend call text.

## Required Executor Task

Run exactly one write-capable executor for M138. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep parser syntax, M129/M130 directive classification, M132 call-island
   recognition, M134 emit-return payload-token behavior, M135 selector
   representation, M136 argument-list representation, M137 diagnostic context,
   and M133/M134 exact add-call lowering stable unless a focused test exposes
   a defect.
3. Use the clean restart catalog and selected implementation context to
   classify exact primitive-call target references. Prefer a small direct
   object/API change over a new request/result/worklist family. If the lowerer
   is called without catalog context, preserve the M137 diagnostic fallback.
4. For named primitive calls, look up only the structured base target name in
   the catalog. Specialization and `attrs[...]` payloads remain opaque, but
   their presence must be reported as unresolved target-reference dimensions,
   not silently ignored.
5. For `@self` calls, identify the currently selected primitive as the base
   target identity without expanding `@self` into a dependency closure.
6. Add a stable diagnostic code for missing named call targets, expected to be
   `TSL-LOWER-UNKNOWN-PRIMITIVE-CALL-TARGET` unless a focused implementation
   reason justifies a different code. Keep
   `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` for known targets that remain
   unsupported.
7. For known base targets with specialization and/or attrs, keep
   `TSL-LOWER-UNSUPPORTED-PRIMITIVE-CALL` and report that the base target is
   known, while specialization-specific and/or attribute-specific target
   reference resolution is not implemented yet.
8. Preserve structured M137 context in both missing-target and known-target
   diagnostics, including target kind, target name where applicable, selector
   source text, optional opaque specialization and attrs payloads, raw
   argument count/payloads, and opaque original payload.
9. Report target-reference classification for both standalone primitive-call
   body tokens and `emit_return(...)` payload primitive-call tokens.
10. Preserve existing diagnostics for raw `emit_return(left)`,
   raw-plus-call payloads, malformed call selectors, malformed call arguments,
   non-call raw bodies, non-call directives, and exact add-call artifacts.
11. Add focused tests for:
    - known named primitive targets;
    - unknown named primitive targets;
    - `@self` base target identity;
    - known named targets with specialization payloads;
    - known named targets with `attrs[...]` payloads;
    - known named targets with both specialization and `attrs[...]`;
    - unknown named base targets with specialization and/or `attrs[...]`;
    - `@self` with specialization and/or `attrs[...]`;
    - zero-argument calls;
    - nested raw argument payloads;
    - `emit_return(call<primitive=...>(...));` payload calls;
    - exact source locations;
    - exact add-call artifact stability;
    - existing M126-M137 diagnostics and artifact-byte stability.
12. Resolve the M137 documentation follow-up by updating the older
    implementation-body domain-model sketch to show the accepted
    `primitive_call` and `payload_tokens` fields, while keeping the sketch
    concise.
13. Update redesign docs if diagnostic behavior, pipeline context, or
    boundaries are clarified.

## Out Of Scope

Primitive dependency closure; selecting dependency implementations; lowering
dependency bodies; rendering backend call text; expanding `@self` beyond base
target identity; interpreting selector specialization or `attrs[...]`;
resolving argument identifiers; recursively lowering argument expressions;
expression parsing; assignment or array-access lowering; source repair;
complete TSIL grammar; runtime `tsldata` semantic lookup; `frozen` or
`tslgenold` runtime dependency; registries; dispatchers; hidden backfeeds;
fixpoint mechanisms; or new request/result/worklist families.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M138 changes only the primitive-call target
   reference diagnostic boundary and preserves M133/M134 exact add-call
   lowering plus M135-M137 representation/diagnostic behavior. It must not
   introduce dependency closure, dependency implementation selection, `@self`
   expansion beyond base target identity, expression parsing, recursive
   argument lowering, backend call rendering, renderer inference, or broad IR
   machinery.
2. Boundary auditor: verify no `frozen`, `tslgenold`, or runtime `tsldata`
   shortcut is used; verify base-target catalog lookup is exact by primitive
   name only; verify specialization, attrs, arguments, nested calls, and
   payload text remain opaque and are not interpreted as successful
   specialization/attribute resolution.
3. Documentation auditor: verify behavior docs, domain model sketch, and
   roadmap accurately describe M138 and preserve M128-M137 boundaries.
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

If M138 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M138 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M138 is accepted. Select exactly one concrete M139 task focused on
lowering from recognized TSIL body-token islands and grounded in the M127
inventory plus the M128-M138 body-intake/body-token/lowering results. Do not
create a separate post-M138 planning prompt unless review returns
`Return To Planner`, `Reject`, or an explicit stop condition is recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 139 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
