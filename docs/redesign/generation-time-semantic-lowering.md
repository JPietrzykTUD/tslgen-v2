# Generation-Time Semantic Lowering Contract

Milestone 41 defines the contract for generation-time helper semantics that
must run before backend translation. It is a planning and inventory milestone:
no production lowering or rendering behavior is added here.

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

The first implementation slice should use an explicit immutable
`GenerationContext` rather than raw parser dictionaries or backend renderer
state.

| Field | Status | Purpose |
| --- | --- | --- |
| selected primitive name | required next | Diagnostic and provenance anchor for branch/query resolution. |
| emitted primitive name | required next | Stable output-facing name when it differs from source primitive identity. |
| selected candidate id | required next | Deterministic identity for one implementation candidate. |
| normalized signature | required next | Confirms the helper is evaluated for the selected overload shape. |
| parameter list | required next | Keeps diagnostics tied to the selected implementation signature. |
| primitive attributes | required next | Supplies boolean values such as `aligned` and `packed`. |
| implementation source location | required next | Provides actionable diagnostics for malformed or unsupported helpers. |
| backend id | likely later | Required for backend-scoped requests after generation values are typed. |
| extension and source extension | likely later | Required for vector metadata, intrinsic suffixes, and conversion helpers. |
| type tag | likely later | Required for signedness, base-type, and suffix queries. |
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
| `if<generation>(value<generation>(primitive::attribute(aligned)))` | `tsldata/primitives/load_store/load.tsl:55-70`, `load.tsl:79-91`, `store.tsl:54-64`, `store.tsl:75-85` | Select aligned or unaligned branch for load/store bodies. | Primitive attributes, candidate id, source location. | Boolean `GenerationValue` plus pruned statement list with branch provenance. | No backend data for the condition itself; branch bodies may contain backend requests. | required-next | Selected for Milestone 42. | Golden TSIL fixture for true/false branch selection, unknown attribute diagnostics, renderer non-evaluation regression. |
| `if<generation>(value<generation>(primitive::attribute(packed)))` | `tsldata/primitives/load_store/store.tsl:177-188`, `store.tsl:196-210` | Select packed mask-store path. | Primitive attributes, mask parameter role, vector metadata. | Same branch-pruning model as `aligned`, with mask-specific context later. | Mask/vector type data for selected branch. | required-later | Defer until mask store parity is selected. | Reuse branch evaluator after selected mask fixture exists. |
| `if<generation>(value<generation>(type::is_signed(type<generation>(base::in))))` | `tsldata/primitives/bitwise/shifts.tsl:535-553`, `shifts.tsl:625-648`, `shifts.tsl:842-886` | Select signed or unsigned shift behavior. | Type tag and signedness query. | Boolean `GenerationValue` derived from typed type query. | Type-map data and base type metadata. | required-later | Defer until signedness branch parity is selected. | Type-query tests before branch tests; unsupported predicate diagnostics. |
| `type<generation>(vector::register)` | `tsldata/primitives/load_store/load.tsl:39-45`, `load.tsl:59-67`, `store.tsl:56-61` | Resolve selected vector register type. | Backend id, extension, type tag, vector/register metadata. | `GenerationTypeRef(kind="vector.register")`. | Language type map. | required-later | Defer until vector register type rendering is selected. | Typed metadata fixtures; missing language-map diagnostics. |
| `value<generation>(vector::length)` | `tsldata/primitives/load_store/load.tsl:41-43`, `tsldata/primitives/bitwise/shifts.tsl:50-53`, `shifts.tsl:218-221` | Resolve lane count for generated loops. | Extension, type tag, lane metadata. | `GenerationValue[int](kind="vector.length")`. | Extension/type metadata. | required-later | Defer with loop lowering. | Deterministic lane query tests after loop model exists. |
| `value<generation>(vector::alignment)` | `tsldata/primitives/load_store/load.tsl:55-70`, `store.tsl:54-64`, `store.tsl:75-85` | Supply alignment value to selected aligned branch. | Extension, type tag, alignment metadata. | `GenerationValue[int](kind="vector.alignment")`. | Extension/type metadata. | required-later | Defer until aligned branch body rendering is selected. | Query tests plus missing alignment diagnostics. |
| `type<generation>(base::in)` | `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:150`, `tsldata/primitives/conversion/repr_change.tsl:121-128` | Resolve selected primitive base type. | Type tag and active vector type. | `GenerationTypeRef(kind="base.in")`. | Language type map. | required-later | Defer until type-aware casts or conversion parity are selected. | Type-query diagnostics for missing type tag. |
| `type<generation>(base::signed_of(...))` and `base::unsigned_of(...)` | `tsldata/primitives/arithmetic/fundamental.tsl:47-80`, `tsldata/primitives/bitwise/shifts.tsl:38-40`, `shifts.tsl:63-82` | Convert selected base type to signed/unsigned companion. | Type tag and integer/float signedness rules. | `GenerationTypeRef(kind="base.signed_of")` or `base.unsigned_of`. | Type metadata and suffix rules. | required-later | Defer until suffix inference or signedness branches are selected. | Query tests for all selected scalar tags; unsupported float/int conversion diagnostics. |
| `type<generation>(vector::transform_extension(...))` and `vector::as_extension(...)` | `tsldata/primitives/conversion/repr_change.tsl:121-128`, `tsldata/primitives/bitwise/shifts.tsl:875-880`, `shifts.tsl:1222-1240` | Build related vector types for conversion or reinterpret paths. | Current extension, target extension, type tag, vector family/width. | `GenerationTypeRef(kind="vector.transform_extension")`. | Extension metadata and language type map. | required-later | Defer until conversion parity slice. | Fixture-driven type transformation tests. |
| `type<generation>(vector::mask_underlying_t)` | `tsldata/primitives/load_store/store.tsl:177-188`, `store.tsl:196-210` | Resolve mask storage word type. | Mask parameter role, vector mask metadata. | `GenerationTypeRef(kind="vector.mask_underlying_t")`. | Language type map and vector mask metadata. | required-later | Defer until mask store parity. | Mask metadata tests. |
| `value<generation>(mask::lane::all_true)` | `tsldata/primitives/bitwise/bit_ops.tsl` search result for `mask::lane::all_true` | Supply all-true mask lane literal. | Mask lane count and representation. | `GenerationValue[int|string](kind="mask.lane.all_true")`. | Mask metadata. | explicitly-deferred | Defer until mask helper parity. | Mask fixture and metadata diagnostics. |
| `type<backend>(vector::as_extension(...))` | `tsldata/primitives/arithmetic/fundamental.tsl:38-45`, `tsldata/primitives/bitwise/shifts.tsl:50-53`, `shifts.tsl:68-76` | Request backend spelling for a semantically selected vector type. | Resolved generation type value and backend id. | Backend translation request over `GenerationTypeRef`. | Language type map. | required-later | Defer until generation type values exist. | Backend translation tests must reject raw nested generation text. |
| `type<backend>(scalar::ui64)` and scalar backend casts | `tsldata/primitives/load_store/store.tsl:181-188`, `store.tsl:196-210`, `tsldata/primitives/conversion/repr_change.tsl:121-128` | Request backend scalar type spelling. | Resolved scalar type and backend id. | Backend type translation request. | Language type map. | required-later | Defer until scalar backend type request slice. | Missing type-map and unsupported backend diagnostics. |
| `value<backend>(intrin::suffix(...))` | `tsldata/primitives/arithmetic/fundamental.tsl:47-80`, `tsldata/primitives/bitwise/shifts.tsl:63-82`, `shifts.tsl:672-683` | Compute backend intrinsic suffix from selected type. | Resolved generation type, extension, backend id. | Backend translation value request. | Translation map and extension metadata. | required-later | Defer until modifier translation slice. | Tests prove generation type resolves before suffix translation. |
| `value<backend>(intrin::prefix)` and stream suffix | `tsldata/primitives/load_store/load.tsl:55-70`, `store.tsl:54-64` | Compute backend intrinsic prefix and stream-load/store suffix. | Backend id and extension. | Backend translation value request. | Translation map and extension metadata. | required-later | Defer until load/store native modifier slice. | Missing translation-map and unsupported extension diagnostics. |
| `post=...`, `infix=...`, `prefix=...`, `suffix=...`, `immediate(n)=...` modifiers | `frozen/tsl-gen/tsl_gen/tsil.lark:75-78`, `frozen/tsl-gen/tsl_gen/resolver/render_support.py:565-699`, `tsldata/primitives/bitwise/shifts.tsl:150`, `shifts.tsl:1511-1517` | Modify composed intrinsic names or direct intrinsic calls. | Resolved type/value modifiers and ordered intrinsic arguments. | Intrinsic modifier IR fields. | Translation map and backend-specific intrinsic metadata. | required-later | Defer broad modifier evaluation; keep only M40 selected default composition active. | Modifier-specific parser and translation diagnostics. |
| Direct `intrin<...>` calls with template placeholders | `tsldata/primitives/bitwise/shifts.tsl:120-128`, `shifts.tsl:150`, `tsldata/primitives/conversion/repr_change.tsl:25-43` | Emit an already named intrinsic or placeholder-bearing intrinsic call. | Backend id, type tag, extension, placeholder rules. | Direct backend intrinsic call IR or explicit unsupported node. | Translation metadata and language-specific rules. | explicitly-deferred | Defer until a direct-intrinsic parity target is selected. | Unsupported diagnostics until selected. |
| Primitive calls and generic loops | `tsldata/primitives/arithmetic/fundamental.tsl:38-45`, `tsldata/primitives/load_store/load.tsl:39-45`, `tsldata/primitives/conversion/repr_change.tsl:121-128` | Compose helper primitives, arrays, and loop bodies. | Primitive dependency graph, variable scope, vector length. | Call, loop, variable, and assignment IR. | Selection, dependency, and lowering metadata. | explicitly-deferred | Defer beyond the first generation helper slice. | Separate primitive-call and loop lowering tests. |

