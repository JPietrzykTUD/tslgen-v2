# M205 Post-Destination Intrinsic Modifier Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M204 as accepted.

This is a planning milestone. Do not modify implementation code. Use
read-only planner/evidence/documentation review as needed; if subagents are
used, they must be read-only. The orchestrator owns final state and next-prompt
updates.

## Accepted State

Accepted through:

```text
M204: Destination Return-Type Intrinsic Suffix Translation
```

Selected milestone:

```text
Milestone 205: Post-Destination Intrinsic Modifier Planning
```

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
- `docs/redesign/flaws-to-fix.md`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/src/tslgen/lowering/selected_specializations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/tests/test_m204_destination_return_type_intrinsic_suffix_translation.py`
- `tsldata/primitives/**/*.tsl` as corpus evidence

## Goal

Plan the next lowering-focused intrinsic modifier slice after M204.

M204 proves that destination/return-type suffix translation is safe once the
suffix operand has already lowered to typed selected-binding IR. The remaining
non-flaw modifier families need a fresh boundary check before execution:

- `infix=to_type_suffix` is an exact semantic marker that likely needs selected
  return-type context;
- `immediate(N)=index` and `immediate(N)=Index` need selected generic or
  immediate parameter value context;
- FTF-002 `intrin::suffix(si?)` remains source-data debt only.

## Planner Scope

- Re-inventory remaining unsupported modifier families after M204 using the
  accepted M182/M195-M204 discovery, lowering, and modifier translation paths.
- Keep context-free corpus accounting distinct from focused selected-context
  behavior. Do not force corpus-wide counts to change by inventing magic names.
- Classify the exact typed context needed for:
  - `infix=to_type_suffix`;
  - `immediate(N)=index`;
  - `immediate(N)=Index`;
  - FTF-002 `intrin::suffix(si?)`.
- Decide whether M206 should:
  - implement exact `infix=to_type_suffix` lowering/translation through typed
    selected return-type context;
  - add selected generic/immediate parameter binding context first;
  - or return to planner with a stop condition.
- Preserve ADR-056, ADR-057, ADR-058, ADR-059, and FTF-002.

## Boundary Rules

- Source-owned names such as `ToBase`, `ResultBase`, `index`, and `Index` must
  not become backend magic strings.
- Backend translation must consume typed lowering results or typed modifier
  facts, not parse raw source text.
- Exact semantic markers may be selected only with explicit accepted source
  forms, diagnostics, and tests.
- Do not broaden into intrinsic-name assembly, renderer policy, dependency
  closure, or target-language expression parsing.

## Out Of Scope

- Implementation code.
- New production modules or tests.
- Generated output.
- Rendering.
- Rust intrinsic module qualification.
- Intrinsic-name assembly implementation.
- Dependency closure.
- Source repair.
- Broad TSIL or target-language parsing.
- Treating `ToBase`, `index`, or `Index` as magic raw strings.
- Resolving or repairing FTF-002 `intrin::suffix(si?)`.

## Required Output

- Update `docs/redesign/implementation-roadmap.md` with the M205 planning
  result and selected next milestone.
- Update `docs/agent/current-redesign-state.md` to point at the next concrete
  prompt, or record an explicit stop condition.
- Create the next concrete prompt under `docs/agent/runs/`, unless a stop
  condition is recorded.
- Record any architecture decision or open question if the corpus requires a
  context/model choice before implementation.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Stop Rule

Do not implement M206. Do not change lowering, backend translation code,
metadata, tests, generated output, or supplementary assets in this planning
milestone.

## Final Report

Report:

1. M205 planning verdict.
2. Selected next milestone and why.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
