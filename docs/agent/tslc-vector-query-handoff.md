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

## 2026-06-24 — Typed Implementation Safety Contract

The implementation safety contract and required-feature call propagation are
now typed through catalog promotion, selection/lowering, dependency
propagation, and Rust rendering.

Implemented pieces:

1. `ImplementationSafety` carries `internal_unsafe`, `caller_unsafe`, and
   reason labels on catalog implementations and lowered specializations.
2. Selector-level `safety:` blocks are parsed as implementation metadata,
   inherit down nested selector entries, and are structurally validated.
3. Lowering combines source safety with inferred effects: intrinsics and memory
   regions mark internal unsafe, and raw-pointer parameter signatures infer a
   caller safety contract.
4. Selection preserves the concrete feature flags selected from
   extension/type-scoped `requires` clauses, and lowering carries them on
   `LoweredSpecialization.required_features`.
5. After unresolved callees are pruned, the pipeline propagates live call-graph
   facts bottom-up to a fixpoint. Unsafe callee metadata becomes an internal
   unsafe dependency plus `unsafe_callee` reason on callers. Required feature
   flags propagate through the same graph, so `prim1 -> prim2 -> primX`
   carries `primX`'s architecture requirements back to `prim1`.
6. Public `caller_unsafe` does not automatically propagate; safe wrappers may
   discharge raw-pointer callees with locally-owned storage.
7. The Rust renderer emits `unsafe fn` trait methods, impl methods, wrappers,
   and free functions from lowered caller-safety facts only.
8. The primitive corpus now carries explicit local `safety:` metadata beside
   every implementation body. The current corpus has 1,327 primitive
   implementation bodies and 1,327 local safety blocks.
9. Rust calls to caller-unsafe generated wrappers are lowered as local typed
   unsafe call-site render fragments. If the whole body already renders inside
   an unsafe frame, those local fragments suppress their own `unsafe { ... }`.
   This removes the nested `MaybeUninit`/callee-call warning pattern from
   `to_array` and similar wrappers while keeping transitive `unsafe_callee`
   safety reasons visible.
10. Generated verification profiles use the machine profile feature set plus
    propagated required features from live lowered specializations.

Focused coverage:

- `tslc/tests/test_safety_contract.py` covers safety promotion/inheritance,
  malformed safety diagnostics, misplaced body-nested safety diagnostics,
  recursive call-fact propagation for safety metadata and required features,
  effective verification profile features, the runtime/immediate overload
  safety-key regression, Rust unsafe signature rendering, corpus-local safety
  coverage, direct corpus facts for intrinsic, memory, and raw-pointer safety,
  and source-backed local unsafe lowering for `call<primitive=store>`.
- `tslc/tests/test_render_model.py` covers typed local unsafe render fragments
  suppressing themselves inside an already unsafe Rust body frame.
- Generated load/store, masked load/store, allocation, shift, and masked-value
  build checks cover raw-pointer caller safety, safe wrapper discharge
  behavior, and immediate intrinsic unsafe frames.

Validation:

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

Result: passed all targeted validations, including 203 non-build tests and 53
generated-build tests.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends rust --output-root ./tslctmp/TEST --test --value-test-warnings
```

Result after local unsafe call-site rendering: passed with `0` Rust
`unnecessary unsafe` warnings. Rust value-test planning still reports the known
unsupported-case warnings for backend gaps.

Metadata audit maintenance tooling is implemented as
`python -m tslc.maintenance.metadata_audit`. It reports typed suggestions for
source-owned `safety:` and `requires` metadata, supports check-only mode,
interactive accept/skip/diff prompts, and automatic application of applicable
suggestions. Automatic safety edits cover direct `intrin<`, `mem<`, and pointer
signature facts. Requirement suggestions compare direct source requirements
with transitive lowered call requirements; automatic `requires` edits are
limited to simple local `requires [..]` lines or leaf-selector insertions, while
scoped/broad forms remain manual suggestions.

Maintenance scripts are now consistently package-owned under
`tslc/src/tslc/maintenance/`. The coverage inventory tool moved from the
repo-local `tslc/tools/coverage_inventory.py` script path to
`python -m tslc.maintenance.coverage_inventory`.

Focused validation for the metadata audit tool:

```bash
python -m pytest -q tslc/tests/test_metadata_audit.py
```

Result: `3 passed`.

Real-corpus safety audit:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.metadata_audit --sources tsldata --checks safety --machine-profiles supplementary/buildsystem/machine_profiles.json
```

Result: `0 suggestion(s), 0 applicable`.

Focused real-corpus requires smoke:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.metadata_audit --sources tsldata --checks requires --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles avx2 --backends cpp --types si32 --primitives add
```

Result: `9 suggestion(s), 0 applicable`; all were low-confidence manual
suggestions for broad/scoped selector shapes.

Full current validation after adding the metadata audit tool:

```bash
./verify.sh
```

Result: passed all targeted validations, including 207 non-build tests and 53
generated-build tests.

The value-test completeness campaign now has a hard typed C++/Rust AVX2 parity
gate for the current corpus. `ValueTestCoverageEntry` uses a typed status
vocabulary and records the planned case kind, `ValueTestParityEntry` groups one
authored value-test identity across backends, and `tslc.value_tests.coverage`
exposes `parity_inventory(...)` and `parity_gaps(...)`. The full-corpus AVX2
parity test requests both C++ and Rust and requires zero missing authored
tests, zero authored-unplanned cases, zero backend-unsupported cases, matching
emitted case counts, and no parity gaps. Rust now emits every current planned
value-test case kind, with the same single compile-only smoke case as C++.

Focused validation:

```bash
python -m pytest -q tslc/tests/test_value_tests.py
./verify.sh
```

Results: focused value-test/planning pytest passed with `19 passed`. A full
Rust AVX2 value-test execution smoke over all 89 selected primitives reported
`rust compile_only_emitted=1` and `rust emitted=1107`, then built and ran with
zero verification diagnostics and zero warning markers. `./verify.sh` passed
with 214 non-build tests and 53 generated-build tests.

### Primitive Value-Test Source Shape Cleanup

The primitive value-test source contract has been simplified after the coverage
discussion:

1. Authored primitive tests now use required semantic `tags [...]`.
2. Source tests no longer carry `test_name`, `lane_set`, or `lanes`.
3. `CatalogBuilder` derives `TestCase.name` from primitive name, type tag,
   typed axes (`extension`, `to_type`, `to_extension`, `index`, `attrs`), and
   either optional `id` or the tag list.
4. `CatalogBuilder` infers promoted `TestCase.lanes` from typed test shape.
   `lane_count` remains only as an explicit escape hatch for mask-only or
   otherwise ambiguous cases.
5. Duplicate derived case names are catalog errors.
6. Value-test render plans no longer add source-order indexes to generated test
   function names; duplicate semantic ids must be fixed in source data.

New/changed implementation files:

- `tslc/src/tslc/catalog/test_cases.py`
- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/builder.py`
- `tslc/src/tslc/catalog/validation/schema_validation.py`
- `tslc/src/tslc/value_tests/case_plans.py`
- `tsldata/primitives/**/*.tsl`

