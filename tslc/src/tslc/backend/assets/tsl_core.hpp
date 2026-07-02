// tslc static substrate (profile-independent). The `simd<base_type, extension>`
// primary template, the scalar registration, and `reg_param`. Per-profile headers
// add the `simd<>` registrations for the extensions that profile actually uses.
#pragma once
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <type_traits>

// Loop-unroll hint for `loop<backend, unroll>`. A no-op by default (a real
// unroll pragma is compiler-specific and only a hint); kept as a macro so
// generated bodies always compile.
#ifndef TSL_UNROLL
#define TSL_UNROLL(n)
#endif

namespace tsl {

// Type-punning bit reinterpret (`cast<bitcast>`): copy the object representation into a
// same-sized destination type. `std::bit_cast` needs C++20; this `memcpy` form is C++17 and
// the optimizer lowers it to a register move (used e.g. to read a SIMD register as another).
template <class To, class From>
inline To bit_cast(const From &src) {
    static_assert(sizeof(To) == sizeof(From), "bit_cast requires equal sizes");
    To dst;
    std::memcpy(&dst, &src, sizeof(To));
    return dst;
}

// Saturating narrowing cast (`cast<saturating>`, used by `convert_down`): clamp the value to the
// target type's representable range, then convert. Used only where the source is wider than the
// target (a narrowing convert), so the bounds convert exactly into `From` for the comparison.
// Counterpart to the Rust `detail::helpers::saturating_cast_value`. `lowest()` is the most-negative finite
// value (int min / float -max); an unsigned target's lower bound is 0 and is never exceeded.
template <class To, class From>
inline To saturating_cast(From value) {
    using ToLim = std::numeric_limits<To>;
    if constexpr (std::is_signed_v<From> || std::is_floating_point_v<From>) {
        if (value < static_cast<From>(ToLim::lowest())) {
            return ToLim::lowest();
        }
    }
    if (value > static_cast<From>(ToLim::max())) {
        return ToLim::max();
    }
    return static_cast<To>(value);
}

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

// Aligned-pointer hint for aligned load/store. `__builtin_assume_aligned` (gcc/clang)
// keeps this C++17-compatible; it is only an optimizer hint, so a plain return is also
// correct if the builtin is unavailable.
template <std::size_t N, class T>
inline T *assume_aligned(T *ptr) noexcept {
#if defined(__GNUC__) || defined(__clang__)
    return static_cast<T *>(__builtin_assume_aligned(ptr, N));
#else
    return ptr;
#endif
}

// Primary trait: simd<BaseType, Extension> exposes base_type and register_type.
template <class T, class Ext>
struct simd;

// scalar is always available and needs no SIMD substrate.
struct scalar {};

template <class T>
struct simd<T, scalar> {
    using base_type = T;
    using register_type = T;
    using mask_type = bool;
    // Integral mask: a fixed unsigned scalar (to_integral packs the 0/1 mask into it).
    using imask_type = std::uint64_t;
    static constexpr std::size_t vector_element_count = 1;
    static constexpr std::size_t vector_alignment = alignof(T);
};

// How a register value is passed to apply(): by value.
template <class Vec>
struct reg_param {
    using type = typename Vec::register_type;
};

// Pointer-offset helpers used by the generic vector's element-wise load/store loops.
template <class T>
inline T *ptr_add_mut(T *p, std::size_t i) {
    return p + i;
}
template <class T>
inline const T *ptr_add(const T *p, std::size_t i) {
    return p + i;
}

// The byte offset of a gather/scatter index: `index * scale` (scale in {1,2,4,8}). Used by the
// fallback loops over a byte-reinterpreted base pointer.
template <class Idx>
inline std::size_t idx_offset(Idx index, std::size_t scale) {
    return static_cast<std::size_t>(index) * scale;
}

// A fixed-size, over-aligned array buffer (the `s[]` kind). Wraps std::array so
// `.data()`/`operator[]`/`.fill()` are uniform with the Rust counterpart; `Align`
// over-aligns the storage so an aligned store into it (via `assume_aligned`) is valid.
// `Align` defaults to the element alignment (the scalar case, length 1).
template <class T, std::size_t N, std::size_t Align = alignof(T)>
struct alignas(Align) array_type {
    std::array<T, N> _storage;
    T *data() { return _storage.data(); }
    const T *data() const { return _storage.data(); }
    const T *as_ptr() const { return _storage.data(); }
    T *as_mut_ptr() { return _storage.data(); }
    T &operator[](std::size_t i) { return _storage[i]; }
    const T &operator[](std::size_t i) const { return _storage[i]; }
    void fill(const T &value) { _storage.fill(value); }
};

// The array type a vector lowers to (to_array's owned result / from_array's read-only
// input): one element per lane, over-aligned to the register. Derived from the register/base
// sizes, so it matches the body's explicit `array_type<base, length, alignment>`.
template <class Vec>
struct array_for {
    // Element-aligned (not register-aligned) so the array type is identical across extensions
    // of the same (base, lane-count) — `to_array<A>`'s result is what `from_array<B>` accepts,
    // for the cross-extension delegation round-trip. The buffer is fed unaligned load/store.
    using type = array_type<typename Vec::base_type,
                            sizeof(typename Vec::register_type) / sizeof(typename Vec::base_type),
                            alignof(typename Vec::base_type)>;
};

template <class Vec>
struct array_param {
    using type = const typename array_for<Vec>::type &;
};

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

// Format a lane array into a text buffer (the `to_ostream` body). `modifier` selects the base
// (0 = binary, 16 = hex, 8 = octal, else decimal); each lane is cast to a 64-bit pattern and its
// low `sizeof(T)*8` bits are emitted, high lane first, '|'-separated, with a trailing newline.
template <class T, std::size_t N, std::size_t Align>
inline void ostream_write(std::string &out, const array_type<T, N, Align> &arr, int modifier) {
    constexpr std::size_t bits = sizeof(T) * 8;
    const unsigned base =
        (modifier == 16) ? 16u : (modifier == 8) ? 8u : (modifier == 0) ? 2u : 10u;
    for (std::size_t lane = 0; lane < N; ++lane) {
        std::uint64_t value = static_cast<std::uint64_t>(arr[N - 1 - lane]);
        std::uint64_t masked = (bits >= 64) ? value : (value & ((std::uint64_t{1} << bits) - 1));
        if (base == 2u) {
            for (std::size_t b = bits; b-- > 0;) {
                out += ((masked >> b) & 1u) ? '1' : '0';
            }
        } else {
            char buf[88];
            std::size_t p = 0;
            if (masked == 0) {
                buf[p++] = '0';
            }
            while (masked) {
                unsigned d = static_cast<unsigned>(masked % base);
                buf[p++] = (d < 10) ? char('0' + d) : char('a' + d - 10);
                masked /= base;
            }
            while (p) {
                out += buf[--p];
            }
        }
        out += '|';
    }
    out += '\n';
}

// The `generic` portable vector: a sized, array-backed register parameterized by its lane
// count. The tag carries `LANES` (a non-type template parameter), so `simd<T, generic<N>>`
// stays an ordinary two-argument specialization. Its register is an indexable `array_type`,
// so emulated bodies can `result[i] = ...` and delegate per lane to scalar. Always available
// (no hardware feature), hence defined here in the static core rather than per profile.
template <std::size_t LANES>
struct generic {};

template <class T, std::size_t LANES>
struct simd<T, generic<LANES>> {
    // The generic vector models a portable register, so its total width must be a whole number of
    // 128-bit registers — the size ladder a size-changing primitive is monomorphized over. This
    // rejects a stray `generic<3>` / a 64-bit `generic<8>` of `int8_t` at instantiation.
    static_assert((LANES * sizeof(T)) % 16 == 0,
                  "tsl::generic<LANES>: LANES * sizeof(T) must be a multiple of 16 bytes (128 bits)");
    using base_type = T;
    using register_type = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    using mask_type = std::uint64_t;
    // Integral mask: the same 64-bit bitset (LANES is a template param, so the lane count
    // can't size a smaller integer at this point).
    using imask_type = std::uint64_t;
    static constexpr std::size_t vector_element_count = LANES;
    static constexpr std::size_t vector_alignment = alignof(register_type);
};

template <class T, std::size_t LANES>
struct reg_param<simd<T, generic<LANES>>> {
    using type = const typename simd<T, generic<LANES>>::register_type &;
};

// Scalar-core helpers used by emulated (loop) bodies. Grows one function at a time as the
// primitives that call `helper<...>` land; `arith_add` is the reductions' accumulate step.
namespace detail::helpers {
template <class T>
inline T arith_add(T a, T b) {
    return a + b;
}
template <class T>
inline T arith_mul(T a, T b) {
    return a * b;
}
// Remainder for emulated `mod` loops: integer `%`, or `std::fmod` for floats (where `%`
// is ill-formed). Matches the frozen runtime-support `arith_rem`.
template <class T>
inline T arith_rem(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        return static_cast<T>(a % b);
    } else {
        return static_cast<T>(std::fmod(a, b));
    }
}
// Population count of an integer mask: the number of set bits, an unsigned count (not the
// input type). Used by `mask_population_count` after `to_integral`. `__builtin_popcountll`
// keeps this C++17 (no `<bit>`/`std::popcount`).
template <class T>
inline std::uint32_t popcount(T v) {
    // Reinterpret through the same-width *unsigned* type before widening: a signed lane (e.g.
    // int8_t -1) must count its own 8 bits, not the 64 bits of a sign-extended widening — which
    // would also disagree with Rust's `count_ones`. (Rust counts the two's-complement bits.)
    using U = std::make_unsigned_t<T>;
    return static_cast<std::uint32_t>(
        __builtin_popcountll(static_cast<unsigned long long>(static_cast<U>(v))));
}
// Trailing-zero count of an integer mask (used by `tzc`): the index of the lowest set bit,
// or the full bit-width when the mask is zero. `__builtin_ctzll(0)` is undefined, hence the
// guard. Matches the frozen runtime-support `ctz` / Rust's `trailing_zeros`.
template <class T>
inline std::uint32_t ctz(T v) {
    using U = std::make_unsigned_t<T>;
    if (v == 0) {
        return static_cast<std::uint32_t>(sizeof(T) * 8);
    }
    return static_cast<std::uint32_t>(
        __builtin_ctzll(static_cast<unsigned long long>(static_cast<U>(v)))
    );
}
// Leading-zero count of an integer (used by `lzc`/`lzc_imask`): the number of high-order
// zero bits, width-aware via `sizeof(T)` (so a `u8` counts within 8 bits), and the full
// bit-width when the value is zero (`__builtin_clzll(0)` is undefined). Matches the frozen
// runtime-support `clz` / Rust's `leading_zeros`.
template <class T>
inline std::uint32_t clz(T v) {
    using U = std::make_unsigned_t<T>;
    if (v == 0) {
        return static_cast<std::uint32_t>(sizeof(T) * 8);
    }
    constexpr int width = static_cast<int>(sizeof(T) * 8);
    constexpr int ull_width = static_cast<int>(sizeof(unsigned long long) * 8);
    const int leading = __builtin_clzll(static_cast<unsigned long long>(static_cast<U>(v)));
    return static_cast<std::uint32_t>(leading - (ull_width - width));
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
    if constexpr (std::is_integral_v<MaskT>) {
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
