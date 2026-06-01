# M203 Post-Stream Intrinsic Modifier Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M202 as accepted.

This is a planning milestone. Do not modify implementation code. Use
read-only planner/evidence/documentation review as needed; if subagents are
used, they must be read-only. The orchestrator owns final state and next-prompt
updates.

## Accepted State

Accepted through:

```text
M202: Stream Intrinsic Suffix Translation
```

Selected milestone:

```text
Milestone 203: Post-Stream Intrinsic Modifier Planning
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
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/tests/test_m202_stream_intrinsic_suffix_translation.py`
- `tsldata/primitives/**/*.tsl` as corpus evidence

## Goal

Plan the next executable intrinsic modifier or context/lowering slice after
M202.

M202 translates the exact named stream suffix policy. The remaining unsupported
modifier families now need a fresh boundary check before execution, because the
largest remaining family uses source-owned symbols such as `ToBase`.

## Planner Scope

- Re-inventory the remaining unsupported modifier families after M202 using the
  accepted M182/M195-M202 discovery, lowering, and modifier translation paths.
- Confirm the expected remaining corpus:

```text
643 total modifier fields
587 translated after M202
56 still unsupported:
  20 suffix=value<backend>(intrin::suffix(SYMBOL))
     - 19 actionable ToBase cases
     - 1 FTF-002 intrin::suffix(si?) source-data flaw
  13 infix=value<backend>(intrin::suffix(ToBase))
  4  infix=to_type_suffix
  19 immediate(N)=symbol
```

- Classify the typed context needed for each remaining family:
  - destination/return-type binding symbols such as `ToBase`;
  - whether `ToBase` is available from selected primitive/implementation
    context or needs a focused lowering/catalog-context prerequisite;
  - the relationship between `suffix(ToBase)`,
    `infix=value<backend>(intrin::suffix(ToBase))`, and
    `infix=to_type_suffix`;
  - symbol immediate argument provenance for `index` and `Index`;
  - FTF-002 `intrin::suffix(si?)` as source-data debt only.
- Decide whether M204 should implement one remaining family, add a narrow typed
  context prerequisite, or return to planner with a stop condition.
- Prefer source-owned typed context over raw text inference. Names like
  `ToBase` are arbitrary user-authored binding names and must not be treated as
  magic keywords unless resolved from selected primitive data.
- Preserve ADR-056, ADR-057, ADR-058, and FTF-002.

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
- Treating `ToBase` or `Index` as magic raw strings.
- Lowering changes unless the planner proves an accepted typed handoff cannot
  represent an observed corpus form or cannot carry the required selected
  context.

## Required Output

- Update `docs/redesign/implementation-roadmap.md` with the M203 planning
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

Do not implement M204. Do not change lowering, backend translation code,
metadata, tests, generated output, or supplementary assets in this planning
milestone.

## Final Report

Report:

1. M203 planning verdict.
2. Selected next milestone and why.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
