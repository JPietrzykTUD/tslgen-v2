# TSLc Vector Query And Primitive Call Handoff

Date: 2026-06-17

Scope: this document summarizes the uncommitted changes made during the chat for `tslc/` and `tsldata/`. It is intended for an agentic follow-up agent that needs to understand what changed, why it changed, how it fits the design, and what remains to verify.

## Original Problem

The generator has TSL data under `tsldata/` and a Python generator under `tslc/`. The problematic source was the conversion primitive data, especially `tsldata/primitives/conversion/repr_change.tsl`.

The insert-based `convert_down` narrowing bodies for AVX variants were broken. They tried to call the `insert` primitive with type arguments such as:

```tsl
call<primitive=insert[..., avx2, index]>(...)
```

Here `avx2` was a bare extension name. The call lowerer treated it as something to render directly, so generated C++ saw an undeclared identifier instead of a vector type. The bug only surfaced when combined generation kept the relevant cross-primitive body after pruning. Pack-based `convert_down` bodies already worked.

There was a second related issue: primitive calls forwarding immediate indices could be named with an `_imm` suffix too broadly. Pure compile-time-immediate primitives such as `insert` and `extract` should not become `insert_imm` or `extract_imm`. The `_imm` split is only appropriate for primitive families that provide both runtime and immediate variants, such as shift primitives.

The user explicitly preferred keeping primitive-to-primitive calls in TSL bodies instead of duplicating the same intrinsic spelling in multiple primitive bodies. Therefore the fix was to make `tslc` correctly lower the primitive call form, not to inline insert intrinsics inside `convert_down`.

## High-Level Design

The implemented direction keeps the TSLc boundaries strict:

- `tsldata/` owns source-level intent and uses source vocabulary such as `call<...>`, `let<type>(...)`, and `vector::*` queries.
- `tslc/src/tslc/lower/calls.py` owns call selector syntax parsing only.
- `tslc/src/tslc/lower/queries.py` owns semantic evaluation of query expressions such as `vector::as_base(...)` and `vector::as(...)`.
- `tslc/src/tslc/lower/region_handlers/` owns TSIL keyword region lowering, including primitive-call lowering and wrapper name decisions.
- `tslc/src/tslc/lower/regions.py` is now a compatibility facade for the region-handler package.
- `tslc/src/tslc/lower/dependencies.py` owns typed dependency extraction for cross-primitive pruning.
- `tslc/src/tslc/pipeline.py` orchestrates selection, dependency closure, lowering, and rendering.
- Backend/render code receives already-decided typed values and does not learn intrinsic-specific special cases for this fix.

No intrinsic names were embedded into lowering or backend logic to fix `convert_down`. The changes are catalog/query driven and preserve the primitive-call style in the TSL source.

## Files Added

### `tslc/src/tslc/lower/calls.py`

This new module contains the shared parser for `call<...>` selector metadata.

It defines:

- `ParsedCallSelector`
- `parse_call_selector(selector_text)`

The parser extracts:

- `primitive_ref`
- `type_args`
- `attrs`

It deliberately does not:

- resolve `@self`
- evaluate vector or type queries
- know about `ToType` or return aliases
- decide wrapper names
- decide mask suffixes
- decide `_imm` suffixes
- compute dependencies
- render target-language code

Reason: before this change, call selector parsing existed in more than one place. Centralizing only the syntax avoids drift without turning the parser into a semantic lowerer.

### `tslc/src/tslc/lower/dependencies.py`

This new module extracts primitive-call dependencies from lowered source bodies.

It defines typed dependency values:

- `VectorIdentity`
- `CallDependency`

It uses:

- `regions.scan(...)` to discover TSIL keyword regions
- `parse_call_selector(...)` for call selector syntax
- `QueryEvaluator` for type and vector query semantics

Reason: cross-primitive pruning used to rely on local regex logic in the pipeline. That was too weak for representation-changing calls because it tracked only a callee name, mask policy, extension, and source type. It did not have a typed target-vector identity, which is necessary for calls such as `insert` inside `convert_down`.

The new dependency extractor is still part of the lowering slice, not the backend. It depends on typed catalog/lowering concepts and does not contain intrinsic-specific behavior.

