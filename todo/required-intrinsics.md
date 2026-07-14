# Required Intrinsics Coverage Inventory

This file tracks whether each required Intel intrinsic already has an exact TSL
primitive mapping.

Status values:

- `covered`: an existing TSL primitive provides the same operation shape.
- `partial`: existing TSL primitives cover related semantics, but not the exact
  Intel intrinsic shape. Keep these in the implementation queue until verified
  or completed.
- `missing`: add a primitive or extend an existing primitive family.

Reviewed against the current `tsldata/primitives/` corpus and the Intel
Intrinsics Guide. Any intrinsic in the source list below that is not named in
`Partial coverage` or `Missing coverage` is currently treated as `covered`.

## Covered mapping

These required intrinsics already map to existing TSL primitive semantics.

- `add`: `_mm512_add_epi32`, `_mm512_add_epi64`, `_mm512_add_pd`,
  `_mm512_add_ps`.
- `sub`: `_mm512_sub_epi32`, `_mm512_sub_epi64`, `_mm512_sub_pd`,
  `_mm512_sub_ps`.
- `mul`: `_mm512_mul_pd`, `_mm512_mul_ps`, `_mm512_mullo_epi32`.
- `div`: `_mm512_div_pd`, `_mm512_div_ps`.
- `min`: `_mm512_min_epi64`, `_mm512_min_pd`, `_mm512_min_ps`.
- `max`: `_mm512_max_epi64`, `_mm512_max_pd`, `_mm512_max_ps`.
- `binary_and`: `_mm512_and_epi32`, `_mm512_and_epi64`,
  `_mm512_and_si512`.
- `binary_andnot`: `_mm512_andnot_si512`.
- `binary_or`: `_mm512_or_epi32`, `_mm512_or_si512`.
- `binary_xor`: `_mm512_xor_epi32`, `_mm512_xor_epi64`.
- `equal`: `_mm256_cmpeq_epi32`, `_mm512_cmpeq_epi32_mask`,
  `_mm512_cmpeq_epi64_mask`.
- `nequal`: `_mm512_cmpneq_epi32_mask`, `_mm512_cmpneq_epi64_mask`.
- `less_than`: `_mm512_cmplt_epi32_mask`, `_mm512_cmplt_epi64_mask`.
- `greater_than`: `_mm512_cmpgt_epi32_mask`, `_mm512_cmpgt_epi64_mask`.
- `less_than_or_equal`: `_mm512_cmple_epi32_mask`,
  `_mm512_cmple_epi64_mask`.
- `greater_than_or_equal`: `_mm512_cmpge_epi32_mask`,
  `_mm512_cmpge_epi64_mask`.
- `equal[mask=zero]`: `_mm512_mask_cmpeq_epi32_mask`,
  `_mm512_mask_cmpeq_epi64_mask`.
- `nequal[mask=zero]`: `_mm512_mask_cmpneq_epi32_mask`.
- `less_than[mask=zero]`: `_mm512_mask_cmplt_epi32_mask`.
- `greater_than[mask=zero]`: `_mm512_mask_cmpgt_epi32_mask`.
- `greater_than_or_equal[mask=zero]`: `_mm512_mask_cmpge_epi64_mask`.
- `conflict`: `_mm512_conflict_epi32`.
- `extract`: `_mm256_castsi256_si128`, `_mm512_castsi512_si128`,
  `_mm512_castsi512_si256`.
- `reinterpret`: `_mm512_castpd_si512`, `_mm512_castps_si512`,
  `_mm512_castsi512_pd`, `_mm512_castsi512_ps`.
- `cast` / `convert_up`: `_mm256_cvtepu8_epi16`,
  `_mm512_cvtepi16_epi32`, `_mm512_cvtepi16_epi64`,
  `_mm512_cvtepi32_epi64`, `_mm512_cvtepi8_epi32`,
  `_mm512_cvtepi8_epi64`, `_mm512_cvtepu16_epi32`,
  `_mm512_cvtepu8_epi32`.
- `extract_value`: `_mm512_cvtsd_f64`, `_mm512_cvtss_f32`,
  `_mm_cvtsi128_si32`, `_mm_cvtsi128_si64`.
