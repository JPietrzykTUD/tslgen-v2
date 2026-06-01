# M211 Post-Selected-Immediate Lowering Completion Gate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M210 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, boundary/simplicity,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 210: Indexed Generic Immediate Execution
```

M208 closed the selected-signature `sImm` immediate family by lowering
`immediate(N)=SYMBOL` into a typed selected-signature immediate fact only when
`SYMBOL` is a selected runtime primitive parameter bound to the `sImm`
signature term.

M210 closed the observed indexed-vector generic immediate family by parsing
observed `generic_params` declarations into typed primitive-local
compile-time/template parameter facts and lowering `immediate(N)=SYMBOL` into
a typed selected-generic immediate fact only when `SYMBOL` is a selected
primitive-local integer generic parameter and the selected signature contains
`SignatureTermKind.INDEXED_VECTOR_ELEMENT`.

Both backend modifier paths consume already-lowered values. Neither path
renders C++/Rust template syntax, evaluates test-case generic values, rewrites
arguments, assembles intrinsic names, or resolves names by spelling.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- M208 and M210 tests and implementation files.

## Goal

Run a lowering-focused completion gate after the selected source-owned
non-literal intrinsic immediate families are accepted.

The gate must decide one of two outcomes:

1. **Lowering complete by current contract after selected immediates.**
   Record that the remaining observed unresolved forms are backend/output
   translation/rendering, backend metadata, accepted opaque requests, source
   helper calls, or deferred broad parsing. Create the next concrete
   backend/output prompt.
2. **Exactly one remaining lowering-owned gap exists.**
   Select that single gap as the next milestone and create a concrete
   execution-review-loop prompt for it.

Do not start backend implementation in this prompt.

## Evidence Work

Use the current `tsldata/**/*.tsl` corpus as ground truth. Keep these buckets
separate:

- primitive-body TSIL/source forms that lowering must recognize;
- accepted typed facts, typed requests, and typed handoff values;
- backend metadata definitions under `tsldata/detail/lang/**`;
- source-authored helper calls such as `details::*`;
- backend translation/rendering work that should consume accepted lowering IR.

At minimum, reconcile:

- accepted M155-M187 lowering behavior;
- accepted M208/M210 selected immediate behavior;
- remaining backend intrinsic modifier unsupported families, especially any
  non-literal immediate fields;
- source-operation, backend-output, backend-value, backend-type, mask,
  generation-control, generation-loop, variable, call, type, and value request
  boundaries;
- whether any remaining backend/output stage would need to rescan raw text for
  a lowering-owned fact that is not yet modeled.

Useful evidence probes include:

```bash
rg -n "immediate\\([0-9]+\\)=[A-Za-z_][A-Za-z0-9_]*" tsldata/primitives -g "*.tsl"
rg -n "generic_params:|kind int|kind bool|kind simd_type" tsldata/primitives -g "*.tsl"
rg -n "assume_aligned<|array_type<|pack<|mask<|intrin<|intrin_compose<|cast<|mem<|io<|type<|value<|call<|var<|let<|loop<|if<|else<|switch<" tsldata -g "*.tsl"
rg -o --no-filename "[A-Za-z_][A-Za-z0-9_:]*<" tsldata -g "*.tsl" | sort -u
rg -o --no-filename "details::[A-Za-z_][A-Za-z0-9_]*" tsldata -g "*.tsl" | sort -u
```

These are evidence probes, not accepted syntax definitions.

## Completion Criteria

Lowering may be declared complete by current contract only if remaining
observed forms are one of:

- already accepted typed facts, semantic values, request islands, handoff
  values, or opaque source tokens;
- backend translation or rendering obligations;
- backend metadata definitions rather than primitive-body lowering;
- source-authored helper calls that lowering should not semantically rewrite;
- broad/deferred target-language parsing, statement parsing, expression
  parsing, recursive payload discovery, or source repair.

If a remaining form must be consumed by lowering before backend/output can
reason about it without rescanning raw text, select exactly one next
milestone. The selected milestone must name exact accepted source forms,
typed values, diagnostics, tests, and out-of-scope work.

## Guardrails

- Do not add production code or tests.
- Do not create a broad TSIL parser, expression parser, statement parser,
  recursive payload walker, registry, dispatcher, or worklist plan.
- Do not turn backend translation/rendering work into lowering work just
  because it is still missing.
- Do not model `details::*` helper calls as arithmetic/operator lowering.
- Do not reopen raw-name immediate resolution. `index` and `Index` are
  already covered only through accepted typed ownership facts.
- Do not require lowering to solve opaque payloads inside accepted
  backend/output request islands unless the evidence proves a backend stage
  cannot consume the accepted request without a missing typed fact.
- Keep any next milestone thin enough for an execution-review loop.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: corpus scan and classification.
2. Boundary/simplicity auditor: slippery-slope and backend/output boundary.
3. Documentation auditor: consistency of completion result and next prompt.
4. Validation auditor: required validation command and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused documentation or
prompt fixes and rerun the relevant focused audit. If any returns
`Return To Planner` or `Reject`, record that result and create the
appropriate next prompt.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Report the exact result.

## Completion Rules

Before finishing:

- update `docs/redesign/lowering-completeness-audit.md`;
- update `docs/redesign/missing-lowering-inventory.md` and
  `docs/redesign/tsil-surface-inventory.md` if classifications changed;
- update `docs/redesign/implementation-roadmap.md` with the planning result;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the next milestone.

## Final Report

Report:

1. Planning result.
2. Whether lowering is complete by current contract or the exact next
   lowering milestone selected.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
