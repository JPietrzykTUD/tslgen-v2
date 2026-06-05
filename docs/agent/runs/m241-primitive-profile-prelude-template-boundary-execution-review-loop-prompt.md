# M241 Primitive Profile Prelude Template Boundary Execution Review Loop Prompt

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
profile artifacts replace skeleton profile files, so they must carry the
active-profile prelude expected by generated smoke tests. Today that prelude is
still duplicated as ad hoc C++/Rust presentation text in focused tests and the
tiny generated pipeline.

Do not reopen lowering in M241. The task is a backend/rendering presentation
boundary cleanup.

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

Move primitive profile active-profile prelude presentation into a focused,
typed, template-backed boundary:

```text
already-decided generated profile render values
-> C++/Rust primitive profile prelude templates
-> RenderedNamespaceText / RenderedModuleText
-> existing primitive profile templates
```

This removes duplicated C++/Rust profile-scaffolding strings from tests and
the tiny generated pipeline while preserving the accepted generated project
behavior.

## Scope

Implement the smallest boundary that proves:

- C++ primitive profile artifacts can get their profile namespace metadata and
  root `tsl::active_profile` / `tsl::active_profile_family` prelude from
  supplementary templates or template partials.
- Rust primitive profile artifacts can get `ACTIVE_PROFILE` and
  `ACTIVE_PROFILE_FAMILY` from supplementary templates or template partials.
- The helper consumes already-decided typed generated-profile render values,
  not raw `.tsl`, source-body text, selected primitive objects, or backend
  semantic requests.
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
  family, file stem / namespace, and Rust module/profile feature values.
- Return existing typed presentation wrappers (`RenderedNamespaceText`,
  `RenderedModuleText`) or a small typed result around those wrappers plus
  diagnostics.

If another shape is clearly smaller, keep the same boundary: typed profile
facts in, template-rendered presentation wrappers out.

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
- Do not add C++/Rust profile-prelude source strings to Python production code.
  Tests may assert expected output strings, but production presentation should
  come from supplementary templates.
- Do not hide semantic decisions in templates. Templates may format already
  decided profile names, family names, namespaces/modules, and active-profile
  constants only.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not grow `tslgen.rendering.intrinsic_body_token_bridge` into this helper.
- Do not add runtime dependencies on `frozen/` or `tslgenold`.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m241_primitive_profile_prelude_template_boundary.py
```

Cover:

- C++ prelude rendering from typed profile values through supplementary
  templates.
- Rust prelude rendering from typed profile values through supplementary
  templates.
- Missing prelude template diagnostics.
- Unknown/semantic field diagnostics for prelude templates, consistent with
  existing template-boundary policy.
- M223/M224/M240 behavior no longer relies on ad hoc active-profile prelude
  strings in tests or `generated_primitive_pipeline.py`.
- Existing generated project write/build verification still passes for the
  tiny scalar project and the synthetic `sse2` intrinsic project.

Keep the slice narrow. Do not convert unrelated primitive rendering or
generated-project template behavior.

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
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m223_first_real_generated_primitive.py tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m238_generated_project_source_template_boundary.py tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py tslgen/tests/test_m241_primitive_profile_prelude_template_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: profile prelude presentation is template
   backed, typed, and does not reopen lowering/parser/catalog/selection or
   template-side semantics.
2. Evidence reviewer: M241 stays compatible with M223/M224/M238/M240 behavior
   and does not implement the full real x86 corpus fixture.
3. Test reviewer: C++/Rust parity, missing/invalid template diagnostics,
   removal of ad hoc prelude strings, deterministic output, and write/verify
   coverage are adequate.
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
