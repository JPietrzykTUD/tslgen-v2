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

## Strict Typed Render Follow-Up

On 2026-06-20 the active `tslc` line also tightened the lowering-to-rendering
handoff so renderer-side semantic body rewrites are no longer needed.

Key points:

- `LoweredSpecialization` now stores a `LoweredBody`; `body_text` remains a
  compatibility render property.
- Lowered bodies carry `RenderText` values: `LiteralText` for terminal accepted
  source fragments, `RenderPlaceholder` for context-sensitive vector/register/
  base/mask/imask spellings, `TemplateApplication` for validated backend
  templates, and `RenderSequence` for ordered composition.
- `ExpressionRenderer` passes typed nested render values to region handlers.
  Handlers render to concrete strings only for generation-time keys, selectors,
  counts, intrinsic suffixes, or diagnostics.
- Declaration initializers and memory/mask template fields preserve typed
  expression fragments through final rendering.
- `let<type>` aliases are stored as typed render values. Raw source chunks
  tokenize alias identifiers into typed fragments, and query evaluation resolves
  alias names for type positions such as `cast<static>(CountT, ...)`.
- Accepted bitwise-not source spelling is explicit TSIL:
  `bit_negate(expr)`. The backend syntax facet renders that semantic operation
  as `~` in C++ and `!` in Rust, avoiding backend-id branches and raw `~`
  interpretation in generic lowering.
- Rust overloaded rendering supplies `RenderContext` values instead of running
  `_concretize_simd_assoc` or replacing body text.
- Backend templates use validated `TemplateApplication` fields; unchecked
  placeholder substitution and body-text semantic rewrites remain disallowed.

Validation for this follow-up:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_render_model.py
python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py
python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_coverage.py
./verify.sh
```

`./verify.sh` passed on 2026-06-20 with 103 non-build tests, 49 generated-build
tests, and the final architecture guards.

## Catalog/Profile Validation Follow-Up

On 2026-06-21 the active `tslc` line added a real validation pass for catalog
and machine profile data before selection, lowering, backend dialect creation,
or rendering.

Key points:

- `tslc.catalog.validation.validate_catalog(...)` checks the promoted catalog
  plus parsed source tree and returns structured diagnostics for duplicate
  source keys, unknown fields, invalid enum-like strings, missing backend/type
  spellings, unknown or cyclic extension inheritance, and malformed `requires`
  shapes.
- `tslc.catalog.validation` is a package: `__init__.py` owns the public
  `validate_catalog(...)` facade, while `invariants.py`, `schema_validation.py`,
  `requires_validation.py`, and `source_spans.py` keep the rule families
  separated.
- `requires` validation is structural only. It confirms accepted flag-list and
  nested-map shapes without trying to perform feature selection or profile
  matching.
- Machine profile loading now has a diagnostic-returning boundary,
  `load_machine_profiles_checked(...)`, which reports malformed JSON, duplicate
  JSON keys, duplicate profile names, unknown fields, invalid profile families,
  malformed flags, and malformed alternative spellings.
- `pipeline.generate(...)` accumulates these diagnostics and stops on errors
  before backend dialect creation or implementation selection.
- The compatibility `load_machine_profiles(...)` API remains and returns only
  the loaded profiles.

Focused coverage:

- `tslc/tests/test_catalog_validation.py` covers successful tiny catalogs,
  duplicate keys, unknown fields, enum-like values, missing backend spellings,
  unknown/cyclic inheritance, malformed `requires`, machine profile shape
  errors, and duplicate JSON keys.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_catalog_validation.py
git diff --check
```

Result: passed.

```bash
PYTHONPATH=tslc/src python - <<'PY'
from pathlib import Path
from tslc.sources import SourceLoader
from tslc.syntax.parser import TslParser
from tslc.catalog.builder import CatalogBuilder
from tslc.catalog.validation import validate_catalog

load = SourceLoader().load_dir(Path("tsldata"))
parsed = TslParser().parse(load.documents)
built = CatalogBuilder().build(parsed)
assert built.catalog is not None
diagnostics = validate_catalog(built.catalog, parsed)
assert diagnostics == (), diagnostics
PY
```

