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

// Scalar-result check (a reduction's single value): compare one lane value to the expectation.
template <class T>
inline int check_scalar(const char *name, T actual, T expected) {
    if (lane_eq<T>(actual, expected)) {
        return 0;
    }
    std::fprintf(stderr, "FAIL %s: expected ", name);
    print_lane<T>(expected);
    std::fprintf(stderr, ", got ");
    print_lane<T>(actual);
    std::fprintf(stderr, "\n");
    return 1;
}

// Differential check: compare two computed lane containers (the hardware result vs the generic
// software reference) for the same inputs. `T` is the lane type; both are indexable.
template <class T, class A, class B>
inline int check_match(const char *name, const A &actual, const B &reference, std::size_t n) {
    int failures = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const T got = static_cast<T>(actual[i]);
        const T ref = static_cast<T>(reference[i]);
        if (!lane_eq<T>(got, ref)) {
            std::fprintf(stderr, "FAIL %s lane %zu: reference ", name, i);
            print_lane<T>(ref);
            std::fprintf(stderr, ", hardware ");
            print_lane<T>(got);
            std::fprintf(stderr, "\n");
            ++failures;
        }
    }
    return failures;
}

// Differential mask check: compare two integer-bitset masks (the hardware mask normalized via
// `to_integral` vs the generic reference's bitset) lane by lane. Representation-neutral.
template <class A, class B>
inline int check_mask_match(const char *name, A hw, B reference, std::size_t n) {
    int failures = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const bool got = ((static_cast<std::uint64_t>(hw) >> i) & 1u) != 0;
        const bool ref = ((static_cast<std::uint64_t>(reference) >> i) & 1u) != 0;
        if (got != ref) {
            std::fprintf(stderr, "FAIL %s lane %zu: reference %s, hardware %s\n", name, i,
                         ref ? "set" : "clear", got ? "set" : "clear");
            ++failures;
        }
    }
    return failures;
}

// Compare a mask result against a per-lane set/clear expectation. The generic reference's mask
// is an integer bitset (bit `i` = lane `i`); `expected_set[i]` is 1 if lane `i` should be set.
// Representation-neutral: only which lanes are set is asserted, never the bit width/pattern.
template <class Mask>
inline int check_mask(const char *name, Mask mask, const int *expected_set, std::size_t n) {
    int failures = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const bool got = ((static_cast<std::uint64_t>(mask) >> i) & 1u) != 0;
        const bool want = expected_set[i] != 0;
        if (got != want) {
            std::fprintf(stderr, "FAIL %s lane %zu: expected %s, got %s\n", name, i,
                         want ? "set" : "clear", got ? "set" : "clear");
            ++failures;
        }
    }
    return failures;
}

// --- Differential fuzzer ----------------------------------------------------------------------
// A deterministic xorshift64* step. The fuzz state is seeded per (primitive, type, extension), so
// a reported seed reproduces the exact input stream. The values binary is built with -fwrapv, so
// signed overflow wraps (two's complement) and matches SIMD — the scalar reference stays a faithful
// oracle even on full-width random inputs.
inline std::uint64_t fuzz_step(std::uint64_t &state) {
    state ^= state >> 12;
    state ^= state << 25;
    state ^= state >> 27;
    return state * 0x2545F4914F6CDD1DULL;
}

// One pseudo-random lane value. Integers span their full width; floats are drawn from a moderate
// finite range so ordinary arithmetic (not just NaN/inf soup) is exercised. Comparison stays
// bitwise / NaN-aware via `lane_eq`, so the infinities and NaN that the op itself produces match.
template <class T>
inline T fuzz_next(std::uint64_t &state) {
    const std::uint64_t bits = fuzz_step(state);
    if constexpr (std::is_floating_point_v<T>) {
        const double unit = static_cast<double>(bits >> 11) / 9007199254740992.0;  // [0, 1)
        return static_cast<T>(unit * 2048.0 - 1024.0);
    } else {
        return static_cast<T>(bits);
    }
}

}  // namespace test
}  // namespace tsl
