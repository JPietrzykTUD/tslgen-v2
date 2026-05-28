# M145 Execution Review Loop Prompt

You are executing and reviewing the accepted next milestone after M144:

```text
Milestone 145: Primitive-Call Target Candidate Matching Boundary
```

Milestones 1 through 144 are accepted. M144 lowered already recognized
`call<primitive=...>(...)` selector payloads into typed selector payload
values. It refined `Vec` into the single semantic value
`CurrentVector(extension: ExtensionName, type_tag: TypeTag)`, lowered exact
type-valued selector entries through the selected M143 type environment,
parsed concrete `attrs[...]` selector payloads, and kept raw selector text as
diagnostic/provenance context only. M144 still deliberately stopped before
primitive-call target matching, dependency closure, dependency-body lowering,
call-argument lowering, and backend rendering.

M145 should take the next small step: consume the M144 typed selector payload
and identify the exact candidate primitive implementation for supported
primitive-call selectors. This is a target-candidate matching boundary, not a
dependency solver and not primitive-call rendering.

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
- `docs/redesign/tsil-type-query-inventory.md`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/analysis/selection.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/type_queries.py`
- `tslgen/src/tslgen/lowering/selector_payload.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m144_selector_payload.py`

## Goal

Add a small typed matching boundary that turns an M144
`PrimitiveCallSelectorPayload` plus selected implementation context and catalog
into either:

- a typed candidate match for one existing catalog primitive implementation; or
- explicit diagnostics explaining why this selector cannot be matched by the
  currently supported boundary.

Supported exact behavior:

- `@self` resolves to the current selected primitive name.
- A named selector resolves to that primitive name.
- No specialization means the current selected vector `(extension, type_tag)`.
  This is the observed current-context call shape such as
  `call<primitive=add>(left, right)`.
- A single exact vector-valued specialization may select the target
  `(extension, type_tag)` if the M144 payload value is already concrete:
  `CurrentVector`, an alias that preserved `CurrentVector`, or a
  backend-type reference whose already-lowered underlying value is concrete.
  Inspect the typed value only; do not render backend type text.
- Concrete selector attrs match catalog primitive attribute variants with the
  same key, optional key-argument, and value semantics used by normal target
  selection.

Diagnostics should be explicit for:

- unknown target primitive name;
- no matching concrete attribute variant;
- no implementation for the requested extension/type;
- unsupported or non-concrete specialization values;
- unsupported extra selector dimensions such as `shift`, `PreserveSign`,
  `index`, extension operands, or numeric selector dimensions.

The result should be a small typed value, for example a
`PrimitiveCallTargetMatch` that carries the matched `SelectedImplementation`,
the original selector payload or source provenance, and diagnostics in a
result object. Use an existing selected implementation / target object where
that keeps ownership simple. Do not introduce a registry, dispatcher,
dependency worklist, fixpoint mechanism, or broad selector-language AST.

## Required Executor Task

Run exactly one write-capable executor for M145. The executor should:

1. Inspect dirty worktree state before editing and preserve unrelated changes.
2. Keep M126-M144 parser/catalog/body-token/selection/lowering behavior stable
   unless a focused test exposes a defect.
3. Add a focused typed candidate-match model in the existing lowering/domain
   ownership area. Prefer one or two obvious dataclasses and pure helper
   functions.
4. Add a lowerer entry point that consumes a selected implementation, catalog,
   and an M144 `PrimitiveCallSelectorPayload`, then returns a target-match
   result plus diagnostics.
5. Reuse existing catalog/selection semantics for primitive names,
   attributes, extension, and type matching where practical. If existing
   `Selector` diagnostics are adapted, preserve call-selector source
   provenance so a TSL author sees the failing call site.
6. Match only exact supported vector selectors:
   - no specialization -> current selected vector;
   - `CurrentVector`;
   - source-defined aliases that preserved `CurrentVector`;
   - a backend-type reference only by inspecting the already-lowered
     underlying value, never by rendering backend type text.
7. Treat selector symbols, selector literals, extension operands, multiple
   specialization entries, and non-concrete type values as unsupported for
   M145 matching unless a test in this milestone explicitly selects one exact
   behavior. Do not interpret `shift`, `PreserveSign`, `index`, numeric
   dimensions, or extension operands as semantic selector matches.
8. Add focused positive tests for:
   - `@self[Vec]`;
   - named `sub[Vec]`;
   - a naked current-context named call such as `sub`;
   - attrs-only named calls such as `sub attrs[mask=zero]`;
   - specialization-plus-attrs calls such as `load[Vec] attrs[aligned=false]`;
   - a source alias that preserves `Vec`.
9. Add focused negative tests for:
   - unknown primitive name;
   - no concrete attribute variant;
   - no implementation for selected extension/type;
   - unsupported selector symbol/dimension such as `PreserveSign`;
   - non-concrete backend/type value that cannot produce a target
     `(extension, type_tag)`.
10. Update redesign docs if the target-match result ownership, diagnostics,
    or out-of-scope dependency/rendering boundary is clarified.

## Out Of Scope

Dependency closure; selecting all transitive dependency implementations;
dependency-body lowering; recursive call argument lowering; matching nested
calls by payload arguments; backend call rendering; backend type text
rendering; source repair; broad TSIL expression parsing; assignment/indexing
lowering; semantic interpretation of selector symbols or literals such as
`shift`, `PreserveSign`, `index`, or numeric dimensions; interpreting
extension operands as candidate-ranking rules; runtime `tsldata`, `frozen`, or
`tslgenold` dependencies; registries, dispatchers, fixpoint mechanisms, broad
request/result/worklist families, or source-data repair.

## Required Review/Audit Subagents

After the executor finishes, use read-only subagents:

1. Architecture reviewer: verify M145 adds only a typed target-candidate
   matching boundary and does not become dependency closure, dependency-body
   lowering, backend rendering, broad expression parsing, or broad machinery.
2. Boundary auditor: verify matching consumes selected context, catalog facts,
   M144 typed selector payloads, and concrete attrs; raw selector text remains
   provenance only; no runtime `tsldata`, `frozen`, or `tslgenold` dependency
   is introduced.
3. Evidence auditor: verify supported positive cases are grounded in observed
   selector forms from `tsldata/**/*.tsl` or accepted clean-restart tests, and
   unsupported cases are explicit diagnostics.
4. Documentation auditor: verify docs accurately describe target-candidate
   matching and defer dependency closure, dependency-body lowering, and backend
   rendering.
5. Validation auditor: verify required validation ran and report exact command
   results.

Reviewer/auditor subagents are read-only. They must not edit files.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py
python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m144_selector_payload.py tslgen/tests/test_m145_primitive_call_target_matching.py
find tslgen -type d -name __pycache__ -print
```

Do not run the old `tslgenold` validation profile as proof of the clean
product slice. Remove validation-created `__pycache__` directories before the
final cache check if any are created.

## Completion Rules

If M145 review returns `Accept` or `Accept With Follow-Ups`:

- update `docs/agent/current-redesign-state.md`;
- mark M145 accepted in `docs/redesign/implementation-roadmap.md`;
- record follow-ups in state if any;
- create the next concrete run prompt under `docs/agent/runs/`.

To keep planning and execution integrated, do the next-run planning inside this
prompt after M145 is accepted. Do not start dependency closure, dependency-body
lowering, or backend call rendering until M145 is accepted and the next prompt
explicitly selects that work.

If review returns `Needs Revision`, run one focused revision executor and then
a focused re-review. If review returns `Return To Planner` or `Reject`, stop
implementation and create the appropriate planner/rollback prompt instead of
continuing.

Do not start the next milestone implementation in this prompt.

## Final Report

Report:

1. Files/directories changed.
2. Executor summary.
3. Review/audit verdicts and any follow-ups.
4. Validation commands and exact results.
5. Next active prompt path.