Focused validation so far:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
```

Result: `20 passed`.

```bash
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py tslc/tests/test_catalog_tests.py tslc/tests/test_determinism.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
```

Result: `46 passed`.

```bash
python -m pytest -q --basetemp=/tmp/tslc-pytest-value-build \
  tslc/tests/test_value_test_planning.py \
  tslc/tests/test_value_tests.py \
  tslc/tests/test_build_verify.py
```

Result: `63 passed`.

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

Result: passed with `load 41`, `parse 0`, `build 0`, and `validate 0`.

```bash
env TSLC_VERIFY_WORKERS=1 ./verify.sh
```

Result: passed with 179 non-build tests, 53 generated-build tests, and the
script's architectural grep guards. An earlier wrapper attempt hit stale
`tslctmp/pytest_build_verify` cleanup state; after that base disappeared, the
clean wrapper rerun passed.

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
- `intrinsics.py`: `intrin` lowering for direct and `build[...]` intrinsic calls.
- `declarations.py`: `var` and `let` lowering.
- `masks.py`: `mask` lowering.
- `casts.py`: `cast` lowering.
- `calls.py`: primitive `call` lowering.
- `control.py`: `if`, `assume_aligned`, `loop`, and `switch` lowering.
- `queries.py`: `type<generation>` and `value<generation>` region lowering.
- `returns.py`: `complete` lowering.
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
the stable `tslc.lower.regions` facade and that the facade exposes the default
region lowerers, from `intrin` through `complete`.

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

### Native NEON Fixed-Width Codegen Slice

The NEON profile now emits native fixed-width extension substrates instead of
only scalar/generic fallback coverage.

Implementation notes:

1. `Extension` promotes `vector_register_types` and backend headers from
   `tsldata/extensions/extension.tsl` into typed catalog metadata.
2. Lowering records each specialization's concrete `register_spelling`, so
   Rust backend rendering consumes an already-decided register type.
3. C++ profile rendering registers non-x86 fixed native extension tags from
   typed register metadata and includes extension-owned C++ headers such as
   `<arm_neon.h>`.
4. Rust profile rendering registers `Neon` from typed register metadata and
   imports `core::arch::aarch64::*` for ARM-profile modules.
5. `SupportPolicy` now admits fixed-width `arm` extension substrates while
   keeping scalable vectors such as SVE deferred.
6. NEON source bodies reached by the `add` closure were repaired with existing
   typed TSIL forms: `blend` uses `intrin<vbslq, build[suffix=base::in]>`,
   NEON `reinterpret` uses semantic bitcast, and NEON `set_undef` uses a typed
   uninitialized register declaration.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_profile_rendering.py tslc/tests/test_value_test_planning.py tslc/tests/test_safety_contract.py
```

Result: `43 passed`.

```bash
./verify.sh
```

Result: passed all targeted validations: `240` non-build tests collected, `5`
value-test build/run checks run serially, and `53` generated-build tests
passed across the generated-build shards.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends rust --output-root /tmp/tslc-neon-native-test --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: generated `878` Rust specializations, cross-built the NEON-profile
test binaries for `aarch64-unknown-linux-musl`, ran them through
`qemu-aarch64 -cpu cortex-a76`, and passed `229` generated value tests.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --profiles neon --primitives add --backends cpp,rust --output-root /tmp/tslc-neon-native-smoke --value-test-warnings
```

Result: generated native C++ and Rust NEON profile artifacts. The generated
C++ header contains `#include <arm_neon.h>`, `struct neon`, and
`simd<int32_t, neon>` with `register_type = int32x4_t`; the Rust module
contains `pub struct Neon`, `Simd<i32, Neon>`, and
`core::arch::aarch64::vaddq_s32`.

Known follow-ups:

- C++ NEON runtime verification still needs a clang-compatible aarch64 C++
  sysroot/standard library.
- SVE/scalable-vector emission remains deferred for a separate design pass.

### ARM Emulator Verification Boundary

The verifier now treats SDE and QEMU as one typed emulator concept instead of
an SDE-specific profile field plus ad hoc runner logic.

Implemented pieces:

1. Machine profiles carry optional `emulator {kind, profile, args}` metadata.
   Current x86 profiles migrated from `sde "chip"` to
   `emulator {"kind": "sde", "profile": "chip"}`.
2. The `neon` machine profile carries
   `emulator {"kind": "qemu-aarch64", "profile": "cortex-a76"}`.
3. `VerifyProfile` carries typed `VerifyEmulator` metadata plus optional C++ and
   Rust target metadata. Executable paths stay in `BuildVerifierConfig`.
4. CLI/API verification accepts `--qemu-aarch64`, `--cpp-target`,
   `--rust-target`, and `--rust-linker` overrides while preserving `--sde`.
5. SDE preserves the previous command shape. C++ wraps `ctest`; Rust builds
   tests with `cargo test --no-run --message-format=json` and then runs the
   produced test binaries through SDE.
6. QEMU uses the same Rust no-run path, but C++ configures
   `CMAKE_CROSSCOMPILING_EMULATOR` so host `ctest` stays native and CMake wraps
   only the generated aarch64 test executable.
7. Aarch64 C++ verifier profiles use `aarch64-linux-gnu` and ARM
   `-march=...` flags; targeted C++ verification defaults to `clang++` unless
   the caller explicitly chooses a compiler.
8. Aarch64 Rust verifier profiles use `aarch64-unknown-linux-musl` and
   `rust-lld`, which produces static binaries runnable by `qemu-aarch64` in the
   current environment.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_catalog_validation.py::test_machine_profile_emulator_metadata_is_validated tslc/tests/test_cli.py tslc/tests/test_profile_rendering.py
