# M239 Backend Intrinsic Body-Token Render Bridge Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M238 as accepted.

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
Milestone 238: Generated Project Source Template Boundary
```

M238 moved generated-project source skeletons into supplementary templates and
partials, preserving the existing scalar/profile generated project
verification behavior. The renderer/template boundary is now clean enough to
resume the small backend intrinsic bridge that M237 identified as the next
backend-output prerequisite.

Do not reopen lowering in M239. The point is to consume already-lowered typed
intrinsic handoff/body-token values and prove they can feed the accepted
rendering path.

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
- `docs/agent/runs/m237-backend-generated-output-resumption-planning-prompt.md`
- `docs/agent/runs/m238-generated-project-source-template-boundary-execution-review-loop-prompt.md`
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/backends/body_token_contract.py`
- `tslgen/src/tslgen/backends/cpp/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/rust/intrinsic_calls.py`
- `tslgen/src/tslgen/backends/cpp/body_tokens.py`
- `tslgen/src/tslgen/backends/rust/body_tokens.py`
- `tslgen/src/tslgen/rendering/primitive_function_shapes.py`
- `tslgen/src/tslgen/rendering/primitive_render_plan.py`
- `tslgen/src/tslgen/rendering/primitive_templates.py`
- `tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py`
- `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`
- `tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py`
- `tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py`
- `tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py`
- `tslgen/tests/test_m238_generated_project_source_template_boundary.py`
- `supplementary/templates/cpp/`
- `supplementary/templates/rust/`

## Goal

Implement the smallest bridge from accepted backend intrinsic body-token
rendering to accepted primitive profile artifact rendering:

```text
already-lowered typed intrinsic handoff/body token
-> existing backend intrinsic invocation/call renderer
-> rendered body text
-> exact v:=(v,v) function-shape templates
-> existing primitive profile templates
-> deterministic C++ and Rust primitive profile artifacts
```

This is a backend/rendering bridge over existing typed facts, not a new
lowering feature.

## Scope

Add a focused adapter or helper, with tests, that proves:

- one explicit already-lowered/typed C++ intrinsic invocation handoff can
  produce a rendered C++ body-token/body text value;
- the Rust parity handoff can produce a rendered Rust body-token/body text
  value through the existing Rust intrinsic call renderer;
- the rendered body text feeds the accepted exact `v:=(v,v)` function-shape
  template boundary;
- the resulting function definitions feed the accepted primitive profile
  templates for C++ and Rust;
- artifact output is deterministic and profile-scoped;
- unsupported/missing typed intrinsic handoff inputs diagnose before profile
  artifact rendering.

Use a synthetic already-lowered fixture if that keeps the slice clean. The
fixture should be typed enough to exercise the existing intrinsic invocation,
call-rendering, body-token substitution, function-shape, and primitive
template boundaries without parsing `.tsl` or selecting from the real corpus.

## Guardrails

- Do not change lowering, recursive TSIL keyword handling, primitive-call
  semantics, parser/catalog/selector code, or source-body scanning.
- Do not implement full `fundamental.tsl`/`add`/`avx2` corpus selection.
- Do not compile-test real intrinsic artifacts in M239.
- Do not add C++/Rust source skeleton strings to Python.
- Do not hide intrinsic/type/feature semantics in templates.
- Do not parse target-language expressions, statements, returns, assignments,
  braces, semicolons, or operators in renderers.
- Do not introduce a broad dispatcher, registry, worklist, or new lowering IR
  family. Any new helper must have this concrete bridge as its owner.
- Do not add runtime dependencies on `frozen/` or `tslgenold`.
- Keep C++ and Rust in parity.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py
```

Cover:

- C++ already-lowered intrinsic handoff to rendered body text to
  `v:=(v,v)` function definition to primitive profile artifact.
- Rust parity through the same boundary.
- Deterministic repeated artifact output.
- Unsupported/missing typed handoff diagnostic before rendering artifacts.
- No parser/lowering/catalog access is needed by the bridge.
- Existing M213/M214/M219/M220/M227/M238 tests continue to pass.

## Out Of Scope

- Full source/corpus path from `tsldata/primitives/arithmetic/fundamental.tsl`.
- Wildcard type expansion or selected primitive context construction.
- Dependency closure/topological primitive planning.
- Vector/register type spelling expansion beyond already-provided render
  values.
- Rust architecture module selection beyond existing renderer inputs.
- Generated project writing or build verification for real intrinsic output.
- New supplementary generated-project templates.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py tslgen/tests/test_m227_vv_function_shape_template_render_boundary.py tslgen/tests/test_m238_generated_project_source_template_boundary.py tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: the bridge consumes already-lowered typed
   values, does not reopen lowering/parser/catalog selection, and keeps
   templates presentation-only.
2. Evidence reviewer: M239 does not implement the full real x86 fixture and
   stays compatible with M213/M214/M219/M220/M227/M238 behavior.
3. Test reviewer: C++/Rust parity, deterministic output, diagnostic coverage,
   and no source/lowering access are covered.
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
- do not start the next milestone inside M239.

## Final Report

Report:

1. Implementation summary.
2. Review/audit verdicts.
3. Validation commands and exact results.
4. Any follow-ups.
5. Next active prompt path.
