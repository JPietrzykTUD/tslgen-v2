#pragma once
// RVV-only helpers for generated C++ value tests. This header is copied into
// generated projects only when extension metadata requests it.

#if defined(__riscv_vector)

#include <riscv_vector.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>

#include "tsl_test_core.hpp"

namespace tsl {
  namespace test {
    namespace detail {
      namespace rvv_detail {

        template <class Vec>
        inline typename Vec::mask_type empty_predicate(std::size_t lanes) {
          using Base = typename Vec::base_type;
          if constexpr (sizeof(Base) == 1) {
            return __riscv_vmclr_m_b8(lanes);
          } else if constexpr (sizeof(Base) == 2) {
            return __riscv_vmclr_m_b16(lanes);
          } else if constexpr (sizeof(Base) == 4) {
            return __riscv_vmclr_m_b32(lanes);
          } else {
            return __riscv_vmclr_m_b64(lanes);
          }
        }

        template <class Vec>
        inline typename Vec::mask_type lane_predicate(std::size_t lane,
                                                      std::size_t lanes) {
          using Base = typename Vec::base_type;
          if constexpr (sizeof(Base) == 1) {
            const vuint8m1_t indexes = __riscv_vid_v_u8m1(lanes);
            return __riscv_vmseq_vx_u8m1_b8(
                indexes, static_cast<std::uint8_t>(lane), lanes);
          } else if constexpr (sizeof(Base) == 2) {
            const vuint16m1_t indexes = __riscv_vid_v_u16m1(lanes);
            return __riscv_vmseq_vx_u16m1_b16(
                indexes, static_cast<std::uint16_t>(lane), lanes);
          } else if constexpr (sizeof(Base) == 4) {
            const vuint32m1_t indexes = __riscv_vid_v_u32m1(lanes);
            return __riscv_vmseq_vx_u32m1_b32(
                indexes, static_cast<std::uint32_t>(lane), lanes);
          } else {
            const vuint64m1_t indexes = __riscv_vid_v_u64m1(lanes);
            return __riscv_vmseq_vx_u64m1_b64(
                indexes, static_cast<std::uint64_t>(lane), lanes);
          }
        }

        template <class Vec>
        inline typename Vec::mask_type mask_or(typename Vec::mask_type left,
                                               typename Vec::mask_type right,
                                               std::size_t lanes) {
          using Base = typename Vec::base_type;
          if constexpr (sizeof(Base) == 1) {
            return __riscv_vmor_mm_b8(left, right, lanes);
          } else if constexpr (sizeof(Base) == 2) {
            return __riscv_vmor_mm_b16(left, right, lanes);
          } else if constexpr (sizeof(Base) == 4) {
            return __riscv_vmor_mm_b32(left, right, lanes);
          } else {
            return __riscv_vmor_mm_b64(left, right, lanes);
          }
        }

        template <class Vec>
        inline typename Vec::mask_type mask_and(typename Vec::mask_type left,
                                                typename Vec::mask_type right,
                                                std::size_t lanes) {
          using Base = typename Vec::base_type;
          if constexpr (sizeof(Base) == 1) {
            return __riscv_vmand_mm_b8(left, right, lanes);
          } else if constexpr (sizeof(Base) == 2) {
            return __riscv_vmand_mm_b16(left, right, lanes);
          } else if constexpr (sizeof(Base) == 4) {
            return __riscv_vmand_mm_b32(left, right, lanes);
          } else {
            return __riscv_vmand_mm_b64(left, right, lanes);
          }
        }

        template <class Vec>
        inline std::size_t mask_population_count(typename Vec::mask_type mask,
                                                 std::size_t lanes) {
          using Base = typename Vec::base_type;
          if constexpr (sizeof(Base) == 1) {
            return __riscv_vcpop_m_b8(mask, lanes);
          } else if constexpr (sizeof(Base) == 2) {
            return __riscv_vcpop_m_b16(mask, lanes);
          } else if constexpr (sizeof(Base) == 4) {
            return __riscv_vcpop_m_b32(mask, lanes);
          } else {
            return __riscv_vcpop_m_b64(mask, lanes);
          }
        }

      }  // namespace rvv_detail

      template <class Vec>
      struct rvv_mask_bits_adapter {
        static typename Vec::mask_type from_bits(std::uint64_t bits,
                                                 std::size_t authored_lanes,
                                                 std::size_t lanes) {
          typename Vec::mask_type result =
              rvv_detail::empty_predicate<Vec>(lanes);
          for (std::size_t i = 0; i < lanes; ++i) {
            if (((bits >> (i % authored_lanes)) & 1u) == 0) {
              continue;
            }
            result = rvv_detail::mask_or<Vec>(
                result, rvv_detail::lane_predicate<Vec>(i, lanes), lanes);
          }
          return result;
        }

        static int check(const char* name, typename Vec::mask_type mask,
                         std::uint64_t bits, std::size_t authored_lanes,
                         std::size_t lanes) {
          int failures = 0;
          for (std::size_t i = 0; i < lanes; ++i) {
            const typename Vec::mask_type lane =
                rvv_detail::lane_predicate<Vec>(i, lanes);
            const bool got =
                rvv_detail::mask_population_count<Vec>(
                    rvv_detail::mask_and<Vec>(mask, lane, lanes), lanes) != 0;
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

#if defined(TSL_PROFILE_RVV)
      template <class Base>
      struct mask_bits_adapter<::tsl::simd<Base, ::tsl::rvv>>
          : rvv_mask_bits_adapter<::tsl::simd<Base, ::tsl::rvv>> {};
#endif

    }  // namespace detail

  }  // namespace test
}  // namespace tsl

#endif