```

Result: `27 passed`.

```bash
./verify.sh
```

Result: passed all targeted validations: `238` non-build tests collected, `5`
value-test build/run checks run serially, and `53` generated-build tests
passed across the generated-build shards.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends rust --output-root ./tslctmp/ARM_RUST_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: Rust cross-built aarch64 musl test binaries with `rust-lld`, ran them
through `qemu-aarch64 -cpu cortex-a76`, and passed `150` generated value tests
for the NEON-profile `add` slice.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends cpp --output-root ./tslctmp/ARM_CPP_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: QEMU/CMake wiring was exercised, but clang failed at the external C++
toolchain boundary because no aarch64 C++ sysroot/standard-library headers are
installed (`fatal error: 'array' file not found`). The verifier path is wired;
the environment still needs an aarch64 C++ sysroot before C++ ARM value tests
can run.

Known follow-ups:

- Native ARM extension emission is still not enabled in the support policy.
  The Rust QEMU proof exercises the NEON machine profile and generated
  fallback coverage, not a native `Simd<_, Neon>` register substrate.
- A later ARM slice should promote extension-owned vector register spellings
  into typed render metadata so C++ and Rust can register `neon`/`sve`
  substrates without primitive-name branches.
- C++ ARM runtime validation needs a clang-compatible aarch64 C++ sysroot.

### Source Specialization Requires Follow-Up

The focused source-owned feature-tier pass added SSE4.1 fast paths for signed
SSE `cast` and `to_mask` cases while leaving lower-feature fallbacks in place.
`compress` and `blend` tiering was revalidated without adding redundant
`avx2_vl` / `sse_vl` child-extension bodies where inherited `avx2` / `sse`
bodies already cover the profile.

Validation:

```text
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `21 passed`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast,to_mask,compress,blend --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `47258` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ CTest and Rust value tests ran through
SDE for x86 profiles, with `neon` skipped because there is no x86 SDE chip
alias.

```text
python -m compileall -q tslc/src/tslc
git diff --check
```

Result: passed.

### Source Specialization Fallback Audit

A follow-up audit scanned fallback-shaped x86 implementation bodies after the
SSE4.1 source-specialization slice. The inventory looked for selected
`sse`/`avx2`/`avx512`/`sse_vl`/`avx2_vl` implementation entries containing
array round-trips, backend loops, `mask<test>`, generation loops, or
`set_zero` composition.

The actionable cleanup was `masked_set1`: the x86 bodies for `avx512`, `avx2`,
and `sse` performed a manual array round-trip and lane loop even though the
same source file already expressed the exact operation as
`blend(mask, data, set1(scalar))` for another backend. `masked_set1` now uses
one shared `[avx512, avx2, sse, neon]` body that composes the existing typed
`blend` and `set1` primitives. Backend-specific blend/broadcast selection stays
owned by those primitives and their `requires` fields.

The fallback-shaped inventory dropped from `314` x86 entries across `38`
primitives to `311` entries across `37` primitives. The remaining buckets were
left alone because they are deliberate lower-feature fallbacks or need a
dedicated semantic slice, not a safe drive-by specialization:

- packed `compress` / `expand` load-store already have AVX-512/VL native tiers;
- `conflict`, `popcnt`, and `lzc` already use direct feature tiers where the
  ISA provides them and fallback elsewhere;
- `blend`, `equal`, `less_than`, `to_integral`, and `to_mask` keep lower-feature
  fallback/composition paths where direct instructions require newer features;
- `convert_up` / `convert_down`, shifts, horizontal reductions, gather/scatter,
  extraction, and conversion-load cases have partial direct tiers plus broad
  fallbacks whose further optimization should be reviewed primitive by
  primitive;
- `to_array`, `from_array`, `mask_false`, `unequal_zero`, and `to_ostream`
  remain representation or helper compositions rather than missing intrinsic
  implementations.

Validation:

```text
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `22 passed`.

```text
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives masked_set1 --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `32776` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ CTest and Rust value tests ran through
SDE for x86 profiles, with `neon` skipped because there is no x86 SDE chip
alias.

### Source-Owned Feature-Gated Specialization Follow-Up

The source corpus now adds feature-gated fast paths where a stronger hardware
feature has a better implementation while the lower-feature fallback remains
available:

1. `cast` on SSE has signed `f32 -> si32` and `f64 -> si32` SSE4.1 fast paths
   using explicit rounding-to-zero plus `cvt*` intrinsics. Unsigned destinations
   stay on the portable fallback path because the corresponding SSE intrinsic
   spelling is not generally available.
2. `to_mask` on SSE has SSE4.1 fast paths for `?i64` and `f64`; SSE/SSE2
   lane-array construction remains the fallback. The new fast paths spell the
   full requirement set (`sse`, `sse2`, `sse4_1`) so the selector's
   more-required-features tie-break chooses them when available.
3. `compress` and `blend` were reviewed in the same pass. Their existing
   native/fallback tiering already carries the needed `requires` layering, so
   no redundant source bodies were added there.

Validation for this follow-up:

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py
```

Result: `21 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast,to_mask,compress,blend --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated `47258` specializations across `83` artifacts and ended with
`build/test-verified 152 commands`; C++ and Rust value tests ran through Intel
SDE for x86 profiles, with `neon` skipped because there is no x86 SDE chip
alias. A first sandboxed attempt failed with SDE `PTRACE_ATTACH` errors; the
same command passed when rerun with elevated execution permissions for SDE.

```bash
python -m compileall -q tslc/src/tslc
git diff --check
```

Result: passed.

### SDE Value-Test Execution Slice

The after-write verifier now supports SDE-backed value-test execution for
SDE-annotated x86 machine profiles. This closes the current runtime coverage
goal for provided x86 profiles by running generated value tests for both C++
and Rust through Intel SDE when native host ISA support is unavailable.

Omitting `--profiles` on the CLI requests every loaded machine profile. The API
represents that as `profiles=None`; explicit `--profiles` remains only a
narrowing mechanism. In SDE value-test mode, non-generic profiles without an
SDE chip alias, such as `neon`, are generated but skipped by the verifier with
a visible `verify-skip` note because x86 SDE cannot emulate them.

Implemented pieces:

1. `MachineProfile` accepts optional validated `sde` chip aliases from
   `supplementary/buildsystem/machine_profiles.json`.
2. C++ and Rust profile render data pass the chip alias into `VerifyProfile`.
3. `tslc.cli --test --sde [PATH]` passes an explicit emulator executable into
   `verify_project`.
