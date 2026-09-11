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
loaded, orchestrated in [pipeline.py](src/tslc/pipeline.py). Typed generation
requests and their cross-field validation live in
[pipeline_request.py](src/tslc/pipeline_request.py), separate from the mutable
per-run orchestration session:

```
sources + compiler assets → parse → catalog → select → scan body → lower → finalize names → validate/plan → render → write → verify
```

| Stage | Module | Role |
|---|---|---|
| **compiler assets** | [compiler_assets.py](src/tslc/compiler_assets.py) | Load the bundled grammar and render assets |
| **sources** | [sources.py](src/tslc/sources.py) | Read `.tsl` source files |
| **syntax** | [syntax/](src/tslc/syntax/) | Lark grammar → parse tree (outer declarations + TSIL body envelopes) |
| **catalog** | [catalog/](src/tslc/catalog/) | Promote parse tree → typed, immutable domain model (`Primitive`, `Extension`, `Catalog`) |
| **select** | [select/](src/tslc/select/) | Enumerate each applicable `(backend, declaration, extension, type, target)` slot and pick the best implementation body, retaining explicit absences for requested analyses |
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
snapshot. The façade builds and caches indexes; immutable query records live in
[catalog_index_model.py](src/tslc/catalog_index_model.py), semantic source
occurrence construction in
[catalog_occurrences.py](src/tslc/catalog_occurrences.py), and hover
presentation in [catalog_hover.py](src/tslc/catalog_hover.py). Symbols,
references, hover, completion, and semantic tokens are pure projections of the
latest successful catalog/index. Hierarchical document
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
TSIL payloads it uses the tolerant projection in
[ir/cursor.py](src/tslc/ir/cursor.py), which shares lexical rules with the
recursive scanner through [ir/lexical.py](src/tslc/ir/lexical.py), to retain
enclosing region paths and distinguish region boundaries, selector shells, and
raw text. Its outer-language fallback reads only the active incomplete line.
Schema- and registry-backed
[authoring_completion.py](src/tslc/authoring_completion.py) orchestrates typed
completion records from
[authoring_completion_model.py](src/tslc/authoring_completion_model.py).
TSIL query and region-shell completion lives in the focused
[authoring_tsil_completion.py](src/tslc/authoring_tsil_completion.py).
Region-shell terms and option bags come from the same authoring descriptors as
registered region keywords, while catalog-backed providers supply primitive
and backend-translation names. Typed query
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
and index. A resolved callable-and-target slot projects either one exact source
body or the automatic compiler-capability frontier over its fallback; every
selected source span remains explicit for navigation. Authored candidate bodies
remain explicit when no profile has selected a winner. Preview and analysis
forward that exact target instead of merging base- and extension-target
specializations. Direct
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
one loaded input snapshot for selection, lowering, dependency closure, and
backend policy, then passes the requested emitted specialization through the
registered backend's normal primitive renderer. Its reported input digest
includes the canonical backend-policy fingerprint, so a policy change cannot
silently alter output under an unchanged snapshot identity. An optional
compiler source point restricts the result to lowered specializations
originating in that exact authored selector, which lets editor CodeLens
previews avoid merging overloads or other source bodies with the same primitive
name. Concrete wildcard-attribute
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
- **Implementation requirements**: target-machine features and backend compiler
  capabilities are separate typed axes. Legacy `requires [feature]` and scoped
  feature maps remain valid; the expanded `requires.target_features` form makes
  the hardware axis explicit. `requires.compiler.<backend>.capabilities` names
  backend-owned compiler facts; extension availability and opt-in header groups
  use the same capability IDs. The generic registry mechanics live in
  [backend/capability.py](src/tslc/backend/capability.py), while each backend
  owns its complete concrete evidence (for C++,
  [backend/cpp_compiler_capabilities.py](src/tslc/backend/cpp_compiler_capabilities.py)).
  Compiler families, feature-test names, macros, diagnostics, header groups,
  and probes do not live in source data. Explicit capability inputs
  select one fixed winner for focused
  authoring and pinned-toolchain workflows. Ordinary project generation retains
  the capability winner frontier over an unconditional fallback in one lowered
  specialization. The C++ project renderer emits backend-owned compile probes,
  exports their results as target compile definitions, and renders local
  preprocessor branches around the alternative bodies. Hardware-profile
  selection and compiler-capability probing therefore remain independent.
  C++ compiler option families, runtime-probe programs, overlay compiler sets,
  and overlay enable macros are finalized in the backend-owned
  [backend/cpp_profile_model.py](src/tslc/backend/cpp_profile_model.py) snapshot;
  [render/cpp_build.py](src/tslc/render/cpp_build.py) only formats those values.

