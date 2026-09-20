// Scalar conversion and arithmetic runtime support for `tsl_core.hpp`.
#pragma once

#include "tsl_core_detail_types.hpp"

#include <cmath>
#include <cstring>
#include <limits>
#include <type_traits>

#if defined(__x86_64__) || defined(_M_X64)
#include <immintrin.h>
#endif

namespace tsl {
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

// A scalar/register overload family uses a generic public wrapper parameter so
// overload resolution can distinguish register arguments.  Prefer an explicit
// scalar conversion only when the corresponding implicit conversion is valid;
// expression SFINAE otherwise preserves the register argument by reference.
// This keeps ordinary C++ conversion semantics without inspecting intrinsic
// register types through type traits, which strict GCC builds diagnose as
// ignored attributes.
template <class Vec>
void scalar_argument_conversion_probe(typename Vec::base_type);

template <class Vec, class Arg>
TSL_FORCE_INLINE auto scalar_or_register_arg(Arg& arg, int)
    noexcept(noexcept(static_cast<typename Vec::base_type>(arg)))
    -> decltype(
        scalar_argument_conversion_probe<Vec>(arg),
        static_cast<typename Vec::base_type>(arg)) {
    return static_cast<typename Vec::base_type>(arg);
}

template <class Vec, class Arg>
TSL_FORCE_INLINE Arg& scalar_or_register_arg(Arg& arg, ...) noexcept {
    return arg;
}

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

// Scalar-core helpers used by emulated (loop) bodies. Grows one function at a time as the
// primitives that call `helper<...>` land; `arith_add` is the reductions' accumulate step.
namespace detail::helpers {

template <class Array>
inline decltype(auto) lane_get_unchecked(Array&& value, std::size_t index) {
    return static_cast<Array&&>(value)[index];
}

template <class Array, class Value>
inline void lane_set_unchecked(
    Array* value,
    std::size_t index,
    Value&& lane
) {
    (*value)[index] = static_cast<Value&&>(lane);
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
        const U result = static_cast<U>(
            static_cast<std::uintmax_t>(static_cast<U>(a))
            + static_cast<std::uintmax_t>(static_cast<U>(b))
        );
        if constexpr (std::is_signed_v<T>) {
            return ::tsl::bit_cast<T>(result);
        } else {
            return result;
        }
    } else {
        return a + b;
    }
}
template <class T>
inline T arith_sub(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
        using U = std::make_unsigned_t<T>;
        const U result = static_cast<U>(
            static_cast<std::uintmax_t>(static_cast<U>(a))
            - static_cast<std::uintmax_t>(static_cast<U>(b))
        );
        if constexpr (std::is_signed_v<T>) {
            return ::tsl::bit_cast<T>(result);
        } else {
            return result;
        }
    } else {
        return a - b;
    }
}
template <class T>
inline T arith_div(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
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
        const U result = static_cast<U>(
            static_cast<std::uintmax_t>(static_cast<U>(a))
            * static_cast<std::uintmax_t>(static_cast<U>(b))
        );
        if constexpr (std::is_signed_v<T>) {
            return ::tsl::bit_cast<T>(result);
        } else {
            return result;
        }
    } else {
        return a * b;
    }
}
// Normalized remainder for emulated `mod` loops: integer `%` under the public
// nonzero-divisor precondition, or `std::fmod` for floats (where `%` is ill-formed).
template <class T>
inline T arith_rem(T a, T b) {
    if constexpr (std::is_integral_v<T>) {
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

}  // namespace detail::helpers
}  // namespace tsl
