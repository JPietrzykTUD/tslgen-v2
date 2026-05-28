# M156 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M155:

```text
Milestone 156: Exact Generation-Control Branch Region Lowering Boundary
```

Milestones 1 through 155 are accepted. M155 added isolated selected-context
`value<generation>(...)` query lowering for current vector metadata, selected
scalar type facts, scalar type predicates, and concrete boolean primitive
attributes. M156 is the first generation-control consumer of those accepted
boolean value facts.

M156 is an implementation milestone. It should implement only exact
generation-control branch-region lowering over existing source-owned body
tokens. Do not implement loop execution, declaration lowering, body rendering,
raw expression parsing, backend rendering, or broad TSIL interpretation.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/next-run-prompt-protocol.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/kiss-generator-restart.md`
- `docs/redesign/requirements.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/testing-strategy.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/generation-value-query-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Add a focused branch-region lowering boundary for exact generation-control
regions shaped as:

```text
if<generation>(VALUE_QUERY) {
  SELECTED_OR_UNSELECTED_BODY_TOKENS
} else<generation> {
  SELECTED_OR_UNSELECTED_BODY_TOKENS
}
```

The condition must be an isolated M155 boolean generation value query:

- `value<generation>(primitive::attribute(KEY))`
- `value<generation>(type::is_signed(TYPE_EXPR))`
- `value<generation>(type::is_same(TYPE_EXPR, TYPE_EXPR))`

The result should preserve source-owned body tokens exactly for the selected
branch and preserve provenance for the region, condition, selected branch, and
unselected branch. This is branch-token selection only. It is not rendering and
not source text replacement.

## Required Executor Task

Run exactly one write-capable executor for M156. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Before implementation, record current `else if<generation>` corpus evidence
   in the relevant redesign inventory/spec document so the M127 follow-up is
   closed before generation-control lowering behavior is added.
3. Add a small typed generation-control region result boundary over existing
   domain body tokens.
4. Match only exact source-owned token regions with an `if` directive whose
   first argument is `generation`, a following raw `{` opener, a matching
   branch close, an `else` directive whose first argument is `generation`, a
   following raw `{` opener, and a matching region close.
5. Use M155 generation-value lowering to evaluate only boolean condition
   queries. Integer value results such as `vector::length`,
   `vector::alignment`, and `type::size_bytes(...)` must produce unsupported
   condition diagnostics.
6. Preserve selected branch body tokens exactly; do not parse, repair,
   normalize, reorder, render, or rewrite branch body contents.
7. Emit deterministic diagnostics for malformed regions, unmatched braces,
   missing else branch, unsupported `else if<generation>` and plain `else`
   variants, unsupported conditions, non-boolean generation values, and M155
   missing-fact diagnostics.
8. Add focused tests for true/false branch selection, malformed regions,
   unsupported conditions, non-boolean values, missing facts, nested or
   adjacent raw tokens that must remain untouched, deterministic diagnostics,
   and no branch body lowering/rendering.
9. Update docs that describe the accepted M156 behavior and any newly
   discovered boundary details.
10. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Keep ownership small and obvious. A focused module or focused additions to
  existing lowering modules are acceptable if cohesion remains clear.
- Use source-owned token streams and exact directive boundaries. Do not add a
  broad TSIL parser, expression parser, registry, dispatcher, worklist,
  fixpoint mechanism, or renderer-side inference.
- Matching braces for this milestone is only to identify the exact selected
  generation-control region. It must not become general target-language block
  parsing or source repair.
- Do not evaluate or parse branch bodies. Branch bodies are token slices for
  later lowering/rendering milestones.
- Do not read `tsldata`, `frozen`, or `tslgenold` at runtime from lowering.
- Preserve M153 helper raw preservation and M155 isolated value-query
  behavior.

## Must Preserve

- M107-M155 accepted behavior, diagnostics, source locations, and generated
  bytes.
- The source-owned body-token model.
- Accepted type-query and generation-value query behavior.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.
- Accepted extension/register/mask catalog facts without adding host CPU
  detection or backend rendering.

## Out Of Scope

Loop execution; `loop<unroll>` or `loop<range>` lowering; declaration lowering;
non-type `let<...>` lowering; body-token rendering; raw text replacement;
source repair; raw expression parsing; arithmetic or comparison folding around
generation values; selector-attribute substitution; mask lane constants;
generic vector lengths/runtime lengths; backend-control `if<compile>`,
`else<compile>`, or `switch<compile>` lowering; `if<runtime>` /
`else<runtime>` behavior; casts, memory, I/O, intrinsics, primitive-call
rendering, backend rendering, dependency scheduling, runtime `tsldata`,
`frozen`, or `tslgenold` dependencies; broad registries, dispatchers,
worklists, callback maps, hidden backfeeds, or fixpoint mechanisms.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M156 adds only the selected exact
   generation-control branch-region boundary and avoids parser/evaluator
   overgrowth, registries, dispatchers, worklists, backend rendering, and
   runtime data reads.
2. Boundary auditor: verify unsupported surrounding syntax remains out of
   scope, branch bodies remain token slices, M153 helper raw preservation and
   M155 value-query behavior remain untouched, and no source repair/raw
   rewriting was added.
3. Evidence auditor: verify `else if<generation>` evidence is recorded before
   implementation behavior and that the selected/unsupported generation-control
   forms match current corpus evidence and exclusions.
4. Test auditor: verify tests cover true/false branch selection, malformed
   regions, unsupported/non-boolean conditions, missing facts, deterministic
   diagnostics, and no branch body lowering/rendering.
5. Documentation auditor: verify roadmap, behavioral/domain docs, missing
   inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M156 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M156 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M156 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M156 is accepted. Do not start M157 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 157 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
