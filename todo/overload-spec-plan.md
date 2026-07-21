# TSL Primitive Overload Specification Plan

## Purpose and Status

This document inventories the overload space authored by the current
`tsldata/primitives` corpus and records the resulting requirements for a future
source-owned overload specification. It is an input to the generated Rust API
plan. The minimal overload field and its current axis/value vocabulary are now
agreed; remaining open questions are listed at the end.

The snapshot was taken on 2026-07-20 from primitive declaration headers and the
typed catalog model. Counts refer to source-authored declarations before
extension, type, profile, and implementation selection.

## Scope and Counts

- 160 authored primitive declarations.
- 104 distinct primitive names.
- 64 exact authored signature spellings.
- 62 normalized typed signature shapes. `s:=v[idx]` normalizes to `s:=v`, and
  `v:=(v)` normalizes to `v:=v`; their additional distinctions come from other
  typed source facts.
- 37 primitive names have more than one authored declaration.
- 21 exact attribute-list spellings occur; after normalizing insignificant
  whitespace they represent 20 semantic combinations.
- 8 declarations contain `aligned=*`; 2 of those also contain `packed=*`.
  Wildcard expansion therefore turns the 160 declarations into 172 typed
  catalog primitives.
- 21 declarations across 14 names contain an `sImm` parameter.
- 49 declarations carry an explicit `mask` policy attribute.

The following are not counted as source overload declarations:

- implementations for different extensions or type groups;
- implementation variants and required target features;
- concrete element types and lane counts selected later;
- the concrete `true`/`false` copies produced from `aligned=*` and `packed=*`;
- backend-only emitted-name rewrites.

## Existing Overload Axes

The corpus already expresses several independent axes. They must not be
collapsed into one flat `meta=(...)` value.

| Axis | Existing source owner | Examples | Overload consequence |
|---|---|---|---|
| Result and parameter kinds | `prim<RESULT:=PARAMS>` | `v`, `s`, `m`, `vidx`, pointers | Distinguishes callable type shapes. |
| Compile-time binding | `sImm` signature kind | immediate shifts, scale, index, shuffle control | Rust const generic; not a runtime parameter. |
| Mask policy | `mask=zero` or `mask=pass_through` | arithmetic, memory, permutation | Determines inactive-lane or inactive-write semantics. |
| Ordinary mask operand | `m` parameter without `mask=...` | mask algebra, active-lane reductions | A mask value is not automatically a mask policy. |
| Boolean variant axis | `aligned=*`, `packed=*` | load/store and mask representation I/O | Expands one declaration into concrete variants. |
| Semantic operation axis | `cast`, `direction`, `op`, `value` | conversions, pack/expand, constructors | Distinguishes semantic variants already named by attributes. |
| Free compile-time parameter | `generic_params` | `PreserveSign`, `Index`, `N` | Adds a const or type generic to one declaration. |
| Result type axis | `return_type` | conversion, resizing, mask extraction/insertion | Adds a caller-selected target base or extension. |
| Implementation safety | implementation `safety` | raw pointers, intrinsics | Changes safety requirements, not overload identity. |

`primary` is independent of the registered overload axis: it identifies the
axis value that a non-overloading language facade uses for the unsuffixed name.
It is not an alternative to `uniform`, `per_lane`, or any binding-time
classification.

Likewise, `uniform_immediate` should not be a primitive enum member. Immediate
binding is already represented by `sImm`; whether that immediate is a uniform
lane operand, an index, a scale, or an encoded control is separate semantics.

## Current Signature-Kind Vocabulary

The table includes every signature kind used by the 160 declarations. The
identity tokens are current typed compiler facts used when target-language
parameter types are compared for overload identity.

