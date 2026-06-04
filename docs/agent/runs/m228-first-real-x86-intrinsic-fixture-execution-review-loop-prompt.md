# M228 First Real X86 Intrinsic Fixture Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M225 and M227 as accepted, M226 as stopped by preflight, and
M226.5 as accepted planning.

This is an implementation task. Use the executor-review loop:

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
Milestone 225: Generated Profile Build Flags
Milestone 226.5: Signature-Shape Template Render-Model Cleanup Planning
Milestone 227: V/V Function-Shape Template Render Boundary
```

M227 carried exact `v:=(v,v)` signature-shape provenance through lowering and
renders C++/Rust function definitions through supplementary shape templates.
The next useful slice is one real observed x86 intrinsic fixture. The focus is
lowering/source support for that fixture, consuming the M227 render boundary
instead of changing it again.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/domain-model.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/flaws-to-fix.md`
- `docs/agent/runs/m226-first-real-x86-intrinsic-fixture-execution-review-loop-prompt.md`
- `docs/agent/runs/m227-vv-function-shape-template-render-boundary-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tslgen/src/tslgen/syntax/parser.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/lowering/lowerer.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/rendering/primitive_function_shapes.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/backends/*intrinsic*`
- `tslgen/src/tslgen/backends/*body_tokens*`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`
- `tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py`

You may inspect `new_chat_test` only as negative evidence. Do not copy it
wholesale.

## Goal

Implement the smallest real observed x86 non-scalar intrinsic fixture for both
C++ and Rust.

The selected fixture must be an exact `.tsl` source form, preferably
`tsldata/primitives/arithmetic/fundamental.tsl` `add` with signature
`v:=(v,v)` and an `avx2` implementation body. The implementation body should
lower to raw source spans plus typed lowerable token values, and backend
rendering should consume those typed values. The M227 function-shape templates
must render the function definition.

## Preflight Step

Before editing implementation code, select one exact observed x86 fixture and
record why it is safe. Prefer a fixture with:

- signature `v:=(v,v)`;
- profile/extension `avx2`;
- no dependency closure beyond the selected primitive;
- no source-data flaw recorded in `docs/redesign/flaws-to-fix.md`;
- an implementation body that can be lowered by one narrow exact source shape;
- both C++ and Rust can render an actual intrinsic call from accepted typed
  backend facts plus one focused exact lowering addition if needed.

If no such fixture exists without broad TSIL parsing, source repair, dependency
closure, or renderer-side semantic inference, stop and create a planner prompt
instead of implementing.

## Scope

Add focused implementation and tests, likely touching:

```text
tslgen/src/tslgen/syntax/parser.py
tslgen/src/tslgen/pipeline/catalog_builder.py
tslgen/src/tslgen/lowering/lowerer.py
tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py
tslgen/tests/test_m228_first_real_x86_intrinsic_fixture.py
```

Use existing backend intrinsic invocation/body-token rendering boundaries where
possible. If one exact lowering/body-token adapter is missing for the selected
fixture, add only that exact adapter and tests.

The implementation should:

- preserve M224/M225 scalar behavior;
- use M227 exact `v:=(v,v)` function-shape templates;
- use M225 `avx2` target-feature build flags;
- use M227 selected-profile replacement policy for generated `avx2` profile
  artifacts;
- produce C++ and Rust generated profile artifacts containing a real rendered
  intrinsic call;
- prevent raw accepted lowerable token text such as `intrin_compose<...>` or
  `value<backend>(...)` from leaking into generated bodies;
- compile/test generated `scalar,avx2` C++ and Rust projects.

## Guardrails

- Do not implement broad TSIL parsing.
- Do not broaden to all `intrin_compose`, `intrin`, `call`, `if`, `loop`,
  `mem`, `io`, or `cast` shapes.
- Do not parse target-language expressions or infer surrounding syntax in
  renderers/templates.
- Do not add broad signature/template framework behavior.
- Do not add new whole C++/Rust function/header/module source strings in
  Python.
- Do not move semantic decisions into templates.
- Do not add dependency closure, all-profile generation, ARM/NEON/SVE/qemu,
  host autodetection, or compiler capability modeling.
- Do not repair source-data mistakes.
- Do not use `frozen/` or `tslgenold/` as runtime dependencies.
- Do not copy `new_chat_test` wholesale.

## Expected Tests

Add focused tests for:

- fixture evidence: the selected observed `.tsl` source form still exists;
- exact parser/catalog/lowering support for the selected non-scalar fixture;
- lowered body representation contains typed lowerable token values plus raw
  spans, not raw lowerable token passthrough;
- C++ and Rust rendered `avx2` profile artifacts contain an actual intrinsic
  call and no raw accepted lowerable token text;
- unsupported nearby fixture/body forms diagnose instead of source repair;
- generated `scalar,avx2` projects write via manifest-clean mode and
  configure/build/test;
- deterministic artifact digests across repeated runs;
- M224/M225/M227 tests keep passing.

Do not add all-profile matrices, ARM/qemu tests, broad corpus-generation
tests, or hardware autodetection tests in M228.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m228_first_real_x86_intrinsic_fixture.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: lowering feeds typed backend rendering;
   M227 templates do presentation only; no renderer-side source parsing.
2. Evidence reviewer: selected fixture is real observed `tsldata` input and
   no runtime dependency on `frozen/`, `tslgenold`, or `new_chat_test` exists.
3. Test reviewer: exact fixture coverage, unsupported-form diagnostics,
   C++/Rust parity, deterministic output, manifest-clean writing, and build
   verification are covered.
4. Documentation reviewer: roadmap/state/design-doc consistency.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update redesign docs if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M229.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