4. C++ value-test commands wrap `ctest` as `sde -chip -- ctest ...` for
   profiles with an SDE alias.
5. Rust value-test commands build tests with
   `cargo test --no-run --message-format=json`, parse compiler-artifact test
   executables, and run each binary through the same SDE prefix.
6. Missing SDE executables and missing Rust test binaries produce structured
   verifier diagnostics.
7. Source-owned feature metadata exposed by the SDE sweep was corrected in
   machine profiles and `.tsl` implementation selectors rather than hidden in
   verifier exceptions.
8. Non-generic profiles without SDE aliases are skipped during SDE value-test
   verification instead of being built with an incompatible host toolchain.

SDE runtime sweep:

```text
sse, sse2, sse3, avx, avx2, knl, kml, skylake, cannonlake,
cascadelake, cooperlake, icelake-rockerlake, tigerlake, zen4,
sapphirerapids, zen5
```

Result: every profile generated, wrote artifacts, and verified C++ plus Rust
value tests through `/opt/intel-sde/sde64` with zero diagnostics.

Focused validation:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_build_verify_config.py tslc/tests/test_catalog_validation.py::test_machine_profile_sde_metadata_is_validated tslc/tests/test_cli.py
```

Result: `30 passed`.

Full validation:

```bash
./verify.sh
```

Result: passed all targeted validations, including 220 non-build tests and 53
generated-build tests.

Default-profile follow-up:

```bash
python -m pytest -q tslc/tests/test_cli.py tslc/tests/test_profile_rendering.py tslc/tests/test_build_verify_config.py
```

Result: `21 passed`.

The exact C++ SDE CLI command without `--profiles`:

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. It generated 59 artifacts, emitted headers for every loaded
profile including `tsl_neon.hpp`, ran all SDE-annotated x86 C++ value tests,
and skipped `neon` with a visible `verify-skip` note because no x86 SDE chip
alias exists for that AArch64 profile.

### Primitive Finalization: `reinterpret`

The primitive-by-primitive finalization campaign has started with
`reinterpret`. The main coverage blocker was not a primitive-specific compiler
rule: inline `tsil "..."` implementation bodies were promoted from raw payload
source text, so escaped source quotes such as `infix_sep=\"\"` reached the TSIL
scanner and prevented top-level `complete(...)` recognition in otherwise valid
bodies. The parser now stores decoded inline scalar text in
`ParsedImplementationBodyEnvelope.payload_text` while keeping
`payload_source` as the raw source span for diagnostics.

After that source-boundary fix, the newly emitted x86 same-type float
reinterpret bodies exposed an invalid source intrinsic spelling
(`_mm*_castps_ps` / `_mm*_castpd_pd`). The x86 `f? -> f?` branch now uses the
no-instruction bitcast path instead of an intrinsic and records no internal
unsafe reason.

Validation:

```bash
python -m pytest -q tslc/tests/test_parse_arithmetic.py
```

Result: `3 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives reinterpret --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 33,288 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports
`reinterpret` with `0` skipped slots and the full inventory moved to
`65840 / 67052` lowered slots.

### Primitive Finalization: `compress`

The next primitive-finalization slice completed `compress`. Its scalar body
still used raw target-language `return` statements after the active TSIL
completion directive had become `complete(expr)`, so every scalar slot skipped
as "no top-level complete". The scalar implementation now computes a local
`result`, updates it through a runtime `if (mask)`, and emits
`complete(result)`.

The remaining skipped slots were AVX-512VL-derived `avx2_vl` / `sse_vl` byte
and word fallback paths. Those inherited the generic AVX2/SSE array fallback,
which used `mask<test>` even though AVX-512VL masks use the
`native_predicate_by_lanes` representation. A source-owned VL fallback now
calls `to_integral[Vec]` once and tests the resulting integral mask bits inside
the array compaction loop.

Validation:

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives compress --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 31,236 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports `compress` with
`0` skipped slots and the full inventory moved to `65976 / 67052` lowered
slots. The `unsupported mask<test>` taxonomy category disappeared from the
current inventory.

### Primitive Finalization: `cast`

The next primitive-finalization slice completed `cast` and also removed the
same call-type-argument blocker from `convert_down`.

The first blocker was generic TSIL call-lowering capability, not a
primitive-specific `cast` rule. Source bodies such as
`call<primitive=extract[Vec, sse, 0]>(data)` use a target vector plus a literal
lane index as forwarded wrapper arguments. `CallLowerer` now accepts decimal
integer call-bracket entries as render-ready template/const arguments; extension
names were already resolved through the typed catalog. A regression in
`test_masks_and_calls.py` asserts the real C++ and Rust `extract` call shapes
and verifies that this no longer records a `call type-args` skip.

The second blocker surfaced after those bodies lowered: `value<backend>(
x86::mm_fround_to_zero)` was present in source but not evaluated. The query
evaluator now resolves zero-argument `x86::...` backend value leaves through the
active backend translation template named `value_...`. The emitted C++ and Rust
spellings still come from `translate_cpp.tsl` / `translate_rust.tsl`, not from
hard-coded lowerer strings. A lowering regression asserts `_MM_FROUND_TO_ZERO`
and `core::arch::x86_64::_MM_FROUND_TO_ZERO` on real `cast` slots.

With those skips gone, build verification exposed source bodies that used
instructions beyond their declared profile requirements. The `avx2` `f32 ->
ui32` path now uses the existing portable array round-trip fallback instead of
the AVX-512VL-only `_mm256_cvtps_epu32`. The SSE `f32 -> ?i32` and `f64 ->
?i32` paths also use the same fallback instead of SSE4.1 round intrinsics, so
SSE2/SSE3 profiles compile and run under SDE.

Validation:

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py::test_call_type_args_accept_extension_and_literal_index tslc/tests/test_select_and_lower.py::test_backend_value_query_uses_backend_translation_template
```

