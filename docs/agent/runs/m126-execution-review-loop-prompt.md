# M126 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M125:

```text
Milestone 126: Tiny Clean Exact TSIL Emit-Return Binary Body Lowering Slice
```

Milestones 1 through 125 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M125 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
and deterministic source-set generation.

M126 keeps the next task focused on lowering and moves the research prototype
closer to `.tsl`-authored implementation bodies: selected binary scalar
implementations may use one exact TSIL-like `emit_return(...)` body line
instead of only the synthetic clean-restart `body ...` fixture line.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/open-questions.md`
- current clean parser/catalog/selection/lowering implementation under
  `tslgen/src/tslgen/`
- current tiny-pipeline tests in `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow one exact selected binary scalar implementation body line of the form:

```text
    tsil "emit_return(add(left, right));"
```

to produce the same typed backend-neutral binary operation body as the
accepted fixture form:

```text
    body add(left, right)
```

The selected implementation must lower through the existing typed
selected-implementation path and preserve M107-M125 behavior.

## Required Executor Task

Run exactly one write-capable executor for M126. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve the M125 exact source-document shape: one primitive header followed
   by one or more implementation/body pairs. Each implementation block remains
   exactly an implementation header immediately followed by one body line.
3. Add exact recognition for binary scalar TSIL emit-return body lines shaped
   as `tsil "emit_return(<operation>(left, right));"` under the accepted
   binary primitive header form.
4. Keep the accepted synthetic `body <operation>(left, right)` line working
   byte-for-byte for existing tests and artifacts.
5. Promote the exact TSIL emit-return body into typed operation body data
   before lowering/backend emission. Downstream lowering and emitters must not
   rescan raw TSIL text or render from raw TSIL text.
6. Preserve accepted primitive header shapes, selected-implementation
   behavior, body argument shape rules, operation descriptors, scalar type
   descriptors, compatibility rules, and the `clean_restart_bootstrap_core`
   semantic-origin contract.
7. Keep target requests explicit. Selection should pick only the implementation
   matching the target extension and type tag; do not add target discovery,
   generate-all behavior, extension fallback, type groups, or implementation
   ranking.
8. Prove that selected exact TSIL emit-return bodies drive lowering by testing
   generated C++/Rust artifacts for at least one representative binary
   primitive.
9. Prove that unselected exact TSIL emit-return bodies are not lowered by
   adding a focused multi-implementation test where an unselected exact TSIL
   body would be a lowering mismatch if selected, while the selected
   implementation still generates successfully.
10. Add negative tests showing selected mismatched TSIL emit-return operation
    bodies and malformed nearby TSIL forms produce structured diagnostics, not
    source repair, renderer inference, or silent fallback.
11. Preserve M125 multi-implementation behavior, M124 multi-document
    source-set behavior, and deterministic artifact ordering.
12. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Parsing broad TSIL strings, nested calls, primitive calls, intrinsics, casts,
  variables, immediates, multiple statements, multiline TSIL bodies, helper
  evaluation, branch pruning, source repair, or TSIL compiler behavior.
- Accepting unary or comparison TSIL emit-return forms in this slice.
- Parsing multiple primitive blocks inside one `.tsl` document, loading broad
  `tsldata/`, parsing broad TSL syntax, adding new operation ids, scalar
  types, templates, type groups, extension fallback, dependency closure,
  backend manifests, target discovery, generated-test execution, CLI behavior,
  writer behavior, or output tree parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen`, `tslgenold`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M126 is an exact selected-body lowering slice,
   remains KISS-compatible, and does not add broad TSIL parsing, corpus
   loading, target discovery, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, implementation selection, lowering, or
   backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M126 as broad TSIL
   parsing, corpus ingestion, backend manifest loading, source repair, target
   discovery, CLI, writer, or old migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

## Completion Rules

If M126 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M126 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M126 is accepted. Select exactly one concrete M127 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M126 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 127 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
