# M244 Real Scalar Emit-Return Matrix Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M243 as accepted.

This is an implementation task focused on backend/rendering integration, not
lowering and not expression parsing. Use the executor-review loop:

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
Milestone 243: Real Scalar Emit-Return Function Rendering
```

M243 added `tslgen.pipeline.real_scalar_pipeline`, a narrow real-corpus bridge
that parses real `tsldata/primitives/arithmetic/fundamental.tsl` through
`OuterTslParser`, selects the unmasked scalar `add` / `si32` implementation at
selector path `("scalar", "arith")`, accepts only an exact single
`emit_return(PAYLOAD);` body, carries raw payload text without parsing `+`,
translates scalar type spelling through backend metadata, renders through
existing `v:=(v,v)` function-shape and primitive-profile templates, composes
the generated-project skeleton, writes through `ArtifactWriter`, and verifies
both generated C++ and Rust scalar projects.

M243 explicitly keeps the tiny M224 path as regression only. The real path
must not use `TslParser`, tiny `body add(left, right)` evidence, local
scalar/operator spelling tables, `LoweredBinaryOperationExpression`,
`frozen`, or `tslgenold`.

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
- `docs/agent/runs/m243-real-scalar-emit-return-function-rendering-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/types/types_rust.tsl`
- `tslgen/src/tslgen/pipeline/real_scalar_pipeline.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/rendering/primitive_function_shapes.py`
- `tslgen/src/tslgen/rendering/primitive_profile_artifacts.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Broaden the accepted real-corpus scalar bridge from one selected real
function to an explicit deterministic matrix of real scalar single-return
functions rendered into one generated C++ and Rust scalar project:

```text
real fundamental.tsl source
-> OuterTslParser primitive/body envelopes
-> explicit selected matrix of real scalar exact emit_return bodies
-> backend metadata type spelling per selected concrete type
-> existing v:=(v,v) function-shape templates
-> existing primitive-profile templates containing multiple definitions
-> generated project skeleton composition
-> ArtifactWriter
-> C++ and Rust build verification
```

The starting matrix is:

- primitives: unmasked `add` and unmasked `sub`;
- selector path: `("scalar", "arith")`;
- signature: `v:=(v,v)`;
- parameter names: `left`, `right`;
- type tags: `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`,
  `f32`, and `f64`.

This should generate deterministic function definitions such as
`add_scalar_si32` and `sub_scalar_si32` in both C++ and Rust scalar profile
artifacts.

## Scope

Implement the smallest useful M243 extension that proves:

- multiple explicit real scalar selected entries can be rendered into the same
  C++ and Rust scalar profile artifacts;
- function names, primitive render records, and profile artifact content are
  deterministic;
- duplicate selected function names or duplicate render records are diagnosed
  before artifact composition;
- each selected primitive body still passes the exact single
  `emit_return(PAYLOAD);` M243 boundary;
- raw payload text stays raw and is placed into existing templates without
  parsing `+`, `-`, or any other operator;
- all scalar type spellings come from the accepted backend metadata
  translation boundary;
- the generated project is written manifest-clean and compile/test verified
  for C++ and Rust.

You may refactor `real_scalar_pipeline.py` if needed, but keep it cohesive and
avoid creating a second scalar renderer. Preserve the current M243 single-case
API as a convenience wrapper unless there is a narrowly justified reason to
adjust it with tests.

## Guardrails

- Do not add new lowering semantics.
- Do not parse target-language expressions, statements, operators,
  assignments, indexing, braces, or semicolons.
- Do not infer `add` or `sub` semantics from the payload. The payload is raw
  source text accepted by the exact `emit_return` boundary.
- Do not introduce wildcard expansion, broad real-corpus catalog selection,
  primitive-call dependency closure, or topological primitive sorting.
- Do not use real primitive `tests:` metadata.
- Do not broaden into vector/intrinsic/mask/generic bodies.
- Do not add local scalar type spelling tables or operator spelling tables.
- Do not move backend semantic decisions into templates.
- Do not add production C++/Rust function/profile source as large raw Python
  strings.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py
```

Cover:

- the explicit add/sub x ten-type selected matrix from real
  `fundamental.tsl`;
- deterministic C++ and Rust artifact output containing all selected function
  names once;
- backend metadata type spellings for representative signed, unsigned, and
  floating types in both languages;
- raw payload preservation for both `left + right` and `left - right`;
- manifest-clean write and C++/Rust build verification of the generated scalar
  project;
- duplicate selected function-name diagnostics;
- unsupported selected matrix entry diagnostics, for example a real selected
  body that is not an exact single `emit_return(PAYLOAD);`;
- guard tests that the matrix path still does not use `TslParser`, tiny
  `body add` evidence, local scalar/operator spelling tables,
  `LoweredBinaryOperationExpression`, `frozen`, or `tslgenold`.

Existing M224/M227/M241/M242/M243 tests must remain compatible.

## Out Of Scope

- Real vector or intrinsic profile rendering.
- Masked scalar bodies.
- Generic fallback body rendering.
- Primitive-call dependency closure.
- Real primitive `tests:` metadata rendering.
- Support-helper availability or `details::*` semantics.
- Rust unsafe policy for intrinsics.
- Host CPU autodetection or compiler capability modeling.
- New CLI/API generation command.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py tslgen/tests/test_m244_real_scalar_emit_return_matrix_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: the matrix path reuses the M243 bridge,
   keeps templates presentation-only, avoids new lowering/operator parsing,
   and does not grow broad catalog/dependency machinery.
2. Evidence reviewer: every positive selected entry comes from real
   `fundamental.tsl` scalar body evidence with source provenance.
3. Test reviewer: matrix coverage, C++/Rust parity, determinism, duplicate
   diagnostics, unsupported-entry diagnostics, and guardrails are covered.
4. Documentation reviewer: roadmap/state/spec consistency and follow-ups are
   accurate.
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
- do not start M245 inside M244.

## Final Report

Report:

1. Implementation summary.
2. Real scalar matrix rendered.
3. Generated artifact and build verification summary.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