Result: passed with zero validation diagnostics for the current `tsldata/`
corpus.

```bash
./verify.sh
```

Result: passed with 115 non-build tests and 53 generated-build tests across the
script's shards.

## Performance-Oriented Follow-Up Changes

After the vector-query and primitive-call slice, the generator was profiled for
avoidable repeated work during `verify.py` generation. Two focused performance
changes were applied without changing generated artifacts or moving semantic
ownership into the pipeline.

### `tslc/src/tslc/catalog/signatures.py`

`parse_signature(...)` is now cached with an unbounded `lru_cache`.

Reason: signature parsing is pure for a given signature string, and generation
repeatedly parses the same small signature vocabulary while specializing many
primitive/backend/type combinations. Caching the parser result removes that
repeat cost without introducing generator-global mutable pipeline state.

### `tslc/src/tslc/lower/lowerer.py` and `context.py`

`Lowerer` now owns a private `_LowererCatalogFacts` cache keyed by catalog
identity. The cached facts are derived once per catalog/generation and reused
for each specialization:

- primitive boolean axes;
- primitive type-argument generic counts;
- mask-policy split primitive names;
- immediate split primitive names.

`LoweringEnv.__post_init__` now avoids re-copying mappings that are already
frozen `MappingProxyType` instances, so these cached immutable facts remain
cheap to pass into each lowering session.

Reason: these maps are lowerer-specific, read-only interpretations of the
catalog. Passing them in from `pipeline.py` would make the orchestration layer
know lowerer internals and weaken separation of concerns. Keeping the cache
inside `Lowerer` makes the optimization local to the owner of those facts.

### `tslc/src/tslc/lower/dependencies.py`, `lowerer.py`, and `pipeline.py`

Dependency extraction can now consume already-scanned TSIL segments through
`extract_call_dependencies_from_segments(...)`. The existing
`extract_call_dependencies(...)` API remains as a compatibility wrapper that
scans raw body text before delegating.

`Lowerer.lower(...)` accepts an optional keyword-only `body_segments` tuple.
When supplied, backend lowering and `_type_param_bounds(...)` reuse that
segment sequence instead of scanning the implementation body again. The private
`_type_param_bounds(...)` helper still accepts raw body text for existing tests
and compatibility callers.

`pipeline.py` now scans each selected implementation body once, with source
span information when available, then passes the same immutable segment tuple
to dependency extraction and to each backend lower call.

Reason: TSIL scanning is a lexical source-body boundary already shared by
lowering and dependency extraction. Reusing the scanned `Segment` tuple removes
one dependency scan plus one scan per backend lower without making the pipeline
parse call selectors, evaluate queries, decide dependencies, or lower regions.
The pipeline owns reuse of the shared input representation; the lower modules
still own semantic interpretation.

### Observed Impact

The first cache-oriented pass reduced the measured generation time for the
`add,hadd` probe from about `9.1s` to `3.5-3.8s`, and the 20-primitive probe
from about `21.6s` to `6.17s`.

The scanned-segment reuse pass then reduced the same probes further to about
`2.8-2.9s` for `add,hadd` and `4.25s` for the 20-primitive set.

Coverage and pruning counts stayed unchanged in the timing probes:

- `add,hadd`: `coverage=5720`, `skipped=176`, `diagnostics=0`;
- 20-primitive probe: `coverage=15920`, `skipped=736`, `diagnostics=0`.

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

The lowering-time backend boundary is now a `BackendDialect` protocol with four
explicit facets:

- `types`: scalar/vector/register/mask/imask spelling and const-param type
  spelling.
- `intrinsics`: intrinsic suffix/name/qualification and immediate intrinsic
  call forms.
