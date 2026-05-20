# Generation-Time Semantic Lowering Contract

Milestone 41 defined the contract for generation-time helper semantics that
must run before backend translation. Milestone 42 implements the first selected
slice: boolean primitive-attribute branch pruning for `aligned`. Milestone 43
implements the next slice: exact base scalar type queries. For prose only,
`base::signed_of(base::in)` and `base::unsigned_of(base::in)` may be used as
shorthand, but accepted TSIL syntax requires the full nested forms documented
below.

## Ordered Contract

The accepted order is:

1. TSIL helper parsing / recognition.
2. Generation-time semantic lowering.
3. Backend translation.
4. Backend rendering.

`if<generation>(...)`, `type<generation>(...)`, and
`value<generation>(...)` must resolve during generation-time semantic lowering.
Backend translation may consume `type<backend>(...)` and
`value<backend>(...)` only as backend-scoped requests whose inputs are already
typed semantic values.

Backend translation must reject unresolved generation-time helper IR. Backend
renderers must never parse or evaluate generation-time helpers.

## GenerationContext Contract

The implemented helper slices use an explicit immutable `GenerationContext`
rather than raw parser dictionaries or backend renderer state.

| Field | Status | Purpose |
| --- | --- | --- |
| selected primitive name | available in M42 | Diagnostic and provenance anchor for branch/query resolution. |
| emitted primitive name | available in M42 | Stable output-facing name when it differs from source primitive identity. |
| selected candidate id | used in M42 | Deterministic identity for one implementation candidate. |
| normalized signature | available in M42 | Confirms the helper is evaluated for the selected overload shape. |
| parameter list | used in M42 | Keeps diagnostics tied to the selected implementation signature. |
| primitive attributes | used in M42 | Supplies boolean values such as `aligned` and `packed`. |
| implementation source location | used in M42 | Provides actionable diagnostics for malformed or unsupported helpers. |
| backend id | likely later | Required for backend-scoped requests after generation values are typed. |
| extension and source extension | likely later | Required for vector metadata, intrinsic suffixes, and conversion helpers. |
| selected type tag | implemented in M43 | Required for base scalar type queries before suffix and signedness work. Defaults from the selected candidate type tag when `GenerationContext.type_tag_override` is absent and candidate defaulting is enabled. |
| type tag override | implemented in M43 | Explicit request-local test/diagnostic override. `GenerationContext.type_tag_override` wins over `selected_type_tag` and the selected candidate type tag. |
| backend type spelling | likely later | Consumed by backend translation and rendering after type resolution. |
| vector/register metadata | partially selected | M70 accepts explicit vector-length metadata for the exact array-initialization request, and M71 accepts explicit vector-alignment metadata for the sibling request. Broad vector/register metadata remains later. |
| primitive attributes with non-bool values | likely later | Needed if non-boolean attribute queries are selected. |
| resolved template | likely later | Required by wrapper/body helper families beyond the first branch slice. |
| parameter roles | likely later | Needed for masks, immediates, and pointer/load/store roles. |
| immediate/generic parameters | likely later | Needed for `sImm`, `immediate(n)`, and generic extension calls. |
| selected feature requirements | likely later | Useful for diagnostics and target-specific helper validation. |
| language/type map boundary | likely later | Supplies typed language data for backend type requests. |
| translation map boundary | likely later | Supplies backend translation metadata after semantic values resolve. |
| local variables and aliases | deferred | Needed for `let<type>`, loops, and primitive-call expansion. |
| full expression scope | deferred | Needed for general TSIL expression evaluation. |
| mask lane constants | deferred | Needed for mask helpers such as `mask::lane::all_true`. |

## Helper Inventory

Inventory method: search the current corpus with
`rg -n "if<generation>|type<generation>|value<generation>|type<backend>|value<backend>|suffix=|prefix=|post=|infix=|immediate\\(" tsldata/primitives`.
Repeated forms are grouped by helper family so future slices can choose one
behavior without treating the whole corpus as implemented.

