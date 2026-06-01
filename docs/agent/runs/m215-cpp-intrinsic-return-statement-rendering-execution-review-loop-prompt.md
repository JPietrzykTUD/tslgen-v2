# M215 C++ Intrinsic Return Statement Rendering Execution Review Loop Prompt

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

The next useful step is to prove that the rendered call value can become a
small body-level C++ fragment without adding another intrinsic-compose layer.

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
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`

## Goal

Implement the smallest C++ body-fragment rendering boundary that consumes an
M214 `CppRenderedIntrinsicCall` and produces typed C++ return-statement text.

## Scope

Add a focused backend module, likely
`tslgen/src/tslgen/backends/cpp/body_fragments.py` or
`tslgen/src/tslgen/backends/cpp/return_statements.py`, and focused unit tests,
likely `tslgen/tests/test_m215_cpp_intrinsic_return_statement_rendering.py`.

The implementation should:

- consume `CppRenderedIntrinsicCall` values;
- render exactly one C++ statement shape: `return {call_text};`;
- preserve the input call value, source provenance, and typed immediate
  metadata on the render result for later wrapper/signature/template work;
- return structured diagnostics for unsupported input shapes if the public
  API accepts a defensive object-shaped input;
- expose a small public API if useful;
- keep the module presentation-level and boring.

## Out Of Scope

- New lowering or raw TSIL rescans.
- Parsing `emit_return(...)` source text.
- Primitive body tokenization or whole primitive body rendering.
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

- rendering a direct C++ intrinsic call as `return call;`;
- rendering a composed C++ intrinsic call as `return call;`;
- preserving source provenance and typed immediate metadata;
- preserving opaque call text without argument parsing or rewriting;
- unsupported input-shape diagnostics if the public API accepts defensive
  object-shaped input;
- public backend imports if the module exposes a new public API.

Do not add corpus-wide rendering, `emit_return(...)` discovery, generated
project rendering, or compile tests in M215.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m215_cpp_intrinsic_return_statement_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: M215 consumes M214 typed call values, stays
   presentation-level, and does not reopen lowering or whole-body rendering.
2. Evidence reviewer: the return-statement fragment is a useful vertical step
   toward C++ primitive rendering without broadening `intrin_compose`.
3. Test reviewer: coverage of direct/composed/provenance/immediate/opaque text
   and diagnostics.
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
  if the accepted implementation adds new public C++ body-fragment render
  values;
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