- `templates`: backend template lookup and placeholder rendering.
- `syntax`: return/body framing, primitive calls, pointer casts,
  assume-aligned, and compile-switch rendering.

`translation.py` remains the stable public import surface. It exports
`BackendDialect`, the four facet protocols, `create_backend_dialect(catalog,
backend_id)`, the existing type-tag helper functions, and `X86_REGISTER_BITS`.
The old `BackendTranslator` and `create_backend_translation(...)` names were
removed from source/tests instead of kept as compatibility aliases.

Concrete behavior stays in the existing backend files:

- `translation_common.py`: shared backend-neutral helpers and facts.
- `cpp_translation.py`: `CppBackendDialect` assembling private `_CppTypes`,
  `_CppIntrinsics`, `_CppTemplates`, and `_CppSyntax` facets.
- `rust_translation.py`: `RustBackendDialect` assembling private `_RustTypes`,
  `_RustIntrinsics`, `_RustTemplates`, and `_RustSyntax` facets.

`LoweringEnv` now carries both `catalog` and `backend`. Query/dependency code
reads extension/catalog facts from `context.env.catalog`; backend-specific
spelling or rendering goes through the relevant dialect facet. This preserves
generated behavior while making handler dependencies visible.

Reason: the previous translator protocol correctly removed backend-ID
conditionals from lowering, but it still mixed semantic translation, type
spelling, template lookup, call rendering, immediate handling, and body framing
in one wide object. The facet split keeps the simple protocol/factory shape
while avoiding a new backend framework or pipeline stage.

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
- named extension resolution uses `context.env.catalog.extensions`;
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

```bash
./verify.sh
```

Result: passed all targeted validations, including 163 non-build tests, 53
generated-build tests, and the architectural grep guards.

### TSIL Statement Terminator Slice

The scanner now owns source-level semicolons after recognized TSIL regions in
statement streams. This keeps authored statement terminators from leaking into
raw text and avoids duplicate `;;` when a lowerer/template already owns target
statement syntax.

Implemented pieces:

1. `Region` carries `has_statement_terminator` when the scanner consumes a
   following source `;`.
2. Top-level body streams and brace-block bodies scan in statement context;
   nested keyword argument payloads scan in expression context.
3. Lowering appends one target `;` by default for consumed non-block
   statement/expression regions. Statement-specific exceptions are owned by the
   keyword lowerers: `VarLowerer` keeps backend declaration templates unchanged,
   and `LetLowerer` keeps substituted aliases as no target statement.
4. Block forms such as `if`, `loop<range>`, and `switch<compile>` do not gain a
   target semicolon.
5. The primitive corpus under `tsldata/primitives` was normalized so all
   scanner-identified `let<type>` and `var<...>` statement regions carry source
   semicolons. The migration inserted 751 semicolons across 24 primitive files.

Focused coverage:

- `tslc/tests/test_tsil_scan.py` asserts source semicolons are consumed for
  top-level regions and not claimed by nested expression atoms.
- `tslc/tests/test_select_and_lower.py` asserts `let<type>(...);`,
  `var<infer>(...);`, `intrin<...>(...);`, and `emit_return(...);` keep the
  intended target statement spelling without duplicate or stray terminators.
- `tslc/tests/test_tsil_statement_terminators.py` scans
  `tsldata/primitives` and fails if an accepted statement keyword family is
  missing its source terminator.

Validation for this slice:

```bash
python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_lane_lists.py
```

Result: `36 passed`.

```bash
python -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
```

