// tslc static substrate (profile-independent). The `simd<base_type, extension>`
// primary template, the scalar registration, and `reg_param`. Per-profile headers
// add the `simd<>` registrations for the extensions that profile actually uses.
#pragma once
#include <cstddef>
#include <cstdint>

namespace tsl {

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
};

// How a register value is passed to apply(): by value.
template <class Vec>
struct reg_param {
    using type = typename Vec::register_type;
};

}  // namespace tsl
