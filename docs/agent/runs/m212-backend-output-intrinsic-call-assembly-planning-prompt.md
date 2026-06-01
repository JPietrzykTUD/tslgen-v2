# M212 Backend Output Intrinsic Call Assembly Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M211 as accepted.

This is a planning/documentation task. Do not implement production code or
tests. Use read-only subagents for evidence, architecture/boundary,
documentation, and validation audits. The orchestrator owns final state and
next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 211: Post-Selected-Immediate Lowering Completion Gate
```

M211 declares lowering complete by current contract after selected immediates.
M208 covers selected-signature `sImm` immediates, M210 covers selected
indexed-vector generic immediates, and no further lowering-owned gap is
selected. Remaining work is backend/output translation, rendering, backend
metadata consumption, support-helper availability, artifact integration, or
broad/deferred parsing that must not be reopened by default.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/redesign/tsil-surface-inventory.md`
- `docs/redesign/flaws-to-fix.md`
- M188-M191 generated-project/output docs and tests.
- M190-M210 backend metadata, intrinsic modifier, signature, and immediate
  docs/tests/implementation files.

## Goal

Plan the next backend/output milestone after lowering completion.

The preferred direction is a typed backend intrinsic invocation assembly
boundary: consume accepted intrinsic request islands plus translated modifier
results and produce the next typed backend/output render input for intrinsic
calls. The plan must verify whether that is the smallest high-value next slice
or whether another backend/output prerequisite is more urgent.

## Planning Questions

Answer these before selecting the next milestone:

- What typed facts/results already exist for direct `intrin<...>(...)` and
  `intrin_compose<...>(...)` islands after M166, M182, and M195-M210?
- What must an intrinsic invocation assembly result contain so a later C++ or
  Rust renderer can render intentionally without parsing raw TSIL again?
- Which pieces are already decided typed values, and which pieces must remain
  opaque source payloads or explicit unresolved backend/output requests?
- How should diagnostics distinguish unsupported intrinsic assembly inputs
  from missing backend metadata, missing modifier translation, and intentionally
  opaque argument text?
- Does the next executable slice need both C++ and Rust assembly contracts, or
  should it produce backend-neutral invocation facts and leave
  language-specific spelling to later backend renderers?

## Scope Options

Choose exactly one next milestone. The expected candidates are:

- **Backend intrinsic invocation assembly.** Build a typed assembly boundary
  over accepted intrinsic islands and translated modifier results, preserving
  opaque argument text and provenance.
- **Backend intrinsic render model.** If assembly already exists well enough,
  select the smallest typed render-model slice that consumes it without
  putting semantics into templates.
- **Prerequisite backend metadata gap.** If assembly cannot proceed because a
  specific accepted typed metadata fact is missing, select exactly that gap.

If a different backend/output prerequisite is clearly higher value, record the
evidence and select only that one milestone.

## Guardrails

- Do not reopen lowering or add another lowering-owned source scan.
- Do not parse arbitrary intrinsic argument expressions.
- Do not assemble primitive dependency closure.
- Do not render whole generated projects.
- Do not move backend semantic choices into templates.
- Do not hardcode backend intrinsic names, prefixes, suffixes, register types,
  feature gates, or type spellings in presentation templates.
- Do not add a registry, dispatcher, worklist, or broad IR family unless the
  plan names two accepted consumers that need the same stable concept.
- Preserve `details::*` helpers as source-authored/backend-support helper
  calls unless a future milestone explicitly selects support-helper modeling.

## Required Review/Audit Subagents

Run read-only subagents:

1. Evidence auditor: accepted backend intrinsic facts/results and corpus
   pressure.
2. Architecture/boundary auditor: template boundary, typed render model, and
   no-lowering-reopen check.
3. Documentation auditor: roadmap/state/prompt consistency.
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

- update `docs/redesign/implementation-roadmap.md` with the planning result;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- update other redesign docs only if the planning decision changes or
  clarifies an accepted design boundary;
- do not start the next milestone.

## Final Report

Report:

1. Planning result.
2. Selected next milestone and why it is useful.
3. Review/audit verdicts.
4. Validation command and exact result.
5. Next active prompt path.
