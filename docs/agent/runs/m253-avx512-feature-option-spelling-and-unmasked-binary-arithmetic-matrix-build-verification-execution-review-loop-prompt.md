# M253 AVX512 Feature Option Spelling And Unmasked Binary Arithmetic Matrix Build Verification Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M252 as accepted.

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
Milestone 252: Real SSE/SSE2 Unmasked Binary Arithmetic Matrix Build Verification
```

M249-M252 proved that the generic selected primitive project pipeline can
render and build-verify real scalar, AVX2, and SSE/SSE2 selected primitives
without fixture-shaped sibling pipelines. The next AVX512 step must not become
another primitive-specific path. Preflight evidence shows the likely shared
blocker is generated feature option spelling: aliases from
`tsldata/detail/flags.tsl` can be selected as output spellings, producing
invalid C++ options such as `-mavx3f` instead of canonical `-mavx512f`.

## Goal

Make machine-profile feature lowering to generated C++ and Rust build options
canonical enough for AVX512 profiles, then render and build-verify the real
AVX512 unmasked binary arithmetic matrix for both C++ and Rust:

```text
primitives: add, sub
integer selector: ("avx512", "?i?")
floating selector: ("avx512", "f?")
integer type_tags: si8, si16, si32, si64, ui8, ui16, ui32, ui64
floating type_tags: f32, f64
selected extension: avx512
requested profile: skylake
parameters: ("left", "right")
```

The selected source is real `tsldata/primitives/arithmetic/fundamental.tsl`.

## Scope

Implement the smallest coherent slice:

- Keep `tsldata/detail/flags.tsl` aliases as input normalization evidence, but
  do not use legacy alias spellings such as `avx3f`, `avx3cd`, `avx3vl`,
  `avx3dq`, or `avx3bw` as default generated compiler options.
- Add or adjust one typed feature-option spelling boundary so generated C++
  profile options use canonical normalized feature names by default, for
  example `-mavx512f`, `-mavx512cd`, `-mavx512vl`, `-mavx512dq`, and
  `-mavx512bw`.
- Preserve explicit machine-profile alternatives as deliberate output spelling
  overrides, for example `avx512_vpclmulqdq=vpclmulqdq`,
  `avx512_gfni=gfni`, and `avx512_vaes=vaes`.
- Keep Rust target features typed and canonical, with explicit alternatives
  applied by the same already-decided build-option model.
- Use the generic selected primitive project pipeline; do not add a sibling
  fixture pipeline.
- Select real unmasked `add` and `sub` entries:
  - selector path `("avx512", "?i?")` for the eight concrete integer type tags;
  - selector path `("avx512", "f?")` for `f32` and `f64`.
- Preserve concrete selected `TypeTag` context for every entry. Wildcard
  source selectors are selection evidence only.
- Reuse accepted exact `emit_return(PAYLOAD);` handling and existing backend
  intrinsic discovery/lowering/handoff path.
- Reuse accepted backend type spelling, extension-owned default
  `intrin_compose` policy, source-provided modifier translation, Rust unsafe
  body policy, artifact writing, and generated-project verification.
- Verify C++ configure/build/test and Rust test for requested profile
  `skylake`.

## Non-Negotiable Guardrails

- No new lowering semantics for TSIL bodies.
- No broad TSIL parser work.
- No exact raw source-string matching of modifier expressions.
- No Python-owned suffix, intrinsic, vector type, primitive, or profile feature
  tables.
- No template-side modifier/type/intrinsic/safety/feature spelling decisions.
- No compiler capability modeling or host CPU autodetection.
- No broad compiler-specific flag database.
- No dependency closure or primitive-call expansion.
- No fixture sibling pipeline such as `real_avx512_pipeline.py`,
  `real_add_pipeline.py`, `real_sub_pipeline.py`, or
  `binary_arithmetic_pipeline.py`.
- No extension of `generated_primitive_pipeline.py`.
- No runtime dependency on `frozen` or `tslgenold`.
- Do not solve masks, generic loop bodies, SVE, NEON, source-operation, or
  primitive-call build verification in this milestone.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m253_avx512_feature_option_spelling_and_unmasked_binary_arithmetic_matrix_build_verification.py
```

Cover:

- Machine/profile feature option spelling chooses canonical generated C++
  options such as `-mavx512f` and not `-mavx3f`.
- Explicit machine-profile alternatives still override canonical spelling for
  accepted cases such as `avx512_vpclmulqdq=vpclmulqdq`,
  `avx512_gfni=gfni`, and `avx512_vaes=vaes`.
- Rust target features are emitted from the same typed build-option model and
  remain deterministic.
- Real `add` and `sub` selected entries for all ten concrete AVX512 type tags
  render deterministic C++ and Rust artifacts.
- Generated output contains concrete register type spellings from extension
  metadata, not wildcard text.
- Floating entries use extension-owned default policy suffixes such as `ps`
  and `pd`.
- Integer entries use source-provided signed suffix modifier behavior for both
  `add` and `sub`, including unsigned selected types using `epi*`, not `epu*`.
- Representative C++ calls include `_mm512_add_ps`, `_mm512_add_epi32`,
  `_mm512_sub_pd`, and `_mm512_sub_epi64`.
- Representative Rust calls use fully-qualified `core::arch::x86_64::...`
  intrinsic paths and the accepted typed unsafe body policy.
- `ArtifactWriter` writes the generated project and `verify_generated_project`
  succeeds with command sequence C++ configure/build/test plus Rust test for
  profile `skylake`.
- Guardrails: no fixture sibling pipeline, no local intrinsic/suffix/type table
  in production code, no exact source-string matcher, no `frozen` or
  `tslgenold` runtime dependency.

## Out Of Scope

New TSIL lowering semantics; source repair; broad body expression parsing;
matching target-language operators; masks; generic loops; primitive-call
rendering; dependency closure; semantic vector runtime tests beyond the
accepted smoke harness; generated test-source production; CLI workflow;
SVE/NEON build verification; target-feature or compiler capability modeling
beyond canonical generated option spelling.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m189_machine_feature_profiles.py tslgen/tests/test_m191_generated_profile_project_skeleton.py tslgen/tests/test_m225_generated_profile_build_flags.py tslgen/tests/test_m249_real_avx2_selected_primitive_build_verification.py tslgen/tests/test_m251_real_avx2_unmasked_binary_arithmetic_matrix_build_verification.py tslgen/tests/test_m252_real_sse_unmasked_binary_arithmetic_matrix_build_verification.py tslgen/tests/test_m253_avx512_feature_option_spelling_and_unmasked_binary_arithmetic_matrix_build_verification.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: typed feature-option boundary plus generic
   selected project pipeline only; no fixture sibling pipeline, raw-source
   matcher, template semantic inference, compiler capability model, or new
   TSIL lowering.
2. Evidence reviewer: selected fixture is real `tsldata`; suffix behavior,
   type spellings, headers, profile flags, target features, and alternatives
   come from accepted catalogs/models.
3. Test reviewer: AVX512 feature spelling, explicit alternatives, matrix
   coverage, unsigned-to-signed suffix behavior, C++/Rust build parity,
   scalar/M249/M251/M252 regressions, determinism, and guardrails.
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
- do not start M254 inside M253.

## Final Report

Report:

1. Implementation summary.
2. Whether AVX512 needed production changes and where.
3. How canonical feature spelling and explicit alternatives are exercised.
4. How typed default and source-provided modifier paths are exercised.
5. C++/Rust generated output and build behavior.
6. Review/audit verdicts.
7. Validation commands and exact results.
8. Any follow-ups.
9. Next active prompt path.
