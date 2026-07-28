# tslc — what it is and how it works

A deep-orientation companion to [README.md](README.md) (quick start) and
[CHARTER.md](CHARTER.md) (the design rules). This file explains the *shape* of
the system: what it compiles, the pipeline, the two nested input languages, and
the design decisions that matter.

## What it is

`tslc` is a **compiler that generates a SIMD wrapper library**. It reads a
declarative data language (`.tsl` files under `tsldata/`) describing abstract
SIMD *primitives* (`add`, `sub`, `load`, `gather`, `select`, …) and emits
deterministic, compilable **C++ and Rust** source implementing each primitive
across a matrix of:

- **hardware extensions** — `scalar`, `sse`, `avx2`, `avx512`, `neon`, `sve`, a
  portable `generic`, … (with inheritance/fallback chains);
- **scalar types** — `si8…si64`, `ui8…ui64`, `f32`, `f64`;
- **machine profiles** — skylake, icelake, etc. (a named CPU-feature set).

The architecture keeps a rich **vocabulary** of domain/IR types while
**budgeting plumbing tightly**: one body model (`Segment`), one lowered form
(`LoweredSpecialization`), and result objects that carry only `(value,
diagnostics)`. Progress is tracked by a coverage table
(*primitive × extension × backend → compiles?*) and by generated artifacts that
build, not by the number of internal abstractions.

## The pipeline

The compiler is a pure function once source data and static compiler assets are
loaded, orchestrated in [pipeline.py](src/tslc/pipeline.py):

```
sources + compiler assets → parse → catalog → select → scan body → lower → finalize names → validate/plan → render → write → verify
```

| Stage | Module | Role |
|---|---|---|
| **compiler assets** | [compiler_assets.py](src/tslc/compiler_assets.py) | Load the bundled grammar and render assets |
| **sources** | [sources.py](src/tslc/sources.py) | Read `.tsl` source files |
| **syntax** | [syntax/](src/tslc/syntax/) | Lark grammar → parse tree (outer declarations + TSIL body envelopes) |
| **catalog** | [catalog/](src/tslc/catalog/) | Promote parse tree → typed, immutable domain model (`Primitive`, `Extension`, `Catalog`) |
| **select** | [select/](src/tslc/select/) | For each `(backend, extension, type)` slot, pick the best implementation body |
| **ir / scan** | [ir/](src/tslc/ir/) | Turn a TSIL body into a recursive `tuple[Segment, ...]` — *not* an AST |
| **lower** | [lower/](src/tslc/lower/) | Walk segments, resolve queries/intrinsics → `LoweredSpecialization` |
| **backend** | [backend/](src/tslc/backend/) | Own target type projection, helper manifests, emitted profiles, Rust compile-target selection, validation, and C++/Rust function text |
| **value tests** | [value_tests/](src/tslc/value_tests/) | Plan executable cases from finalized emitted names |
| **benchmark** | [benchmark/](src/tslc/benchmark/) | Plan explicit implementation-variant measurements and render optional backend-scoped report/policy tools |
| **render** | [render/](src/tslc/render/) | Format validated profiles and prebuilt test plans into headers/modules, dispatch, CMake/Cargo, and docs |
| **output** | [output/](src/tslc/output/) | Write the file tree; build-verify with real toolchains (incl. SDE/QEMU emulation) |

Entry points: [cli.py](src/tslc/cli.py) (installed as `tslc`, also
`python -m tslc`) and [api.py](src/tslc/api.py). The CLI discovers repository
defaults through [project_config.py](src/tslc/project_config.py). Catalog-only
author validation is a separate boundary in
[authoring.py](src/tslc/authoring.py): `tslc check` stops after parse, catalog
promotion, invariants, and TSIL shell validation unless explicit slot filters
request selection and lowering. Catalog `list`/`show` and `doctor` consume the
same typed catalog, backend registry, machine-profile projection, and verifier
drivers rather than maintaining parallel compiler knowledge.

An omitted API/backend request resolves the live backend registry when the
`GenerationRequest` is constructed; no import-time snapshot defines later
requests. The project renderer consumes the request's explicit backend tuple.

Compiler diagnostics carry one canonical, end-exclusive `SourceSpan`; producers
must supply `span=` and may project its start only for point-oriented display
APIs. Strict-mode promotion, variant context, value-test coverage, and generation
snapshot schema version 2 preserve the complete range rather than rebuilding it
from a start location.