| Kind | Results | Parameter occurrences | Current identity token | Relevant meaning |
|---|---:|---:|---|---|
| `cptr` | 0 | 12 | `const_ptr` | Const pointer. |
| `cptr+` | 0 | 1 | `const_ptr` | Const pointer with a distinct source shape. |
| `im` | 9 | 10 | `base` | Integral-mask value. |
| `imt` | 0 | 2 | `target_imask` | Caller-selected target integral-mask type. |
| `lanes<s>` | 0 | 1 | `lane_list` | Source lane-list argument. |
| `m` | 30 | 70 | `mask` | Logical mask value. |
| `o` | 1 | 1 | `base` | Output-stream-like value. |
| `ptr` | 2 | 10 | `ptr` | Mutable pointer. |
| `s` | 13 | 13 | `base` | Runtime scalar value. |
| `sImm` | 0 | 21 | `base` | Compile-time scalar immediate; removed from runtime arguments. |
| `s[]` | 1 | 1 | `array` | Borrowed scalar array. |
| `usize` | 5 | 11 | `base` | Runtime size/index value. |
| `v` | 90 | 184 | `register`, or `base` when the register is the base type | Ordinary vector/register value. |
| `vidx` | 0 | 9 | `index_register` | Integral index vector. |
| `void` | 9 | 0 | `base` | No result. |
| `vt` | 0 | 1 | `target_register` | Caller-selected target vector type. |

The catalog also knows `ptr+`, but no current primitive declaration uses it.
It is therefore outside this observed matrix.

## Complete Authored Signature Matrix

This table contains all 64 exact signature spellings in the corpus. The count
is the number of declarations using the spelling, including masked and
attribute variants.

