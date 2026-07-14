# Required Intrinsics Implementation Plan

## Scope and audit method

This is a fresh inventory of the 191 intrinsics in
[`required-intrinsics.md`](required-intrinsics.md), reviewed against the current
public primitive contracts, authored semantics, implementation slots, and tests
under `tsldata/primitives/` on 2026-07-14.

The inventory uses these status rules:

- **Covered** means one current public TSL primitive has the required observable
  operation shape. The implementation may use a generated intrinsic name or a
  semantic primitive composition; the Intel spelling does not have to occur
  literally in the source body.
- **Partial** means the correct primitive family or close semantic building
  blocks exist, but the public signature, merge source, mask polarity, memory
  policy, result shape, or conversion behavior does not exactly match.
- **Missing** means the core operation has no public TSL primitive contract yet.
  A literal use of the intrinsic inside another primitive is not public
  coverage.

This produces **130 covered**, **61 partial**, and **0 missing** intrinsics. Each
source-list intrinsic occurs in exactly one inventory section below.

The exact Intel operand and result behavior was checked against the
[Intel Intrinsics Guide](https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html).
The source corpus remains the authority for whether TSL already exposes that
behavior.

## Material changes from the previous inventory

- The eight formerly missing spellings now have public contracts: `abs`,
  `align_right_lanes`, `permute_lanes4`, `permute_lanes`, `permute_lanes2`, and
  `random_step`.
- The arithmetic and swizzle contracts cover every vector extension and all ten
  datatypes through portable semantic implementations, with exact x86
  specializations where the Intel operation matches. `random_step` is the
  deliberate exception: it is x86-only, `ui64`-only, and feature-gated by
  `rdrand` because a portable entropy fallback would change the contract.
- Native mask AND, OR, and NOT are now covered by `mask_binary_and`,
  `mask_binary_or`, and `mask_binary_not`.
- The merge-source vector expand shape is now covered by the current
  three-input `expand` primitive.
- `compress_store` is not exact coverage for the required unaligned intrinsic:
  its only public contract is still `[aligned=true]`, even though its AVX-512
  body selects `mask_compressstoreu`.
- `convert_down` cannot cover the two required truncating conversions. Its
  authored contract and tests are saturating/clamping, while the required Intel
  operations discard high bits.
- `blend_add` does not cover `_mm512_mask_add_epi32`: its authored semantics,
  tests, and body keep `left` on active mask lanes and add on inactive lanes.
  The required intrinsic adds on active lanes and takes an independent `src`
  for inactive lanes.
- `tsldata/primitives/misc/swizzle.tsl` now contains public, target-independent
  lane-alignment and permutation primitives; the Intel spellings are
  implementation choices rather than API names.

## Public primitive naming decision

An x86 intrinsic should normally be represented by a normal TSL primitive when
it expresses a useful operation independent of x86. The public name therefore
describes the operation (`abs`, `permute_lanes`, and so on), while an intrinsic
such as `_mm512_permutexvar_epi32` is an exact specialization of that contract.
Publishing `_mm*` names as primitives would expose register widths, Intel type
spellings, and ISA-specific operand conventions in the cross-target API.

The exception is a genuinely target-specific capability. `_rdrand64_step` is
not an optimization of a deterministic portable operation, so `random_step`
has an x86-only feature-gated contract and no fabricated fallback.

## Covered inventory (130)

These required intrinsics already have an exact public semantic mapping in the
current corpus.

- `add`: `_mm512_add_epi32`, `_mm512_add_epi64`, `_mm512_add_pd`,
  `_mm512_add_ps`.
- `sub`: `_mm512_sub_epi32`, `_mm512_sub_epi64`, `_mm512_sub_pd`,
  `_mm512_sub_ps`.
- `mul`: `_mm512_mul_pd`, `_mm512_mul_ps`, `_mm512_mullo_epi32`.
- `div`: `_mm512_div_pd`, `_mm512_div_ps`.
- `min`: `_mm512_min_epi64`, `_mm512_min_pd`, `_mm512_min_ps`.
- `max`: `_mm512_max_epi64`, `_mm512_max_pd`, `_mm512_max_ps`.
- `abs`: `_mm512_abs_epi64`.
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
- `extract_value` with the default low-lane index: `_mm512_cvtsd_f64`,
  `_mm512_cvtss_f32`, `_mm_cvtsi128_si32`, `_mm_cvtsi128_si64`.
