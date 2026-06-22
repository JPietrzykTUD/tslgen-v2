#pragma once
// Shared, profile-independent helpers for the generated value-correctness tests.
// Comparison is typed: integers compare exactly; floats compare BITWISE (so -0.0, the
// infinities, and NaN payloads are distinguished — `==` would conflate -0.0 with 0.0 and
// never match NaN). The matching Rust helper (`tsl_test_core.rs`) mirrors this semantics so
// the same expected data drives both backends.
#include "tsl_core.hpp"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <type_traits>

namespace tsl {
namespace test {

// Lane-wise equality. For floating point this is an exact bit compare.
template <class T>
inline bool lane_eq(T actual, T expected) {
    if constexpr (std::is_floating_point_v<T>) {
        // Any NaN equals any NaN (a self-unequal value is NaN): the NaN sign/payload is not
        // semantically meaningful, and INF-INF legitimately yields +nan on one path, -nan on
        // another. Otherwise compare bits so -0.0 != 0.0 and the infinities stay exact.
        if (actual != actual && expected != expected) {
            return true;
        }
        using Bits = std::conditional_t<sizeof(T) == 4, std::uint32_t, std::uint64_t>;
        return ::tsl::bit_cast<Bits>(actual) == ::tsl::bit_cast<Bits>(expected);
    } else {
        return actual == expected;
    }
}

// One lane's value rendered for a failure message (signed/unsigned/float as a 64-bit-ish form).
template <class T>
inline void print_lane(const T &value) {
    if constexpr (std::is_floating_point_v<T>) {
        std::fprintf(stderr, "%g", static_cast<double>(value));
    } else if constexpr (std::is_signed_v<T>) {
        std::fprintf(stderr, "%lld", static_cast<long long>(value));
    } else {
        std::fprintf(stderr, "%llu", static_cast<unsigned long long>(value));
    }
}

// Compare `n` lanes of `actual` (anything with operator[], e.g. an array_type) against the
// `expected` C array. Returns the number of mismatching lanes and reports each.
template <class T, class Actual>
inline int check_lanes(const char *name, const Actual &actual, const T *expected,
                       std::size_t n) {
    int failures = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const T got = static_cast<T>(actual[i]);
        if (!lane_eq<T>(got, expected[i])) {
            std::fprintf(stderr, "FAIL %s lane %zu: expected ", name, i);
            print_lane<T>(expected[i]);
            std::fprintf(stderr, ", got ");
            print_lane<T>(got);
            std::fprintf(stderr, "\n");
            ++failures;
        }
    }
    return failures;
}

}  // namespace test
}  // namespace tsl
