# M124 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M123:

```text
Milestone 124: Tiny Clean Multi-Primitive Source-Set Lowering Slice
```

Milestones 1 through 123 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M123 built the
tiny clean restart path from explicit `.tsl` source loading through catalog
construction, selection, lowering, backend emission, artifact writing, focused
scalar operation expansion, and explicit bootstrap-core semantic origins for
accepted scalar operation descriptors and compatibility rules.

M124 keeps the next task focused on lowering while moving the research
prototype closer to the intended product loop: changing explicit `.tsl` source
files should affect selected lowered functions and generated artifacts, or
produce clear diagnostics.

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
- current clean source/catalog/selection/lowering implementation under
  `tslgen/src/tslgen/`
- current tiny-pipeline tests in `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Allow one generator run to consume a small explicit source set containing
multiple exact supported primitive `.tsl` files, select explicit targets from
that catalog, lower the selected implementations through the accepted
M108-M123 lowering path, and emit deterministic C++/Rust artifacts.

## Required Executor Task

Run exactly one write-capable executor for M124. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Broaden catalog construction from exactly one parsed primitive per run to a
   deterministic catalog of multiple parsed primitives across explicit source
   documents. Preserve the current exact parser shape of one primitive,
   one scalar implementation, and one body line per `.tsl` file.
3. Preserve the accepted M107-M123 body forms, scalar type descriptors,
   operation descriptors, compatibility rules, and
   `clean_restart_bootstrap_core` semantic-origin contract. Do not add
   operations, scalar types, or source body syntax.
4. Add a focused duplicate primitive-name diagnostic before selection/lowering
   so multiple source files cannot silently choose whichever duplicate appears
   first.
5. Keep target requests explicit. Selection should choose requested primitive,
   backend, extension, and type from the multi-primitive catalog; do not add
   automatic target discovery or "generate everything" behavior.
6. Prove that a source-set change flows through lowering by adding fixtures or
   test-built source documents for representative binary, unary, and
   comparison primitives and by asserting selected lowered functions/artifacts
   reflect the `.tsl` primitive/body/type data.
7. Add negative tests showing unsupported or mismatched `.tsl` operation bodies
   still produce structured lowering diagnostics rather than source repair,
   renderer inference, or silent fallback.
8. Add determinism tests that run the same explicit source set in different
   input orders and compare diagnostics, artifact logical paths, contents, and
   digests.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- Parsing multiple primitive blocks inside one `.tsl` document, loading the
  broad `tsldata/` corpus, parsing broad TSL syntax, parsing TSIL strings, or
  accepting body shapes beyond the exact M107-M123 forms.
- Adding new operation ids, scalar types, templates, implementation variants,
  extension fallback, dependency closure, backend manifests, target discovery,
  generated-test execution, CLI behavior, writer behavior, or output tree
  parity.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen/`, `tslgenold/`, plugins, or
  environment configuration at runtime.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M124 is a source-set-to-lowering product
   slice, remains KISS-compatible, and does not add broad parser/corpus loading
   or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, source-set cataloging, or lowering.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M124 as broad corpus
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
python -B -m py_compile tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/pipeline/generator.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

Remove any validation-created `__pycache__` directories before the final cache
check. Do not run the old `tslgenold` validation profile as proof of the clean
product slice.

## Completion Rules

If M124 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M124 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M124 is accepted. Select exactly one concrete M125 task, prefer a
high-value research-prototype step, and create the next execution-review-loop
prompt directly. Do not create a separate post-M124 planning prompt unless
review returns `Return To Planner`, `Reject`, or an explicit stop condition is
recorded.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 125 implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
