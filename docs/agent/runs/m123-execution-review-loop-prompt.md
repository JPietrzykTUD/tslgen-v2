# M123 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M122:

```text
Milestone 123: Tiny Clean Bootstrap Operation Semantics Contract Slice
```

Milestones 1 through 122 are accepted. M106 moved the pre-restart top-level
`tslgen/` tree to `tslgenold/` as evidence-only old state. M107-M122 built the
tiny clean restart path from source loading through catalog construction,
selection, lowering, backend emission, artifact writing, and focused scalar
operation expansion. M122 broadened the accepted scalar comparison path to the
same-shape comparison operator family.

This milestone intentionally keeps the next task focused on lowering. It must
make the accepted scalar operation descriptor and compatibility-rule facts an
explicit bootstrap-core lowering contract, so operation facts observed in
`tsldata/*` do not appear to have silently leaked into product generator code.

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
- current clean lowering implementation under `tslgen/src/tslgen/lowering/`

## Goal

Make the existing lowering-owned scalar operation descriptor and
operation/type compatibility facts explicitly identify their semantic origin as
accepted clean-restart bootstrap core semantics:

```text
add/sub/mul/div/mod/bit_*/shift_* -> binary bootstrap core operations
bit_not/neg -> unary bootstrap core operations
equal/nequal/less_than/... -> comparison bootstrap core operations
integer-only and tag-specific compatibility gates -> bootstrap core rules
```

## Required Executor Task

Run exactly one write-capable executor for M123. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Add the smallest typed lowering-owned semantic-origin contract needed for
   accepted operation descriptor and operation/type compatibility rule records.
   The origin should identify accepted bootstrap-core semantics and must not be
   a path into `tsldata/`, `frozen/`, or `tslgenold/`.
3. Attach that origin to existing binary, unary, and comparison operation
   descriptor records without changing operation ids, arity, category, source
   body operation, semantic name, deterministic order, lookup behavior, or
   public import surface except where tests deliberately assert the new typed
   origin field.
4. Attach the same origin contract to the existing lowering-owned
   operation/type compatibility rules for integer-only binary operations,
   `bit_not`, and `neg`.
5. Keep backend result/type/operator spellings in the C++ and Rust backend
   layers. Lowering descriptors and compatibility rules must not contain
   backend text, backend capability state, backend manifest keys, or renderer
   policy.
6. Preserve accepted binary, unary, and comparison lowering behavior,
   diagnostics, descriptor ordering, stage-output behavior, public API imports,
   generated logical paths, artifact ordering, and representative artifact
   bytes.
7. Add focused tests proving every accepted operation descriptor and
   compatibility rule declares the bootstrap-core origin, no descriptor/rule
   records corpus paths or backend spelling, descriptor/rule ordering is
   stable, existing lowering diagnostics remain clear, and representative
   binary, unary, and comparison artifacts remain byte-stable.
8. Add a focused no-runtime-corpus-read regression for operation descriptor and
   compatibility-rule lookup/lowering if it can be done without broad monkey
   patching or hidden environment dependencies.
9. Update docs only for behavior, decisions, open questions, or workflow state
   revealed by this slice.

## Out Of Scope

- Adding new operation ids, scalar types, source syntax, templates, body
  shapes, broad TSIL parsing, arbitrary arity support, multiple statements,
  nested expressions, variables, calls, source repair, or generalized
  expression trees.
- Loading operation semantics, compatibility rules, or backend spellings from
  `tsldata/`, backend manifests, YAML, `frozen/`, `tslgenold/`, plugins, or
  environment configuration at runtime.
- Introducing a registry, dispatcher, callback map, plugin system, hidden
  backfeed, fixpoint mechanism, broad operation framework, or new lowering IR
  category/request/result family.
- Moving backend-owned C++/Rust type, result, or operator spellings into
  lowering.
- Defining runtime floating NaN/special-value policy, signed ordering policy,
  shift-count policy, overflow/wrapping policy, vector/SIMD semantics, mask
  ABI policy, dependency closure, backend planning, artifact writing, CLI
  behavior, or generated-test execution.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M123 is genuinely lowering focused, makes the
   bootstrap-core semantic contract explicit without broad IR ceremony, and
   does not add renderer-side semantic inference.
2. Boundary auditor: verify `frozen/`, `tslgenold/`, and `tsldata/` remain
   evidence/source inputs only and are not runtime shortcuts for operation
   lookup or compatibility evaluation.
3. Documentation auditor: verify behavior, roadmap, design decisions, and
   workflow state remain coherent and do not describe M123 as backend
   manifest loading, broad data-driven operation semantics, source repair,
   runtime floating/signed-ordering policy, CLI, writer, or old migration work.
4. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
python -B -c "from tslgen import Generator, Target, generate_from_paths"
python -B -m py_compile tslgen/src/tslgen/lowering/binary_operations.py tslgen/src/tslgen/lowering/unary_operations.py tslgen/src/tslgen/lowering/comparison_operations.py tslgen/src/tslgen/lowering/operation_type_compatibility.py tslgen/src/tslgen/lowering/lowerer.py tslgen/tests/test_m107_tiny_pipeline.py
```

Run the smallest additional import check needed for the new semantic-origin
contract. Do not run the old `tslgenold` validation profile as proof of the
clean product slice.

## Completion Rules

If M123 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M123 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

Do not start Milestone 124 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Scope confirmation.
3. Review verdict and subagent verdicts.
4. Follow-ups recorded, if any.
5. Next concrete run prompt created.
6. Validation command(s) and exact result.