| Signature | Count | Primitive names |
|---|---:|---|
| `im:=(im,im,usize)` | 1 | `overlay_imask` |
| `im:=(im,usize)` | 5 | `extract_imask`, `shift_left_imask`, `shift_right_imask`, `test_imask` |
| `im:=(imt,im,usize)` | 2 | `insert_imask` |
| `im:=m` | 1 | `to_integral` |
| `m:=()` | 2 | `mask_false`, `mask_true` |
| `m:=(m,m)` | 3 | `mask_binary_and`, `mask_binary_or`, `mask_binary_xor` |
| `m:=(m,v)` | 1 | `conflict_free` |
| `m:=(m,v,v)` | 6 | `equal`, `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`, `nequal` |
| `m:=(m,v,v,v)` | 4 | `between_exclusive`, `between_inclusive`, `between_left_inclusive`, `between_right_inclusive` |
| `m:=(v,v)` | 6 | `equal`, `greater_than`, `greater_than_or_equal`, `less_than`, `less_than_or_equal`, `nequal` |
| `m:=(v,v,v)` | 4 | `between_exclusive`, `between_inclusive`, `between_left_inclusive`, `between_right_inclusive` |
| `m:=cptr` | 1 | `load_mask_repr` |
| `m:=im` | 1 | `to_mask` |
| `m:=m` | 1 | `mask_binary_not` |
| `m:=v` | 1 | `unequal_zero` |
| `o:=(o,v,s)` | 1 | `to_ostream` |
| `ptr:=(usize)` | 1 | `allocate` |
| `ptr:=(usize,usize)` | 1 | `allocate_aligned` |
| `s:=(m,v)` | 5 | `hadd`, `hand`, `hmax`, `hmin`, `hor` |
| `s:=(v,s)` | 1 | `count_matches` |
| `s:=cptr` | 1 | `load_scalar` |
| `s:=v` | 5 | `hadd`, `hand`, `hmax`, `hmin`, `hor` |
| `s:=v[idx]` | 1 | `extract_value` |
| `s[]:=v` | 1 | `to_array` |
| `usize:=(ptr)` | 1 | `random_step` |
| `usize:=m` | 3 | `lzc_imask`, `mask_population_count`, `tzc` |
| `usize:=s` | 1 | `lzc_scalar` |
| `v:=()` | 3 | `sequence`, `set_undef`, `set_zero` |
| `v:=(cptr,cptr,sImm)` | 1 | `gather_narrow` |
| `v:=(cptr,vidx,sImm)` | 2 | `gather`, `gather_narrow_partial` |
| `v:=(lanes<s>)` | 1 | `set` |
| `v:=(m,cptr)` | 2 | `expand_load`, `load` |
| `v:=(m,cptr,v)` | 1 | `load` |
| `v:=(m,cptr,vidx,v,sImm)` | 1 | `gather` |
| `v:=(m,v)` | 4 | `compress`, `inv`, `mov` |
| `v:=(m,v,s)` | 1 | `masked_set1` |
| `v:=(m,v,sImm)` | 5 | `mod_imm`, `mul_imm`, `shift_left` |
| `v:=(m,v,v)` | 21 | `add`, `binary_and`, `binary_andnot`, `binary_or`, `binary_xor`, `blend`, `div`, `expand`, `mod`, `mov`, `mul`, `sub` |
| `v:=(m,v,v,v)` | 1 | `blend_add` |
| `v:=(m,v,v,vidx)` | 1 | `permute_lanes` |
| `v:=(m,v,vidx)` | 1 | `permute_lanes` |
| `v:=(s,s)` | 1 | `custom_sequence` |
| `v:=(v)` | 1 | `abs` |
| `v:=(v,s)` | 3 | `insert_value`, `shift_left`, `shift_right` |
| `v:=(v,sImm)` | 8 | `convert_down`, `convert_up`, `extract`, `mod_imm`, `mul_imm`, `permute_lanes`, `shift_left`, `shift_right` |
| `v:=(v,v)` | 14 | `add`, `binary_and`, `binary_andnot`, `binary_or`, `binary_xor`, `concat`, `div`, `max`, `min`, `mod`, `mul`, `shift_left`, `shift_right`, `sub` |
| `v:=(v,v,sImm)` | 1 | `align_right_lanes` |
| `v:=(v,vidx)` | 1 | `permute_lanes` |
| `v:=(v,vidx,v)` | 1 | `table_lookup` |
| `v:=(vt,v,sImm)` | 1 | `insert` |
| `v:=cptr` | 1 | `load` |
| `v:=cptr+` | 1 | `load_convert_up` |
| `v:=m` | 1 | `to_vector` |
| `v:=s` | 1 | `set1` |
| `v:=s[]` | 1 | `from_array` |
| `v:=v` | 9 | `cast`, `conflict`, `inv`, `lzc`, `popcnt`, `reinterpret`, `resize_down`, `resize_up_undef`, `resize_up_zero` |
| `void:=(m,ptr,v)` | 2 | `compress_store`, `store` |
| `void:=(m,ptr,vidx,v,sImm)` | 1 | `scatter` |
| `void:=(ptr)` | 1 | `deallocate` |
| `void:=(ptr,cptr,s,s)` | 1 | `memory_cp` |
| `void:=(ptr,m)` | 1 | `store_mask_repr` |
| `void:=(ptr,s)` | 1 | `store` |
| `void:=(ptr,v)` | 1 | `store` |
| `void:=(ptr,vidx,v,sImm)` | 1 | `scatter` |

## Complete Same-Name Overload Matrix

Exactly 37 names have multiple authored declarations. The table groups names
only when their declaration matrices are identical. It accounts for all 93
declarations belonging to those names; the other 67 declarations have unique
names.

