# M201 Post-Current-Suffix Intrinsic Modifier Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M200 as accepted.

This is a planning milestone. Do not modify implementation code. Use
read-only planner/evidence/documentation review as needed; if subagents are
used, they must be read-only. The orchestrator owns final state and next-prompt
updates.

## Accepted State

Accepted through:

```text
M200: Current-Type Intrinsic Suffix Translation
```

Selected milestone:

```text
Milestone 201: Post-Current-Suffix Intrinsic Modifier Planning
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
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/**/*.tsl` as corpus evidence

## Goal

Plan the next executable backend intrinsic modifier translation slice after
M200.

M200 translates current-type no-argument `intrin::suffix` requests for both
`suffix` and `infix` fields. The remaining unsupported modifier families must
now be assessed from the current corpus and typed handoff model before
selecting the next implementation task.

## Planner Scope

- Re-inventory the remaining unsupported modifier families after M200 using the
  accepted M182/M195/M197/M198/M200 discovery, lowering, and modifier
  translation paths.
- Classify the remaining families at least by:
  - string suffix requests such as `intrin::suffix("stream")`;
  - symbol suffix requests such as `intrin::suffix(ToBase)`;
  - symbol suffix requests used as `infix`, such as
    `infix=value<backend>(intrin::suffix(ToBase))`;
  - semantic `infix=to_type_suffix`;
  - symbol immediates such as `immediate(1)=index` and
    `immediate(1)=Index`;
  - FTF-002 `intrin::suffix(si?)` as source-data debt, not an
    implementation family.
- Identify what typed context each remaining family needs, such as
  destination/return-type bindings, return-type specialization names like
  `ToBase`, selected/current type, named suffix policy for `"stream"`,
  immediate argument provenance, backend metadata, or intrinsic-name assembly.
- Decide whether the next executable milestone should implement one remaining
  modifier family, implement intrinsic-name assembly over already translated
  modifiers, or first add a narrow typed context prerequisite.
- Preserve ADR-056: Rust intrinsic calls will later use explicit
  `core::arch::...` paths, but modifier translation must not prepend those
  paths.
- Preserve ADR-057: no-argument `intrin::suffix` means selected/current
  `TypeTag`; do not reinterpret it from surrounding source text.
- Preserve FTF-002: do not turn `intrin::suffix(si?)` into a supported
  semantic family.
- Produce the next concrete run prompt, expected as M202 unless the planner
  records a stop condition.

## Out Of Scope

- Implementation code.
- New production modules or tests.
- Generated output.
- Rendering.
- Rust intrinsic module qualification.
- Import-based Rust intrinsic rendering.
- Intrinsic-name assembly implementation.
- Dependency closure.
- Source repair.
- Broad TSIL or target-language parsing.
- Lowering changes unless the planner proves an accepted typed handoff cannot
  represent an observed corpus form.

## Required Output

- Update `docs/redesign/implementation-roadmap.md` with the M201 planning
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

Do not implement M202. Do not change lowering, backend translation code,
metadata, tests, generated output, or supplementary assets in this planning
milestone.

## Final Report

Report:

1. M201 planning verdict.
2. Selected next milestone and why.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