Result: `2 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `163 passed`.

```bash
git diff --check
```

Result: passed.

## Value-Test Planning Boundary Slice

On 2026-06-23 the generated value-test path was refactored so renderers no
longer classify primitive/test shapes directly.

Key points:

- `tslc.value_tests` now owns value-test planning. `ValueTestPlanner` consumes
  the finalized profile render data plus the catalog and emits typed
  `ValueTestProjectPlan` / `ValueTestProfilePlan` / `ValueTestCasePlan` values.
- `tslc.render.tests_project` is now a thin artifact assembler: it copies the
  shared helper assets and delegates C++/Rust test text formatting to
  plan-consuming renderers.
- `LoweredSpecialization` now carries `source_primitive_name` separately from
  `primitive_name`, so emitted wrappers such as `_mask`, `_maskz`, and `_imm`
  keep a stable link to the source primitive whose authored `tests:` should be
  planned.
- Value-test harness helpers are discovered from unique catalog signatures
  (`v:=s[]`, `s[]:=v`, and `im:=m`) instead of fixed primitive names. Pipeline
  `test_harness=True` seeds dependency closure from those discovered names.
- Value-test planning diagnostics are surfaced through `RenderedProject` and
  `GenerationResult`. Warnings are only surfaced for explicit test-harness
  generation; planning errors remain surfaced for ordinary generation.

Focused coverage:

- `tslc/tests/test_value_test_planning.py` covers signature-based harness
  discovery with renamed primitives, emitted/source identity preservation,
  source-identity lookup for split masked names, renderer operation from
  prebuilt plans without a catalog, and an assembler guard for
  `render/tests_project.py`.
- The follow-up cleanup split `tslc.value_tests.planner` into focused modules:
  `harness.py` owns signature-based helper discovery, `patterns.py` owns typed
  matchers, `case_plans.py` owns render-ready case construction, and
  `literals.py` owns C++/Rust literal spelling. `planner.py` is now an
  orchestration boundary again.
- The cleanup also removed the stray Rust literal formatter from
  `render_cpp.py`, renamed source-looking plan kinds to `vector_to_array` and
  `mask_to_vector`, and added an architecture guard for renderer literal
  ownership plus planner size.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py
```

Result: `49 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `145 passed`.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_generated_profiles_build
```

Result: `1 passed`.

```bash
git diff --check
```

Result: passed.

Follow-up cleanup: value-test planning now separates semantic pattern matching
from backend renderer capability. `ValueTestPattern` no longer carries
`backend_ids`, `ValueTestProjectPlan` no longer has C++/Rust-specific profile
fields, and renderers declare `ValueTestBackendSupport` values listing the
case kinds they can consume. `render_project(...)` is the only current wiring
point that maps finalized C++/Rust profile data into generic
`ValueTestBackendProfileInput` values for the planner.

Focused validation for the capability cleanup:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_lane_lists.py tslc/tests/test_support_policy.py tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

Result: compile passed; value-test planning passed with 7 tests; combined
focused shard passed with 26 tests; diff check passed.

Remaining follow-up risk: `tslc.value_tests.case_plans` is still the largest
value-test module because it owns the case-construction helper family. The next
value-test expansion should split that helper family by plan-kind cluster
before adding new shapes.

```bash
./verify.sh
```

Result: passed all targeted validations, including 123 non-build tests and 53
generated-build tests across its shards.

### Support Policy Capability Boundary Slice

The support-policy follow-up centralizes current prototype support decisions in
`tslc.support_policy.SupportPolicy` and removes behavior branches that inferred
compiler capability from the source extension identity `generic`.

Implemented pieces:

1. `Extension` now preserves minimal capability metadata promoted from source:
   `intrinsic_style`, `vector_bits_kind`, `size_parameter_name`, and
   `vector_register_type_policy`, with inheritance through parent extensions.
2. `SupportPolicy` owns supported backend ids, emitted extension families,
   signature kinds, maskable signature forms/suffixes, immediate and variadic
   kinds, pointer/index kinds, target-marker values, and deferred cases.
3. `tslc.support_policy_views` owns deterministic catalog-derived scans:
   selectable primitive variants, mask/immediate split-name discovery, and
   representation target candidate filtering. `SupportPolicy` no longer imports
   `Catalog` or `Primitive`.