| Primitive names | Ordinary/base forms | Active-mask form without policy | `mask=zero` | `mask=pass_through` | Other axis |
|---|---|---|---|---|---|
| `add`, `binary_and`, `binary_andnot`, `binary_or`, `binary_xor`, `div`, `mod`, `mul`, `sub` | `v:=(v,v)` | — | `v:=(m,v,v)` | `v:=(m,v,v)` | — |
| `mod_imm`, `mul_imm` | `v:=(v,sImm)` | — | `v:=(m,v,sImm)` | `v:=(m,v,sImm)` | Immediate binding. |
| `inv` | `v:=v` | — | `v:=(m,v)` | `v:=(m,v)` | — |
| `equal`, `nequal`, `less_than`, `less_than_or_equal`, `greater_than`, `greater_than_or_equal` | `m:=(v,v)` | — | `m:=(m,v,v)` | — | Mask result. |
| `between_exclusive`, `between_inclusive`, `between_left_inclusive`, `between_right_inclusive` | `m:=(v,v,v)` | — | `m:=(m,v,v,v)` | — | Mask result. |
| `hadd`, `hand`, `hmax`, `hmin`, `hor` | `s:=v` | `s:=(m,v)` | — | — | Mask selects active reduction lanes but has no `mask` policy attribute. |
| `gather` | `v:=(cptr,vidx,sImm)` | — | — | `v:=(m,cptr,vidx,v,sImm)` | Per-lane indices, immediate scale, explicit pass-through source. |
| `scatter` | `void:=(ptr,vidx,v,sImm)` | — | `void:=(m,ptr,vidx,v,sImm)` | — | Per-lane indices and immediate scale; inactive lanes do not write. |
| `load` | `v:=cptr` | — | `v:=(m,cptr)` | `v:=(m,cptr,v)` | Every form also has `aligned=*`. |
| `store` | `void:=(ptr,v)` and `void:=(ptr,s)` | — | — | `void:=(m,ptr,v)` | Every form has `aligned=*`; payload extent varies between full vector and one scalar. |
| `mov` | — | — | `v:=(m,v)` with `op=keep` | `v:=(m,v,v)` | No ordinary unmasked declaration. |
| `permute_lanes` | `v:=(v,sImm)` and `v:=(v,vidx)` | — | `v:=(m,v,vidx)` | `v:=(m,v,v,vidx)` | Immediate encoded control versus runtime index vector. |
| `shift_left` | `v:=(v,sImm)`, `v:=(v,s)`, and `v:=(v,v)` | — | — | `v:=(m,v,sImm)` | Uniform immediate, uniform runtime, and per-lane runtime counts. |
| `shift_right` | `v:=(v,sImm)`, `v:=(v,s)`, and `v:=(v,v)` | — | — | — | All forms additionally have the `PreserveSign` bool generic. |
| `extract_imask` | Two declarations of `im:=(im,usize)` | — | — | — | `return_type` is `base: ToBase` versus `extension: ToExtension`. |
| `insert_imask` | Two declarations of `im:=(imt,im,usize)` | — | — | — | `return_type` is `base: ToBase` versus `extension: ToExtension`. |

### Exact Duplicate Headers

Only two names repeat an identical header and parameter list:

- `extract_imask` at `tsldata/primitives/mask/special.tsl:246` and `:355`;
- `insert_imask` at `tsldata/primitives/mask/special.tsl:98` and `:208`.

They are not accidental duplicates. Their `return_type` blocks select different
target dimensions, so overload identity cannot be reduced to name, signature,
and header attributes alone.

## Semantic Forms Observed in Overloaded Families

The following sparse matrix captures semantic distinctions that matter when a
backend cannot use target-language overload resolution. The source snapshot
does not yet author `primary`; the last column records the agreed planned
status rather than a current corpus fact.

| Family | Binding | Runtime/source shape | Semantic distinction | Planned primary status |
|---|---|---|---|---|
| `shift_left`, `shift_right` | Immediate | `sImm` count | One compile-time count applies to all lanes. | Inherits primary `uniform`; `_imm` remains mandatory. |
| `shift_left`, `shift_right` | Runtime | `s` count | One runtime count applies to all lanes. | Primary `uniform` declaration. |
| `shift_left`, `shift_right` | Runtime | `v` count | Each lane supplies its corresponding count. | No. |
| `permute_lanes` | Immediate | `sImm` control | One integer encodes multiple two-bit selectors; this is not a uniform lane value. | Not an overload-axis participant; `_imm` distinguishes it. |
| `permute_lanes` | Runtime | `vidx` indexes | Every output lane obtains an index from the corresponding index lane. | Not an overload-axis participant. |
| `store` | Runtime | `v` payload | Writes the full vector lane sequence. | Primary `vector` declaration. |
| `store` | Runtime | `s` payload | Writes exactly one scalar value. | No. |
| `extract_imask`, `insert_imask` | Runtime | Same runtime parameters | The caller-selected result target changes either the base type or extension. | Not an overload-axis participant; `return_type` owns it. |

