# M246 Real Vector Intrinsic Rendering Readiness Planning Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M245 as accepted.

This is a planning task. Do not implement production code. The purpose is to
select the next executable real vector/intrinsic rendering slice without
assuming unsupported `intrin_compose` semantics or creating another
fixture-shaped pipeline.

Use the subagent workflow for read-only planning:

```text
orchestrator/planner
-> read-only evidence, lowering/boundary, backend/rendering, test, and
   documentation auditors
-> final selected M247 executor prompt
```

The orchestrator owns final state and next-prompt updates.

## Accepted State

Accepted through:

```text
Milestone 245: Extension Register Type Spelling Boundary
```

M245 taught `tslgen.backends.type_spelling` to translate already-lowered
`CurrentVector(extension, type_tag)` and
`LoweredVectorMemberType(member="register", extension, type_tag)` values
through `Extension.resolved_vector_register_types` from the typed extension
catalog. Register spellings for C++ and Rust now come from
`tsldata/extensions/extension.tsl`, not Python spelling tables or templates.

M244.5 made the generic `primitive_project_pipeline.py` the real selected
primitive project bridge. The M224 `generated_primitive_pipeline.py` remains
tiny/regression-only and should not be extended for real vector work.

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
- `docs/agent/runs/m245-extension-register-type-spelling-boundary-execution-review-loop-prompt.md`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tsldata/extensions/extension.tsl`
- `tslgen/src/tslgen/pipeline/primitive_project_pipeline.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/rendering/intrinsic_body_token_bridge.py`
- `tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py`
- `tslgen/tests/test_m240_synthetic_intrinsic_generated_project_verification.py`
- `tslgen/tests/test_m245_extension_register_type_spelling_boundary.py`

## Goal

Plan the first safe real vector/intrinsic generated-project executor slice
after M245.

The plan must answer:

- which real unmasked vector `add`/`sub` implementation bodies are plausible
  first candidates;
- whether each candidate can already pass through accepted recursive TSIL
  keyword lowering and backend intrinsic handoff boundaries;
- which backend translation/rendering boundaries are already sufficient;
- which exact missing typed policy, if any, blocks correct backend intrinsic
  name assembly;
- what the next M247 executor should implement in one coherent slice.

## Planning Scope

Use real `tsldata/primitives/arithmetic/fundamental.tsl` as the source
evidence. At minimum, inspect these unmasked body families:

- `sse` integer `?i?` forms with explicit
  `suffix=value<backend>(intrin::suffix(...))`;
- `sse` floating forms such as `f32`/`f64` with
  `intrin_compose<add>(...)`;
- `avx2` integer and floating forms;
- `avx512` integer and floating forms;
- `neon` arithmetic forms such as `intrin_compose<vaddq>(...)`;
- `sve` forms only as evidence unless their `call<primitive=...>` dependency
  makes them unsuitable for the first executor.

For each candidate family, classify:

- selected primitive, extension, type selector/type tag, and parameters;
- body shape and whether it is single-line or multiline;
- required already-lowered type values, especially current vector/register
  result and parameter types;
- required intrinsic handoff kind and modifier fields;
- whether accepted modifier translation can produce all required name parts;
- whether intrinsic invocation assembly would currently produce the correct
  backend intrinsic name;
- whether C++ and Rust can be kept in parity for the selected slice;
- whether generated C++/Rust build verification is feasible without new
  runtime or host assumptions.

## Guardrails

- Do not implement production code in M246.
- Do not invent backend intrinsic spellings in the plan.
- Do not assume `intrin_compose<add>(...)` automatically means
  `_mm_add_ps`, `_mm256_add_ps`, `vaddq_*`, or any other backend name unless
  an accepted typed policy already provides that behavior.
- Do not add a pairwise special case such as
  `emit_return + intrin_compose`. The next executor must use recursive body
  token lowering and existing keyword boundaries compositionally.
- Do not broaden primitive selection, dependency closure, mask rendering,
  generic runtime-sized register policies, test metadata rendering, source
  repair, or target-language parsing.
- Do not extend `generated_primitive_pipeline.py` for real vector work.
- Do not add fixture-shaped pipelines for `sse`, `avx2`, `neon`, `add`, a
  type tag, or an exact body form.
- Do not make `frozen` or `tslgenold` runtime dependencies.

## Expected Output

Update the roadmap/state with a concise planning result and create the next
M247 execution-review prompt. The selected M247 prompt should be as broad as
is safely coherent, but it must name exact accepted source forms, typed inputs,
diagnostics, and out-of-scope behavior.

If the evidence shows that real vector rendering is blocked by a missing typed
backend compose-name policy, M247 should implement that policy first rather
than forcing a generated-project slice.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Read-Only Subagents

After the planning draft, run read-only subagents:

1. Evidence auditor: verifies the real `fundamental.tsl` body inventory and
   candidate classification.
2. Lowering/boundary auditor: verifies the plan uses recursive keyword
   lowering compositionally and does not create pairwise combinations.
3. Backend/rendering auditor: verifies the plan identifies existing and
   missing intrinsic compose-name/type-spelling/rendering boundaries.
4. Test auditor: verifies the proposed M247 validation and tests are sufficient
   without relying on host CPU features beyond build-tool assumptions already
   accepted.
5. Documentation auditor: verifies roadmap/state/prompt consistency.

If any auditor returns `Needs Revision`, revise only the planning docs/prompt
needed to fix the blocking issue and rerun the focused audit. If any returns
`Return To Planner` or `Reject`, record the stop condition or replacement
planner prompt.

## Completion Rules

Before finishing:

- update `docs/redesign/implementation-roadmap.md` with the M246 planning
  result;
- update `docs/agent/current-redesign-state.md`;
- create the next concrete M247 prompt under `docs/agent/runs/`;
- do not implement M247 inside M246.

## Final Report

Report:

1. Planning conclusion.
2. Selected M247 direction and why it is safe.
3. Review/audit verdicts.
4. Validation commands and exact results.
5. Next active prompt path.
