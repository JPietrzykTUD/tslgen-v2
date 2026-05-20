# M86 Execution Review Loop Prompt

You are executing and reviewing the accepted Milestone 86.

Milestones 1 through 85 are accepted. Post-M85 planning is accepted and
selected:

```text
Milestone 86: Candidate Payload Intake And Mini-TSIL Leaf Lowering Extraction Slice
```

Use the orchestrated executor-review loop in this prompt. M86 is an
implementation milestone; one write-capable executor may implement the
selected slice. Do not start M87.

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
- `tslgen/src/tslgen/lowering/boundary.py`
- `tslgen/src/tslgen/lowering/_stage_contracts.py`
- `tslgen/src/tslgen/lowering/_generation_models.py`
- `tslgen/src/tslgen/lowering/_generation_queries.py`
- `tslgen/src/tslgen/lowering/_generation_control_flow.py`
- `tslgen/src/tslgen/lowering/_generation_diagnostics.py`
- `tslgen/src/tslgen/lowering/_selected_body_lowering.py`
- `tslgen/src/tslgen/lowering/_array_body_pipeline.py`
- `tslgen/src/tslgen/lowering/_array_body_sources.py`
- `tslgen/src/tslgen/lowering/_array_body_lowering.py`
- `tslgen/src/tslgen/lowering/__init__.py`
- `tslgen/tests/unit/test_lowering_boundary.py`

## Goal

Move the accepted candidate payload-intake helpers and accepted mini-TSIL leaf
return lowering implementation out of `tslgen/src/tslgen/lowering/boundary.py`
into focused private typed lowering modules while preserving all accepted
M42-M85 behavior, public imports, diagnostics, source locations, stage
names/order, output identities, deterministic keys, selected-branch-only
behavior, pipeline snapshots, and no-external-input boundaries.

M86 is behavior-preserving lowering architecture work. It broadens the
`boundary.py` refactor beyond only mini-TSIL regex movement, but it remains one
cohesive ownership slice: candidate payload intake plus the leaf mini-TSIL
return lowerer that consumes that intake. It should make `boundary.py` closer
to a true facade/coordinator without moving central `_lower_input`
orchestration or adding new semantic lowering.

## Scope

- Create a focused private payload-intake module such as
  `tslgen.lowering._lowering_inputs`.
- Move the accepted payload-intake value/helper cluster out of `boundary.py`:
  `LoweringStrategy`, `PayloadClassification`, `ClassifiedPayload`,
  `LoweringInput`, `_classify_payload`, and
  `_unsupported_payload_diagnostic`.
- Preserve public facade imports and calls through `tslgen.lowering.boundary`
  and `tslgen.lowering` by re-exporting or tiny delegating from the facade.
- Keep `LoweringInputSet`, `LoweringRequest`, `GenerationContext`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, and `_lower_input` facade-owned.
- Create a focused private mini-TSIL leaf-lowering module such as
  `tslgen.lowering._mini_tsil_lowering`.
- Move the accepted mini-TSIL leaf return-lowering cluster out of
  `boundary.py`: the direct parameter-add return regex/helper, the
  `intrin_compose<add>` return regex/helper, mini-TSIL identifier validation,
  argument splitting, declared-parameter validation, and the accepted
  mini-TSIL diagnostics.
- Preserve accepted mini-TSIL behavior exactly:
  `emit_return(<parameter> + <parameter>);` and
  `emit_return(intrin_compose<add>(<parameter>, <parameter>));` remain the only
  semantically lowered mini-TSIL statement shapes.
- Preserve the intended import direction:
  `boundary.py -> _lowering_inputs`,
  `boundary.py -> _mini_tsil_lowering`,
  `_mini_tsil_lowering -> _lowering_inputs and _stage_contracts`, and
  `_lowering_inputs -> candidates, diagnostics, result, values` only.
- `_lower_input` may only delegate the accepted payload-classification and
  mini-TSIL leaf return-lowering calls to focused private helpers while
  preserving the existing call order, diagnostics, and stage construction.
- Record the post-M86 `boundary.py` line count measured against the accepted
  M85 1,417-line baseline.

## Out Of Scope

- Moving `LoweringInputSet`, `LoweringRequest`, `GenerationContext`,
  `LoweredImplementation`, `LoweringPlan`, `prepare_lowering_inputs`,
  `lower_candidates`, `_lower_input`, stage construction,
  `_context_for_candidate`, generation query payload lowering, generation
  control-flow pruning, selected-body lowering, exact array-body lowering,
  exact array-body pipeline orchestration, request/result model ownership, or
  package-level public surface policy beyond stable facade aliases.
- New lowering semantics, new mini-TSIL syntax, broad TSIL parsing, broad
  statement/body/call/store/return/declaration/array semantics,
  exact return-emission IR, `emit_return(tmp)` interpretation, `tmp.data()`
  semantics, variable scope/lifetime semantics, renderer-ready IR, broad
  direct-intrinsic semantics, helper-family expansion, or stage output changes.
- Creating registries, generic dispatchers, plugin systems, callback maps,
  ordered lowerer tables, generic TSIL statement dispatchers,
  fixpoint/backfeed engines, raw text rewrite engines, raw helper dispatch,
  token-keyed semantic maps, broad source-adapter protocols, or a mini-TSIL
  framework.