Mask policy composes with these forms rather than replacing them. For example,
the current corpus contains an immediate pass-through `shift_left`, indexed
zeroing and pass-through `permute_lanes` forms, and aligned mask-policy load and
store forms.

## Immediate-Operand Semantic Matrix

`sImm` determines binding time only. The 14 primitive names using it cover at
least the following semantic roles:

| Immediate role | Primitive names | Meaning |
|---|---|---|
| Uniform arithmetic operand | `mul_imm`, `mod_imm` | Factor or divisor applied lane-wise. |
| Uniform shift count | `shift_left`, `shift_right` | Same count for every lane. |
| Address scale | `gather`, `gather_narrow_partial`, `gather_narrow`, `scatter` | Scale used with runtime per-lane or pointer-provided indices. |
| Representation or part index | `extract`, `insert`, `convert_up`, `convert_down` | Selects a lane, part, or conversion result; not a uniform lane operand. |
| Lane-window offset | `align_right_lanes` | Selects a window from two concatenated vectors. |
| Encoded lane control | `permute_lanes` | Encodes several lane selectors in one immediate. |

Nine declarations provide an explicit `params` entry for their immediate;
other `sImm` declarations currently use the compiler defaults. Regardless of
that metadata coverage, the `sImm` signature kind already owns compile-time
binding and must not be duplicated by overload metadata.

## Runtime-Scalar Semantic Matrix

The two current same-name collisions involving `s` are only part of the scalar
semantic space:

| Scalar role | Examples |
|---|---|
| Uniform lane control | runtime `shift_left` and `shift_right` count |
| One-value memory payload | scalar `store` |
| Comparison value | `count_matches` |
| Inserted lane payload | `insert_value` |
| Broadcast payload | `set1`, `masked_set1` |
| Sequence parameters | `custom_sequence` start and step |
| Byte count or operation selector | `memory_cp` |
| Presentation modifier | `to_ostream` |

Consequently, `s` cannot generically mean `uniform`, just as `sImm` cannot
generically mean `uniform_immediate`. Any such semantic form must be
source-authored or validated from a stronger typed role.

## Mask-Operand Matrix

A leading `m` is not sufficient to infer a control-mask policy. The 17
declarations with a leading or sole `m` parameter but no `mask=...` attribute
are:

- active-lane reductions: `hadd`, `hand`, `hmax`, `hmin`, `hor`;
- mask-consuming analysis/conversion: `lzc_imask`, `tzc`, `to_integral`,
  `to_vector`, `mask_population_count`, `conflict_free`;
- mask algebra: `mask_binary_and`, `mask_binary_or`, `mask_binary_xor`,
  `mask_binary_not`;
- semantic pack/expand memory operations: `compress_store`, `expand_load`.

The 49 declarations with a `mask` policy divide into 28 zeroing forms and 21
pass-through forms after including combinations with `aligned` and `op`.
These existing policies remain the source of inactive-lane or inactive-write
semantics.

## Complete Attribute-Combination Matrix

Whitespace-normalized attribute combinations are listed below. Counts sum to
the 160 authored declarations.

| Attribute combination | Count |
|---|---:|
| none | 90 |
| `[aligned=*]` | 3 |
| `[aligned=*, mask=zero]` | 1 |
| `[aligned=*, mask=pass_through]` | 2 |
| `[aligned=*, packed=*]` | 2 |
| `[aligned=false]` | 1 |
| `[aligned=true, op=expand]` | 1 |
| `[aligned=true, op=pack]` | 1 |
| `[cast=convert]` | 1 |
| `[cast=convert, direction=down]` | 1 |
| `[cast=convert, direction=up]` | 1 |
| `[cast=reinterpret]` | 3 |
| `[mask=pass_through]` | 18 |
| `[mask=pass_through, op=expand]` | 1 |
| `[mask=zero]` | 25 |
| `[mask=zero, op=keep]` | 1 |
| `[mask=zero, op=pack]` | 1 |
| `[value=all]` | 1 |
| `[value=undef]` | 2 |
| `[value=zero]` | 4 |