4. Selection skips variadic sized-vector forms through
   `SupportPolicy.skips_variadic_on_extension(...)`, not by extension family or
   source extension name.
5. Lowering records `uses_sized_vector` and lane-parameter facts on lowered
   specializations and representation-change targets; register/base collapse is
   derived from the extension register policy.
6. Query evaluation resolves named extensions from the catalog and treats
   sized-vector targets by capability. `vector::as_extension(generic)` remains
   accepted source data because `generic` is a catalog extension name, but the
   behavior is driven by `vector_bits_kind == "sized"`.
7. Backend renderers receive lowered sized-vector facts instead of checking the
   source extension name. Backend substrate spellings remain local to the C++ and
   Rust presentation layer.

Focused coverage:

- `tslc/tests/test_support_policy.py` covers backend/signature support, pure
  mask-form facts, sized-vector capability derivation, variadic deferral, type
  width, and target-dimension facts.
- `tslc/tests/test_support_policy_views.py` covers catalog-derived maskability,
  selectable variants, split-name discovery, and representation-change target
  filtering.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_support_policy_views.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py
```

Result: `45 passed`.

```bash
python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_build_verify.py tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
```

Result: `108 passed`.

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

## Lane-List `set` Planning Decision

On 2026-06-23, the active `tslc` line accepted the design direction recorded in
ADR-079: replace the variadic `set` source shape with a first-class lane-list
parameter.

Current transition source:

```tsl
prim<v:=s...>[arg_count(args)=return_vector_length] set(args...):
```

Selected target source:

```tsl
prim<v:=(lanes<s>)> set(values):
```

The accepted first-class source mechanisms are deliberately small:

- `lanes<s>` is a single named parameter whose length is the selected return
  vector lane count.
- `lanes<at>(values, N)` accesses one scalar lane-list element, and `N` must be
  generation-time known.
- `loop<generation>(i, start, end, step) { ... }` expands in the generator and
  binds `i` as a generation-time integer.
- Existing `loop<range>` remains a normal emitted target-language loop.
- No `lanes<expand>` or `lanes<expand_reverse>` should be added in the first
  design.

The x86-style reverse construction currently expected by `set` tests should be
made explicit in the `set` body, for example by using
`lanes<at>(values, value<generation>(vector::length) - 1 - i)`, rather than
hiding reversal in the signature or renderer.

Lane-list `set` migration completed in the current worktree:

- `SignatureShape` now carries structured `SignatureTerm` values while keeping
  the compatibility `result_kind`/`param_kinds` surface.
- `lanes<s>` is a supported parameter-position signature term and is rejected in
  result position or malformed forms such as `lanes<>`, `lanes<v>`, and nested
  lane lists.
- Lowering records named `LaneListParameter` facts with element kind and selected
  lane count/expression.
- `lanes<at>(values, N)` lowers for generation-time integer indexes, including
  loop-bound symbols and the arithmetic needed by `set`.
- `loop<generation>(i, start, end, step) { ... }` expands in the generator,
  binds `i` as a generation-time integer, and diagnoses malformed arity,
  non-integer bounds, and zero step.
- C++ and Rust render `lanes<s>` parameters through the existing array-like lane
  storage ABI instead of a public C++ variadic pack.
- The real corpus `set` source is now `prim<v:=(lanes<s>)> set(values):`.
- C++/Rust value-test planning renders a `lane_list` case kind for
  `v:=(lanes<s>)`.
- Production support for the old C++ variadic wrapper, variadic selection skip,
  `variadic_lanes` handoff, backend pack syntax hooks, and `pack_first` helper
  has been removed. `pack<...>` is quarantined as an unsupported TSIL keyword.

Validation for the completed migration:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py tslc/tests/test_support_policy.py tslc/tests/test_catalog_validation.py tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

Results: compile passed; the combined targeted run passed with 61 tests; diff
check passed.

Next concrete prompt:

```text
docs/agent/runs/tslc-lane-list-set-migration-review-prompt.md
```

After the backend dialect facet split, validation was rerun in the local
workspace:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `10 passed`.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py
```

