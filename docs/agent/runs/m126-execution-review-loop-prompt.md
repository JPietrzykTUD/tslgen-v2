# M126 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M125:

```text
Milestone 126: Tiny Clean Ordered Implementation Body Line Boundary Slice
```

Milestones 1 through 125 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M125 built the
tiny clean restart path from explicit `.tsl` source loading through
multi-document and multi-implementation catalog construction, explicit target
selection, selected-implementation lowering, backend emission, artifact
writing, focused scalar operation expansion, bootstrap-core semantic origins,
and deterministic source-set generation.

M126 applies ADR-036 before adding more TSIL source forms. Implementation
bodies should become ordered source-owned body lines with optional lowerable
segments. This first slice preserves the existing exact `body ...` fixture
syntax by representing it as a one-line body containing one lowerable operation
fragment. It must not add TSIL `emit_return(...)` parsing, helper
substitution, raw body passthrough, broad statement/expression parsing, or
renderer-side inference.

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

Represent the existing accepted source body line:

```text
    body add(left, right)
```

as an ordered implementation body:

```text
ImplementationBody
  lines:
    SegmentedBodyLine
      segments:
        LowerableOperationFragment(operation="add", arguments=("left", "right"))
```

The selected implementation must still lower through the existing typed
selected-implementation path and preserve M107-M125 behavior and representative
artifact bytes.

## Required Executor Task

Run exactly one write-capable executor for M126. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Preserve the M125 exact source-document shape: one primitive header followed
   by one or more implementation/body pairs. Each implementation block remains
   exactly an implementation header immediately followed by one body line.
3. Introduce small typed parser/domain values for implementation bodies as
   ordered body lines with optional lowerable segments, aligned with ADR-036.
   Suggested names are less important than the boundary:
   - `ImplementationBody` or equivalent body container;
   - `BodyLine` values for body lines;
   - `RawStringLine` / `SegmentedLine` or equivalent line variants;
   - `RawStringToken`, `LowerableOperationFragment`, and
     `LowerableDirective` segment concepts, if segment values are introduced
     in this slice.
4. Represent the existing exact `body <operation>(...)` line as a one-line
   body containing one lowerable operation fragment. Do not add new accepted
   source syntax.
5. Keep lowering focused: consume only the accepted one-line / one-fragment
   body forms for already supported binary, unary, and comparison templates.
6. Preserve accepted primitive header shapes, selected-implementation
   behavior, body argument shape rules, operation descriptors, scalar type
   descriptors, compatibility rules, and the `clean_restart_bootstrap_core`
   semantic-origin contract.
7. Keep target requests explicit. Selection should pick only the implementation
   matching the target extension and type tag; do not add target discovery,
   generate-all behavior, extension fallback, type groups, or implementation
   ranking.
8. Prove that existing selected bodies still drive lowering by testing
   generated C++/Rust artifacts for representative binary, unary, and
   comparison primitives.
9. Prove that unselected body lines are still not lowered by preserving or
   adapting the M125 multi-implementation tests.
10. Add negative tests showing malformed body-line/segment containers produce
    structured diagnostics, not source repair, renderer inference, raw
    passthrough, or silent fallback.
11. Preserve M125 multi-implementation behavior, M124 multi-document
    source-set behavior, and deterministic artifact ordering.
12. Update docs only for behavior, decisions, open questions, or workflow state
    revealed by this slice.

## Out Of Scope

- Parsing or accepting TSIL strings, `emit_return(...)`, helper calls,
  primitive calls, intrinsics, casts, variables, immediates, multiple
  statements, multiline bodies, raw body passthrough, helper evaluation, branch
  pruning, source repair, or TSIL compiler behavior.
- Segmenting mixed raw/lowerable TSIL lines. M126 creates the body-line
  boundary but does not yet recognize raw text tokens or lowerable islands
  inside a raw source line.
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
  category/request/result/worklist family.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M126 is a body-model consolidation slice,
   remains KISS-compatible, and does not add broad TSIL parsing, new exact TSIL
   source forms, corpus loading, target discovery, raw passthrough rendering,
   or IR ceremony.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup, compatibility evaluation, implementation selection, lowering, body
   segmentation, or backend spellings.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M126 as TSIL
   `emit_return(...)` support, broad TSIL parsing, corpus ingestion, backend
   manifest loading, source repair, target discovery, CLI, writer, or old
   migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/syntax/parser.py tslgen/src/tslgen/syntax/ast.py tslgen/src/tslgen/domain/catalog.py tslgen/src/tslgen/pipeline/catalog_builder.py tslgen/src/tslgen/analysis/selection.py tslgen/src/tslgen/lowering/model.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
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
high-value research-prototype step aligned with ADR-036, and create the next
execution-review-loop prompt directly. Do not create a separate post-M126
planning prompt unless review returns `Return To Planner`, `Reject`, or an
explicit stop condition is recorded.

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
