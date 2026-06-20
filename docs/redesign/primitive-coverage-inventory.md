# Primitive Coverage Inventory

Generated 2026-06-19 by `tslc/tools/coverage_inventory.py`. **Regenerate** with
`python tslc/tools/coverage_inventory.py`; do not hand-edit (it rewrites this file).

## Summary

- **89 distinct primitives** in `tsldata/`.
- **84 build-verified** (compile in C++ *and* Rust via `tslc/tests/test_build_verify.py`).
- **0 lower cleanly but are not build-verified** (codegen succeeds, 0 skips; compilation unconfirmed).
- **0 partial** (emit for some extension/type slots, skip others).
- **5 emit nothing** under the probed profiles.
- **51414 / 58586 (profile×backend×ext×type) slots lower**; **0 errors**.
- **C++/Rust parity is exact**: every primitive emits the identical extension set for both backends.

Status legend: **VERIFIED** = has a passing build test; **lowers** = codegen clean, 0 skips, no build test; **partial** = some slots lower, some skip; **NONE** = nothing emitted.

> Caveat: "lowers" means the generator produced C++/Rust text without diagnostics — it is *not* a compile guarantee. Only **VERIFIED** primitives are confirmed to compile. The probe uses the 10 arith type tags (si/ui 8-64, f32/f64) across profiles `scalar, sse2, avx, avx2, skylake, icelake-rockerlake`.

## Tiers

### Build-verified (84) — compile in C++ & Rust

`add`, `between_exclusive`, `between_inclusive`, `between_left_inclusive`, `between_right_inclusive`, `binary_and`, `binary_andnot`, `binary_or`, `binary_xor`, `blend`, `blend_add`, `cast`, `compress`, `compress_store`, `conflict`, `conflict_free`, `convert_down`, `convert_up`, `count_matches`, `custom_sequence`, `div`, `equal`, `expand_load`, `extract`, `extract_imask`, `extract_value`, `from_array`, `gather`, `greater_than`, `greater_than_or_equal`, `hadd`, `hand`, `hmax`, `hmin`, `hor`, `insert`, `insert_imask`, `inv`, `less_than`, `less_than_or_equal`, `load`, `load_convert_up`, `load_mask`, `load_scalar`, `lzc`, `lzc_imask`, `lzc_scalar`, `mask_binary_and`, `mask_binary_not`, `mask_binary_or`, `mask_binary_xor`, `mask_false`, `mask_population_count`, `mask_true`, `masked_set1`, `max`, `memory_cp`, `min`, `mod`, `mod_imm`, `mov`, `mul`, `mul_imm`, `nequal`, `popcnt`, `reinterpret`, `scatter`, `sequence`, `set1`, `set_undef`, `set_zero`, `shift_left`, `shift_right`, `shift_right_imask`, `store`, `store_mask`, `sub`, `test_imask`, `to_array`, `to_integral`, `to_mask`, `to_vector`, `tzc`, `unequal_zero`

### Lower but not build-verified (0) — codegen clean, compilation unconfirmed



### Partial (0) — some slots lower, some skip



### Emit nothing (5)

`allocate`, `allocate_aligned`, `deallocate`, `set`, `to_ostream`

## Per-primitive table