- `load[aligned=true|false]`: `_mm256_load_si256`,
  `_mm256_loadu_si256`, `_mm512_load_epi32`, `_mm512_load_epi64`,
  `_mm512_load_pd`, `_mm512_load_ps`, `_mm512_load_si512`,
  `_mm512_loadu_si512`, `_mm_load_si128`, `_mm_loadu_si128`.
- `load[aligned=false, mask=pass_through]`: `_mm512_mask_loadu_epi32`.
- `store[aligned=true|false]`: `_mm512_store_epi32`,
  `_mm512_store_epi64`, `_mm512_store_pd`, `_mm512_store_ps`,
  `_mm512_store_si512`, `_mm512_storeu_si512`, `_mm_store_si128`.
- `store[aligned=false, mask=pass_through]`: `_mm512_mask_storeu_epi32`.
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
- `popcnt`, including its scalar specialization: `_mm_popcnt_u32`,
  `_mm_popcnt_u64`.
- `to_integral`: `_mm512_mask2int`.
- `mov[mask=pass_through]`: `_mm512_mask_mov_epi32`.
- `blend`: `_mm512_mask_blend_epi32`.
- `gather`: `_mm512_i32gather_epi32`, `_mm512_i32gather_ps`,
  `_mm512_i64gather_epi64`.
- `gather[mask=pass_through]`: `_mm512_mask_i32gather_epi32`,
  `_mm512_mask_i64gather_epi64`.
- `scatter`: `_mm512_i32scatter_epi32`, `_mm512_i32scatter_ps`,
  `_mm512_i64scatter_epi64`.
- `scatter[mask=zero]`: `_mm512_mask_i32scatter_ps`.
- `mask_binary_and`: `_mm512_kand`.
- `mask_binary_or`: `_mm512_kor`.
- `mask_binary_not`: `_mm512_knot`.
- `expand[mask=pass_through]`: `_mm512_mask_expand_epi32`.
- `align_right_lanes`: `_mm512_alignr_epi32`, `_mm512_alignr_epi64`.
- `permute_lanes4`: `_mm256_permute4x64_epi64`, `_mm_shuffle_epi32`.
- `permute_lanes`: `_mm512_permutexvar_epi32`.
- `permute_lanes2`: `_mm512_permutex2var_epi32`.
- `random_step`: `_rdrand64_step`.

## Partial inventory and proposed primitives (61)

Every intrinsic in this section has nearby vocabulary, but no current public
primitive has the exact operation shape.

