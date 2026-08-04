#include "pipcost/measurement.hpp"

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>

#include "pipcost/data.hpp"

namespace pipcost {
namespace {

constexpr unsigned char kNativeCanary = 0xa5;

void set_native_canary(NativeMask& value) {
    std::memset(&value, kNativeCanary, sizeof(value));
}

bool is_native_canary(const NativeMask& value) {
    const auto* bytes = reinterpret_cast<const unsigned char*>(&value);
    return std::all_of(
        bytes,
        bytes + sizeof(value),
        [](unsigned char byte) { return byte == kNativeCanary; });
}

}  // namespace

std::int64_t scalar_reference(const DataSet& data) {
    std::int64_t total = 0;
    for (std::size_t row = 0; row < data.a.size(); ++row) {
        if (data.a[row] < data.p1 && data.b[row] > data.p2) {
            total += static_cast<std::int64_t>(data.c[row]);
        }
    }
    return total;
}

Scratch::Scratch(std::size_t rows)
    : native_masks(
          tsl::algo::mask_chunk_count<
              tsl::algo::mask_layout::native,
              Parallelism,
              std::int32_t>(std::max<std::size_t>(rows, 1)) +
          2),
      integral_masks(
          tsl::algo::mask_chunk_count<
              tsl::algo::mask_layout::integral,
              Parallelism,
              std::int32_t>(std::max<std::size_t>(rows, 1)) +
          2),
      bit_masks(
          tsl::algo::mask_chunk_count<
              tsl::algo::mask_layout::bits,
              Parallelism,
              std::int32_t>(std::max<std::size_t>(rows, 1)) +
          2),
      positions(std::max<std::size_t>(rows, 1) + 2) {
    reset_canaries();
}

void Scratch::reset_canaries() {
    set_native_canary(native_masks.front());
    set_native_canary(native_masks.back());
    integral_masks.front() = std::numeric_limits<IntegralMask>::max();
    integral_masks.back() = std::numeric_limits<IntegralMask>::max();
    bit_masks.front() = std::numeric_limits<BitMask>::max();
    bit_masks.back() = std::numeric_limits<BitMask>::max();
    positions.front() = std::numeric_limits<std::uint32_t>::max();
    positions.back() = std::numeric_limits<std::uint32_t>::max();
}

bool Scratch::canaries_intact() const {
    return
        is_native_canary(native_masks.front()) &&
        is_native_canary(native_masks.back()) &&
        integral_masks.front() == std::numeric_limits<IntegralMask>::max() &&
        integral_masks.back() == std::numeric_limits<IntegralMask>::max() &&
        bit_masks.front() == std::numeric_limits<BitMask>::max() &&
        bit_masks.back() == std::numeric_limits<BitMask>::max() &&
        positions.front() == std::numeric_limits<std::uint32_t>::max() &&
        positions.back() == std::numeric_limits<std::uint32_t>::max();
}

bool run_correctness_suite() {
    const std::array<std::size_t, 11> rows = {
        0,
        1,
        PIPCOST_SIMD_LANES - 1,
        PIPCOST_SIMD_LANES,
        PIPCOST_SIMD_LANES + 1,
        2 * PIPCOST_SIMD_LANES - 1,
        2 * PIPCOST_SIMD_LANES,
        31,
        64,
        1003,
        4097,
    };
    const std::array<double, 3> selectivities = {0.0, 0.5, 1.0};
    const std::array<const char*, 2> patterns = {"random", "clustered"};

    for (const auto count : rows) {
        for (const auto first : selectivities) {
            for (const auto conditional : selectivities) {
                for (const auto* pattern : patterns) {
                    const auto data = generate_data(
                        DataSpec{count, first, conditional, pattern, 91});
                    const auto expected = scalar_reference(data);
                    const std::array<std::size_t, 4> batches = {
                        1,
                        std::max<std::size_t>(PIPCOST_SIMD_LANES - 1, 1),
                        PIPCOST_SIMD_LANES * 2,
                        std::max<std::size_t>(count, 1),
                    };
                    for (const auto batch : batches) {
                        QueryView query{
                            data.a.data(),
                            data.b.data(),
                            data.c.data(),
                            count,
                            batch,
                            data.p1,
                            data.p2,
                        };
                        for (const auto& plan : plan_registry()) {
                            if (!plan.supported) {
                                continue;
                            }
                            Scratch scratch(count);
                            const auto actual = plan.function(query, scratch);
                            if (actual.sum != expected || !scratch.canaries_intact()) {
                                return false;
                            }
                        }
                    }
                }
            }
        }
    }
    return true;
}

}  // namespace pipcost
