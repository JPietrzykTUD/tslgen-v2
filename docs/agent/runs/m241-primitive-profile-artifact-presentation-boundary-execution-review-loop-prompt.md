# M241 Primitive Profile Artifact Presentation Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M240 as accepted.

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
Milestone 240: Synthetic Intrinsic Generated-Project Verification
```

M240 proved that synthetic already-lowered typed intrinsic handoffs can render
primitive profile artifacts, compose into the generated project skeleton, write
through `ArtifactWriter`, and verify through the existing C++/Rust build
verifier. It stayed synthetic and did not reopen lowering or real corpus
selection.

M240 also exposed a concrete profile-artifact presentation boundary: primitive
profile artifacts replace skeleton profile files, so they must own the full
profile-file presentation wrapper expected by generated smoke tests. Today
parts of that wrapper are still duplicated as ad hoc C++/Rust presentation text
in focused tests and the tiny generated pipeline.

Do not reopen lowering in M241. The task is a backend/rendering presentation
boundary cleanup for the primitive profile artifact wrapper.

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
- `docs/agent/runs/m240-synthetic-intrinsic-generated-project-verification-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/tests/test_m223_first_real_generated_primitive.py`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m238_generated_project_source_template_boundary.py`
- `tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Move primitive profile artifact presentation into a focused, typed,
template-backed boundary:

```text
already-decided generated profile render values
+ already-rendered primitive declarations/definitions/body text
-> C++/Rust primitive profile artifact templates
-> primitive profile ArtifactSet
   or RenderedNamespaceText / RenderedModuleText used by the existing templates
-> existing primitive profile templates
```

This removes duplicated C++/Rust profile-scaffolding strings from tests and
the tiny generated pipeline while preserving the accepted generated project
behavior. The milestone should be broader than just the active-profile
constants: it should own the small wrapper around primitive profile files.

## Scope

Implement the smallest boundary that proves primitive profile replacement
artifacts have a single template-backed presentation owner:

- C++ primitive profile artifacts can get their profile includes, namespace
  open/close text, profile namespace metadata, root `tsl::active_profile` /
  `tsl::active_profile_family` constants, and primitive declarations/
  definitions from supplementary templates or template partials.
- Rust primitive profile artifacts can get their imports, module wrapper,
  `ACTIVE_PROFILE` / `ACTIVE_PROFILE_FAMILY` constants, and primitive
  definitions from supplementary templates or template partials.
- The helper consumes already-decided typed generated-profile render values,
  already-rendered primitive presentation values, and explicit artifact paths;
  it does not consume raw `.tsl`, source-body text, selected primitive objects,
  or backend semantic requests.
- Existing M223/M224/M240 generated outputs and write/build verification
  behavior remain compatible.
- C++ and Rust stay in parity.

Preferred shape:

- Add focused supplementary assets under a clear primitive-profile location,
  for example:

```text
supplementary/templates/cpp/primitive_profile/
supplementary/templates/rust/primitive_profile/
```

- Add a small rendering helper that accepts typed profile presentation values
  already present in generated-project render models, such as profile name,
  family, file stem / namespace, Rust module/profile feature values, and
  already-rendered primitive presentation text.
- Return either primitive profile `ArtifactSet` values directly, or existing
  typed presentation wrappers (`RenderedNamespaceText`, `RenderedModuleText`)
  feeding the existing primitive profile templates. Pick the smaller shape that
  removes duplicated wrapper text without changing semantic boundaries.

If another shape is clearly smaller, keep the same boundary: typed profile
facts plus already-rendered primitive presentation in, template-rendered
profile artifacts or wrappers out.

## Guardrails

- Do not change lowering, recursive TSIL keyword handling, primitive-call
  semantics, parser/catalog/selector code, source-body scanning, or real
  primitive selection.
- Do not implement full `fundamental.tsl`/real x86 corpus selection.
- Do not implement dependency closure or topological primitive planning.
- Do not add new intrinsic, type, value, source-operation, or feature
  semantics.
- Do not change generated-project composition policy unless a blocking bug in
  the existing replacement contract is proven. The expected slice should use
  the existing replacement contract.
- Do not add C++/Rust primitive profile wrapper source strings to Python
  production code. Tests may assert expected output strings, but production
  presentation should come from supplementary templates.
- Do not hide semantic decisions in templates. Templates may format already
  decided profile names, family names, namespaces/modules, includes/imports,
  active-profile constants, and already-rendered primitive declarations/
  definitions only.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not grow `tslgen.rendering.intrinsic_body_token_bridge` into this helper.
- Do not add runtime dependencies on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py
```

Cover:

- C++ primitive profile artifact rendering from typed profile values and
  already-rendered primitive presentation through supplementary templates.
- Rust primitive profile artifact rendering from typed profile values and
  already-rendered primitive presentation through supplementary templates.
- Missing primitive-profile template diagnostics.
- Unknown/semantic field diagnostics for primitive-profile templates,
  consistent with existing template-boundary policy.
- M223/M224/M240 behavior no longer relies on ad hoc active-profile prelude,
  namespace/module wrapper, include/import, or profile scaffolding strings in
  tests or `generated_primitive_pipeline.py`.
- Existing generated project write/build verification still passes for the
  tiny scalar project and the synthetic `sse2` intrinsic project.

Keep the slice bounded to primitive profile artifact presentation. Do not
convert unrelated generated-project skeleton behavior, buildsystem behavior, or
backend semantic translation.

## Out Of Scope

- Full source/corpus path from `tsldata/primitives/arithmetic/fundamental.tsl`.
- Wildcard type expansion or selected primitive context construction.
- Dependency closure/topological primitive planning.
- Vector/register type spelling expansion beyond already-provided render
  values.
- Rust architecture module selection beyond existing renderer inputs.
- New generated-project composition mode.
- New CLI/API generation command.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m223_first_real_generated_primitive.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m238_generated_project_source_template_boundary.py tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: primitive profile artifact presentation is
   template backed, typed, and does not reopen lowering/parser/catalog/
   selection or template-side semantics.
2. Evidence reviewer: M241 stays compatible with M223/M224/M238/M240 behavior
   and does not implement the full real x86 corpus fixture.
3. Test reviewer: C++/Rust parity, missing/invalid template diagnostics,
   removal of ad hoc profile wrapper strings, deterministic output, and
   write/verify coverage are adequate.
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
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start the next milestone inside M241.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