| Required intrinsic(s) | Current corpus evidence and exact gap | Proposed primitive contract |
|---|---|---|
| `_mm_broadcast_ss`, `_mm256_broadcast_sd` | `load_scalar` and `set1` compose the value result, but no primitive takes a pointer and broadcasts the loaded scalar. | Add `load_broadcast(ptr)` in `load_store/construct.tsl` or `load.tsl`, with a `v:=cptr` contract and unaligned scalar access. |
| `_mm_broadcastb_epi8`, `_mm_broadcastw_epi16`, `_mm512_broadcastd_epi32`, `_mm512_broadcastq_epi64` | `extract_value<0>` plus `set1` composes the result, but `set1` accepts a scalar rather than a vector source. | Add `broadcast_lane<SourceVec, Index=0>(source) -> Vec`; permit a typed source vector whose register width differs from the destination. |
| `_mm512_broadcast_f32x4`, `_mm512_broadcast_f64x4` | `extract`/`insert` can assemble repeated chunks, but there is no chunk-broadcast contract. | Add `broadcast_chunk<SourceVec>(source) -> Vec`, defined as cyclic repetition of all source lanes into the destination. |
| `_mm512_castsi128_si512`, `_mm512_castsi256_si512` | `set_undef` plus `insert` composes the low chunk, but no one-argument contract states that only the low source bits are preserved and upper bits are undefined. | Add `widen_undef<SourceVec>(source) -> Vec`; use compile-only tests plus assertions on the defined low chunk only. |
| `_mm512_cmp_pd_mask`, `_mm512_cmp_ps_mask` | Six named comparison primitives exist, but the immediate form exposes the full Intel predicate space, including ordered/unordered and signaling choices. | Add `compare_predicate(left, right, predicate: sImm) -> m`; define predicate values in source data rather than decoding them in a template. |
| `_mm512_mask_cmp_pd_mask` | Masked named comparisons exist, but no masked immediate-predicate overload exists. | Add `compare_predicate(mask, left, right, predicate) -> m` with `[mask=zero]`. |
| `_mm512_cvtepi32_epi16`, `_mm512_cvtepi32_epi8` | `convert_down` is explicitly saturating/clamping and zero-fills a destination chunk. These Intel operations truncate high bits. | Add a separate `truncate_down<ToBase, Index=0>(data)` primitive. Do not weaken or silently rename the existing saturating `convert_down` contract. |
| `_mm512_i32logather_epi64`, `_mm512_i32logather_pd` | `gather` already has typed `IndicesType`, but its 64-bit AVX-512 slots select `i64gather`; they do not consume packed 32-bit indices from the lower half of the source index vector. | Extend `gather` for 64-bit data plus 32-bit `IndicesType`, consuming the first result-lane-count indices and selecting `i32gather`. |
| `_mm512_i32loscatter_epi64`, `_mm512_i32loscatter_pd` | `scatter` has the right address semantics and typed index generic, but 64-bit data selects `i64scatter`. | Extend `scatter` for 64-bit data plus 32-bit `IndicesType`, selecting `i32scatter`. |
| `_mm512_mask_i32logather_epi64` | The masked `gather` has an independent merge source, but the 64-bit specialization still lacks the narrow 32-bit index shape. | Add the same 64-bit-data/32-bit-index specialization to `gather[mask=pass_through]`. |
| `_mm512_mask_i32loscatter_epi64`, `_mm512_mask_i32loscatter_pd` | Masked `scatter` has the correct write gating but lacks the narrow index specialization for 64-bit data. | Add the same 64-bit-data/32-bit-index specialization to masked `scatter`. |
| `_mm512_mask_add_epi32`, `_mm512_mask_and_epi64`, `_mm512_mask_or_epi64`, `_mm512_mask_sub_epi32` | Current pass-through overloads reuse `left` as both arithmetic operand and inactive-lane source. `blend_add` has the opposite mask selection polarity and is not exact. | Add four-input merge overloads `op(mask, source, left, right)` for `add`, `binary_and`, `binary_or`, and `sub`, all with `[mask=pass_through]`. |
| `_mm512_mask_broadcastq_epi64` | `masked_set1` has an independent inactive-lane source but accepts a scalar, not the low lane of a vector source. | Add the merge overload `broadcast_lane(mask, source, lane_source, Index=0)` with `[mask=pass_through]`. |
| `_mm512_mask_compress_epi32` | Current `compress(mask, data)` zero-fills lanes after the packed prefix; the Intel merge form copies those lanes from `src`. | Add `compress(mask, source, data)` with `[mask=pass_through]`, retaining the current two-input zero-fill overload. |
| `_mm512_mask_compressstoreu_epi32` | `compress_store` has exact packing semantics and already uses the unaligned intrinsic internally, but its only public declaration is `[aligned=true]`. | Make `compress_store` expose `[aligned=*]` and add an explicit `aligned=false` implementation/test slot; do not treat an unaligned body as proof of an unaligned API contract. |
| `_mm512_mask_cvtepu8_epi32` | `convert_up` covers unsigned widening and `blend` can merge, but there is no masked conversion with an independent `src`. | Add `convert_up(mask, source, data, index)` with `[mask=pass_through]`; the source-vector and destination-vector widths must be typed explicitly. |
| `_mm512_mask_expandloadu_epi32` | `expand_load(mask, ptr)` is zero-fill and declared `[aligned=true]`; the required form is unaligned and preserves an independent source in inactive lanes. | Add `expand_load(mask, ptr, source)` with `[aligned=false, mask=pass_through]`, keeping the current zero-fill overload. |
| `_mm512_kandn` | `mask_binary_not` plus `mask_binary_and` composes `(~a) & b`, but no exact mask operation exists. | Add `mask_binary_andnot(mask_a, mask_b) -> m` with left-operand inversion, matching `binary_andnot` operand order. |
| `_mm512_kortestz` | `mask_binary_or` can form the intermediate mask, but there is no two-mask scalar zero test. | Add `mask_or_test_zero(mask_a, mask_b) -> im`, returning one exactly when the OR result has no active bits. |
| `_mm512_kunpackb` | `insert_imask(a, b, 8)` is close, but it does not mask away the high bits of either input before concatenating the low bytes. | Add `concat_imask_low<HalfBits=8>(low, high) -> im`, explicitly taking the low `HalfBits` from each operand. |
| `_mm512_kxnor` | `mask_binary_xor` plus `mask_binary_not` composes XNOR, but no exact mask primitive exists. | Add `mask_binary_xnor(mask_a, mask_b) -> m`. |
| `_mm256_testc_si256`, `_mm256_testz_si256` | Vector bitwise primitives exist, but the corpus has no whole-register scalar truth reduction for these conditions. | Add `contains_all_bits(left, right) -> im` for `(~left & right) == 0`, and `all_bits_disjoint(left, right) -> im` for `(left & right) == 0`. |
| `_mm512_test_epi32_mask`, `_mm512_test_epi64_mask`, `_mm512_testn_epi32_mask` | `binary_and`, `unequal_zero`, and named comparisons compose the lane masks, but there is no public bit-test family. | Add `bitwise_intersects(left, right) -> m` for nonzero lane intersections and `bitwise_disjoint(left, right) -> m` for zero lane intersections. |
| `_mm512_mask_test_epi32_mask`, `_mm512_mask_testn_epi32_mask`, `_mm512_mask_testn_epi64_mask` | The same per-lane composition exists, but the input writemask is not part of one primitive contract. | Add `[mask=zero]` overloads of `bitwise_intersects` and `bitwise_disjoint`. |
| `_mm256_stream_load_si256`, `_mm512_stream_load_si512`, `_mm_stream_load_si128` | Aligned `load` exists, but it has no non-temporal/cache-policy contract. | Extend `load` with an explicit `[memory=non_temporal]` attribute, valid only with `aligned=true`, rather than creating ISA-named stream primitives. |
| `_mm512_stream_si512`, `_mm_stream_si128`, `_mm_stream_si32`, `_mm_stream_si64` | Vector and scalar `store` overloads exist, but none expresses non-temporal store policy. | Extend both `store(ptr, vector)` and `store(ptr, scalar)` with `[memory=non_temporal, aligned=true]`. |
| `_mm512_mul_epu32` | `mul` is same-width lane multiplication; it does not select even 32-bit lanes or widen the products to 64 bits. | Add `mul_widen_even<ToBase=ui64>(left, right) -> Vec`, with explicit even-lane selection and unsigned widening semantics. |
| `_mm512_rol_epi32`, `_mm512_ror_epi64` | Shifts and binary OR compose rotates, but no primitive defines modulo-width rotate semantics. | Add `rotate_left(data, shift: sImm)` and `rotate_right(data, shift: sImm)` in `bitwise/shifts.tsl`. |
| `_mm512_ternarylogic_epi32`, `_mm512_ternarylogic_epi64` | Binary Boolean primitives can realize a fixed expression, but there is no immediate-controlled three-input truth-table operation. | Add `bitwise_ternary(a, b, c, truth_table: sImm) -> v`; define the immediate bit ordering in authored semantics and tests. |
| `__blsr_u64` | Arithmetic and bitwise primitives compose `x & (x - 1)`, but no scalar contract names the operation. | Add `reset_lowest_set_bit(data: s) -> s`, with zero mapping to zero. |
| `__tzcnt_u32`, `__tzcnt_u64` | `tzc` accepts a mask, while `lzc_scalar` demonstrates the desired scalar bit-count shape. | Add `tzc_scalar(data: s) -> usize`, with zero mapping to the scalar bit width. |
| `_mm_cvtsi32_si128`, `_mm_cvtsi64_si128` | `set_zero` plus `insert_value<0>` composes the value, but no scalar constructor promises zeroed upper lanes. | Add `set_low(value: s) -> v`; distinguish it from `set1`, which broadcasts. |
| `_mm_loadl_epi64` | Masked load or `load_scalar` plus `set_low` can compose the result, but no load contract states that only the low lane is read and all upper lanes are zero. | Add `load_low(ptr, LaneCount=1) -> v` with unaligned access and zeroed upper lanes. |