- **Signatures** (`v:=(v,v)`): `v` vector, `m` mask, `im` integral mask, `s`
  scalar, `ptr`/`usize` (presence makes it a free function), `lanes<s>` a lane
  list. Representation changes may use target-owned operands such as `vt`
  (target register) and `imt` (target integral mask); a target result projects
  the declared result kind through the target vector.
- **Primitive attribute semantics**: closed `cast`, `mask`, and `value`
  spellings are promoted once into `PrimitiveCastMode`, `PrimitiveMaskMode`,
  and `PrimitiveValueMode`. Selection, lowering, dependency closure, benchmark
  inventory, and value-test planning consume those typed fields rather than
  comparing raw attribute strings or recognizing primitive names.
- **Type-group keys**: `?i?` (any int), `f?` (any float), `arith` (all), plus
  concrete tags. Ranked by **specificity** — `si32` beats `?i?` beats `arith`.
- **Extension fallback**: extensions form `inherits` chains (e.g. `avx2_vl →
  avx2`); an active variant can explicitly `supersedes` another extension while
  still borrowing fallback bodies from its inheritance chain.
- **Register multiplicity**: `register_multiplicity_types` is a sparse,
  source-owned map from a physical capacity (`x2`, `x4`, `d2`, and so on) and
  scalar type/group to backend spelling. The catalog promotes the capacity to
  `RegisterMultiplicity`; conversion semantics derive the required capacity
  from concrete source/target widths, and backend dialects translate only that
  finalized fact. These physical spellings are deliberately not inherited by
  fixed-width facades, whose register representation may differ. The map does
  not create a general target-language type AST or make a grouped vector part
  of the public API by itself.
- **Target-family capabilities**: `target_families:` owns behavioral roles for
  source-named extension families—fallback classification, free-function
  ownership, declared-register requirements, and index-vector support—and for
  profile families, including whether a profile runs natively without an
  emulator, whether runtime failures can be observed, and each backend's
  explicit target architecture/toolchain facts. Source selects an optional
  backend detection strategy ID; the backend registry owns its concrete target
  syntax, feature-test macros, validation, and probes. It also owns
  documentation family/order labels and the catalog of accepted
  target features plus their default/backend compiler spellings;
  machine profiles retain only genuine profile-specific overrides. Selection,
  lowering, translation, documentation, and verification consume those typed
  roles instead of recognizing family or feature-name patterns. Documentation
  target classes combine that declared family label with scalar, lane-count,
  numeric-bit-width, scalable, or explicitly declared width facts; the renderer
  does not recognize concrete family or extension identities.
- **Profile build roles**: a machine profile may declare
  `default_build_fallback` and a semantic `auto_detect_gate`. Exactly one
  ungated fallback is accepted. The C++ detection registry
  ([backend/cpp_detection.py](src/tslc/backend/cpp_detection.py)) maps gate IDs
  to CMake modes, helper functions, and packaged assets before render-model
  construction; renderers never infer compiler selection from a compile-mode or
  profile-name literal.
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
  `to_integral`/`to_mask` form the representation-safe bridge to hardware
  masks. On little-endian Clang toolchains that provide Boolean extended vectors
  and `__builtin_convertvector`, a generated compiler-capability branch converts
  comparison masks through a dense Boolean vector and bit-casts only that
  one-bit-per-lane representation to the integral mask. The inverse path
  normalizes unused high bits before the bit-cast and converts Boolean lanes back
  to canonical all-zero/all-one comparison lanes. Dense Boolean masks use the
  same normalized bit bridge directly. Other toolchains and byte orders retain
  the representation-independent lane loop, so arbitrary comparison mask
  objects are never assumed bit-cast-compatible. The dense boolean mask is not
  assumed to map to a hardware predicate register, and its explicit policy keeps
  that performance choice benchmarkable without changing the default.
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
  syntax-only helpers in [ir/region_syntax.py](src/tslc/ir/region_syntax.py)
  and [ir/query_syntax.py](src/tslc/ir/query_syntax.py), and whose `(...)`
  payload is recursively scanned.