| Observed form | Evidence | Apparent semantics | Required context | Candidate lowered IR concept | Backend/data dependency | Priority | Future status | Validation strategy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `if<generation>(value<generation>(primitive::attribute(aligned)))` | `tsldata/primitives/load_store/load.tsl:55-70`, `load.tsl:79-91`, `store.tsl:54-64`, `store.tsl:75-85` | Select aligned or unaligned branch for load/store bodies. | Primitive attributes, candidate id, source location. | Boolean primitive-attribute condition plus pruned branch provenance. | No backend data for the condition itself; branch bodies may contain backend requests. | required-now | Implemented by Milestone 42. | Unit tests cover true/false pruning, missing/non-bool/unknown attributes, selected-branch-only diagnostics, and deterministic output. |
| `if<generation>(value<generation>(primitive::attribute(packed)))` | `tsldata/primitives/load_store/store.tsl:177-188`, `store.tsl:196-210` | Select packed mask-store path. | Primitive attributes, mask parameter role, vector metadata. | Same branch-pruning model as `aligned`, with mask-specific context later. | Mask/vector type data for selected branch. | required-later | Defer until mask store parity is selected. | Reuse branch evaluator after selected mask fixture exists. |
| `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))` | Exact `else<generation>` forms in `tsldata/primitives/bitwise/shifts.tsl:535-547`, `shifts.tsl:625-635`, `shifts.tsl:842-887`, `shifts.tsl:933-943`, `shifts.tsl:1222-1244`, `shifts.tsl:1268-1280`, `shifts.tsl:1465-1481`, and `shifts.tsl:1507-1518`; plain-`else` evidence in `tsldata/primitives/conversion/repr_change.tsl:1210-1217`, with additional same-predicate evidence at `:540-649`, `:1093-1100`, and `:1160-1167`. | Select signed or unsigned branch behavior. | Type tag from typed M43 `GenerationTypeRef(kind="base.in")`, plus M42 branch provenance context. | Boolean `GenerationValue` derived from typed type query and pruned branch provenance. | No backend data for the predicate itself; selected branch bodies may contain backend requests. | M48 implemented `else<generation>`; M51 implemented exact plain `else` | M51 accepts only the exact plain-`else` syntax for this predicate. Branch bodies, conversion parity, and broad plain-`else` support remain deferred. | True/false pruning, selected-branch-only diagnostics, unsupported predicate/type diagnostics, missing type context, raw-helper rejection, and no conversion-body lowering. |
| `type<generation>(vector::register)` | `tsldata/primitives/load_store/load.tsl:39-45`, `load.tsl:59-67`, `store.tsl:56-61` | Resolve selected vector register type. | Backend id, extension, type tag, vector/register metadata. | `GenerationTypeRef(kind="vector.register")`. | Language type map. | required-later | Defer until vector register type rendering is selected. | Typed metadata fixtures; missing language-map diagnostics. |
| `value<generation>(vector::length)` | `tsldata/primitives/load_store/load.tsl:41-43`, `tsldata/primitives/bitwise/shifts.tsl:50-53`, `shifts.tsl:218-221`; exact M70 array-initialization request in `tsldata/primitives/load_store/array.tsl:105` | Resolve lane count or explicit runtime/scalable vector-length policy for selected contexts. | Extension, type tag, lane metadata, and for M70 the typed M67/M69 array-initialization request context. | Narrow typed vector-length result such as `ExactArrayInitializationVectorLengthResolutionIr`; broad vector/query consumers may later use `GenerationValue` or a typed policy value. | Explicit typed metadata supplied before lowering evaluation. | M70 accepted for exact array-initialization request; broad vector/loop use remains required-later. | M70 resolves only the exact M67 array-initialization vector-length request. Broad loop/vector metadata resolution remains deferred. | M70 direct and pipeline tests with explicit metadata, missing/duplicate/unsupported runtime/scalable diagnostics, determinism, raw-helper rejection, no host CPU/catalog/`tsldata` reads during lowering, and no backend/rendering output. Broad loop tests remain later. |
| `value<generation>(vector::alignment)` | Exact M71 array-initialization request in `tsldata/primitives/load_store/array.tsl:105`; broader aligned load/store evidence in `tsldata/primitives/load_store/load.tsl:55-70`, `store.tsl:54-64`, and `store.tsl:75-85` | Supply alignment value or explicit unsupported policy for selected contexts. | Extension, type tag, alignment metadata, and for M71 the typed M67/M70 array-initialization request context. | Narrow typed vector-alignment result such as `ExactArrayInitializationVectorAlignmentResolutionIr`; broad vector/query consumers may later use `GenerationValue` or a typed policy value. | Explicit typed metadata supplied before lowering evaluation. | M71 accepted for exact array-initialization request; broad aligned load/store use remains required-later. | M71 resolves only the exact M67 array-initialization vector-alignment request. Broad aligned-branch, `assume_aligned`, and vector/register metadata semantics remain deferred. | M71 direct and pipeline tests with explicit metadata, missing/duplicate/conflicting/unsupported diagnostics, determinism, raw-helper rejection, no host CPU/catalog/`tsldata` reads during lowering, backend uninit still unresolved, and no backend/rendering output. Broad aligned branch tests remain later. |
| `value<backend>(uninit::array)` | Exact remaining M67 array-initialization request in `tsldata/primitives/load_store/array.tsl:105`; backend output-map evidence in `tsldata/detail/lang/translate_cpp.tsl` | Preserve the backend-uninit helper as typed deferred backend-value request state so the exact first-slot helper set can become one typed handoff. | Accepted M67 request record, accepted M68/M70/M71 resolution chain, candidate/slot provenance, optional typed backend context as provenance only. | Narrow typed backend-uninit boundary/policy nested in an exact helper-set completion IR. | No backend map or renderer dependency during lowering. | M72 implemented for exact helper-set completion; backend translation/rendering remains required-later. | M72 packages the exact helper set and the deferred backend-uninit boundary; it does not translate or render uninit, lower declarations, or introduce generic backend-value evaluation. | M72 direct and pipeline tests for aggregate construction, typed request identity, diagnostics, determinism, no backend map/rendering/output, and no catalog/`tsldata`/host CPU reads during lowering. |
| `value<generation>(type::size_bytes(type<generation>(base::in)))` | `tsldata/primitives/io/out.tsl:43-52`, `tsldata/primitives/bitwise/bit_counts.tsl:99`, `tsldata/primitives/load_store/array.tsl:107-109`, `tsldata/primitives/misc/conflict.tsl:79` | Resolve the selected scalar base type byte size. | Selected type tag plus explicit scalar size-byte rules for selected singleton scalar tags. | `GenerationValue[int](kind="type.size_bytes")`. | No backend data for the value itself. Later backend/rendering may consume already-lowered values only after separate slices. | implemented by M55 | M55 selects only the exact nested `base::in` query for `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, `ui64`, `f32`, and `f64`. | Byte-value tests, float scope tests, unsupported group/wildcard diagnostics, missing context/rule diagnostics, determinism, raw-helper rejection, and no surrounding body lowering. |
| `value<generation>(type::size_bytes(type<generation>(base::in))) * 8` | `tsldata/primitives/io/out.tsl:43`, `:46`, `:48`, `:50`, `:52`, `:70`, `:73`, `:75`, `:77`, `:79`; `tsldata/primitives/misc/conflict.tsl:79` | Resolve selected scalar base type bit width from the accepted typed size-byte value. | Selected type tag plus explicit scalar size-byte rules for selected singleton scalar tags. | `GenerationValue[int](kind="type.size_bits")`. | No backend data for the value itself. | implemented by M56 | M56 selects only this exact left-associated `size_bytes * 8` expression and does not add general arithmetic or branch pruning. | Bit-width tests, unsupported operator/literal/operand diagnostics, context precedence, determinism, raw-helper rejection, and no surrounding body lowering. |
| `value<generation>(type::size_bytes(type<generation>(base::in))) == 2`, `== 4`, and `== 8` | `tsldata/primitives/load_store/array.tsl:107-109` | Resolve exact scalar size-byte equality predicates before any branch-chain policy. | Selected type tag plus explicit scalar size-byte rules for selected singleton scalar tags. | Typed boolean predicate value, for example `GenerationPredicate(kind="type.size_bytes.equals")`. | No backend data for the predicate itself. | implemented by M57 | M57 selects only these exact predicates. Branch-chain pruning and `else if<generation>` remain deferred. | Predicate truth-table tests for 2/4/8, unsupported operator/literal/operand diagnostics, determinism, raw-helper rejection, and no branch-chain/body lowering. |
| `type<generation>(base::in)` | `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:150`, `tsldata/primitives/conversion/repr_change.tsl:1210-1225`, `tsldata/primitives/load_store/array.tsl:105` | Resolve selected primitive base type. | Type tag and active vector type. | `GenerationTypeRef(kind="base.in")`. | No backend data to resolve the semantic type; later backend spelling uses language maps. | implemented M43; M68 resolves the exact M67 array-initialization base-type request | Selected by Milestone 43 as part of the base type query family. M68 reuses the accepted typed semantics for the exact M67 request record without reparsing leaf text. | Type-query diagnostics for missing type tag; M68 request-resolution diagnostics for malformed M67 request/provenance state. |
| `type<generation>(base::signed_of(type<generation>(base::in)))` and `type<generation>(base::unsigned_of(type<generation>(base::in)))` | `tsldata/primitives/arithmetic/fundamental.tsl:47-90`, `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:63-82` | Convert selected base type to signed/unsigned companion. | Type tag and integer signedness rules. | `GenerationTypeRef(kind="base.signed_of")` or `base.unsigned_of`. | No backend data to resolve the semantic type; later suffix translation uses translation maps. | implemented M43 | Milestone 43 accepts only these exact nested forms. Prose shorthand such as `base::signed_of(base::in)` is not accepted TSIL syntax. | Query tests for selected integer tags; unsupported float/pointer/generic conversion diagnostics. |
| `type<generation>(vector::transform_extension(...))` and `vector::as_extension(...)` | `tsldata/primitives/conversion/repr_change.tsl:121-128`, `tsldata/primitives/bitwise/shifts.tsl:875-880`, `shifts.tsl:1222-1240` | Build related vector types for conversion or reinterpret paths. | Current extension, target extension, type tag, vector family/width. | `GenerationTypeRef(kind="vector.transform_extension")`. | Extension metadata and language type map. | required-later | Defer until conversion parity slice. | Fixture-driven type transformation tests. |
| `type<generation>(vector::mask_underlying_t)` | `tsldata/primitives/load_store/store.tsl:177-188`, `store.tsl:196-210` | Resolve mask storage word type. | Mask parameter role, vector mask metadata. | `GenerationTypeRef(kind="vector.mask_underlying_t")`. | Language type map and vector mask metadata. | required-later | Defer until mask store parity. | Mask metadata tests. |
| `value<generation>(mask::lane::all_true)` | `tsldata/primitives/bitwise/bit_ops.tsl` search result for `mask::lane::all_true` | Supply all-true mask lane literal. | Mask lane count and representation. | `GenerationValue[int|string](kind="mask.lane.all_true")`. | Mask metadata. | explicitly-deferred | Defer until mask helper parity. | Mask fixture and metadata diagnostics. |
| `type<backend>(vector::as_extension(...))` | `tsldata/primitives/arithmetic/fundamental.tsl:38-45`, `tsldata/primitives/bitwise/shifts.tsl:50-53`, `shifts.tsl:68-76` | Request backend spelling for a semantically selected vector type. | Resolved generation type value and backend id. | Backend translation request over `GenerationTypeRef`. | Language type map. | required-later | Defer until generation type values exist. | Backend translation tests must reject raw nested generation text. |
| `type<backend>(scalar::ui64)` and scalar backend casts | `tsldata/primitives/load_store/store.tsl:181-188`, `store.tsl:196-210`, `tsldata/primitives/conversion/repr_change.tsl:121-128` | Request backend scalar type spelling. | Resolved scalar type and backend id. | Backend type translation request. | Language type map. | required-later | Defer until scalar backend type request slice. | Missing type-map and unsupported backend diagnostics. |
| `value<backend>(intrin::suffix(...))` | `tsldata/primitives/arithmetic/fundamental.tsl:47-80`, `tsldata/primitives/bitwise/shifts.tsl:63-82`, `shifts.tsl:672-683` | Compute backend intrinsic suffix from selected type. | Resolved generation type, extension, backend id. | Backend translation value request. | Translation map and extension metadata. | implemented M45 for selected suffix | M45 implements only `suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))` over typed M43 `base.signed_of` inputs for selected C++ AVX2 `si32`/`ui32` integer add. | Tests prove generation type resolves before suffix translation. |
| `value<backend>(intrin::prefix)` and stream suffix | `tsldata/primitives/load_store/load.tsl:55-70`, `store.tsl:54-64` | Compute backend intrinsic prefix and stream-load/store suffix. | Backend id and extension. | Backend translation value request. | Translation map and extension metadata. | required-later | Defer until load/store native modifier slice. | Missing translation-map and unsupported extension diagnostics. |
| `post=...`, `infix=...`, `prefix=...`, `suffix=...`, `immediate(n)=...` modifiers | `frozen/tsl-gen/tsl_gen/tsil.lark:75-78`, `frozen/tsl-gen/tsl_gen/resolver/render_support.py:565-699`, `tsldata/primitives/bitwise/shifts.tsl:150`, `shifts.tsl:1511-1517` | Modify composed intrinsic names or direct intrinsic calls. | Resolved type/value modifiers and ordered intrinsic arguments. | Intrinsic modifier IR fields. | Translation map and backend-specific intrinsic metadata. | required-later | Defer broad modifier evaluation; keep only M40 selected default composition active. | Modifier-specific parser and translation diagnostics. |
| Direct `intrin<...>` calls with template placeholders | `tsldata/primitives/bitwise/shifts.tsl:120-128`, `shifts.tsl:150`, `tsldata/primitives/conversion/repr_change.tsl:25-43` | Emit an already named intrinsic or placeholder-bearing intrinsic call. | Backend id, type tag, extension, placeholder rules. | Direct backend intrinsic call IR or explicit unsupported node. | Translation metadata and language-specific rules. | explicitly-deferred | Defer until a direct-intrinsic parity target is selected. | Unsupported diagnostics until selected. |
| Primitive calls and generic loops | `tsldata/primitives/arithmetic/fundamental.tsl:38-45`, `tsldata/primitives/load_store/load.tsl:39-45`, `tsldata/primitives/conversion/repr_change.tsl:121-128` | Compose helper primitives, arrays, and loop bodies. | Primitive dependency graph, variable scope, vector length. | Call, loop, variable, and assignment IR. | Selection, dependency, and lowering metadata. | explicitly-deferred | Defer beyond the first generation helper slice. | Separate primitive-call and loop lowering tests. |

## Implemented Helper Slice

Milestone 42 implements exactly the boolean primitive-attribute generation
condition:

```text
if<generation>(value<generation>(primitive::attribute(aligned))) {
  ...
} else<generation> {
  ...
}
```

The active evidence is `tsldata/primitives/load_store/load.tsl:55-70`,
`load.tsl:79-91`, and `tsldata/primitives/load_store/store.tsl:54-64`.
`store.tsl:75-85` supplies the same shape for floating store. These forms are
small enough because the condition depends only on primitive attributes.

Milestone 42 records the selected branch as typed provenance and then lowers
the pruned branch through the existing mini TSIL forms. The selected branch may
lower to direct parameter-add return or `intrin_compose<add>` return. The
unselected branch is discarded before nested helper diagnostics run.

The selected branch bodies in corpus evidence may still contain deferred helper
forms such as
`type<generation>(vector::register)`, `value<generation>(vector::alignment)`,
and `value<backend>(intrin::prefix)`. Those remain unsupported unless a future
slice selects them.

Required context fields for the selected slice:

- selected primitive name
- emitted primitive name
- selected candidate id
- normalized signature
- parameter list
- primitive attributes
- implementation source location

Implemented lowered behavior:

- Recognizes the selected `if<generation>` condition shape.
- Resolves `value<generation>(primitive::attribute(aligned))` to a typed boolean
  generation value.
- Keeps only the selected branch as the semantic-lowering output, with
  deterministic provenance.
- Diagnoses unknown attributes, non-boolean attribute values, malformed branch
  syntax, unsupported condition expressions, and missing generation context.
- Diagnoses unresolved nested generation-time helpers only when they appear in
  the selected branch.
- Does not diagnose unresolved helpers in the unselected branch.
- Continues to prevent unresolved generation-time helpers from reaching backend
  translation.

Milestone 42 diagnostics:

- `TSL-LOWER-GEN-IF-MALFORMED`
- `TSL-LOWER-GEN-IF-UNSUPPORTED`
- `TSL-LOWER-GEN-ATTRIBUTE-UNKNOWN`
- `TSL-LOWER-GEN-ATTRIBUTE-MISSING`
- `TSL-LOWER-GEN-ATTRIBUTE-TYPE`
- `TSL-LOWER-GEN-CONTEXT-MISSING`
- `TSL-LOWER-GEN-UNRESOLVED-SELECTED-BRANCH`

## Post-M42 Candidate Decision Table

Selection method:

- Inspect the accepted M40/M42 code paths listed in the planning request.
- Inspect source corpus evidence with
  `rg -n "type<generation>|value<generation>|if<generation>|type<backend>|value<backend>|suffix=|prefix=|post=|infix=|immediate\\(" ...`.
- Inspect legacy behavior evidence only by line-number reading, not by import
  or execution.

| Candidate | Evidence path and extraction | Helper form | Required `GenerationContext` fields | Expected typed semantic result | Current lowering dependency | Backend metadata/language-map dependency | Needed for C++ `binary/add` parity path | Needed for next likely path after `binary/add` | Implementation risk | Test strategy | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Base scalar type query family | `tsldata/primitives/arithmetic/fundamental.tsl:47-90`; `tsldata/primitives/bitwise/shifts.tsl:38-40`, `63-82`, `625-648`; `tsldata/primitives/conversion/repr_change.tsl:1210-1225`; legacy canonicalization in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:319-354` and signedness classification in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:4578-4596`. | `type<generation>(base::in)`, `type<generation>(base::signed_of(type<generation>(base::in)))`, `type<generation>(base::unsigned_of(type<generation>(base::in)))`. | Selected primitive, emitted primitive, candidate id, normalized signature, parameters, selected type tag, implementation source location. | `GenerationTypeRef` for `base.in`, `base.signed_of`, or `base.unsigned_of` with selected/source type tags. | Can be recognized as exact helper forms in the existing mini lowering boundary; does not require branch, loop, or call lowering. | None to resolve the semantic type; later backend suffix/type spelling uses language and translation maps. | Not needed for the already-accepted `avx2/f32` add slice, but required for native integer `binary/add` suffix parity. | Yes. Integer native add, shifts, and conversions all need base type references before backend suffix or signedness predicates can be evaluated. | Low to medium: nested exact-form parsing and integer companion policy only. | Unit tests for `si32`/`ui32`, explicit context override, missing/unknown type diagnostics, unsupported float/pointer/generic companion diagnostics, determinism, and translation-boundary rejection of raw generation text. | Select as Milestone 43. |
| Backend modifier value family | `tsldata/primitives/arithmetic/fundamental.tsl:57`, `:73`, `:89`; `tsldata/primitives/load_store/load.tsl:57`, `:66`; `tsldata/primitives/conversion/repr_change.tsl:364-370`, `:912-918`; grammar evidence in `frozen/tsl-gen/tsl_gen/tsil.lark:75-78`; modifier behavior evidence in `frozen/tsl-gen/tsl_gen/resolver/render_support.py:565-699`. | `value<backend>(intrin::suffix(...))`, `value<backend>(intrin::prefix)`, literal `post=...`, `infix=...`, and `immediate(n)=...` modifier fields, often fed by generation type queries. | Backend id, extension, source extension, resolved generation type values, intrinsic base name, ordered arguments, implementation source location. | Backend modifier values or an intrinsic-compose modifier IR record. | Requires parsing intrinsic modifier metadata beyond the current bare `intrin_compose<add>` form. | Requires translation map and extension metadata; suffix translation also needs language/type metadata. | Required for native integer `binary/add`; not needed for accepted f32 default suffix case. | Yes, especially integer add and load/store native paths. | Medium to high: crosses into backend translation and modifier parsing. | Defer tests until base generation type refs exist; then test suffix/prefix/immediate parsing, missing maps, unsupported extension/type, and renderer non-evaluation. | M44 selects the family boundary; M45 implements suffix only. |
| Signedness/type predicate branch | Exact `else<generation>` forms in `tsldata/primitives/bitwise/shifts.tsl:535-547`, `:625-635`, `:842-887`, `:933-943`, `:1222-1244`, `:1268-1280`, `:1465-1481`, and `:1507-1518`; predicate-only evidence with plain `else` in `tsldata/primitives/conversion/repr_change.tsl:1210-1217`; canonical predicate evidence in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:403-404`, `:4586-4596`, and `:5011-5097`. | `if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }`. | Selected type tag plus the M42 branch-pruning provenance fields. | Boolean generation value derived from a typed M43 `GenerationTypeRef(kind="base.in")`. | Builds on M42 branch pruning and consumes the M43 base type query model instead of parsing type text separately. | None for the predicate itself; selected branch bodies may contain backend requests. | Not needed for accepted `binary/add`; M47 is accepted without this branch form. | Yes for shift-right and conversion parity after the type query model exists. | Low to medium after M43. | Branch true/false tests for signed and unsigned integer candidates, selected-branch-only diagnostics, unsupported predicate/type diagnostics, missing type context, and unresolved selected-branch helper tests. | Implemented as Milestone 48 after the accepted M44-M47 native integer add phase. |
| Vector/register metadata query family | `tsldata/primitives/load_store/load.tsl:39-42`, `:55-70`; `tsldata/primitives/load_store/store.tsl:54-64`, `:177-205`; `tsldata/primitives/conversion/repr_change.tsl:1512-1529`; C++ metadata keys in `tsldata/detail/lang/translate_cpp.tsl:16-23` and `:63-65`; legacy vector refs in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:3877-3892`. | `type<generation>(vector::register)`, `type<generation>(vector::as_extension(...))`, `type<generation>(vector::transform_extension(...))`, `value<generation>(vector::length)`, `value<generation>(vector::alignment)`. | Backend id only after translation, selected extension/source extension, type tag, vector width/lane/alignment metadata, implementation source location. | `GenerationTypeRef` for vector/register concepts or `GenerationValue` with integer or symbolic payload for vector length/alignment. | Selected forms appear inside loops, casts, calls, and aligned branch bodies, so a standalone query would not make those bodies lowerable yet. | Extension metadata and later language/translation maps. | Not needed for current `binary/add`. | Likely for load/store after add, but it needs several companion constructs. | Medium to high. | Metadata fixtures for fixed-width vectors, missing metadata diagnostics, deterministic value tests, and no host-CPU dependency. | Defer; revisit when load/store parity is selected. |
| Immediate and generic-parameter value family | `tsldata/primitives/conversion/repr_change.tsl:1-10` for `sImm_type`; `tsldata/primitives/conversion/repr_change.tsl:121-128` and `:1188-1225` for `generic::length(OutVec)`; `tsldata/primitives/conversion/repr_change.tsl:352-370` and `:908-918` for `immediate(n)=...`; `tsldata/primitives/bitwise/shifts.tsl:1-10` for shift immediates. | `value<generation>(generic::length(OutVec))`, immediate modifier values such as `index` or a literal, selected generic parameters such as `ToBase`, `ToExtension`, and `index`. | Generic parameter bindings, immediate parameter roles, type aliases, selected extension/type context, parameter list, implementation source location. | `GenerationValue[int]`, `GenerationValue[GenericParamRef]`, or typed immediate-modifier value. | Requires compile switches, generic parameter scope, aliases, calls, and modifier parsing that are outside M42. | Some forms later require backend translation maps for modifier emission. | Not needed for current `binary/add`. | Important for conversion/extract/insert, but not the next smallest parity slice. | High. | Scope tests for generic bindings, immediate position validation, missing parameter diagnostics, and deterministic generic length once alias/type scope exists. | Defer. |
| Second primitive-attribute branch | `store.tsl:177-188` and `196-213`; M42 already implements the aligned attribute shape. | `if<generation>(value<generation>(primitive::attribute(packed))) { ... } else<generation> { ... }`. | Primitive attributes, selected candidate id, implementation source location; useful mask-store lowering also needs mask roles and vector metadata. | Boolean primitive-attribute generation value plus pruned branch provenance. | Small code change if generalized from `aligned`, but selected branch bodies still contain unsupported masks, vector types, loops, and backend scalar casts. | None for the condition; branch bodies later need backend/type metadata. | Not needed. | Only useful when mask store parity is selected. | Low implementation risk, low parity value now. | Reuse M42 branch tests for `packed`, plus mask-store selected-branch diagnostics when mask parity exists. | Defer. |

## Milestone 43 Selected Helper Slice

Milestone 43 implements the base scalar type query family:

```text
type<generation>(base::in)
type<generation>(base::signed_of(type<generation>(base::in)))
type<generation>(base::unsigned_of(type<generation>(base::in)))
```

This is the narrowest evidence-backed slice that advances functional parity
without broad TSIL semantics. It is useful for native integer `binary/add`
suffix translation and for later shift/conversion predicates, yet it does not
require backend rendering, modifier evaluation, vector metadata, loops, or
primitive-call lowering.

M43 typed semantic result:

- `GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`
- `GenerationTypeRef(kind="base.signed_of", type_tag=<signed companion>,
  source_type_tag=<selected type tag>)`
- `GenerationTypeRef(kind="base.unsigned_of", type_tag=<unsigned companion>,
  source_type_tag=<selected type tag>)`

M43 context additions:

- `GenerationContext.type_tag_override`, an explicit request-local override
  used by tests and diagnostics. It wins over `selected_type_tag` and over the
  selected candidate type tag.
- `GenerationContext.selected_type_tag`, used when supplied by a caller.
- selected candidate type tag defaulting, used when neither override nor
  context-selected type tag is supplied and candidate defaulting is enabled.
- the existing M42 diagnostic/provenance fields: selected primitive name,
  emitted primitive name, selected candidate id, normalized signature,
  parameter list, and implementation source location.

If a generation type query is evaluated without `type_tag_override`, without
`selected_type_tag`, and without an available selected candidate type tag,
lowering emits `TSL-LOWER-GEN-TYPE-CONTEXT-MISSING`. The override is part of
the immutable request-local `GenerationContext`; it is not global state.

M43 introduced this behavior for `si32` and `ui32`. M52 extends the same exact
typed query forms to the selected concrete integer family:

| Selected tag | `base::in` | signed companion | unsigned companion |
| --- | --- | --- | --- |
| `si8` | `si8` | `si8` | `ui8` |
| `ui8` | `ui8` | `si8` | `ui8` |
| `si16` | `si16` | `si16` | `ui16` |
| `ui16` | `ui16` | `si16` | `ui16` |
| `si32` | `si32` | `si32` | `ui32` |
| `ui32` | `ui32` | `si32` | `ui32` |
| `si64` | `si64` | `si64` | `ui64` |
| `ui64` | `ui64` | `si64` | `ui64` |

The exact accepted companion query forms are:

```text
type<generation>(base::signed_of(type<generation>(base::in)))
type<generation>(base::unsigned_of(type<generation>(base::in)))
```

Shorthand forms such as `type<generation>(base::signed_of(base::in))` and
`type<generation>(base::unsigned_of(base::in))` are diagnostics, not aliases.

M43 diagnostics:

- `TSL-LOWER-GEN-TYPE-MALFORMED`
- `TSL-LOWER-GEN-TYPE-UNSUPPORTED`
- `TSL-LOWER-GEN-TYPE-NESTED-UNSUPPORTED`
- `TSL-LOWER-GEN-TYPE-CONTEXT-MISSING`
- `TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED`
- `TSL-LOWER-GEN-TYPE-TAG-UNKNOWN`
- `TSL-LOWER-GEN-TYPE-NON-INTEGER`

Backend translation still rejects raw unresolved generation-time helper text.
If lowering already produced a `GenerationTypeRef`, M45 now translates only the
selected intrinsic suffix request over typed M43 inputs:
`GenerationTypeRef(kind="base.signed_of", type_tag="si32",
source_type_tag="si32")` and
`GenerationTypeRef(kind="base.signed_of", type_tag="si32",
source_type_tag="ui32")`. That slice produces a typed backend modifier value
equivalent to `BackendIntrinsicModifier(kind="suffix", backend_id="cpp",
extension="avx2", intrinsic="add", value="epi32",
source_type_tag="si32", source_ref_kind="base.signed_of")`. Raw
`type<generation>(...)` text remains rejected by backend translation. M46 now
translates selected C++ scalar type spelling requests over typed M43
`GenerationTypeRef` values for `base.in`, `base.signed_of`, and
`base.unsigned_of`, producing typed backend type-spelling values equivalent to
`BackendTypeSpelling(backend_id="cpp", type_tag="si32",
spelling="int32_t")` and `BackendTypeSpelling(backend_id="cpp",
type_tag="ui32", spelling="uint32_t")`. M47 now renders only the selected C++
native integer `binary/add` `avx2` `si32`/`ui32` output after consuming those
M45/M46 values as explicit renderer inputs. Prefix, infix, post, immediate, and
broad translation-map or language-map evaluation remain deferred. Renderers
remain non-evaluating text emitters and must not parse raw generation-time
helper text.

## Post-M43 Through Selected Post-M55 Direction

The accepted post-M43 phase is numbered in the roadmap:

- Milestone 44 selects the backend modifier value family boundary and chooses
  intrinsic suffix as the first implementation target. The selected M45 input
  is `suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))`, where the
  type ref is already the M43 result for
  `type<generation>(base::signed_of(type<generation>(base::in)))`.
- Milestone 45 translates only the selected suffix request
  `suffix=value<backend>(intrin::suffix(<GenerationTypeRef>))` over typed M43
  inputs. For selected `si32` and `ui32` native integer add candidates, M43
  produces `GenerationTypeRef(kind="base.signed_of", type_tag="si32",
  source_type_tag=<selected tag>)`, and M45 returns typed backend modifier
  value `BackendIntrinsicModifier(kind="suffix", backend_id="cpp",
  extension="avx2", intrinsic="add", value="epi32",
  source_type_tag="si32", source_ref_kind="base.signed_of")`.
- Milestone 46 translates selected C++ scalar type spelling requests over typed
  M43 `GenerationTypeRef` inputs for `base.in`, `base.signed_of`, and
  `base.unsigned_of`, using the C++ language map to produce `int32_t` for
  `si32` and `uint32_t` for `ui32`.
- Milestone 47 renders selected native integer C++ `binary/add` output only
  after the suffix and type-spelling translation outputs are explicit renderer
  inputs; the implemented fixture is
  `tslgen/tests/fixtures/golden/parity/cpp/add_native_avx2_i32_u32_excerpt.hpp`.
- Milestone 48 implements the selected post-M47 generation-time semantic
  lowering slice. It evaluates only
  `value<generation>(type::is_signed(type<generation>(base::in)))` over typed
  M43 `GenerationTypeRef(kind="base.in")` values, prunes exact
  `if<generation> ... else<generation>` branches with M42-style provenance,
  and does not add backend translation or rendering behavior.
- Milestone 49 is accepted as the generated C++ test-source parity slice.
  It consumes typed `TestSourcePlan` values plus an explicit typed C++ type
  spelling value and must not add generation-time lowering, backend
  translation, generated C++ implementation rendering, or compiler execution.
- Milestone 50 is the selected post-M49 reporting adapter slice. It consumes
  accepted typed coverage/report DTOs and must not add generation-time lowering,
  backend translation, renderer semantic inference, CLI/writer behavior, or
  compiler execution.
- Milestone 51 is accepted as the exact generation-time semantic lowering slice
  for the M48 signedness predicate branch form with plain
  `else`, over typed M43 `GenerationTypeRef(kind="base.in")` values. It must
  not add conversion body lowering, backend translation, rendering, generated
  output, or broad TSIL parsing.
- Milestone 52 extends only the accepted M43, M48, and M51 generation-time
  type/signedness semantics from the selected
  `si32`/`ui32` pair to the concrete integer tag family
  `si8`, `ui8`, `si16`, `ui16`, `si32`, `ui32`, `si64`, and `ui64`. It remains
  typed lowering only and must not add backend suffix/type-spelling expansion,
  generated output, branch-body semantics, vector/register metadata, or broad
  TSIL parsing.
- Milestone 53 is accepted. It moves ownership of those accepted concrete
  integer generation rules from a lowering-private table to a typed
  domain/catalog rule source, preserving M52 behavior exactly and keeping broad
  type semantics from raw tag spelling or wildcard/group selectors
  unsupported.
- Milestone 54 wires the M53 rule source through the normal catalog/lowering
  input path. A focused lowering request adapter builds catalog-derived
  `ConcreteIntegerGenerationRuleSet` values from typed `Catalog.type_groups`
  before evaluation and passes them through `GenerationContext`; malformed or
  incomplete explicit catalog data reports rule-source diagnostics instead of
  falling back to synthetic defaults.
- Milestone 55 introduces the exact scalar
  `value<generation>(type::size_bytes(type<generation>(base::in)))` query as a
  typed generation integer value for explicit selected scalar tags. It does not
  broaden standalone `base.in` or signed/unsigned companion behavior to floats
  and does not lower the surrounding bodies where the helper appears.
- Milestone 56 introduces only the exact
  `value<generation>(type::size_bytes(type<generation>(base::in))) * 8`
  arithmetic expression as a typed generation integer value for selected scalar
  bit widths. It reuses the M55 typed value and scalar size-byte rules, and
  does not add comparisons, branch pruning, `else if<generation>`, body
  lowering, backend translation, or rendering.
- Milestone 57 introduces only exact size-byte
  equality predicates over
  `value<generation>(type::size_bytes(type<generation>(base::in))) == 2`,
  `== 4`, and `== 8`. It reuses the M55 typed value and scalar size-byte
  rules, and produces typed boolean predicate results. Branch-chain pruning,
  `else if<generation>`, and direct-intrinsic/body lowering remain deferred.

M55 typed semantic result:

- `GenerationValue(kind="type.size_bytes", value=<bytes>, type_tag=<selected tag>)`

M56 typed semantic result:

- `GenerationValue(kind="type.size_bits", value=<bits>, type_tag=<selected tag>)`

M55 diagnostics:

- `TSL-LOWER-GEN-VALUE-MALFORMED`
- `TSL-LOWER-GEN-VALUE-UNSUPPORTED`
- `TSL-LOWER-GEN-VALUE-NESTED-UNSUPPORTED`
- `TSL-LOWER-GEN-VALUE-ARITY`
- `TSL-LOWER-GEN-VALUE-CONTEXT-MISSING`
- `TSL-LOWER-GEN-VALUE-TAG-UNSUPPORTED`
- `TSL-LOWER-GEN-VALUE-TAG-UNKNOWN`
- `TSL-DOMAIN-GEN-SIZE-RULE-TAG-UNSUPPORTED`
- `TSL-DOMAIN-GEN-SIZE-RULE-TAG-UNKNOWN`
- `TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-MISSING`
- `TSL-DOMAIN-GEN-SIZE-RULE-SINGLETON-INCONSISTENT`

M56 additional diagnostics:

- `TSL-LOWER-GEN-VALUE-ARITH-MALFORMED`
- `TSL-LOWER-GEN-VALUE-ARITH-OPERATOR`
- `TSL-LOWER-GEN-VALUE-ARITH-LITERAL`
- `TSL-LOWER-GEN-VALUE-ARITH-OPERAND`

M57 additional diagnostics:

- `TSL-LOWER-GEN-PREDICATE-MALFORMED`
- `TSL-LOWER-GEN-PREDICATE-OPERATOR`
- `TSL-LOWER-GEN-PREDICATE-LITERAL`
- `TSL-LOWER-GEN-PREDICATE-OPERAND`

M57 also reuses M55 missing type context, unsupported/unknown selected tag, and
malformed scalar size-byte rule diagnostics.

This phase does not make backend translation parse raw generation-time helper
text and does not move suffix or type-spelling evaluation into renderers.

## Planned Staged Lowering Direction

Post-M56 and post-M57 planning kept size-byte equality predicate lowering
separate from branch-chain pruning. The accepted staged direction is:

1. Recognize exact selected generation helper expressions.
2. Resolve typed generation values, such as M55 `type.size_bytes` and M56
   `type.size_bits`.
3. Resolve typed generation predicates, starting with accepted M57
   `type.size_bytes == 2/4/8`.
4. Consume typed predicate results for control-flow pruning, as accepted by
   M59 for the exact size-byte branch chain.
5. Hand selected branch bodies forward as typed/provenanced lowering inputs
   before any body-specific lowering slice; M60 accepted this opaque handoff
   boundary.
6. Recognize exactly selected body forms from the M60 handoff as typed
   form-recognition records before any semantic body lowering. M61 keeps this
   recognition boundary limited to the exact selected assignment form in the
   SVE size-byte branch bodies.
7. Convert exactly selected recognized body forms into typed body-specific IR
   values only after form recognition. M62 accepts the exact M61
   assignment/direct-intrinsic form, with unresolved backend-neutral body IR
   and no SVE/backend/rendering semantics.

This staged path is a semantic contract. It does not require every step to be a
separate traversal immediately, but each milestone should expose typed outputs
that the next step can consume without reparsing raw helper text in backend
translation or renderers.

Milestone 58 makes that contract concrete for the accepted M55-M57 path by
recording deterministic generation-lowering stage outputs on lowered
implementations. The stage records expose helper/expression recognition,
accepted typed generation values, accepted typed generation predicates,
generation control-flow pruning, and selected-body lowering as typed values.
For the M57 size-byte equality predicates, the staged output carries the
underlying M55 `GenerationValue(kind="type.size_bytes")` and the resulting
`GenerationPredicate(kind="type.size_bytes.equals")`, while the legacy
`generation_values` and `generation_predicates` observable fields remain
unchanged. The M59 branch-chain pruning slice consumes the typed predicate
stage output directly instead of reparsing the raw
`value<generation>(...) == ...` helper text. M58 does not add branch-chain
pruning, new helper forms, new comparison or arithmetic semantics, selected body
handoff policy, backend translation, rendering, or generated output.

M59 consumes those typed predicate stage outputs for exactly the documented SVE
size-byte no-final-else branch chain in
`tsldata/primitives/load_store/array.tsl:107-109`. It records matching arm
provenance for byte sizes `2`, `4`, and `8`, records explicit no-match
provenance for byte size `1`, and must not introduce broad
`else if<generation>` parsing, body handoff, direct-intrinsic/SVE body
lowering, backend translation, rendering, or generated output.

M60 is accepted as the opaque selected-body handoff slice. It consumes M59's
typed branch-chain pruning result and produces a distinct typed handoff value
for the selected branch body text and provenance, or an explicit
no-selected-body/no-match result for byte size `1`. M60 does not parse or
lower direct `intrin<...>` / SVE statements, assignments, arrays, calls,
casts, loops, vector metadata, backend values, renderer output, generated
artifacts, CLI/reporting/writer behavior, Rust, compiler execution, broad
TSIL, or runtime `frozen/` evidence.

Milestone 61 is selected-body assignment-form recognition. It consumes only
typed M60 handoff values and recognizes exactly the selected single-statement
forms
`pg = intrin<svptrue_b16>();`, `pg = intrin<svptrue_b32>();`, and
`pg = intrin<svptrue_b64>();` from
`tsldata/primitives/load_store/array.tsl:107-109`. M61 preserves the
assignment target, opaque RHS/direct-intrinsic token text, original body text,
and provenance as typed form metadata through a distinct
`selected_body_form_recognition` stage. It must not lower assignment semantics,
validate direct intrinsics, infer SVE predicate meaning, map selected size-byte
literals to intrinsic token text, inspect unselected branch bodies, feed backend
translation or rendering, add generated output, or parse broad TSIL body
syntax.

Milestone 62 is the first body-specific lowering IR slice. It consumes only M61
typed `selected_body_form_recognition` outputs and converts the exact selected
assignment/direct-intrinsic form into unresolved, backend-neutral typed
selected-body IR through the distinct `selected_body_ir_lowering` stage. The
selected IR preserves the M61 assignment target, direct-intrinsic token text,
explicit empty argument list, original RHS/body text, selected type/literal,
and provenance. The no-selected-body M61 result becomes an explicit no-body-IR
result for byte-size `1` cases. M62 does not derive semantics by rereading
preserved body text, validate intrinsic names, infer `type.size_bytes` to
`svptrue_b*` mappings, prove SVE predicate meaning for `pg`, create backend
translation requests, feed renderers, or emit generated output.

Milestone 63 is accepted as the next lowering boundary. It consumes only M62
`selected_body_ir_lowering` outputs and wraps the selected-body IR or no-body
IR result in a backend-neutral selected-body envelope with a deterministic
typed statement sequence. For M63, the selected sequence is exact and
singleton: it contains only the existing M62
`SelectedAssignmentDirectIntrinsicBodyIr`; byte-size `1` cases produce an
explicit no-body envelope. M63 treats the SVE-looking array body in
`tsldata/primitives/load_store/array.tsl:105-111` as evidence for a needed
whole-body boundary, not as architecture. It must not parse surrounding
statements, lower direct-intrinsic semantics, infer SVE predicate meaning,
map byte sizes to intrinsic tokens, add vector length/alignment semantics,
feed backend translation or rendering, or emit generated output.

Milestone 64 is accepted as the structural lowering boundary. It consumes
accepted typed M63 `selected_body_envelope_lowering` outputs and assembles the
exact ordered array-body shape evidenced by
`tsldata/primitives/load_store/array.tsl:105-111` into a deterministic typed
slot envelope. The M64 envelope has opaque pre-branch and post-branch slots
plus one selected-body slot referencing the M63 selected/no-body envelope.
Slot labels are structural/provenance labels only. M64 does not lower or
validate declarations, arrays, `svbool_t`, `pg`, direct intrinsics, `svst1`,
stores, `tmp.data()`, `emit_return`, vector length/alignment, backend uninit
values, backend translation, rendering, generated output, or broad TSIL body
syntax.

Milestone 65 is accepted as the pipeline-integration boundary. It wires the
accepted M64 exact array-body envelope into the normal staged lowering
pipeline by consuming typed/provenanced `ExactArrayBodyEnvelopeSkeleton` input
plus accepted M63 selected/no-body envelopes, producing
`LoweredImplementation.array_body_envelopes`, and appending the
`array_body_envelope_slot_assembly` stage. M65 does not produce skeletons from
raw body text, parse broad TSIL, lower slot semantics, infer SVE/direct
intrinsic meanings, evaluate vector length/alignment or backend uninit values,
feed backend translation or rendering, or emit generated output.

Milestone 66 implements the exact array-initialization slot form-IR boundary.
It consumes accepted M65 `ExactArrayBodyEnvelopeIr` values and refines only the
`opaque_pre_branch_array_initialization` slot at ordinal `0` for the exact
`tsldata/primitives/load_store/array.tsl:105` form into typed form IR. M66
records unresolved typed/provenance leaves for `type<generation>(base::in)`,
`value<generation>(vector::length)`,
`value<generation>(vector::alignment)`, and
`value<backend>(uninit::array)`, but does not evaluate those helpers. M66 does
not lower generic declarations, arrays, variables, store/return slots,
SVE/direct intrinsics, backend translation, rendering, generated output, or
broad TSIL body syntax.

Milestone 67 is accepted as the exact array-initialization helper request IR
slice. It consumes accepted M66 `ExactArrayInitializationSlotFormIr` values,
the `array_initialization_slot_form_lowering` stage, or a typed
`LoweredImplementation` carrying exactly one accepted M66 form as a
container/source, and classifies exactly the four M66 unresolved helper leaves
into deterministic typed deferred helper-request records. M67 preserves leaf
kind, source text, source locations, candidate/type/envelope provenance, slot
ordinal, branch-chain identity, and variable token `tmp`, but it does not
evaluate, resolve, translate, normalize, or render any helper.

Milestone 68 is accepted as the exact array-initialization base-type helper
request resolution slice. It consumes accepted M67
`ExactArrayInitializationHelperRequestIr` values, the
`array_initialization_helper_request_lowering` stage, or a typed
`LoweredImplementation` carrying exactly one accepted M67 helper-request IR as
a container/source. M68 resolves only the M67 request record for
`type<generation>(base::in)` into a typed result equivalent to
`GenerationTypeRef(kind="base.in", type_tag=<selected type tag>)`, preserving
M67 request provenance and leaving the vector length, vector alignment, and
backend uninit requests unresolved. M68 must consume typed M67 request fields,
not reparse `leaf_source_text`, `original_slot_text`, raw TSIL, raw TSL, or
helper strings, and it must not call raw query-string helper evaluators on M67
leaf text.

Milestone 69 is accepted as a behavior-preserving exact array-initialization
stage pipeline extraction slice. It extracts the accepted M64-M68
array-initialization stage assembly tail from `_lower_input` into a private
typed helper/result while preserving the same lowered outputs, stage names/
order, diagnostics, source locations, deterministic behavior, and unresolved
vector/backend requests. M69 does not add helper semantics, parse raw helper
text, resolve vector length/alignment or backend uninit requests, or create
backend translation/rendering/output behavior.

Milestone 70 is accepted as exact array-initialization vector-length request
resolution. It resolves only the accepted M67 request for
`value<generation>(vector::length)` through the M69 extracted pipeline and
explicit typed vector-length metadata supplied before lowering evaluation. M70
must not infer lane counts from SVE token text, extension names, `vector_bits`,
selected type tags, scalar sizes, host CPU features, catalog data, `tsldata`,
backend maps, or renderer names during lowering. Runtime/scalable metadata
must remain an explicit typed policy/value or produce diagnostics; it must not
be converted into a fake fixed lane count. Vector alignment, backend uninit,
declaration/array semantics, backend translation/rendering/output behavior,
and broad vector/register metadata remain deferred after M70.

Milestone 71 is accepted as exact array-initialization vector-alignment
request resolution. It resolves only the accepted M67 request for
`value<generation>(vector::alignment)` through the M69/M70 pipeline and
explicit typed vector-alignment metadata supplied before lowering evaluation.
M71 must not infer alignment from vector length, vector bits, scalar byte
size, selected type tags, SVE token text, extension names, host CPU features,
catalog data, `tsldata`, backend maps, backend vector-alignment spellings, or
renderer names during lowering. Backend uninit, declaration/array semantics,
aligned load/store semantics, `assume_aligned`, backend translation/rendering/
output behavior, and broad vector/register metadata remain deferred.

Milestone 72 implements exact array-initialization helper-set completion IR. It
consumes the accepted M71 vector-alignment resolution and packages the complete
exact first-slot helper set into one typed aggregate: M68 base type, M70 vector
length, M71 vector alignment, and the remaining M67
`value<backend>(uninit::array)` request as a typed deferred backend-value
boundary. M72 does not resolve backend uninit into backend text, backend
translation requests, renderer-ready values, generated output, or
declaration/array semantics.

Milestone 73 implements exact first-slot declaration-shell structural IR. It
consumes the M72 helper-set completion and produces typed structure for the
exact `array.tsl:105` `var<typed>(array_type<...>, tmp, ...)` shell. M73
records only the structural declaration kind, array-type shape, `tmp`
variable token, accepted M68/M70/M71 helper facts, and M72 deferred backend
uninit boundary as lowering state. Generic declarations, generic arrays,
allocation/lifetime, initializer behavior, variable scope, stores, returns,
`tmp.data()`, `emit_return`, backend uninit translation, backend translation
maps, rendering, and generated output remain deferred.

Milestone 74 implements exact array-body structural sequence and slot-role
classification. It consumes the accepted M64/M65 exact array-body envelope and
accepted M73 first-slot declaration-shell IR, then produces one typed
source-ordered sequence for the exact `array.tsl:105-111` body. Slot roles are
structural/provenance labels only, not executable statement semantics:
first-slot declaration shell, opaque predicate-init-shaped slot, selected-body
envelope slot, opaque post-branch store-call-shaped slot, and opaque
return-emission-shaped slot. M74 preserves non-first slots as opaque/unresolved
structural evidence and must not interpret `svbool_t`,
`svptrue_b8`, selected `svptrue_b*`, `svst1`, `tmp.data()`, `emit_return`,
`assume_aligned`, store/return behavior, SVE/direct-intrinsic behavior,
backend maps, rendering, generated output, or broad TSIL/body semantics.

Milestone 75 implements exact predicate path structural/request IR. It
consumes the accepted M74 exact array-body structural sequence and records the
exact predicate path across slot 1 predicate initialization, slot 2 accepted
selected/no-body predicate update evidence, and slot 3 post-branch store-call
predicate-token use. The result is typed structural/request lowering state
only: `svbool_t`, `pg`, `svptrue_b8`, selected `svptrue_b16/b32/b64`, and the
slot-3 `pg` argument remain structural tokens and unresolved direct-intrinsic/
request provenance. M75 does not interpret SVE predicate semantics,
byte-size-to-token relationships, store semantics, `svst1`, `tmp.data()`, `a`,
backend maps, rendering, generated output, variable scope, or broad body
semantics.

Milestone 76 is accepted as exact post-branch intrinsic call-site structural/
request IR. It consumes accepted M75 predicate-path state and records the exact
`array.tsl:110` call-site shape
`intrin<svst1>(pg, tmp.data(), a);` as typed lowering state. The result is
structural/provenance only: `intrin`, unresolved token `svst1`, predicate
argument token `pg`, member-access-shaped token/path `tmp.data()`, and source
operand token `a` must not become ARM/SVE intrinsic semantics, store
semantics, memory behavior, pointer semantics, variable scope, backend
translation, renderer-ready IR, or generated output. The M76 stage
follows `predicate_path_structural_request_lowering` and must use source text
only as exact shape/provenance evidence, not as raw helper dispatch.

Milestone 77 implements a behavior-preserving composable lowering
pipeline/module boundary. M77 does not add new generation-time helper
semantics. It moves exact recognizer shapes and tokens into
`tslgen.lowering._exact_shapes` and records the accepted M69-M76 exact
array-body stage tail through `tslgen.lowering._pipeline` as typed facts,
dependencies, and an empty typed backfeed-request boundary. Future backfeeds
must not be implemented as hidden recursive stage calls, broad registries, raw
helper dispatch, or central semantic `if`/`elif` chains. Exact tokens that look
extension-specific remain slice-local structural evidence until a future
milestone supplies explicit typed semantic rules.

Post-M77 planning selects Milestone 78 as behavior-preserving generation-time
lowering package decomposition. M78 must not add helper semantics. It should
move the accepted exact array-body / array-initialization lowering package
from `boundary.py` into private typed modules, preserve all accepted M57-M77
stage behavior, and prove the central facade is materially smaller. The
pre-M78 line-count baseline is 12,371 physical lines, and M78 requires at
least 1,000 net lines removed from `boundary.py` without duplicate moved code.

M78 execution keeps generation-time helper behavior unchanged. It moves exact
array-initialization helper/slot shape and request-rule values into
`tslgen.lowering._array_body_shapes`, exact package diagnostics into
`tslgen.lowering._array_body_diagnostics`, and exact predicate-init structural
tokens into `tslgen.lowering._exact_shapes`. `boundary.py` remains the facade
and now measures 11,109 physical lines. The new modules do not evaluate helper
text, query catalogs/backends, render output, or import `boundary.py`.

Post-M78 planning selects M79 as behavior-preserving exact array-body typed
model ownership extraction. M79 keeps generation-time helper behavior
unchanged: it must not evaluate helper text, add helper semantics, query
catalogs/backends, render output, or create a registry/dispatcher. Its purpose
is to move exact array-body / array-initialization model ownership behind
private typed modules, consolidate exact helper alias ownership, and tighten
targeted diagnostic typing where the same private model boundary supplies the
needed attributes. `boundary.py` remains the public facade and private modules
must not import it.

M79 execution keeps those generation-time semantics unchanged. The private
`tslgen.lowering._array_body_models` module now owns exact array-body /
array-initialization helper aliases, helper rules, typed IR/value models, and
the small protocols used by diagnostics. `_array_body_shapes.py` shares those
helper definitions, `_array_body_diagnostics.py` uses protocol-typed inputs
instead of targeted unconstrained `Any` parameters, and `boundary.py` remains
the facade at 8,915 physical lines. No helper text is evaluated and no
catalog, backend map, renderer, or generated-output path is added.

Post-M79 planning selects M80 as behavior-preserving exact array-body
validation boundary extraction. It keeps generation-time helper behavior
unchanged: validators and request-record helpers may move to a private module,
but they must continue to consume typed M57-M79 values, accepted exact helper
rules, and structural provenance only. M80 must not evaluate helper text,
query catalogs/backends, add source adapters, add return/store semantics,
render output, or create a validation registry/semantic dispatcher.

M80 execution preserves that boundary. The exact validation and request-record
helpers now live in `tslgen.lowering._array_body_validation` and consume
accepted typed models, helper rules, diagnostics, and structural provenance
without importing `boundary.py`. `boundary.py` remains the facade/coordinator
and now measures 7,208 physical lines. No generation-time helper evaluation,
raw helper dispatch, catalog/backend query, source adapter, return/store
semantic value, renderer-ready value, or output behavior was added.

M81 executes behavior-preserving generation-time lowering core ownership
extraction. Accepted generation type/value/predicate models, exact generation
helper query parsing and resolution, accepted generation branch-chain
parsing/pruning helpers, and related diagnostics now live in private typed
generation modules. It preserves the M42-M80 helper semantics and diagnostics
exactly; it does not add new helper evaluation, broad helper parsing, backend
translation, rendering, generated output, catalog/backend reads, or
extension-specific semantic shortcuts.

M82 executes behavior-preserving selected-body envelope ownership extraction.
The minimal cohesive M60-M63 selected-body model cluster now lives in
`tslgen.lowering._selected_body_models` while accepted lowering functions,
source adapters, stage construction, and public facade behavior remain stable.
It is not a new helper-evaluation slice and does not add selected-body
semantics, broad TSIL/body parsing, backend translation, rendering, generated
output, catalog/backend reads, or extension-specific semantic shortcuts.

M83 is accepted as behavior-preserving stage output-contract ownership
extraction.
The accepted `GenerationLoweringStage` stage-name/output compatibility
contract now lives in a private typed lowering module, preserving public
imports, stage names/order, output identities, keys, and invalid-stage/output
error behavior. It is a pipeline maintainability step before new semantic
stages; it does not evaluate helpers, parse broad TSIL, interpret exact
return-emission/store-call slots, add backend translation/rendering/output
behavior, or introduce a registry, dispatcher, plugin system, or
fixpoint/backfeed engine.

M84 is accepted as exact array-body pipeline and source-adapter ownership
extraction. M84 is still no-new-semantics lowering architecture work: it moved
accepted exact array-body pipeline/source-adapter and exact-array public
lowerer ownership out of `boundary.py` into private typed lowering modules
while preserving the same typed values, diagnostics, source locations, stage
snapshots, and public facade behavior. It must not evaluate new helpers,
broaden source parsing, interpret `emit_return(tmp)` or store/call semantics,
introduce raw-helper dispatch, or add backend translation/rendering/output
behavior.

Post-M84 planning selects M85 as selected-body lowering ownership extraction.
M85 is also no-new-semantics lowering architecture work: it should move the
accepted M60-M63 selected-body lowerer implementations and direct private
helpers out of `boundary.py` into a focused private typed lowering module
while preserving the same typed values, diagnostics, source locations, stage
snapshots, and public facade behavior. It must not evaluate new helpers,
broaden selected-body parsing, interpret SVE-looking direct-intrinsic tokens,
interpret `emit_return(tmp)` or store/call semantics, introduce raw-helper
dispatch, or add backend translation/rendering/output behavior.

M85 is accepted as that move in
`tslgen.lowering._selected_body_lowering`, with `boundary.py` and
`tslgen.lowering` preserving the accepted public call surface. The extraction
does not add selected-body semantics or change the accepted Stage 8 selected-
body snapshots.

M86 is accepted as candidate payload-intake and mini-TSIL leaf return lowering
extraction. It is also no-new-semantics lowering architecture work: it moved
accepted payload classification, typed-opaque unsupported-payload diagnostics,
direct parameter-add return lowering, and `intrin_compose<add>` return
lowering out of `boundary.py` while preserving the same typed mini-TSIL return
statements, diagnostics, source locations, stage snapshots, and public facade
behavior. It does not broaden TSIL parsing, interpret `emit_return(tmp)` or
return/store/call semantics, introduce raw helper dispatch, or add backend
translation/rendering/output behavior.

M87 is accepted as exact return-emission structural/request IR. The accepted
slice consumes M74 structural sequence provenance and M76 post-branch call-site
provenance, then records only the exact trailing `emit_return(tmp);` shape with
insignificant whitespace. The returned token must match the accepted
declaration-shell variable token as provenance. M87 does not repair wrong
`.tsl` bodies, broaden `emit_return(...)`, infer return operands, implement
return semantics, add renderer-ready IR, or add backend/rendering/output
behavior. Unsupported nearby forms remain diagnostics.

Post-M87 planning selects M88 as exact array-body structural package assembly.
M88 should consume accepted M64-M87 typed facts and assemble one typed,
source-ordered package for the selected `array.tsl:105-111` structural body.
This package is an aggregation/provenance-validation boundary only: it must not
reparse or repair source bodies, infer declaration/store/return/SVE/backend
semantics, query catalogs or backend maps, add renderer-ready IR, or produce
generated output. The package should give later lowering/backend-planning work
one stable typed handoff instead of requiring every future stage to understand
the separate exact array-body facts.

M61 diagnostics:

- `TSL-LOWER-SELECTED-BODY-FORM-SOURCE-UNSUPPORTED`
- `TSL-LOWER-SELECTED-BODY-FORM-EXTRA-STATEMENTS`
- `TSL-LOWER-SELECTED-BODY-FORM-MALFORMED`
- `TSL-LOWER-SELECTED-BODY-FORM-TARGET-UNSUPPORTED`
- `TSL-LOWER-SELECTED-BODY-FORM-RHS-UNSUPPORTED`

M62 diagnostics:

- `TSL-LOWER-SELECTED-BODY-IR-SOURCE-UNSUPPORTED`

M63 diagnostics:

- `TSL-LOWER-SELECTED-BODY-ENVELOPE-SOURCE-UNSUPPORTED`
- `TSL-LOWER-SELECTED-BODY-ENVELOPE-INCONSISTENT`

M64 diagnostics:

- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SOURCE-UNSUPPORTED`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SHAPE-UNSUPPORTED`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SLOT-ORDER`
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-PROVENANCE-MISMATCH`

M65 diagnostics:

- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-MISSING`: required typed skeleton
  input is absent for a candidate whose lowering contract requires M65
  envelope integration.
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-DUPLICATE`: more than one identical
  skeleton is supplied for the same candidate, selected type tag, and
  branch-chain identity.
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-CONFLICT`: more than one different
  skeleton is supplied for the same candidate, selected type tag, and
  branch-chain identity.
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-ORPHAN`: a skeleton is supplied for
  a candidate or branch path that has no accepted M63 selected/no-body
  envelope to assemble.
- `TSL-LOWER-ARRAY-BODY-ENVELOPE-SKELETON-PROVENANCE-MISMATCH`: the supplied
  skeleton and M63 envelope disagree on candidate id, selected type tag,
  branch-chain identity, or source provenance required for assembly.

M66 diagnostics:

- `TSL-LOWER-ARRAY-INIT-SLOT-SOURCE-UNSUPPORTED`: exact
  array-initialization slot form lowering was invoked with something other
  than an accepted M65 `ExactArrayBodyEnvelopeIr`, the
  `array_body_envelope_slot_assembly` stage output, or a matching lowered
  implementation envelope.
- `TSL-LOWER-ARRAY-INIT-SLOT-MISSING`: no accepted M65 array-body envelope or
  slot is available for the M66 form boundary.
- `TSL-LOWER-ARRAY-INIT-SLOT-WRONG-POSITION`: the typed slot evidence is not
  the `opaque_pre_branch_array_initialization` slot at ordinal `0`.
- `TSL-LOWER-ARRAY-INIT-SLOT-FORM-MALFORMED`: slot text selected from the M65
  envelope does not have the exact `array.tsl:105` form.
- `TSL-LOWER-ARRAY-INIT-SLOT-HELPER-UNSUPPORTED`: the slot has the surrounding
  `var<typed>(array_type<...>, tmp, ...)` shape but one of the unresolved
  helper leaves is not the exact M66 helper evidence.
- `TSL-LOWER-ARRAY-INIT-SLOT-PROVENANCE-MISMATCH`: the slot and envelope
  disagree on candidate id, selected type tag, or branch-chain identity.

M67 diagnostics:

- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-SOURCE-UNSUPPORTED`: helper-request
  lowering was invoked with something other than an accepted M66
  `ExactArrayInitializationSlotFormIr`, the
  `array_initialization_slot_form_lowering` stage output, or a typed
  `LoweredImplementation` carrying exactly one accepted M66 form; this also
  covers a `LoweredImplementation` carrying multiple M66 forms at the M67
  request boundary.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-FORM-MISSING`: a
  `LoweredImplementation` source does not carry an accepted M66
  array-initialization slot form.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISSING`: an accepted M66 form is
  missing one of the four required unresolved helper leaves.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-MISMATCH`: an M66 leaf field
  carries a different leaf kind than the exact request boundary expects.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-DUPLICATE`: the M66 form presents
  the same helper leaf kind more than once.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-LEAF-UNSUPPORTED`: an M66 helper leaf
  has source text outside the exact accepted first-slot helper evidence.
- `TSL-LOWER-ARRAY-INIT-HELPER-REQUEST-PROVENANCE-MISMATCH`: the M66 form,
  leaf, request record, or source container disagrees on candidate id,
  selected type tag, branch-chain identity, envelope identity, slot ordinal, or
  variable-token provenance required by the request boundary.

M68 diagnostics:

- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-SOURCE-UNSUPPORTED`: base-type
  request resolution was invoked with something other than an accepted M67
  `ExactArrayInitializationHelperRequestIr`, the
  `array_initialization_helper_request_lowering` stage output, or a typed
  `LoweredImplementation` carrying the accepted M67 helper-request IR.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MISSING`: a
  `LoweredImplementation` source does not carry an accepted M67 helper-request
  IR.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-IR-MULTIPLE`: a
  `LoweredImplementation` source carries more than one M67 helper-request IR
  at the M68 request-resolution boundary.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISSING`: the accepted M67 request
  IR does not contain the required base-type request record.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-DUPLICATE`: the M67 request IR
  contains more than one base-type request record.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-MISMATCH`: the selected M67
  base-type request record does not carry the expected ordinal `0`, request
  kind `generation_type`, and helper leaf kind `type_generation_base_in`.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-UNSUPPORTED`: the selected M67
  base-type request record does not preserve the exact accepted
  `type<generation>(base::in)` leaf text as provenance/invariant evidence.
