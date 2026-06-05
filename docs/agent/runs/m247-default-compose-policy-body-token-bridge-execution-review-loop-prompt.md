# M247 Default Compose Policy Body-Token Bridge Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M246 as accepted.

This is an implementation task focused on consuming extension-owned default
`intrin_compose` policy in the existing intrinsic body-token bridge. Use the
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
Milestone 246: Extension-Owned Default Intrin Compose Policy
```

M246 added typed `IntrinsicComposePolicy` metadata to the extension catalog,
populated extension-owned default prefix/suffix policy for representative x86
and NEON extensions, and made backend intrinsic invocation assembly consume an
optional already-resolved `BackendIntrinsicComposeDefaultPolicy`. Explicit
source modifiers still override defaults.

## Goal

Wire M246's typed default compose policy into the intrinsic body-token bridge
so any already-lowered composed intrinsic request can use selected
extension/type defaults when a prefix or suffix is absent:

```text
BackendIntrinsicComposeHandoffRequest
  + selected backend
  + selected extension
  + selected type tag
  + ExtensionCatalog.intrinsic_compose_policy
  -> assembled intrinsic invocation
  -> rendered C++ or Rust body token text
```

This should make the bridge ready for real vector project rendering without
creating pairwise source-shape combinations such as
`emit_return + intrin_compose`.

## Scope

Implement the smallest coherent bridge slice:

- Extend `IntrinsicBodyTokenProfileRenderContext` or a narrow adjacent typed
  context with selected `ExtensionName`, selected `TypeTag`, and
  `ExtensionCatalog` data needed to resolve default compose policy.
- For every `BackendIntrinsicComposeHandoffRequest` segment, resolve and pass
  a `BackendIntrinsicComposeDefaultPolicy` to
  `assemble_backend_intrinsic_invocation(...)` only when the request is missing
  a prefix and/or suffix default that assembly may need.
- Preserve explicit source modifier behavior. If the source has a translated
  `prefix` or `suffix`, that part must override the extension default. If the
  source has both prefix and suffix, the bridge must not require extension
  default policy only to render that request.
- Keep direct `intrin<...>(...)` requests, immediate metadata, argument
  payloads, and body-token substitution behavior compatible with M214, M219,
  M220, M239, and M246.
- Add a typed Rust call-rendering qualification path so names assembled from
  full `core::arch::*` prefixes in extension metadata are rendered without
  double qualification. Preserve the existing unqualified Rust renderer
  behavior for direct or explicitly-unqualified intrinsic names.
- Do not infer Rust qualification by repairing source text or by moving
  semantic decisions into templates. If a small typed flag/value is needed,
  keep it attached to backend invocation/render context and cover it with
  tests.
- Emit stable diagnostics for missing extension catalog/context, missing
  default policy, missing backend prefix, missing type suffix, unknown
  extension, unsupported backend, and Rust qualification misuse.

## Expected Tests

Add or update focused tests, likely in:

```text
tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py
tslgen/tests/test_m247_default_compose_policy_body_token_bridge.py
```

Cover:

- C++ bridge rendering of a no-modifier composed request such as
  `intrin_compose<add>(left, right)` for selected `avx2/f32` using M246
  extension policy.
- C++ bridge rendering where an explicit source suffix overrides the default
  suffix while the default prefix still applies.
- Rust bridge rendering of a no-modifier composed request for selected
  `avx2/f32` or `neon/si32` without producing doubled
  `core::arch::...::core::arch::...`.
- Existing M219 unqualified Rust call-rendering behavior remains compatible.
- No default policy is required for a composed request whose translated source
  modifiers already provide both prefix and suffix.
- Diagnostics for missing context/catalog/policy/type suffix are stable and
  sourced.
- Guardrails: no backend intrinsic prefix/suffix spelling table appears in
  Python bridge code or templates, and no pairwise
  `emit_return + intrin_compose` special-case code is introduced.

## Out Of Scope

- Generated-project integration through `primitive_project_pipeline.py`.
- Vector/register type spelling in function signatures.
- Build verification of real AVX/NEON generated projects.
- Primitive selection, dependency closure, or candidate expansion.
- New TSIL keyword lowering or source parsing.
- Pairwise parent/child keyword special cases.
- Target-language expression/operator parsing.
- Moving intrinsic-name decisions into templates.
- Extending `generated_primitive_pipeline.py`.
- Runtime dependencies on `frozen` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py tslgen/tests/test_m220_shared_intrinsic_body_token_substitution_parity.py tslgen/tests/test_m239_backend_intrinsic_body_token_render_bridge.py tslgen/tests/test_m246_extension_default_intrin_compose_policy.py tslgen/tests/test_m247_default_compose_policy_body_token_bridge.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: bridge consumes typed extension policy and
   does not add pairwise source-shape special cases, fixture pipelines, or
   renderer/template semantic inference.
2. Evidence reviewer: selected examples reflect real `extension.tsl` policy
   and observed `intrin_compose` source needs; no spellings come from
   `frozen`, `tslgenold`, Python tables, or templates.
3. Test reviewer: C++/Rust parity, explicit overrides, no-default-needed case,
   diagnostics, and guardrails are covered.
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
- do not start M248 inside M247.

## Final Report

Report:

1. Implementation summary.
2. Default-policy bridge behavior.
3. Rust qualification behavior.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
