# M88 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 88.

Milestones 1 through 87 are accepted. Post-M87 planning is accepted and
selected:

```text
Milestone 88: Exact Array Body Structural Package Assembly Slice
```

Use the orchestrated executor-review loop in this prompt. M88 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M88 planning until M88 review returns
`Accept` or `Accept With Follow-Ups`.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/agent/subagents/`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/generation-time-semantic-lowering.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/open-questions.md`
- `tsldata/primitives/load_store/array.tsl`
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_array_body_models.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_return_emission.py`
- `tslgen/src/tslgen/lowering/_pipeline.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Assemble accepted exact array-body structural/request facts into one typed,
source-ordered structural package for the selected `array.tsl:105-111` body
shape.

M88 turns the accepted M64-M87 exact array-body facts into one coherent Stage 8
handoff while preserving their structural-only meaning. It must not claim that
the array body is semantically lowered.

## Scope

- Add a typed exact array-body structural package value, such as
  `ExactArrayBodyStructuralPackageIr`, behind a focused private lowering
  ownership boundary.
- Prefer a focused private module such as
  `tslgen.lowering._array_body_package` for package assembly, source
  selection, and package-specific diagnostics rather than growing central exact
  array-body modules into catch-all files.
- Consume accepted typed facts only:
  M64/M65 exact array-body envelope state, M72 helper-set completion, M73
  declaration-shell structural IR, M74 source-ordered structural sequence,
  M75 predicate-path structural request, M76 post-branch intrinsic call-site
  structural request, and M87 return-emission structural request.
- Validate that the package members belong to the same candidate, source
  envelope/sequence, branch path, target extension, source extension, selected
  type tag, and source-ordered exact body.
- Preserve object identity/provenance for the packaged member facts instead of
  copying or normalizing them into semantic body nodes.
- Add one deterministic package-assembly stage after
  `return_emission_structural_request_lowering`, such as
  `array_body_structural_package_assembly`.
- Preserve public facade imports through `tslgen.lowering.boundary` and
  `tslgen.lowering` if a new public alias is exposed; otherwise keep the new
  helper private and test the public pipeline result.

## Out Of Scope

- Correcting, normalizing, rewriting, completing, reordering, reparsing, or
  guessing intended meaning for malformed `.tsl` implementation bodies.
- Broad TSIL parsing, generic body IR, generic statement packages, source-body
  repair, raw helper dispatch, registries, callback maps, plugin systems,
  dispatch tables keyed by raw text, or fixpoint/backfeed machinery.
- Declaration semantics, array semantics, variable lifetime/scope, allocation
  semantics, initializer behavior, store semantics, return-value semantics,
  `tmp.data()` pointer semantics, `emit_return` semantics, `assume_aligned`
  semantics, `intrin<svst1>` semantics, SVE predicate/vector/register
  semantics, memory behavior, or broad direct-intrinsic semantics.
- Backend uninit translation, backend map reads, backend translation, renderer-
  ready IR, rendering, generated C++ or Rust output, generated tests,
  CLI/report/writer behavior, compiler execution, catalog reads during
  lowering, `tsldata` reads during lowering evaluation, host CPU queries, or
  runtime dependency on `frozen/`.
- Moving unrelated request/result models, `LoweringInputSet`,
  `prepare_lowering_inputs`, `_lower_input`, `lower_candidates`, selected-body
  lowering, generation query/control-flow staging, or broad exact array-body
  orchestration out of `boundary.py`.

## Required Inputs

- Accepted M64/M65 exact array-body envelope and pipeline integration.
- Accepted M72 array-initialization helper-set completion, including the
  deferred `value<backend>(uninit::array)` backend-value boundary as data only.
- Accepted M73 declaration-shell structural IR and declaration variable token.
- Accepted M74 source-ordered array-body structural sequence.
- Accepted M75 predicate-path structural request.
- Accepted M76 post-branch intrinsic call-site structural request.
- Accepted M87 return-emission structural request.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:105-111`.

## Expected Outputs

- A typed exact array-body structural package value carrying stable package
  identity, source location/provenance, candidate id, target extension, source
  extension, selected type tag, branch-chain id, source sequence identity, and
  references to the accepted member facts.
- A source-ordered package member sequence that preserves the accepted exact
  declaration, predicate path, selected-body/predicate update evidence,
  post-branch call-site, and return-emission structural/request facts.
- Deterministic key/provenance behavior matching accepted M64-M87 conventions.
- A pipeline stage snapshot entry for the package-assembly stage.
- Structured diagnostics for unsupported source, missing member facts,
  duplicate member facts, source/order mismatch, context mismatch, and
  provenance mismatch.

## Required Executor Task

Run exactly one write-capable executor for M88. The executor should:

1. Implement the smallest coherent exact array-body structural package assembly
   slice described above.
2. Add focused M88 tests for positive package assembly, source-ordered member
   identity/provenance, missing/duplicate/mismatched/out-of-order/provenance
   diagnostics, deterministic keys, stage order after M87, selected-branch-only
   behavior, pipeline snapshots, and import boundaries.
3. Preserve all accepted M64-M87 diagnostics, source locations, stage
   names/order, output identities, deterministic keys, selected-branch-only
   behavior, public imports, and pipeline snapshots.
4. Avoid source-body repair, semantic body lowering, broad TSIL parsing,
   return/store/declaration/array/SVE/backend/rendering/output behavior,
   generic dispatch, raw helper dispatch, broad protocols, fixpoint/backfeed
   machinery, and catch-all modules.
5. Run the required validation commands below.
6. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_return_emission.py tslgen/src/tslgen/lowering/_array_body_package.py tslgen/src/tslgen/lowering/_pipeline.py tslgen/src/tslgen/lowering/_stage_contracts.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m88 or structural_package or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses a different focused private package module name,
include that file consistently in the line-count, py-compile, and
import-boundary validation, and update this prompt,
`docs/agent/current-redesign-state.md`, and the final report consistently.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M88 stays structural package assembly only,
   consumes accepted typed M64-M87 facts, does not repair source bodies, and
   does not add body/declaration/store/return/SVE/backend/rendering/output
   semantics, raw helper dispatch, generic TSIL parsing, hardwiring, or
   catch-all modules.
3. Extensibility auditor: verify the staged lowering pipeline remains
   maintainable, focused package ownership is cohesive, import direction stays
   clean, and future stages can consume one package without broad protocols,
   registries, dispatchers, callback injection, hidden backfeeds, or fixpoint
   machinery.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M88 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M87 handoff wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M88 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M88
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M88 result

Record:

- M88 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m88-planning-plus-review-prompt.md
```

The post-M88 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M89 unless that future prompt explicitly
selects an executor task.

Do not start post-M88 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
