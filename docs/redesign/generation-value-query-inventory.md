# Generation Value Query Inventory

Milestone 154 inventories the current `value<generation>(...)` surface in
`tsldata/**/*.tsl`. It is documentation only: no evaluator, branch pruning,
loop execution, backend rendering, source repair, or expression parser is
introduced here.

## Evidence

Required corpus commands:

```bash
rg -n "value<generation>\\(" tsldata -g "*.tsl"
rg --count-matches "value<generation>\\(" tsldata -g "*.tsl"
```

The balanced query scan found 597 `value<generation>(...)` islands in 24
files. They group into 10 semantic query families and 13 exact observed forms.
The `rg -n` evidence listing has 576 matching source lines because some lines
contain multiple query islands.

Per-file match counts from `rg --count-matches`:

| File | Matches |
| --- | ---: |
| `tsldata/primitives/conversion/mask_specific.tsl` | 33 |
| `tsldata/primitives/load_store/store.tsl` | 24 |
| `tsldata/primitives/conversion/repr_change.tsl` | 115 |
| `tsldata/primitives/bitwise/shifts.tsl` | 24 |
| `tsldata/primitives/misc/conflict.tsl` | 2 |
| `tsldata/primitives/conversion/cast.tsl` | 50 |
| `tsldata/primitives/load_store/load.tsl` | 30 |
| `tsldata/primitives/load_store/sequence.tsl` | 4 |
| `tsldata/primitives/load_store/pack_expand.tsl` | 7 |
| `tsldata/primitives/mask/construct.tsl` | 3 |
| `tsldata/primitives/io/out.tsl` | 22 |
| `tsldata/primitives/bitwise/horizontal.tsl` | 47 |
| `tsldata/primitives/misc/compress.tsl` | 4 |
| `tsldata/primitives/load_store/construct.tsl` | 12 |
| `tsldata/primitives/comparison/fundamental.tsl` | 72 |
| `tsldata/primitives/load_store/rnd_access.tsl` | 24 |
| `tsldata/primitives/arithmetic/horizontal.tsl` | 12 |
| `tsldata/primitives/load_store/array.tsl` | 31 |
| `tsldata/primitives/bitwise/bit_ops.tsl` | 42 |
| `tsldata/primitives/mask/bitwise.tsl` | 11 |
| `tsldata/primitives/misc/blend.tsl` | 2 |
| `tsldata/primitives/arithmetic/fundamental.tsl` | 4 |
| `tsldata/primitives/arithmetic/complex.tsl` | 14 |
| `tsldata/primitives/bitwise/bit_counts.tsl` | 8 |

## Observed Families

| Family | Count | Representative locations | Required facts | Surrounding contexts | M154 classification |
| --- | ---: | --- | --- | --- | --- |
| `value<generation>(vector::length)` | 287 | `tsldata/primitives/arithmetic/complex.tsl:37`, `tsldata/primitives/load_store/rnd_access.tsl:65`, `tsldata/primitives/load_store/array.tsl:125` | selected `CurrentVector`, extension metadata, scalar type tag, lane-count policy | `loop<unroll>`, `loop<range>`, `array_type`, index arithmetic, casts, calls | Selected for the next largest-safe isolated value-query slice. |
| `value<generation>(vector::alignment)` | 31 | `tsldata/primitives/load_store/array.tsl:37`, `:38`, `tsldata/primitives/load_store/construct.tsl:103` | selected `CurrentVector`, extension/type alignment metadata | `array_type`, `assume_aligned<...>`, declarations | Selected for the next largest-safe isolated value-query slice. |
| `value<generation>(type::size_bytes(type<generation>(base::in)))` | 35 | `tsldata/primitives/bitwise/bit_counts.tsl:99`, `tsldata/primitives/bitwise/horizontal.tsl:154`, `tsldata/primitives/load_store/array.tsl:107` | selected scalar `TypeTag` and scalar size facts | `mem<copy>`, arithmetic such as `* 8` or division, generation branch comparisons | Selected for the next largest-safe isolated value-query slice. Surrounding arithmetic/comparisons remain later. |
| `value<generation>(type::size_bytes(type<generation>(vector::imask)))` | 3 | `tsldata/primitives/conversion/mask_specific.tsl:100`, `:126`, `:487` | selected vector mask/integral-mask type policy plus type-size facts | arithmetic `* 8`, mask loops | Deferred to a mask/vector-mask value slice. |
| `value<generation>(type::is_signed(type<generation>(base::in)))` | 50 | `tsldata/primitives/bitwise/shifts.tsl:535`, `tsldata/primitives/conversion/repr_change.tsl:540`, `:1093` | selected scalar `TypeTag` signedness facts | `if<generation>`, type-selection contexts | Selected for the next largest-safe isolated value-query slice. Branch pruning remains later. |
| `value<generation>(type::is_signed(type<generation>(vector::imask)))` | 1 | `tsldata/primitives/mask/bitwise.tsl:359` | selected vector mask/integral-mask type policy plus signedness facts | `if<compile>` with additional raw boolean syntax | Deferred to a mask/vector-mask value slice. |
| `value<generation>(type::is_same(type<generation>(base::in), ...))` | 43 | `tsldata/primitives/bitwise/bit_counts.tsl:97`, `tsldata/primitives/conversion/repr_change.tsl:670`, `tsldata/primitives/conversion/cast.tsl:394` | selected scalar `TypeTag`, scalar literal type tag | `type<generation>(select(...))`, `if<generation>`, `if<compile>` | Selected for the next largest-safe isolated value-query slice. Type-select consumption and branch pruning remain separate consumers. |
| `value<generation>(primitive::attribute(aligned))` | 21 | `tsldata/primitives/load_store/load.tsl:55`, `:228`, `tsldata/primitives/load_store/store.tsl:54` | selected concrete primitive attributes from catalog/selection | `if<generation>`, `attrs[...]` selector payloads | Selected for the next largest-safe isolated value-query slice. Attribute substitution inside selector text remains later. |
| `value<generation>(primitive::attribute(packed))` | 7 | `tsldata/primitives/load_store/store.tsl:177`, `:196`, `:235` | selected concrete primitive attributes from catalog/selection | `if<generation>`, mask store bodies | Selected with the same primitive-attribute value-query boundary as `aligned`. |
| `value<generation>(mask::lane::all_true)` | 30 | `tsldata/primitives/bitwise/bit_ops.tsl:608`, `:1559`, `tsldata/primitives/conversion/mask_specific.tsl:192` | typed backend/support-helper request, later backend helper rendering | nested `call<primitive=set1[...]>(...)`, assignments, `var<const_infer>` values | M177 discovers exact request islands without rendering helper text. |
| `value<generation>(mask::lane::all_false)` | 12 | `tsldata/primitives/comparison/fundamental.tsl:57`, `:216`, `:368` | typed backend/support-helper request, later backend helper rendering | `var<const_infer>` values | M177 discovers exact request islands without rendering helper text. |
| `value<generation>(generic::length(OutVec))` | 75 | `tsldata/primitives/conversion/cast.tsl:618`, `tsldata/primitives/conversion/repr_change.tsl:124`, `tsldata/primitives/load_store/pack_expand.tsl:392` | resolved type alias/generic-vector alias facts for `OutVec` | loop bounds, start-index arithmetic | M168 lowers exact `generic::length(TYPE_EXPR)` when `TYPE_EXPR` resolves to a concrete fixed vector. M169 can make `OutVec` concrete when aliases flow through explicit selected base/extension bindings. |
| `value<generation>(generic::runtime_length(ToType))` | 2 | `tsldata/primitives/conversion/cast.tsl:847`, `:893` | resolved alias facts plus runtime/scalable length policy | raw assignment to `out_lanes` | M168 lowers exact `generic::runtime_length(TYPE_EXPR)` only for concrete fixed vectors; M169 can make `ToType` concrete only when an explicit selected vector/type binding is supplied. Runtime/scalable cases remain diagnostics. |