- `TSL-LOWER-ARRAY-INIT-BASE-TYPE-REQUEST-PROVENANCE-MISMATCH`: the M67
  helper-request IR, source form, source request record, or resolved
  base-type result disagree on candidate id, selected type tag, branch-chain
  identity, envelope identity, slot ordinal, variable token, source location,
  or remaining unresolved request provenance.

M68 also reuses the existing generation-type diagnostics, such as
`TSL-LOWER-GEN-TYPE-TAG-UNSUPPORTED`, when the selected typed base type cannot
be resolved through the accepted concrete integer generation rule inputs.

M70 diagnostics:

- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-SOURCE-UNSUPPORTED`: vector-
  length request resolution was invoked with something other than an accepted
  M68 `ExactArrayInitializationBaseTypeResolutionIr`, the
  `array_initialization_base_type_request_resolution` stage output, or a typed
  `LoweredImplementation` carrying the accepted M68 base-type resolution.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MISSING`: a
  `LoweredImplementation` source does not carry an accepted M68 base-type
  resolution.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-IR-MULTIPLE`: a
  `LoweredImplementation` source carries more than one M68 base-type
  resolution at the M70 request-resolution boundary.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISSING`: the M68 unresolved
  request records do not contain the required vector-length request.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-DUPLICATE`: the M68 unresolved
  request records contain more than one vector-length request.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-MISMATCH`: the selected M67
  vector-length request record does not carry the expected ordinal `1`,
  request kind `generation_value`, and helper leaf kind
  `value_generation_vector_length`.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-REQUEST-UNSUPPORTED`: the selected M67
  vector-length request record does not preserve the exact accepted
  `value<generation>(vector::length)` leaf text as provenance/invariant
  evidence.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-MISSING`: explicit typed
  vector-length metadata is absent for the structured candidate id,
  target/source extension, and selected type tag.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-DUPLICATE`: more than one
  identical vector-length metadata entry is supplied for the same structured
  context.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-CONFLICT`: conflicting
  vector-length metadata entries are supplied for the same structured context.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-METADATA-UNSUPPORTED`: a caller requests
  fixed numeric lanes from typed runtime/scalable metadata.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-CONTEXT-MISMATCH`: the typed selected
  candidate context disagrees with the M68 base-type resolution candidate id
  or selected type tag.
