# M249 Real AVX2 Selected Primitive Build Verification Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M248 as accepted.

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
Milestone 248: Generic Selected Primitive Project Intrinsic Rendering Integration
```

M248 connected the M247 context-aware intrinsic body-token bridge to the generic
selected primitive project pipeline. The pipeline can render the real
`add` `avx2/f32` implementation from
`tsldata/primitives/arithmetic/fundamental.tsl` through M245 `CurrentVector`
type spelling, extension-owned C++ headers, extension-owned
`intrin_compose` policy, and deterministic C++/Rust generated project
artifacts.

## Goal

Make the same real selected primitive project slice compile under the existing
generated project verification path for C++ and Rust:

```text
primitive: add
selector_path: ("avx2", "f?")
selected extension: avx2
type_tag: f32
requested profile: avx2
parameters: ("left", "right")
```

This milestone turns the M248 rendered artifact into a build-verified artifact.
It is not another `intrin_compose` milestone and it must not reopen source
lowering.

## Scope

Implement the smallest coherent build-verification slice:

- Use `tslgen.pipeline.primitive_project_pipeline` to render the real
  `add` `avx2/f32` project for C++ and Rust.
- Write the in-memory artifacts to a temporary generated output tree through
  `ArtifactWriter`.
- Verify the generated project through the accepted `verify_generated_project`
  boundary for the selected `avx2` profile.
- Preserve C++ and Rust parity. The expected verification command sequence is
  C++ configure/build/test and Rust test for profile `avx2`.
- Reuse the existing generated project build flags/profile metadata. The
  generator still does not model compiler support or host hardware; verification
  failures from an incapable environment remain environment/build failures.
- If Rust fails because a lowered backend intrinsic call needs an unsafe call
  boundary or target-feature presentation, add the smallest typed backend
  rendering policy needed for the already-lowered intrinsic body-token result.
  The policy must be driven by typed backend/profile/render context, not string
  matching of `_mm256` or `core::arch`.
- Keep Rust module qualification policy from M247 intact. Do not double
  qualify `core::arch::*` names.
- Keep templates presentation-only. Templates may format an already-decided
  unsafe wrapper/attribute/body text value, but must not decide whether an
  intrinsic is unsafe, which profile is selected, which target feature applies,
  or which intrinsic/type spelling to use.
- Preserve M243/M244 scalar build behavior and M248 text-rendering behavior.

## Non-Negotiable Guardrails

- No new source lowering semantics.
- No broad TSIL parser work.
- No dependency closure or primitive-call expansion.
- No pairwise `emit_return + intrin_compose` special case.
- No Python-owned C++/Rust primitive bodies or backend intrinsic spelling
  tables.
- No template-side intrinsic/type/feature/safety selection.
- No extension of `generated_primitive_pipeline.py`.
- No sibling fixture pipeline such as `real_avx2_pipeline.py`.
- No runtime dependency on `frozen` or `tslgenold`.
- Do not solve AVX512, NEON, SVE, mask, generic, or primitive-call build
  verification in this milestone.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m249_real_avx2_selected_primitive_build_verification.py
tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py
```

Cover:

- Real `add` `avx2/f32` selected entry writes deterministic artifacts and
  `verify_generated_project(...)` succeeds for both C++ and Rust using profile
  `avx2`.
- The verification report contains the expected command sequence:
  C++ `configure`, `build`, `test`, then Rust `test`, all for profile `avx2`,
  all with return code 0.
- Generated C++ still contains extension-owned `__m256`, `<immintrin.h>`, and
  `_mm256_add_ps(left, right)`.
- Generated Rust still contains extension-owned
  `core::arch::x86_64::__m256` and exactly one
  `core::arch::x86_64::_mm256_add_ps(left, right)` call path.
- If a Rust unsafe wrapper/attribute is added, assert the already-decided
  rendered output shape and keep it typed/presentation-only.
- Scalar M243/M244 build-verification tests still pass.
- Guardrails: no fixture sibling pipeline, no local intrinsic spelling table,
  no `frozen`/`tslgenold` runtime dependency, no semantic fields added to
  templates for intrinsic/type/profile decisions.

## Out Of Scope

Lowering completeness work; source-operation rendering; primitive-call
rendering; dependency closure; mask/generic/SVE/NEON/AVX512 generated build
verification; generated semantic tests that execute vector values; CLI
workflow; deleting `generated_primitive_pipeline.py`; host feature detection;
compiler capability modeling.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py tslgen/tests/test_m244_5_real_primitive_project_pipeline_consolidation.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py tslgen/tests/test_m247_selected_implementation_render_context.py tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py tslgen/tests/test_m249_real_avx2_selected_primitive_build_verification.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: real selected project pipeline only; typed
   safety/profile policy if needed; no fixture sibling pipeline, no pairwise
   keyword special case, no renderer or template semantic inference.
2. Evidence reviewer: selected fixture is real `tsldata`; type, intrinsic,
   header, profile, and target-feature data come from accepted catalogs/models.
3. Test reviewer: C++/Rust parity, real build verification, scalar regression,
   determinism, diagnostics, and guardrails are covered.
4. Documentation reviewer: roadmap/state/spec/decision consistency and next
   prompt accuracy.
5. Validation auditor: exact validation results and workspace hygiene.

If any reviewer returns `Needs Revision`, make only focused fixes for the
blocking issues and rerun the relevant focused review. If any returns
`Return To Planner` or `Reject`, stop implementation and create the appropriate
next prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the execution result;
- update `docs/redesign/behavioral-spec.md` or
  `docs/redesign/design-decisions.md` if behavior or architecture changes;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete prompt under `docs/agent/runs/`;
- do not start M250 inside M249.

## Final Report

Report:

1. Implementation summary.
2. How the real AVX2 generated project is verified.
3. C++/Rust generated output and build behavior.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