`let<type>(Name, ...)` creates a typed lowering binding rather than a target-language
declaration. TSIL-owned type positions resolve it directly, for example
`cast<static>(Name, value)` or `var<typed>(Name, local, init)`. Use `type(Name)` only
to insert its spelling into otherwise raw target text. Bare names inside `RawText`
are ordinary target text and are never searched or rewritten, including in comments,
literals, and Rust lifetimes. The one narrow, non-rewriting identity check is owned by
the existing `complete` region: a payload whose complete trimmed text exactly equals
a declared primitive parameter is classified as a direct parameter return. Parentheses,
comments, local names, operators, and every other raw expression remain opaque.

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

The [Lowerer](src/tslc/lower/lowerer.py) orchestrates one
`(primitive, extension, type, backend)` slot → a `LoweredSpecialization`
(concrete type spellings, register type, body text, mask policy, safety,
required target features). The frozen lowered records live in
[lower/model.py](src/tslc/lower/model.py), cached catalog-derived facts in
[lower/catalog_facts.py](src/tslc/lower/catalog_facts.py), and typed public
parameter projection in [lower/param_types.py](src/tslc/lower/param_types.py).
Region handlers
([lower/region_handlers/](src/tslc/lower/region_handlers/)) translate each
keyword; a query evaluator ([lower/queries.py](src/tslc/lower/queries.py))
resolves the `<...>` selectors.

Address intent is a typed `address<of|borrow_mut>(...)` TSIL region. Pointer
casts consume that region or an ordinary pointer-valued expression; common
lowering never parses C++ `&` or Rust `&mut` tokens from `RawText`.

Successful `call<...>` lowering records typed dependency origins using the same
query evaluator and live generation-time control flow that produced the body.
An edge to a callee with an applicable catastrophic precondition also carries
one source-located typed obligation per condition. Source authors either
`forward[...]` the condition through an unchanged vector identity and exact
caller/callee parameter and condition-context identities to the caller's
matching root precondition, or make an explicit
`discharge[...]` implementation assertion. This proof model never interprets
raw target-language expressions or treats an unsafe render frame as proof.
Catalog validation rejects missing, stale, ambiguous, or mismatched
dispositions; lowering retains unresolved obligations so checked-wrapper
admission can fail closed, including after transitive closure.

The pipeline then runs a **profile-scoped dependency closure**: from the
requested primitives it resolves those lowered call facts
([lower/dependencies.py](src/tslc/lower/dependencies.py)), lowers callees, and
**prunes to a fixpoint** any specialization whose implementation-body callees
aren't themselves emitted for the same concrete `simd<type,ext>` (else the
generated call wouldn't link). Compiler-created checked-guard calls are
discovered through the same typed dependency model but are not body edges:
after ordinary closure stabilizes, an unavailable guard dependency suppresses
only the optional checked companion, never the unchecked callable. A call on a
free SIMD type parameter instead retains a symbolic
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
[backend/algorithm_admission.py](src/tslc/backend/algorithm_admission.py)
joins those exact primitive and mask-policy requirements to the shared
algorithm families. C++ computes a project-wide intersection in
[backend/cpp_algorithm_plan.py](src/tslc/backend/cpp_algorithm_plan.py); Rust
retains a profile-local admission. Both expose deterministic gaps carrying the
backend, profile, helper feature, semantic family, primitive, and mask policy,
so optional compaction or mask helpers suppress only dependent forms. The same
helper groups seed dependency closure, including Rust's mandatory contiguous
load/store foundation.

Backends differ idiomatically (a `BackendDialect`,
[backend/translation.py](src/tslc/backend/translation.py), abstracts type
spellings, intrinsic composition, call syntax, and unsafe framing). The
[backend registry](src/tslc/backend/registry.py) owns each backend's dialect
factory, artifact media type, complete artifact renderer, documentation
formatter, validation, helper manifest, value-test support, optional benchmark
planner, verification adapter, and post-generation formatting/documentation
specs. C++ and Rust machine-profile verification projections live in
[backend/cpp_verification.py](src/tslc/backend/cpp_verification.py) and
[backend/rust_verification.py](src/tslc/backend/rust_verification.py);
render modules only format their already-decided project models. Signature type
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

C++ extension metadata separates ordinary `headers` from third-party
`system_headers`. The latter are parsed inside a narrowly scoped compiler
diagnostic boundary, before `tsl_core.hpp` when vendor types affect core helper
overloads. Both classes remain part of the typed compiler/doctor preflight; the
classification changes warning ownership, not dependency detection.

