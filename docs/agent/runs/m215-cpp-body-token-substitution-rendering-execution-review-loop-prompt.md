# M215 C++ Body Token Substitution Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M214 as accepted.

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
Milestone 214: C++ Intrinsic Invocation Call Rendering
```

M214 added a focused C++ backend/output renderer that consumes already
assembled M213 intrinsic invocation values and produces typed C++ call text.
The call renderer preserves opaque argument payload text and typed immediate
metadata, and it deliberately does not reopen lowering or parse intrinsic
arguments.

The accepted implementation-body model is a source-owned token stream: raw
text spans plus lowerable/renderable token islands. The next useful step is
not a special return-statement renderer. It is the smallest backend rendering
boundary that preserves raw body text and substitutes an already-rendered C++
intrinsic call for the matching lowerable backend-intrinsic island.

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
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`

## Goal

Implement the smallest C++ body-token substitution renderer for backend
intrinsic islands:

```text
opaque/raw text segment
+ backend-intrinsic request segment with rendered C++ call
+ opaque/raw text segment
-> concatenated C++ body text
```

Example fixture shape:

```text
Raw("return ")
+ rendered intrin<_mm_add_epi32>(left, right)
+ Raw(";")
-> "return _mm_add_epi32(left, right);"
```

The `return ` and `;` text are raw source text. M215 must not invent or parse
them.

## Scope

Add a focused C++ backend module, likely
`tslgen/src/tslgen/backends/cpp/body_tokens.py`, and focused unit tests,
likely `tslgen/tests/test_m215_cpp_body_token_substitution_rendering.py`.

The implementation should:

- consume an accepted `BackendIntrinsicHandoff` segment stream;
- consume explicit `CppRenderedIntrinsicCall` values produced from request
  segments in that handoff;
- preserve `BackendIntrinsicOpaqueTextSegment.text` exactly and in order;
- substitute each `BackendIntrinsicHandoffRequestSegment` with the matching
  rendered C++ intrinsic call text;
- match rendered calls to request segments by the already-preserved typed
  request object/provenance, not by rescanning source text;
- support any number of ordered intrinsic request segments in the stream;
- preserve rendered call provenance and typed immediate metadata in the body
  render result for later wrapper/signature/template work;
- return structured diagnostics for missing, extra, duplicate, or
  backend-mismatched rendered calls;
- diagnose opaque non-renderable token segments rather than guessing or
  stringifying them;
- expose a small public API if useful.

## Out Of Scope

- New lowering or raw TSIL rescans.
- Parsing `return`, `emit_return(...)`, assignments, array access, loops,
  braces, semicolons, operators, or surrounding C++ syntax.
- A special return-statement renderer or assignment renderer.
- Primitive body tokenization beyond consuming the already accepted intrinsic
  handoff segment stream.
- Parsing, splitting, normalizing, or repairing intrinsic arguments.
- Intrinsic-name assembly, direct placeholder resolution, or modifier
  translation.
- Rust rendering or Rust `core::arch::*` qualification.
- C++ non-type template signature rendering.
- Rust const generic rendering.
- Primitive dependency closure.
- Whole generated project rendering, writing, or build verification.
- Template-side semantic decisions.
- Runtime dependency on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests for:

- `Raw("return ") + rendered direct intrinsic + Raw(";")` rendering to
  `return call;` without a return-statement renderer;
- assignment/indexing-looking raw text around a rendered composed intrinsic,
  proving surrounding syntax stays raw;
- multiple intrinsic request segments substituted in source order;
- empty intrinsic argument payload still coming from M214 as `name()`;
- opaque nested TSIL-looking argument payload preserved through substitution;
- source provenance and typed immediate metadata preserved on the body render
  result;
- missing rendered call diagnostic for a request segment;
- extra rendered call diagnostic for a call whose request is not in the
  handoff stream;
- duplicate rendered call diagnostic for one request segment;
- opaque non-renderable token segment diagnostic;
- public backend imports if the module exposes a new public API.

Do not add corpus-wide rendering, `emit_return(...)` discovery, return
statement rendering, generated project rendering, or compile tests in M215.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m215_cpp_body_token_substitution_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: M215 consumes accepted segment/rendered-call
   values, preserves raw spans, substitutes only rendered intrinsic tokens, and
   does not invent statement syntax.
2. Evidence reviewer: the token-substitution renderer is a useful vertical
   step toward C++ primitive body rendering without broadening
   `intrin_compose` or parsing surrounding syntax.
3. Test reviewer: coverage of raw preservation, direct/composed substitution,
   multiple tokens, provenance/immediates, and diagnostics.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` and `docs/redesign/domain-model.md`
  if the accepted implementation adds new public C++ body-token render values;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the next milestone.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