### `tslc/src/tslc/lower/region_handlers/`

The former monolithic `lower/regions.py` file was split into a focused package:

- `protocol.py`: shared `RenderBody` and `RegionLowerer` contracts.
- `common.py`: local helper functions shared by multiple handlers.
- `intrinsics.py`: `intrin` and `intrin_compose` lowering.
- `declarations.py`: `var` and `let` lowering.
- `masks.py`: `mask` lowering.
- `casts.py`: `cast` lowering.
- `calls.py`: primitive `call` lowering.
- `control.py`: `if`, `assume_aligned`, `loop`, and `switch` lowering.
- `queries.py`: `type<generation>` and `value<generation>` region lowering.
- `returns.py`: `emit_return` lowering.
- `registry.py`: the canonical `DEFAULT_REGION_LOWERERS` ordering.

`tslc/src/tslc/lower/regions.py` now re-exports the same public names and
keeps the old import path stable. This keeps the cleanup behavior-preserving
while reducing the size and responsibility of the original file.

Reason: `regions.py` had become a broad TSIL keyword handler module. Splitting
it keeps each keyword family reviewable without introducing a new lowering
stage, new backend semantics, or a second call-selector parser.

### `tslc/src/tslc/render/`

The former monolithic `render/project.py` file was split into focused render
modules while preserving `render_project(...)`, `ProfileRender`, and
`RenderedProject` as the stable public entry point in `project.py`.

Added modules:

- `_common.py`: shared render helpers for profile slugs, feature spelling,
  static backend assets, text artifacts, used extension/pair discovery, and
  base-type bit-width parsing.
- `emitted_names.py`: emitted wrapper-name finalization for mask-policy and
  mixed runtime/immediate overload sets.
- `cpp_project.py`: C++ artifact assembly, CMake rendering, C++ verify-profile
  flags, x86 `simd<T, ext>` registration rendering, and C++ smoke-test source.
- `rust_project.py`: Rust artifact assembly, Cargo rendering, Rust
  verify-profile target features, Rust `SimdVector` registration rendering, and
  Rust smoke-test source.

`project.py` now only sorts/finalizes profiles, delegates backend artifact
assembly, constructs `VerifyBackend` entries, and returns the in-memory
`RenderedProject`.

Reason: project rendering had grown to mix orchestration, emitted wrapper-name
planning, C++ project formatting, Rust project formatting, and x86 substrate
registration rendering. The split keeps the render package flat and avoids a
new rendering framework, while making the non-presentation naming step explicit
in `emitted_names.py`.

### `tslc/src/tslc/backend/`

The lowering-time backend translation boundary was changed from a single
`BackendTranslation(catalog, backend_id)` class with internal
`backend_id == "rust"` branches to a protocol plus concrete translators.

Added modules:

- `translation_common.py`: backend-neutral type-tag helpers, scalar spelling
  lookup, template lookup/rendering, return framing, intrinsic prefix/suffix
  composition, and the shared `X86_REGISTER_BITS` fact.
- `cpp_translation.py`: C++ lowering-time target-language behavior.
- `rust_translation.py`: Rust lowering-time target-language behavior.

`translation.py` remains the stable public import surface. It now exports:

- `BackendTranslator`
- `create_backend_translation(catalog, backend_id)`
- the existing helper functions such as `signed_of`, `unsigned_of`,
  `is_signed`, `is_type_tag`, `normalize_scalar_tag`
- `X86_REGISTER_BITS`

Lowering code now receives a `BackendTranslator` protocol instance and direct
construction sites use `create_backend_translation(...)`.

The backend-specific behavior moved behind concrete translator methods:

- wrapper call spelling;
- vector and generic-vector type spelling;
- target register spelling;
- register/mask/imask type spelling;
- pointer casts;
- direct intrinsic qualification;
- body framing and Rust unsafe wrapping;
- assume-aligned rendering;
- compile-switch rendering;
- immediate intrinsic forwarding and Rust literal-match intrinsic rendering;
- generic const parameter type spelling.

Reason: lowering extensibility should not depend on adding more
`if backend_id == "..."` checks. A future backend should add a concrete
translator instead of modifying lowering behavior across multiple modules.

