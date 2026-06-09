// tslc static core (scalar-safe). Hand-written library substrate, copied verbatim
// into generated C++ projects. Defines the simd<base_type, extension> trait that
// generated specializations key on.
#pragma once
#include <cstdint>

namespace tsl {

// Extension tag types (the second simd<> argument).
struct scalar {};
struct sse {};
struct avx2 {};

// Primary trait: simd<BaseType, Extension> exposes base_type and register_type.
template <class T, class Ext>
struct simd;

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