- `TSL-LOWER-ARRAY-INIT-VECTOR-LENGTH-PROVENANCE-MISMATCH`: the M68 base-type
  resolution, unresolved request records, or M70 result disagree on candidate,
  type, branch-chain, slot, variable-token, source-location, or source-request
  provenance required by the boundary.

M71 diagnostics:

- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-SOURCE-UNSUPPORTED`:
  vector-alignment request resolution was invoked with something other than
  an accepted M70 `ExactArrayInitializationVectorLengthResolutionIr`, the
  `array_initialization_vector_length_request_resolution` stage output, or a
  typed `LoweredImplementation` carrying the accepted M70 vector-length
  resolution.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MISSING`: a
  `LoweredImplementation` source does not carry an accepted M70 vector-length
  resolution.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-IR-MULTIPLE`: a
  `LoweredImplementation` source carries more than one M70 vector-length
  resolution at the M71 request-resolution boundary.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISSING`: the M70 unresolved
  request records do not contain the required vector-alignment request.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-DUPLICATE`: the M70
  unresolved request records contain more than one vector-alignment request.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-MISMATCH`: the selected M67
  vector-alignment request record does not carry the expected ordinal `2`,
  request kind `generation_value`, and helper leaf kind
  `value_generation_vector_alignment`.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-REQUEST-UNSUPPORTED`: the selected
  M67 vector-alignment request record does not preserve the exact accepted
  `value<generation>(vector::alignment)` leaf text as provenance/invariant
  evidence.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-MISSING`: explicit typed
  vector-alignment metadata is absent for the structured candidate id,
  target/source extension, and selected type tag.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-DUPLICATE`: more than one
  identical vector-alignment metadata entry is supplied for the same
  structured context.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-CONFLICT`: conflicting
  vector-alignment metadata entries are supplied for the same structured
  context.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-METADATA-UNSUPPORTED`: a caller
  requests fixed numeric alignment from typed unsupported alignment metadata.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-CONTEXT-MISMATCH`: the typed
  selected candidate context disagrees with the M70 vector-length resolution
  candidate id or selected type tag.
