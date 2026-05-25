# M125 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M124:

```text
Milestone 125: Tiny Clean Multi-Implementation Primitive Lowering Slice
```

Milestones 1 through 124 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M124 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document catalog construction, explicit target selection, lowering,
backend emission, artifact writing, focused scalar operation expansion,
bootstrap-core semantic origins, and deterministic source-set generation.

M125 keeps the next task focused on lowering and moves the research prototype
closer to real `.tsl` primitive authoring: one supported primitive document
may declare multiple exact scalar implementations, and explicit targets select
which implementation is lowered.

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

Allow one exact supported primitive `.tsl` document to contain multiple scalar
implementation blocks for distinct type tags. Selection must choose the
implementation requested by the explicit target, and lowering/backend emission
must consume only that selected implementation while preserving accepted
M108-M124 behavior.

## Required Executor Task

Run exactly one write-capable executor for M125. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Broaden the narrow parser/catalog source shape from one scalar
   implementation block per primitive document to two or more exact scalar
   implementation blocks under one primitive header. Each implementation block
   remains exactly an implementation header immediately followed by one body
   line.
3. Preserve the accepted primitive header shapes, body argument shapes,
   operation descriptors, scalar type descriptors, compatibility rules, and
   `clean_restart_bootstrap_core` semantic-origin contract.
4. Add duplicate implementation-key diagnostics for repeated
   `(extension, type_tag)` entries within the same primitive before selection
   and lowering.
5. Keep target requests explicit. Selection should pick only the implementation
   matching the target extension and type tag; do not add target discovery,
   generate-all behavior, extension fallback, type groups, or implementation
   ranking.
6. Prove that selected implementation bodies drive lowering by testing a
   source document with multiple type-specific implementations for at least
   one representative binary primitive, and by asserting generated C++/Rust
   artifacts reflect the selected implementation's type/body.
7. Prove that unselected implementation bodies are not lowered by adding a
   focused test where an unselected exact-shape implementation would be
   semantically unsupported if selected, while the selected implementation
   still generates successfully.
8. Add negative tests showing duplicate implementation keys and selected
   mismatched bodies produce structured diagnostics, not source repair,
   renderer inference, or silent fallback.
9. Preserve M124 multi-document source-set behavior and deterministic artifact
   ordering.
10. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Parsing multiple primitive blocks inside one `.tsl` document, loading broad
  `tsldata/`, parsing broad TSL syntax, parsing TSIL strings, or accepting
  body shapes beyond the exact M107-M124 forms.
- Adding new operation ids, scalar types, templates, type groups, extension
  fallback, dependency closure, backend manifests, target discovery,
  generated-test execution, CLI behavior, writer behavior, or output tree
  parity.
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

1. Architecture reviewer: verify M125 is a selected-implementation lowering
   slice, remains KISS-compatible, and does not add broad parser/corpus loading,
   target discovery, or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, implementation selection, lowering, or
   backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M125 as broad corpus
   ingestion, backend manifest loading, source repair, target discovery, CLI,
   writer, or old migration work.
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

If M125 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M125 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M125 is accepted. Select exactly one concrete M126 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M125 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 126 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
