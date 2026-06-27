#pragma once
// SVE-only helpers for generated C++ value tests. This header is copied into
// generated projects only when extension metadata requests it.

#if defined(__ARM_FEATURE_SVE)

#include "tsl_sve.hpp"
#include "tsl_test_core.hpp"

#include <arm_sve.h>
#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace tsl {
namespace test {
namespace detail {
namespace sve_detail {

template <class Vec>
inline svbool_t all_predicate() {
    using Base = typename Vec::base_type;
    if constexpr (sizeof(Base) == 1) {
        return svptrue_b8();
    } else if constexpr (sizeof(Base) == 2) {
        return svptrue_b16();
    } else if constexpr (sizeof(Base) == 4) {
        return svptrue_b32();
    } else {
        return svptrue_b64();
    }
}

template <class Vec>
inline svbool_t lane_predicate(std::size_t lane) {
    using Base = typename Vec::base_type;
    const svbool_t all = all_predicate<Vec>();
    if constexpr (sizeof(Base) == 1) {
        const svuint8_t indexes = svindex_u8(0, 1);
        return svcmpeq_n_u8(all, indexes, static_cast<std::uint8_t>(lane));
    } else if constexpr (sizeof(Base) == 2) {
        const svuint16_t indexes = svindex_u16(0, 1);
        return svcmpeq_n_u16(all, indexes, static_cast<std::uint16_t>(lane));
    } else if constexpr (sizeof(Base) == 4) {
        const svuint32_t indexes = svindex_u32(0, 1);
        return svcmpeq_n_u32(all, indexes, static_cast<std::uint32_t>(lane));
    } else {
        const svuint64_t indexes = svindex_u64(0, 1);
        return svcmpeq_n_u64(all, indexes, static_cast<std::uint64_t>(lane));
    }
}

}  // namespace sve_detail

template <class Base>
struct mask_bits_adapter<::tsl::simd<Base, ::tsl::sve>> {
    using Vec = ::tsl::simd<Base, ::tsl::sve>;

    static typename Vec::mask_type from_bits(std::uint64_t bits,
                                             std::size_t authored_lanes,
                                             std::size_t lanes) {
        typename Vec::mask_type result = svpfalse_b();
        const svbool_t all = sve_detail::all_predicate<Vec>();
        for (std::size_t i = 0; i < lanes; ++i) {
            if (((bits >> (i % authored_lanes)) & 1u) == 0) {
                continue;
            }
            result = svorr_b_z(all, result, sve_detail::lane_predicate<Vec>(i));
        }
        return result;
    }

    static int check(const char *name, typename Vec::mask_type mask,
                     std::uint64_t bits, std::size_t authored_lanes,
                     std::size_t lanes) {
        int failures = 0;
        for (std::size_t i = 0; i < lanes; ++i) {
            const svbool_t lane = sve_detail::lane_predicate<Vec>(i);
            const bool got = svptest_any(lane, mask);
            const bool want = ((bits >> (i % authored_lanes)) & 1u) != 0;
            if (got != want) {
                std::fprintf(stderr, "FAIL %s lane %zu: expected %s, got %s\n",
                             name, i, want ? "set" : "clear",
                             got ? "set" : "clear");
                ++failures;
            }
        }
        return failures;
    }
};

}  // namespace detail

}  // namespace test
}  // namespace tsl

#endif