- `TSL-LOWER-ARRAY-INIT-VECTOR-ALIGNMENT-PROVENANCE-MISMATCH`: the M70
  vector-length resolution, unresolved request records, or M71 result disagree
  on candidate, type, branch-chain, slot, variable-token, source-location, or
  source-request provenance required by the boundary.

M73 diagnostics:

- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-SOURCE-UNSUPPORTED`: declaration-
  shell lowering was invoked with something other than an accepted M72
  `ExactArrayInitializationHelperSetCompletionIr`, the
  `array_initialization_helper_set_completion` stage output, or a typed
  `LoweredImplementation` carrying a matching M72 helper-set completion.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MISSING`: a
  `LoweredImplementation` source does not carry an accepted M72
  `array_initialization_helper_set_completions` entry.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-IR-MULTIPLE`: a
  `LoweredImplementation` source carries more than one M72 helper-set
  completion at the M73 declaration-shell boundary.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-CONTEXT-MISMATCH`: the typed
  selected candidate context supplied to M73 disagrees with the M72 helper-set
  completion candidate id, target extension, source extension, or selected
  type tag.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-PROVENANCE-MISMATCH`: the M72
  helper-set completion, reachable M66/M65 source chain, M68/M70/M71 results,
  backend-uninit request/boundary, or structural shell output disagree on the
  candidate, extension, selected type, branch-chain, slot, variable, or source
  provenance required by the boundary.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-MALFORMED`: the M72 completion or
  reachable source chain does not preserve the exact first-slot
  `opaque_pre_branch_array_initialization` ordinal `0`
  `var<typed>(array_type<...>, tmp, value<backend>(uninit::array))` shell, the
  exact M66 helper leaves, or the accepted M68/M70/M71 typed helper facts.