| primitive | signatures | status | extensions (cpp=rust) | skipped slots | dominant gap |
|---|---|---|---|--:|---|
| `add` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `allocate` | `ptr:=(s)` | NONE | — | 0 | — |
| `allocate_aligned` | `ptr:=(s,s)` | NONE | — | 0 | — |
| `between_exclusive` | `m:=(m,v,v,v)` `m:=(v,v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `between_inclusive` | `m:=(m,v,v,v)` `m:=(v,v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `between_left_inclusive` | `m:=(m,v,v,v)` `m:=(v,v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `between_right_inclusive` | `m:=(m,v,v,v)` `m:=(v,v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `binary_and` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 8 | pruned (closure) |
| `binary_andnot` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `binary_or` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 8 | pruned (closure) |
| `binary_xor` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 8 | pruned (closure) |
| `blend` | `v:=(m,v,v)` | VERIFIED | avx2/avx512/scalar/sse | 0 | — |
| `blend_add` | `v:=(m,v,v,v)` | VERIFIED | avx2/avx512/scalar/sse | 0 | — |
| `cast` | `v:=v` | VERIFIED | avx2/avx512/scalar/sse | 1500 | generic-vector repr-change (deferred) |
| `compress` | `v:=(m,v)` | VERIFIED | avx2/avx512/sse | 140 | no top-level emit_return |
| `compress_store` | `void:=(m,ptr,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `conflict` | `v:=v` | VERIFIED | avx2/avx512/scalar/sse | 208 | unresolved value query |
| `conflict_free` | `m:=(m,v)` | VERIFIED | avx2/avx512/scalar/sse | 208 | pruned (closure) |
| `convert_down` | `v:=(v,sImm)` | VERIFIED | avx2/avx512/sse | 24 | call type-args (bare-ext/index) |
| `convert_up` | `v:=(v,sImm)` | VERIFIED | avx2/avx512/sse | 0 | — |
| `count_matches` | `s:=(v,s)` | VERIFIED | avx2/avx512/generic/scalar/sse | 4 | pruned (closure) |
| `custom_sequence` | `v:=(s,s)` | VERIFIED | avx2/avx512/generic/scalar/sse | 24 | pruned (closure) |
| `deallocate` | `void:=(ptr)` | NONE | — | 0 | — |
| `div` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `equal` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `expand_load` | `v:=(m,ptr)` | VERIFIED | avx2/avx512/generic/scalar/sse | 4 | pruned (closure) |
| `extract` | `v:=(v,sImm)` | VERIFIED | avx2/avx512/scalar | 0 | — |
| `extract_imask` | `im:=(im,im)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `extract_value` | `s:=v[idx]` | VERIFIED | avx2/avx512/generic/scalar/sse | 8 | pruned (closure) |
| `from_array` | `v:=s[]` | VERIFIED | avx2/avx512/generic/scalar/sse | 16 | pruned (closure) |
| `gather` | `v:=(m,ptr,vidx,v,sImm)` `v:=(ptr,vidx,sImm)` | VERIFIED | avx2/avx512/generic/scalar/sse | 12 | pruned (closure) |
| `greater_than` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `greater_than_or_equal` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `hadd` | `s:=(m,v)` `s:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `hand` | `s:=(m,v)` `s:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 88 | unresolved type query |
| `hmax` | `s:=(m,v)` `s:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `hmin` | `s:=(m,v)` `s:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `hor` | `s:=(m,v)` `s:=v` | VERIFIED | avx2/avx512/sse | 8 | unresolved type query |
| `insert` | `v:=(vt,v,sImm)` | VERIFIED | avx2/sse | 0 | — |
| `insert_imask` | `im:=(im,im,im)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `inv` | `v:=(m,v)` `v:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 16 | pruned (closure) |
| `less_than` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `less_than_or_equal` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `load` | `v:=(m,ptr)` `v:=(m,ptr,v)` `v:=ptr` | VERIFIED | avx2/avx512/generic/scalar/sse | 96 | pruned (closure) |
| `load_convert_up` | `v:=ptr+` | VERIFIED | avx2/avx512 | 4 | pruned (closure) |
| `load_mask` | `m:=ptr` | VERIFIED | avx2/avx512/scalar/sse | 644 | pruned (closure) |
| `load_scalar` | `s:=ptr` | VERIFIED | avx2/avx512/generic/sse | 0 | — |
| `lzc` | `v:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 100 | pruned (closure) |
| `lzc_imask` | `s:=m` | VERIFIED | avx2/avx512/scalar/sse | 128 | pruned (closure) |
| `lzc_scalar` | `s:=s` | VERIFIED | generic/scalar | 48 | unresolved type query |
| `mask_binary_and` | `m:=(m,m)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `mask_binary_not` | `m:=m` | VERIFIED | avx2/avx512/generic/scalar/sse | 40 | pruned (closure) |
| `mask_binary_or` | `m:=(m,m)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `mask_binary_xor` | `m:=(m,m)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `mask_false` | `m:=()` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `mask_population_count` | `usize:=m` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `mask_true` | `m:=()` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `masked_set1` | `v:=(m,v,s)` | VERIFIED | avx2/avx512/scalar/sse | 12 | pruned (closure) |
| `max` | `v:=(v,v)` | VERIFIED | avx2/avx512/scalar/sse | 124 | pruned (closure) |
| `memory_cp` | `void:=(ptr,ptr,s,s)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `min` | `v:=(v,v)` | VERIFIED | avx2/avx512/scalar/sse | 124 | pruned (closure) |
| `mod` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 88 | pruned (closure) |
| `mod_imm` | `v:=(m,v,sImm)` `v:=(v,sImm)` | VERIFIED | avx2/avx512/generic/scalar/sse | 88 | pruned (closure) |
| `mov` | `v:=(m,v)` `v:=(m,v,v)` | VERIFIED | avx2/avx512/scalar/sse | 0 | — |
| `mul` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 40 | pruned (closure) |
| `mul_imm` | `v:=(m,v,sImm)` `v:=(v,sImm)` | VERIFIED | avx2/avx512/generic/scalar/sse | 40 | pruned (closure) |
| `nequal` | `m:=(m,v,v)` `m:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `popcnt` | `v:=v` | VERIFIED | avx2/avx512/sse | 304 | unresolved type query |
| `reinterpret` | `v:=v` | VERIFIED | avx2/avx512/scalar/sse | 532 | generic-vector repr-change (deferred) |
| `scatter` | `void:=(m,ptr,vidx,v,sImm)` `void:=(ptr,vidx,v,sImm)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `sequence` | `v:=()` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `set` | `v:=s...` | NONE | — | 460 | unsupported signature kind v:=s... |
| `set1` | `v:=s` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `set_undef` | `v:=()` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `set_zero` | `v:=()` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `shift_left` | `v:=(m,v,sImm)` `v:=(v,s)` `v:=(v,sImm)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 104 | pruned (closure) |
| `shift_right` | `v:=(v,s)` `v:=(v,sImm)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 72 | pruned (closure) |
| `shift_right_imask` | `im:=(im,s)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `store` | `void:=(m,ptr,v)` `void:=(ptr,s)` `void:=(ptr,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 8 | pruned (closure) |
| `store_mask` | `void:=(ptr,m)` | VERIFIED | avx2/avx512/scalar/sse | 1120 | unresolved type query |
| `sub` | `v:=(m,v,v)` `v:=(v,v)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `test_imask` | `im:=(im,im)` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `to_array` | `s[]:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `to_integral` | `im:=m` | VERIFIED | avx2/avx512/scalar/sse | 120 | unresolved value query |
| `to_mask` | `m:=im` | VERIFIED | avx2/avx512/scalar/sse | 120 | unresolved value query |
| `to_ostream` | `o:=(o,v,s)` | NONE | — | 340 | unsupported signature kind o:=(o,v,s) |
| `to_vector` | `v:=m` | VERIFIED | avx2/avx512/generic/scalar/sse | 0 | — |
| `tzc` | `s:=m` | VERIFIED | avx2/avx512/scalar/sse | 128 | pruned (closure) |
| `unequal_zero` | `m:=v` | VERIFIED | avx2/avx512/generic/scalar/sse | 4 | pruned (closure) |

## Skip-reason taxonomy (what blocks the gaps)

| skips | category | meaning / action |
|--:|---|---|
| 2452 | pruned (closure) | Dependency-closure dropped a body whose callee is unavailable in that profile. **Structural, not a defect** — expected behavior. |
| 1512 | generic-vector repr-change (deferred) | `cast`/`reinterpret` on the `simd<T, generic<LANES>>` vector (LANES-sized target). Known deferred slice. |
| 1128 | unresolved type query | A `type<generation>(...)` query is not yet evaluated (e.g. `vector::offset_base`, `vector::mask_underlying_t`, `vector::transform(...)`). Blocks compress/expand/conflict/popcnt/lzc/hand/hor/store_mask generic paths. |
| 498 | unresolved value query | A `value<generation>(...)` / `value<backend>(...)` query unevaluated (e.g. `type::size_bytes(...)`, `x86::mm_fround_to_zero`). Blocks to_integral/to_mask generic + div/mod float rounding. |
| 460 | unsupported signature kind v:=s... | Unsupported signature kind: variadic `set` (`v:=s...`) and `to_ostream` (`o:=(o,v,s)`). |
| 398 | no top-level emit_return | Body has no top-level `emit_return(...)` (where:-clause / switch-bodied forms) — not lowerable yet (reinterpret, compress, cast). |
| 340 | unsupported signature kind o:=(o,v,s) | Unsupported signature kind: variadic `set` (`v:=s...`) and `to_ostream` (`o:=(o,v,s)`). |
| 216 | call type-args (bare-ext/index) | `call<primitive=extract[Vec, sse, 0]>` style: a bare extension + literal index in call type-args not yet supported. |
| 152 | unresolved pointer-cast type | `cast<reinterpret>` to a `vector::mask_underlying_t` pointer not resolved. |
| 16 | unsupported mask<test> | `mask<test>` on the `native_predicate_by_lanes` (avx512 `__mmaskN`) representation. |

### NONE primitives — why nothing emits

- `allocate`, `allocate_aligned`, `deallocate`: host memory helpers with no vector (`v`) axis (`ptr:=(s)` etc.), so the per-type selector produces no slots. Not a lowering defect; needs a non-vector codegen path if wanted.
- `lzc_scalar` (`s:=s`): attempted but every slot blocked by an unresolved type query.
- `set` (`v:=s...`): variadic scalar-pack kind `s...` is an unsupported signature kind.
- `to_ostream` (`o:=(o,v,s)`): ostream kind `o` is an unsupported signature kind.
