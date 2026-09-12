// Integral-mask and mask-lane runtime support for `tsl_core.hpp`.
#pragma once

#include "tsl_core_detail_types.hpp"

#include <cstring>
#include <limits>
#include <type_traits>

namespace tsl {

// Mask lane values (`mask<lane_true>()` / `mask<lane_false>()`): the all-bits-set / all-bits-clear
// value of a lane, broadcast by `set1` to build an all-true / all-false lane-bitmask mask.
// Uniform for integer and float via the object representation — all-ones bytes are an int's
// all-ones and a float's all-ones-bit NaN. (Runtime, not constexpr: `set1`'s arg is a
// runtime broadcast.)
template <class T>
inline T mask_lane_all_true() {
    T value;
    std::memset(&value, 0xFF, sizeof(T));
    return value;
}
template <class T>
inline T mask_lane_all_false() {
    return T{};
}

namespace detail {

// Lane-bitmask integral type: the smallest unsigned integer with at least one
// bit per lane. Native profile registrations use this for integral masks whose
// representation is not a backend-native predicate type.
template <int Bits> struct uint_for_bits { using type = std::uint64_t; };
template <> struct uint_for_bits<8> { using type = std::uint8_t; };
template <> struct uint_for_bits<16> { using type = std::uint16_t; };
template <> struct uint_for_bits<32> { using type = std::uint32_t; };
template <> struct uint_for_bits<64> { using type = std::uint64_t; };

template <int Bits, class T>
struct lane_bitmask_int {
    static constexpr int lanes = Bits / (static_cast<int>(sizeof(T)) * 8);
    static constexpr int bits = lanes <= 8 ? 8 : lanes <= 16 ? 16 : lanes <= 32 ? 32 : 64;
    using type = typename uint_for_bits<bits>::type;
};

}  // namespace detail

namespace detail::helpers {

// Population count of an integer mask: the number of set bits, an unsigned count (not the
// input type). Used by `mask_population_count` after `to_integral`. The compact loop keeps the
// runtime support portable to every C++17 compiler without compiler-specific builtins.
template <class T>
inline std::uint32_t popcount(T v) {
    // Reinterpret through the same-width *unsigned* type before widening: a signed lane (e.g.
    // int8_t -1) must count its own 8 bits, not the 64 bits of a sign-extended widening — which
    // would also disagree with Rust's `count_ones`. (Rust counts the two's-complement bits.)
    using U = std::make_unsigned_t<T>;
    U bits = static_cast<U>(v);
    std::uint32_t count = 0;
    while (bits != 0) {
        bits = static_cast<U>(bits & static_cast<U>(bits - U{1}));
        ++count;
    }
    return count;
}
#if defined(AC_VERSION)
template <int W, bool S>
inline std::uint32_t popcount(ac_int<W, S> v) {
    std::uint32_t count = 0;
    for (int i = 0; i < W; ++i) {
        count += v[i] ? 1u : 0u;
    }
    return count;
}
#endif
// Trailing-zero count of an integer mask (used by `tzc`): the index of the lowest set bit,
// or the full bit-width when the mask is zero. Matches the frozen runtime-support `ctz` /
// Rust's `trailing_zeros`.
template <class T>
inline std::uint32_t ctz(T v) {
    using U = std::make_unsigned_t<T>;
    U bits = static_cast<U>(v);
    if (bits == 0) {
        return static_cast<std::uint32_t>(sizeof(T) * 8);
    }
    std::uint32_t count = 0;
    while ((bits & U{1}) == 0) {
        bits = static_cast<U>(bits >> 1);
        ++count;
    }
    return count;
}
#if defined(AC_VERSION)
template <int W, bool S>
inline std::uint32_t ctz(ac_int<W, S> v) {
    for (int i = 0; i < W; ++i) {
        if (v[i]) {
            return static_cast<std::uint32_t>(i);
        }
    }
    return static_cast<std::uint32_t>(W);
}
#endif
// Leading-zero count of an integer (used by `lzc`/`lzc_imask`): the number of high-order
// zero bits, width-aware via `sizeof(T)` (so a `u8` counts within 8 bits), and the full
// bit-width when the value is zero. Matches the frozen runtime-support `clz` / Rust's
// `leading_zeros`.
template <class T>
inline std::uint32_t clz(T v) {
    using U = std::make_unsigned_t<T>;
    U bits = static_cast<U>(v);
    std::uint32_t count = static_cast<std::uint32_t>(sizeof(T) * 8);
    while (bits != 0) {
        bits = static_cast<U>(bits >> 1);
        --count;
    }
    return count;
}
#if defined(AC_VERSION)
template <int W, bool S>
inline std::uint32_t clz(ac_int<W, S> v) {
    for (int i = W; i-- > 0;) {
        if (v[i]) {
            return static_cast<std::uint32_t>(W - 1 - i);
        }
    }
    return static_cast<std::uint32_t>(W);
}
#endif
inline constexpr std::uint64_t imask_low_bits(std::size_t count) {
    return count >= 64
        ? std::numeric_limits<std::uint64_t>::max()
        : count == 0
            ? std::uint64_t{0}
            : (std::uint64_t{1} << count) - std::uint64_t{1};
}

// Replace a source-mask window in a target mask. Lane counts, rather than the
// storage integer widths, define the copied window; this matters for compact
// masks whose public integer type is rounded up to 8/16/32/64 bits.
template <class ToVec>
inline typename ToVec::imask_type imask_insert(
    std::uint64_t orig,
    std::uint64_t data,
    std::size_t position,
    std::size_t source_lanes,
    std::size_t target_lanes
) {
    const std::uint64_t normalized_orig = orig & imask_low_bits(target_lanes);
    if (position >= target_lanes || position >= 64) {
        return static_cast<typename ToVec::imask_type>(normalized_orig);
    }
    const std::size_t available = target_lanes - position;
    const std::size_t copied = source_lanes < available ? source_lanes : available;
    const std::uint64_t window = imask_low_bits(copied) << position;
    const std::uint64_t inserted = (data & imask_low_bits(copied)) << position;
    return static_cast<typename ToVec::imask_type>(
        (normalized_orig & ~window) | inserted
    );
}

// Select a target-sized source-mask window and normalize it to bit zero.
template <class ToVec>
inline typename ToVec::imask_type imask_extract(
    std::uint64_t data,
    std::size_t position,
    std::size_t source_lanes,
    std::size_t target_lanes
) {
    if (position >= source_lanes || position >= 64) {
        return static_cast<typename ToVec::imask_type>(0);
    }
    const std::size_t available = source_lanes - position;
    const std::size_t copied = target_lanes < available ? target_lanes : available;
    return static_cast<typename ToVec::imask_type>(
        (data >> position) & imask_low_bits(copied)
    );
}

// Test lane `index` of an emulated mask, agnostic to how the vector stores it. Two reprs:
// an integer bitset (the generic vector's `std::uint64_t`, or a native `__mmaskN`) tests bit
// `index`; a register lane-mask (sse/avx2, where the mask IS a data register whose lanes are
// all-ones/all-zeros) reads lane `index`'s base-sized chunk and tests it for nonzero. The
// `if constexpr` keeps each branch well-formed for only the matching `mask_type`. (`mask<test>`
// routes register reprs here; the bitset repr stays the inline shift template.)
template <class Vec>
inline bool mask_test(const typename Vec::mask_type& mask, std::size_t index) {
    using MaskT = typename Vec::mask_type;
    if constexpr (Vec::mask_is_bitset) {
        return ((mask >> index) & 1ull) != 0;
    } else {
        using BaseT = typename Vec::base_type;
        BaseT lanes[sizeof(MaskT) / sizeof(BaseT)];
        std::memcpy(lanes, &mask, sizeof(mask));
        return lanes[index] != BaseT(0);
    }
}

}  // namespace detail::helpers
}  // namespace tsl
