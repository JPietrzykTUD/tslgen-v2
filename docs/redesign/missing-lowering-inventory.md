# Missing Lowering Inventory

This document is the living inventory of known missing lowering work. It keeps
the deferred lowering surface in one place so future milestones can choose the
next focused slice without rediscovering the same gaps from the roadmap,
behavioral matrix, and open questions.

The inventory is documentation only. It is not a runtime input, generated
artifact, source scanner, dependency-closure plan, or completeness oracle.
Future milestones may cite it, but implementation must still be driven by
typed redesign contracts, explicit evidence, diagnostics, and tests.

## Current Baseline

Accepted through M187:

- Generation-time lowering handles only the accepted typed helper/predicate
  forms from M38, M41-M43, M48, M51-M59, and M67-M72.
- Selected body lowering handles only the accepted M60-M63 selected-body
  handoff/form/body-IR/envelope path.
- Exact array-body lowering handles only the accepted M64-M76 structural and
  request forms plus M87-M92 return/package/backend-handoff slices.
- Stage 8 operation packages, completion manifests, gap inventories, stage
  assembly, backend-translation request inventories, the exact C++
  backend-uninit translation-result boundary, the first lowering IR
  taxonomy/provenance contract, and the first typed category/protocol surface
  are accepted through M93-M102.
- Broad backend translation, Stage 9 planning, renderer-ready IR, rendering,
  generated output, dependency closure, Rust uninit translation, and broad TSIL
  semantics remain deferred unless a milestone explicitly selects a narrow
  slice.
- The clean restart M127-M156 line has accepted real TSIL payload intake,
  source-owned body tokens, directive-envelope classification, primitive-call
  island classification, selected implementation context/type-query lowering,
  extension/register/mask facts, primitive-call selector payload lowering,
  target matching, raw argument binding, reference inventory, dependency
  closure, exact return-call expression lowering, and primitive-call
  resolver/collector consolidation, helper raw preservation, and
  generation-value query inventory plus isolated selected-context
  generation-value query lowering for the M155 scalar/current-vector/
  primitive-attribute subset, exact M156 selected-branch token selection
  for two-arm `if<generation>` / `else<generation>` regions, M157
  selected-branch handoff into already accepted direct body lowering, M158
  exact integer comparison predicates, M159 explicit
  `arith<generation>::add/sub/mul/div/rem(...)` integer arithmetic inside
  `value<generation>(...)`, M160 exact selected-body
  `else if<generation>` branch-chain selection with an optional final
  `else<generation>` fallback, M161 exact `loop<range>(...)` region facts
  with optional adjacent `loop<unroll>(...)` metadata, M162 discovery of every
  exact top-level M161 loop region inside arbitrary source-owned body token
  streams, M163 exact top-level classified `var<...>(...)` declaration request
  discovery with opaque type/initializer payload text, and M164 exact
  `value<backend>(...)` backend value query request discovery over
  source-owned text, and M165 exact classified backend-control directive
  request discovery for `if<compile>(...)`, `else<compile>`, and
  `switch<compile>(...)`, M166 exact backend intrinsic request-island
  discovery for `intrin<...>(...)` and `intrin_compose<...>(...)` over
  source-owned text and contiguous raw body-token runs, and M167 exact
  source-operation request-island discovery for `cast<...>(...)`,
  `mem<...>(...)`, and `io<...>(...)` over source-owned text and contiguous
  raw body-token runs, M177 exact mask lane constant backend/support-helper
  request discovery, M178 shared source-island scanner consolidation, M179
  exact `type<backend>(...)` backend type query request-island discovery,
  M180 exact backend type query island handoff to existing
  `BackendTypeSpellingRequest` values, M181 exact backend-value payload
  handoff for the five observed backend-value families, M182 exact
  top-level intrinsic-compose modifier handoff, M183 exact source-operation
  selector handoff for the observed cast/memory/I/O selectors, M184
  lowering completeness audit, and M185 exact `mask<...>(...)` mask keyword
  request discovery/classification for the observed `zero`, `test`, `set`,
  and `set:1` selectors, M186 typed generation boolean condition grammar
  lowering for `if<generation>` / `else if<generation>` conditions over
  accepted boolean leaves, integer-comparison leaves, `!`, `&&`, `||`, and
  parentheses, and M187 exact backend/output source-island discovery for
  `assume_aligned<...>(...)`, `array_type<...>`, and `pack<...>(...)`
  with opaque payload preservation. That path deliberately still does not render
  primitive-call expressions, declarations, loops, backend values, backend
  type spellings, backend control flow, intrinsic calls, cast/memory/I/O
  calls, mask keyword calls, or backend/output helper islands; parse raw
  arithmetic operators; parse broad TSIL expressions/statements; execute
  loops; support recursive generation control; or translate/render the
  accepted backend type/value/source operation/mask/backend-output spelling
  requests.