Sized-vector lane arithmetic crosses that boundary as a typed `LaneCount`.
C++ renders scaled symbolic counts as constant expressions; stable Rust rejects
them before target text is produced unless selection has monomorphized the
count. Neutral lowering never constructs a C++ or Rust lane-count expression.

- **C++** — `*_impl<Vec>` struct partial-specializations + wrapper function
  templates ([backend/cpp.py](src/tslc/backend/cpp.py)).
- **Rust** — traits + impls + turbofish wrappers, explicit `unsafe {}` framing,
  and `core::arch` intrinsic qualification. The
  [backend/rust.py](src/tslc/backend/rust.py) façade owns orchestration;
  [backend/rust_signatures.py](src/tslc/backend/rust_signatures.py),
  [backend/rust_direct_calls.py](src/tslc/backend/rust_direct_calls.py), and
  [backend/rust_documentation_api.py](src/tslc/backend/rust_documentation_api.py)
  own signature projection, direct-call rendering, and documentation API text.
  Generated rustdoc uses a `cfg(doc)` profile-neutral facade containing one
  public signature per emitted Rust primitive; concrete profile availability
  stays in the specialization explorer, while normal builds select their
  `profile` alias from compile-target cfgs with an exact generic fallback.
  [backend/rust_algorithm_plan.py](src/tslc/backend/rust_algorithm_plan.py)
  finalizes profile-local algorithm admission, exact static/native mappings,
  memory and optional-helper bindings, implementation targets, and primitive
  facades before rendering. It reuses the mapping records selected by
  `RustStaticSelectionPlan`; profiles without a compile-target selection reuse
  that plan's exact generic fallback. The target formatter in
  [backend/rust_algorithm.py](src/tslc/backend/rust_algorithm.py) consumes only
  those decided facts and semantic-family static assets. The project renderer
  keeps the stable `profile::algo` module path while emitting a private
  `algo/support.rs` for helper implementations and primitive policy facades,
  plus ordered private utility, iteration, predicate, count, selection,
  transform, consume, and aggregate wrapper modules. `algo.rs` explicitly
  re-exports their stable functions and `Profile`; concrete and fallback
  profiles use the same layout, and the parent profile cfg owns whether any
  child is compiled. Missing mandatory contiguous memory support and missing
  optional family helpers remain typed admission gaps rather than an empty
  formatter result or a template-time decision. Static
  algorithm-wrapper names are reserved by the compiler manifest in
  [backend/rust_algorithm_manifest.py](src/tslc/backend/rust_algorithm_manifest.py),
  with an asset-consistency test preventing drift.
  [backend/rust_algorithm_facade.py](src/tslc/backend/rust_algorithm_facade.py)
  separately formats the shared `tsl_algorithm` facade. Its stable root module
  explicitly re-exports public policy/representation types, mask layouts,
  kernel traits, and callable algorithms from private generated children.
  Representation, mask, kernel-trait, and range/address-validation substrate
  modules depend only on shared substrate; semantic-family modules may consume
  them but are never imported by them. Utility, iteration, predicate, count,
  selection/index, transform, consume, and aggregate implementations each have
  one focused private child derived in semantic-family order.

C++ keeps `tsl_algorithm.hpp` as the stable public umbrella. The project-wide
algorithm admission plan owns its ordered generated family-header records and
the renderer only formats those decided includes. Utility aliases and helpers,
iteration, predicate, count, selection/index, transform, consume, and aggregate
each have focused public headers; every behavioral family also owns a matching
private detail-loop header.

The public safety surface is a typed projection, not a renderer convention.
[backend/checked_api.py](src/tslc/backend/checked_api.py) admits a `_checked`
companion only for a complete catastrophic runtime precondition declared in the
catalog. C++ value companions preserve the ordinary value return and append a
final `precondition_error&`; C++ void companions return that error directly.
Rust companions return `Result`, while the ordinary Rust function remains
`unsafe` when its caller contract can cause undefined behavior. A failed
companion reports before dispatch; C++ returns only an initialized,
semantically unspecified placeholder. Memory companions replace bare pointers
with spans/slices carrying the exact checkable extent, but valid object
lifetime, provenance, references, and concurrency remain caller obligations.
Checked-memory admission also fails closed unless every caller-unsafe
specialization carries the reviewed `raw_pointer` obligation and only the
narrow implementation-mechanism labels currently known to coexist with it.
Unknown labels, unchecked indexing, and generic unsafe operations cannot be
erased by a range signature. Compiler-derived, internal-only
`value_reinterpretation` and `unsafe_callee` framing effects are admitted; the
latter does not itself prove that the callee's own condition was forwarded or
discharged. Typed `forward[...]` and `discharge[...]` call dispositions own
that proof independently, and unresolved obligations make checked admission
fail closed through the live ordinary call graph.

