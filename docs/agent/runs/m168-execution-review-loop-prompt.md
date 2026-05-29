# M168 Execution Review Loop Prompt

This is the active follow-on prompt after M167. Execute it only when
`docs/agent/current-redesign-state.md` points here and records M167 as
accepted.

You are executing and reviewing the accepted next milestone after M167:

```text
Milestone 168: Exact `generic::*` Generation-Expression Boundary
```

Milestones 1 through 167 are accepted. M167 records exact
`cast<...>(...)`, `mem<...>(...)`, and `io<...>(...)` islands as unresolved
source-operation requests over source-owned text and contiguous raw body-token
runs while preserving payloads and surrounding tokens opaque.

M168 is an implementation milestone. It should add the next lowering boundary
for the largest safe subset of remaining `generic::*` generation expressions:

```text
generic::length(TYPE_EXPR)
generic::runtime_length(TYPE_EXPR)
```

This is an inner generation-expression capability. `value<generation>(...)`
is one caller that can materialize such an expression, but it is not the owner
of the `generic::*` semantics. Other already accepted generation-expression
contexts may reuse the same capability when they already pass an expression
payload through the generation-expression lowerer.

`TYPE_EXPR` must lower through the already accepted selected type environment
and M143 type-expression path first. M168 must not match alias names or type
expressions by raw string.

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
- `docs/redesign/generation-value-query-inventory.md`
- `docs/redesign/tsil-type-query-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/missing-lowering-inventory.md`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/lowering/generation_values.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/type_syntax.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m1625_tsil_lexical.py`
- `tslgen/tests/test_m163_generation_variables.py`
- `tslgen/tests/test_m164_backend_value_queries.py`
- `tslgen/tests/test_m165_backend_control.py`
- `tslgen/tests/test_m166_backend_intrinsics.py`
- `tslgen/tests/test_m167_source_operations.py`

## Goal

Lower exact `generic::*` generation expressions for generic vector lengths
when all required facts are concrete:

```text
generic::length(TYPE_EXPR)
generic::runtime_length(TYPE_EXPR)
```

The result should be a typed integer generation-expression value only when:

- a selected TSIL generation-time context has provided the expression payload
  to the generation-expression lowerer;
- the expression is exactly `generic::length(TYPE_EXPR)` or
  `generic::runtime_length(TYPE_EXPR)`;
- `TYPE_EXPR` lowers through the accepted type-expression/type-alias
  environment to a concrete vector type value;
- the vector type has a concrete extension and scalar type tag;
- the catalog has deterministic fixed lane metadata for that extension and
  scalar type.

Runtime/scalable, size-parameter-only, unresolved alias/specialization,
non-vector, malformed, or metadata-missing forms must produce deterministic
diagnostics rather than guessed generation values.

M168 must not scan arbitrary raw target-language text for `generic::*` calls.
The caller context must already be a TSIL generation-time expression context,
such as `value<generation>(...)`, generation-control conditions, or loop
arguments that are already modeled as generation expressions. If a surrounding
context is still opaque raw text, this milestone leaves it opaque.

## Required Executor Task

Run exactly one write-capable executor for M168. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Inventory current `generic::length(...)` and
   `generic::runtime_length(...)` evidence across all `tsldata/**/*.tsl`
   files. Use corpus examples as evidence for the query surface and required
   facts, not as surrounding-shape templates.
3. Add or extend the smallest central generation-expression lowering
   capability needed for exact `generic::OP(...)` expressions. Keep operation
   handling direct and typed; do not add a broad registry, dispatcher,
   callback map, or worklist.
4. Wire the capability through existing generation-expression callers only
   where they already pass an expression payload through the same boundary.
   `value<generation>(...)` may materialize the result, but the semantics must
   live in the reusable expression lowerer rather than in a wrapper-specific
   string match.
5. Extend `LoweredGenerationValueKind` or the equivalent accepted typed
   generation-value/result model with the smallest result shape needed for
   successful generic length values.
6. Reuse `lower_type_expression(...)` / the selected type environment for
   `TYPE_EXPR`. Do not compare raw alias names such as `OutVec` or `ToType`
   directly.
7. Resolve only concrete vector type values accepted by the current type model
   such as current vector, vector transform/as-extension values, and aliases
   that lower to those values. Add precise diagnostics for non-vector values.
8. Compute lane count only from explicit scalar type descriptors and catalog
   extension metadata. If the extension is runtime/scalable, size-parameter
   based, missing, or otherwise not fixed at generation time, emit an
   unsupported/missing-fact diagnostic.
9. Keep `generic::runtime_length(...)` in the same boundary only when it can be
   exactly resolved for fixed-size vectors; otherwise diagnose it explicitly
   as unsupported for runtime/scalable or unresolved vectors.
10. Diagnose unknown or unsupported `generic::OP(...)` names deterministically
    when they occur inside an accepted generation-expression context. Do not
    treat unknown names as target-language passthrough after the context has
    selected them for generation-time lowering.
11. Preserve M155-M167 accepted behavior, diagnostics, source locations,
    selected-branch handoff, loop discovery, declaration requests, backend
    value queries, backend-control requests, intrinsic requests, source
    operation requests, primitive-call behavior, and generated bytes.
12. Add focused tests for:
   - direct generation-expression lowering of `generic::length(...)`;
   - positive `generic::length(...)` over an inline fixed vector type;
   - positive `generic::length(...)` through a preceding `let<type>` alias;
   - `value<generation>(generic::length(...))` as a materialization caller,
     if that caller already exists in the accepted generation-value path;
   - positive fixed-vector `generic::runtime_length(...)` if implemented;
   - unsupported `generic::OP(...)` operation name inside a selected
     generation-expression context;
   - malformed arity;
   - unresolved alias/specialization;
   - scalar/non-vector argument;
   - missing catalog extension metadata;
   - runtime/scalable or size-parameter-only extension metadata;
   - deterministic results;
   - preservation of existing M155-M167 tests.
13. Update docs that describe the accepted M168 behavior and any newly
    discovered boundary details.
14. Leave final accepted-state updates to the orchestrator after read-only
    review returns `Accept` or `Accept With Follow-Ups`.

## Design Guardrails

- Treat this as typed generation-expression lowering for selected
  generation-time contexts, not loop execution, declaration rendering, source
  replacement, arbitrary raw-text discovery, or backend rendering.
- The implementation may introduce a small inner helper/class for
  `generic::OP(...)` expressions if that clarifies ownership. It must remain a
  direct, finite set of accepted operations, not a framework for every future
  namespace.
- Lower nested type expressions first. Do not hardcode alias names like
  `OutVec`, `ToType`, `MaskVec`, or `GenericVec`.
- Do not infer lane counts from raw source text, target-language spellings,
  intrinsic names, primitive names, or backend helper calls.
- Do not solve runtime/scalable vector lengths by inventing compile-time
  constants. Unsupported or unresolved runtime-length cases are diagnostics.
- Do not scan opaque raw target-language fragments for `generic::*` calls.
  The surrounding TSIL construct must already establish generation-time
  expression semantics.
- Do not add a general expression parser, statement parser, source repair
  mechanism, dependency scheduler, broad registry, dispatcher, worklist,
  callback map, hidden backfeed, or fixpoint mechanism.

## Must Preserve

- M107-M167 accepted behavior, diagnostics, source locations, and generated
  bytes.
- M143 complete observed type lowering and ordered `let<type>(...)` alias
  visibility.
- M155 isolated generation-value query behavior.
- M158/M159 comparison and explicit `arith<generation>::...` behavior.
- M156-M160 generation-control region and branch-chain behavior.
- M161/M162 loop-region fact and discovery behavior.
- M163 declaration request discovery.
- M164 backend value query request discovery.
- M165 backend-control request discovery.
- M166 backend intrinsic request-island discovery.
- M167 source-operation request-island discovery.
- Accepted primitive-call resolver/collector behavior and helper raw
  preservation.

## Out Of Scope

Loop execution or unrolling; loop-variable substitution; branch selection
changes; declaration rendering; source replacement; backend rendering; cast,
memory, I/O, intrinsic, primitive-call, or backend-control translation;
runtime/scalable vector-length solving; generic-size-parameter code emission;
type inference; arbitrary expression/statement parsing; scanning opaque raw
target-language text for `generic::*`; source repair; dependency scheduling;
output writing; runtime `tsldata`, `frozen`, or `tslgenold` dependencies;
broad registries, dispatchers, worklists, callback maps, hidden backfeeds, or
fixpoint machinery.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M168 adds only exact typed
   generation-expression lowering for concrete `generic::*` vector length
   facts in selected generation-time contexts and avoids loop execution,
   rendering, raw alias matching, runtime/scalable guesses, arbitrary raw-text
   scanning, expression parsing, registries, dispatchers, worklists, source
   repair, and runtime data reads.
2. Boundary auditor: verify M155-M167 behavior remains intact, that
   `generic::*` semantics are owned by a reusable generation-expression
   boundary rather than wrapper-specific string matching, and that type
   expressions lower through accepted type facts rather than raw text.
3. Evidence auditor: verify the selected `generic::length(...)` /
   `generic::runtime_length(...)` surface and fixed/unresolved split are
   grounded in current `tsldata/**/*.tsl` evidence without requiring
   surrounding-shape overfitting.
4. Test auditor: verify tests cover positive fixed cases, alias cases,
   malformed/unsupported diagnostics, metadata diagnostics, determinism, and
   preservation of previous suites.
5. Documentation auditor: verify roadmap, behavioral/domain docs, generation
   value inventory, missing inventory, and current state are coherent.
6. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m165_backend_control.py tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m167_source_operations.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1625_tsil_lexical.py tslgen/tests/test_m163_generation_variables.py tslgen/tests/test_m164_backend_value_queries.py tslgen/tests/test_m165_backend_control.py tslgen/tests/test_m166_backend_intrinsics.py tslgen/tests/test_m167_source_operations.py
find tslgen -type d -name __pycache__ -print
```

If the executor adds focused M168 test files, include them in the compileall
and targeted pytest commands. Remove validation-created `__pycache__`
directories before the final cache check if any are created.

## Completion Rules

If M168 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M168 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside
this prompt after M168 is accepted. Do not start M169 until the next prompt
explicitly selects it.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start Milestone 169 in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