M184 records a focused completeness audit in
`docs/redesign/lowering-completeness-audit.md`. M185 resolved the audit's
selected `mask<...>(...)` lowering-owned gap at the request/selector
boundary. The audit still classifies `details::*`, backend-control rendering,
backend intrinsic/source-operation translation, raw target-language text, and
backend translation metadata as backend-owned, source-convention, or deferred
rather than next lowering implementation. Interactive review after M186
clarified that `assume_aligned<...>(...)`, `array_type<...>`, and
`pack<...>(...)` should not be semantically solved by lowering, but may still
require one exact typed backend/output request-island discovery milestone so
later backends can consume them intentionally.

The post-M185 lowering completion gate found one remaining lowering-owned
condition-expression gap before the project could honestly leave lowering:
current primitive bodies contained 15 bare
`if<generation>(type::is_same(...))` conditions, including three exact
two-term top-level `type::is_same(...) || type::is_same(...)` disjunctions.
M186 closed that gap with a small typed TSIL generation boolean condition
grammar over accepted generation expression/value leaves, integer comparison
leaves, `!`, `&&`, `||`, and parentheses. Recursive branch
lowering, plain target-language `else`, arbitrary target-language expression
parsing, backend translation/rendering, and the backend/output-owned families
listed above remain out of scope.

The post-M186 lowering completion gate selected M187 as one remaining
lowering-owned request discovery gap. M187 accepted exact backend/output
source-island discovery for `assume_aligned<...>(...)`, `array_type<...>`,
and `pack<...>(...)`. The accepted boundary is intentionally opaque and does
not solve alignment, array type/layout, or pack semantics.

## Post-M152 Clean Restart Lowering Paths

The next clean restart milestones should choose from these generation-relevant
TSIL keyword lanes. This list records the missing paths; it is not permission
to implement several lanes in one milestone.

