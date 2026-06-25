# TSLc Implementation Safety Contract Review Prompt

## Goal

Review the typed implementation safety contract and required-feature call
propagation slice, including the explicit primitive corpus safety annotation
sweep, recursive post-prune call-fact propagation, local unsafe call-site
rendering, effective verification feature flags, and Rust `unsafe fn`
rendering.

## Scope

Files to inspect:

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/syntax/parser.py`
- `tslc/src/tslc/lower/context.py`
- `tslc/src/tslc/lower/lowerer.py`
- `tslc/src/tslc/lower/region_handlers/calls.py`
- `tslc/src/tslc/lower/region_handlers/intrinsics.py`
- `tslc/src/tslc/lower/region_handlers/memory.py`
- `tslc/src/tslc/select/selector.py`
- `tslc/src/tslc/pipeline.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/src/tslc/render/model.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/render/rust_project.py`
- `tsldata/primitives/**/*.tsl`
- `tslc/tests/test_safety_contract.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Expected Design

- Source safety is typed catalog data: `ImplementationSafety` carries
  `internal_unsafe`, `caller_unsafe`, and stable reason labels.
- `safety:` is implementation-selector metadata, inherited down nested selector
  entries like `requires` and `unroll_variants`; it is not parsed as a selector
  branch and not hidden in body text.
- Validation checks the structural source shape and keeps reason labels open
  for future data-owned documentation.
- The primitive corpus has local `safety:` metadata beside every implementation
  body. Current expected count: 1,327 primitive implementation bodies and 1,327
  local safety blocks.
- Misplaced safety metadata under an `implementation:` body field should be a
  diagnostic, not silently ignored by body extraction.
- Lowering combines source safety with inferred body effects:
  - intrinsic regions mark internal unsafe with reason `intrinsic`;
  - memory regions mark internal unsafe with reason `raw_memory`;
  - raw-pointer parameter signatures infer caller unsafe with reason
    `raw_pointer`.
- Selection preserves concrete feature flags from extension/type-scoped
  `requires` clauses, and lowering carries them on
  `LoweredSpecialization.required_features`.
- Transitivity runs after unresolved dependencies are pruned and before render
  finalization. Live call-graph facts propagate bottom-up to a fixpoint:
  unsafe callee metadata propagates an internal unsafe dependency and
  `unsafe_callee` reason to callers, while required feature flags propagate
  through recursive primitive calls.
- Public `caller_unsafe` does not automatically propagate; safe wrappers may
  discharge unsafe callees with locally-owned storage.
- Generated verification profiles should include machine profile features plus
  propagated required features from live lowered specializations.
- Rust lowering renders calls to caller-unsafe generated wrappers as typed local
  unsafe call-site fragments. Callee-only transitive unsafety should not force a
  whole-body unsafe frame, and local unsafe fragments should suppress themselves
  when an enclosing body frame is already unsafe.
- Call-fact propagation keeps runtime/immediate overload bodies distinct even
  though dependency pruning still uses the broader pre-finalization callable
  identity.
- Rust renderers consume lowered safety facts only. They should format
  `unsafe fn` trait methods, impl methods, wrappers, and free functions when
  `caller_unsafe` is true, and should not rediscover primitive or extension
  semantics.
- C++ rendering should remain unaffected by Rust safety presentation.

## Validation Already Run

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_safety_contract.py
```

Result: `11 passed`.

```bash
python -m pytest -q tslc/tests/test_safety_contract.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_profile_rendering.py tslc/tests/test_build_verify.py::test_shift_right_avx512_immediate_builds tslc/tests/test_build_verify.py::test_masked_load_store_build
```

Result: `54 passed`.

```bash
./verify.sh
```

Result: passed, including 203 non-build tests and 53 generated-build tests.

Additional corpus evidence:

```text
primitive implementation bodies: 1327
local safety blocks: 1327
active/inherited safety blocks: 1327
load/parse/build/validate diagnostics: 0/0/0/0
Rust value-test CLI unnecessary unsafe warnings: 0
```

## Review Questions

1. Is the safety contract owned by typed catalog/lowering data rather than
   renderer-local inference?
2. Is transitive propagation conservative enough to compile current wrappers
   while still surfacing unsafe callees and architecture requirements on
   callers?
3. Are raw-pointer APIs correctly inferred as caller-unsafe without making
   safe higher-level abstractions unnecessarily unsafe?
4. Does the Rust renderer keep formatting separate from semantic safety
   classification?
5. Are diagnostics and tests sufficient for malformed source safety blocks?
6. Are the authored corpus safety classifications plausible and free of
   primitive- or extension-name special cases in production code?
7. Does local unsafe call-site rendering remove nested Rust `unsafe` warnings
   without hiding real caller-unsafe contracts?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

For any non-`Accept` verdict, include concrete findings with file/line
references and the smallest recommended next action.