Result: `2 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives cast --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 40,474 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports `cast` and
`convert_down` with `0` skipped slots and the full inventory moved to
`66310 / 67062` lowered slots. The `call type-args`, `unresolved value query`,
`no top-level complete`, and `unsupported mask<test>` taxonomy categories are
no longer present in the current inventory.

### Primitive Finalization: `hand` / `hor`

The next primitive-finalization slice completed `hand` and also cleared the
same unresolved type-query gap from `hor`.

The blocker was generic TSIL query vocabulary, not a primitive-specific rule.
Float bitwise horizontal reductions need a generation-time carrier type:
`select(type::is_same(base::in, f32), ui32, ui64)`. `QueryEvaluator` now has a
small typed `select(cond, then, else)` query function that folds only when the
condition is a `BoolValue` and both branches produce the same query-value kind.
This lets the existing source bodies resolve `UnsignedT` without renderer or
primitive-name inference.

The newly lowered Rust paths exposed a backend syntax issue for source-owned
raw-memory fallbacks. Rust pointer casts of address expressions such as
`cast<reinterpret>(void*, &result)` now render through
`core::ptr::addr_of_mut!(result).cast::<u8>()`; const address expressions use
`core::ptr::addr_of!(...).cast::<u8>()`. Ordinary pointer expressions still use
the normal raw-pointer cast path.

Validation:

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py
```

Result: `22 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives hand --machine-profiles supplementary/buildsystem/machine_profiles.json --backends rust --output-root ./tslctmp/TEST_HAND_RUST --test --value-test-warnings
```

Result: passed with `build/test-verified 19 commands`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives hand --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 31,268 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports `hand` and `hor`
with `0` skipped slots and the full inventory moved to `66454 / 67062` lowered
slots. At that point, the only non-closure skip category left was
`unresolved type query` with 48 candidate slots, owned by `lzc_scalar`.

### Primitive Finalization: `lzc_scalar`

The next primitive-finalization slice completed `lzc_scalar` and removed the
last non-closure skip category from the current coverage inventory.

The blocker was not a missing compiler query. The source body still called the
old helper shape `details::clz<T, vector::offset_base>(...)`, but the C++ and
Rust helper implementations are already width-aware: C++ dispatches via
`sizeof(T)` and Rust uses the scalar type's `leading_zeros` implementation.
The source body now keeps the typed unsigned carrier selected by
`select(type::is_same(...), ui32, ui64)`, initializes it with `var<infer>`, uses
`mem<copy>` to bit-copy the float scalar into that carrier, and calls
`details::clz(bits)`.

This deliberately does **not** add a `vector::offset_base` query to the
compiler. The old argument was vestigial source debt, and removing it keeps the
query vocabulary smaller.

Validation:

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py::test_lzc_scalar_float_bitwise_path_does_not_need_offset_base
```

Result: `1 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives lzc_scalar --machine-profiles supplementary/buildsystem/machine_profiles.json --backends rust --output-root ./tslctmp/TEST_LZC_RUST --test --value-test-warnings
```

Result: passed with `build/test-verified 19 commands`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives lzc_scalar --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 30,524 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports all 89 primitives
as `VERIFIED`, with `66594 / 67062` lowered slots. The only remaining skip
taxonomy category is `pruned (closure)`, which records dependency-closure
drops where a callee is unavailable in a profile and is structural rather than
a lowering defect.

### Primitive Finalization: `to_array` AVX Requirement

The next primitive-finalization micro-slice reduced closure-pruned slots by
aligning `to_array` requirements with the implementation it actually delegates
to.

The remaining closure inventory showed many AVX-profile `avx2` byte/word
fallback bodies pruned because they called `to_array[Vec]` for `si8`, `ui8`,
`si16`, or `ui16`. The `to_array` implementation simply creates a temporary
array and calls `store(tmp.data(), a)`. `store` already declares AVX-only
support for every AVX2 integer width, including byte and word lanes, because
the relevant 256-bit integer register store is available under the existing
AVX profile support. `to_array` was stricter than its callee and required
`avx2` for byte/word lanes.

The `avx2` `to_array` integer requirement is now the same for all integer type
tags: `[avx]`. This is a source metadata correction, not a compiler special
case. It also follows the extension-inheritance rule: do not add child-specific
fallback bodies when the parent body and its actual callees are already valid.

Validation:

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_to_from_array_roundtrip_builds
```

Result: `1 passed`. The test now includes the `avx` profile so this requirement
boundary is build-verified.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives to_array,from_array --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: passed. The run generated 29,812 specializations across 83 artifacts,
ran C++ value tests through SDE for every SDE-annotated x86 profile, ran Rust
test binaries through SDE, skipped `neon` visibly because no x86 SDE chip alias
exists, and reported `build/test-verified 152 commands`.

`python -m tslc.maintenance.coverage_inventory` now reports all 89 primitives
as `VERIFIED`, with `66722 / 67070` lowered slots. Remaining closure-pruned
slots dropped from 468 to 348.

### CLI Value-Test Flag Slice

The CLI now exposes the existing value-test path through `--test`.

Implemented pieces:

1. `--test` requires `--output-root` so artifacts are written before build/test
   verification.
2. CLI generation passes `test_harness=True` and enables value-test planning
   warnings when `--test` is present.
3. CLI after-write verification runs when either `--verify` or `--test` is
   present, and passes `run_value_tests=True` only for `--test`.
4. CLI output says `building and running generated value tests` before
   invoking the verifier, prints captured stdout/stderr for verifier commands
   whose step is `test` (`ctest` and value-enabled `cargo test`), and reports
   `build/test-verified ... commands` after success.
5. Omitting `--primitives` now means the pipeline starts from every primitive
   in the loaded catalog. An explicit `--primitives ...` list narrows the run
   for focused smoke tests. The all-corpus default is resolved after catalog
   building, not by a CLI-side source scan.
6. A `--test` run returns failure for any verifier diagnostic, so failed
   generated value-test commands cannot still produce `build/test-verified`.
7. No new pipeline mode, API wrapper, verifier path, or source test semantics
   were added.

Focused coverage:

- `tslc/tests/test_cli.py` asserts the `--test` mapping to existing generation
  and verifier options.
- `tslc/tests/test_cli.py` asserts `--test` exits before generation when
  `--output-root` is missing.
- `tslc/tests/test_cli.py` asserts captured test-command output is printed and
  non-test build output remains quiet.
- `tslc/tests/test_cli.py` asserts omitted `--primitives` delegates to the API
  all-catalog default.
- `tslc/tests/test_cli.py` asserts value-test verifier diagnostics fail the CLI
  even when their diagnostic severity is warning.

Validation for this slice:

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests/test_cli.py
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_cli.py
```

Result: `2 passed`.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
```

Result: `3 passed`.

```bash
./verify.sh
```

Result: passed all targeted validations, including 165 non-build tests, 53
generated-build tests, and the architectural grep guards.

```bash
./verify.sh
```

