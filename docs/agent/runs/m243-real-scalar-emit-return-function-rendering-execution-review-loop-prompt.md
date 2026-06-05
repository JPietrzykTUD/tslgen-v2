# M243 Real Scalar Emit-Return Function Rendering Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M242 as accepted.

This is an implementation task focused on backend/rendering integration, not
another lowering milestone and not a new scalar renderer. Use the
executor-review loop:

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
Milestone 242: Real Corpus Lowering Completion Gate
```

M242 proved against all current `tsldata/primitives/**/*.tsl` files that the
observed generation-relevant TSIL/source-island surface is covered by accepted
lowering, handoff, or diagnostic boundaries. It considered 30 primitive files,
30 parsed documents, 140 primitive declarations, and 1331 implementation body
envelopes, including both `tsil` and `tsl` implementation payloads. It found
no unsupported generation-relevant lowering family.

The next step must therefore make backend/rendering progress by connecting
the already accepted rendering stack to a real `.tsl` primitive. Do not add
another lowering-confidence milestone unless implementation discovers a new
concrete generation-relevant TSIL family that M242 missed.

The following pieces are already accepted and must be reused instead of
rebuilt:

- generated-project skeleton rendering, `ArtifactWriter`, and `BuildVerifier`;
- exact `v:=(v,v)` C++ and Rust function-shape templates;
- primitive profile artifact templates;
- typed backend/type-spelling translation boundaries where they already exist;
- the tiny M224 generated-project path as regression evidence only.

M243 closes the gap that remains after those pieces: the current positive
generated-project path still comes from a tiny synthetic fixture and local
bridge logic, not from `tsldata/primitives/arithmetic/fundamental.tsl`
through the accepted real-corpus parser/body/lowering path.

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
- `docs/redesign/lowering-completeness-audit.md`
- `docs/redesign/missing-lowering-inventory.md`
- `docs/agent/runs/m242-real-corpus-lowering-completion-gate-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/detail/types.tsl`
- `tsldata/detail/lang/types/types_cpp.tsl`
- `tsldata/detail/lang/types/types_rust.tsl`
- `tslgen/src/tslgen/syntax/outer_parser.py`
- `tslgen/src/tslgen/syntax/outer_ast.py`
- `tslgen/src/tslgen/lowering/source_body_fragments.py`
- `tslgen/src/tslgen/lowering/emit_return_regions.py`
- `tslgen/src/tslgen/rendering/primitive_function_shapes.py`
- `tslgen/src/tslgen/rendering/primitive_profile_artifacts.py`
- `tslgen/src/tslgen/rendering/generated_project.py`
- `tslgen/src/tslgen/rendering/generated_primitive_project.py`
- `tslgen/src/tslgen/pipeline/generated_primitive_pipeline.py`
- `tslgen/src/tslgen/pipeline/backend_metadata.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/pipeline/build_verifier.py`
- `tslgen/src/tslgen/io/artifact_writer.py`
- `tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py`
- `tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py`
- `tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py`
- `tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Replace or bypass the tiny synthetic positive bridge with the smallest
real-corpus integration path that renders and compiles a generated C++ and
Rust scalar project from a real `tsldata` primitive implementation body:

```text
real tsldata primitive file
-> accepted OuterTslParser primitive/body envelopes
-> selected real scalar implementation with exact single emit_return(PAYLOAD);
-> accepted recursive source-body lowering
-> already-decided typed backend/render values
-> existing C++/Rust function-shape templates
-> existing primitive profile artifact templates
-> generated project skeleton composition
-> ArtifactWriter
-> C++ and Rust build verification
```

The selected starting case is the real scalar `add` / `si32` slice from
`tsldata/primitives/arithmetic/fundamental.tsl`, whose scalar implementation
body is:

```text
emit_return(left + right);
```

The payload `left + right` is raw source text carried by the accepted
`emit_return` body boundary. M243 must not parse `+`, model target-language
operators, or infer semantics from the payload. It only places already-accepted
body payload text into already template-backed C++ and Rust function shapes.

This milestone is successful only if the new positive path is driven by real
`tsldata` evidence. Reusing existing renderers/templates/writer/verifier is
the intended outcome; adding a parallel scalar rendering stack is a failure.

## Scope

Implement the smallest useful real-corpus integration bridge that proves:

- A real primitive declaration/body can be read from
  `tsldata/primitives/arithmetic/fundamental.tsl` through `OuterTslParser`.
- The implementation selector path can be matched narrowly for the selected
  real scalar implementation, such as `("scalar", "arith")`, and then tied to
  an explicit selected concrete `TypeTag` such as `si32`.
- The selected body must be an exact single accepted `emit_return(PAYLOAD);`
  region. Nearby multiline/multiple-statement bodies should be diagnostics or
  unsupported for M243, not repaired.
- The emitted function shape is selected from the already parsed primitive
  signature, currently `v:=(v,v)`.