Editor overlays use that same boundary through
[lsp/workspace.py](src/tslc/lsp/workspace.py). A workspace-scoped parsed cache
reparses changed buffers and reuses unchanged documents; a per-document
[catalog index](src/tslc/catalog_index.py) similarly reuses unchanged source
fragments before deterministic full-catalog validation publishes a new
snapshot. Symbols, references, hover, completion, and semantic tokens are pure
projections of the latest successful catalog/index. Hierarchical document
symbols and registry-backed semantic token facts are built separately in
[catalog_authoring_index.py](src/tslc/catalog_authoring_index.py); the core
index retains resolvable catalog occurrences, including individual list
selector elements, primitive-scoped result targets, and source-defined
semantic-overload axes and values. Overload completion, hover, navigation,
references, symbols, tokens, and diagnostics all project the same typed
registry and validated primitive-family facts; the parsed cursor contributes
only generic sibling scalar fields for axis-scoped value completion. Implementation
selector levels are classified by the catalog-owned projection in
[catalog/selector_paths.py](src/tslc/catalog/selector_paths.py) — one
interpretation shared by catalog promotion, indexing, and editor context — so
target axes are recognized by name and `where` constraint levels are never
indexed as type groups. The parsed-source boundary
in [syntax/authoring.py](src/tslc/syntax/authoring.py) constructs a typed cursor
context from declaration, field, selector, map, list, and value spans. Inside
TSIL payloads it uses the recursive scanner's cursor spans to retain enclosing
region paths and distinguish region boundaries, selector shells, and raw text;
its outer-language fallback reads only the active incomplete line. Schema- and
registry-backed
[authoring_completion.py](src/tslc/authoring_completion.py) returns typed
completion records with replacement ranges, snippets, details, and stable
ordering for the LSP adapter. Region-shell terms and option bags come from the
same authoring descriptors as registered region keywords, while catalog-backed
providers supply primitive and backend-translation names. Typed query
completion is a pure projection of the evaluator function descriptors and
closed leaf namespaces in
[lower/query_authoring.py](src/tslc/lower/query_authoring.py); lexical scanner
facts delimit registered region arguments without classifying raw C++ or Rust,
and parsed primitive facts supply only reliable parameter, generic-parameter,
and selector-axis names. Failed document
parses retain that document's
last valid parsed structure without replacing current diagnostics. The
editor-neutral pygls transport is in `lsp/`; an initially invalid overlay uses
the valid saved corpus for catalog facts, parsed context, and definitions while
retaining parseable overlay occurrence spans.

Backend translation entries named `query_value::<namespace>::<name>` add typed
value leaves to both lowering and catalog-aware completion. The generic query
resolver delegates their spelling to the active backend template dialect, so a
new target namespace does not require a resolver branch.
[lsp/specialization_context.py](src/tslc/lsp/specialization_context.py)
combines the parsed cursor scope with the real selector to expose valid
`(profile, extension, type, result target)` slots to editor clients without
duplicating source parsing or compatibility rules in TypeScript. Inside an
authored implementation it retains only slots for which that exact source body
wins selection. [lsp/implementation_preview.py](src/tslc/lsp/implementation_preview.py)
projects one deterministic CodeLens site per promoted physical implementation
field from parsed/catalog source spans; lens collection never selects, lowers,
or renders a slot.
[version.py](src/tslc/version.py) derives the installed distribution version
used by `tslc --version`, LSP server metadata, and diagnostic sources. The
platform-specific editor release freezes this same CLI/LSP entry point and its
package assets; its release manifest records that compiler version, the
extension version, source commit, build tools, licenses, and every runtime file
checksum. The TypeScript client validates only distribution facts and process
placement, never compiler semantics.
[lsp/primitive_scaffold.py](src/tslc/lsp/primitive_scaffold.py) likewise owns
catalog-backed primitive-shape discovery, default parameter-name selection,
name validation, and source scaffolding; the client only presents choices and
applies the returned edit. The TypeScript VS Code client contains no compiler
semantics. Exact diagnostic and metadata-audit repairs are represented by the
typed, editor-neutral records in
[authoring_fixes.py](src/tslc/authoring_fixes.py). They bind an edit to its
diagnostic or suggestion identity, source path, document version and digest,
replacement range, and expected original text. The LSP adapter revalidates the
record and returns a versioned `WorkspaceEdit`; compiler and server code never
write the document. Ambiguous diagnostics yield non-editing guide actions.
[lsp/primitive_explorer.py](src/tslc/lsp/primitive_explorer.py)
projects File/Corpus primitive lists in either authored-source or concrete
profile mode. It owns authored, selected, profile-rejected, missing, and
backend-unsupported slot states plus callable identity (signature and sorted
primitive attributes), concrete representation-target identity, implementation
origins, and source spans from the same catalog, selector, support-policy view,
and index. A resolved callable-and-target slot has one selected source body, so
editor navigation opens it directly; authored candidate bodies remain explicit
when no profile has selected a winner. Preview and analysis forward that exact
target instead of merging base- and extension-target specializations. Direct
Calls/Called By relationships
are indexed from registered `call` regions. The VS Code tree providers render
those typed facts and never reconstruct selector or dependency rules.
Explicit concrete explorer analysis runs `tslc analyze` as a saved-corpus
child. An opt-in immutable pipeline trace preserves the same post-pruning slot
identities, active call edges, unresolved origins, and propagated
native/composed/fallback/unknown state used by generation. The command returns
a deterministic cycle-terminating tree plus the complete input digest; the
client owns only cancellable execution, complete-context caching, stale-state
presentation, and source navigation. Lookup refreshes never collect this trace
or start analysis.
Concrete preview runs `tslc preview` as a separate saved-file child. It uses
one loaded input snapshot for selection, lowering, and dependency closure, then
passes the requested emitted specialization through the registered backend's
normal primitive renderer. An optional compiler source point restricts the
result to lowered specializations originating in that exact authored selector,
which lets editor CodeLens previews avoid merging overloads or other source
bodies with the same primitive name. Concrete wildcard-attribute
variants that share that selector intentionally remain grouped. It does not
load project render assets, plan tests or benchmarks, write a generated
project, or invoke a toolchain. `tslc explain` remains the detailed
selection/lowering diagnostic view.