The observed attribute vocabulary is:

- `aligned`: `true`, `false`, or wildcard `*`;
- `packed`: wildcard `*`;
- `cast`: `convert` or `reinterpret`;
- `direction`: `up` or `down`;
- `mask`: `zero` or `pass_through`;
- `op`: `keep`, `pack`, or `expand`;
- `value`: `all`, `undef`, or `zero`.

Ordinary header attributes participate in semantic selection and wildcard
expansion. A future overload descriptor should not be smuggled into this map as
an untyped `meta=(...)` tuple.

## Generic and Target-Type Axes

### Free generic parameters

| Kind | Parameter | Primitive declarations |
|---|---|---|
| `bool` | `PreserveSign` | All three `shift_right` forms and `shift_right_imask`. |
| `int` | `Index` | `extract_value`, `insert_value`. |
| `int` | `N` | Gather/scatter families. |
| `simd_type` | `IndicesType` | Gather/scatter families, indexed `permute_lanes` forms, `table_lookup`. |

These are parameters of one declaration, not additional same-name
declarations, but they contribute to the complete public call shape.

### Result target parameters

| Target dimension | Primitive declarations |
|---|---|
| Base type | `reinterpret`, `cast`, `convert_up`, `convert_down`, `load_convert_up`, and the base-target `insert_imask`/`extract_imask` declarations. |
| Extension | `extract`, `insert`, `resize_down`, `resize_up_undef`, `resize_up_zero`, `concat`, and the extension-target `insert_imask`/`extract_imask` declarations. |

The result target is another overload-identity dimension even when runtime
parameter shapes are identical.

## Schema Consequences

The observed matrix rules out this shape:

```text
prim<SHAPE>[meta=(primary, uniform, uniform_immediate, per_lane)]
```

Problems with that representation:

1. `primary` is orthogonal to semantic form.
2. Immediate binding is already owned by `sImm`.
3. A primitive can combine per-lane indices with a uniform immediate scale.
4. An immediate may be an index or encoded control rather than a uniform value.
5. Scalar and vector parameters can be payloads rather than lane-control forms.
6. Ordinary header attributes already have selection and wildcard behavior.
7. Result-target overloads are not distinguishable through parameter form.

## Agreed Overload Field

The source-owned `overload` block has exactly three keys:

| Key | Required | Valid values | Meaning |
|---|---|---|---|
| `axis` | Yes | A registered axis listed below | The semantic dimension on which same-name declarations differ. |
| `value` | Yes | A value registered for that exact axis | This declaration's position on the semantic dimension. |
| `primary` | No | `true` or `false`; default `false` | Marks the value that owns the unsuffixed non-overloading-facade name. |

No other key is valid. In particular, the block has no `form`, operand name,
binding-time, mask-policy, generic-parameter, result-target, or backend-spelling
key.

### Current registry

The initial registry is deliberately minimal and closed. It contains exactly
these four valid axis/value pairs:

| `axis` | Valid `value` | Intended declarations |
|---|---|---|
| `count_distribution` | `uniform` | A single shift count applies to every lane, whether runtime or `sImm`. |
| `count_distribution` | `per_lane` | Each vector lane supplies its corresponding shift count. |
| `payload_extent` | `vector` | A store writes one full vector payload. |
| `payload_extent` | `scalar` | A store writes exactly one scalar payload. |

Values are axis-dependent. For example, `count_distribution=scalar` and
`payload_extent=uniform` are invalid. Unknown axes and values are diagnosed;
they are not accepted as arbitrary identifiers. A future semantic distinction
requires an intentional source-registry addition with validation and tests.

### Field rules

- `axis` and `value` are both mandatory when an `overload` block is present.
- Every declaration participating in one of these semantic axes declares the
  same registered axis and its applicable value, including immediate and
  masked variants.
- Within one primitive name and axis, exactly one value is primary. One
  declaration carrying that value writes `primary true`; the compiler promotes
  primary status to the value, so sibling immediate or masked declarations
  with the same value do not repeat it.