## Missing inventory and proposed primitives (0)

No required intrinsic remains without a public semantic primitive contract.

## Closure of the formerly missing inventory (8)

| Required intrinsic(s) | Implemented primitive contract | Coverage and verification |
|---|---|---|
| `_mm512_abs_epi64` | `abs(data) -> v` | All vector extensions and all ten datatypes. Signed minimum retains its two's-complement bit pattern; floating-point absolute value clears the sign bit. Exact AVX-512 `si64` specialization plus portable fallbacks. |
| `_mm512_alignr_epi32`, `_mm512_alignr_epi64` | `align_right_lanes(left, right, count: sImm) -> v` | All vector extensions and datatypes, with count reduced modulo the active lane count. Exact AVX-512 32/64-bit integral specializations plus portable fallbacks. |
| `_mm256_permute4x64_epi64`, `_mm_shuffle_epi32` | `permute_lanes4(data, control: sImm) -> v` | All vector extensions and datatypes, operating independently on groups of at most four lanes. Exact matching x86 specializations plus portable fallbacks. |
| `_mm512_permutexvar_epi32` | `permute_lanes(data, indexes) -> v` | All vector extensions and datatypes; signed or unsigned same-width integral index vectors are supported and indexes are reduced modulo lane count. Exact AVX-512 32-bit integral specialization plus portable fallbacks. |
| `_mm512_permutex2var_epi32` | `permute_lanes2(left, indexes, right) -> v` | All vector extensions and datatypes; indexes address the concatenation of both sources modulo twice the lane count. Exact AVX-512 32-bit integral specialization plus portable fallbacks. |
| `_rdrand64_step` | `random_step(out: ptr) -> usize` | Intentionally limited to x86 `ui64` profiles with the `rdrand` feature. Returns a 0/1 status and writes only on success; compile/contract tests avoid asserting randomness. |