## TSL Data Changes

### `tsldata/primitives/conversion/repr_change.tsl`

The insert-based `convert_down` bodies were updated so that insert calls use vector type aliases instead of bare extension names.

The intended call shape is now based on resolved vector types. Conceptually, the fix changes calls from:

```tsl
call<primitive=insert[..., avx2, index]>(...)
```

to a shape where the type argument is a vector alias/query result, for example an alias derived from the declared return type or a `vector::*` query.

Reason: `insert` expects a vector type, not an extension token. The extension name alone is data about an ISA/profile; it is not a target-language vector type.

### Vector Query Vocabulary Migration

The vector query vocabulary was cleaned up across `tsldata/`.

Old forms:

```tsl
vector::as_extension(ext)
vector::as_extension(ext, base)
vector::transform_extension(base)
```

New forms:

```tsl
vector::as_extension(ext)  // same base, named extension
vector::as_base(base)      // same extension, named base
vector::as(ext, base)      // named extension, named base
```

The old two-argument and transform forms are intentionally unsupported after migration:

- `vector::as_extension(ext, ToBase)` must fail.
- `vector::transform_extension(ToBase)` must fail.

Migrated files:

- `tsldata/primitives/bitwise/shifts.tsl`
- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/pack_expand.tsl`
- `tsldata/primitives/misc/compress.tsl`

Reason: `vector::as_extension(ext, base)` was overloaded and easy to misread. `vector::transform_extension(base)` also suggested that the extension changed, while it actually changed the base type. The new names make the changed dimension explicit.

## Lowering Changes

### `tslc/src/tslc/lower/queries.py`

The query evaluator now supports the explicit vector vocabulary:

- `vector::as_extension(ext)` through `AsExtensionQuery`
- `vector::as_base(base)` through `AsBaseQuery`
- `vector::as(ext, base)` through `VectorAsQuery`

The following forms are not accepted:

- `vector::as_extension(ext, base)`
- `vector::transform_extension(base)`

`TransformExtensionQuery` was removed/renamed so the code no longer carries a misleading name.

`TargetVector` now carries `base_tag` as part of its semantic identity. This is important for dependency planning and type identity because rendered target-language spelling alone is not enough to describe what vector type is meant.

The `X86_REGISTER_BITS` fallback was removed from `lower/queries.py`. Extension width resolution is now catalog driven:

- current extension resolution uses the selected `Extension` object;
- named extension resolution uses `context.env.translation.catalog.extensions`;
- lookup can match extension block names and emitted `isa_name`;
- unknown extension names fail unresolved instead of falling back to a backend table.

Reason: lowering must not import backend x86 register-width constants. Width and type facts belong in the catalog/source data. Backend-specific tables can still exist in backend/render layers, but query evaluation should remain catalog-driven.

### `tslc/src/tslc/lower/context.py`

The old all-purpose `LoweringContext` was replaced by an explicit
`LoweringSession` aggregate:

- `LoweringEnv`: frozen selected facts for one specialization.
- `LoweringScope`: mutable body-local aliases and query symbols.
- `LoweringEffects`: diagnostics, unsupported state, and Rust `unsafe`
  marking.
- `LoweringSession`: the thin object threaded through query and region
  handlers.

The split keeps the low-plumbing handler API: handlers still receive one
argument named `context`. The difference is that field access now makes the
dependency visible:

- selected facts live under `context.env`;
- aliases and query symbols live under `context.scope`;
- diagnostics and side effects live under `context.effects`.

The scope keeps separate channels for:

- `target_type_symbols`: declared return-target type aliases plus the
  compatibility synonym `ToType`;
- `extension_symbols`: declared return-target extension aliases;
- `type_symbols`: `let<type>(...)` aliases that resolve to source type tags;
- `vector_aliases`: `let<type>(...)` aliases that resolve to structured
  `VectorValue` identities;
- `type_aliases`: rendered type spellings used for post-render substitution.

Reason: query evaluation and dependency extraction need semantic type/vector identities, not just rendered C++ spellings.
The old mutable context made selected facts, body-local alias state, call
naming policy, diagnostics, and unsafe state look equivalent. The split keeps
the implementation simple while making handler dependencies auditable.

### `tslc/src/tslc/lower/lowerer.py`

The lowerer now binds return-target aliases more precisely:

- `return_type: base: Alias` binds `Alias` and `ToType` to the selected target base.
- `return_type: extension: Alias` binds `Alias` to the selected target extension.

`ToType` remains an implicit synonym for the target base. It is not a declared return alias by itself. The declared alias from `return_type` is now respected as the primary source-data name.

`Lowerer.lower(...)` now computes base type, representation-change target
facts, and immediate metadata before constructing `LoweringEnv`. That lets the
environment remain frozen after session creation.

`LetLowerer` records `let<type>(...)` aliases through
`LoweringScope.bind_type_alias(...)`, while still preserving rendered alias
behavior where needed.

The helper that computes type parameter bounds no longer searches raw body text with regex. It scans TSIL fragments and parses call selectors through `parse_call_selector(...)`.

Reason: raw string scanning could match call-looking text inside string literals. The shared scanner/parser path is less brittle and keeps call metadata extraction consistent.
The session split is intentionally not a new lowering stage or IR taxonomy; it
is ownership cleanup around existing lowering state.

### `tslc/src/tslc/lower/regions.py` and `region_handlers/`

`CallLowerer` now lives in `lower/region_handlers/calls.py` and uses
`parse_call_selector(...)` for call selector parsing.

It still owns semantic call lowering:

- resolves `@self` to `context.env.current_primitive`;
- evaluates type and vector arguments through `QueryEvaluator`;
- renders extra type and constant arguments;
- applies mask-policy naming only when the callee is policy split;
- applies `_imm` only when the callee belongs to an immediate-split primitive family.

Reason: `calls.py` is intentionally syntax-only. `CallLowerer` is the correct location for source-call lowering because it has the full lowering context.

The other TSIL keyword lowerers were moved to focused `region_handlers/*`
modules with the same behavior and the same default lowerer ordering. The old
`lower/regions.py` module is intentionally retained as a facade so existing
imports of `DEFAULT_REGION_LOWERERS`, `RegionLowerer`, or individual lowerer
classes continue to work.

## Selection And Pipeline Changes

### `tslc/src/tslc/select/selector.py`

The selector now computes `immediate_split_names(catalog)`.

This identifies primitive families that have both runtime and compile-time immediate variants. It deliberately does not classify pure compile-time-immediate primitives such as `insert` and `extract` as `_imm` split families.

Reason: `_imm` suffixing is a wrapper-family naming concern. It should be based on catalog structure, not on a local heuristic that any forwarded immediate implies `_imm`.

### `tslc/src/tslc/pipeline.py`

The pipeline now uses typed call dependencies from `lower/dependencies.py` for dependency closure.

The dependency key is based on:

- backend
- primitive
- mask policy
- source `VectorIdentity`
- optional target `VectorIdentity`

This replaces the narrower dependency shape that tracked only extension/type-like strings.

The pipeline also passes immediate split names into rendering/lowering context.

Reason: representation-changing primitive calls need target-vector identity. For example, `convert_down` calling `insert` must request the correct target vector implementation so pruning does not discard the needed callee.

The large earlier pipeline edits were cleaned up by moving parsing and dependency semantics out to focused lower modules. The pipeline now acts as orchestrator rather than owning call parsing, query semantics, or backend details.

### `tslc/src/tslc/render/project.py`

Render context wiring was updated so generated wrapper naming receives immediate-split information.

Reason: rendering should format already-decided names and selected implementations; it should not infer which primitive families need `_imm` naming by inspecting source bodies.

## Documentation Change

### `docs/redesign/design-decisions.md`

ADR-074 records the vector query vocabulary decision.

Decision summary:

- keep `vector::as_extension(ext)` for changing only the extension;
- add `vector::as_base(base)` for changing only the base;
- add `vector::as(ext, base)` for changing both extension and base;
- reject the old two-argument `vector::as_extension(ext, base)`;
- reject the old `vector::transform_extension(base)`.

Reason: the source language should make vector dimension changes explicit and avoid overloaded names.

## Test Changes

### `tslc/tests/test_generation_conditionals.py`

Added and updated tests around query evaluation:

- positive coverage for `vector::as_extension(ext)`;
- positive coverage for `vector::as_base(base)`;
- positive coverage for `vector::as(ext, base)`;
- negative coverage for unsupported old forms.

### `tslc/tests/test_masks_and_calls.py`

Added or updated tests for:

- shared call selector parsing;
- type-parameter-bound extraction through TSIL scanning instead of raw regex;
- immediate split naming only for mixed runtime/immediate families;
- `convert_down` insert calls resolving target vector aliases rather than bare extension names.

### `tslc/tests/test_build_verify.py`

Updated comments/fixtures to use the new vector query vocabulary.

## Validation Performed

The following commands passed:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench python -m compileall -q tslc/src/tslc
```

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_queries tslc/tests/test_generation_conditionals.py -q
```

Result: `19 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_calls tslc/tests/test_masks_and_calls.py -q
```

Result: `8 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_convert tslc/tests/test_build_verify.py::test_convert_builds -q
```

Result: `1 passed`.

The same targeted validation set was rerun on 2026-06-17 with fresh temp
directories:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_queries_rerun tslc/tests/test_generation_conditionals.py -q
```

Result: `19 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_calls_rerun tslc/tests/test_masks_and_calls.py -q
```

Result: `8 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_convert_rerun tslc/tests/test_build_verify.py::test_convert_builds -q
```

Result: `1 passed`.

The relevant build tests were also run together earlier:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_insert_builds tslc/tests/test_build_verify.py::test_shift_right_delegation_builds tslc/tests/test_build_verify.py::test_gather_scatter_builds -q
```

The non-convert tests passed in that run, but `test_convert_builds` hit a setup error caused by a stale pytest temp directory after a previous timeout. It was rerun with a fresh `--basetemp` and passed.

Static checks performed:

```powershell
git diff --check
```

Result: passed.

```powershell
rg -n 'TransformExtensionQuery|vector::transform_extension|vector::as_extension\([^,\)]*,' tslc\src\tslc tsldata
```

Result: no hits.

```powershell
rg X86_REGISTER_BITS tslc/src/tslc/lower/queries.py
```

Result: no hits.

`docs/redesign/design-decisions.md` ADR-074 was reviewed after migration and
updated so its context and consequences describe the migration as implemented,
not pending.

The uncommitted diff was audited with `git status --short --untracked-files=all`
and `git diff --name-only`. The changed paths are confined to docs, `tslc/`,
and `tsldata/`.

After the `regions.py` split into `lower/region_handlers/`, the targeted
validation was rerun through the devcontainer:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench python -m compileall -q tslc/src/tslc
```

Result: passed.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_region_handlers_calls_rerun tslc/tests/test_masks_and_calls.py -q
```

Result: `8 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_region_handlers_queries tslc/tests/test_generation_conditionals.py -q
```

Result: `19 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_region_handlers_convert_build tslc/tests/test_build_verify.py::test_convert_builds -q
```

Result: `1 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench git diff --check
```

Result: passed.

Additional import-boundary checks confirmed that `lower/lowerer.py` still uses
the stable `tslc.lower.regions` facade and that the facade exposes the same
14 default region lowerers, from `intrin_compose` through `emit_return`.

After the `render/project.py` split into focused render modules, validation was
rerun through the devcontainer:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench python -m compileall -q tslc/src/tslc
```

Result: passed.

After the backend translator protocol cleanup, validation was rerun through the
devcontainer:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench python -m compileall -q tslc/src/tslc
```

Result: passed.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_backend_translation_select tslc/tests/test_select_and_lower.py -q
```

Result: `10 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_backend_translation_conditions tslc/tests/test_generation_conditionals.py -q
```

Result: `19 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_backend_translation_calls tslc/tests/test_masks_and_calls.py -q
```

Result: `8 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_render_project_calls tslc/tests/test_masks_and_calls.py -q
```

Result: `8 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_render_project_convert tslc/tests/test_build_verify.py::test_convert_builds -q
```

Result: `1 passed`.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench git diff --check -- tslc/src/tslc/render
```

Result: passed.

After the `LoweringContext` ownership cleanup into
`LoweringSession(env, scope, effects)`, validation was rerun in the local
workspace:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
```

Result: `29 passed`.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `75 passed`.

```bash
git diff --check
```

Result: passed.

The full suite was also probed with:

```bash
python -m pytest -q -x tslc/tests
```

Result: stopped at
`tslc/tests/test_build_verify.py::test_generated_profiles_build`. This was an
environmental C++ configure failure, not a Python/lowering failure:
`CXX=zig c++`, and CMake's compiler-identification step attempted to create
`/root/.cache/zig/tmp/...`, which failed with `ReadOnlyFileSystem`.

`docs/redesign/design-decisions.md` was checked after the session split. No
ADR update was made because the change is a local `tslc` ownership refactor
that implements the existing separation-of-concerns policy rather than a new
source-language or repository-wide architecture decision.

## Known Caveats

Full `tslc/tests/test_build_verify.py` was attempted with fresh temp
directories and exceeded the tool timeout twice:

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_build_verify_full_rerun tslc/tests/test_build_verify.py -q
```

Result: timed out after about 15 minutes.

```powershell
devcontainer.cmd exec --workspace-folder C:\Users\johan\own\work\tmp\py-bench pytest --basetemp=tslctmp/pytest_catalog_vector_build_verify_full_rerun2 tslc/tests/test_build_verify.py -q
```

Result: timed out after about 40 minutes.

No pytest, cmake, ninja, or python build processes were left running after the
timeouts. Targeted build tests relevant to this slice passed.

There are stale temporary directories under `tslctmp/` from interrupted test runs. They were not removed to avoid unrelated filesystem cleanup.

`X86_REGISTER_BITS` still exists outside `lower/queries.py`, for example in backend/render-oriented modules. That is acceptable for this slice because the explicit requirement was to remove the fallback from query lowering. A future cleanup can decide whether backend uses are still appropriate.

The `ToType` implicit alias still exists. It is a compatibility/source-language convention for target-base aliases. The implementation now also honors the declared `return_type` alias, so future TSL data can prefer explicit declared aliases over `ToType`.

The old vector query forms are intentionally unsupported. If future TSL data reintroduces them, query evaluation should fail instead of silently accepting compatibility syntax.

## Design Assessment

The current slice is in line with the intended TSLc separation of concerns:

- Call selector syntax is centralized but semantic-free.
- Query evaluation is catalog-driven and typed.
- Lowering state is split into `LoweringEnv`, `LoweringScope`, and
  `LoweringEffects` under one `LoweringSession`, so handlers still have low
  plumbing while selected facts, alias mutation, and diagnostics are separate.
- Dependency extraction reuses the shared parser and query evaluator.
- Pipeline code is orchestration, not a source scanner.
- TSIL keyword lowerers are split by keyword family under `lower/region_handlers/`.
- `lower/regions.py` is a small compatibility facade, not a second implementation.
- Project rendering is split by responsibility under `render/`, with
  `project.py` kept as a thin public orchestrator.
- Emitted wrapper-name finalization is explicit in `render/emitted_names.py`
  instead of being hidden inside project artifact formatting.
- Backend lowering translation now uses a protocol/factory plus concrete C++
  and Rust translators, so backend behavior is not selected by conditional
  branches inside lowering.
- Backend/render code does not receive intrinsic-specific rules for `convert_down`.
- TSL data remains responsible for expressing primitive-to-primitive calls.
- The fix does not duplicate insert intrinsics in conversion bodies.

The most important hygiene property is that there is now one parser for call selector syntax and one evaluator for vector/type query semantics. This reduces drift between call lowering and dependency pruning.

The later `regions.py` cleanup also reduces the review surface of the lowering
slice without changing the source/lowering/backend boundary. It is a module
organization change, not a semantic rewrite.

## Suggested Follow-Up

Before committing, a follow-up agent should:

1. Run full `tslc/tests/test_build_verify.py` with a fresh `--basetemp` in an environment that can allow more than 40 minutes, or split the file deliberately if full-file runtime remains impractical.
2. Re-run `git diff --check` after any further edits.
3. Keep old vector query forms unsupported unless the user explicitly revises the decision.
