# M246 Extension-Owned Default Intrin Compose Policy Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M245 as accepted.

This is an implementation task focused on default backend intrinsic compose
name policy. Use the executor-review loop:

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
tiny/regression-only and must not be extended for real vector work.

## Decision To Implement

Default `intrin_compose<NAME>(...)` naming policy belongs to
`tsldata/extensions/extension.tsl`.

Use this exact source shape:

```tsl
intrinsic_compose:
  prefix:
    cpp "_mm256_"
    rust "core::arch::x86_64::_mm256_"
  suffix:
    by_type:
      f32 "ps"
      f64 "pd"
      si8 "epi8"
      si16 "epi16"
      si32 "epi32"
      si64 "epi64"
      ui8 "epu8"
      ui16 "epu16"
      ui32 "epu32"
      ui64 "epu64"
```

Suffixes are concrete per `TypeTag`, not grouped by type group. Rust module
qualification stays in the backend-specific `prefix` value, for example
`core::arch::x86_64::_mm256_`.

Source-provided `intrin_compose` modifiers always override defaults. If the
source provides `prefix=...`, `infix=...`, or `suffix=...`, the backend must
use the translated source modifier for that name part and must not also apply
the extension default for the same part.

Missing extension/default policy/type suffix/backend prefix must produce
diagnostics. Do not guess backend intrinsic names.

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
- `tsldata/extensions/extension.tsl`
- `tsldata/primitives/arithmetic/fundamental.tsl`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/extension_catalog.py`
- `tslgen/src/tslgen/backends/intrinsic_invocations.py`
- `tslgen/src/tslgen/backends/intrinsic_modifiers.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py`
- `tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py`
- `tslgen/tests/test_m245_extension_register_type_spelling_boundary.py`

## Goal

Implement extension-owned default intrinsic compose naming:

```text
intrin_compose<BASE>(args)
  + selected backend
  + selected extension
  + selected type tag
  -> extension intrinsic_compose default prefix/suffix policy
  -> typed backend intrinsic invocation name parts
```

The immediate purpose is to make unqualified real forms such as
`intrin_compose<add>(left, right)` resolvable without hardcoded backend name
tables in Python or templates.

## Scope

Implement the smallest coherent typed slice:

- Add `intrinsic_compose` metadata blocks to `tsldata/extensions/extension.tsl`
  for extensions that need default compose policy for observed unmasked
  arithmetic forms, at minimum `sse`, `avx2`, `avx512`, and `neon`.
- Include concrete per-`TypeTag` suffix entries. Do not use wildcard suffixes
  or type-group suffix entries.
- Preserve extension inheritance where appropriate, so VL variants can inherit
  a parent policy unless they explicitly override it.
- Parse and promote the new metadata into typed extension catalog values.
  Use dataclasses/enums/NewTypes as appropriate; do not expose raw dictionaries
  past the parser/catalog boundary.
- Add a typed backend default compose-name policy/value consumed by intrinsic
  invocation assembly or a narrow adjacent backend translation boundary.
- Apply default prefix/suffix only when the source `intrin_compose` request
  does not provide that name part explicitly.
- Preserve explicit source modifier behavior from M195-M214. Explicit
  `prefix`, `infix`, and `suffix` always win over extension defaults.
- Keep suffix selection concrete by current selected `TypeTag`.
- Keep Rust full `core::arch::*` qualification in the extension-owned prefix
  metadata.
- Emit stable diagnostics for missing policy, missing backend prefix, missing
  type suffix, unknown extension, unsupported backend, and unsupported default
  policy shape.

## Expected Tests

Add focused tests, likely:

```text
tslgen/tests/test_m246_extension_default_intrin_compose_policy.py
```

Cover:

- Extension catalog parses default compose prefix/suffix metadata from
  `extension.tsl`.
- Inherited policy is visible for an inherited extension where applicable.
- `intrin_compose<add>(left, right)` assembles to representative C++ x86 names
  from extension policy, for example SSE `f32`, AVX2 `f32`, and AVX512
  integer.
- The same typed policy assembles representative Rust x86 names with full
  `core::arch::x86_64::...` prefix from `extension.tsl`.
- NEON assembles a representative name such as `vaddq_s32` or `vaddq_f32`
  from concrete per-type suffix policy.
- Source-provided explicit `prefix`/`suffix` overrides the extension default
  for the same part.
- Existing explicit modifier tests from M195-M214 remain compatible.
- Diagnostics cover missing policy, missing backend prefix, missing type
  suffix, unknown extension, unsupported backend, and malformed policy source.
- Guard tests ensure no local Python table contains register/intrinsic prefix
  or suffix spellings such as `_mm256_`, `core::arch::x86_64::_mm`, `epi32`,
  `vaddq_s32`, or `float32x4_t`.

## Out Of Scope

- Real vector/intrinsic generated-project rendering.
- Primitive selection, dependency closure, or broad candidate expansion.
- New TSIL keyword lowering or source parsing.
- Pairwise `emit_return + intrin_compose` handling.
- Mask, generic, SVE dependency-call rendering, or real test metadata.
- Target-language expression/operator parsing.
- Moving intrinsic-name decisions into templates.
- Extending `generated_primitive_pipeline.py`.
- Adding fixture-shaped pipelines for `sse`, `avx2`, `neon`, `add`, type
  tags, signatures, or exact body forms.
- Runtime dependencies on `frozen` or `tslgenold`.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m195_literal_intrinsic_modifier_translation.py tslgen/tests/test_m198_intrinsic_prefix_modifier_translation.py tslgen/tests/test_m200_current_type_intrinsic_suffix_translation.py tslgen/tests/test_m213_backend_intrinsic_invocation_assembly.py tslgen/tests/test_m214_cpp_intrinsic_invocation_call_rendering.py tslgen/tests/test_m219_rust_intrinsic_invocation_call_rendering.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py tslgen/tests/test_m246_extension_default_intrin_compose_policy.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: default compose policy is extension-owned
   typed metadata, explicit source modifiers override defaults, and no broad
   backend dispatcher or renderer-side semantic inference was introduced.
2. Evidence reviewer: policy entries reflect real `extension.tsl` and
   observed `fundamental.tsl` `intrin_compose` needs; no spellings come from
   `frozen`, `tslgenold`, Python tables, or templates.
3. Test reviewer: parsing, inheritance, C++/Rust parity, explicit override,
   diagnostics, and guardrails are covered.
4. Documentation reviewer: roadmap/state/spec/decision consistency and next
   prompt accuracy.
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
- do not start M247 inside M246.

## Final Report

Report:

1. Implementation summary.
2. Extension compose policy coverage.
3. Explicit override behavior.
4. Review/audit verdicts.
5. Validation commands and exact results.
6. Any follow-ups.
7. Next active prompt path.
