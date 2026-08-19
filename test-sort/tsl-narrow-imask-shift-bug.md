# TSL bug report: `shift_left_imask` / `shift_right_imask` broken for 8/16-bit element masks

**TSL version:** generated release `v0.2.4` (`tslgen-v2`), profile
`SAPPHIRE_EMERALD_GRANITE_RAPIDS`.
**Compiler:** clang 21, `-O2 -std=c++17` with the profile's full AVX-512 flag set.
**Host:** AVX-512 (Sapphire-Rapids-class), BW/VBMI/VBMI2/VL present.
**Status:** fixed in generated release `v0.2.5`; `v0.2.7` and `v0.2.8` are also
clean. See [Resolution](#resolution). `test-sort` pins `v0.2.8`.

## Summary

`tsl::shift_right_imask` / `tsl::shift_left_imask` return **0** (wrong bits) when
the vector's element type is 8- or 16-bit, while behaving correctly for 32/64-bit
elements — even at the *same* mask width. Because integral masks are used to build
selection masks for `compress`/`expand`, this silently corrupts any compaction of
u8/u16 data (observed as unsorted output / zeroed lanes in a SIMD partition).

`compress`, `expand`, `mask_true`, `to_integral`, `greater_than`/`less_than`/
`equal`, `min`/`max`, and `permute_lanes` are all **correct** for u8/u16 — the bug
is isolated to the integral-mask shifts.

## Evidence

`shift_right_imask(to_integral(mask_true), lane_count-2)` should yield `0x3`:

| vector | lanes | mask reg | shift_right result | expected |
|---|---|---|---|---|
| u8  x16 | 16 | `__mmask16` | `0x0` ✗ | `0x3` |
| u16 x32 | 32 | `__mmask32` | `0x0` ✗ | `0x3` |
| u32 x16 | 16 | `__mmask16` | `0x3` ✓ | `0x3` |

Note u8×16 and u32×16 use the **same** `__mmask16` and shift amount, yet differ —
so the defect is keyed on the *element type*, not the mask width. `shift_left_imask`
behaves identically (u8×16 `low2<<3` → `0x0`, u32×16 → `0x18`).

That the surrounding primitives are fine (isolating the shifts):

```cpp
using V = tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<16>, std::uint8_t>;
alignas(64) std::array<std::uint8_t,16> b{}; for (int i=0;i<16;++i) b[i]=10+i*10;
auto v = tsl::load<V,false>(b.data());

// mask from a COMPARISON (native mask_type): lanes with value<25 -> {0,1}
auto m_cmp   = tsl::less_than<V>(v, tsl::set1<V>(25));
// mask from the integral-shift path
auto m_shift = tsl::shift_right_imask<V>(tsl::to_integral<V>(tsl::mask_true<V>()), 16-2);

tsl::compress<V>(m_cmp,   v);  // -> [10,20,0,...]  CORRECT
tsl::compress<V>(m_shift, v);  // -> [0,0,0,...]    m_shift is wrongly 0
```

A directly-built integral mask (`imask_type((1u<<2)-1)`) or `to_mask` of it both
drive `compress` correctly for u8/u16 — confirming only the shifts are at fault.

## Resolution

Fixed in `v0.2.5`. Both primitives clamp a shift that exceeds the vector's lane
count to `0`; in `v0.2.4` that clamp compared the shift against the **element
bit width** instead of the **lane count**, so every 8/16-bit case shifted itself
to nothing:

| element | lanes | v0.2.4 clamp | v0.2.5+ clamp |
|---|---|---|---|
| u8 avx512  | 64 | `shift >= 8`  | `shift >= 64` |
| u16 avx512 | 32 | `shift >= 16` | `shift >= 32` |
| u32 avx512 | 16 | `shift >= 32` | `shift >= 16` |
| u64 avx512 |  8 | `shift >= 64` | `shift >= 8`  |

32/64-bit elements were unaffected because their over-wide clamp never fired for
an in-range shift. The same change tightened sub-native lane counts in the other
direction: `shift_left_imask` on a 2-lane vector with `shift == 3` now returns
`0` per the documented semantics, where `v0.2.4` returned `0x18`.

Re-verified 2026-08-18 on a Xeon w5-3425 with clang 21, profile
`SAPPHIRE_EMERALD_GRANITE_RAPIDS`, by comparing `low_lane_mask`/`lane_mask` — the
`shift_right_imask(to_integral(mask_true), lane_count - count)` and
`shift_left_imask(..., offset)` composition the partition uses — against integer
mask arithmetic for u8/u16/u32/u64 at every `(offset, count)` with
`offset + count <= lane_count`. `v0.2.4` fails every 8/16-bit case; `v0.2.5`,
`v0.2.7` and `v0.2.8` pass all 2965 combinations.

## Consumer note

Consumers that must support a buggy release can build low/offset lane masks with
plain integer arithmetic (`imask_type((1u64<<count)-1)`, `<<offset`), which is
correct for all element widths (guard `count>=64` to avoid `1<<64`). `test-sort`
does not: `TslPartitionReplayStep::low_lane_mask` in
[`cosort_network.hpp`](cosort_network.hpp) uses the TSL primitives directly and
was never affected, because the co-sort only instantiates `u32` and `u64`.