Result: passed all targeted validations, including 163 non-build tests, 53
generated-build tests, and the architectural grep guards.

### Unified Intrinsic Build Slice

Intrinsic lowering now uses one TSIL keyword:

- `intrin<NAME>(...)` is a direct intrinsic call. The backend may qualify the
  name, such as Rust's `core::arch` path.
- `intrin<BASE, build>(...)` is a composed intrinsic call using backend and
  extension defaults for prefix and suffix.
- `intrin<BASE, build[prefix=..., infix=..., suffix=..., post=..., immediate(N)=...]>`
  applies explicit build modifiers. Omitted build fields keep their defaults;
  explicit empty text suppresses that field.
- `suffix=` and `infix=` accept either text values or typed generation values.
  Type values are mapped through the selected extension's intrinsic suffix
  metadata. `prefix=` remains text-only; omit it when the selected extension's
  default prefix is desired.

Implemented pieces:

1. `IntrinLowerer` owns both direct and built intrinsic calls through an
   `IntrinsicSelector`.
2. The old `IntrinComposeLowerer` was removed from the scanner/registry
   surface.
3. `intrin::prefix` is a normal query function, so explicit
   `prefix=value<backend>(intrin::prefix)` resolves through the selected
   backend/extension instead of being ignored or special-cased.
4. The primitive corpus was migrated from `intrin_compose<...>(...)` to
   `intrin<..., build...>(...)`.
5. Redundant backend-value wrappers were removed from the primitive corpus:
   `suffix=`/`infix=` now use direct typed expressions such as
   `base::signed_of(base::in)`, `base::in`, `ToBase`, `si32`, and `si64`.
   Named suffix policies remain explicit, for example
   `intrin::suffix("stream")`.
6. A corpus guard fails if `intrin_compose<` appears in primitive TSIL bodies.
7. Selector-term splitting lives in `tslc.lower._text.split_selector_terms`;
   `IntrinLowerer` keeps only intrinsic-specific selector/modifier
   interpretation.

Focused coverage:

- `tslc/tests/test_tsil_scan.py` asserts the scanner sees one `intrin` region
  and keeps `build[...]` selectors raw.
- `tslc/tests/test_select_and_lower.py` asserts explicit build prefix/suffix
  lowering, typed `suffix=`/`infix=` lowering, and text-only `prefix=`.
- `tslc/tests/test_diagnostic_provenance.py` keeps unresolved build suffix
  diagnostics anchored on the intrinsic region.
- `tslc/tests/test_tsil_statement_terminators.py` guards the corpus migration.
- `tslc/tests/test_lower_text.py` covers shared selector splitting for
  `build[...]`, top-level whitespace, quoted strings, and nested selectors.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_parse_arithmetic.py tslc/tests/test_tsil_scan.py::test_nested_modifier_selector_kept_verbatim tslc/tests/test_diagnostic_provenance.py::test_intrin_build_unresolved_suffix_has_region_source_location
```

Result: `7 passed`.

```bash
python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_tsil_scan.py::test_intrin_build_selector_is_raw_and_args_recurse tslc/tests/test_tsil_scan.py::test_nested_modifier_selector_kept_verbatim
```

Result: `8 passed`.

```bash
python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_parse_arithmetic.py tslc/tests/test_diagnostic_provenance.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py
```

Result: `60 passed`.

```bash
git diff --check
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_cast_reinterpret_builds tslc/tests/test_build_verify.py::test_gather_scatter_builds tslc/tests/test_build_verify.py::test_set_builds tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
```

Result: `6 passed`.

```bash
env TSLC_VERIFY_WORKERS=1 ./verify.sh
```

Result: passed all targeted validations, including 167 non-build tests and 53
generated-build tests.

### Call Selector Comma Migration Slice

`call` selector clauses now use comma separation, consistent with the current
`intrin<BASE, build[...]>(...)` selector surface:

```tsl
call<primitive=load[Vec], attrs[aligned=false]>(ptr)
call<primitive=mov, attrs[mask=zero]>(mask, value)
```

Implemented pieces:

1. `parse_call_selector(...)` accepts `primitive=NAME[...], attrs[...]` and
   rejects the old whitespace-separated `primitive=NAME[...] attrs[...]`
   spelling.
2. The primitive corpus under `tsldata/primitives` was migrated to the comma
   form.
3. `tslc/tests/test_masks_and_calls.py` covers positive parser behavior,
   rejection of the old form, and a corpus guard against reintroducing
   whitespace-separated `call` attribute clauses.

Focused validation:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py::test_call_selector_parser_keeps_syntax_only_shape tslc/tests/test_masks_and_calls.py::test_primitive_corpus_uses_comma_separated_call_attrs tslc/tests/test_masks_and_calls.py::test_type_param_bounds_use_call_regions_not_raw_text
```

Result: `3 passed`.

```bash
python -m pytest -q tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_tsil_scan.py
```

