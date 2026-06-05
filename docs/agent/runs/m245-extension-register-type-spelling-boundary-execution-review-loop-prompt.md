# M245 Extension Register Type Spelling Boundary Execution Review Loop Prompt

Execute this prompt only when `docs/agent/current-redesign-state.md` points
here and records M244.5 as accepted.

This is an implementation task focused on backend type translation for
already-lowered vector/register type values. It is not a new lowering task and
not real vector/intrinsic rendering. Use the executor-review loop:

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
Milestone 244.5: Real Primitive Project Pipeline Consolidation
```

M244 added an explicit real scalar selected matrix on top of the M243 bridge:
real unmasked `add` and `sub` from
`tsldata/primitives/arithmetic/fundamental.tsl`, selector path
`("scalar", "arith")`, signature `v:=(v,v)`, parameters `left`/`right`, and
type tags `si8`, `si16`, `si32`, `si64`, `ui8`, `ui16`, `ui32`, `ui64`,
`f32`, and `f64`. It renders 20 deterministic C++ and Rust scalar profile
functions, writes the generated project manifest-clean, and verifies both
generated scalar projects. Payload text remains raw and operators are not
parsed.

The next real vector/intrinsic rendering slice needs vector register type
spellings. Those spellings are already source-owned metadata in
`tsldata/extensions/extension.tsl`, not values to hardcode in Python and not
template-side semantic decisions.

M244.5 consolidated the real primitive project pipeline ownership so M245 must
extend the generic real selected primitive project path, not the retired
fixture-shaped `real_scalar_pipeline.py` path.

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
- `docs/agent/runs/m244-real-scalar-emit-return-matrix-rendering-execution-review-loop-prompt.md`
- `tsldata/extensions/extension.tsl`
- `tsldata/detail/types.tsl`
- `tslgen/src/tslgen/domain/catalog.py`
- `tslgen/src/tslgen/pipeline/extension_catalog.py`
- `tslgen/src/tslgen/pipeline/catalog_builder.py`
- `tslgen/src/tslgen/backends/type_spelling.py`
- `tslgen/src/tslgen/lowering/model.py`
- `tslgen/tests/test_m143_1_extension_catalog.py`
- `tslgen/tests/test_m192_backend_type_spelling_translation.py`

## Goal

Teach the backend type-spelling boundary to translate already-lowered
current-vector/register type requests through the typed extension catalog:

```text
Lowered type value
  -> explicit backend type-spelling request
  -> extension catalog resolved vector register metadata
  -> typed backend type spelling result
```

The immediate purpose is to let the next real vector/intrinsic generated
project render function signatures and result types from `extension.tsl`
metadata, for example C++ `__m256` and Rust
`core::arch::x86_64::__m256`, without embedding those spellings in Python
backend logic or templates.

## Scope

Implement the smallest useful extension of the M192 type-spelling boundary:

- support `CurrentVector(extension=ExtensionName(...), type_tag=TypeTag(...))`;
- support `LoweredVectorMemberType(member="register", extension=..., type_tag=...)`;
- resolve C++ and Rust spellings only from
  `Extension.resolved_vector_register_types`;
- preserve the existing M192 scalar identity and `LoweredSizeType` behavior;
- preserve a convenient existing M192 public API, using a small typed context
  or optional catalog parameter only if needed;
- include source/request provenance in successful results;
- emit stable diagnostics for missing extension catalog metadata, unknown
  extension, unsupported vector member, unsupported backend, and missing
  register spelling;
- cover all fixed resolved vector register entries currently present in
  `tsldata/extensions/extension.tsl` for C++ and Rust, with representative
  assertions for x86 and ARM metadata.

Keep this as a typed backend translation boundary. It may consume already
lowered `CurrentVector` / `LoweredVectorMemberType` values, but it must not
parse raw `type<backend>(...)` text and must not add new lowering semantics.

## Guardrails

- Do not hardcode register spelling maps such as `avx2/f32 -> __m256` in
  Python.
- Do not move vector type selection or backend type spelling decisions into
  templates.
- Do not render real vector/intrinsic functions or generated projects in M245.
- Do not add mask or integral-mask type spelling in M245.
- Do not implement generic/runtime-sized register policies.
- Do not broaden primitive selection, dependency closure, or profile
  selection.
- Do not parse target-language expressions, operators, statements, or TSIL
  source text.
- Do not introduce runtime dependencies on `frozen` or `tslgenold`.
- Do not turn the type-spelling translator into a broad backend semantic
  dispatcher; keep the added responsibility to vector register type spelling.

## Expected Tests

Add focused tests, likely in:

```text
tslgen/tests/test_m245_extension_register_type_spelling_boundary.py
```

Cover:

- C++ and Rust spelling for `CurrentVector(avx2, f32)` and
  `CurrentVector(avx2, f64)`;
- C++ and Rust spelling for `LoweredVectorMemberType("register", sse, si32)`;
- representative ARM/NEON register spelling if present in the resolved
  extension metadata;
- a corpus-style assertion that every resolved vector register type entry in
  `extension.tsl` can be translated for its declared backend;
- M192 scalar and size-type tests remain compatible;
- diagnostics for missing extension catalog metadata, unknown extension,
  unsupported vector member such as `"mask"`, unsupported backend, and missing
  register spelling;
- guard tests that no local register spelling table, template semantic
  decision, `frozen`, or `tslgenold` runtime dependency is introduced.

## Out Of Scope

- Real vector or intrinsic generated-project rendering.
- Function signature rendering for vector primitives.
- Intrinsic name assembly or body-token rendering changes.
- Masked vector bodies and mask/integral-mask type spelling.
- Generic/runtime-sized vector register spellings.
- Primitive-call dependency closure.
- Real primitive `tests:` metadata rendering.
- Generated CLI/API changes.
- Rust unsafe policy changes.
- New lowering or source parsing.

## Required Validation

Run:

```bash
git diff --check
python -B -m compileall -q tslgen/src/tslgen tslgen/tests
PYTHONPATH=tslgen/src python -B -m pytest -p no:cacheprovider tslgen/tests/test_m143_1_extension_catalog.py tslgen/tests/test_m192_backend_type_spelling_translation.py tslgen/tests/test_m245_extension_register_type_spelling_boundary.py
find tslgen -type d -name __pycache__ -print
```

If validation creates `__pycache__` directories under `tslgen`, remove them
and rerun the final `find` command. Also remove local `.pytest_cache`,
`.mypy_cache`, or `.ruff_cache` directories if validation creates them.

## Required Review/Audit Subagents

After implementation and validation, run read-only subagents:

1. Architecture/boundary reviewer: the type-spelling boundary consumes typed
   lowered values plus typed extension metadata, preserves M192 behavior, and
   does not become a broad backend dispatcher.
2. Evidence reviewer: register spellings come from real
   `tsldata/extensions/extension.tsl` metadata and resolved catalog entries,
   not Python tables or templates.
3. Test reviewer: C++/Rust parity, all resolved metadata entries,
   representative x86/ARM assertions, diagnostics, and guardrails are covered.
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
- do not start M246 inside M245.

## Final Report

Report:

1. Implementation summary.
2. Register type spelling coverage.
3. Review/audit verdicts.
4. Validation commands and exact results.
5. Any follow-ups.
6. Next active prompt path.