- `TSL-LOWER-ARRAY-INIT-DECLARATION-SHELL-BACKEND-UNINIT-POLICY-MISMATCH`:
  the backend-uninit boundary no longer carries the M72
  `deferred_backend_value` policy that M73 must preserve without translation.

M74 diagnostics:

- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-SOURCE-UNSUPPORTED`: the
  source is not an accepted M73 declaration shell, M73 stage output, accepted
  M64/M65 exact array-body envelope source, or typed lowered implementation
  carrying exactly the required M64/M65/M73 values.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MISSING`: a typed source
  container does not carry the required exact M64/M65 envelope or M73
  declaration-shell value.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-IR-MULTIPLE`: a typed source
  container carries multiple candidate envelope or declaration-shell values
  where M74 requires exactly one.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-CONTEXT-MISMATCH`: selected
  candidate, extension, selected type, or branch-chain context does not match
  the typed M64/M65/M73 inputs.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-PROVENANCE-MISMATCH`: accepted
  M64/M65 envelope, M63 selected-body envelope, and M73 declaration shell do
  not agree on candidate, selected type, branch-chain, slot identity, or source
  provenance.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-ROLE-MISMATCH`: the accepted
  envelope does not expose the exact five source-ordered structural/provenance
  roles required by `array.tsl:105-111`.
