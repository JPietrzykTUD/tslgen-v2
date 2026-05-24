# M101 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 101.

Milestones 1 through 100 are accepted. Post-M100 planning is accepted and
selected:

```text
Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice
```

Use the orchestrated executor-review loop in this prompt. M101 is an
implementation/documentation milestone; one write-capable executor may
implement the selected consolidation slice. Do not start post-M101 planning
until M101 review returns `Accept` or `Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_lowering_stage_assembly.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py`
- `tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py`
- `tslgen/tests/unit/test_lowering_backend_translation_result.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Define and enforce a smaller lowering IR taxonomy contract, then apply it only
to the accepted M99/M100 backend-translation request/result path. M101 should
reduce repeated provenance and one-off request/result layering without changing
observable lowering behavior or adding new backend semantics.

For M101, "IR taxonomy contract" means stable categories:

- semantic fact;
- request;
- result;
- inventory;
- provenance value;
- rule input;
- stage envelope.

It does not mean a broad inheritance hierarchy, a generic semantic dispatcher,
a registry, a callback system, a plugin mechanism, a fixpoint system, or a
rewrite of every existing lowering IR class.

## Scope

- Preserve accepted M99/M100 behavior while reducing repeated
  request/result/provenance shape where safe.
- Add focused private lowering ownership if implementation needs a small shared
  contract/provenance module. Keep it behavior-neutral and narrowly applied.
- Apply the contract only to the accepted M99/M100 backend-translation
  request/result path, especially repeated candidate/source-location/
  provenance and object-identity validation patterns.
- Preserve accepted M99/M100 public imports, stage names, stage ordering, keys,
  diagnostics, source locations, object identities where required, and
  deterministic ordering.
- Keep `boundary.py` as a narrow facade; do not add more orchestration there.
- Prefer focused tests in an M99/M100-specific test module rather than adding
  broad coverage to `test_lowering_boundary.py`.
- Update redesign docs if the implementation clarifies the taxonomy contract
  or records a blocker.

## Out Of Scope

- New lowering semantics, new request families, new translation result
  families, C++ declaration/body assembly, Rust translation, generic
  `value<backend>(...)` or `type<backend>(...)` evaluation, backend
  map/catalog/manifest reads during lowering, backend support decisions,
  Stage 9 backend planning, rendering, generated output, operation scheduling,
  dependency closure, wrapper planning, artifact planning, CLI/report/writer
  behavior, compiler execution, or host hardware dependency.
- Raw `.tsl` source parsing, source-body reparsing, source repair,
  source normalization, best-effort correction, broad TSIL/body parsing,
  selected-body direct-intrinsic resolution, SVE/direct-intrinsic semantics,
  byte-size-to-token inference, or vector/register metadata expansion.
- Broad base-class hierarchy imposed across M57-M100 IR, a new registry,
  dispatcher, callback map, plugin mechanism, hidden backfeed, or fixpoint
  machinery.

## Required Executor Task

Run exactly one write-capable executor for M101. The executor should:

1. Inspect the accepted M99/M100 backend-translation request/result modules and
   identify repeated taxonomy/provenance shape.
2. Add the smallest shared contract/provenance structure that reduces repeated
   shape without weakening diagnostics, object identity, or deterministic keys,
   or document why consolidation is unsafe.
3. Apply the shared contract only to the M99/M100 backend-translation
   request/result path.
4. Preserve all accepted public imports, stage names, ordering, keys,
   diagnostics, source locations, object identities where required, and
   deterministic behavior.
5. Add focused tests for behavior preservation, diagnostics, determinism,
   object identity, import boundaries, and line-count guardrails.
6. Avoid all out-of-scope backend, rendering, output, source-repair, raw-body
   parsing, registry/dispatcher, broad-hierarchy, hidden-backfeed, fixpoint,
   and semantic-expansion behavior.
7. Run the required validation commands below.
8. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

If the executor discovers that the M99/M100 path cannot be consolidated without
semantic risk, stop implementation, record the blocker in
`docs/redesign/open-questions.md`, and return `Return To Planner` with a
planning-revision prompt.

## Required Tests

- Focused regression tests for M99 backend-translation request inventory and
  M100 exact-array C++ backend-uninit translation-result behavior.
- Determinism tests proving result keys and ordering remain stable before and
  after consolidation.
- Diagnostic tests proving source/container, provenance mismatch, context
  mismatch, source-location mismatch, missing/duplicate/conflicting rule,
  unsupported backend, and wrong request-kind diagnostics remain stable.
- Import-boundary tests proving any new contract/provenance module does not
  import `boundary.py`, the `tslgen.lowering` facade, backend modules,
  renderers, backend planners, `tsldata`, or `frozen`.
- Line-count tests or source assertions proving the consolidation does not grow
  `boundary.py`, M99/M100 modules, or `_lowering_stage_assembly.py` into a new
  monolith.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_lowering_stage_assembly.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_inventory.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_request_diagnostics.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_sources.py tslgen/src/tslgen/lowering/_lowering_backend_translation_result_diagnostics.py tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_backend_translation_result.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m99 or backend_translation_request_inventory or exact_array_backend_uninit_translation_result or m100 or m101"
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering tslgen/tests/unit/test_lowering_backend_translation_result.py
git diff --check
```