All required prompt-listed families are present in the current corpus. The only
additional observed family is `mask::lane::all_false`.

## Largest Safe Next Subset

M154 selects this next executor subset:

```text
Selected-context generation value query lowering:
- value<generation>(vector::length)
- value<generation>(vector::alignment)
- value<generation>(type::size_bytes(TYPE_EXPR))
- value<generation>(type::is_signed(TYPE_EXPR))
- value<generation>(type::is_same(TYPE_EXPR, TYPE_EXPR))
- value<generation>(primitive::attribute(KEY))
```

This covers 474 of the 597 observed query islands while staying inside one
cohesive boundary: all selected forms consume the already accepted selected
implementation context, current vector/type facts, selected scalar `TypeTag`,
extension metadata, and concrete primitive attributes. They can be lowered as
isolated query islands and tested through one focused generation-value owner
without parsing surrounding loops, assignments, casts, primitive calls,
operators, branch regions, or backend render syntax.

For the `type::*` families, the selected boundary is the outer value query
family plus typed argument lowering. M155 should lower each `TYPE_EXPR`
through the accepted type-lowering path first, then evaluate only supported
lowered scalar type values. The current corpus evidence is dominated by
`type<generation>(base::in)`, but M155 should not raw-string match that exact
nested spelling. Lowered vector/mask/generic type values remain deferred
diagnostics for this milestone.

The selected subset is deliberately not a promise that every current source
line containing those queries becomes renderable. For example,
`loop<range>(..., value<generation>(vector::length), ...)`, `if<generation>(...)`,
`array_type<...>`, `assume_aligned<...>`, arithmetic such as `* 8`, and
`attrs[...]` payload use remain separate surrounding TSIL/raw contexts.

## Excluded Candidates

| Candidate | Additional count | Why excluded from M155 |
| --- | ---: | --- |
| Add `vector::imask` size/signedness queries | 4 | These require the mask/integral-mask type policy to be solved as generation-value size/signedness facts, not only as type-query values. Keeping them out prevents the selected scalar type-value slice from becoming a mask policy milestone. |
| Add mask lane constants | 42 | M177 implements exact typed backend/support-helper request island discovery. Rendering them remains a later backend/helper rule. |
| Add generic length/runtime length | 77 | Addressed by M168 as exact `generic::*` generation-expression lowering for concrete fixed vector facts. M169 lets selected binding facts make `OutVec` aliases concrete when they flow through declared base/extension symbols, and lets explicit vector/type bindings make `ToType`-style `TYPE_EXPR` values concrete before `generic::*` evaluation. Runtime/scalable, size-parameter-only, unresolved alias/specialization, non-vector, and metadata-missing cases remain diagnostics. |
| Add all surrounding consumers | n/a | Branch pruning, loop expansion, declarations, selector-attribute substitution, arithmetic, comparisons, casts, memory, I/O, primitive-call rendering, and backend rendering are separate TSIL keyword or rendering milestones. |

## M155 Boundary Recommendation

M155 should implement only isolated selected-context generation-value query
lowering for the selected subset above. It should expose a small typed value
result such as integer, boolean, or primitive attribute value, preserve source
text/provenance, and return precise diagnostics for unsupported query families.

M155 should not implement branch pruning, loop expansion, expression
arithmetic, comparison folding, selector-attribute substitution, mask
constants, generic alias lengths, backend rendering, or raw text replacement.