- `TSL-LOWER-ARRAY-BODY-STRUCTURAL-SEQUENCE-MALFORMED`: the exact structural
  sequence is missing a role, has reordered/extra roles, attaches the M73
  declaration shell to a nonzero slot, or otherwise violates the exact
  five-slot structural invariant without implying slot semantics.

M75 diagnostics:

- `TSL-LOWER-PREDICATE-PATH-SOURCE-UNSUPPORTED`: the source is not an accepted
  M74 structural sequence, M74 stage output, or typed lowered implementation
  carrying exactly one M74 value.
- `TSL-LOWER-PREDICATE-PATH-IR-MISSING`: a typed source container does not
  carry the required exact M74 structural sequence.
- `TSL-LOWER-PREDICATE-PATH-IR-MULTIPLE`: a typed source container carries
  multiple M74 structural sequences where M75 requires exactly one.
- `TSL-LOWER-PREDICATE-PATH-CONTEXT-MISMATCH`: selected candidate, extension,
  selected type, or branch-chain context does not match the typed M74 input.
- `TSL-LOWER-PREDICATE-PATH-PROVENANCE-MISMATCH`: accepted M74 sequence,
  M64/M65 envelope slots, M63 selected-body envelope, and M62 selected-body IR
  do not agree on candidate, selected type, branch-chain, slot identity, or
  source provenance required for predicate-path classification.
