# M210 Indexed Generic Immediate Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M209 as accepted.

This is an implementation milestone. Use the executor-review loop: one
write-capable executor, then read-only reviewer/auditor subagents, then one
focused revision executor only if the consolidated verdict is `Needs
Revision`. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M209: Indexed-Vector Generic Immediate Planning
```

Selected milestone:

```text
Milestone 210: Indexed Generic Immediate Execution
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
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/tests/test_m2065_signature_term_model.py`
- `tslgen/tests/test_m208_selected_signature_immediate_translation.py`
- `tsldata/primitives/load_store/array.tsl`
- `tsldata/primitives/load_store/rnd_access.tsl`
- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/mask/bitwise.tsl`

## Goal

Implement the M209-selected typed ownership path for the remaining observed
non-literal immediate family:

```text
immediate(1)=Index
```

in the NEON `extract_value` implementation. `Index` must resolve only through
the selected primitive's typed `generic_params` facts, not through raw-name
magic.

## Executor Scope

- Add typed primitive-local generic parameter domain values. Use dataclasses
  and an enum or equivalent typed value for the observed kinds:
  - `int`
  - `bool`
  - `simd_type`
- Preserve typed defaults and source provenance:
  - `int` defaults as integers;
  - `bool` defaults as booleans;
  - absent defaults as `None`.
- Support only the observed declaration spellings at the parser/catalog
  boundary:
  - block style:

    ```text
    PreserveSign:
      kind bool
      default true
    ```

  - inline style:

    ```text
    Index {kind int, default 0}
    IndicesType {kind simd_type}
    N {kind int, default 1}
    ```

- Promote generic parameter facts onto `Primitive` and
  `SelectedImplementationLoweringContext`.
- Add a lowering-owned value for a selected generic immediate parameter. It
  must carry:
  - the immediate argument index from `immediate(N)`;
  - the resolved typed generic parameter fact;
  - source text and source location.
- During backend intrinsic modifier handoff lowering, resolve
  `immediate(N)=SYMBOL` into the generic immediate value only when all are
  true:
  - the modifier key is `immediate(N)`;
  - `SYMBOL` resolves by exact name to one selected primitive-local generic
    parameter;
  - that generic parameter kind is `int`;
  - the selected primitive signature includes
    `SignatureTermKind.INDEXED_VECTOR_ELEMENT`.
- Backend intrinsic modifier translation must consume only the already-lowered
  generic immediate value. It must not inspect raw symbol names,
  `generic_params`, selected context, primitive signatures, or test values to
  decide whether something is immediate.
- Preserve M208 behavior for signature-parameter `sImm` immediates.

## Required Positive Coverage

- A selected `extract_value`-like context with signature `s:=v[idx]`,
  parameter `(a)`, and `generic_params.Index {kind int, default 0}` lowers
  `immediate(1)=Index` to the typed generic immediate value and backend
  translation consumes it.
- The same path works with an arbitrary integer generic parameter name, proving
  `Index` is not hardcoded.
- Corpus characterization proves the observed `array.tsl` NEON
  `immediate(1)=Index` occurrence is accepted under matching selected context.
- Catalog/domain coverage records all observed `generic_params` forms:
  `PreserveSign bool default true`, `IndicesType simd_type`, `N int default 1`,
  and `Index int default 0`.

## Required Negative Coverage

- `immediate(1)=Index` remains unsupported without a matching selected generic
  parameter.
- `immediate(1)=Index` remains unsupported when the selected generic parameter
  kind is not `int`.
- `immediate(1)=N` remains unsupported for a selected integer generic
  parameter when the selected primitive signature has no indexed-vector term.
- Raw `BackendIntrinsicModifierSymbolOperand("Index")` remains unsupported in
  backend translation.
- Existing M208 `sImm` signature-parameter behavior remains unchanged.
- Unsupported or malformed generic parameter kinds/defaults produce
  diagnostics at the parser/catalog boundary; they are not repaired.

## Out Of Scope

- Full generic/template system design.
- Resolving `Index`, `N`, `PreserveSign`, or `IndicesType` by spelling.
- Evaluating test-case generic values.
- Lowering generic parameter uses in `if<compile>`, `call<primitive=...>`,
  casts, array subscripts, type aliases, selectors, or loop bounds.
- Validating that the compose argument text at position `N` matches the symbol.
- C++ non-type template parameter rendering.
- Rust const generic rendering.
- Intrinsic-name assembly.
- Argument-list rewriting.
- Dependency closure.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m210_indexed_generic_immediate_translation.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m208_selected_signature_immediate_translation.py tslgen/tests/test_m2065_signature_term_model.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- generic parameter facts are typed domain/catalog facts, not dictionaries or
  raw string conventions past the parser boundary;
- lowering resolves generic immediates through selected primitive-local facts
  and the indexed-vector signature term, not through names such as `Index`;
- backend translation consumes only the already-lowered generic immediate
  value and does not inspect selected context or raw symbols;
- M208 signature-parameter immediates remain stable;
- `N`, `PreserveSign`, `IndicesType`, unknown symbols, and raw backend symbol
  operands remain unsupported for immediate lowering unless explicitly in the
  selected M210 rule;
- the change does not render C++/Rust compile-time parameter syntax, assemble
  intrinsic names, parse broad TSIL, rewrite arguments, or repair source.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M210 result, and create the
next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Executor/review verdict.
2. What M210 changed.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