| Path | TSIL surface | Why it matters | Boundary |
| --- | --- | --- | --- |
| Generation value/query lowering | `value<generation>(...)` forms from the current corpus plus explicit future generation-value functions | Generation-time conditions, loop bounds, declarations, type predicates, vector metadata, primitive attributes, and selected source regions depend on typed values rather than raw helper text. | M155 accepts isolated selected-context evaluators for vector length/alignment, scalar type facts, and concrete boolean primitive attributes. M158 accepts exact integer comparisons over accepted integer value queries. M159 accepts explicit function-shaped integer arithmetic via `arith<generation>::add/sub/mul/div/rem(...)` inside `value<generation>(...)`. Remaining value families should still be selected explicitly and must not add a general expression parser or raw operator parser. |
| Generation control lowering | `if<generation>(...)`, `else if<generation>(...)`, `else<generation>` | Real bodies need selected-branch pruning before backend rendering. | M156 accepts exact two-arm `if<generation>(VALUE_QUERY) { ... } else<generation> { ... }` token regions for M155 boolean conditions and preserves selected/unselected branch token slices. M157 hands selected branch tokens to existing direct body lowering. M160 accepts exact classified `else if<generation>` branch-chain selection with an optional final `else<generation>` fallback and first-true/no-match behavior. M186 accepts a typed generation boolean condition grammar over accepted boolean/integer-comparison leaves, `!`, `&&`, `||`, and parentheses. Plain target-language `else`, recursive branch lowering, arbitrary target-language expression parsing, and rendering remain deferred. |
| Generation declaration/iteration lowering | `loop<unroll>(...)`, `loop<range>(...)`, `var<...>(...)`, non-type `let<...>(...)` | Generic/vector fallback bodies use TSIL directives for repeated statements, declarations, temporaries, and aliases. | M161 accepts an exact `loop<range>(...)` region fact with optional adjacent `loop<unroll>(...)` metadata over source-owned body tokens. M162 discovers every exact top-level M161 loop region inside arbitrary body token streams and preserves non-loop tokens as opaque spans. M162.5 refactors shared lexical delimiter/top-level scanning without adding new source behavior. M163 accepts exact top-level classified `var<init_register>`, `var<infer>`, `var<const_infer>`, and `var<typed>` declaration facts as unresolved backend-facing requests with opaque type/initializer payload text. `let<type>(...)` alias facts already feed the type environment. Loop execution/unrolling, loop-variable substitution, declaration rendering, raw multiline declaration-token intake, and broad surrounding target-language statement parsing remain deferred. |
| Backend query lowering | `value<backend>(...)`, accepted `type<backend>(...)` requests | Backend spellings, suffixes, uninit values, and type spellings must be derived from typed semantic values before rendering. | M164 accepts exact `value<backend>(...)` request islands as unresolved backend-owned facts over source-owned text. M179 accepts exact `type<backend>(...)` request-island discovery over source-owned text and contiguous raw body-token runs, keeping raw islands distinct from `BackendTypeSpellingRequest`. M180 accepts handoff from those exact discovered islands to existing selected-context `lower_backend_type_query(...)` semantics, producing existing `BackendTypeSpellingRequest` values while preserving opaque surroundings. M181 accepts handoff from M164 backend-value query islands to one typed unresolved backend-value request boundary for the five observed payload families: `intrin::suffix...`, `intrin::prefix`, `uninit::array`, `uninit::scalar`, and `x86::mm_fround_to_zero`. Backend translation requests/results, backend maps, backend value evaluation, and rendering remain deferred. Renderers must not evaluate raw query text. |
| Backend control lowering | `if<compile>(...)`, `else<compile>`, `switch<compile>(...)` | Backend-specific compile-time control appears in current `tsldata` bodies. | M165 accepts exact classified compile-control directive request facts over source-owned body tokens. Backend-control translation, rendering, branch selection, and block matching remain deferred. `if<runtime>` / `else<runtime>` are absent from the current corpus and should remain future/diagnostic unless new source data adds them. |
| Backend-owned operation lowering | `intrin_compose<...>(...)`, `intrin<...>(...)` | Intrinsic calls are generation relevant but backend-owned, not portable primitive semantics by themselves. | M166 accepts exact intrinsic request-island discovery in source-owned text and contiguous raw body-token runs. M182 accepts a handoff for top-level `intrin_compose<...>` modifier fields into typed unresolved modifier facts while preserving direct `intrin<...>` names and intrinsic arguments opaque. Backend intrinsic translation, argument splitting, modifier evaluation, and rendering remain deferred. |
| Primitive-call completion | Nested and surrounding `call<primitive=...>(...)` islands | M144-M152 can classify, match, bind, and collect primitive-call dependencies. M170 lets selector payloads consume explicit selected specialization facts for bare base, extension, and vector/type binding names. M171 lets target matching carry the exact concrete-vector plus selected return-binding selector shape into the matched target context. M172 lets target matching consume already lowered concrete vector-transform aliases. M173 lets `MaskVec`-style aliases participate only when vector member type queries resolve through fixed typed metadata and accepted scalar descriptors; M174 completes descriptor coverage for current real `ui8`/`ui16`/`ui64` member results. Complete generation still needs recursive token-stream use, backend rendering, and deterministic output scheduling. | Extend the existing call boundary only when a selected milestone needs recursive/nested calls or rendering. Avoid context-specific consumers for every possible surrounding syntax. |
| Cast/memory/I/O keyword families | `cast<...>`, `mem<...>`, `io<...>` | These are generation-relevant backend/source directives that appear in broad body contexts. | M167 accepts exact request-island discovery over this shared outer keyword shape in source-owned text and contiguous raw body-token runs. M183 accepts classification of the exact observed selector payloads into typed finite selector values while keeping arguments opaque and backend/source-operation translation deferred. Type lowering inside payloads, argument splitting, rendering, and recursive payload discovery remain deferred. |
| Mask keyword family | `mask<zero>()`, `mask<test>(...)`, `mask<set>(...)`, `mask<set:1>(...)` | Primitive bodies use `mask<...>(...)` as a real TSIL-like keyword family distinct from M177 mask lane constants. | M185 accepts exact request-island discovery and typed selector classification only. Backend mask helper translation, argument splitting, recursive payload lowering, and surrounding expression parsing remain deferred. |
| Backend/output source-island family | `assume_aligned<...>(...)`, `array_type<...>`, `pack<...>(...)` | Backend/output stages need structured request identity for source forms that must not remain anonymous raw text, while their semantics remain backend/rendering-owned. | M187 accepts exact island discovery for all three forms with opaque payload preservation. Alignment, array layout/type, pack semantics, argument splitting, nested payload lowering, and rendering remain out of scope. |
| Body-token rendering policy | Raw target-language text plus accepted lowerable TSIL islands | Generated artifacts need a way to emit raw source text around lowered islands without turning lowering into a C++/Rust parser. | Backend rendering/output integration consumes typed lowering results and source-owned raw tokens. This is not helper-call substitution or source repair. |

