# M219 Rust Intrinsic Invocation Call Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M218 as accepted.

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
Milestone 218: Typed Primitive Render Context
```

M213 added typed backend intrinsic invocation values. M214 renders those
assembled values into C++ intrinsic call text. M215 substitutes already
rendered C++ intrinsic calls into C++ body-token streams. M216-M218 then moved
primitive templates and typed primitive render contexts to the front so C++
and Rust source structure does not accumulate as Python strings.

M219 restores Rust parity for the M214 call-rendering boundary. It must not
start Rust body-token substitution or whole primitive rendering.

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
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/cpp/__init__.py`
- `tslgen/src/tslgen/backends/rust/__init__.py`
- `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`

## Goal

Implement the smallest Rust backend/output rendering boundary that consumes
already assembled M213 intrinsic invocation values and produces typed Rust
intrinsic call text with explicit `core::arch::*` qualification.

## Scope

Add a focused backend module and tests, likely:

```text
tslgen/src/tslgen/backends/rust/intrinsic_calls.py
tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py
```

The implementation should:

- consume `BackendDirectIntrinsicInvocation` and
  `BackendComposedIntrinsicInvocation` values;
- support only backend `rust` in M219;
- require an explicit typed Rust architecture-module render context/value,
  such as `x86_64` or `aarch64`;
- render Rust call text as
  `core::arch::{module}::{assembled_name}(opaque_argument_payload)`;
- preserve empty argument payloads as
  `core::arch::{module}::{assembled_name}()`;
- preserve opaque argument payload text byte-for-byte;
- preserve M213 typed immediate metadata on the render result for later
  wrapper/signature/template work, but do not render Rust const-generic syntax
  in this slice;
- preserve invocation/request/source provenance;
- return structured diagnostics for non-Rust invocation values, unsupported
  invocation shapes, or invalid/missing architecture-module values;
- expose a small public Rust backend API if useful, without adding a registry,
  dispatcher, worklist, or new intrinsic-compose IR family.

The architecture module must be an already-decided typed render input. Do not
infer it from raw intrinsic names such as `_mm256_add_epi32`, `vaddq_u32`, or
`svadd_s32_x`. ADR-056 requires explicit Rust architecture paths and says the
renderer/backend call-translation layer owns module qualification from typed
backend/profile/extension facts.

## Out Of Scope

- New lowering or raw TSIL rescans.
- Parsing, splitting, normalizing, or repairing intrinsic arguments.
- Inferring architecture modules from intrinsic name text.
- Inventing ARM/NEON/SVE `intrin::prefix` mappings.
- Direct-intrinsic placeholder resolution.
- Rust const generic rendering.
- C++ non-type template signature rendering.
- Primitive dependency closure.
- Body-token substitution.
- Whole primitive body rendering.
- Whole generated project rendering, writing, or build verification.
- Template-side semantic decisions.
- Runtime dependency on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests for:

- direct Rust intrinsic invocation call rendering with an `x86_64` module;
- direct Rust intrinsic invocation call rendering with an `aarch64` module;
- composed Rust intrinsic invocation call rendering;
- empty argument payload rendering as the qualified `name()`;
- argument payloads containing nested TSIL-looking text remaining opaque;
- typed immediate metadata preserved on the rendered call result, with no
  const-generic or argument rewriting;
- non-Rust invocation values diagnosed as unsupported by this Rust renderer;
- unsupported invocation shapes diagnosed;
- invalid or missing architecture-module values diagnosed;
- public Rust backend imports if the module exposes a new public API.

Do not add corpus-wide rendering, primitive body rendering, generated project
rendering, compile tests, or Rust body-token substitution in M219.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: Rust rendering consumes M213 typed values
   and explicit typed architecture-module context, no lowering reopen, no
   argument parsing, no raw-name architecture inference, and no template
   semantics.
2. Evidence reviewer: M214 parity, ADR-056 explicit path policy, and whether
   the Rust call shape is a useful vertical step before Rust body-token
   substitution.
3. Test reviewer: coverage of direct/composed/empty/opaque/immediate/
   diagnostic behavior and public imports.
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
  or clarifies Rust intrinsic call render values or policy;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M220.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
