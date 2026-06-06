# M252 Real SSE/SSE2 Unmasked Binary Arithmetic Matrix Build Verification Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M251 as accepted.

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
Milestone 251: Real AVX2 Unmasked Binary Arithmetic Matrix Build Verification
```

M251 proved that the existing generic selected primitive project pipeline
already renders and build-verifies the real unmasked `add`/`sub` AVX2 matrix
for integer and floating type tags without production-code changes. The next
task should broaden confidence in the same generic path, not add another
intrinsic-specific subsystem.

## Goal

Render and build-verify the real SSE/SSE2 unmasked binary arithmetic matrix
for both C++ and Rust:

```text
primitives: add, sub
integer selector: ("sse", "?i?")
floating selectors: ("sse", "f32"), ("sse", "f64")
integer type_tags: si8, si16, si32, si64, ui8, ui16, ui32, ui64
floating type_tags: f32, f64
selected extension: sse
requested profile: sse2
parameters: ("left", "right")
```

The selected source is real `tsldata/primitives/arithmetic/fundamental.tsl`.

## Scope

Implement the smallest coherent slice:

- Use the generic selected primitive project pipeline; do not add a sibling
  fixture pipeline.
- Select real unmasked `add` and `sub` entries:
  - selector path `("sse", "?i?")` for the eight concrete integer type tags;
  - selector path `("sse", "f32")` for `f32`;
  - selector path `("sse", "f64")` for `f64`.
- Preserve concrete selected `TypeTag` context for every entry. Wildcard
  source selectors are selection evidence only.
- Reuse accepted exact `emit_return(PAYLOAD);` handling and existing backend
  intrinsic discovery/lowering/handoff path.
- Reuse accepted backend type spelling, extension-owned default
  `intrin_compose` policy, source-provided modifier translation, Rust unsafe
  body policy, artifact writing, and generated-project verification.
- Verify C++ configure/build/test and Rust test for requested profile `sse2`.
- If the existing implementation already supports the matrix, add tests and
  docs only. If implementation is needed, limit it to generic selected-project
  plumbing required by this real matrix.
- Preserve M249, M250, M251, and scalar M243/M244 build behavior.

## Non-Negotiable Guardrails

- No new lowering semantics.
- No broad TSIL parser work.
- No exact raw source-string matching of modifier expressions.
- No Python-owned suffix, intrinsic, vector type, primitive, or profile feature
  tables.
- No template-side modifier/type/intrinsic/safety decisions.
- No dependency closure or primitive-call expansion.
- No fixture sibling pipeline such as `real_sse_pipeline.py`,
  `real_add_pipeline.py`, `real_sub_pipeline.py`, or
  `binary_arithmetic_pipeline.py`.
- No extension of `generated_primitive_pipeline.py`.
- No runtime dependency on `frozen` or `tslgenold`.
- Do not solve masks, generic loop bodies, SVE, NEON, AVX2 broadening,
  AVX512, source-operation, or primitive-call build verification in this
  milestone.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m252_real_sse_unmasked_binary_arithmetic_matrix_build_verification.py
```

Cover:

- Real `add` and `sub` selected entries for all ten concrete SSE/SSE2 type
  tags render deterministic C++ and Rust artifacts.
- Generated output contains concrete register type spellings from extension
  metadata, not wildcard text.
- Floating entries use extension-owned default policy suffixes such as `ps`
  and `pd`.
- Integer entries use source-provided signed suffix modifier behavior for both
  `add` and `sub`, including unsigned selected types using `epi*`, not `epu*`.
- Representative C++ calls include `_mm_add_ps`, `_mm_add_epi32`,
  `_mm_sub_pd`, and `_mm_sub_epi64`.
- Representative Rust calls use fully-qualified `core::arch::x86_64::...`
  intrinsic paths and the accepted typed unsafe body policy.
- `ArtifactWriter` writes the generated project and `verify_generated_project`
  succeeds with command sequence C++ configure/build/test plus Rust test for
  profile `sse2`.
- Guardrails: no fixture sibling pipeline, no local `_mm`/suffix spelling
  table in production code, no exact source-string matcher, no `frozen` or
  `tslgenold` runtime dependency.

## Out Of Scope

New lowering semantics; source repair; broad body expression parsing; matching
target-language operators; masks; generic loops; primitive-call rendering;
dependency closure; semantic vector runtime tests; generated test-source
production; CLI workflow; SVE/NEON/AVX2/AVX512 build verification;
target-feature or compiler capability modeling beyond the accepted
generated-project verifier.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py tslgen/tests/test_m247_selected_implementation_render_context.py tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py tslgen/tests/test_m249_real_avx2_selected_primitive_build_verification.py tslgen/tests/test_m250_real_avx2_integer_modifier_lowering_build_verification.py tslgen/tests/test_m251_real_avx2_unmasked_binary_arithmetic_matrix_build_verification.py tslgen/tests/test_m252_real_sse_unmasked_binary_arithmetic_matrix_build_verification.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: generic selected project pipeline only;
   no fixture sibling pipeline, raw-source matcher, template semantic
   inference, or new lowering.
2. Evidence reviewer: selected fixture is real `tsldata`; suffix behavior,
   type spellings, headers, profiles, and target features come from accepted
   catalogs/models.
3. Test reviewer: matrix coverage, unsigned-to-signed suffix behavior,
   C++/Rust build parity, scalar/M249/M250/M251 regressions, determinism, and
   guardrails.
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
- do not start M253 inside M252.

## Final Report

Report:

1. Implementation summary.
2. Whether the matrix needed production changes or only coverage/docs.
3. How typed default and source-provided modifier paths are exercised.
4. C++/Rust generated output and build behavior.
5. Review/audit verdicts.
6. Validation commands and exact results.
7. Any follow-ups.
8. Next active prompt path.
