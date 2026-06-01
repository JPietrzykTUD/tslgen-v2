# M199 Post-Prefix Intrinsic Modifier Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M198 as accepted.

This is a planning milestone. Do not modify implementation code. Use
read-only planner/evidence/documentation review as needed; if subagents are
used, they must be read-only. The orchestrator owns final state and next-prompt
updates.

## Accepted State

Accepted through:

```text
M198: Intrinsic Prefix Modifier Translation
```

Selected milestone:

```text
Milestone 199: Post-Prefix Intrinsic Modifier Planning
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
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/_intrinsic_metadata_modifiers.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/lowering/backend_value_queries.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py`
- `tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/**/*.tsl` as corpus evidence

## Goal

Plan the next executable backend intrinsic translation slice after M198.

M198 translated the observed typed `intrin::prefix` modifier family and kept
Rust `core::arch::*` qualification out of modifier translation. The remaining
unsupported modifier families must now be assessed from the current corpus and
typed handoff model before selecting the next implementation task.

## Planner Scope

- Re-inventory remaining unsupported modifier families after M198 using the
  accepted M182/M195/M197/M198 discovery, lowering, and modifier translation
  paths.
- Classify the remaining families at least by:
  - no-argument suffix requests;
  - string-argument suffix requests such as `intrin::suffix("stream")`;
  - symbol-argument suffix requests such as `intrin::suffix(ToBase)`;
  - backend-value infix suffix requests;
  - symbol immediates;
  - `infix=to_type_suffix`;
  - any already translated literal/type-derived suffix/prefix/post/infix
    families needed as context.
- Identify what typed context each remaining family needs, such as selected
  extension, selected type tag, resolved aliases, return-type bindings,
  immediate argument provenance, or backend metadata.
- Decide whether the next executable milestone should implement one remaining
  modifier family, implement intrinsic-name assembly over already translated
  modifiers, or first add a narrow typed context prerequisite.
- Keep ADR-056 intact: Rust intrinsic calls will later use explicit
  `core::arch::...` paths, but modifier translation must not prepend those
  paths.
- Keep M198's corpus boundary intact: do not invent ARM/NEON/SVE
  `intrin::prefix` rules unless the `.tsl` corpus starts using that modifier.
- Produce the next concrete run prompt, expected as M200 unless the planner
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

- Update `docs/redesign/implementation-roadmap.md` with the M199 planning
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

Do not implement M200. Do not change lowering, backend translation code,
metadata, tests, generated output, or supplementary assets in this planning
milestone.

## Final Report

Report:

1. M199 planning verdict.
2. Selected next milestone and why.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
