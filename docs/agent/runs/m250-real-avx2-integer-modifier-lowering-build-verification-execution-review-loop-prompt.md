# M250 Real AVX2 Integer Modifier Lowering Build Verification Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M249 as accepted.

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
Milestone 249: Real AVX2 Selected Primitive Build Verification
```

M249 verifies the real `add` `avx2/f32` selected primitive project through the
generic selected primitive project pipeline, `ArtifactWriter`, and
`verify_generated_project` for both C++ and Rust. It also accepts typed Rust
intrinsic body safety policy for already-lowered intrinsic body-token output.

The next task focuses on lowering handoff, not new source syntax: the real
AVX2 integer `add` body already contains accepted nested lowering facts, but
the selected project bridge must pass the already-lowered modifier facts into
backend modifier translation before rendering.

## Goal

Make the real `add` `avx2/?i?` selected implementation matrix compile through
the same generated project verification path as M249, while proving that the
source-provided intrinsic suffix modifier is handled through typed lowering
and backend translation:

```text
suffix=value<backend>(
  intrin::suffix(
    type<generation>(
      base::signed_of(type<generation>(base::in))
    )
  )
)
```

The selected source is real `tsldata/primitives/arithmetic/fundamental.tsl`.

## Scope

Implement the smallest coherent slice:

- Render the real `add` selected entries for:

  ```text
  selector_path: ("avx2", "?i?")
  selected extension: avx2
  requested profile: avx2
  parameters: ("left", "right")
  type_tags: si8, si16, si32, si64, ui8, ui16, ui32, ui64
  ```

- Preserve concrete selected `TypeTag` context for every entry. Wildcard
  source selectors are selection evidence only; do not render or translate
  wildcard text as the current type.
- Use the accepted multiline `emit_return(...)` payload handling and existing
  backend intrinsic discovery/lowering path.
- If the current pipeline fails to render the source-provided suffix modifier,
  connect already-lowered `BackendIntrinsicComposeHandoffRequest` modifier
  fields to the accepted backend intrinsic modifier translation boundary before
  calling the M247/M249 body-token bridge.
- Translate modifier fields from typed selected context: backend id, selected
  extension, selected concrete type tag, backend metadata, extension catalog,
  and existing lowered type/value facts. Do not match the exact raw source
  string above.
- For unsigned integer selected types, preserve the source-requested
  `base::signed_of(base::in)` behavior: the lowered modifier selects the signed
  intrinsic suffix family such as `epi8`, not unsigned suffix text guessed from
  the selected type tag.
- Write artifacts through `ArtifactWriter`.
- Verify C++ configure/build/test and Rust test for profile `avx2`.
- Preserve M249 `add avx2/f32` build verification and M243/M244 scalar build
  behavior.

## Non-Negotiable Guardrails

- No new source lowering semantics.
- No broad TSIL parser work.
- No exact raw string matching of the modifier expression.
- No Python-owned suffix, intrinsic, vector type, or profile feature tables.
- No template-side modifier/type/intrinsic/safety decisions.
- No dependency closure or primitive-call expansion.
- No fixture sibling pipeline such as `real_avx2_pipeline.py`,
  `real_add_pipeline.py`, or `integer_modifier_pipeline.py`.
- No extension of `generated_primitive_pipeline.py`.
- No runtime dependency on `frozen` or `tslgenold`.
- Do not solve mask, generic, SVE, NEON, AVX512, source-operation, or
  primitive-call build verification in this milestone.

## Expected Tests

Add or update focused tests, likely:

```text
tslgen/tests/test_m250_real_avx2_integer_modifier_lowering_build_verification.py
```

Cover:

- Real `add` `avx2/?i?` selected entries for all eight concrete integer type
  tags render deterministic C++ and Rust artifacts.
- Generated output contains concrete register type spellings from extension
  metadata, not wildcard text.
- The source-provided suffix modifier is translated through typed modifier
  facts. Assert representative output:
  - C++ integer calls use `_mm256_add_epi8`, `_mm256_add_epi16`,
    `_mm256_add_epi32`, and `_mm256_add_epi64`.
  - Rust integer calls use the fully-qualified `core::arch::x86_64::...`
    versions and are wrapped by the accepted typed Rust unsafe body policy.
- Unsigned selected types use the signed intrinsic suffix requested by the
  source modifier, for example `ui8` uses `epi8`, not `epu8`.
- `ArtifactWriter` writes the generated project and `verify_generated_project`
  succeeds with command sequence C++ configure/build/test plus Rust test for
  profile `avx2`.
- M249 `add avx2/f32` and scalar M243/M244 build tests still pass.
- Guardrails: no fixture sibling pipeline, no local `_mm256`/suffix spelling
  table in production code, no exact source-string matcher, no `frozen` or
  `tslgenold` runtime dependency.

## Out Of Scope

New lowering semantics; source repair; broad body expression parsing; matching
target-language operators; primitive-call rendering; dependency closure;
semantic vector runtime tests; generated test-source production; CLI workflow;
mask/generic/SVE/NEON/AVX512 build verification; target-feature or compiler
capability modeling beyond the accepted generated-project verifier.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m197_type_derived_intrinsic_suffix_translation.py tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py tslgen/tests/test_m247_selected_implementation_render_context.py tslgen/tests/test_m248_generic_selected_primitive_project_intrinsic_rendering.py tslgen/tests/test_m249_real_avx2_selected_primitive_build_verification.py tslgen/tests/test_m250_real_avx2_integer_modifier_lowering_build_verification.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: generic selected project pipeline only;
   already-lowered modifier facts flow through typed backend translation;
   no raw-string matcher, fixture sibling pipeline, or template semantic
   inference.
2. Evidence reviewer: selected fixture is real `tsldata`; suffix behavior,
   type spellings, headers, profiles, and target features come from accepted
   catalogs/models.
3. Test reviewer: integer matrix coverage, unsigned-to-signed suffix behavior,
   C++/Rust build parity, scalar/M249 regressions, determinism, and guardrails.
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
- do not start M251 inside M250.

## Final Report

Report:

1. Implementation summary.
2. How typed modifier lowering/translation reaches rendering.
3. C++/Rust generated output and build behavior.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