This two-path surface is implemented and release-ratcheted; it is not pending
refactor work. In particular, `internal_unsafe` describes the implementation
boundary needed by generated Rust, while `caller_unsafe` describes the public
call contract. Pointer-shaped signature syntax is not enough to infer either
fact: source metadata owns uncheckable caller obligations, while typed TSIL
regions contribute only their internal implementation effects. A `raw_memory`
mechanism without a `raw_pointer` or another
outstanding catastrophic caller obligation does not make the public function
unsafe. The unsuffixed operation remains direct in both languages, and the
optional checked companion never changes its behavior.
[catalog/memory.py](src/tslc/catalog/memory.py) also owns whether indexed
operations consume one address per result-vector lane or per index-vector lane;
catalog validation requires that fact for indexed memory, and checked wrappers
validate the corresponding lane-count relationship before inspecting index
lanes or dispatching.
Compacted memory likewise carries both its mask-dependent payload extent and
the selected alignment contract. Checked wrappers validate capacity first and,
when an aligned specialization would access at least one element, validate the
selected vector alignment before dispatch. An all-inactive compacted operation
accesses no memory and therefore does not reject an empty, unaligned view.
[backend/cpp_checked_api.py](src/tslc/backend/cpp_checked_api.py) owns C++
signature/check projection, and the backend-neutral algorithm family inventory
and repeated callable forms in
[backend/algorithm_surface.py](src/tslc/backend/algorithm_surface.py) prevent
C++ and Rust algorithm surfaces from drifting. Typed range and result checks
remain owned by
[backend/algorithm_contracts.py](src/tslc/backend/algorithm_contracts.py);
each backend joins those target-neutral identities to its exact declaration
records and explicitly classifies unsupported forms. Iteration, predicate,
count, selection, index-producing, transform, consume, and aggregate
declarations and render-hole identities are expanded by focused backend
builders from those shared forms; exceptional target signatures remain explicit
inside the backend projection.

The ordinary Rust API is finalized before source rendering by the frozen records
in [backend/rust_api_model.py](src/tslc/backend/rust_api_model.py), the
cross-record invariants in
[backend/rust_api_model_validation.py](src/tslc/backend/rust_api_model_validation.py),
the joined semantic-and-call inventory in
[backend/rust_api_core.py](src/tslc/backend/rust_api_core.py), and focused
candidate, comprehensive, curated, and surface planners under `backend/rust_api_*`.
Rust facade checked-condition translation remains in
[backend/rust_facade_checked.py](src/tslc/backend/rust_facade_checked.py); the
renderer receives those finalized backend facts and only formats public items.
Primitive-call lowering records callee identities, source-located typed
precondition dispositions, and the necessary local Rust unsafe boundary.
Catalog validation and transitive closure reject or retain unresolved proof
gaps without inferring anything from raw target text.
The public
[backend/rust_api_planner.py](src/tslc/backend/rust_api_planner.py)
orchestrates those projections directly and preserves the compiler-facing
planning and validation API. The frozen plan owns its cross-record invariant
and invokes the focused validator on construction. The validator depends at
runtime only on shared facade enum vocabulary and semantic operations; model
and arm types are type-checking-only dependencies, so plan replacement remains
validated without a runtime import cycle.
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
static-selection, algorithm, facade, dispatch, policy-consumption, and
benchmark-layout plans once. The private project boundary in
[render/rust_project.py](src/tslc/render/rust_project.py) trusts and formats
those frozen plans; it does not replan or recompute-and-compare them.