- `TSL-LOWER-PREDICATE-PATH-MALFORMED`: the exact predicate-init or
  store-call-shaped predicate-token slot cannot satisfy the M75 structural
  shape invariant.
- `TSL-LOWER-PREDICATE-PATH-TOKEN-MISMATCH`: the exact slot-1 predicate token,
  selected-body assignment target token, or slot-3 predicate argument token do
  not match the required structural `pg` path.

M76 diagnostics:

- `TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-UNSUPPORTED`: the source is not an
  accepted M75 predicate-path request, M75 stage output, or typed lowered
  implementation carrying exactly one M75 value with the required M74 sequence.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MISSING`: a typed source container does
  not carry the required exact M75 predicate-path request.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-IR-MULTIPLE`: a typed source container
  carries multiple M75 predicate-path requests where M76 requires exactly one.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-CONTEXT-MISMATCH`: selected candidate,
  target extension, source extension, selected type, or branch-chain context
  does not match the typed M75/M74/M73 inputs.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-PROVENANCE-MISMATCH`: accepted M75
  predicate-path state, accepted M74 sequence, accepted M73 declaration shell,
  or the slot-3 structural role disagree on candidate, extension, selected
  type, branch-chain identity, role identity, source location, source text, or
  variable-token provenance required for call-site classification.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-SEQUENCE-MISSING`: the accepted M75 value
  does not preserve the M74 structural sequence required by the M76 boundary.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-MALFORMED`: the slot-3 source text cannot
  be parsed as the exact `intrin<...>(...);` call-site shape.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-SHAPE-UNSUPPORTED`: the slot-3 source text
  has a call-like shape but is not the exact supported post-branch call-site
  form.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-CALL-HEAD-MISMATCH`: the structural call
  head token is not the exact `intrin` token.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-INTRINSIC-TOKEN-MISMATCH`: the unresolved
  intrinsic token is not the exact structural `svst1` token.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-ARGUMENT-COUNT-MISMATCH`: the call-site
  does not preserve exactly three structural arguments.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-PREDICATE-ARGUMENT-MISMATCH`: argument 0
  does not match the accepted M75 slot-3 predicate-token use.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-MEMBER-ACCESS-UNSUPPORTED`: argument 1 is
  not the exact structural `tmp.data()` member-access-shaped token/path linked
  to the M73/M74/M75 `tmp` provenance.
- `TSL-LOWER-POST-BRANCH-CALL-SITE-SOURCE-OPERAND-UNSUPPORTED`: argument 2 is
  not the exact structural source operand token `a`.

## Explicit Deferrals

Deferred beyond the implemented M43-M76 semantic-lowering, structural
slot-assembly, pipeline-integration, exact array-initialization slot form IR,
M67 helper-request IR, accepted M68 base-type request resolution, M69 pipeline
extraction, M70 vector-length request resolution, M71 vector-alignment
request resolution, M72 helper-set completion, M73 exact declaration-shell
structural IR, accepted M74 exact structural-sequence classification,
accepted M75 exact predicate-path structural/request IR, and accepted M76 exact
post-branch intrinsic call-site structural/request IR slices, plus the
accepted M77 behavior-preserving composable lowering pipeline/module
boundary, the accepted M78 behavior-preserving lowering package
decomposition, accepted M79 exact array-body typed model ownership, accepted
M80 exact array-body validation boundary extraction, accepted M81
generation-time lowering core ownership extraction, accepted M82 selected-body
envelope ownership extraction, accepted M83 stage-contract ownership
extraction, accepted M84 exact array-body pipeline/source-adapter ownership
extraction, accepted M85 selected-body lowering ownership extraction, and
accepted M86 payload-intake / mini-TSIL leaf lowering ownership extraction:

- Full TSIL grammar and general expression evaluation.
- Generation-time type queries for vector registers, extension transforms, mask
  types, generic vector lengths, aliases, and non-selected base forms.
- Generation-time value queries other than the accepted M55 scalar
  size-bytes form, M56 exact size-bits expression, M57 exact size-byte
  equality predicates, the accepted M70 exact array-initialization
  `value<generation>(vector::length)` request, and the accepted M71 exact
  array-initialization `value<generation>(vector::alignment)` request remain
  deferred. Broad/generic vector-length semantics, broad aligned load/store
  alignment semantics, mask lane constants, and generic lengths remain
  deferred. Accepted M67 classifies the exact M66 vector length/alignment
  leaves as deferred helper-request records; only the M70 request-resolution
  boundary may resolve the vector-length request, and only the accepted M71
  request-resolution boundary may resolve the vector-alignment request. Both
  must consume explicit typed metadata.
- Arithmetic over generation values remains deferred except for the accepted
  M56 exact `type.size_bytes * 8` expression. Comparisons over generation
  values remain deferred except for the accepted M57 exact
  `type.size_bytes == 2/4/8` predicates. Branch-chain pruning over those
  predicates is implemented only for the exact M59 SVE size-byte no-final-else
  branch chain; M60 adds only opaque selected-body handoff, M61 adds only
  exact selected assignment-form recognition, M62 adds only unresolved typed
  body IR for that recognized form, and M63 adds only a backend-neutral
  envelope/sequence boundary over those M62 typed values. Accepted M64 adds
  only exact structural array-body slot assembly around M63 envelopes, and
  accepted M65 wires that typed envelope into the normal lowering pipeline
  without adding skeleton recognition or slot semantics. M66 refines only the
  exact first array-initialization slot into typed form IR. Accepted M67
  classifies the four M66 helper leaves into typed deferred request/provenance
  IR, while keeping helper evaluation and other slots deferred. General
  `else if<generation>` syntax, final-else policy, broad branch pruning based
  on generation values, assignment semantics beyond that selected IR shape,
  broad direct-intrinsic/SVE semantics, backend intrinsic lowering, vector
  length/alignment semantics, backend uninit semantics, generic
  declaration/array semantics, allocation/lifetime, initializer behavior,
  variable scope, surrounding store/return semantics beyond the exact M73
  structural declaration shell,
  skeleton recognition from raw body text, and broad body lowering remain
  deferred. Accepted M68 narrows only the exact M67 base-type request, accepted
  M69 extracts that existing stage assembly without new semantics, accepted
  M70 resolves only the exact vector-length request through explicit typed
  metadata, and accepted M71 resolves only the exact vector-alignment request
  through explicit typed metadata. Implemented M72 packages the exact helper
  set and keeps backend uninit as a typed deferred backend-value boundary.
  Implemented M73 records only the exact first-slot declaration-shell
  structure over that helper set. Implemented M74 records only exact
  source-ordered body sequence and structural/provenance slot roles around
  that M73 value. Accepted M75 records only exact predicate-path
  structural/request state across slots 1, 2, and 3 without SVE or store
  semantics. Accepted M76 records only exact post-branch intrinsic call-site
  structural/request state for slot 3 without store, memory, pointer,
  variable-scope, ARM/SVE intrinsic, backend translation, rendering, or output
  semantics. Backend uninit translation, broad
  vector/register metadata, generic declaration/array/body semantics,
  allocation/lifetime, initializer behavior, variable scope, predicate
  semantics, direct-intrinsic/SVE semantics, store/return semantics, aligned
  load/store semantics, rendering, and output remain deferred.
- Signedness branch pruning is accepted for the exact M48 slice:
  `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))`
  plus `else<generation>` form over typed M43 `base.in` values. M51 adds only
  the same predicate with plain `else`; broader plain `else`,
  vector/generic predicates, and branch body semantics remain deferred.
- Backend modifier translation remains limited to the M45 intrinsic suffix
  request over typed M43 inputs; prefix, infix, post, and `immediate(n)` remain
  deferred.
- Backend suffix/type-spelling translation for concrete integer tags beyond the
  accepted selected M45/M46 `si32`/`ui32` behavior remains deferred even though
  M52 accepts generation-time type/signedness semantics for those tags, M53
  moves the rule source boundary, and M54 only wires catalog-derived rules into
  lowering input.
- Backend type/value requests whose inputs are still raw generation-time text.
- Primitive-call lowering, loops, variables, aliases, casts, arrays, and
  branch-dependent backend output.
- Generated-test parity beyond the selected M49 `add_i32_basic` source slice,
  Rust body rendering, CLI compatibility, broad report parity beyond the
  selected M50 row, artifact writer changes, and compiler/test execution.
