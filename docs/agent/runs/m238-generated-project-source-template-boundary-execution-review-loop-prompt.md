# M238 Generated Project Source Template Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M237 as accepted.

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
Milestone 237: Backend Generated-Output Resumption Planning
```

M237 audited the backend/generated-output path after M229-M236 and selected
this boundary before another real intrinsic fixture attempt. The current path
can generate and compile/test narrow scalar C++ and Rust projects. CMake and
Cargo buildsystem files already render through supplementary templates, and
primitive profile artifacts already use primitive/function-shape templates.
The remaining smell is generated-project source skeleton text in
`generated_project.py`: public entry files, profile source files, and smoke
tests are still assembled from C++/Rust source strings in Python.

## Read First

- `docs/agent/current-redesign-state.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/agent/review-checklist.md`
- `docs/redesign/implementation-roadmap.md`
- `docs/redesign/behavioral-spec.md`
- `docs/redesign/design-decisions.md`
- `docs/redesign/pipeline-design.md`
- `docs/redesign/target-architecture.md`
- `docs/redesign/flaws-to-fix.md`
- `docs/agent/runs/m237-backend-generated-output-resumption-planning-prompt.md`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/domain/generated_project.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/tests/test_m191_generated_project_smoke_boundary.py`
- `tslgen/tests/test_m217_primitive_template_boundary.py`
- `tslgen/tests/test_m223_first_real_generated_primitive.py`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m225_generated_profile_build_flags.py`
- `supplementary/buildsystem/cpp/templates/`
- `supplementary/buildsystem/rust/templates/`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Move generated-project source skeleton presentation into supplementary
templates or template partials for both C++ and Rust:

```text
typed generated-project render model
+ supplementary source templates/partials
-> deterministic in-memory generated-project source artifacts
```

Templates own language presentation. Python owns typed already-decided values
and side-effect-free rendering orchestration. Neither side may decide backend
semantics in this milestone.

## Scope

Implement the smallest source-template boundary that preserves existing
generated output behavior.

Move these generated source skeletons out of raw Python string assembly:

- `cpp/include/tsl.hpp`
- `cpp/include/profiles/{profile}.hpp`
- `cpp/tests/smoke.cpp`
- `rust/src/lib.rs`
- `rust/src/profiles/{profile}.rs`
- `rust/tests/smoke.rs`

Add supplementary templates or partial templates under the accepted layout,
preferably below:

```text
supplementary/templates/cpp/generated_project/
supplementary/templates/rust/generated_project/
```

Use the existing standard-library formatting approach unless the executor
documents a concrete presentation-only reason that the current engine is not
enough. If profile loops are needed, prefer small supplementary partial
templates rendered per typed profile and joined by Python over introducing a
broader template engine. A new engine such as Jinja2 is allowed only if it
stays presentation-only and the tests prove it does not become a semantic
engine.

The implementation should:

- keep `build_generated_project_render_model(...)` typed and semantic-free;
- keep profile feature normalization and buildsystem template behavior
  unchanged;
- render the source skeleton artifacts from typed values such as profile
  macros, profile names, file stems, Rust feature/module names, package/crate
  names, and already-rendered template partials;
- preserve current artifact paths, media types, metadata, and deterministic
  ordering;
- preserve current scalar and scalar+`avx2` generated-project write/verify
  behavior;
- diagnose missing source skeleton templates;
- reject unknown fields, unsupported compound field shapes, and semantic or
  unresolved fields in generated-project source templates;
- avoid new public APIs unless the existing rendering package clearly needs
  one.

## Guardrails

- Do not reopen lowering, parser, catalog, selector, primitive-call, or TSIL
  keyword work.
- Do not implement the real x86 intrinsic fixture.
- Do not add an intrinsic translation/render bridge in M238.
- Do not change primitive render plans, primitive templates, or function-shape
  templates except for compatibility fixes forced by this boundary.
- Do not add backend semantic decisions, type spelling, intrinsic selection,
  primitive selection, dependency closure, feature gating, fallback selection,
  source repair, or compiler capability policy to templates.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not keep or add whole generated C++/Rust header/module/test source
  assembly in Python. Python may compute typed render values and join
  already-rendered supplementary partials.
- Do not use `frozen/` or `tslgenold/` as runtime dependencies.
- Keep C++ and Rust in parity.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m238_generated_project_source_template_boundary.py
```

Cover:

- C++ public header, C++ profile header, and C++ smoke test render through
  supplementary source templates or partials.
- Rust `lib.rs`, Rust profile module, and Rust smoke test render through
  supplementary source templates or partials.
- Current scalar artifact contents and scalar+`avx2` build-flag behavior remain
  compatible with M224/M225 expectations.
- Deterministic artifact output across repeated renders.
- Missing C++ source template diagnostic.
- Missing Rust source template diagnostic.
- Unknown field diagnostic.
- Unsupported compound field diagnostic.
- Semantic/unresolved field diagnostic for generated-project source templates.
- No production Python function remains responsible for assembling a complete
  generated C++/Rust public header, profile source file, or smoke test from raw
  language-line lists.

Keep brittle source-text checks focused on this explicit boundary. Prefer
behavioral tests for generated artifacts and diagnostics elsewhere.

## Out Of Scope

- New lowering facts or lowering cleanup.
- Outer TSL parser/corpus integration.
- Full `tsldata` primitive selection.
- Real `fundamental.tsl` x86 intrinsic output.
- Backend intrinsic translation, Rust architecture module policy, unsafe body
  policy, vector/register type spelling, or non-scalar primitive signatures.
- New dependency closure/topological planning behavior.
- Broad generated test framework.
- CLI/API changes.
- Artifact writer changes beyond preserving existing manifest-clean behavior.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m191_generated_project_smoke_boundary.py tslgen/tests/test_m217_primitive_template_boundary.py tslgen/tests/test_m223_first_real_generated_primitive.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m238_generated_project_source_template_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: generated-project source presentation moved
   to supplementary templates/partials; templates are presentation-only; Python
   computes typed values only; no lowering or semantic rendering leak.
2. Evidence reviewer: current M191/M224/M225 behavior, artifact paths,
   profile flags, and build verification remain compatible; M238 does not
   implement the real x86 fixture.
3. Test reviewer: C++/Rust parity, missing/invalid template diagnostics,
   deterministic output, and compile/test verification coverage are adequate.
4. Documentation reviewer: roadmap/state/design-doc consistency and follow-ups
   are accurate.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the
appropriate next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` only if behavior or architecture changes
  beyond the M237-selected boundary;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the next milestone inside M238.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