The focused renderer in
[render/rust_facade.py](src/tslc/render/rust_facade.py) turns those finalized
shape records into sealed, opaque `Simd<T, N>` and `Mask<T, N>` values. A
compile target selects one exact private hardware representation or the
source-backed generic representation; no profile or extension is a Cargo
feature. Complete release metadata is carried through the backend-neutral
`ProjectRenderConfig` into the Rust package renderer, so templates format
configured Cargo facts rather than owning repository release policy. The Cargo
manifest uses an explicit source/test/benchmark include set: generated docs,
research history, scratch trees, and unrelated checkout files cannot enter the
published crate merely because documentation was built in place.

Generated documentation is assembled by
[maintenance/documentation.py](src/tslc/maintenance/documentation.py). Doxygen
consumes the documentation-only primitive facade plus stable core,
data-parallel, and ordinary/checked algorithm headers. Strict mode validates
typed public type and algorithm manifests, primitive prose, unique callable
identities, and ordinary twins for checked callables. Rustdoc treats the opaque
root facade and selected `profile` API as the stable documented boundary; its
public low-level substrate remains available for generated signatures but is
hidden from the stable overview. Shared examples and the Sphinx contract page
explain unchecked preconditions, checked errors, and residual language-level
obligations. The repository maintenance projections
[maintenance/public_api_baseline.py](src/tslc/maintenance/public_api_baseline.py)
and [maintenance/checked_api_census.py](src/tslc/maintenance/checked_api_census.py)
ratchet the typed v1 callable-family contract and exact checked coverage
separately; both load the typed corpus through one maintenance-only catalog
boundary. Each generated C++ and Rust project also carries `public-api.json`,
serialized from backend-owned frozen declaration records. Those records own
names, owners, reachability, overload identities, generic/template bounds,
parameters and roles, qualifiers or safety, results, checked twins, reexports,
stable type members, and stability classification. Static assets contain named
holes for stable declarations and retain implementation bodies; renderers and
the manifest consume the same records. A non-stable module/type may provide the
default classification for otherwise-unrecorded descendants, while every
stable exception remains an exact record. Rust reachability records include the
typed target architecture,
features, stronger-profile exclusions, and fallback selection. No compiler or
maintenance path parses or hashes generated target text to reconstruct this
contract. The schema-v3 release baseline ratchets the reviewed scalar/AVX2
records in addition to the per-project scope-exact manifests.

The repository release projection is split by ownership across
[maintenance/release_contract_model.py](src/tslc/maintenance/release_contract_model.py),
[maintenance/release_contract_policy.py](src/tslc/maintenance/release_contract_policy.py),
[maintenance/release_contract.py](src/tslc/maintenance/release_contract.py), and
[maintenance/release_contract_render.py](src/tslc/maintenance/release_contract_render.py).
It layers only product choices—version lines, release profile selection,
target-specific/portable exceptions, and fallback policy—over the typed catalog,
machine profiles, support policy, implementation-state meanings, and public-API
baseline. The generated JSON and Markdown are projections of the same frozen
model. Distributable packaging consumes that projection, while CI profile
sharding reads the same narrow policy file; neither owns a second release
profile list.