- `load`: `_mm256_load_si256`, `_mm256_loadu_si256`,
  `_mm512_load_epi32`, `_mm512_load_epi64`, `_mm512_load_pd`,
  `_mm512_load_ps`, `_mm512_load_si512`, `_mm512_loadu_si512`,
  `_mm_load_si128`, `_mm_loadu_si128`.
- `load[mask=pass_through]`: `_mm512_mask_loadu_epi32`.
- `store`: `_mm512_store_epi32`, `_mm512_store_epi64`,
  `_mm512_store_pd`, `_mm512_store_ps`, `_mm512_store_si512`,
  `_mm512_storeu_si512`, `_mm_store_si128`.
- `store[mask=pass_through]`: `_mm512_mask_storeu_epi32`.
- `set_zero`: `_mm512_setzero_pd`, `_mm512_setzero_ps`,
  `_mm512_setzero_si512`.
- `set_undef`: `_mm256_undefined_si256`, `_mm512_undefined_epi32`.
- `shift_left`: `_mm512_sll_epi32`, `_mm512_slli_epi32`,
  `_mm512_slli_epi64`, `_mm512_sllv_epi32`, `_mm512_sllv_epi64`.
- `shift_right`: `_mm512_srai_epi64`, `_mm512_srl_epi32`,
  `_mm512_srli_epi32`, `_mm512_srli_epi64`, `_mm512_srlv_epi32`,
  `_mm512_srlv_epi64`.
- `lzc`: `_mm512_lzcnt_epi32`, `_mm512_lzcnt_epi64`.
- `lzc_scalar`: `_lzcnt_u64`.
- `popcnt`: `_mm_popcnt_u32`, `_mm_popcnt_u64`.
- `to_integral`: `_mm512_mask2int`.
- `mov[mask=pass_through]`: `_mm512_mask_mov_epi32`.
- `blend`: `_mm512_mask_blend_epi32`.
- `compress_store`: `_mm512_mask_compressstoreu_epi32`.
- `gather`: `_mm512_i32gather_epi32`, `_mm512_i32gather_ps`,
  `_mm512_i64gather_epi64`.
- `gather[mask=pass_through]`: `_mm512_mask_i32gather_epi32`,
  `_mm512_mask_i64gather_epi64`.
- `scatter`: `_mm512_i32scatter_epi32`, `_mm512_i32scatter_ps`,
  `_mm512_i64scatter_epi64`.
- `scatter[mask=zero]`: `_mm512_mask_i32scatter_ps`.

## Partial coverage

These are close enough to have existing TSL vocabulary, but should not be
counted complete until the exact Intel operation shape is verified or added.

- `_mm_broadcast_ss`: related to `set1`; add/verify exact memory or low-lane
  broadcast shape.
- `_mm256_broadcast_sd`: related to `set1`; add/verify exact memory or low-lane
  broadcast shape.
- `_mm_broadcastb_epi8`: related to `set1`; add/verify exact byte broadcast from
  vector source.
- `_mm_broadcastw_epi16`: related to `set1`; add/verify exact word broadcast
  from vector source.
- `_mm512_broadcast_f32x4`: add/verify exact 128-bit `f32x4` chunk broadcast.
- `_mm512_broadcast_f64x4`: add/verify exact 256-bit `f64x4` chunk broadcast.
- `_mm512_broadcastd_epi32`: add/verify exact dword broadcast from vector source.
- `_mm512_broadcastq_epi64`: add/verify exact qword broadcast from vector source.
- `_mm512_castsi128_si512`: can compose `set_undef` + `insert`; add exact
  one-argument cast-with-undefined-upper mapping.
- `_mm512_castsi256_si512`: can compose `set_undef` + `insert`; add exact
  one-argument cast-with-undefined-upper mapping.
- `_mm512_cmp_pd_mask`: named comparisons exist; add/verify exact
  immediate-predicate compare shape.
- `_mm512_cmp_ps_mask`: named comparisons exist; add/verify exact
  immediate-predicate compare shape.