## Implementation sequence for the remaining partial inventory

Keep each numbered item as a separate coherent slice. A slice is complete only
when its declared contracts select, lower, render, and receive the applicable
generated checks; source declarations alone do not close an inventory row.

1. **Mask, merge-source, and comparison contracts.** Add the independent-source
   overloads, immediate comparisons, mask AND-NOT/XNOR/concatenation/OR-test,
   vector bit tests, and merge `compress`. These mostly reuse current signature
   kinds and mask policies. Resolve the contradictory `blend_add` description
   while preserving its current tested behavior; do not repurpose it as masked
   add.
2. **Memory policy and packed memory.** Add a typed `memory=non_temporal`
   attribute to vector/scalar load/store contracts, make `compress_store`
   honestly expose unaligned use, and add merge-source unaligned `expand_load`.
   Attribute validation should reject non-temporal unaligned shapes that the
   target intrinsic does not support.
3. **Broadcast, construction, and conversion.** Add pointer broadcast,
   lane/chunk broadcast, `set_low`, `load_low`, `widen_undef`, masked
   `convert_up`, and truncating `truncate_down`. First confirm that the typed
   signature model can express a source vector whose extension/width differs
   from the destination; if not, add one typed vector-parameter shape at the
   catalog/backend boundary rather than encoding width choices in raw text.
4. **Narrow-index gather/scatter.** Extend existing `IndicesType` selection for
   64-bit values with 32-bit indices, including masked forms. Add tests that use
   all eight consumed low indices and poison the unused upper index lanes so an
   accidental 64-bit-index interpretation fails visibly.
5. **Remaining bit and arithmetic operations.** Add widening even-lane
   multiply, rotates, ternary logic, scalar TZC, reset-lowest-set-bit, and
   whole-register test reductions. Keep unsigned bit-pattern behavior explicit
   at signed edge values.

## Validation and closure criteria

For every slice:

1. Add authored tests for the actual contract, including mask-none/mask-all,
   independent pass-through sources, zero, signed extrema, lane ordering,
   immediate boundaries, and alignment where applicable.
2. Run catalog and source validation:

   ```bash
   PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
   ```

3. Run selection/lowering and value-test planning at the touched boundary:

   ```bash
   PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_*.py
   PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_value_test_planning.py
   ```

4. Inspect representative AVX2/AVX-512 specializations with `dev.sh explain` or
   `dev.sh dump --stage lowered`. This is mandatory for non-temporal operations,
   undefined-upper casts, immediate predicates, and narrow-index gathers where
   value equality alone cannot prove the selected operation shape.
5. Build and run the smallest applicable generated matrix, normally C++ and
   Rust for `avx2` and `avx512`; record a structured backend skip if a required
   intrinsic has no stable Rust equivalent rather than silently substituting a
   different contract.
6. Run `git diff --check` for every slice. Run the full Python suite once a
   family is complete.

An intrinsic moves to **covered** only after its exact public primitive contract
is present and the applicable generated specialization builds. A composable
recipe, a private intrinsic occurrence, or an unverified implementation slot
remains **partial**.
