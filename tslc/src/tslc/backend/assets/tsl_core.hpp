// tslc static substrate (profile-independent). The `simd<base_type, extension>`
// primary template, the scalar registration, and `reg_param`. Per-profile headers
// add the `simd<>` registrations for the extensions that profile actually uses.
#pragma once
#include <cstdint>

namespace tsl {

// Primary trait: simd<BaseType, Extension> exposes base_type and register_type.
template <class T, class Ext>
struct simd;

// scalar is always available and needs no SIMD substrate.
struct scalar {};

template <class T>
struct simd<T, scalar> {
    using base_type = T;
    using register_type = T;
};

// How a register value is passed to apply(): by value.
template <class Vec>
struct reg_param {
    using type = typename Vec::register_type;
};

}  // namespace tsl