- Treating selected literals, SVE-looking tokens, selected type tags, backend
  ids, renderer names, corpus line numbers, request ordinals, or raw source
  text as semantic dispatch keys. Existing exact tokens may remain structural
  provenance or invariant evidence only.
- Backend translation, rendering, generated output, golden files, generated
  tests, CLI/report/writer behavior, Rust behavior, compiler execution,
  generated-test execution, lowering-time file/catalog reads, `tsldata` reads
  during lowering evaluation, host CPU queries, backend map reads, or runtime
  dependency on `frozen/`.
- Starting M87.

## Required Executor Task

Run exactly one write-capable executor for M86. The executor should:

1. Implement the smallest coherent behavior-preserving extraction that moves
   payload-intake and mini-TSIL leaf return-lowering ownership out of
   `boundary.py`.
2. Add focused M86 tests for public facade import/call stability, private
   import boundaries, payload classification and typed-opaque behavior,
   accepted mini-TSIL diagnostics/source locations, pipeline snapshots, stage
   order, keys, output identity, selected-branch-only behavior, and
   deterministic source locations.
3. Preserve accepted direct parameter-add and `intrin_compose<add>` return
   behavior exactly.
4. Preserve all accepted public imports and existing lowering behavior.
5. Avoid moving `_lower_input`, request/result models, stage builders,
   source adapters, selected-body lowering, exact array-body lowering,
   generation query payload lowering, generation control-flow pruning, broad
   TSIL parsing, duplicate moved code, and another catch-all private module.
6. Run the required validation commands below.
7. Return a concise implementation summary, files changed, validation results,
   and any follow-ups.

## Required Validation

Run:

```bash
wc -l tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py
PYTHONPATH=tslgen/src python -m py_compile tslgen/src/tslgen/lowering/boundary.py tslgen/src/tslgen/lowering/_lowering_inputs.py tslgen/src/tslgen/lowering/_mini_tsil_lowering.py tslgen/src/tslgen/lowering/_stage_contracts.py tslgen/src/tslgen/lowering/_generation_models.py tslgen/src/tslgen/lowering/_generation_queries.py tslgen/src/tslgen/lowering/_generation_control_flow.py tslgen/src/tslgen/lowering/_generation_diagnostics.py tslgen/src/tslgen/lowering/_selected_body_lowering.py tslgen/src/tslgen/lowering/_array_body_pipeline.py tslgen/src/tslgen/lowering/_array_body_sources.py tslgen/src/tslgen/lowering/_array_body_lowering.py
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py -k "m86 or lowering_input or payload_classification or mini_tsil or typed_opaque"
PYTHONPATH=tslgen/src pytest tslgen/tests/unit/test_lowering_boundary.py
MYPYPATH=tslgen/src:tslgen/tests/unit mypy --explicit-package-bases tslgen/src/tslgen/lowering
PYTHONPATH=tslgen/src python -m tslgen.tooling.validation
git diff --check
```

If implementation chooses different private module names than
`_lowering_inputs.py` and `_mini_tsil_lowering.py`, update the py-compile and
line-count commands consistently in this prompt,
`docs/agent/current-redesign-state.md`, and the final report.

## Review And Audit Subagents

After the executor finishes, run read-only subagents:

1. Reviewer: use `docs/agent/review-checklist.md` and return `Accept`,
   `Accept With Follow-Ups`, `Needs Revision`, `Return To Planner`, or
   `Reject`.
2. Boundary auditor: verify the extraction is one behavior-preserving lowering
   ownership slice, private modules do not import the facade, `_lower_input`
   and request/result models remain facade-owned, and no raw helper dispatch,
   broad TSIL/body/call/store/return semantics, backend/rendering/output
   leakage, hardwiring, or catch-all module was introduced.
3. Extensibility auditor: verify the staged lowering pipeline remains
   maintainable and future stages can be added without registries,
   dispatchers, broad protocols, callback injection, hidden backfeeds, or a
   generic TSIL statement framework.
4. Validation auditor: verify required commands ran, results are recorded, and
   tests cover the declared M86 risks.
5. Documentation auditor: verify roadmap/state/testing/design docs match the
   implemented result and no stale M86/M85 handoff wording remains.

Reviewers and auditors are read-only.

## Revision Loop

If review returns `Needs Revision`, run one focused write-capable revision
executor for only the blocking issues. Then run focused read-only re-review for
the affected issue class. Repeat only if the remaining issues are tightly
scoped local fixes.

If review returns `Return To Planner`, stop implementation and create a
planning prompt under `docs/agent/runs/` that describes the unresolved design
issue. Do not continue M86 implementation.

If review returns `Reject`, stop implementation and create the appropriate
rollback/redesign prompt under `docs/agent/runs/`. Do not continue M86
implementation.

## Finalization

If review returns `Accept` or `Accept With Follow-Ups`, update:

- `docs/agent/current-redesign-state.md`
- `docs/redesign/implementation-roadmap.md`
- any other redesign docs needed to reflect the accepted M86 result

Record:

- M86 accepted status and review verdict.
- Files changed.
- The `boundary.py` line count before and after M86.
- Validation commands and exact results.
- Any non-blocking follow-ups.
- Boundary reminders for future lowering work.

Create the next concrete prompt:

```text
docs/agent/runs/post-m86-planning-plus-review-prompt.md
```

The post-M86 prompt must focus on lowering, use read-only planning/review
subagents, and must not implement M87 unless that future prompt explicitly
selects an executor task.

Do not start M87 in this prompt.