## The input language (two nested languages)

### 1. The outer TSL data language

An indentation-sensitive, YAML-ish DSL. A primitive declares a signature, docs,
authored test cases, and a tree of implementations keyed by
`extension → type-group`. Abbreviated from
[`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl):

```
prim<v:=(v,v)> add(left, right):
  tests:
    - {tags [basic], type "si32", case {inputs [[1,2,...],[8,7,...]], expected [9,9,...]}}
  impls:
    avx2:
      ?i?:                         # type-group wildcard: any integer width
        requires [avx, avx2]
        implementation:
          tsil "complete(intrin<add, build[suffix=base::signed_of(base::in)]>(left, right));"
```

- **Signatures** (`v:=(v,v)`): `v` vector, `m` mask, `im` integral mask, `s`
  scalar, `ptr`/`usize` (presence makes it a free function), `lanes<s>` a lane
  list. Representation changes may use target-owned operands such as `vt`
  (target register) and `imt` (target integral mask); a target result projects
  the declared result kind through the target vector.
- **Type-group keys**: `?i?` (any int), `f?` (any float), `arith` (all), plus
  concrete tags. Ranked by **specificity** — `si32` beats `?i?` beats `arith`.
- **Extension fallback**: extensions form `inherits` chains (e.g. `avx2_vl →
  avx2`); an active variant can explicitly `supersedes` another extension while
  still borrowing fallback bodies from its inheritance chain.
- **Target-family capabilities**: `target_families:` owns behavioral roles for
  source-named extension families—fallback classification, free-function
  ownership, declared-register requirements, and index-vector support—and for
  profile families, including whether a profile runs natively without an
  emulator and each backend's explicit target architecture/toolchain facts. It
  also owns documentation family/order labels and the catalog of accepted
  target features plus their default/backend compiler spellings;
  machine profiles retain only genuine profile-specific overrides. Selection,
  lowering, translation, documentation, and verification consume those typed
  roles instead of recognizing family or feature-name patterns.
- **Semantic overloads**: `overload_axes:` declares closed axes, values, and
  accepted operand signature kinds in source data. A primitive `overload`
  block selects one axis/value and may mark its source declaration primary.
  The catalog promotes these into immutable registry and primitive values,
  validates complete same-name families, resolves the primary value once, and
  structurally identifies the distinguishing operand without interpreting
  parameter names or implementation text. Lowering carries the resolved
  declaration fact—not the registry—inside `LoweredSpecialization`, making it
  available to backend/API, documentation, test, and benchmark projections
  without reopening the catalog. Those consumers do not apply facade policy yet.
- **Arithmetic contracts**: a primitive may declare an explicit nonempty set of
  `operations`, parameter-bound `operand_roles`, and atomic `guarantees` in an
  `arithmetic:` block. The catalog promotes this into the frozen enum-backed
  types in
  [catalog/arithmetic.py](src/tslc/catalog/arithmetic.py), resolving each role to
  its parameter index, non-mask ordinal, and signature kind. The compiler-owned
  guarantee descriptor table validates operation, numeric-domain, mask, role,
  and conflict prerequisites; same-name declarations must agree on operations,
  corresponding role bindings, and non-mask guarantees. Catalog inspection and
  editor completion, tokens, navigation, and hover project those same facts.
  Consumers never infer arithmetic semantics from primitive names, parameter
  spellings or positions, prose, or implementation text.
- **Primitive operation contracts**: curated non-arithmetic families declare a
  closed language-neutral `operation` plus explicit parameter-bound
  `operand_roles`, including runtime lane indices where applicable. Focused
  `memory`, `conversion`, and `shift` blocks add only
  contiguous access direction, conversion/lane-count relations and numeric
  modes, or wrapping
  count/lane rules and admitted scalar count types that are not already owned
  by attributes, result targets, and semantic overloads. The catalog
  promotes these through the frozen records in
  [catalog/semantics.py](src/tslc/catalog/semantics.py),
  [catalog/memory.py](src/tslc/catalog/memory.py), and
  [catalog/conversion.py](src/tslc/catalog/conversion.py), and
  [catalog/shift.py](src/tslc/catalog/shift.py); it validates signature kinds,
  required roles, same-name families, and domain compatibility while retaining
  source spans. Catalog inspection and editor completion, tokens, navigation,
  references, and hover consume those same enums. Lowering carries
  the promoted contracts unchanged inside `LoweredSpecialization`; backend and
  downstream projections therefore receive typed facts without reconstructing
  them. Source data contains no Rust-specific spelling policy, and this stage
  does not apply one.
- **Explicit result vectors**: `return_type: vector: Name` refers to a declared
  `kind simd_type` generic and makes that complete caller-supplied vector the
  result owner without adding an implementation-selector axis. Lane-preserving
  numeric conversions use this result form and may declare the language-neutral
  `scalar_as` mode; the lower-level primitive checks equal logical lane counts,
  while facades can make the relation structural by preserving their lane-count
  parameter.
- **Fixed-width SVE**: `sve128`/`sve256`/`sve512` inherit scalable `sve` bodies
  but supersede `sve` in their fixed profiles, so one profile emits one SVE
  model. The fixed width is a compile mode (`sve_vector_bits_N`) plus C++ flags
  such as `-msve-vector-bits=N`, not a separate hardware target feature.
  Scalable `sve` remains available through the separate `sve` profile; fixed
  profiles make `dataparallel::native` resolve to the selected fixed SVE model.
- **Clang vector overlays**: C++ profiles may expose the opt-in
  `clang_v128`/`clang_v256`/`clang_v512` extensions through a dedicated
  `tsl_<profile>_clang.hpp` header and `tsl::<profile>_clang` CMake target.
  These compiler-vector types do not participate in `native` or `fixed<N>`
  inference. Consumers explicitly request one with
  `dataparallel::simd_for_t<clang_fixed<N>, T>`, where `N` is the lane count;
  the guarded overlay maps the resulting bit width to the corresponding
  `clang_v128`/`clang_v256`/`clang_v512` extension. The default uses Clang's
  comparison-result vector as its mask. Consumers may instead request the
  dense boolean-vector representation with
  `clang_fixed<N, clang_mask::boolean_vector>` when Clang reports
  `__has_feature(ext_vector_type_boolean)`. The generated data vector is the
  same; only the mask contract changes. A body that needs a hardware
  implementation uses the typed `vector::fixed` query, which dependency closure
  resolves concretely while C++ renders
  `dataparallel::simd_for_t<fixed<N>, T>`. Their `comparison_lane_vector` mask
  policy derives `mask_type` from Clang's exact vector-comparison result. Direct
  mask operations retain all-one/all-zero lane semantics, while
  `to_integral`/`to_mask` form the representation-safe bridge to hardware masks;
  mask objects are never assumed bit-cast-compatible. The dense boolean mask is
  not assumed to map to a hardware predicate register, and its explicit policy
  keeps that performance choice benchmarkable without changing the default.
  Rust does not emit these
  compiler-builtin extensions: stable Rust's SIMD surface is the
  architecture-specific `core::arch`, while its analogous portable
  `core::simd::Simd<T, N>` and lower-level compiler SIMD facilities remain
  nightly-only. A future nightly Rust path belongs in a separate opt-in
  `portable_simd` overlay rather than behind the Clang-specific policy.
- **Mask policies**: `[mask=zero]` (zeroing) and `[mask=pass_through]` (merge).
- `requires`, `safety` (internal/caller unsafe), and boolean attribute wildcards
  (e.g. `[aligned=*]`, expanded at catalog-build time).

### 2. The inner TSIL body language — the key design decision

A function body is **semi-valid target-language code sprinkled with TSIL keyword
islands**. Per the charter: *we do not parse C++/Rust expressions; we translate
only keyword islands.* [ir/scan.py](src/tslc/ir/scan.py) scans a body into a
recursive `tuple[Segment, ...]`:

- **`RawText`** — target source, passed through verbatim; line and block comments
  are opaque to the keyword scanner (including nested Rust block comments);
- **`Region`** — a recognized keyword island whose `<...>` shell is parsed by
  syntax-only helpers in [ir/region_syntax.py](src/tslc/ir/region_syntax.py) and
  whose `(...)` payload is recursively scanned.

`let<type>(Name, ...)` creates a typed lowering binding rather than a target-language
declaration. TSIL-owned type positions resolve it directly, for example
`cast<static>(Name, value)` or `var<typed>(Name, local, init)`. Use `type(Name)` only
to insert its spelling into otherwise raw target text. A bare `Name` inside `RawText`
is ordinary target text and is never searched or rewritten, including in comments,
literals, and Rust lifetimes.

The descriptor registry
([ir/region_registry.py](src/tslc/ir/region_registry.py)) is the lexical and
authoring source of truth consumed by scanning, shell validation, discovery,
and editor hover. Each descriptor carries a concise purpose and accepted source
forms in addition to its structural and validator keys. The typed lower-owned
registration
([lower/region_handlers/registry.py](src/tslc/lower/region_handlers/registry.py))
joins each keyword's handler factory with its implementation-state effect, so
lowering and state classification cannot drift into parallel keyword lists.
Together they cover `complete`, `intrin`, `helper`, `op`, `call`, `value`,
`type`, `cast`, `var`, `let`, `mask`, `mem`, `lanes`, `array`, `io`, `if`,
`select_expr`, `loop`, `switch`, and `assume_aligned`. **A call-shaped keyword
grows by adding a lexical descriptor, its owned validator when needed, and one
lowering registration row. A genuinely new structural body shape also adds one
paired scanner/malformed-scanner parser registration in `ir/scan.py`.**

So `intrin<add, build[suffix=base::signed_of(base::in)]>(left, right)` becomes
`_mm256_add_epi32(...)` for AVX2/si32, and
`call<primitive=mov, attrs[mask=zero]>(...)` resolves to another generated
primitive. Generation-time queries (`base::in`, `vector::length`,
`is_same(...)`) and control (`if<generation>`, `loop<generation>`,
`switch<compile>`) are evaluated *at compile time* against the concrete
type/extension being specialized.

## Lowering & assembly

The [Selector](src/tslc/select/selector.py) enumerates the literal
`(extension, type, representation-target)` axis before choosing bodies. A
free-function primitive follows a separate path and returns the first usable
declaration-owning extension slot in established profile order, because its
rendered declaration has no SIMD axis.

The [Lowerer](src/tslc/lower/lowerer.py) walks the segments for one
`(primitive, extension, type, backend)` slot → a `LoweredSpecialization`
(concrete type spellings, register type, body text, mask policy, safety,
required target features). Region handlers
([lower/region_handlers/](src/tslc/lower/region_handlers/)) translate each
keyword; a query evaluator ([lower/queries.py](src/tslc/lower/queries.py))
resolves the `<...>` selectors.

Successful `call<...>` lowering records typed dependency origins using the same
query evaluator and live generation-time control flow that produced the body.
The pipeline then runs a **profile-scoped dependency closure**: from the
requested primitives it resolves those lowered call facts
([lower/dependencies.py](src/tslc/lower/dependencies.py)), lowers callees, and
**prunes to a fixpoint** any specialization whose callees aren't themselves
emitted for the same concrete `simd<type,ext>` (else the generated call
wouldn't link). A call on a free SIMD type parameter instead retains a symbolic
reference containing the authored parameter name and its optional selected base
binding, never the caller's extension. Its compiler-derived trait bounds are
validated during lowering, and dependency discovery keeps the corresponding
callee family in the profile scope. Because its concrete representation is
chosen only by the generic caller, that edge does not participate in exact-slot
pruning or fact propagation. Concrete edges continue to **propagate bottom-up**
unsafe-ness, required target features, and implementation-state joins through
the live call graph
([_pipeline_closure.py](src/tslc/_pipeline_closure.py),
`_propagate_transitive_call_facts`).

After closure, constructing an
[backend/emitted_profile.py](src/tslc/backend/emitted_profile.py) profile uses
[backend/emitted_names.py](src/tslc/backend/emitted_names.py) to finalize masked
and immediate wrapper names, then freezes deterministic per-backend groups.
Backend validators reject contradictory declared
capabilities before artifacts are constructed, while an extension that declares
a backend unsupported is not admitted as a coverage attempt for that backend.
Helper dependency roots and helper
admission both come from typed manifests in
[backend/helper_requirements.py](src/tslc/backend/helper_requirements.py).

Backends differ idiomatically (a `BackendDialect`,
[backend/translation.py](src/tslc/backend/translation.py), abstracts type
spellings, intrinsic composition, call syntax, and unsafe framing). The
[backend registry](src/tslc/backend/registry.py) owns each backend's dialect
factory, artifact media type, complete artifact renderer, documentation
formatter, validation, helper manifest, value-test support, optional benchmark
planner, verification adapter, and
post-generation formatting/documentation specs. Signature type
projection machinery and the concrete C++/Rust projection tables are co-located
in [backend/signature_types.py](src/tslc/backend/signature_types.py), then shared
by function emitters and documentation formatting. They are backend-owned facts,
not registry capabilities. Backend-neutral variant/body facts live in
[backend/primitive_rendering.py](src/tslc/backend/primitive_rendering.py);
language documentation assembly and Rust type-parameter/state-query spelling
live in focused sibling modules rather than the function emitters.
The complete renderer receives emitted profiles, value-test plans, and
benchmark plans as one frozen snapshot. This lets a backend compute any shared
semantic-to-layout projection once before its focused project, test, and
benchmark formatters run.

Sized-vector lane arithmetic crosses that boundary as a typed `LaneCount`.
C++ renders scaled symbolic counts as constant expressions; stable Rust rejects
them before target text is produced unless selection has monomorphized the
count. Neutral lowering never constructs a C++ or Rust lane-count expression.

- **C++** — `*_impl<Vec>` struct partial-specializations + wrapper function
  templates ([backend/cpp.py](src/tslc/backend/cpp.py)).
- **Rust** — traits + impls + turbofish wrappers, explicit `unsafe {}` framing,
  `core::arch` intrinsic qualification ([backend/rust.py](src/tslc/backend/rust.py)).
  Generated rustdoc uses a `cfg(doc)` profile-neutral facade containing one
  public signature per emitted Rust primitive; concrete profile availability
  stays in the specialization explorer, while normal builds select their
  `profile` alias from compile-target cfgs with an exact generic fallback.
  Profile-local algorithm trait impls
  share typed Scalar/Generic/concrete render targets in
  [backend/rust_algorithm.py](src/tslc/backend/rust_algorithm.py). Static
  algorithm-wrapper names are reserved by the compiler manifest in
  [backend/rust_algorithm_manifest.py](src/tslc/backend/rust_algorithm_manifest.py),
  with an asset-consistency test preventing drift.

The ordinary Rust API is finalized before source rendering by the frozen records
in [backend/rust_api_model.py](src/tslc/backend/rust_api_model.py) and focused
candidate, comprehensive, curated, and surface planners under `backend/rust_api_*`.
The public
[backend/rust_api_planner.py](src/tslc/backend/rust_api_planner.py)
orchestrates those projections directly and preserves the compiler-facing
planning and validation API.
That projection combines lowered language-neutral operation, operand-role,
overload, conversion, and safety contracts with static fixed-shape selection.
It owns Rust receiver placement, const/type-parameter spelling, method suffixes,
curated trait admission, native candidates, cfg/delegate identity, and collision
diagnostics. It does not inspect implementation text, infer semantics from a
primitive name, reopen `tsldata`, or render Rust. Backend validation constructs
the plan at the post-lowering boundary, exposing one compiler-owned input for
Rust source, rustdoc, fixture, benchmark, and dispatch projections.
For artifact production,
[backend/rust_capability.py](src/tslc/backend/rust_capability.py) constructs the
static-selection, facade, dispatch, policy-consumption, and benchmark-layout
plans once. The private project boundary in
[render/rust_project.py](src/tslc/render/rust_project.py) trusts and formats
those frozen plans; it does not replan or recompute-and-compare them.

The focused renderer in
[render/rust_facade.py](src/tslc/render/rust_facade.py) turns those finalized
shape records into sealed, opaque `Simd<T, N>` and `Mask<T, N>` values. A
compile target selects one exact private hardware representation or the
source-backed generic representation; no profile or extension is a Cargo
feature. Complete release metadata is carried through the backend-neutral
`ProjectRenderConfig` into the Rust package renderer, so templates format
configured Cargo facts rather than owning repository release policy.

A static substrate ships as assets
([backend/assets/tsl_core.hpp](src/tslc/backend/assets/tsl_core.hpp),
[tsl_core.rs](src/tslc/backend/assets/tsl_core.rs)) defining `simd<T,Ext>` /
`SimdVector` and helpers. Whole-file scaffolding and stable profile metadata
also live there as named templates; Python renderers supply only finalized,
typed holes and dynamic declarations. Backend target-text values use
[target_text.py](src/tslc/target_text.py); [render/](src/tslc/render/) only formats
finalized, validated profiles, prebuilt value-test plans, and prebuilt
benchmark plans into a per-profile project with a top-level dispatch
header/module.

The optional [benchmark/](src/tslc/benchmark/) stage consumes finalized
backend specializations and authored value-test facts through one
backend-parameterized typed planner. It plans every explicitly coexisting named
variant in the emitted primitive/dependency closure and emits structured skip
coverage for unsupported signature shapes. C++ renders those facts as a
standalone native benchmark/policy tool. Rust admits scenario coverage through
explicit named `profile × scenario-family` pairs while deriving profile family,
features, spellings, modes, and flags from the live machine profile. It renders
the `sse2` register and immediate families plus `avx2` one-vector scalar
reductions as standard-library-only custom Cargo benchmarks. The
compiler-cfg-gated hot loop lives inside the library crate, and a thin
per-profile bench target invokes it only with the unpublished
`tsl_variant_benchmarks` compiler cfg plus the exact compiler-owned codegen and
target-feature flags. Ordinary Cargo builds retain the authored wrapper choice.
Rust candidate calls use backend-owned concrete type, trait, const-argument, and
unsafe spelling; all authored expectations pass before any samples are timed or
written. The Rust runtime validates the exact sample inventory and applies the
conservative paired reducer. Its summary keeps the observed candidate and
improvement even when compile-time selection is unsupported; the separate
policy decision remains the authored default.
Profiles without a consumable mapping do not advertise or produce a policy
file. Policy-capable reports stage raw JSONL, summary, and backend-scoped policy
files before publishing the policy last. Policy production is native x86 and
build-local. It requires
`TSL_RUST_BENCHMARK_CONTEXT` as the caller's explicit identity for the
build-local inputs that Cargo does not expose to `build.rs`. Policy-producing
and policy-consuming invocations use the same exact compiler-owned trailing
Rust codegen flags and `CARGO_INCREMENTAL=0`; under the recorded Cargo version,
these neutralize stable workspace, manifest, and command-line profile settings
that would otherwise change generated code invisibly. The compiler compares
the tokenized flags, Cargo and rustc verbose identities, observable profile
facts, wrappers, target facts, and the caller's context identity in both
phases. Environment-exposed extra profile settings and compiler wrappers fail
closed. This is a compatibility boundary for the documented ordinary Cargo
commands, not an adversarial security boundary or a portable-policy claim.
Callers must change the external context identity when an unobservable runner
or other build-local input changes. Extra `cargo rustc --` arguments, forced
Cargo `[env]` values, custom/untrusted Cargo or rustc executables, nightly-only
flag channels, and future Cargo codegen mechanisms outside the versioned guard
are unsupported. A
separate native policy-enabled Cargo build may consume the precomputed file
through `TSL_RUST_VARIANT_POLICY_FILE`. The build script joins it to a
compiler-rendered descriptor, requires the same compiler, target, generated
codegen contract, attested context identity, and CPU facts. Policy-producing
and policy-consuming library builds retain the same private compiler cfg and
exact codegen contract so their generated code context is identical; this is
not a published Cargo feature. The benchmark target itself independently
rejects any policy input. The generated per-profile benchmark help prints the
exact explicit workflow and codegen guard. For the policy-capable `sse2`
register profile, its first Cargo invocation removes
`TSL_RUST_VARIANT_POLICY_FILE`, runs the optimized benchmark, and writes samples,
summary, and policy below the Cargo target tree. A separate policy-enabled Cargo
invocation consumes that precomputed file; no convenience command hides or
cycles the two phases. The
generated benchmark Cargo profile is pinned to the compiler-owned settings. A
frozen semantic consumption plan joins benchmark evidence to the selection
seam; one render projection derives the Cargo and artifact names shared by
project and benchmark rendering. Missing benchmark evidence therefore leaves
an ordinary default-only build instead of a dangling policy module. The build
script materializes one complete mapping under `OUT_DIR` for
both authored-default and policy-selected builds, and the library includes that
Cargo-owned path unconditionally instead of exposing a caller-forgeable cfg or
mapping environment seam. It neither executes timing code nor edits generated
`src/` files. Unset input retains the authored-default mapping, while any
requested missing, foreign, stale, partial, duplicate, or report-only selection
fails before library compilation. Unadmitted profile and scenario-family pairs
remain structured Rust coverage gaps. The benchmark maintenance projection runs one
backend per invocation: the original C++ issue baseline remains unchanged,
while separate Rust evidence preserves every raw report gap plus exact profile
manifest, candidate ID/body hash, policy eligibility, and compiler-rendered
mapping hashes. Aggregate shape counts are explanatory inventory, not the Rust
ratchet identity. Value-test tags do not control benchmark admission.
Workload semantics are resolved in
[benchmark/scenarios.py](src/tslc/benchmark/scenarios.py) before rendering:
each typed scenario and correctness case validates its own structural and
specialization compatibility and owns its canonical policy identity. Candidate
sets only enforce homogeneous matching families. Harness discovery/closure is
checked through one planner boundary, while C++ scenario renderers supply typed
fragments to one shared timing skeleton; the remaining family dispatch selects
genuinely different input construction and invocation behavior. Pure-register
scenarios carry
their operand generators and dependency parameter, vector-plus-scalar scenarios
keep the scalar input independent, immediate scenarios carry an authored
concrete value, indexed-load scenarios carry a SIMD index binding and bounded
hot-L1 memory contract, vector-to-scalar reduction scenarios carry an
independent input generator, vector-input mask-result scenarios carry their
operand generators, and integral-mask conversion scenarios carry exact
active-lane counts. A primitive uses the
validated `benchmarks.latency_chain` catalog fact only when its latency operand
is ambiguous; `benchmarks.operand_domains` can constrain a compatible vector or
scalar operand to a validated domain such as `nonzero` or `shift_count`. Source
data never embeds benchmark C++. The generated CMake project runs the tool only
through explicit report, policy, or autotune options;
ordinary generation and builds retain the authored default.

## Differential value tests

Authored `tests:` blocks (input lanes → expected lanes) drive the
[value_tests/](src/tslc/value_tests/) subsystem, which generates **executable**
C++/Rust tests: build a SIMD register from a lane array, run the generated
primitive, read the result back, compare to `expected`. Each case plan groups
inputs, expectations, invocation facts, memory layouts, representation changes,
scalable harness facts, and differential harness facts into frozen typed
components
([value_tests/case_components.py](src/tslc/value_tests/case_components.py));
[case-kind capabilities](src/tslc/value_tests/case_capabilities.py) validate
those facts through the focused
[case plan](src/tslc/value_tests/case_plan.py) before rendering. The
source-authored `comparison bitwise` mode is deliberately limited to vector
results with vector operands; it makes C++ and Rust golden and differential
tests compare exact lane representations, including NaN sign and payload bits.
The default `comparison value` remains NaN-aware while retaining exact signed
zero and infinity checks. The
`status_pointer` case kind validates nondeterministic status-plus-output
contracts by checking the status domain and failure-path output preservation,
without inventing vector lanes or a deterministic success value. The
array↔register round-trip uses auto-discovered "harness primitives"
(`from_array`, `to_array`,
`to_integral`, found by signature shape in
[value_tests/harness.py](src/tslc/value_tests/harness.py)). A **differential**
mode cross-checks each hardware implementation against the portable `generic`
one. [output/verify.py](src/tslc/output/verify.py) then actually compiles and
runs them — optionally under **Intel SDE** or **qemu-aarch64** so
AVX-512/NEON/SVE code runs on hardware that lacks it.

## State / outcome

- **Coverage-not-completeness**: in `partial` mode a primitive whose body can't
  be lowered yet is *recorded as a skip*, not a failure; `strict` mode promotes
  skips to errors. [coverage.py](src/tslc/coverage.py) and
  [maintenance/](src/tslc/maintenance/) (e.g. `coverage_inventory`)
  operationalize the charter's coverage-not-completeness rule. `tslc coverage
  inventory` is read-only by default and folds finalized lowering outcomes into
  one typed report with text, Markdown, and JSON renderers. Its profile/backend
  shared-availability percentages use a logical-candidate denominator and are
  shown beside backend-local lowering success. Profile rows use the typed
  architecture order, then target-feature count and name. Explicit `--update`
  and `--check` modes own the canonical tracked Markdown evidence.
- **Honest edges**: [support_policy.py](src/tslc/support_policy.py) centralizes
  what the compiler can emit today; some keyword forms are *recognized so a
  body skips cleanly* rather than leaking through as raw text.
- **Tests**: the default pytest run exercises the pure-logic suite and skips
  generated C++/Rust build/value gates. Run `pytest --run-generated-builds
  tests/test_build_verify.py tests/test_value_tests.py` when a slice needs real
  toolchain coverage. Run the suite from the **repo root**, not from `tslc/` —
  `tests/test_value_test_planning.py` reads source via repo-root-relative paths
  and otherwise reports false failures.

## Where to look first

- Big picture / rules: [README.md](README.md), [CHARTER.md](CHARTER.md).
- The body model: [ir/segments.py](src/tslc/ir/segments.py),
  [ir/scan.py](src/tslc/ir/scan.py).
- Orchestration: [pipeline.py](src/tslc/pipeline.py).
- A real primitive with all the moving parts:
  [`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl).
