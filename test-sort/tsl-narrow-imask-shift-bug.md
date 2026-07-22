# TSL bug report: `shift_left_imask` / `shift_right_imask` broken for 8/16-bit element masks

**TSL version:** generated release `v0.2.4` (`tslgen-v2`), profile
`SAPPHIRE_EMERALD_GRANITE_RAPIDS`.
**Compiler:** clang 21, `-O2 -std=c++17` with the profile's full AVX-512 flag set.
**Host:** AVX-512 (Sapphire-Rapids-class), BW/VBMI/VBMI2/VL present.

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

## Likely location

`shift_left_imask` / `shift_right_imask` `*_impl` for byte/word element widths.
For 32/64-bit the integral mask shift is a plain `k`-register / integer shift; the
8/16-bit specialization appears to shift by the wrong amount (e.g. scaled by
element size) or select a wrong/no-op path, yielding 0.

## Downstream workaround

Consumers can avoid the shifts by constructing low/offset lane masks with plain
integer arithmetic (`imask_type((1u64<<count)-1)`, `<<offset`), which is correct
for all element widths (guard `count>=64` to avoid `1<<64`). `test-sort`'s
partition uses this.
