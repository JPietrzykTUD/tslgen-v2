# Post-M187 Lowering Completion Gate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M187 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, boundary/simplicity,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 187: Exact Backend/Output Source-Island Discovery Boundary
```

M187 added exact backend/output source-island request discovery for:

```text
assume_aligned<...>(...)
array_type<...>
pack<...>(...)
```

The accepted boundary preserves request identity and opaque payload text only.
It does not solve alignment, array layout/type, pack semantics, nested
payloads, argument splitting, backend translation, declaration rendering, or
C++/Rust output.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/tsil-surface-inventory.md`
- The accepted source-island modules for M164-M187.

## Goal

Run a final lowering-focused completion gate after M187.

The gate must decide one of two outcomes:

1. **Lowering complete by current contract.**
   Record that accepted lowering now covers the current generation-relevant
   TSIL keyword/request/fact surface needed before backend/output integration,
   and create the next concrete prompt for the first backend/output planning
   step.
2. **Exactly one remaining lowering-owned gap exists.**
   Select that single gap as the next milestone and create a concrete
   execution-review-loop prompt for it.

Do not start backend implementation in this prompt.

## Evidence Work

Use the current `tsldata/**/*.tsl` corpus as ground truth, while keeping
primitive-body TSIL, backend translation metadata, type/extension definitions,
and support helper definitions in separate buckets.

At minimum, reconcile:

- exact TSIL keyword/head families observed across `tsldata/**/*.tsl`;
- accepted M155-M187 lowering behavior;
- backend/output-owned forms that should remain unresolved requests or raw
  source convention;
- source-authored support helpers such as `details::*`;
- any forms under `tsldata/detail/lang/**` that are backend metadata rather
  than primitive-body lowering obligations.

Useful probes include:

```bash
rg -n "tsil \"" tsldata -g "*.tsl"
rg -o --no-filename "[A-Za-z_][A-Za-z0-9_:]*<" tsldata -g "*.tsl"
rg -o --no-filename "details::[A-Za-z_][A-Za-z0-9_]*" tsldata -g "*.tsl"
rg -n "if<runtime>|else<runtime>|switch<runtime>|if<compile>|else<compile>|switch<compile>" tsldata -g "*.tsl"
rg -n "assume_aligned<|array_type<|pack<|mask<|intrin<|intrin_compose<|cast<|mem<|io<|type<|value<|call<|var<|let<|loop<|if<|else<|switch<" tsldata -g "*.tsl"
```

These commands are evidence probes, not accepted syntax definitions.

## Completion Criteria

Lowering may be declared complete by current contract only if the remaining
observed forms are one of:

- already accepted typed facts, typed semantic values, typed request islands,
  typed handoff values, or source-owned opaque tokens;
- backend/output translation or rendering obligations;
- backend metadata definitions rather than primitive-body lowering;
- source-authored support-helper calls that should not be semantically
  rewritten by lowering;
- broad/deferred target-language parsing, statement parsing, expression
  parsing, recursive payload discovery, or source repair.

If a remaining form must be consumed by lowering before backend/output can
reason about it without rescanning raw text, select exactly one next
milestone. The milestone must state exact accepted source forms, typed values,
diagnostics, tests, and out-of-scope work.

## Guardrails

- Do not add production code.
- Do not create a broad TSIL parser, expression parser, statement parser,
  recursive payload walker, registry, dispatcher, or worklist plan.
- Do not turn backend translation/rendering work into lowering work just
  because it is still missing.
- Do not model `details::*` helper calls as arithmetic/operator lowering.
- Do not require lowering to solve M187 payloads such as
  `value<generation>(...)` or `type<generation>(...)` while they remain
  intentionally opaque inside backend/output request islands.
- Keep any next milestone thin enough for an execution-review loop.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: corpus scan and classification.
2. Boundary/simplicity auditor: slippery-slope and backend/output boundary.
3. Documentation auditor: consistency of completion result and next prompt.
4. Validation auditor: required validation command and workspace hygiene.

If any auditor returns `Needs Revision`, make only focused documentation/prompt
fixes and re-run the relevant focused audit. If any returns `Return To
Planner` or `Reject`, record that result and create the appropriate next
prompt.

## Required Validation

Run:

```bash
git diff --check
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
