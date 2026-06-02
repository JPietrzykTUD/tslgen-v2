# M223 First Real Generated Primitive Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M222 as accepted.

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
Milestone 222: Primitive Render Plan
```

M217 established presentation-only C++ and Rust primitive templates. M218
established typed already-decided primitive render model values. M222 added
the primitive render plan boundary that preserves supplied primitive order and
adapts already-rendered plan values into M218/M217 contexts.

M191 established scalar profile selection, generated-project skeleton
rendering, manifest-clean artifact writing, and after-write build
verification. M223 is the first slice that combines those pieces for one tiny
already-decided generated primitive.

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
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/primitive_render_model.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/io/artifacts.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/tests/test_m191_generated_project_smoke_boundary.py`
- `tslgen/tests/test_m222_primitive_render_plan.py`

## Goal

Render one tiny already-decided primitive through the accepted C++ and Rust
primitive templates, compose those profile artifacts with the accepted
generated-project skeleton, write the combined artifact set, and verify scalar
C++ and Rust generated projects.

This milestone proves the first end-to-end backend/output artifact path after
lowering is complete by current contract, without reading `.tsl` data or
inventing backend semantics.

## Scope

Add focused implementation and tests, likely:

```text
tslgen/src/tslgen/rendering/generated_primitive_project.py
tslgen/tests/test_m223_first_real_generated_primitive.py
```

The implementation should:

- use accepted scalar generated-profile selection and generated-project
  skeleton rendering;
- use M222 primitive render plans for one tiny already-decided C++ scalar
  profile header and one tiny already-decided Rust scalar profile module;
- render primitive profile artifacts through M217 primitive templates;
- compose skeleton artifacts and primitive artifacts deterministically;
- allow primitive profile artifacts to replace the skeleton's empty profile
  artifacts only at the exact selected profile artifact paths:
  `cpp/include/profiles/scalar.hpp` and `rust/src/profiles/scalar.rs`;
- keep unrelated duplicate logical paths as structured diagnostics;
- preserve public entry artifacts (`cpp/include/tsl.hpp`, `rust/src/lib.rs`),
  buildsystem artifacts, and smoke tests from the skeleton;
- make the primitive replacement profile artifacts include the active-profile
  constants expected by the existing scalar smoke tests;
- write the combined artifacts with the manifest-clean artifact writer into a
  temporary test output root;
- run the existing after-write build verifier for scalar C++ and Rust;
- keep artifact ordering and digests deterministic.

The tiny primitive may be an already-rendered fixture such as `add_one` or
`identity`. The important boundary is that M223 consumes already-decided
render text; it must not select a primitive from `tsldata` or lower a body.

## Guardrails

- Do not reopen lowering or rescan raw TSIL.
- Do not parse `.tsl` files or select primitives from `tsldata`.
- Do not run body-token substitution in M223.
- Do not translate source operations, intrinsics, type queries, value queries,
  signatures, declarations, or primitive calls.
- Do not implement dependency closure or topological sorting.
- Do not broaden profile selection beyond the scalar default.
- Do not move C++ or Rust code into Python beyond already-rendered tiny
  fixture text used by the test slice.
- Do not hide semantic decisions in templates, renderers, the artifact
  writer, or the build verifier.
- Do not make `frozen/` or `tslgenold` runtime dependencies.

## Expected Tests

Add focused tests for:

- C++ and Rust primitive render plans producing profile artifacts at the
  selected scalar paths;
- deterministic composition of skeleton plus primitive profile artifacts;
- allowed replacement of the skeleton scalar profile artifacts by primitive
  artifacts;
- diagnostics for unrelated duplicate logical paths;
- manifest-clean write of the combined artifact set in a temporary output
  root;
- real scalar C++/Rust build verification using the existing verifier;
- preservation of public entry artifacts and smoke-test artifacts;
- deterministic digest manifest across two identical runs;
- no `.tsl` parsing, lowering, body-token substitution, or template-side
  semantics;
- public imports if new API is exposed.

Do not add broad generated-corpus rendering, profile matrices, dependency
closure, or generated tests beyond the accepted scalar smoke path in M223.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m223_first_real_generated_primitive.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: composition consumes already-rendered
   primitive artifacts and skeleton artifacts, keeps writer/verifier side
   effects at their boundaries, and does not reopen lowering or selection.
2. Evidence reviewer: M191/M217/M222 contracts are used correctly, and the
   scalar profile replacement paths match the generated-project layout.
3. Test reviewer: coverage of C++/Rust parity, deterministic composition,
   duplicate diagnostics, manifest-clean writing, build verification, and
   public imports.
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
  or clarifies generated primitive project composition policy;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M224.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
