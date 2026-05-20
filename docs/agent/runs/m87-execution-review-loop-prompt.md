# M87 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 87.

Milestones 1 through 86 are accepted. Post-M86 planning is accepted and
selected:

```text
Milestone 87: Exact Return-Emission Structural Request IR Slice
```

Use the orchestrated executor-review loop in this prompt. M87 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start post-M87 planning until M87 review returns
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
- `tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_diagnostics.py`
- `tslgen/src/tslgen/lowering/_array_body_validation.py`
- `tslgen/src/tslgen/lowering/_exact_shapes.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Add the next lowering semantic frontier after the M77-M86 facade/module
cleanup: record the exact trailing return-emission-shaped slot from the
accepted exact array-body path as typed structural/request IR.

M87 recognizes only the exact source form shaped as `emit_return(tmp);` with
insignificant whitespace, links the returned token to the accepted M73
declaration-shell variable token, and keeps the result structural/request-only.

This is not a `.tsl` body repair milestone. If the source body is wrong,
nearby, malformed, or merely resembles the selected form, M87 must emit a
structured diagnostic instead of correcting or broadening the accepted shape.

## Scope

- Add a typed exact return-emission structural/request IR value, such as
  `ExactReturnEmissionStructuralRequestIr`, behind the private exact array-body
  lowering boundary.
- Consume accepted M74 `ExactArrayBodyStructuralSequenceIr` provenance and the
  accepted M76 post-branch intrinsic call-site structural request as typed
  inputs so the return-emission request is ordered after the accepted
  post-branch call-site path without interpreting store semantics.
- Recognize only the M74 role ordinal `4` /
  `opaque_return_emission_shaped_slot` source text with the exact
  `emit_return(<token>);` shape, allowing insignificant whitespace.
- Require the returned token text to match the accepted M73 declaration-shell
  variable token carried by the M74 sequence. This is provenance linkage only,
  not variable lifetime, allocation, or return-value semantics.
- Add a deterministic `return_emission_structural_request_lowering` stage after
  the accepted post-branch call-site stage in the exact array-body pipeline.
- Preserve public facade imports through `tslgen.lowering.boundary` and
  `tslgen.lowering` if new public aliases are exposed; otherwise keep new
  model/lowering helpers private and test the public pipeline result.
- Keep implementation cohesive. If existing exact array-body modules would grow
  into catch-all files or materially past the roughly 1,000-line guardrail,
  create a focused private return-emission module with one-way imports rather
  than adding a large new cluster to an already substantial file, or document
  why a temporary exception is safer.

## Out Of Scope

- Correcting, normalizing, rewriting, completing, reordering, or guessing the
  intended meaning of malformed `.tsl` implementation bodies.
- Supporting broad `emit_return(...)`, expressions inside `emit_return`,
  multiple return statements, missing semicolons, alternate variables,
  `tmp.data()`, stores, calls, direct `intrin<...>` semantics, variable
  lifetime/scope, allocation semantics, array value semantics, or return-value
  semantics.
- Backend translation, renderer-ready return IR, rendering, generated C++ or
  Rust output, generated tests, golden files, CLI/report/writer behavior,
  compiler execution, or generated-test execution.
- Broad TSIL parsing, source-file reads during lowering, catalog reads,
  `tsldata` reads, backend map reads, host CPU queries, runtime dependency on
  `frozen/`, registries, dispatchers, plugin systems, raw text rewrite
  engines, raw helper dispatch, or fixpoint/backfeed machinery.
- Moving unrelated request/result models, `LoweringInputSet`,
  `prepare_lowering_inputs`, `_lower_input`, `lower_candidates`, selected-body
  lowering, generation query/control-flow staging, or broad exact array-body
  orchestration out of `boundary.py`.

## Required Inputs

- Accepted M64-M65 exact array-body envelope and pipeline integration.
- Accepted M73 declaration-shell structural IR and declaration variable token.
- Accepted M74 source-ordered array-body structural sequence with role ordinal
  `4` / `opaque_return_emission_shaped_slot` provenance.
- Accepted M75 predicate-path and M76 post-branch call-site structural request
  values as typed ordering/provenance inputs.
- Accepted M84 exact array-body pipeline/source/lowering module boundaries and
  M86 public facade behavior.
- Corpus evidence:
  `tsldata/primitives/load_store/array.tsl:104-112`, especially the trailing
  `emit_return(tmp) ;` shape at line 111.

## Expected Outputs

- A typed exact return-emission structural/request IR value carrying:
  source sequence identity, post-branch call-site identity, return role label,
  slot ordinal `4`, source location, original source text, `emit_return` token,
  returned token text, declaration-shell variable-token link, candidate id,
  target extension, source extension, selected type tag, and branch-chain id.
- Deterministic key/provenance behavior matching accepted M74-M86 conventions.
- A pipeline stage snapshot entry for the exact return-emission structural
  request when the exact shape is present.
- Structured diagnostics for unsupported source, missing return slot, malformed
  return-emission shape, returned-token mismatch, context mismatch, and
  provenance mismatch.
- No backend/rendering/output artifacts and no semantic correction of source
  bodies.

## Required Executor Task

Run exactly one write-capable executor for M87. The executor should:

1. Implement the smallest coherent exact return-emission structural/request IR
   slice described above.
2. Add focused M87 tests for the exact accepted shape, returned-token
   provenance, negative diagnostics, stage insertion/order, key/source-location
   stability, selected-branch-only behavior, and import boundaries.
3. Preserve all accepted M64-M86 diagnostics, source locations, stage
   names/order, output identities, deterministic keys, selected-branch-only
   behavior, public imports, and pipeline snapshots.
4. Avoid source-body repair, broad `emit_return(...)`, return semantics,
   store/call semantics, `tmp.data()` semantics, backend/rendering/output
   behavior, generic dispatch, raw helper dispatch, fixpoint/backfeed
   machinery, and catch-all modules.
5. Run the required validation commands below.
6. Return a concise implementation summary, files changed, validation results,
   line counts, and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_array_body_models.py tslgen/src/tslgen/lowering/_array_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_diagnostics.py tslgen/src/tslgen/lowering/_array_body_validation.py tslgen/src/tslgen/lowering/_exact_shapes.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m87 or return_emission or exact_array_body_pipeline"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation creates a focused private return-emission module, include it
in the line-count, py-compile, and import-boundary validation, and update this
prompt, `docs/agent/current-redesign-state.md`, and the final report
consistently.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify M87 stays structural/request-only, consumes typed
   M74/M76 inputs, does not repair source bodies, does not broaden
   `emit_return(...)`, and does not add return/store/variable semantics,
   backend translation, rendering, generated output, raw helper dispatch,
   generic TSIL parsing, hardwiring, or catch-all modules.
3. Extensibility auditor: verify the staged lowering pipeline remains
   maintainable, module ownership is focused, import direction stays clean,
   and future stages can be added without registries, dispatchers, broad
   protocols, callback injection, hidden backfeeds, or fixpoint machinery.
4. Validation auditor: verify required commands ran, exact results are
   recorded, line counts are reported, and tests cover the declared M87 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale post-M86 handoff wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M87 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M87
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M87 result

Record:

- M87 accepted status and review verdict.
- Files changed.
- Line counts for touched lowering modules.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m87-planning-plus-review-prompt.md
```

The post-M87 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M88 unless that future prompt explicitly
selects an executor task.

Do not start post-M87 planning in this prompt.

## Final Report

Report:

1. Files changed.
2. Implementation summary.
3. Review/audit verdicts and follow-ups.
4. Validation commands and exact results.
5. State transition made.
6. Next concrete prompt path created.
