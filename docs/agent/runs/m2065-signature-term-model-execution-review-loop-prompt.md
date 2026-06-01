# M206.5 Signature Term Model Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M206 as accepted.

This is an implementation milestone. Use the executor-review loop: one
write-capable executor, then read-only reviewer/auditor subagents, then one
focused revision executor only if the consolidated verdict is `Needs
Revision`. The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M206: To-Type Suffix Infix Marker Translation
```

Selected milestone:

```text
Milestone 206.5: Complete Observed Signature Term Model
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
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/syntax/ast.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m107_tiny_pipeline.py`
- `tslgen/tests/test_m1685_return_type_bindings.py`
- `tslgen/tests/test_m206_to_type_suffix_infix_translation.py`
- `tsldata/primitives/**/*.tsl`

## Goal

Introduce a typed signature model for all primitive signature forms currently
observed in `tsldata/primitives/**/*.tsl`. The immediate motivation is that
later lowering must know that a parameter is compile-time immediate because
its signature term is `sImm`, not because its source-owned name happens to be
`index` or `Index`.

## Executor Scope

- Add typed signature domain values using dataclasses and enums. A reasonable
  shape is:

  ```python
  class SignatureTermKind(Enum): ...

  @dataclass(frozen=True, slots=True)
  class SignatureTerm:
      kind: SignatureTermKind
      source_text: str

  @dataclass(frozen=True, slots=True)
  class PrimitiveSignature:
      result: SignatureTerm
      parameters: tuple[SignatureTerm, ...]
      source_text: str
  ```

- Represent all observed term spellings explicitly:
  `v`, `m`, `s`, `sImm`, `ptr`, `vidx`, `void`, `o`, `sequence`, `s[]`,
  `v[idx]`, `ptr+`, and `s...`.
- Preserve normalized signature text for deterministic identity, sorting, and
  diagnostics. If a temporary compatibility field is needed, name it clearly
  as text such as `signature_text`; downstream semantic code should consume
  the typed signature model.
- Expose parameter-to-signature-term mapping by position through the domain
  catalog and selected lowering context. For example:

  ```text
  prim<v:=(v,sImm)> convert_up(data, index)
  ```

  must make `data -> v` and `index -> sImm` available as typed facts.

- Update the parser/catalog boundary so accepted primitive headers construct
  typed signatures. Do not broaden implementation-body parsing as part of this
  milestone.
- Add focused tests, preferably in
  `tslgen/tests/test_m2065_signature_term_model.py`.
- Add corpus evidence coverage that scans all `prim<...>` signatures in
  `tsldata/primitives/**/*.tsl` and proves the typed signature parser accepts
  exactly the observed set.
- Preserve existing behavior for the tiny clean signatures and previous M206
  intrinsic modifier tests.

## Required Observed Signature Forms

The typed signature parser must accept the currently observed corpus forms:

```text
m:=()
m:=(m,m)
m:=(m,s)
m:=(m,v)
m:=(m,v,v)
m:=(m,v,v,v)
m:=(v,v)
m:=(v,v,v)
m:=m
m:=ptr
m:=s
m:=v
o:=(o,v,s)
ptr:=(s)
ptr:=(s,s)
s:=(m,v)
s:=(s,s)
s:=(s,s,s)
s:=(v,s)
s:=m
s:=ptr
s:=s
s:=v
s:=v[idx]
s[]:=v
v:=()
v:=(m,ptr)
v:=(m,ptr,v)
v:=(m,ptr,vidx,v,sImm)
v:=(m,v)
v:=(m,v,s)
v:=(m,v,sImm)
v:=(m,v,v)
v:=(m,v,v,v)
v:=(ptr,vidx,sImm)
v:=(s,s)
v:=(v,s)
v:=(v,sImm)
v:=(v,v)
v:=(v,v,sImm)
v:=m
v:=ptr+
v:=ptr
v:=s...
v:=s
v:=s[]
v:=sequence
v:=v
void:=(m,ptr,v)
void:=(m,ptr,vidx,v,sImm)
void:=(ptr)
void:=(ptr,m)
void:=(ptr,ptr,s,s)
void:=(ptr,s)
void:=(ptr,v)
void:=(ptr,vidx,v,sImm)
```

## Required Negative Coverage

- Unknown signature terms produce deterministic diagnostics.
- Parameter count mismatch between a primitive header and its typed signature
  produces a deterministic diagnostic.
- `sImm` is represented as a signature term kind, not as a raw parameter name
  convention.
- Parameters named `index`, `Index`, or any arbitrary name are not considered
  immediate unless their corresponding signature term is `sImm`.
- Existing M206 `infix=to_type_suffix` lowering/translation behavior remains
  unchanged.

## Out Of Scope

- Lowering `immediate(N)=index` or `immediate(N)=Index`.
- Backend translation of compile-time parameter operands.
- C++ non-type template parameter syntax.
- Rust const generic syntax.
- Signature-to-template resolution beyond existing behavior.
- Parsing every complex `.tsl` implementation body.
- Intrinsic-name assembly.
- Rendering, generated output, artifact writing, or build verification.
- Dependency closure.
- Source repair.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m2065_signature_term_model.py
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m107_tiny_pipeline.py tslgen/tests/test_m1685_return_type_bindings.py tslgen/tests/test_m206_to_type_suffix_infix_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Review Requirements

Use `docs/agent/review-checklist.md`.

Reviewers must verify:

- Signatures are represented with typed dataclasses/enums, not dictionaries or
  raw strings as the semantic model.
- All observed corpus signature forms and terms are covered by tests.
- Parameter-to-term mapping is available in the selected lowering context.
- `sImm` immediate-ness comes from typed signature terms, not parameter names.
- Existing parser/catalog/lowering behavior for accepted tiny fixtures remains
  stable.
- M206 intrinsic modifier behavior remains stable.
- The milestone does not implement immediate modifier lowering, backend
  compile-time parameter rendering, broad body parsing, rendering, or source
  repair.

## Final State Update

Before finishing an accepted run, update
`docs/agent/current-redesign-state.md`, update
`docs/redesign/implementation-roadmap.md` with the M206.5 result, and create
the next concrete prompt under `docs/agent/runs/` according to
`docs/agent/next-run-prompt-protocol.md`, unless review records an explicit
stop condition.

## Final Report

Report:

1. Executor/review verdict.
2. What M206.5 changed.
3. Files changed.
4. Validation commands with exact results.
5. Next active prompt path or stop condition.