If implementation creates a new contract/provenance module, include that file
in line-count, py-compile, import-boundary tests, and final reporting.

Run broader validation if shared lowering behavior changes beyond the
M99/M100 path:

```bash
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
```

## Required Subagents

After the executor completes, use read-only subagents:

1. Reviewer: review the implementation against this prompt, `AGENTS.md`,
   `PLANS.md`, `docs/agent/review-checklist.md`, and the roadmap. Return
   `Accept`, `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`,
   or `Reject`.
2. Boundary auditor: verify no new backend semantics, no backend map/catalog/
   manifest reads during lowering, no raw helper parsing, no source repair, no
   renderer inference, no Stage 9 planning, no rendering/output, no Rust, no
   generic backend helper evaluation, and no direct-intrinsic/SVE semantics.
3. Extensibility auditor: verify the taxonomy/provenance contract reduces
   repeated shape without creating a broad hierarchy, registry, dispatcher,
   callback system, plugin mechanism, hidden backfeed, fixpoint system, or
   replacement monolith.
4. Validation auditor: verify tests and validation results, including
   diagnostics, determinism, object identity, import boundaries, line counts,
   and mypy.
5. Documentation auditor: verify roadmap/state/design docs and
   `docs/redesign/missing-lowering-inventory.md` reflect M101 accurately.

## Review Loop

The main thread is the orchestrator.

- If all reviews return `Accept`, mark M101 accepted, update
  `docs/agent/current-redesign-state.md`, update any needed redesign docs, and
  create `docs/agent/runs/post-m101-planning-plus-review-prompt.md`.
- If reviews return `Accept With Follow-Ups`, record non-blocking follow-ups,
  mark M101 accepted, update state/docs, and create the post-M101 planning
  prompt.
- If any review returns `Needs Revision`, run one focused write-capable
  revision executor limited to the blocking issues, then run focused re-review.
- If any review returns `Return To Planner`, stop implementation, update state,
  and create an appropriate post-M101 planning-revision prompt.
- If any review returns `Reject`, stop implementation, update state, and create
  an appropriate rollback/redesign prompt.

Only one write-capable executor or revision executor may modify a worktree at
a time. Review and audit subagents are read-only unless the orchestrator later
creates a focused revision task.

## Finalization Rules

On `Accept` or `Accept With Follow-Ups`, before finishing:

- update `docs/agent/current-redesign-state.md`;
- update `docs/redesign/implementation-roadmap.md` and any other redesign docs
  needed to record accepted M101 behavior and validation;
- update `docs/redesign/missing-lowering-inventory.md` if M101 narrows or
  resolves an IR-taxonomy/provenance gap;
- create the next concrete run prompt under `docs/agent/runs/`;
- run the final `git diff --check`.

Do not start Milestone 102 or post-M101 implementation work.

## Final Report

Report:

1. Implementation summary.
2. Review verdict and subagent verdicts.
3. Files changed.
4. Follow-ups recorded, if any.
5. Validation commands and exact results.
6. Next concrete run prompt created.