Result: `56 passed`.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_masked_value_ops_build tslc/tests/test_build_verify.py::test_masked_load_store_build tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
```

Result: `4 passed`.

```bash
env TSLC_VERIFY_WORKERS=1 ./verify.sh
```

Result: passed all targeted validations, including 171 non-build tests and 53
generated-build tests.

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
4. Block forms such as `if`, `loop<backend>`, and `switch<compile>` do not gain a
   target semicolon.
5. The primitive corpus under `tsldata/primitives` was normalized so all
   scanner-identified `let<type>` and `var<...>` statement regions carry source
   semicolons. The migration inserted 751 semicolons across 24 primitive files.

Focused coverage:

- `tslc/tests/test_tsil_scan.py` asserts source semicolons are consumed for
  top-level regions and not claimed by nested expression atoms.
- `tslc/tests/test_select_and_lower.py` asserts `let<type>(...);`,
  `var<infer>(...);`, `intrin<...>(...);`, and `complete(...);` keep the
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
  `GenerationResult`. Warnings are surfaced only when explicitly requested with
  `value_test_warnings=True` / `--value-test-warnings`; planning errors remain
  surfaced for ordinary generation. This is intentionally independent of
  `test_harness`, whose job is dependency closure for generated value-test
  binaries.

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
- The 2026-06-24 design-principles follow-up tightened unsupported authored
  case diagnostics: each `tests:` case that cannot produce a backend-supported
  plan now emits `TSL-VALUE-TEST-UNSUPPORTED-CASE`, even when sibling cases for
  the same primitive/profile plan successfully.

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
- `loop<backend>(i, start, end, step) { ... }` emits a normal target-language
  loop.
- `loop<backend, unroll>(i, start, end, step) { ... }` is the same emitted loop
  with an explicit optional unroll hint.
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

## TSIL Backend Loop Surface Cleanup

The current worktree also harmonizes emitted TSIL loops:

- `loop<range>(var, start, end, step) { ... }` is now
  `loop<backend>(var, start, end, step) { ... }`.
- A standalone preceding `loop<unroll>(count)` directive is removed. Explicit
  unroll intent is attached to the emitted loop as
  `loop<backend, unroll>(var, start, end, step) { ... }`.
- `loop<generation>(var, start, end, step) { ... }` is unchanged: it expands in
  the generator and binds the loop variable as a generation-time integer.
- Backend translation metadata now uses `loop_backend`; C++ and C17 also declare
  `loop_backend_unroll`. Rust omits the unroll template and therefore renders a
  normal loop for `loop<backend, unroll>`.
- `LoopLowerer` emits an unroll hint only when the selected backend declares the
  optional unroll template and the loop trip count is generation-known. Symbolic
  counts such as sized-vector `LANES` remain valid normal backend loops.
- The primitive corpus under `tsldata/primitives` has been migrated and guarded
  against reintroducing `loop<range>` or standalone `loop<unroll>`.

Validation for this slice so far:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lane_lists.py tslc/tests/test_tsil_scan.py::test_backend_loop_unroll_selector_captures_block tslc/tests/test_tsil_statement_terminators.py::test_primitive_tsil_uses_backend_loop_surface
python -m pytest -q tslc/tests/test_tsil_statement_terminators.py tslc/tests/test_tsil_scan.py tslc/tests/test_select_and_lower.py tslc/tests/test_generation_conditionals.py tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds
env TSLC_VERIFY_WORKERS=1 ./verify.sh
git diff --check
```

Results: compile passed; the focused loop run passed with 17 tests; the
affected non-build run passed with 60 tests; the full-corpus AVX2 value gate
passed; `verify.sh` passed all targeted validations with 178 non-build tests
and 53 generated-build tests; final diff check passed.

## Design Follow-Up Cleanup

The latest post-change design audit findings have been fixed:

- `tslc.lower._text.split_selector_terms` now splits only on top-level commas.
  `IntrinLowerer` rejects whitespace-separated selector clauses such as
  `intrin<foo build[...]>(...)`, matching the comma-separated source surface
  chosen for `intrin<BASE, build[...]>(...)` and `call<primitive=..., attrs[...]>(...)`.
- Value-test differential planning no longer branches on the source extension
  name `scalar`. Differential candidates are selected from typed extension facts:
  they must be concrete fixed-width vector extensions with a lane-compatible
  `vector_bits` value.
- `tslc.value_tests.case_plans` no longer exposes `simple_case(kind=...)`.
  Case construction now uses explicit per-kind builders such as `store_case`,
  `load_case`, `lane_list_case`, and `mask_to_vector_case`, wired by
  `ValueTestPattern` objects.

Validation for this cleanup:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lower_text.py tslc/tests/test_select_and_lower.py::test_intrin_build_rejects_whitespace_separated_selector_terms tslc/tests/test_select_and_lower.py::test_intrin_build_supports_explicit_prefix_and_suffix tslc/tests/test_select_and_lower.py::test_intrin_build_suffix_and_infix_accept_type_values tslc/tests/test_select_and_lower.py::test_intrin_build_prefix_remains_text_only tslc/tests/test_value_test_planning.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py tslc/tests/test_tsil_scan.py tslc/tests/test_masks_and_calls.py tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_builds tslc/tests/test_build_verify.py::test_load_store_builds tslc/tests/test_build_verify.py::test_convert_builds tslc/tests/test_build_verify.py::test_set_builds
env TSLC_VERIFY_WORKERS=1 ./verify.sh
git diff --check
```

Results: compile passed; focused cleanup tests passed with 14 tests; the
broader TSIL/value-test shard passed with 68 tests; generated-build/value tests
passed with 4 tests; `verify.sh` passed with 179 non-build tests and 53
generated-build tests; final diff check passed.

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
   `complete` now attach the nearest available source-authored span.

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

### Value-Test Completeness Slice

The value-test completeness slice is implemented for the C++ and Rust AVX2
full-corpus gate. The planner now treats coverage as a typed output instead of
a generated source-code heuristic.

Implemented pieces:

1. `TestArg` now promotes source inputs to typed `vector`, `mask`, or `scalar`
   values according to the primitive signature position.
2. `TestCase.role` defaults to `value`; `role "compile"` is accepted for
   deterministic compile-only smoke cases such as `set_undef`.
3. `ValueTestCoverageEntry` records `emitted`, `compile_only_emitted`,
   `missing_authored_tests`, `authored_unplanned`, and `backend_unsupported`
   outcomes. `ValueTestProjectPlan.coverage` is exposed through
   `RenderedProject.value_tests`.
4. The full C++ AVX2 coverage test asserts no missing authored tests, no
   authored applicable-but-unplanned cases, and no backend-unsupported cases.
5. The C++ planner patterns now cover additional typed roles: vector/array
   round trips, scalar results, mask constants and mask/scalar conversions,
   scalar and mask pointer loads/stores, masked contiguous memory operations,
   memory copy, pointer lifetime/free smoke cases, indexed gather/scatter,
   load-convert, stream output, scalar-to-vector constructors, extension
   insert/extract, representation-change cases, and compile-only cases.
6. Profile-specific authored tests are admitted only when the selected
   specialization set contains the matching extension/type/target facts.
7. The primitive corpus has added or repaired completeness tests for
   `from_array`, `lzc_imask`, `lzc_scalar`, `set_undef`,
   `shift_right_imask`, and selected mask-store packed/unpacked cases.
8. `case_plans.py` and `render_cpp.py` were split before becoming new
   monoliths. Shared planner helpers live in `tslc.value_tests.case_helpers`;
   pure C++ formatting helpers live in `tslc.value_tests.render_cpp_helpers`.
9. A focused `store_mask_repr` follow-up makes `packed=false` an explicit source
   layout distinction. Packed cases store the compact integral mask; unpacked
   cases store unsigned lane words through a source-body reinterpret cast, and
   the C++ value-test plan carries the expected unsigned storage type/tag.
10. The mask representation primitives are named `load_mask_repr` and
   `store_mask_repr` to avoid colliding with emitted masked overload names such
   as `store_mask`.

Validation so far:

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_catalog_tests.py tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete
```

