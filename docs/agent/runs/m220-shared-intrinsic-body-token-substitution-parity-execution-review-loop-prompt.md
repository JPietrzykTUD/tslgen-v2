# M220 Shared Intrinsic Body Token Substitution Parity Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M219 as accepted.

This is an implementation task. Use the executor-review loop:

```text
single write-capable executor
-> read-only reviewer/auditor subagents
-> focused revision executor if Needs Revision
-> focused re-review
-> next-run prompt generation
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 219: Rust Intrinsic Invocation Call Rendering Parity
```

M214 added C++ intrinsic-call rendering over accepted M213 invocation values.
M215 added C++ body-token substitution over accepted
`BackendIntrinsicHandoff` streams and already-rendered C++ intrinsic calls.
M219 added Rust intrinsic-call rendering over the same M213 invocation values,
using explicit typed `RustArchitectureModule` qualification.

M220 brings the body-token substitution boundary to C++/Rust parity. It may
introduce a shared replacement/provenance contract only because there are now
two concrete consumers: the accepted C++ M215 body-token substitution path and
the Rust body-token substitution path added in this milestone.

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
- `tslgen/src/tslgen/lowering/backend_intrinsics.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/src/tslgen/backends/cpp/body_tokens.py`
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/rust/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/cpp/__init__.py`
- `tslgen/src/tslgen/backends/rust/__init__.py`
- `tslgen/tests/test_m215_cpp_body_token_substitution_rendering.py`
- `tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py`

## Goal

Introduce the smallest shared intrinsic body-token replacement/provenance
contract needed by C++ and Rust, then add Rust body-token substitution parity:

```text
opaque/raw text segment
+ backend-intrinsic request segment with rendered Rust call
+ opaque/raw text segment
-> concatenated Rust body text
```

As in M215, surrounding source text such as `return `, `;`, assignments,
indexing, braces, or operators remains raw text. M220 must not invent or parse
statement syntax.

## Scope

Add focused shared/Rust implementation and tests, likely:

```text
tslgen/src/tslgen/backends/body_token_contract.py
tslgen/src/tslgen/backends/rust/body_tokens.py
tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py
```

The implementation should:

- define the minimal shared typed contract needed for body-token substitution
  to obtain:
  - backend id;
  - rendered call text;
  - original handoff request object/provenance;
  - typed immediate metadata;
  - source provenance;
- adapt or refactor the existing C++ M215 path only as much as needed to use
  that shared contract while preserving its public API and behavior;
- add Rust body-token substitution that consumes `BackendIntrinsicHandoff`
  streams plus explicit `RustRenderedIntrinsicCall` values;
- preserve `BackendIntrinsicOpaqueTextSegment.text` exactly and in source
  order;
- substitute each `BackendIntrinsicHandoffRequestSegment` with the matching
  rendered Rust intrinsic call text;
- match rendered calls to request segments by preserved typed request object/
  provenance, not by rescanning source text or comparing raw spellings;
- support any number of ordered intrinsic request segments in the stream;
- preserve rendered call provenance and typed immediate metadata in the body
  render result for later wrapper/signature/template work;
- return structured diagnostics for missing, extra, duplicate, or
  backend-mismatched rendered calls;
- diagnose opaque non-renderable token segments rather than guessing or
  stringifying them;
- expose a small public Rust backend API if useful.

## Guardrails

- Do not add a broad registry, dispatcher, worklist, or token replacement
  framework beyond the two accepted consumers named above.
- Do not add non-intrinsic type/value/source-operation token substitution.
- Do not reopen lowering or rescan raw TSIL.
- Do not parse `return`, `emit_return(...)`, assignments, array access, loops,
  braces, semicolons, operators, or surrounding Rust/C++ syntax.
- Do not parse, split, normalize, or repair intrinsic arguments.
- Do not assemble intrinsic names, translate modifiers, resolve direct-name
  placeholders, infer Rust architecture modules, render Rust const generics,
  or render C++ non-type templates.
- Do not perform primitive dependency closure, whole primitive body rendering,
  generated project rendering/writing/build verification, or template-side
  semantic decisions.
- Do not make `frozen/` or `tslgenold` runtime dependencies.

## Expected Tests

Add focused tests for:

- existing M215 C++ tests still passing after the shared contract refactor;
- Rust `Raw("return ") + rendered direct intrinsic + Raw(";")` rendering to
  `return core::arch::...::call(...);` without a return-statement renderer;
- assignment/indexing-looking raw text around a rendered composed Rust
  intrinsic, proving surrounding syntax stays raw;
- multiple Rust intrinsic request segments substituted in source order;
- empty intrinsic argument payload still coming from M219 as qualified
  `name()`;
- opaque nested TSIL-looking argument payload preserved through substitution;
- source provenance and typed immediate metadata preserved on the Rust body
  render result;
- missing rendered Rust call diagnostic for a request segment;
- extra rendered Rust call diagnostic for a call whose request is not in the
  handoff stream;
- duplicate rendered Rust call diagnostic for one request segment;
- backend-mismatched rendered Rust/C++ call diagnostic as applicable;
- opaque non-renderable token segment diagnostic;
- public backend imports if new API is exposed.

Do not add corpus-wide rendering, `emit_return(...)` discovery, generated
project rendering, compile tests, or non-intrinsic token substitution in M220.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m215_cpp_body_token_substitution_rendering.py tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: shared contract is minimal, has exactly the
   two named consumers, preserves raw spans, substitutes only rendered
   intrinsic tokens, and does not invent statement syntax.
2. Evidence reviewer: M215 C++ behavior is preserved and M219 Rust rendered
   calls now have the matching substitution boundary needed before primitive
   body rendering.
3. Test reviewer: coverage of C++ preservation, Rust raw preservation,
   direct/composed/multiple/empty/opaque/immediate/provenance behavior, and
   diagnostics.
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
  or clarifies shared/Rust body-token render values or policy;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M221.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
