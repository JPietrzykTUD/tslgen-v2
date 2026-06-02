# M221 Non-Intrinsic Body Token Substitution Parity Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M220 as accepted.

This is an implementation task with an evidence gate. Use the executor-review
loop:

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

M221 extends that body-token substitution idea only where the already accepted
pipeline has the same two ingredients:

```text
typed lowered handoff stream
+ explicit already-rendered backend values with request provenance
```

Do not invent raw-string backend rendering inside body substitution just to
make a family available.

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

Before implementing, identify the largest safe subset of non-intrinsic
body-token families that already have both:

- a typed lowered handoff stream with opaque text/token segments and request
  segments; and
- explicit already-rendered backend values carrying backend id, output text,
  typed request provenance, and source provenance for C++ and Rust.

Expected candidates are backend type query handoffs and backend value query
handoffs, because backend type spelling and backend value translation already
exist as typed backend translation boundaries. Source-operation handoffs are
not eligible unless accepted already-rendered source-operation values already
exist before M221 implementation begins.

If no non-intrinsic family satisfies the evidence gate, do not implement a
placeholder renderer. Stop, record the evidence, and create a return-to-
planner prompt.

## Goal

Add the smallest non-intrinsic body-token substitution parity slice for C++
and Rust:

```text
opaque/raw text segment
+ non-intrinsic request segment with already-rendered backend value
+ opaque/raw text segment
-> concatenated backend body text
```

Surrounding source text such as `return `, `;`, assignments, indexing, braces,
or operators remains raw text. M221 must not invent or parse statement syntax.

## Scope

Add focused implementation and tests, likely in small modules near the
existing backend body-token code. The implementation should:

- consume only accepted typed handoff streams and already-rendered backend
  values identified by the evidence gate;
- preserve opaque text segments exactly and in source order;
- substitute request segments only with matching already-rendered backend
  values by preserved typed request-object provenance, not raw text matching;
- support any number of ordered request segments in the stream;
- preserve rendered value provenance and deterministic substitution order for
  later primitive body rendering;
- return structured diagnostics for missing, extra, duplicate, backend-
  mismatched, and opaque non-renderable token segments;
- keep C++ and Rust in parity for every family implemented in M221;
- keep the shared shape small and justified by the concrete families selected
  by the evidence gate.

## Guardrails

- Do not add a broad registry, dispatcher, worklist, or all-token replacement
  framework.
- Do not reopen lowering or rescan raw TSIL.
- Do not parse `return`, `emit_return(...)`, assignments, array access, loops,
  braces, semicolons, operators, or surrounding Rust/C++ syntax.
- Do not parse, split, normalize, or repair request payloads.
- Do not invent source-operation backend rendering if typed rendered
  source-operation values do not already exist.
- Do not render Rust const generics, C++ non-type templates, primitive
  signatures, primitive dependency closure, whole primitive bodies, generated
  project files, or build verification.
- Do not put semantic decisions into templates.
- Do not make `frozen/` or `tslgenold` runtime dependencies.

## Expected Tests

Add focused tests for the selected non-intrinsic family/families:

- evidence-gate coverage documenting which families were eligible and which
  were intentionally excluded;
- C++ and Rust raw text preservation around rendered non-intrinsic islands;
- multiple request segments substituted in source order;
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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m221_non_intrinsic_body_token_substitution_parity.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: evidence gate is honored, shared shape is
   minimal, raw spans are preserved, and no broad token replacement framework
   or syntax parser was introduced.
2. Evidence reviewer: selected non-intrinsic family/families truly had typed
   handoff streams plus already-rendered backend values before substitution.
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
  or clarifies non-intrinsic body-token render values or policy;
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