- `_mm512_cvtepi32_epi16`: existing down-conversion paths need exact
  truncation-vs-saturation verification.
- `_mm512_cvtepi32_epi8`: existing down-conversion paths need exact
  truncation-vs-saturation verification.
- `_mm512_i32logather_epi64`: related narrow-index gather support exists;
  verify/add exact i32-index to 64-bit integer gather.
- `_mm512_i32logather_pd`: related narrow-index gather support exists;
  verify/add exact i32-index to `f64` gather.
- `_mm512_i32loscatter_epi64`: related scatter support exists; verify/add exact
  i32-index to 64-bit integer scatter.
- `_mm512_i32loscatter_pd`: related scatter support exists; verify/add exact
  i32-index to `f64` scatter.
- `_mm512_mask_add_epi32`: `add[mask=pass_through]` exists, but verify/add exact
  independent `src, k, a, b` shape.
- `_mm512_mask_and_epi64`: `binary_and[mask=pass_through]` exists, but
  verify/add exact independent `src, k, a, b` shape.
- `_mm512_mask_broadcastq_epi64`: add/verify exact masked qword broadcast from
  vector source.
- `_mm512_mask_cmp_pd_mask`: named masked comparisons exist; add/verify exact
  immediate-predicate compare shape.
- `_mm512_mask_compress_epi32`: `compress` exists with zero-fill semantics;
  verify/add exact masked compress shape.
- `_mm512_mask_expand_epi32`: `expand_load` exists; add/verify exact vector
  expand shape.
- `_mm512_mask_expandloadu_epi32`: `expand_load` exists; verify exact unaligned
  masked expand-load shape.
- `_mm512_mask_i32logather_epi64`: related narrow-index masked gather support
  exists; verify/add exact shape.
- `_mm512_mask_i32loscatter_epi64`: related scatter support exists; verify/add
  exact masked shape.
- `_mm512_mask_i32loscatter_pd`: related scatter support exists; verify/add exact
  masked shape.
- `_mm512_mask_or_epi64`: `binary_or[mask=pass_through]` exists, but verify/add
  exact independent `src, k, a, b` shape.
- `_mm512_mask_sub_epi32`: `sub[mask=pass_through]` exists, but verify/add exact
  independent `src, k, a, b` shape.
- `_mm_loadl_epi64`: `load`/partial-load behavior is related; verify exact
  upper-zero behavior before counting complete.
- `_mm_shuffle_epi32`: existing lane selection/shuffle use is related; verify
  exact immediate-controlled public primitive if needed.

## Missing coverage

These should become new primitives or focused extensions to existing primitive
families.

- `_mm256_testc_si256`: integer vector test-c/all-ones-after-andnot scalar result.
- `_mm256_testz_si256`: integer vector test-zero-after-and scalar result.
- `_mm256_permute4x64_epi64`: immediate-controlled 64-bit lane permute.
- `_mm256_stream_load_si256`: non-temporal aligned integer load.
- `_mm512_abs_epi64`: signed 64-bit lane absolute value.
- `_mm512_alignr_epi32`: immediate-controlled concatenated lane-align.
- `_mm512_alignr_epi64`: immediate-controlled concatenated lane-align.
- `_mm512_kand`: native mask bitwise AND.
- `_mm512_kandn`: native mask AND-NOT.
- `_mm512_knot`: native mask NOT.
- `_mm512_kor`: native mask OR.
- `_mm512_kortestz`: native mask OR-test-zero scalar result.
- `_mm512_kunpackb`: mask unpack/concatenate.
- `_mm512_kxnor`: native mask XNOR.
- `_mm512_mask_cvtepu8_epi32`: masked unsigned 8-bit to 32-bit widening
  conversion.