Not a lowering path by default: `details::arith_add`,
`details::arith_mul`, `details::arith_rem`, `details::popcount`,
`details::clz`, `details::clz_recursive`, `details::ctz`, and
`details::mask_test`. They are source-authored/backend-support helper calls
unless a future milestone explicitly introduces typed support-helper
availability facts for backend output integration.

Generation-time arithmetic must be explicit TSIL, not guessed from raw target
syntax. The accepted M159 shape is `arith<generation>::...` inside
`value<generation>(...)`; raw `+`, `-`, `*`, `/`, and `%` remain source text
unless a later milestone explicitly accepts a narrower source form with tests.

## Post-M155 Generation Value Query Boundary

M154 records the current `value<generation>(...)` corpus in
`docs/redesign/generation-value-query-inventory.md`: 597 query islands across
24 `tsldata/**/*.tsl` files, grouped into 10 semantic query families and 13
exact observed forms. All prompt-listed families are present, and the
additional observed exact form is `value<generation>(mask::lane::all_false)`.

M155 implements the selected largest-safe executable slice as selected-context
generation value query lowering for isolated query islands:

- `value<generation>(vector::length)`;
- `value<generation>(vector::alignment)`;
- `value<generation>(type::size_bytes(TYPE_EXPR))`;
- `value<generation>(type::is_signed(TYPE_EXPR))`;
- `value<generation>(type::is_same(TYPE_EXPR, TYPE_EXPR))`;
- `value<generation>(primitive::attribute(KEY))`.