Result: `23 passed`.

```bash
python -m pytest -q tslc/tests/test_value_tests.py
```

Result: `3 passed`.

```bash
./verify.sh
```

Result: passed all targeted validations, including 184 non-build tests and 53
generated-build tests across its shards.

After the focused `store_mask_repr` packed-layout follow-up, the exact
`test_full_corpus_builds` regression and the full `./verify.sh` gate were rerun
with the same 184 non-build and 53 generated-build counts.

After the mask-representation primitive rename to `load_mask_repr` /
`store_mask_repr`, targeted value/build tests and `./verify.sh` were rerun
again with the same 184 non-build and 53 generated-build counts.

After the design-principles residual-risk cleanup, `load_mask_repr`
`packed=false` uses explicit unsigned lane-word storage like `store_mask_repr`,
and dependency extraction no longer constructs a backend dialect for
backend-neutral call closure.

After the Rust `load_mask_repr` parity fix, the generic unpacked path indexes a
reinterpreted unsigned lane-word pointer instead of the original vector base
pointer, and AVX2/SSE register-mask comparisons are reinterpreted back to the
current vector mask representation before returning. Targeted
`test_masked_memory_build`, targeted `test_full_corpus_builds`, and the full
`./verify.sh` gate passed; the full gate reported 185 non-build tests and 53
generated-build tests across its shards.

After the TSIL completion directive rename, active value-returning source
bodies use `complete(expr)` instead of an emission-oriented directive name. The
scanner recognizes only `complete`, backend translation metadata uses the
`complete` template key, and the lowerer reports `TSL-LOWER-NO-COMPLETE` when a
value-returning body has no completion directive. Focused TSIL/lowering/catalog
tests, the full non-build suite, and `./verify.sh` passed after the rename.

After the Rust warning hygiene slice, runtime `if` rendering uses backend
translation templates (`if ({cond})` for C++ and `if {cond}` for Rust), Rust
casts wrap only their operand (`({expr}) as Type`), and Rust pointer casts avoid
an extra outer pair of parentheses. Non-mutated `var<infer>` / `var<typed>`
declarations in `tsldata/primitives` now use const forms, and cast-before-shift
source expressions explicitly parenthesize the cast result. Rust `s[]`
parameters render as immutable bindings by default; source bodies that need
`.data()` introduce a mutable local copy explicitly. `var<const_init_register>`
covers zero registers returned without mutation.

The warning-focused Rust CLI value-test run passed, and a quiet all-feature
`cargo test` warning census reported zero `unnecessary parentheses around ...`
warnings and zero `unused_mut` warnings. The remaining Rust warning family is
the separate unnecessary `unsafe` wrapper follow-up. `./verify.sh` also passed
after the warning cleanup, with 191 non-build tests and 53 generated-build
tests across its shards.

Known follow-ups:

- Rust value-test parity is still a separate milestone.
- Rust warning hygiene still has one non-blocking follow-up: make unnecessary
  unsafe wrappers conditional.
- The completeness gate is intentionally C++ AVX2-first; future profiles should
  add their own typed admission rules instead of broadening this gate by source
  primitive name.
- `case_plans.py` is below the module-size guardrail but still dense; future
  additions should prefer new focused helper modules or per-shape builders.

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

### Primitive Finalization Closure Completion

The selected C++/Rust corpus now has exact closure coverage for the probed
profiles without adding generic workaround bodies for inherited `_vl`
extensions. `avx2_vl` still inherits from `avx2`, and `sse_vl` still inherits
from `sse`; explicit child bodies remain reserved for genuinely different
AVX-512VL representation paths.

Source-data fixes in this slice:

1. `blend` has an AVX-only array-roundtrip fallback used by AVX-profile masked
   `mov` composition.
2. `mask_true` and `mask_false` no longer use an unsupported `default`
   requirement key for SSE; the SSE type groups are explicit.
3. `to_integral` has an AVX2 arithmetic fallback using `mask<test>` over
   `vector::length`.
4. AVX-512 float `binary_and`, `binary_or`, and `binary_xor` reinterpret
   through the signed carrier matching the current base width instead of
   hard-wiring a 64-bit carrier.
5. `inv` float requirements now match the AVX-capable callees it composes.
6. SSE `equal` and `less_than` have SSE2-compatible 64-bit lane-array
   fallbacks, and `nequal` can compose those SSE64 comparisons.
7. SSE64 `to_mask` uses lane-array mask construction rather than requiring
   SSE4.1 `cmpeq_epi64`.
8. AVX-512 float `hor` bodies now use canonical
   `var<typed>(UnsignedT, result, ...)` TSIL declarations instead of raw
   C-style `UnsignedT result = ...`, which had rendered invalid Rust once the
   full-corpus build reached those bodies.

Validation for this slice:

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_build_verify.py::test_full_corpus_builds
```

Result: `1 passed`.

```bash
python -m pytest -q tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_coverage_is_complete tslc/tests/test_value_tests.py::test_value_full_corpus_avx2_rust_parity_inventory_is_explicit tslc/tests/test_build_verify.py::test_masked_memory_build tslc/tests/test_build_verify.py::test_to_mask_builds
```

Result: `4 passed`.

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.coverage_inventory
```

Result: wrote `docs/redesign/primitive-coverage-inventory.md` with `89
verified, 0 lowers, 0 partial, 0 none; 67232/67232 slots`.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --primitives blend,mov,load,mask_true,mask_false,to_integral,to_mask,store_mask_repr,load_mask_repr,lzc_imask,tzc,binary_and,binary_or,binary_xor,inv,equal,nequal,less_than,hor --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/TEST --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: generated 83 artifacts and ended with `build/test-verified 152
commands`; C++ CTest and Rust value tests ran successfully through SDE for
annotated x86 profiles, with `neon` visibly skipped because there is no x86
SDE chip alias.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --backends cpp,rust --output-root ./tslctmp/FULL --test --value-test-warnings --sde /opt/intel-sde/sde64
```

Result: with `--primitives` omitted, generated all primitives by default:
220352 specializations across 83 artifacts. C++ and Rust value tests ran
successfully through SDE for annotated x86 profiles, `neon` was visibly skipped
because there is no x86 SDE chip alias, and the command ended with
`build/test-verified 152 commands`.

```bash
git diff --check
```

Result: passed.
