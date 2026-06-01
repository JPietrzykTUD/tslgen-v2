# M208 Selected Signature Immediate Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M207 as accepted.

This is an implementation milestone. Use the executor-review loop: one
write-capable executor, then read-only reviewer/auditor subagents, then one
focused revision executor only if the consolidated verdict is `Needs
Revision`. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M207: Selected Symbol Immediate Planning
```

Selected milestone:

```text
Milestone 208: Selected Signature-Parameter Immediate Execution
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
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`
- `tslgen/tests/test_m206_to_type_suffix_infix_translation.py`
- `tslgen/tests/test_m2065_signature_term_model.py`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/load_store/array.tsl`

## Goal

Add a lowering-owned representation for source-owned symbol immediate modifier
operands. Lowering resolves the symbol only when it is a selected primitive
parameter whose M206.5 signature term is `sImm`; backend translation then
consumes that already-lowered value.

The accepted corpus evidence is:

- 18 `immediate(1)=index` occurrences in
  `tsldata/primitives/conversion/repr_change.tsl` under
  `prim<v:=(v,sImm)>[cast=convert, direction=up] convert_up(data, index):`.
- 1 `immediate(1)=Index` occurrence in
  `tsldata/primitives/load_store/array.tsl` under
  `prim<s:=v[idx]> extract_value(a):`.

M208 handles only the first family. `Index` is not a primitive parameter and
must remain unsupported until a separate indexed-vector/generic-parameter
ownership model is selected.

## Executor Scope

- Add a typed lowered selected-signature-immediate parameter value for backend
  intrinsic modifier handling. A reasonable shape is:

  ```python
  @dataclass(frozen=True, slots=True)
  class LoweredSelectedSignatureImmediateParameter:
      parameter: SignatureParameterTerm
      source_text: str
      source: SourceLocation
  ```

  The exact name may differ, but the model must carry the resolved typed
  parameter binding and source provenance. This is a lowering result, not a
  backend decision. Do not represent the semantic value as a raw string.

- During lowering of backend intrinsic modifier handoff fields, resolve
  `immediate(N)=SYMBOL` into the typed lowered value only when all of these are
  true:
  - the modifier key is `immediate(N)`;
  - `SYMBOL` resolves by exact name to one selected primitive parameter in
    `SelectedImplementationLoweringContext.parameter_signature_terms`;
  - that parameter's term kind is `SignatureTermKind.SCALAR_IMMEDIATE`.

- Keep unresolved symbols and non-`sImm` parameters as
  `BackendIntrinsicModifierSymbolOperand` or an equivalent unsupported
  boundary that preserves current diagnostics.
- Backend translation must consume only the already-lowered selected-signature
  immediate value. It must not inspect
  `SelectedImplementationLoweringContext`, `parameter_signature_terms`,
  `SignatureTermKind`, primitive signatures, or raw source-owned symbol names
  to decide whether something is immediate.
- Backend translation of the already-lowered value produces a typed backend
  modifier result. The result must record:
  - the immediate argument index from `immediate(N)`;
  - the selected parameter identity/binding;
  - source provenance.
- The translated value must not be a literal integer and must not be rendered
  C++ or Rust syntax. It is a typed compile-time parameter reference for later
  renderer work.
- Preserve the context-free M195 behavior: without selected context, raw
  `immediate(N)=index` and `immediate(N)=Index` remain unsupported.
- Preserve M206 destination suffix behavior.

## Required Positive Coverage

- A selected context with `v:=(v,sImm)` and parameters `(data, index)` lowers
  `immediate(1)=index` to the typed selected-signature-immediate value before
  backend translation, and backend translation consumes that lowered value.
- A selected context with `v:=(v,sImm)` and parameters `(data, arbitrary)`
  lowers and translates `immediate(1)=arbitrary`, proving the name is not
  hardcoded.
- A backend translation test constructs the lowered selected-signature
  immediate value directly and proves the backend consumes it without selected
  signature context.
- Corpus characterization proves the 18 observed
  `conversion/repr_change.tsl` `immediate(1)=index` occurrences are accepted
  under the matching selected `convert_up(data, index)` signature context.

## Required Negative Coverage

- `immediate(1)=index` with a selected signature such as `v:=(v,v)` remains
  unsupported.
- `immediate(1)=missing` remains unsupported even when another `sImm`
  parameter exists.
- `immediate(1)=Index` under `s:=v[idx]` remains unsupported in M208 because
  `Index` is not a primitive parameter binding.
- Existing M195 context-free unsupported diagnostics for raw symbol immediates
  remain unchanged.
- Backend translation of a raw `BackendIntrinsicModifierSymbolOperand("index")`
  remains unsupported; the backend must not perform signature-parameter lookup
  itself.

## Out Of Scope

- Generic/indexed-vector ownership for `Index`.
- Parsing or modeling `generic_params`.
- Treating `v[idx]` as a resolved parameter name.
- C++ non-type template parameter rendering.
- Rust const generic rendering.
- Intrinsic-name assembly.
- Backend-side resolution of signature parameter symbols.
- Argument-list rewriting or validating that the compose argument text at
  position `N` matches the symbol.
- Dependency closure.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m208_selected_signature_immediate_translation.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py tslgen/tests/test_m206_to_type_suffix_infix_translation.py tslgen/tests/test_m2065_signature_term_model.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- Lowering resolves symbol immediates through typed M206.5
  `SignatureParameterTerm` facts, not raw names.
- Backend translation consumes only the lowered selected-signature-immediate
  value and does not inspect selected signature context or raw symbol names.
- Arbitrary `sImm` parameter names work.
- Runtime parameters and unknown symbols remain unsupported.
- `Index` remains unsupported and is recorded as a follow-up requiring a
  generic/indexed-vector ownership model.
- The change does not render C++/Rust compile-time parameter syntax, assemble
  intrinsic names, parse broad TSIL, rewrite arguments, or repair source.
- M195, M206, and M206.5 behavior remains stable.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M208 result, and create the
next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Executor/review verdict.
2. What M208 changed.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