This subset covers 474 current query islands and shares one explicit typed
input boundary: selected implementation context, `CurrentVector`
extension/type facts, selected scalar `TypeTag`, extension metadata, selected
type aliases, and concrete selected primitive attributes. For `type::*` value
families, `TYPE_EXPR` arguments lower through the accepted type lowering path
first and only supported lowered scalar type values are evaluated; exact raw
nested strings such as `type<generation>(base::in)` are evidence, not the
matching boundary. Surrounding consumers remain separate work:
`if<generation>` branch pruning, `loop<...>` execution, declarations,
selector-attribute substitution, comparison predicates, explicit generation
arithmetic functions, raw expression parsing, primitive-call rendering,
backend rendering, and source replacement
are not part of the selected value-query slice.

Deferred generation-value sublanes after M155:

| Sublane | Evidence | Missing prerequisite |
| --- | --- | --- |
| Vector member type values | `type::size_bytes(type<generation>(vector::register))`, `type::size_bytes(type<generation>(vector::imask))`, `type::is_signed(type<generation>(vector::imask))` | M175 connects descriptor-backed fixed vector member type facts from M173/M174 into existing `type::*` generation value evaluators when an explicit catalog is supplied. M175.5 additionally lets `type::size_bytes(...)` compute fixed byte sizes for `vector::register`, lane-bitmask mask/imask/underlying members, and lane-keyed native predicate masks from typed extension metadata. Backend-owned spelling, runtime/scalable, symbolic/generic, missing metadata, unsupported policy, and no-catalog cases remain diagnostics or deferred backend facts. |
| Mask lane constants | `mask::lane::all_true`, `mask::lane::all_false` | M177 implements typed backend/support-helper request discovery for exact mask lane constants in source-owned text and selected body raw-token text. Backend helper rendering, source convention cleanup, and treating these constants as Python booleans remain out of scope. |
| Generic vector lengths | `generic::length(OutVec)`, `generic::runtime_length(ToType)` | M168 lowers exact `generic::length(TYPE_EXPR)` and fixed-vector `generic::runtime_length(TYPE_EXPR)` as selected generation expressions after type-alias/type-query lowering. M169 lets explicit selected specialization bindings make aliases concrete when they flow through declared return-type symbols, and lets explicit vector/type bindings make `ToType`-style `TYPE_EXPR` values concrete before `generic::*` evaluation. Runtime/scalable, size-parameter-only, unresolved alias/specialization, non-vector, and metadata-missing forms remain diagnostic boundaries, not guessed generation values. |

M99 is accepted:

```text
Milestone 99: Operation Package Backend-Translation Request Inventory Slice
```

For M99, "backend-translation request inventory" means a typed Stage 8
inventory/provenance view over already accepted deferred/backend-scoped request
facts. It does not translate, resolve, evaluate, plan, or render those facts.
The accepted M99 inventory records exact-array
`exact_array_backend_value_uninit_array`, selected-body
`selected_body_direct_intrinsic_handoff`, and
`no_accepted_backend_scoped_request` states.

Post-M99 planning selected and M100 execution accepted:

```text
Milestone 100: Exact Array Backend-Uninit Translation Result Boundary Slice
```

M100 is the first accepted request-to-translation-result boundary. It narrows
only the exact-array `exact_array_backend_value_uninit_array` request to typed
C++ backend-uninit translation-result state from explicit typed rule/metadata
input. It does not render C++ or Rust code, start Stage 9 backend planning,
resolve Rust `value_array_uninit`, evaluate generic backend helpers, resolve
selected-body direct intrinsics, read backend maps/catalogs/manifests, or treat
this inventory as a runtime input.

Post-M100 planning selected and M101 execution accepted:

```text
Milestone 101: Lowering IR Taxonomy Contract and Backend-Translation Provenance Consolidation Slice
```

M101 is accepted as a behavior-preserving consolidation milestone before
adding more lowering features. It defines a smaller vocabulary for lowering
facts, requests, results, inventories, provenance, rule inputs, and stage
envelopes, then applies that contract only to the accepted M99/M100
backend-translation request/result path. It did not introduce new backend
semantics, Stage 9 planning, rendering, output, Rust translation, generic
backend helper evaluation, raw source parsing, source repair,
direct-intrinsic/SVE semantics, or a broad inheritance/registry/dispatcher
mechanism.

