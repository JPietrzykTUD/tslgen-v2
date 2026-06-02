# M221 Backend Type/Value Body Token Substitution Parity Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M220 as accepted.

This is an implementation task with a narrow evidence gate. Use the
executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if `Needs Revision`
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 220: Shared Intrinsic Body Token Substitution Parity
```

M220 added the minimal shared intrinsic body-token substitution contract and
Rust parity for already-rendered intrinsic calls. It deliberately stayed
intrinsic-only: raw text spans remained raw, request segments were matched by
typed request-object provenance, and no surrounding target-language syntax was
parsed.

M221 applies that same substitution boundary to the complete currently
eligible **backend type/value** subset, not to arbitrary remaining token
families. The only selected candidate families are:

```text
BackendTypeQueryHandoff + BackendTranslatedTypeSpelling
BackendValueQueryHandoff + BackendTranslatedValue
```

These families are selected because the accepted pipeline already has both:

```text
typed lowered handoff stream
+ explicit already-rendered backend value with request provenance
```

Do not invent raw-string backend rendering inside body substitution just to
make another family available.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `tslgen/src/tslgen/backends/body_token_contract.py`
- `tslgen/src/tslgen/backends/cpp/body_tokens.py`
- `tslgen/src/tslgen/backends/rust/body_tokens.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/value_translation.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m192_backend_type_spelling_translation.py`
- `tslgen/tests/test_m193_backend_value_translation.py`
- `tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py`

## Evidence Gate

Before implementing, verify that both selected backend type/value families
have the two accepted ingredients:

- `BackendTypeQueryHandoff` has opaque text/token segments and
  `BackendTypeQueryHandoffRequestSegment` values whose request is a
  `BackendTypeSpellingRequest`; `BackendTranslatedTypeSpelling` carries that
  request plus backend id, output spelling text, and source provenance.
- `BackendValueQueryHandoff` has opaque text/token segments and
  `BackendValueQueryHandoffRequestSegment` values whose request is a
  `BackendValueRequest`; `BackendTranslatedValue` carries that request plus
  backend id, output value text, and source provenance.

If either family lacks these ingredients, do not invent a placeholder
renderer. Implement only the eligible family/families, record the exclusion in
tests/docs, and create a follow-up or return-to-planner prompt if the missing
family blocks useful progress.

Source-operation handoffs, control directives, loops, primitive calls,
signatures, and other body-token families are not M221 candidates.

## Goal

Add backend type/value body-token substitution parity for C++ and Rust:

```text
opaque/raw text segment
+ backend type/value request segment with already-rendered backend value
+ opaque/raw text segment
-> concatenated backend body text
```

Surrounding source text such as `return `, `;`, assignments, indexing, braces,
or operators remains raw text. M221 must not invent or parse statement syntax.

## Scope

Add focused implementation and tests near the existing backend body-token
code. The implementation should:

- support `BackendTypeQueryHandoff` plus
  `BackendTranslatedTypeSpelling`;
- support `BackendValueQueryHandoff` plus `BackendTranslatedValue`;
- preserve opaque text segments exactly and in source order;
- substitute request segments only with matching already-rendered backend
  type/value values by preserved typed request-object provenance, not raw text
  matching;
- support any number of ordered request segments in the stream;
- preserve rendered value provenance and deterministic substitution order for
  later primitive body rendering;
- return structured diagnostics for missing, extra, duplicate, backend-
  mismatched, and opaque non-renderable token segments;
- keep C++ and Rust in parity for type and value substitution;
- keep the shared shape small and justified by these two concrete families.

## Guardrails

- Do not add a broad registry, dispatcher, worklist, or all-token replacement
  framework.
- Do not implement source-operation substitution or source-operation backend
  rendering in M221.
- Do not add control directive, loop, primitive-call, signature, intrinsic, or
  general body-token substitution in M221.
- Do not reopen lowering or rescan raw TSIL.
- Do not parse `return`, `emit_return(...)`, assignments, array access, loops,
  braces, semicolons, operators, or surrounding Rust/C++ syntax.
- Do not parse, split, normalize, or repair request payloads.
- Do not render Rust const generics, C++ non-type templates, primitive
  signatures, primitive dependency closure, whole primitive bodies, generated
  project files, or build verification.
- Do not put semantic decisions into templates.
- Do not make `frozen/` or `tslgenold` runtime dependencies.

## Expected Tests

Add focused tests for backend type/value substitution:

- evidence-gate coverage documenting that type and value are the selected
  eligible families and that source operations/control/loops/primitive calls
  are intentionally excluded;
- C++ and Rust raw text preservation around rendered type islands;
- C++ and Rust raw text preservation around rendered value islands;
- multiple type/value request segments substituted in source order;
- missing rendered value diagnostic for a request segment;
- extra rendered value diagnostic for a value whose request is not in the
  handoff stream;
- duplicate rendered value diagnostic for one request segment;
- backend-mismatched rendered value diagnostic;
- opaque non-renderable token segment diagnostic;
- deterministic ordered rendered-value provenance on the body result;
- public backend imports if new API is exposed.

Do not add corpus-wide rendering, generated project rendering, compile tests,
or primitive dependency closure in M221.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m221_backend_type_value_body_token_substitution_parity.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: type/value-only scope is honored, shared
   shape is minimal, raw spans are preserved, and no broad token replacement
   framework or syntax parser was introduced.
2. Evidence reviewer: backend type/value families truly had typed handoff
   streams plus already-rendered backend values before substitution, and
   excluded families were not pulled in.
3. Test reviewer: coverage of raw preservation, C++/Rust parity, diagnostics,
   provenance/order, and excluded families.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md`, `docs/redesign/domain-model.md`,
  or `docs/redesign/design-decisions.md` if the accepted implementation adds
  or clarifies backend type/value body-token render values or policy;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M222.

## Final Report

Report:

1. Evidence-gate result and implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
