// tslc static substrate (profile-independent). The `simd<base_type, extension>`
// primary template, the scalar registration, and `reg_param`. Per-profile headers
// add the `simd<>` registrations for the extensions that profile actually uses.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>

// Loop-unroll hint for `loop<unroll>`. A no-op by default (a real unroll pragma is
// compiler-specific and only a hint); kept as a macro so generated bodies always compile.
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

// Mask lane values (`mask::lane::all_true` / `all_false`): the all-bits-set / all-bits-clear
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
    T &operator[](std::size_t i) { return _storage[i]; }
    const T &operator[](std::size_t i) const { return _storage[i]; }
    void fill(const T &value) { _storage.fill(value); }
};

// The array type a vector lowers to (to_array's result / from_array's argument): one
// element per lane, over-aligned to the register. Derived from the register/base sizes,
// so it matches the body's explicit `array_type<base, length, alignment>`.
template <class Vec>
struct array_for {
    // Element-aligned (not register-aligned) so the array type is identical across extensions
    // of the same (base, lane-count) — `to_array<A>`'s result is what `from_array<B>` accepts,
    // for the cross-extension delegation round-trip. The buffer is fed unaligned load/store.
    using type = array_type<typename Vec::base_type,
                            sizeof(typename Vec::register_type) / sizeof(typename Vec::base_type),
                            alignof(typename Vec::base_type)>;
};

// The `generic` portable vector: a sized, array-backed register parameterized by its lane
// count. The tag carries `LANES` (a non-type template parameter), so `simd<T, generic<N>>`
// stays an ordinary two-argument specialization. Its register is an indexable `array_type`,
// so emulated bodies can `result[i] = ...` and delegate per lane to scalar. Always available
// (no hardware feature), hence defined here in the static core rather than per profile.
template <std::size_t LANES>
struct generic {};

template <class T, std::size_t LANES>
struct simd<T, generic<LANES>> {
    using base_type = T;
    using register_type = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    using mask_type = std::uint64_t;
    // Integral mask: the same 64-bit bitset (LANES is a template param, so the lane count
    // can't size a smaller integer at this point).
    using imask_type = std::uint64_t;
};

// Scalar-core helpers used by emulated (loop) bodies. Grows one function at a time as the
// primitives that call `details::*` land; `arith_add` is the reductions' accumulate step.
namespace details {
template <class T>
inline T arith_add(T a, T b) {
    return a + b;
}
template <class T>
inline T arith_mul(T a, T b) {
    return a * b;
}
// Population count of an integer mask: the number of set bits, an unsigned count (not the
// input type). Used by `mask_population_count` after `to_integral`. `__builtin_popcountll`
// keeps this C++17 (no `<bit>`/`std::popcount`).
template <class T>
inline std::uint32_t popcount(T v) {
    return static_cast<std::uint32_t>(__builtin_popcountll(static_cast<unsigned long long>(v)));
}
}  // namespace details

}  // namespace tsl