- `primary` omitted means `false`.
- Exactly one declaration per primitive name and axis writes `primary true`;
  duplicate markers are invalid even when they name the same value.
- Existing typed facts compose with the overload axis. They are never copied
  into the block.

The complete annotations required by the current corpus are therefore:

```text
prim<v:=(v,s)> shift_left(data, shift):
  overload:
    axis count_distribution
    value uniform
    primary true

prim<v:=(v,sImm)> shift_left(data, shift):
  overload:
    axis count_distribution
    value uniform

prim<v:=(m,v,sImm)>[mask=pass_through] shift_left(mask, data, shift):
  overload:
    axis count_distribution
    value uniform

prim<v:=(v,v)> shift_left(data, shift):
  overload:
    axis count_distribution
    value per_lane
```

`shift_right` uses the same `count_distribution` values. Its three declarations
retain their existing `PreserveSign` generic parameter independently.

```text
prim<void:=(ptr,v)>[aligned=*] store(ptr, data):
  overload:
    axis payload_extent
    value vector
    primary true

prim<void:=(m,ptr,v)>[aligned=*,mask=pass_through] store(mask, ptr, data):
  overload:
    axis payload_extent
    value vector

prim<void:=(ptr,s)>[aligned=*] store(ptr, scalar):
  overload:
    axis payload_extent
    value scalar
```

No other current primitive family requires an overload block:

- immediate binding remains derived from `sImm`;
- zeroing and pass-through forms remain derived from `mask`;
- `permute_lanes` is already distinguished by `sImm` versus `vidx` together
  with the mandatory immediate suffix;
- base-target and extension-target results remain owned by `return_type`;
- active-lane reductions require a separate mask-role decision rather than an
  overload value.

The following are explicitly invalid as `axis` or `value` entries:

- `uniform_immediate` or `immediate`;
- `masked`, `zero`, or `pass_through`;
- `base_target` or `extension_target`;
- `encoded_control` or `indices` under the current minimal registry.

## Required Validation for an Implemented Schema

Any implemented overload specification should provide source-located,
deterministic diagnostics for at least these invariants:

- `axis` and `value` must be a registered pair and no unknown block key is
  accepted;
- exactly one primary value exists for each participating primitive name and
  axis;
- no duplicate overload value, binding-time, mask-policy, generic-axis, and
  result-target identity;
- `count_distribution=uniform` agrees with a scalar or `sImm` count and
  `count_distribution=per_lane` agrees with a vector count;
- `payload_extent=vector` agrees with a vector payload and
  `payload_extent=scalar` agrees with a scalar payload;
- mask-policy suffixes come only from `mask`, not from parameter position;
- result-target duplicates remain distinguishable;
- adding a registered axis or value does not require a primitive-name branch
  in either backend;
- authoring diagnostics, hover, completion, documentation, and facade planning
  consume the same typed owner.

Focused schema tests should cover `shift_left`, `permute_lanes`, `store`, one
masked arithmetic family, one active-mask reduction, and the duplicate-header
`extract_imask`/`insert_imask` result-target families. Corpus validation should
then prove that all 160 authored declarations remain representable.

## Open Decisions

- The exact source syntax and location of the source-owned axis/value registry.
- The general Rust spelling for `per_lane` (`_per_lane` versus `_each`).
- Name-composition order when an overload value, `_imm`, `_masked`, and `_masked_zero`
  distinctions occur together.
- How base-target and extension-target declarations with identical runtime
  parameters should be presented by Rust.
- How active-lane mask operations are represented in source data; this remains
  separate from the overload registry.

## Decision Log

- 2026-07-21: Agreed that `overload` has exactly `axis`, `value`, and optional
  `primary` keys. The initial source-owned registry is closed to
  `count_distribution={uniform, per_lane}` and
  `payload_extent={vector, scalar}`. Immediate binding, mask policy, generic
  parameters, and result-target dimensions remain with their existing typed
  owners and are invalid as overload metadata.
