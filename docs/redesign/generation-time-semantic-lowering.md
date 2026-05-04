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
| vector/register metadata | likely later | Required for `vector::length`, `vector::alignment`, and register types. |
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
| `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))` | `tsldata/primitives/bitwise/shifts.tsl:535-553`, `shifts.tsl:625-648`, `shifts.tsl:842-886` | Select signed or unsigned shift behavior. | Type tag and signedness query. | Boolean `GenerationValue` derived from typed type query. | Type-map data and base type metadata. | required-later | Defer until signedness branch parity is selected. | Type-query tests before branch tests; unsupported predicate diagnostics. |
| `type<generation>(vector::register)` | `tsldata/primitives/load_store/load.tsl:39-45`, `load.tsl:59-67`, `store.tsl:56-61` | Resolve selected vector register type. | Backend id, extension, type tag, vector/register metadata. | `GenerationTypeRef(kind="vector.register")`. | Language type map. | required-later | Defer until vector register type rendering is selected. | Typed metadata fixtures; missing language-map diagnostics. |
| `value<generation>(vector::length)` | `tsldata/primitives/load_store/load.tsl:41-43`, `tsldata/primitives/bitwise/shifts.tsl:50-53`, `shifts.tsl:218-221` | Resolve lane count for generated loops. | Extension, type tag, lane metadata. | `GenerationValue[int](kind="vector.length")`. | Extension/type metadata. | required-later | Defer with loop lowering. | Deterministic lane query tests after loop model exists. |
| `value<generation>(vector::alignment)` | `tsldata/primitives/load_store/load.tsl:55-70`, `store.tsl:54-64`, `store.tsl:75-85` | Supply alignment value to selected aligned branch. | Extension, type tag, alignment metadata. | `GenerationValue[int](kind="vector.alignment")`. | Extension/type metadata. | required-later | Defer until aligned branch body rendering is selected. | Query tests plus missing alignment diagnostics. |
| `type<generation>(base::in)` | `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:150`, `tsldata/primitives/conversion/repr_change.tsl:1210-1225` | Resolve selected primitive base type. | Type tag and active vector type. | `GenerationTypeRef(kind="base.in")`. | No backend data to resolve the semantic type; later backend spelling uses language maps. | implemented M43 | Selected by Milestone 43 as part of the base type query family. | Type-query diagnostics for missing type tag. |
| `type<generation>(base::signed_of(type<generation>(base::in)))` and `type<generation>(base::unsigned_of(type<generation>(base::in)))` | `tsldata/primitives/arithmetic/fundamental.tsl:47-90`, `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:63-82` | Convert selected base type to signed/unsigned companion. | Type tag and integer signedness rules. | `GenerationTypeRef(kind="base.signed_of")` or `base.unsigned_of`. | No backend data to resolve the semantic type; later suffix translation uses translation maps. | implemented M43 | Milestone 43 accepts only these exact nested forms. Prose shorthand such as `base::signed_of(base::in)` is not accepted TSIL syntax. | Query tests for selected scalar tags; unsupported float/pointer/generic conversion diagnostics. |
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
| Signedness/type predicate branch | `tsldata/primitives/bitwise/shifts.tsl:535-553`, `:625-648`, `:842-886`; `tsldata/primitives/conversion/repr_change.tsl:1210-1217`; canonical predicate evidence in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:403`, `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:4586-4596`, and `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:4848-4930`. | `if<generation>(value<generation>(type::is_signed(type<generation>(base::in)))) { ... } else<generation> { ... }`. | Selected type tag plus the M42 branch-pruning provenance fields. | Boolean generation value derived from a `GenerationTypeRef(kind="base.in")`. | Builds on M42 branch pruning and should consume the base type query model instead of parsing type text separately. | None for the predicate itself; selected branch bodies may contain backend requests. | Not needed for accepted `binary/add`; not the shortest path to native integer add suffixes. | Yes for shift-right and conversion parity after the type query model exists. | Low to medium after M43, medium if implemented before type refs. | Branch true/false tests for signed and unsigned integer candidates, selected-branch-only diagnostics, unsupported predicate diagnostics, and unresolved selected-branch helper tests. | Defer until after the M44-M47 native integer add phase unless a shift/conversion parity slice is selected earlier. |
| Vector/register metadata query family | `tsldata/primitives/load_store/load.tsl:39-42`, `:55-70`; `tsldata/primitives/load_store/store.tsl:54-64`, `:177-205`; `tsldata/primitives/conversion/repr_change.tsl:1512-1529`; C++ metadata keys in `tsldata/detail/lang/translate_cpp.tsl:16-23` and `:63-65`; legacy vector refs in `frozen/tsl-gen/tsl_gen/tsil_engine/expansion_support.py:3877-3892`. | `type<generation>(vector::register)`, `type<generation>(vector::as_extension(...))`, `type<generation>(vector::transform_extension(...))`, `value<generation>(vector::length)`, `value<generation>(vector::alignment)`. | Backend id only after translation, selected extension/source extension, type tag, vector width/lane/alignment metadata, implementation source location. | `GenerationTypeRef` for vector/register concepts or `GenerationValue` with integer or symbolic payload for vector length/alignment. | Selected forms appear inside loops, casts, calls, and aligned branch bodies, so a standalone query would not make those bodies lowerable yet. | Extension metadata and later language/translation maps. | Not needed for current `binary/add`. | Likely for load/store after add, but it needs several companion constructs. | Medium to high. | Metadata fixtures for fixed-width vectors, missing metadata diagnostics, deterministic value tests, and no host-CPU dependency. | Defer; revisit when load/store parity is selected. |
| Immediate and generic-parameter value family | `tsldata/primitives/conversion/repr_change.tsl:1-10` for `sImm_type`; `tsldata/primitives/conversion/repr_change.tsl:121-128` and `:1188-1225` for `generic::length(OutVec)`; `tsldata/primitives/conversion/repr_change.tsl:352-370` and `:908-918` for `immediate(n)=...`; `tsldata/primitives/bitwise/shifts.tsl:1-10` for shift immediates. | `value<generation>(generic::length(OutVec))`, immediate modifier values such as `index` or a literal, selected generic parameters such as `ToBase`, `ToExtension`, and `index`. | Generic parameter bindings, immediate parameter roles, type aliases, selected extension/type context, parameter list, implementation source location. | `GenerationValue[int]`, `GenerationValue[GenericParamRef]`, or typed immediate-modifier value. | Requires compile switches, generic parameter scope, aliases, calls, and modifier parsing that are outside M42. | Some forms later require backend translation maps for modifier emission. | Not needed for current `binary/add`. | Important for conversion/extract/insert, but not the next smallest parity slice. | High. | Scope tests for generic bindings, immediate position validation, missing parameter diagnostics, and deterministic generic length once alias/type scope exists. | Defer. |
| Second primitive-attribute branch | `store.tsl:177-188` and `196-213`; M42 already implements the aligned attribute shape. | `if<generation>(value<generation>(primitive::attribute(packed))) { ... } else<generation> { ... }`. | Primitive attributes, selected candidate id, implementation source location; useful mask-store lowering also needs mask roles and vector metadata. | Boolean primitive-attribute generation value plus pruned branch provenance. | Small code change if generalized from `aligned`, but selected branch bodies still contain unsupported masks, vector types, loops, and backend scalar casts. | None for the condition; branch bodies later need backend/type metadata. | Not needed. | Only useful when mask store parity is selected. | Low implementation risk, low parity value now. | Reuse M42 branch tests for `packed`, plus mask-store selected-branch diagnostics when mask parity exists. | Defer. |

## Selected Next Helper Slice

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

M43 supported type tags and companion behavior:

| Selected tag | `base::in` | signed companion | unsigned companion |
| --- | --- | --- | --- |
| `si32` | `si32` | `si32` | `ui32` |
| `ui32` | `ui32` | `si32` | `ui32` |

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
type_tag="ui32", spelling="uint32_t")`. Native integer rendering remains
deferred to M47. Prefix, infix, post, immediate, and broad translation-map or
language-map evaluation remain deferred. Renderers remain non-evaluating text
emitters and must not parse raw generation-time helper text.

## Post-M43 Phase Direction

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
  inputs.

This phase does not make backend translation parse raw generation-time helper
text and does not move suffix or type-spelling evaluation into renderers.

## Explicit Deferrals

Deferred beyond the Milestone 43 slice:

- Full TSIL grammar and general expression evaluation.
- Generation-time type queries for vector registers, extension transforms, mask
  types, generic vector lengths, aliases, and non-selected base forms.
- Generation-time value queries for vector length, vector alignment, mask lane
  constants, and generic lengths.
- Signedness branch pruning for
  `if<generation>(value<generation>(type::is_signed(...)))`.
- Backend modifier translation remains limited to the M45 intrinsic suffix
  request over typed M43 inputs; prefix, infix, post, and `immediate(n)` remain
  deferred.
- Backend type/value requests whose inputs are still raw generation-time text.
- Primitive-call lowering, loops, variables, aliases, casts, arrays, and
  branch-dependent backend output.
- Rust body rendering, generated-test parity, CLI compatibility, report parity,
  artifact writer changes, and compiler/test execution.
