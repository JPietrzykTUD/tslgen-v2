// tslc static substrate (profile-independent). The `simd<base_type, extension>`
// primary template, the scalar registration, and `reg_param`. Per-profile headers
// add the `simd<>` registrations for the extensions that profile actually uses.
#pragma once
#include <array>
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
    using type = array_type<typename Vec::base_type,
                            sizeof(typename Vec::register_type) / sizeof(typename Vec::base_type),
                            alignof(typename Vec::register_type)>;
};

}  // namespace tsl
