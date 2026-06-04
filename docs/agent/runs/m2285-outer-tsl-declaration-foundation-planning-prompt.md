# M228.5 Outer TSL Declaration Foundation Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M227 as accepted, M228 as stopped before implementation, and
the sideways M228.5 parser/body attempt as evidence only.

This is a planning/documentation task. Do not implement production code.

## Accepted State

Accepted through:

```text
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
```

M228 and the later sideways M228.5 parser/body attempt are not accepted
implementation milestones. The `m228-spike` branch and the
`m2285-sideways-parser-body-attempt.patch` branch are evidence only. Do not
copy or cherry-pick them wholesale.

The important lesson is that the first real x86 fixture is premature: it pulls
outer `.tsl` declaration parsing, nested `impls`, wildcard selection,
multiline TSIL body tokenization, lowering, backend translation, rendering,
and generated build verification into one milestone.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/agent/runs/m228-restarted-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `frozen/tsl-gen/tsl_gen/tsl_data.lark`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/tsil_lexical.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`

You may inspect `m228-spike` and
`m2285-sideways-parser-body-attempt.patch` only as negative/evidence material.
Do not make either branch a runtime dependency.

## Goal

Plan the missing foundation that must exist before the real x86 fixture can
resume.

The output should decide what the next executable milestone should be, with a
strong bias toward parser/source-body foundation rather than fixture rendering.

## Planning Scope

Answer these questions from repository evidence:

1. What outer `.tsl` declaration forms must be understood before the first
   real fixture path can safely resume?
2. Should the next parser step be:
   - a grammar/Lark-based outer declaration parser,
   - a smaller typed parser for a selected declaration subset,
   - or another explicit foundation slice?
3. What typed declaration model is needed at the parser/catalog boundary?
   Keep dictionaries out past parser/catalog boundaries.
4. Where is the boundary between outer TSL declaration parsing and TSIL
   implementation body tokenization?
5. What should shared lexical body-region mechanics provide before
   keyword-specific lowerers consume multiline bodies?
6. What must remain raw source text, and what may become lowerable typed
   tokens?
7. Which module-size or accretion risks must be handled before implementation?

Use all `tsldata/**/*.tsl` files as evidence when inventorying outer
declaration forms, but do not attempt to fully parse or semantically validate
the corpus in this planning milestone.

## Guardrails

- Do not implement production code.
- Do not revive the real x86 fixture milestone yet.
- Do not create a broad TSIL parser plan.
- Do not plan source repair, target-language parsing, or expression/statement
  semantics.
- Do not add backend rendering, generated project writing, dependency closure,
  qemu/ARM, all-profile generation, host detection, or compiler capability
  modeling.
- Do not make `frozen/`, `tslgenold/`, `m228-spike`, or
  `m2285-sideways-parser-body-attempt.patch` runtime dependencies.
- Do not propose more regex accretion in `parser.py`, `lowerer.py`, or
  `generated_primitive_pipeline.py`.

## Expected Planning Output

Update docs with:

- a concise result in `docs/redesign/implementation-roadmap.md`;
- any accepted design decision in `docs/redesign/design-decisions.md`;
- open questions in `docs/redesign/open-questions.md` if the evidence is
  insufficient;
- the next active prompt under `docs/agent/runs/`;
- `docs/agent/current-redesign-state.md` pointing at that next prompt.

The next prompt should be concrete and executable. It may be an implementation
prompt only if the foundation decision is narrow enough and clearly avoids the
sideways M228.5 failure mode. Otherwise, it should be another planning or
inventory prompt.

## Suggested Read-Only Subagents

Use read-only subagents if useful:

1. Parser evidence auditor: observed outer `.tsl` declaration forms across
   `tsldata/**/*.tsl`.
2. Parser architecture reviewer: Lark/grammar vs focused typed parser tradeoff.
3. Body-boundary reviewer: outer declaration parsing vs TSIL body-token
   lexical mechanics.
4. Complexity auditor: module-size/accretion risks and whether the next slice
   is still too broad.

The orchestrator owns the final decision and state update.

## Required Validation

Run:

```bash
git diff --check
```

## Final Report

Report:

1. Planning decision.
2. Why the real fixture remains deferred.
3. Docs changed.
4. Validation command and exact result.
5. Next active prompt path.