- `_mm512_mask_test_epi32_mask`: masked bit-test mask-return primitive.
- `_mm512_mask_testn_epi32_mask`: masked inverted bit-test mask-return primitive.
- `_mm512_mask_testn_epi64_mask`: masked inverted bit-test mask-return primitive.
- `_mm512_mul_epu32`: even-lane unsigned 32x32 to 64-bit multiply.
- `_mm512_permutex2var_epi32`: two-source indexed permute.
- `_mm512_permutexvar_epi32`: indexed permute.
- `_mm512_rol_epi32`: rotate-left immediate.
- `_mm512_ror_epi64`: rotate-right immediate.
- `_mm512_stream_load_si512`: non-temporal aligned integer load.
- `_mm512_stream_si512`: non-temporal aligned integer store.
- `_mm512_ternarylogic_epi32`: immediate-controlled ternary bitwise logic.
- `_mm512_ternarylogic_epi64`: immediate-controlled ternary bitwise logic.
- `_mm512_test_epi32_mask`: bit-test mask-return primitive.
- `_mm512_test_epi64_mask`: bit-test mask-return primitive.
- `_mm512_testn_epi32_mask`: inverted bit-test mask-return primitive.
- `__blsr_u64`: scalar reset-lowest-set-bit.
- `__tzcnt_u32`: scalar trailing-zero-count for 32-bit input.
- `__tzcnt_u64`: scalar trailing-zero-count for 64-bit input.
- `_rdrand64_step`: x86-only random/entropy primitive or explicit unsupported
  policy.
- `_mm_cvtsi32_si128`: scalar-to-low-lane vector constructor with zeroed upper
  bits.
- `_mm_cvtsi64_si128`: scalar-to-low-lane vector constructor with zeroed upper
  bits.
- `_mm_stream_si128`: non-temporal aligned integer store.
- `_mm_stream_si32`: non-temporal scalar 32-bit store.
- `_mm_stream_si64`: non-temporal scalar 64-bit store.
- `_mm_stream_load_si128`: non-temporal aligned integer load.

## Source list