Post-M102 planning selected:

```text
Milestone 103: Stage 8 Backend-Translation Boundary Worklist Inventory Slice
```

M103 adds a static typed inventory/provenance view over accepted M99/M100
backend-boundary facts. It is not a scheduler, dependency-closure plan, Stage 9
backend plan, renderer-ready IR, completeness oracle, source scanner,
backend-map evaluator, registry, dispatcher, hidden backfeed, or fixpoint
mechanism.

M104 accepts a broadened but still single-boundary lowering milestone: M103
worklist entry to typed backend translation expansion result. M104 narrows both
exact-array backend-uninit unresolved entries and selected-body direct-intrinsic
deferred entries, but only through explicit typed rule inputs over accepted
concrete worklist/request/result facts.

M97's no-known-gap state is not a statement that no lowering work is missing.
It only means the accepted M96 manifest has no currently supported
manifest-visible unresolved backend-handoff dependency records. This document
tracks the broader known missing lowering surface.

M105 records the KISS generator restart charter rather than another lowering
micro-layer. The missing lowering surface below remains useful evidence, but
it is not a mandate to keep extending the accepted M57-M104 request/result/
worklist chain. Restart milestones should first prove the simple product path
from `.tsl` source data to deterministic C++ and Rust library artifacts, then
reintroduce lowering concepts only where two concrete stages need a shared
typed boundary. M106 performed the structural layout reset before that product
path starts: old `tslgen/` state now lives under `tslgenold/`, and fresh
`tslgen/` is reserved for clean implementation.

## Missing Work

