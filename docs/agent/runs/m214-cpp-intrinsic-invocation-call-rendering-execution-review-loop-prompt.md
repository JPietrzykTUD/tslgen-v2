# M214 C++ Intrinsic Invocation Call Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M213 as accepted.

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
Milestone 213: Backend Intrinsic Invocation Assembly
```

M213 added typed backend intrinsic invocation values over accepted M166/M182
handoff requests and M195-M210 translated modifier results. Those values
already contain the assembled intrinsic name, opaque argument payload text, and
typed immediate metadata.

The next useful step is not another intrinsic-compose planning slice. Prove
that the M213 data is useful by rendering one concrete backend call shape.

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
- `docs/redesign/tsil-surface-inventory.md`
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py`

## Goal

Implement the smallest C++ backend/output rendering boundary that consumes
already assembled M213 intrinsic invocation values and produces typed C++
intrinsic call text.

## Scope

Add a focused backend module, likely
`tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`, and focused unit tests,
likely `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`.

The implementation should:

- consume `BackendDirectIntrinsicInvocation` and
  `BackendComposedIntrinsicInvocation` values;
- support only backend `cpp` in M214;
- render C++ call text as `assembled_name(opaque_argument_payload)`;
- preserve empty argument payloads as `assembled_name()`;
- preserve the M213 typed immediate metadata on the render result for later
  wrapper/signature/template work, but do not rewrite argument text or render
  separate C++ non-type template syntax in this slice;
- preserve invocation/request/source provenance;
- return structured diagnostics for non-C++ invocation values or unsupported
  invocation shapes;
- expose a small public API if useful, without adding a registry, dispatcher,
  worklist, or new intrinsic-compose IR family.

## Out Of Scope

- New lowering or raw TSIL rescans.
- Parsing, splitting, normalizing, or repairing intrinsic arguments.
- Direct-intrinsic placeholder resolution.
- Rust rendering or Rust `core::arch::*` qualification.
- C++ non-type template signature rendering.
- Rust const generic rendering.
- Primitive dependency closure.
- Whole primitive body rendering.
- Whole generated project rendering, writing, or build verification.
- Template-side semantic decisions.
- Runtime dependency on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests for:

- direct C++ intrinsic invocation call rendering;
- composed C++ intrinsic invocation call rendering;
- empty argument payload rendering as `name()`;
- argument payloads containing nested TSIL-looking text remaining opaque;
- typed immediate metadata preserved on the rendered call result, with no
  additional call-text rewriting;
- non-C++ invocation values diagnosed as unsupported by this C++ renderer;
- public backend imports if the module exposes a new public API.

Do not add corpus-wide rendering, primitive body rendering, generated project
rendering, or compile tests in M214.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: C++ rendering consumes M213 typed values,
   no lowering reopen, no argument parsing, no template semantics.
2. Evidence reviewer: M213 invocation compatibility and whether the C++ call
   shape is a useful vertical step without broadening `intrin_compose`.
3. Test reviewer: coverage of direct/composed/empty/opaque/immediate/diagnostic
   behavior.
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
  if the accepted implementation adds new public C++ intrinsic call render
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