A static substrate ships as assets. C++ keeps
[backend/assets/tsl_core.hpp](src/tslc/backend/assets/tsl_core.hpp) as its stable
facade over a directly includable type foundation and focused memory, scalar,
integral-mask, and I/O runtime headers. Rust likewise keeps
[tsl_core.rs](src/tslc/backend/assets/tsl_core.rs) as the stable facade defining
its public representation types while private generated `tsl_core` children own
memory/allocation, scalar arithmetic and conversion, integral-mask, and text-I/O
runtime support. Explicit root and `detail::helpers` re-exports preserve the
existing visibility and generated paths; typed vector registrations append
their destination-validity proofs only to the scalar child. Whole-file
scaffolding and stable profile metadata also live there as named templates;
Python renderers supply only finalized, typed holes and dynamic declarations.
Backend target-text values use
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
the `sse2` register, whole-register cross-lane, and immediate families plus
`avx2` one-vector scalar reductions as standard-library-only custom Cargo
benchmarks. Native feature
detection consumes the profile family's typed strategy ID; concrete Rust
`target_arch` and feature-test macro spellings live in
[backend/rust_benchmark_detection.py](src/tslc/backend/rust_benchmark_detection.py),
not in profile-family-name branches. The compiler-cfg-gated hot loop lives
inside the library crate, and a thin
per-profile bench target invokes it only with the unpublished
`tsl_variant_benchmarks` compiler cfg plus the exact compiler-owned codegen and
target-feature flags. Those exact admissions and the deliberately narrow
compile-time selection pilot are backend-owned declarative evidence in
`backend/policy_assets/rust_policy.json`, strictly promoted by
[backend/rust_policy_manifest.py](src/tslc/backend/rust_policy_manifest.py).
The backend registry loads this resource once for each artifact-producing
request into a frozen `BackendPolicyInputs` snapshot at the compiler input
boundary. Benchmark planning, artifact rendering, and focused preview receive
that same explicit snapshot; importing a backend module performs no policy-file
I/O. For an unfiltered backend inventory, backend validation also emits
structured diagnostics unless every declared pilot matches exactly one lowered
slot; focused projections skip that full-inventory proof.
Unknown fields, duplicate identities, and live specializations that do not
match the complete declared identity fail closed; primitive, extension,
profile, and type literals do not appear in the planner's control flow.
Ordinary Cargo builds retain the authored wrapper choice.
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
while the Rust audit generates each selected profile independently and merges
the resulting typed plans instead of combining unordered compile targets in
one crate. Separate Rust evidence preserves every raw report gap plus exact
profile manifest, candidate ID/body hash, policy eligibility, and
compiler-rendered mapping hashes. Aggregate shape counts are explanatory
inventory, not the Rust ratchet identity. The public maintenance façade
([maintenance/benchmark_coverage.py](src/tslc/maintenance/benchmark_coverage.py))
owns CLI orchestration; frozen records, audit joins, and baseline serialization
live in `benchmark_coverage_model.py`, `benchmark_coverage_audit.py`, and
`benchmark_coverage_baseline.py`. Value-test tags do not control benchmark
admission.
Workload semantics are resolved in
[benchmark/scenarios.py](src/tslc/benchmark/scenarios.py) before rendering:
each typed scenario and correctness case validates its own structural and
specialization compatibility and owns its canonical policy identity. Candidate
sets only enforce homogeneous matching families. Harness discovery/closure is
checked through one planner boundary, while C++ scenario renderers supply typed
fragments to one shared timing skeleton; the remaining family dispatch selects
genuinely different input construction and invocation behavior. Lane-local
pure-register scenarios carry their operand generators and dependency parameter
and may tile authored correctness vectors. Whole-register cross-lane scenarios
use the same vector call wiring but require an authored correctness case at the
exact specialization width. Vector-plus-scalar scenarios
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
runs them — optionally under **Intel SDE**, **qemu-aarch64**, or
**qemu-riscv64** so target code runs on hardware that lacks it. Scalable
machine profiles may provide typed, named runner variants. The verifier builds
one value-test binary and executes that exact binary at every declared vector
length; CI consumes the same profile-owned matrix.

Verification writes mutable run evidence under
`.tslctmp/verification/attestation.json`, separately from deterministic
generated artifacts. The versioned attestation references both the compiler
input digest and `.tslc-manifest.json` digest, then records exact commands,
explicit command environment, runner CPU/profile and vector length, captured
outcomes, diagnostics, and skips. QEMU executions are correctness evidence;
their timings are not performance evidence. When a configured formatter is
invoked, the artifact writer re-hashes exactly the manifest-owned files before
verification, so the attestation identifies the bytes that were compiled.

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
  The opt-in exact target-support trace in
  [target_support.py](src/tslc/target_support.py) is different: selection owns
  its complete declaration/type/target universe, including slots with no
  candidate, and the pipeline advances each selected realization through
  `selected`, `lowered`, `pruned`, `policy_deferred`, or `emitted`. Emitted
  realizations retain the propagated implementation state. The release-only
  [target_support_ratchet.py](src/tslc/maintenance/target_support_ratchet.py)
  filters those facts through the typed v1 support contract and serializes the
  exact SVE/SVE128/SVE256/SVE512/RVV baseline; it never selects or infers a
  body itself. Release CI uses `--require-complete`, so a previously recorded
  absent, selected-only, deferred, or pruned applicable slot is still a
  failure; impossible source/target pairs must be declared as reviewed typed
  exclusions rather than hidden in the baseline.
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
  [ir/scan.py](src/tslc/ir/scan.py), and [ir/cursor.py](src/tslc/ir/cursor.py).
- Orchestration and request ownership: [pipeline.py](src/tslc/pipeline.py) and
  [pipeline_request.py](src/tslc/pipeline_request.py).
- A real primitive with all the moving parts:
  [`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl).