Result: `19 passed`.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests/test_determinism.py
```

Result: `1 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `75 passed`.

```bash
rg "BackendTranslator|create_backend_translation|env\\.translation|translation\\.catalog" tslc/src/tslc tslc/tests
```

Result: no hits.

```bash
git diff --check
```

Result: passed.

The full suite was also probed after the dialect split with:

```bash
python -m pytest -q -x tslc/tests
```

Result: stopped at
`tslc/tests/test_build_verify.py::test_generated_profiles_build`. This remains
the environmental Zig/CMake failure: `/opt/zig/zig c++` attempts to create
`/root/.cache/zig/tmp/...` and fails with `ReadOnlyFileSystem`.

`docs/redesign/design-decisions.md` was checked after the session split and
again after the backend dialect split. No ADR update was made because both
changes implement the existing separation-of-concerns and capability-boundary
policies rather than a new source-language or repository-wide architecture
decision.

The backend dialect facet split then went through a focused review pass. The
review verdict was `Accept`: no blocking architecture, boundary, migration, or
validation issues were found. The review confirmed that lowering-time backend
access now runs through the `BackendDialect` facets, `LoweringEnv` carries the
explicit `Catalog`, query/dependency code no longer reaches through
`translation.catalog`, and the removed names
`BackendTranslator`/`create_backend_translation`/`env.translation` do not
remain in source or tests.

After the performance follow-up changes, local validation was rerun:

```bash
python -B -m py_compile tslc/src/tslc/catalog/signatures.py tslc/src/tslc/lower/context.py tslc/src/tslc/lower/dependencies.py tslc/src/tslc/lower/lowerer.py tslc/src/tslc/pipeline.py
```

Result: passed.

Focused lowerer, dependency, query, and TSIL-scan tests were rerun.

Result: `41 passed`.

```bash
python -m pytest -q -k 'not build' tslc/tests
```

Result: `80 passed, 40 deselected in 63.17s`.

The performance timing probes were rerun after each pass. The first pass
covered `parse_signature` caching, lowerer-owned catalog fact caching, and
cheaper frozen mapping reuse. The second pass covered scanned TSIL segment
reuse across dependency extraction and backend lowering. Build-verification
tests were not rerun as part of the performance pass; the build caveats below
still apply.

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
- Pipeline code orchestrates one shared TSIL scan per selected body, then passes
  immutable segments to dependency extraction and backend lowering; it does not
  parse call selectors or own dependency semantics.
- TSIL keyword lowerers are split by keyword family under `lower/region_handlers/`.
- `lower/regions.py` is a small compatibility facade, not a second implementation.
- Project rendering is split by responsibility under `render/`, with
  `project.py` kept as a thin public orchestrator.
- Emitted wrapper-name finalization is explicit in `render/emitted_names.py`
  instead of being hidden inside project artifact formatting.
- Backend lowering translation now uses `BackendDialect` facets (`types`,
  `intrinsics`, `templates`, `syntax`) plus concrete C++ and Rust dialects, so
  lowering handlers can depend on the narrow backend capability they need.
- Backend/render code does not receive intrinsic-specific rules for `convert_down`.
- TSL data remains responsible for expressing primitive-to-primitive calls.
- The fix does not duplicate insert intrinsics in conversion bodies.

The most important hygiene property is that there is now one parser for call
selector syntax, one evaluator for vector/type query semantics, and one scanned
TSIL segment sequence shared by dependency extraction and backend lowering for a
selected body. This reduces drift between call lowering and dependency pruning
while avoiding redundant lexical scans.

The later `regions.py` cleanup also reduces the review surface of the lowering
slice without changing the source/lowering/backend boundary. It is a module
organization change, not a semantic rewrite.

## Suggested Follow-Up

Before committing, a follow-up agent should:

