# M209 Indexed-Vector Generic Immediate Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M208 as accepted.

This is a planning milestone. Use planning plus read-only review/audit
subagents. Do not modify implementation code. The orchestrator owns final
state and next-prompt updates.

## Accepted State

Accepted through:

```text
M208: Selected Signature-Parameter Immediate Execution
```

Selected planning target:

```text
Milestone 209: Indexed-Vector Generic Immediate Planning
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
- `tslgen/src/tslgen/domain/signatures.py`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/tests/test_m2065_signature_term_model.py`
- `tslgen/tests/test_m208_selected_signature_immediate_translation.py`
- `tsldata/primitives/load_store/array.tsl`
- `tsldata/primitives/**/*.tsl`

## Goal

Plan the smallest correct lowering path for the remaining observed
non-literal immediate family:

```text
immediate(1)=Index
```

in `tsldata/primitives/load_store/array.tsl` under:

```text
prim<s:=v[idx]> extract_value(a):
  generic_params:
    Index {kind int, default 0}
```

M208 deliberately kept this unsupported because `Index` is not a primitive
parameter binding. M209 must identify the typed ownership facts needed before
lowering may resolve it without raw-name magic.

## Planner Scope

- Inventory all observed `generic_params` blocks across
  `tsldata/primitives/**/*.tsl`, including parameter names, kinds, defaults,
  source locations, owning primitives, signatures, and body references when
  relevant.
- Inventory all observed indexed-vector signature terms such as `v[idx]` and
  connect them to their owning primitive parameters and nearby
  `generic_params` evidence.
- Re-check all remaining non-literal `immediate(N)=SYMBOL` modifier operands
  after M208 and confirm the remaining actionable family.
- Determine the minimal typed catalog and selected-context facts needed for a
  future executor to lower `immediate(N)=Index`. For example, decide whether
  the catalog needs a `PrimitiveGenericParameter` value with a constrained kind
  enum and default value, and whether selected lowering context needs a typed
  selected generic parameter binding.
- Decide whether the next executable slice should:
  - add catalog parsing/modeling for observed `generic_params` only;
  - add selected-context generic-parameter facts;
  - directly lower the exact `immediate(N)=SYMBOL` case when the symbol is a
    selected integer generic parameter connected to `v[idx]`;
  - or split those steps.
- Preserve the M208 boundary: signature-owned `sImm` parameter immediates stay
  handled by M208; indexed/generic immediates must use their own typed facts.

## Out Of Scope

- Implementation code changes.
- Translating `Index` by raw spelling.
- Treating every `generic_params` form as supported if it is not observed and
  documented in this planning pass.
- Full generic/template system design.
- C++ non-type template parameter rendering.
- Rust const generic rendering.
- Intrinsic-name assembly.
- Argument-list rewriting.
- Dependency closure.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Planning Output

Record in `docs/redesign/implementation-roadmap.md`:

- the exact observed `generic_params` forms and indexed-vector forms;
- the selected typed domain/selected-context boundary for the next executor;
- whether M210 is implementation or another planning slice;
- exact positive and negative coverage required for the next executor;
- explicit out-of-scope boundaries that prevent raw-name or broad generic
  overengineering.

Update `docs/agent/current-redesign-state.md` and create the next concrete
prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`.

## Required Validation

Run:

```bash
git diff --check
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- the plan uses `.tsl` corpus evidence as ground truth;
- the plan does not translate `Index` by spelling;
- the plan identifies typed catalog and selected-context ownership facts before
  lowering;
- the plan does not start a full generic/template system;
- the next prompt is concrete and executable.

## Final Report

Report:

1. Planning/review verdict.
2. What M209 decided.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