- C++ and Rust scalar type spellings come from accepted typed backend metadata
  translation where possible. Do not add new local scalar spelling tables in
  the generated pipeline.
- The real-corpus positive path does not depend on `_SCALAR_TYPE_SPELLINGS`,
  `_BINARY_OPERATION_SPELLINGS`, `LoweredBinaryOperationExpression`, or any
  tiny-parser-only lowering/rendering shortcut from
  `generated_primitive_pipeline.py`. Existing tiny-path code may remain only
  to keep M224 regression tests passing.
- Function and profile artifacts use existing supplementary templates. Do not
  put whole C++ or Rust function/profile source strings into production Python.
- The generated scalar project composes with the existing project skeleton,
  writes through `ArtifactWriter`, and verifies through the existing
  `BuildVerifier` for C++ and Rust.
- C++ and Rust remain in parity for the selected real scalar case.

If the implementation can safely broaden beyond `add` within the same
boundary, it may include additional real scalar single-`emit_return` bodies
with the same signature/function-shape and backend type-spelling support.
Do not broaden into vector/intrinsic/mask/generic bodies in M243.

## Guardrails

- Do not implement new lowering semantics.
- Do not parse target-language expressions, statements, operators,
  assignments, indexing, braces, or semicolons.
- Do not introduce a second scalar renderer or copy/paste the tiny M224 bridge
  into a real-corpus module.
- Do not introduce pairwise keyword-combination lowering.
- Do not use the old tiny `body add(left, right)` fixture as the evidence
  source for the new real-corpus path. Existing tests may remain for
  regression, but M243's new positive path must use real `tsldata`.
- Do not implement broad real-corpus catalog selection, wildcard expansion,
  dependency closure, topological primitive sorting, or generated test metadata
  planning.
- Do not assemble intrinsic names or translate intrinsic modifiers beyond
  already accepted typed backend handoff/rendering behavior.
- Do not add backend semantic decisions to templates. Templates may format
  only already-decided presentation fields.
- Do not add C++/Rust code as large raw production strings. Production
  language presentation should come from supplementary templates or already
  rendered typed values.
- Do not make `frozen/` or `tslgenold/` runtime dependencies.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py
```

Cover:

- Real `tsldata/primitives/arithmetic/fundamental.tsl` parsing through
  `OuterTslParser` and selection of the real scalar `add` implementation
  body.
- Exact single `emit_return(PAYLOAD);` body extraction through accepted
  source-body lowering, with `left + right` preserved as raw payload text.
- C++ and Rust function definitions rendered through the accepted
  function-shape templates for the selected real scalar function.
- C++ and Rust primitive profile artifacts rendered through the accepted
  primitive-profile templates.
- Generated project skeleton composition, manifest-clean write, and C++/Rust
  build verification for the selected scalar profile.
- Deterministic artifact digest output across repeated renders.
- Negative diagnostics for unsupported real bodies, such as a selected body
  with multiple top-level statements or no exact single `emit_return`.
- Guard tests that the new path does not call `TslParser`/tiny `body add`
  evidence, does not import `frozen`/`tslgenold`, and does not add new local
  scalar type or operator spelling tables for the real path.
- Guard tests that the real path does not use the tiny-only
  `LoweredBinaryOperationExpression` rendering shortcut; the accepted
  `emit_return` payload text is carried as body payload text unless nested
  TSIL keyword islands were already accepted and rendered by existing token
  renderers.

Keep tests focused on the real scalar single-return rendering bridge. Existing
M224/M227/M241/M242 tests should remain compatible.

## Out Of Scope

- Real vector or intrinsic profile rendering.
- Real mask/generic/generation-control body rendering.
- Primitive-call dependency closure.
- Real primitive `tests:` metadata rendering.
- Support-helper availability or `details::*` semantics.
- Rust unsafe policy for intrinsics.
- Host CPU autodetection or compiler capability modeling.
- New CLI/API generation command.
- Broad replacement of the older tiny pipeline unless it is a small cleanup
  forced by this bridge.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m224_parsed_tiny_tsl_to_generated_project.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m241_primitive_profile_artifact_presentation_boundary.py tslgen/tests/test_m242_real_corpus_lowering_completion_gate.py tslgen/tests/test_m243_real_scalar_emit_return_function_rendering.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: the bridge consumes real parser/body
   facts and already-decided render values, keeps templates presentation-only,
   avoids new lowering/operator parsing, and does not grow a broad catalog or
   dependency system.
2. Evidence reviewer: the positive path uses real `tsldata` scalar primitive
   evidence and preserves source provenance; synthetic tiny `body add` data is
   not the evidence source for M243.
3. Test reviewer: C++/Rust parity, exact single-return extraction, generated
   project write/build verification, determinism, and negative diagnostics are
   adequately covered.
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
- do not start M244 inside M243.

## Final Report

Report:

1. Implementation summary.
2. Real scalar corpus slice rendered.
3. Generated artifact and build verification summary.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