| Area | Evidence paths | Current accepted boundary | Required typed fact/request | Candidate milestone | Boundary notes |
| --- | --- | --- | --- | --- | --- |
| Stage 8 to backend handoff | `tsldata/primitives/load_store/array.tsl`, accepted M92/M96/M97/M99 records | M99 accepts the first cross-package backend-scoped request inventory over accepted package/manifest/gap facts; M100 accepts one exact C++ backend-uninit translation-result boundary after that inventory; M103 accepts a static worklist inventory over accepted M99/M100 states; M104 accepts typed translation expansion results over selected M103 worklist entries. | Additional typed request/result families as they are accepted; later backend resolution/translation consumes the inventory/result surface. | Accepted M104 worklist-driven backend translation result expansion | M104 deliberately broadens from one literal classification to one documented gap: M103 worklist entry to typed translation expansion result. The worklist remains static inventory/provenance, not Stage 9 planning, rendering, output, scheduling, dependency closure, readiness, source scanning, backend-map evaluation, or inferred requests. |
| Backend value/type requests | `tsldata/detail/lang/types/types_cpp.tsl`, `tsldata/detail/lang/translate_cpp.tsl`, array/uninit evidence | M72 preserves exact `value<backend>(uninit::array)` as deferred state; M92 carries it as handoff; M99 inventories it as `exact_array_backend_value_uninit_array`; M100 resolves that exact C++ request to a typed translation-result value from explicit typed rule input; M103 classifies translated/unresolved states in the backend-boundary worklist; M104 accepts explicit-rule exact-array unresolved translation expansion. M179 discovers raw `type<backend>(...)` islands, and M180 turns those raw islands into existing `BackendTypeSpellingRequest` values without rendering. | Typed backend value/type request records over already resolved semantic values; additional exact/broad value/type results remain missing. | M180 accepted for raw backend type query island to `BackendTypeSpellingRequest` handoff; later slices cover Rust typed context, backend value payload semantics, and broader backend translation results. | Do not parse raw helper text, read backend maps/catalogs/manifests during lowering, or evaluate backend maps in renderers. Rust remains deferred unless a future slice introduces explicit typed `{type}` context; broad Rust rendering remains deferred. |
| Lowering IR taxonomy and provenance | Accepted M57-M102 lowering stage/result modules; M99/M100 backend-translation request/result path | M101 adds the first private taxonomy/provenance contract and M102 adds the first typed category/protocol surface, applied only to M99/M100 backend-translation request/result classes. | Future feature-specific IR should conform to the accepted category/protocol surface before adding one-off request/result layers. | Accepted M101/M102 over M99/M100 only | Behavior-preserving consolidation only: no new lowering semantics, no broad hierarchy, no registry/dispatcher, no public `LoweringRequest` rename, and no weakening of diagnostics or object-identity guarantees. |
| Direct intrinsics | `tsldata/primitives/load_store/array.tsl`, `load_store/store.tsl`, accepted M62/M63/M76/M95 facts | M62/M63/M95 preserve only selected assignment direct-intrinsic facts; M76 preserves one exact post-branch call-site structural request; M99 inventories accepted selected-body direct-intrinsic handoffs as backend-scoped requests; M103 classifies selected-body handoff as deferred; M104 accepts explicit-rule selected-body direct-intrinsic translation expansion. | Typed direct-intrinsic call/body request records and diagnostics. | Later direct-intrinsic broadening over typed context/rules | No SVE hardwiring, byte-size-to-token inference, intrinsic-text dispatch, extension-id dispatch, primitive-name dispatch, or resolver choice. M104 uses explicit typed rule input and produces typed deferred/unsupported state when no rule applies. |
| Intrinsic modifiers | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `frozen/tsl-gen/tsl_gen/tsil.lark` | M182 hands exact M166 `intrin_compose<...>(...)` islands to typed top-level modifier records for `prefix`, `suffix`, `infix`, `infix_sep`, `post`, and `immediate(N)` fields, reusing M181 only for modifier values that are exactly one `value<backend>(...)` island. | Later backend translation result records for resolved modifier text and rendered intrinsic calls. | Later backend intrinsic translation/rendering slice | M182 is handoff only. Translation consumes typed records; renderers do not infer modifiers from raw angle payload text. |
| Primitive calls and dependencies | `frozen/tsl-gen/tsl_gen/tsil_engine/dependencies.py`, `tsldata/primitives/**.tsl` | Candidate fallback visibility exists; semantic TSIL call AST and dependency closure remain deferred. | Typed primitive-call IR, dependency request records, and closure policy. | Later call/dependency slice | No dependency closure hidden inside lowering inventories. |
| Backend/support helper calls | `tsldata/primitives/arithmetic/complex.tsl`, `tsldata/primitives/arithmetic/horizontal.tsl`, `tsldata/primitives/load_store/sequence.tsl`, `tsldata/detail/lang/translate_rust.tsl`, `docs/redesign/tsil-surface-inventory.md` | M127 inventories `details::arith_add`, `details::arith_mul`, and `details::arith_rem`; product review classifies them with other predefined backend/language support helpers, not as semantic lowering islands. | No lowering fact is required for these helper names by default. Future backend rendering/support-library work may need typed support-helper availability facts, but lowering should preserve the calls as source-authored text. | M153 backend-helper raw preservation boundary | Lock down that `details::arith_add`, `details::arith_mul`, and `details::arith_rem` are raw/predefined helper calls. Do not rewrite them to operators, parse surrounding assignments, loops, array indexing, or expressions, or sweep support helpers into semantic operation lowering. |
| Body structure | `frozen/tsl-gen/tsl_gen/tsil.lark`, `tsldata/primitives/load_store/*.tsl` | M64-M76 and M87 cover only named exact array-body slots and trailing `emit_return(tmp);` request structure. | Typed body model for loops, variables, scopes, assignments, indexing, declarations, arrays, stores, returns, and casts. | Later body-model slices | Introduce real TSIL/body models when needed; do not grow regex-like recognition. |
| Generation expressions | `tsldata/primitives/bitwise/shifts.tsl`, `conversion/repr_change.tsl`, `load_store/*.tsl` | M55-M59 cover size-byte value, selected arithmetic, equality predicates, and one exact branch-chain form. M48/M51/M52 cover selected signedness forms. | Typed evaluator functions for selected comparison, boolean, arithmetic, nested expression, and branch families. | Later generation-expression slices | Preserve selected-branch-only diagnostics; no renderer evaluation. |
| Vector/register metadata | `tsldata/primitives/load_store/load.tsl`, `store.tsl`, `conversion/repr_change.tsl` | M70/M71 resolve only exact array-initialization vector length/alignment requests from explicit metadata. | Typed vector/register/generic metadata facts and validation. | Later vector-metadata slices | Metadata must be supplied before lowering evaluation; no host CPU or token inference. |
| Source-body coverage | `tsldata/primitives/**.tsl` | Accepted narrow forms are named exact shapes; nearby malformed forms are diagnostic boundaries. | Explicit accepted forms or typed parser/model slices. | Per-family slices | Do not repair, complete, reorder, normalize, or guess source bodies. |
| Renderer-ready body IR | Accepted M93-M103 package/manifest/gap/request-inventory/worklist state | Current Stage 8 packages, manifests, gaps, request inventories, and M103 worklists are provenance/readiness only, not renderer-ready IR. | Backend-translated body/value IR after typed request resolution. | Later Stage 8/Stage 9 boundary after M104 result expansion | Keep Stage 8 inventories and M104 translation expansion results separate from renderer readiness. |
| Backend maps and support decisions | `tsldata/detail/lang/*.tsl`, backend manifests | M40/M45/M46 cover selected translation values for native add; M99 adds inventory only; M100 accepts one explicit-rule C++ result; M103 classifies accepted facts only. | Typed backend translation results and support diagnostics. | M104 explicit-rule translation expansion; Stage 9/backend slices later | Backend translation consumes typed requests and metadata; no raw generation helper text or backend-map/catalog/manifest reads during M103/M104. |
| Output integration | `frozen/out/**`, `frozen/run_all.sh`, generated-output docs | Narrow output/report/test slices are accepted, but broad output remains outside lowering. | Renderer-ready values, artifact plans, writers, and optional toolchain execution policies. | Output/backend phases | Not lowering work, but blocked on typed lowering/backend results. |

