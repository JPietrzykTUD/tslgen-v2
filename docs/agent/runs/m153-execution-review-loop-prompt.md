# M153 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M152:

```text
Milestone 153: Backend Helper Raw Preservation Boundary
```

Milestones 1 through 152 are accepted. M152 reduced `Lowerer` by removing
primitive-call substep facades and kept primitive-call ownership on the focused
selector-payload helper, `PrimitiveCallResolver`, and
`PrimitiveCallDependencyCollector`.

M153 corrects the previous helper-substitution direction. Product review
clarified that `details::arith_add`, `details::arith_mul`, and
`details::arith_rem` are source-authored calls to predefined backend/language
support helpers. They are not semantic lowering islands and must not be
rewritten to typed `add`, `mul`, `mod`, `+`, `*`, or `%` by lowering.

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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`

## Goal

Lock down raw helper preservation:

- classify `details::arith_add(...)`, `details::arith_mul(...)`, and
  `details::arith_rem(...)` as raw/predefined backend support helper calls;
- preserve those calls as source-authored implementation-body text;
- ensure lowering does not rewrite them to typed `add`, `mul`, `mod`, or
  backend operator spellings;
- keep future backend support-library/rendering work separate from semantic
  lowering.

Also record the post-M152 lowering path backlog so the next milestones are
selected from explicit generation-relevant TSIL keyword families rather than
from chat memory or accidental expression-parsing pressure.

## Required Executor Task

Run exactly one write-capable executor for M153. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Update docs to remove the mistaken helper-substitution/lowering premise for
   `details::arith_add`, `details::arith_mul`, and `details::arith_rem`.
3. Add regression coverage, if the existing suite does not already prove it,
   that `emit_return(details::arith_mul(...));` remains an opaque unsupported
   return expression at lowering rather than becoming a typed binary operation.
4. Record a compact post-M152 lowering path backlog in
   `docs/redesign/missing-lowering-inventory.md` and keep the roadmap/current
   state consistent with it. The backlog must distinguish actual lowerable
   TSIL keyword families from raw/backend support helper calls.
5. Preserve raw source locations, raw payload text, deterministic token order,
   and existing diagnostics.
6. Do not introduce a helper token classifier, semantic helper IR, helper
   operation descriptor table, or backend operator substitution.
7. Leave acceptance-state updates to the orchestrator finalization step after
   read-only review returns `Accept` or `Accept With Follow-Ups`.

## Lowering Path Backlog To Record

M153 must not implement these paths, but it must record them as candidate
future milestone lanes:

1. Generation value/query lowering:
   `value<generation>(...)` families from the current corpus, building on the
   accepted type-query work without broad expression parsing.
2. Generation control lowering:
   `if<generation>(...)`, `else if<generation>(...)`, and
   `else<generation>` over source-owned body tokens with selected-branch
   provenance and diagnostics.
3. Generation declaration/iteration lowering:
   `loop<unroll>(...)`, `loop<range>(...)`, `var<...>(...)`, and non-type
   `let<...>(...)`; `let<type>(...)` alias facts are already partially handled
   and should stay connected to the type environment.
4. Backend query lowering:
   `value<backend>(...)` and backend rendering/translation of accepted
   `type<backend>(...)` requests from typed semantic values.
5. Backend control lowering:
   `if<compile>(...)`, `else<compile>`, and `switch<compile>(...)`; record
   `if<runtime>` / `else<runtime>` as absent from the current corpus unless
   new `.tsl` data introduces them.
6. Backend-owned operation lowering:
   `intrin_compose<...>(...)` and `intrin<...>(...)` to typed backend
   intrinsic requests, not renderer inference.
7. Primitive-call completion:
   recursive/nested `call<primitive=...>(...)` lowering in token streams,
   backend rendering of lowered primitive-call expressions, and deterministic
   dependency scheduling/output once selected.
8. Cast/memory/I/O keyword families:
   `cast<...>`, `mem<...>`, and `io<...>` must be inventoried over all
   `tsldata/**/*.tsl` before any implementation milestone selects them.
9. Body-token rendering policy:
   raw source text plus accepted lowerable TSIL islands must be rendered by
   backend-owned rules after lowering produces typed values; this is output
   integration, not semantic helper-call lowering.

Explicitly record that `details::arith_*`, `details::popcount`,
`details::clz`, `details::clz_recursive`, `details::ctz`, and
`details::mask_test` are not lowering lanes by default.

## Must Preserve

- M107-M152 accepted behavior, diagnostics, source locations, and generated
  bytes.
- Raw source text as source truth.
- Backend ownership of support-library functions and any eventual rendering
  policy for raw source text.
- Existing primitive-call resolver/collector ownership and exact M150
  primitive-call return consumer behavior.
- `details::popcount`, `details::clz`, `details::clz_recursive`,
  `details::ctz`, and `details::mask_test` as source-authored/backend-support
  helper calls.

## Out Of Scope

Lowering `details::arith_add`, `details::arith_mul`, or
`details::arith_rem` to semantic operations or operators; general helper-call
lowering; support helper lowering; primitive-call semantics; recursive
expression parsing; operator precedence; assignment, array/index, loop, `var`,
`let`, `if`, `switch`, cast, intrinsic, memory, or I/O lowering; backend call
rendering; backend type rendering; raw source rewriting; source repair;
runtime `tsldata`, `frozen`, or `tslgenold` dependencies; registries,
dispatchers, fixpoint mechanisms, broad request/result/worklist families, or
source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M153 prevents the mistaken helper-lowering
   path and does not add helper IR, expression parsing, backend rendering,
   source repair, or primitive-call middleware.
2. Boundary auditor: verify M107-M152 behavior remains stable and raw helper
   payloads stay opaque/unsupported at lowering.
3. Evidence auditor: verify the helper classification is grounded in
   `docs/redesign/tsil-surface-inventory.md` / current `tsldata` evidence and
   backend support-helper data.
4. Documentation auditor: verify behavioral/domain/roadmap/missing-inventory
   docs accurately describe raw helper preservation and exclusions.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py -k "emit_return or unsupported_return or m129 or m153"
find tslgen -type d -name __pycache__ -print
```

If the executor adds a focused M153 test file, include it in the compileall
command. If it adds focused M153 tests to an existing test file, include `m153`
in the pytest selector. Update this prompt, the roadmap, and current state
during finalization.

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M153 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M153 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M153 is accepted. Do not start broad helper substitution,
primitive-call recursive scanning, assignment/loop/body rendering, expression
trees, backend call rendering, or dependency scheduling until M153 is accepted
and the next prompt explicitly selects that work. The next prompt must choose
one path from the recorded backlog or state why a documentation/planning
milestone is needed first.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 154 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
