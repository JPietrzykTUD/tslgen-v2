# M195 Literal Intrinsic Modifier Translation Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M194 as accepted.

This is an implementation milestone. Use the orchestrated executor-review loop
defined in `PLANS.md` and `AGENTS.md`: one write-capable executor, then
read-only reviewer/auditor subagents, then focused revision only if needed.
The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
M194: Intrinsic Modifier Translation Boundary Planning
```

Selected milestone:

```text
Milestone 195: Literal Intrinsic Modifier Translation For Compose Handoff
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
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/lowering/backend_intrinsic_handoff.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/value_translation.py`
- `tslgen/tests/test_m182_intrinsic_modifier_handoff.py`
- `tslgen/tests/test_m193_backend_value_translation.py`
- `tsldata/**/*.tsl` as source-corpus evidence only

## Goal

Add a small backend translation boundary that consumes accepted M182
`BackendIntrinsicComposeHandoffRequest` modifier fields and translates only
final literal modifier facts into typed backend intrinsic modifier results.

This milestone makes literal compose modifiers structured for a later
intrinsic-composition stage without assembling intrinsic names, parsing direct
intrinsics, parsing intrinsic arguments, or guessing backend suffix/prefix
semantics.

## Executor Scope

- Add a focused backend translation module, expected near
  `tslgen/src/tslgen/backends/`, for literal intrinsic compose modifiers.
- Consume typed M182 values:
  - `BackendIntrinsicComposeHandoffRequest`;
  - `BackendDirectIntrinsicHandoffRequest` only for an unsupported diagnostic
    if a mixed batch helper is introduced;
  - `BackendIntrinsicModifierField`;
  - `BackendIntrinsicModifierSymbolOperand`;
  - `BackendIntrinsicModifierStringOperand`;
  - `BackendIntrinsicModifierIntegerOperand`;
  - `BackendIntrinsicModifierBackendValueOperand` only for unsupported
    diagnostics.
- Define typed translation result values. The result must be per modifier, not
  a composed intrinsic name. A simple expected shape is:

```python
BackendTranslatedIntrinsicModifier(
    backend=BackendId(...),
    field=BackendIntrinsicModifierField(...),
    name=BackendIntrinsicModifierName(...),
    value=BackendIntrinsicLiteralFragment(...)
        | BackendIntrinsicInfixSeparator(...)
        | BackendIntrinsicImmediateLiteral(...),
    source=SourceLocation(...),
)
```

- Translate only these safe final forms:
  - `suffix` with direct symbol or quoted-string operands that contain no
    unresolved wildcard marker such as `?`, for example `suffix=si128`,
    `suffix=epi32`, `suffix="epi64"`, or `suffix="epi64x"`;
  - `post` with direct symbol or quoted-string operands, such as `post=x`,
    `post=z`, `post=m`, or `post=mask`;
  - `infix` only when the direct symbol or quoted-string operand is a final
    literal fragment; the observed `infix=to_type_suffix` is explicitly
    unsupported in this milestone;
  - `infix_sep` with quoted-string operands, such as `infix_sep=""`;
  - `immediate(N)` with integer operands, such as `immediate(1)=4`.
- Preserve source/request/field provenance and modifier order.
- Export the public translator and typed results through
  `tslgen.backends.__init__` if the existing package pattern calls for it.
- Add focused tests in
  `tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py`.
- Add a corpus characterization test over `tsldata/primitives/**/*.tsl` that
  discovers and lowers every observed `intrin_compose<...>` occurrence through
  the accepted M182 lowering path, then feeds the resulting compose modifier
  fields into the M195 translator.

## Required Diagnostics

Add stable error diagnostics for unsupported or malformed translation inputs.
The exact names may be refined, but tests must assert codes and source
locations. Required diagnostic coverage:

- unsupported modifier field, including `prefix`;
- unsupported operand kind for an otherwise supported field;
- unsupported backend-value modifier operand, including:
  - `suffix=value<backend>(intrin::suffix)`;
  - `suffix=value<backend>(intrin::suffix(type<generation>(...)))`;
  - `suffix=value<backend>(intrin::suffix("stream"))`;
  - `suffix=value<backend>(intrin::suffix(ToBase))`;
  - `prefix=value<backend>(intrin::prefix)`;
- unsupported unsafe literal fragments, including wildcard-looking direct
  suffix symbols such as `suffix=si?`;
- unsupported semantic infix symbol such as `infix=to_type_suffix`;
- unsupported immediate operands that are not integer literals, such as
  `immediate(1)=Index` or `immediate(1)=index`;
- missing immediate index if an invalid object is constructed in a focused
  negative test;
- unsupported direct `BackendDirectIntrinsicHandoffRequest` if a handoff/batch
  helper accepts mixed intrinsic handoff segments.

Diagnostics must not repair source, infer hidden suffix rules, or silently
pass unsupported backend-value operands through as text.

## Required Tests

Positive tests:

- translate direct literal suffix symbol and string operands;
- translate literal post modifiers including `x`, `z`, `m`, and `mask`;
- translate `infix_sep=""`;
- translate integer immediate modifiers while preserving the immediate argument
  index;
- preserve modifier order and source/field provenance.

Negative tests:

- diagnose `prefix=value<backend>(intrin::prefix)`;
- diagnose no-argument suffix backend-value operands;
- diagnose type-derived suffix backend-value operands;
- diagnose string-argument suffix backend-value operands such as
  `intrin::suffix("stream")`;
- diagnose symbol-argument suffix backend-value operands such as `ToBase`;
- diagnose wildcard-looking direct suffix symbols such as `suffix=si?`;
- diagnose symbol immediate operands such as `Index` or `index`;
- diagnose `infix=to_type_suffix` as a future typed rule, not a literal
  fragment;
- prove direct intrinsic names and argument payloads are not parsed or
  translated by this boundary.

Boundary tests:

- no intrinsic name assembly occurs;
- no backend metadata catalog is needed or read;
- no lowering code changes are required unless a true blocker is documented
  and the task returns to planning.

Corpus characterization test:

- scan `tsldata/primitives/**/*.tsl`;
- discover and lower every balanced `intrin_compose<...>` occurrence using
  the accepted lowering discovery/handoff path, not a separate ad-hoc parser;
- feed each resulting `BackendIntrinsicComposeHandoffRequest` modifier field
  into the M195 translator;
- assert every observed modifier is classified into exactly one of:
  - translated final literal fragment;
  - expected unsupported backend-value suffix or prefix request;
  - expected unsupported semantic infix such as `to_type_suffix`;
  - expected unsupported symbol immediate such as `index` or `Index`;
  - expected unsupported wildcard-looking literal such as `si?`;
  - expected unsupported direct intrinsic handoff if encountered by a mixed
    helper;
- assert there are no unknown or unclassified diagnostics.

This test must not require every observed `intrin_compose` occurrence to
translate successfully. It is a soundness guard for the selected boundary:
all corpus forms are either translated by M195 or intentionally diagnosed in a
named unsupported family.

## Out Of Scope

- Rendering.
- Primitive body rendering.
- Direct `intrin<...>(...)` name parsing.
- Intrinsic argument payload parsing.
- Intrinsic base-token translation.
- Broad intrinsic-name assembly.
- No-argument suffix resolution.
- Type-derived suffix resolution.
- String-argument suffix resolution such as `intrin::suffix("stream")`.
- Symbol-argument suffix resolution such as `ToBase`.
- Prefix resolution.
- `infix=to_type_suffix` semantics.
- Symbol immediate resolution.
- Backend metadata lookup.
- M192/M193 translation changes.
- Arbitrary placeholder formatting.
- Source repair or semantic validation beyond the selected boundary.
- Dependency closure.
- Machine profile or generated-project changes.
- Lowering changes unless implementation proves the accepted M182 handoff is
  insufficient.
- Runtime dependency on `frozen/` or `tslgenold`.

## Required Review Subagents

After the executor finishes and validation has been run, use read-only
subagents:

1. Architecture/boundary reviewer: verify typed backend translation boundaries,
   no renderer/template semantics, no direct intrinsic parsing, no suffix/prefix
   inference, no symbol-immediate resolution, and no lowering drift.
2. Evidence auditor: compare accepted/unsupported cases against representative
   `tsldata/**/*.tsl` modifier families from M194.
3. Validation auditor: inspect test coverage and validation output.
4. Documentation auditor: verify roadmap/state/next prompt updates accurately
   record the result and follow-ups.

If reviewers return `Needs Revision`, use one focused write-capable revision
executor for the named issues and then run focused re-review. If reviewers
return `Return To Planner` or `Reject`, stop implementation and create the
appropriate planner/rollback prompt.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py
find tslgen -type d -name __pycache__ -print
```

Remove validation-created `__pycache__` directories before final validation
reporting if any appear.

## Completion Rules

Before finishing an accepted M195 run:

- update `docs/redesign/implementation-roadmap.md` with the M195 result and
  selected next milestone;
- update redesign docs if implementation clarifies behavior, decisions, or
  open questions;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- report exact validation results.

## Stop Rule

Do not start Milestone 196. Do not implement suffix/prefix semantic rules,
symbol immediate resolution, or intrinsic-name assembly in this milestone.

## Final Report

Report:

1. M195 review verdict.
2. Implemented files and docs changed.
3. Boundary decisions preserved.
4. Validation commands with exact results.
5. Review/audit verdicts.
6. Next active prompt path.