## Selected Next Helper Slice

Outcome A is selected for the next implementation milestone.

The next slice should implement exactly the boolean primitive-attribute
generation condition:

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
small enough because the condition depends only on primitive attributes. The
selected branch bodies still contain deferred helper forms such as
`type<generation>(vector::register)`, `value<generation>(vector::alignment)`,
and `value<backend>(intrin::prefix)`, so Milestone 42 should prune the branch
and preserve unsupported diagnostics for any unselected nested helper.

Required context fields for the selected slice:

- selected primitive name
- emitted primitive name
- selected candidate id
- normalized signature
- parameter list
- primitive attributes
- implementation source location

Expected lowered behavior:

- Recognize the selected `if<generation>` condition shape.
- Resolve `value<generation>(primitive::attribute(aligned))` to a typed boolean
  generation value.
- Keep only the selected branch as the semantic-lowering output, with
  deterministic provenance.
- Diagnose unknown attributes, non-boolean attribute values, malformed branch
  syntax, unsupported condition expressions, and missing generation context.
- Continue diagnosing unresolved nested generation-time helpers before backend
  translation unless a later slice selects them.

Milestone 42 should implement this selected primitive-attribute branch slice.

## Explicit Deferrals

Deferred beyond Milestone 41:

- Full TSIL grammar and general expression evaluation.
- Generation-time type queries for vector registers, base signedness, extension
  transforms, mask types, and generic vector lengths.
- Generation-time value queries for vector length, vector alignment, mask lane
  constants, and generic lengths.
- Backend modifier translation for suffix, prefix, infix, post, and
  `immediate(n)`.
- Backend type/value requests whose inputs are still raw generation-time text.
- Primitive-call lowering, loops, variables, aliases, casts, arrays, and
  branch-dependent backend output.
- Rust body rendering, generated-test parity, CLI compatibility, report parity,
  artifact writer changes, and compiler/test execution.