[AVX]
_mm256_broadcast_sd
_mm256_castsi256_si128
_mm256_load_si256
_mm256_loadu_si256
_mm256_testc_si256
_mm256_testz_si256
_mm256_undefined_si256
_mm_broadcast_ss
[AVX2]
_mm256_cmpeq_epi32
_mm256_cvtepu8_epi16
_mm256_permute4x64_epi64
_mm256_stream_load_si256
_mm_broadcastb_epi8
_mm_broadcastw_epi16
[AVX512]
_mm512_abs_epi64
_mm512_add_epi32
_mm512_add_epi64
_mm512_add_pd
_mm512_add_ps
_mm512_alignr_epi32
_mm512_alignr_epi64
_mm512_and_epi32
_mm512_and_epi64
_mm512_and_si512
_mm512_andnot_si512
_mm512_broadcast_f32x4
_mm512_broadcast_f64x4
_mm512_broadcastd_epi32
_mm512_broadcastq_epi64
_mm512_castpd_si512
_mm512_castps_si512
_mm512_castsi128_si512
_mm512_castsi256_si512
_mm512_castsi512_pd
_mm512_castsi512_ps
_mm512_castsi512_si128
_mm512_castsi512_si256
_mm512_cmp_pd_mask
_mm512_cmp_ps_mask
_mm512_cmpeq_epi32_mask
_mm512_cmpeq_epi64_mask
_mm512_cmpge_epi32_mask
_mm512_cmpge_epi64_mask
_mm512_cmpgt_epi32_mask
_mm512_cmpgt_epi64_mask
_mm512_cmple_epi32_mask
_mm512_cmple_epi64_mask
_mm512_cmplt_epi32_mask
_mm512_cmplt_epi64_mask
_mm512_cmpneq_epi32_mask
_mm512_cmpneq_epi64_mask
_mm512_conflict_epi32
_mm512_cvtepi16_epi32
_mm512_cvtepi16_epi64
_mm512_cvtepi32_epi16
_mm512_cvtepi32_epi64
_mm512_cvtepi32_epi8
_mm512_cvtepi8_epi32
_mm512_cvtepi8_epi64
_mm512_cvtepu16_epi32
_mm512_cvtepu8_epi32
_mm512_cvtsd_f64
_mm512_cvtss_f32
_mm512_div_pd
_mm512_div_ps
_mm512_i32gather_epi32
_mm512_i32gather_ps
_mm512_i32logather_epi64
_mm512_i32logather_pd
_mm512_i32loscatter_epi64
_mm512_i32loscatter_pd
_mm512_i32scatter_epi32
_mm512_i32scatter_ps
_mm512_i64gather_epi64
_mm512_i64scatter_epi64
_mm512_kand
_mm512_kandn
_mm512_knot
_mm512_kor
_mm512_kortestz
_mm512_kunpackb
_mm512_kxnor
_mm512_load_epi32
_mm512_load_epi64
_mm512_load_pd
_mm512_load_ps
_mm512_load_si512
_mm512_loadu_si512
_mm512_lzcnt_epi32
_mm512_lzcnt_epi64
_mm512_mask2int
_mm512_mask_add_epi32
_mm512_mask_and_epi64
_mm512_mask_blend_epi32
_mm512_mask_broadcastq_epi64
_mm512_mask_cmp_pd_mask
_mm512_mask_cmpeq_epi32_mask
_mm512_mask_cmpeq_epi64_mask
_mm512_mask_cmpge_epi64_mask
_mm512_mask_cmpgt_epi32_mask
_mm512_mask_cmplt_epi32_mask
_mm512_mask_cmpneq_epi32_mask
_mm512_mask_compress_epi32
_mm512_mask_compressstoreu_epi32
_mm512_mask_cvtepu8_epi32
_mm512_mask_expand_epi32
_mm512_mask_expandloadu_epi32
_mm512_mask_i32gather_epi32
_mm512_mask_i32logather_epi64
_mm512_mask_i32loscatter_epi64
_mm512_mask_i32loscatter_pd
_mm512_mask_i32scatter_ps
_mm512_mask_i64gather_epi64
_mm512_mask_loadu_epi32
_mm512_mask_mov_epi32
_mm512_mask_or_epi64
_mm512_mask_storeu_epi32
_mm512_mask_sub_epi32
_mm512_mask_test_epi32_mask
_mm512_mask_testn_epi32_mask
_mm512_mask_testn_epi64_mask
_mm512_max_epi64
_mm512_max_pd
_mm512_max_ps
_mm512_min_epi64
_mm512_min_pd
_mm512_min_ps
_mm512_mul_epu32
_mm512_mul_pd
_mm512_mul_ps
_mm512_mullo_epi32
_mm512_or_epi32
_mm512_or_si512
_mm512_permutex2var_epi32
_mm512_permutexvar_epi32
_mm512_rol_epi32
_mm512_ror_epi64
_mm512_setzero_pd
_mm512_setzero_ps
_mm512_setzero_si512
_mm512_sll_epi32
_mm512_slli_epi32
_mm512_slli_epi64
_mm512_sllv_epi32
_mm512_sllv_epi64
_mm512_srai_epi64
_mm512_srl_epi32
_mm512_srli_epi32
_mm512_srli_epi64
_mm512_srlv_epi32
_mm512_srlv_epi64
_mm512_store_epi32
_mm512_store_epi64
_mm512_store_pd
_mm512_store_ps
_mm512_store_si512
_mm512_storeu_si512
_mm512_stream_load_si512
_mm512_stream_si512
_mm512_sub_epi32
_mm512_sub_epi64
_mm512_sub_pd
_mm512_sub_ps
_mm512_ternarylogic_epi32
_mm512_ternarylogic_epi64
_mm512_test_epi32_mask
_mm512_test_epi64_mask
_mm512_testn_epi32_mask
_mm512_undefined_epi32
_mm512_xor_epi32
_mm512_xor_epi64
[SSE]
__blsr_u64
__tzcnt_u32
__tzcnt_u64
_lzcnt_u64
_mm_popcnt_u32
_mm_popcnt_u64
_rdrand64_step
[SSE2]
_mm_cvtsi128_si32
_mm_cvtsi128_si64
_mm_cvtsi32_si128
_mm_cvtsi64_si128
_mm_load_si128
_mm_loadl_epi64
_mm_loadu_si128
_mm_shuffle_epi32
_mm_store_si128
_mm_stream_si128
_mm_stream_si32
_mm_stream_si64
[SSE4.1]
_mm_stream_load_si128
