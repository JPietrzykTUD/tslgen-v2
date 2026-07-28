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
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#endif

// Loop-unroll hint for `loop<backend, unroll>`. A no-op by default (a real
// unroll pragma is compiler-specific and only a hint); kept as a macro so
// generated bodies always compile.
#ifndef TSL_UNROLL
#define TSL_UNROLL(n)
#endif

namespace tsl {

enum class implementation_state {
    native,
    composed,
    fallback,
    unknown,
};

template <auto Value>
struct value_arg {
    static constexpr auto value = Value;
};

template <class Primitive, class... Args>
struct implementation_state_of {
    static constexpr implementation_state value = implementation_state::unknown;
};

template <class Primitive, class... Args>
inline constexpr implementation_state implementation_state_v =
    implementation_state_of<Primitive, Args...>::value;

namespace detail {

struct base_si8_tag {};
struct base_si16_tag {};
struct base_si32_tag {};
struct base_si64_tag {};
struct base_ui8_tag {};
struct base_ui16_tag {};
struct base_ui32_tag {};
struct base_ui64_tag {};
struct base_f32_tag {};
struct base_f64_tag {};

template <class T, class Enable = void>
struct base_type_dispatch_key;

template <> struct base_type_dispatch_key<std::int8_t> { using type = base_si8_tag; };
template <> struct base_type_dispatch_key<std::int16_t> { using type = base_si16_tag; };
template <> struct base_type_dispatch_key<std::int32_t> { using type = base_si32_tag; };
template <> struct base_type_dispatch_key<std::int64_t> { using type = base_si64_tag; };
template <> struct base_type_dispatch_key<std::uint8_t> { using type = base_ui8_tag; };
template <> struct base_type_dispatch_key<std::uint16_t> { using type = base_ui16_tag; };
template <> struct base_type_dispatch_key<std::uint32_t> { using type = base_ui32_tag; };
template <> struct base_type_dispatch_key<std::uint64_t> { using type = base_ui64_tag; };
template <> struct base_type_dispatch_key<float> { using type = base_f32_tag; };
template <> struct base_type_dispatch_key<double> { using type = base_f64_tag; };

template <class T>
using base_type_dispatch_key_t = typename base_type_dispatch_key<T>::type;

}  // namespace detail

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

// Language-neutral scalar numeric conversion used by lane-preserving conversion. Its
// contract matches Rust scalar `as`: integer narrowing wraps, integer widening preserves
// signed value where representable, and float-to-integer truncates then saturates with NaN
// mapped to zero.
template <class To, class From>
inline To scalar_as_cast(From value) {
    static_assert(std::is_arithmetic_v<To> && std::is_arithmetic_v<From>);
    if constexpr (std::is_integral_v<From> && std::is_integral_v<To>) {
        if constexpr (std::is_unsigned_v<To>) {
            return static_cast<To>(value);
        } else if constexpr (
            (std::is_signed_v<From> && std::numeric_limits<To>::digits >=
                std::numeric_limits<From>::digits) ||
            (std::is_unsigned_v<From> && std::numeric_limits<To>::digits >=
                std::numeric_limits<From>::digits)) {
            return static_cast<To>(value);
        } else {
            using UnsignedTo = std::make_unsigned_t<To>;
            const auto bits = static_cast<UnsignedTo>(value);
            return ::tsl::bit_cast<To>(bits);
        }
    } else if constexpr (std::is_floating_point_v<From> && std::is_integral_v<To>) {
        if (std::isnan(value)) {
            return To{0};
        }
        const long double converted = static_cast<long double>(value);
        const long double upper_exclusive = std::ldexp(
            1.0L, std::numeric_limits<To>::digits
        );
        if constexpr (std::is_unsigned_v<To>) {
            if (converted <= 0.0L) {
                return To{0};
            }
            if (converted >= upper_exclusive) {
                return std::numeric_limits<To>::max();
            }
        } else {
            if (converted <= -upper_exclusive) {
                return std::numeric_limits<To>::lowest();
            }
            if (converted >= upper_exclusive) {
                return std::numeric_limits<To>::max();
            }
        }
        return static_cast<To>(value);
    } else {
        return static_cast<To>(value);
    }
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
    using extension_type = scalar;
    using register_type = T;
    using mask_type = bool;
    // Integral mask: a fixed unsigned scalar (to_integral packs the 0/1 mask into it).
    using imask_type = std::uint64_t;
    template <class ToBase>
    using with_base_type = simd<ToBase, scalar>;
    template <class ToExtension>
    using with_extension = simd<T, ToExtension>;
    static constexpr bool has_static_lane_count_v = true;
    static constexpr std::size_t lane_count_v = 1;
    static constexpr std::size_t vector_element_count = lane_count_v;
    static constexpr std::size_t lane_count() noexcept {
        return lane_count_v;
    }
    static constexpr std::size_t vector_alignment = alignof(T);
    static constexpr std::size_t simd_register_alignment_v = vector_alignment;
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
    using extension_type = generic<LANES>;
    using register_type = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    using mask_type = std::uint64_t;
    // Integral mask: the same 64-bit bitset (LANES is a template param, so the lane count
    // can't size a smaller integer at this point).
    using imask_type = std::uint64_t;
    template <class ToBase>
    using with_base_type = simd<ToBase, generic<LANES>>;
    template <class ToExtension>
    using with_extension = simd<T, ToExtension>;
    static constexpr bool has_static_lane_count_v = true;
    static constexpr std::size_t lane_count_v = LANES;
    static constexpr std::size_t vector_element_count = lane_count_v;
    static constexpr std::size_t lane_count() noexcept {
        return lane_count_v;
    }
    static constexpr std::size_t vector_alignment = alignof(register_type);
    static constexpr std::size_t simd_register_alignment_v = vector_alignment;
};

template <class T, std::size_t LANES>
struct reg_param<simd<T, generic<LANES>>> {
    using type = const typename simd<T, generic<LANES>>::register_type &;
};

// Scalar-core helpers used by emulated (loop) bodies. Grows one function at a time as the
// primitives that call `helper<...>` land; `arith_add` is the reductions' accumulate step.
namespace detail::helpers {

inline void require_same_lanes(std::size_t source_lanes, std::size_t target_lanes) {
    if (source_lanes != target_lanes) {
#if defined(__SYCL_DEVICE_ONLY__) || defined(__wasm__)
        __builtin_trap();
#else
        throw std::invalid_argument(
            "lane-preserving conversion requires equal source and target lane counts"
        );
#endif
    }
}
#if defined(__x86_64__) || defined(_M_X64)
#if defined(__GNUC__) || defined(__clang__)
__attribute__((target("rdrnd")))
#endif
inline std::size_t random_step_u64(std::uint64_t* out) {
    unsigned long long value = 0;
    const int status = _rdrand64_step(&value);
    if (status != 0) {
        *out = static_cast<std::uint64_t>(value);
    }
    return status != 0 ? std::size_t{1} : std::size_t{0};
}
#endif

template <class T>
inline T arith_add(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        using U = std::make_unsigned_t<T>;
        const U result = static_cast<U>(a) + static_cast<U>(b);
        if constexpr (std::is_signed_v<T>) {
            return ::tsl::bit_cast<T>(result);
        } else {
            return result;
        }
    } else {
        return a + b;
    }
}
[[noreturn]] inline void arith_zero_divisor_fail() {
#if defined(__SYCL_DEVICE_ONLY__) || defined(__wasm__)
    __builtin_trap();
#else
    throw std::domain_error("TSL_ARITH_INTEGER_ZERO_DIVISOR");
#endif
}
template <class T>
inline T arith_div(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        if (b == T{0}) {
            arith_zero_divisor_fail();
        }
        if constexpr (std::is_signed_v<T>) {
            if (a == std::numeric_limits<T>::lowest() && b == T{-1}) {
                return a;
            }
        }
    }
    return static_cast<T>(a / b);
}
template <class T>
inline T arith_mul(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        using U = std::make_unsigned_t<T>;
        const U result = static_cast<U>(a) * static_cast<U>(b);
        if constexpr (std::is_signed_v<T>) {
            return ::tsl::bit_cast<T>(result);
        } else {
            return result;
        }
    } else {
        return a * b;
    }
}
// Normalized remainder for emulated `mod` loops: checked integer `%`, or `std::fmod`
// for floats (where `%` is ill-formed).
template <class T>
inline T arith_rem(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        if (b == T{0}) {
            arith_zero_divisor_fail();
        }
        if constexpr (std::is_signed_v<T>) {
            if (a == std::numeric_limits<T>::lowest() && b == T{-1}) {
                return T{0};
            }
        }
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