## Guardrails

- Treat accepted `.tsl` bodies as source inputs, not repair targets.
- Consume accepted typed Stage 8 facts; do not reparse raw implementation text
  unless a future milestone explicitly creates a typed body parser/model.
- Do not use source locations, extension ids, backend ids, primitive names,
  selected type tags, direct-intrinsic tokens, or hardware-looking tokens as
  semantic dispatch keys.
- Keep inventories as inventories: no backend planning, operation scheduling,
  dependency closure, renderer-ready IR, rendering, output, hidden backfeeds,
  or fixpoint behavior.
- Keep M100 translation results as typed backend value state only: no
  renderer-ready IR, generated source, artifact plans, Stage 9 planning, Rust,
  direct-intrinsic/SVE semantics, or generic backend helper evaluation.
- Keep new ownership in focused private modules and keep public facade changes
  narrow and tested.
- Before adding another feature-specific lowering request/result family, check
  whether a taxonomy/provenance consolidation slice is needed instead.
- For restart work, do not treat this inventory as a product roadmap. Use it
  as evidence for requirements, diagnostics, and traps to avoid while proving
  source-to-artifact slices through the KISS restart charter.

## Maintenance Rule

Every future lowering planning or execution milestone should update this file
when it accepts, resolves, narrows, or newly discovers a lowering gap. If a
milestone deliberately leaves a gap unresolved, record the boundary rather than
encoding the gap as a silent assumption.