1. Run full `tslc/tests/test_build_verify.py` with a fresh `--basetemp` in an environment that can allow more than 40 minutes, or split the file deliberately if full-file runtime remains impractical.
2. Re-run `git diff --check` after any further edits.
3. Keep old vector query forms unsupported unless the user explicitly revises the decision.

### Diagnostic Provenance Slice

The diagnostic provenance slice now carries source-authored object provenance
past parsing without changing selection, lowering, rendering, or generated text.

Implemented pieces:

1. `tslc.diagnostics.SourceSpan` is the stable domain provenance value,
   separate from parser-private `ParsedTslSourceSpan`.
2. `source_location(...)` and `diagnostic_at(...)` keep diagnostics on the
   existing `Diagnostic.location` point-location contract.
3. `ParsedPrimitiveDeclaration` now exposes `signature_source`; catalog
   promotion converts parser spans into `SourceSpan`.
4. `Primitive`, `Implementation`, `ImmediateParam`, and `GenericParam` carry
   optional source fields so hand-built fixtures stay lightweight.
5. `CatalogBuilder` attaches locations to `params:` diagnostics for duplicate,
   unknown, non-`sImm`, and malformed-range entries.
6. Selector ambiguity warnings use implementation/primitive provenance when a
   source-authored ambiguous body is known.
7. Lowerer early-return diagnostics for bad signatures, unsupported signature
   kinds, signature arity mismatch, missing base/immediate type spellings,
   unsupported representation-change target vectors, and missing top-level
   `emit_return` now attach the nearest available source-authored span.

Focused coverage lives in `tslc/tests/test_diagnostic_provenance.py` and asserts
diagnostic `path`, `line`, and `column` for catalog, selector, and lowerer
diagnostics.

Validation for this slice:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_diagnostic_provenance.py tslc/tests/test_immediate_params.py
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `10 passed`.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py
```

Result: `19 passed`.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `78 passed`.

```bash
git diff --check
```

Result: passed.

Still out of scope for this domain-provenance slice: diagnostic notes or
secondary locations, CLI/API request provenance, build verifier/output writer
locations, generated text changes, source repair, and any broad diagnostic
framework replacement.

### TSIL Region Span Slice

The follow-up TSIL span slice now refines provenance inside implementation body
payloads. It preserves generated text, selection behavior, lowering behavior,
and render structure.

Implemented pieces:

1. `scan(text, source=...)` accepts an optional `SourceSpan` for the body
   payload and keeps the existing `scan(text)` behavior for callers that do not
   have source provenance.
2. `RawText` and `Region` now carry optional `source` spans. Nested payloads,
   `if`/`else` blocks, loop blocks, and switch arms compute spans relative to
   the original body payload, not their local substring.
3. The main lowerer calls `scan(selected.implementation.body_text,
   source=selected.implementation.body_source)`.
4. Dependency extraction accepts an optional body source and passes it to the
   shared scanner; dependency behavior remains source-semantic and diagnostics
   free.
5. `LoweringEffects.error(...)` and `skip(...)` accept optional source spans,
   and region handlers pass `source=region.source` for handler diagnostics.
6. Unsupported-region diagnostics from `ExpressionRenderer` use
   `source=segment.source`.

Focused coverage:

- `tslc/tests/test_tsil_scan.py` asserts nested `RawText` and `Region` source
  spans from a synthetic body payload.
- `tslc/tests/test_diagnostic_provenance.py` asserts an unresolved inner
  `value<generation>(...)` handler diagnostic points at the exact query island,
  not the body start.

Validation for this slice:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_diagnostic_provenance.py
```

Result: `14 passed`.

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `10 passed`.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py
```

Result: `19 passed`.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests/test_immediate_params.py
```

Result: `5 passed`.

```bash
python -m pytest -q tslc/tests --ignore=tslc/tests/test_build_verify.py
```

Result: `80 passed`.

```bash
git diff --check
```

Result: passed.
