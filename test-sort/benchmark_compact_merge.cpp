#include <immintrin.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <new>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

struct config {
  std::size_t cases = 200'000;
  std::size_t trials = 7;
  std::uint64_t seed = 0x9e3779b97f4a7c15ULL;
};

struct case_u64 {
  __mmask8 low_mask;
  __mmask8 mid_mask;
  __mmask8 high_mask;
  int low_count;
  int mid_count;
  int high_count;
};

struct case_u32 {
  __mmask16 low_mask;
  __mmask16 mid_mask;
  __mmask16 high_mask;
  int low_count;
  int mid_count;
  int high_count;
};

auto parse_args(int argc, char ** argv) -> config {
  config result;
  for (int arg = 1; arg < argc; ++arg) {
    auto const current = std::string(argv[arg]);
    auto require_value = [&](char const * option) -> char const * {
      if (arg + 1 >= argc) {
        throw std::runtime_error(std::string("missing value for ") + option);
      }
      return argv[++arg];
    };

    if (current == "--cases") {
      result.cases = static_cast<std::size_t>(std::stoull(require_value("--cases")));
    } else if (current == "--trials") {
      result.trials = static_cast<std::size_t>(std::stoull(require_value("--trials")));
    } else if (current == "--seed") {
      result.seed = static_cast<std::uint64_t>(std::stoull(require_value("--seed"), nullptr, 0));
    } else if (current == "-h" || current == "--help") {
      std::cout
        << "Usage: benchmark_compact_merge [--cases N] [--trials N] [--seed N]\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + current);
    }
  }
  if (result.cases == 0 || result.trials == 0) {
    throw std::runtime_error("--cases and --trials must be positive");
  }
  return result;
}

auto popcount8(__mmask8 mask) -> int {
  return __builtin_popcount(static_cast<unsigned>(mask));
}

auto popcount16(__mmask16 mask) -> int {
  return __builtin_popcount(static_cast<unsigned>(mask));
}

auto low_mask8(int count) -> __mmask8 {
  return count >= 8 ? static_cast<__mmask8>(0xffu) : static_cast<__mmask8>((1u << count) - 1u);
}

auto low_mask16(int count) -> __mmask16 {
  return count >= 16 ? static_cast<__mmask16>(0xffffu) : static_cast<__mmask16>((1u << count) - 1u);
}

auto lane_mask8(int offset, int count) -> __mmask8 {
  return static_cast<__mmask8>(static_cast<unsigned>(low_mask8(count)) << offset);
}

auto lane_mask16(int offset, int count) -> __mmask16 {
  return static_cast<__mmask16>(static_cast<unsigned>(low_mask16(count)) << offset);
}

template <std::size_t LaneCount, class Mask>
auto random_mask_with_count(std::mt19937_64 & rng, int count) -> Mask {
  std::array<int, LaneCount> lanes{};
  for (std::size_t lane = 0; lane < LaneCount; ++lane) {
    lanes[lane] = static_cast<int>(lane);
  }
  std::shuffle(lanes.begin(), lanes.end(), rng);

  unsigned mask = 0;
  for (int index = 0; index < count; ++index) {
    mask |= 1u << lanes[static_cast<std::size_t>(index)];
  }
  return static_cast<Mask>(mask);
}

auto make_cases_u64(std::size_t count, std::uint64_t seed) -> std::vector<case_u64> {
  std::mt19937_64 rng(seed);
  std::vector<case_u64> cases;
  cases.reserve(count);
  for (std::size_t i = 0; i < count; ++i) {
    std::uniform_int_distribution<int> first_dist(0, 8);
    auto const low_count = first_dist(rng);
    std::uniform_int_distribution<int> second_dist(0, 8 - low_count);
    auto const mid_count = second_dist(rng);
    auto const high_count = 8 - low_count - mid_count;
    auto const low_mask = random_mask_with_count<8, __mmask8>(rng, low_count);
    auto const mid_mask = random_mask_with_count<8, __mmask8>(rng, mid_count);
    auto const high_mask = random_mask_with_count<8, __mmask8>(rng, high_count);
    cases.push_back({low_mask, mid_mask, high_mask, low_count, mid_count, high_count});
  }
  return cases;
}

auto make_cases_u32(std::size_t count, std::uint64_t seed) -> std::vector<case_u32> {
  std::mt19937_64 rng(seed);
  std::vector<case_u32> cases;
  cases.reserve(count);
  for (std::size_t i = 0; i < count; ++i) {
    std::uniform_int_distribution<int> first_dist(0, 16);
    auto const low_count = first_dist(rng);
    std::uniform_int_distribution<int> second_dist(0, 16 - low_count);
    auto const mid_count = second_dist(rng);
    auto const high_count = 16 - low_count - mid_count;
    auto const low_mask = random_mask_with_count<16, __mmask16>(rng, low_count);
    auto const mid_mask = random_mask_with_count<16, __mmask16>(rng, mid_count);
    auto const high_mask = random_mask_with_count<16, __mmask16>(rng, high_count);
    cases.push_back({low_mask, mid_mask, high_mask, low_count, mid_count, high_count});
  }
  return cases;
}

auto compact_valid_mask8(__mmask8 mask) -> __mmask8 {
  alignas(64) static constexpr auto masks = [] {
    std::array<std::uint8_t, 1u << 8> result{};
    for (unsigned mask_value = 0; mask_value < (1u << 8); ++mask_value) {
      auto const count = __builtin_popcount(mask_value);
      result[mask_value] = static_cast<std::uint8_t>((1u << count) - 1u);
    }
    return result;
  }();
  return static_cast<__mmask8>(masks[mask]);
}

auto compact_valid_mask16(__mmask16 mask) -> __mmask16 {
  alignas(64) static constexpr auto masks = [] {
    std::array<std::uint16_t, 1u << 16> result{};
    for (unsigned mask_value = 0; mask_value < (1u << 16); ++mask_value) {
      auto const count = __builtin_popcount(mask_value);
      result[mask_value] = static_cast<std::uint16_t>((1u << count) - 1u);
    }
    return result;
  }();
  return static_cast<__mmask16>(masks[mask]);
}

auto compact_index_lanes_u64(__mmask8 in_mask, int offset = 0) -> __m512i {
  constexpr std::size_t lane_count = 8;
  constexpr std::size_t offset_count = lane_count + 1;
  constexpr std::size_t mask_count = 1u << lane_count;

  alignas(64) static constexpr auto permutation = [] {
    std::array<std::uint64_t, offset_count * mask_count * lane_count> result{};
    for (std::size_t current_offset = 0; current_offset < offset_count; ++current_offset) {
      for (std::size_t mask = 0; mask < mask_count; ++mask) {
        auto const base = current_offset * mask_count * lane_count + mask * lane_count;
        auto output_lane = current_offset;
        for (std::size_t input_lane = 0; input_lane < lane_count && output_lane < lane_count; ++input_lane) {
          if ((mask & (std::size_t{1} << input_lane)) != 0) {
            result[base + output_lane] = input_lane;
            ++output_lane;
          }
        }
      }
    }
    return result;
  }();

  auto const base =
    static_cast<std::size_t>(offset) * mask_count * lane_count
    + static_cast<std::size_t>(in_mask) * lane_count;
  return _mm512_load_si512(permutation.data() + base);
}

auto compact_index_lanes_u32(__mmask16 in_mask, int offset = 0) -> __m512i {
  constexpr std::size_t lane_count = 16;
  constexpr std::size_t offset_count = lane_count + 1;
  constexpr std::size_t mask_count = 1u << lane_count;
  constexpr std::size_t table_entries = offset_count * mask_count * lane_count;
  constexpr std::size_t table_bytes = table_entries * sizeof(std::uint32_t);

  static auto const table = [] {
    auto * memory = static_cast<std::uint32_t *>(std::aligned_alloc(64, table_bytes));
    if (memory == nullptr) {
      throw std::bad_alloc{};
    }
    std::memset(memory, 0, table_bytes);
    for (std::size_t current_offset = 0; current_offset < offset_count; ++current_offset) {
      for (std::size_t mask = 0; mask < mask_count; ++mask) {
        auto const base = current_offset * mask_count * lane_count + mask * lane_count;
        auto output_lane = current_offset;
        for (std::size_t input_lane = 0; input_lane < lane_count && output_lane < lane_count; ++input_lane) {
          if ((mask & (std::size_t{1} << input_lane)) != 0) {
            memory[base + output_lane] = static_cast<std::uint32_t>(input_lane);
            ++output_lane;
          }
        }
      }
    }
    return memory;
  }();

  auto const base =
    static_cast<std::size_t>(offset) * mask_count * lane_count
    + static_cast<std::size_t>(in_mask) * lane_count;
  return _mm512_load_si512(table + base);
}

auto compact_index_lanes_u32_u8offset(__mmask16 in_mask, int offset = 0) -> __m512i {
  constexpr std::size_t lane_count = 16;
  constexpr std::size_t offset_count = lane_count + 1;
  constexpr std::size_t mask_count = 1u << lane_count;
  constexpr std::size_t table_entries = offset_count * mask_count * lane_count;
  constexpr std::size_t table_bytes = table_entries * sizeof(std::uint8_t);

  static auto const table = [] {
    auto * memory = static_cast<std::uint8_t *>(std::aligned_alloc(64, table_bytes));
    if (memory == nullptr) {
      throw std::bad_alloc{};
    }
    std::memset(memory, 0, table_bytes);
    for (std::size_t current_offset = 0; current_offset < offset_count; ++current_offset) {
      for (std::size_t mask = 0; mask < mask_count; ++mask) {
        auto const base = current_offset * mask_count * lane_count + mask * lane_count;
        auto output_lane = current_offset;
        for (std::size_t input_lane = 0; input_lane < lane_count && output_lane < lane_count; ++input_lane) {
          if ((mask & (std::size_t{1} << input_lane)) != 0) {
            memory[base + output_lane] = static_cast<std::uint8_t>(input_lane);
            ++output_lane;
          }
        }
      }
    }
    return memory;
  }();

  auto const base =
    static_cast<std::size_t>(offset) * mask_count * lane_count
    + static_cast<std::size_t>(in_mask) * lane_count;
  auto const indices8 = _mm_loadu_si128(reinterpret_cast<__m128i const *>(table + base));
  return _mm512_cvtepu8_epi32(indices8);
}

auto compact_index_lanes_u32_split8(__mmask8 in_mask, int offset, int source_base) -> __m512i {
  constexpr std::size_t lane_count = 16;
  constexpr std::size_t half_lane_count = 8;
  constexpr std::size_t source_half_count = 2;
  constexpr std::size_t offset_count = lane_count + 1;
  constexpr std::size_t mask_count = 1u << half_lane_count;
  constexpr std::size_t table_entries =
    source_half_count * offset_count * mask_count * lane_count;
  constexpr std::size_t table_bytes = table_entries * sizeof(std::uint8_t);

  static auto const table = [] {
    auto * memory = static_cast<std::uint8_t *>(std::aligned_alloc(64, table_bytes));
    if (memory == nullptr) {
      throw std::bad_alloc{};
    }
    std::memset(memory, 0, table_bytes);
    for (std::size_t source_half = 0; source_half < source_half_count; ++source_half) {
      auto const current_source_base = source_half * half_lane_count;
      for (std::size_t current_offset = 0; current_offset < offset_count; ++current_offset) {
        for (std::size_t mask = 0; mask < mask_count; ++mask) {
          auto const base =
            source_half * offset_count * mask_count * lane_count
            + current_offset * mask_count * lane_count
            + mask * lane_count;
          auto output_lane = current_offset;
          for (std::size_t input_lane = 0; input_lane < half_lane_count && output_lane < lane_count; ++input_lane) {
            if ((mask & (std::size_t{1} << input_lane)) != 0) {
              memory[base + output_lane] = static_cast<std::uint8_t>(current_source_base + input_lane);
              ++output_lane;
            }
          }
        }
      }
    }
    return memory;
  }();

  auto const source_half = static_cast<std::size_t>(source_base != 0);
  auto const base =
    source_half * offset_count * mask_count * lane_count
    + static_cast<std::size_t>(offset) * mask_count * lane_count
    + static_cast<std::size_t>(in_mask) * lane_count;
  auto const indices8 = _mm_loadu_si128(reinterpret_cast<__m128i const *>(table + base));
  return _mm512_cvtepu8_epi32(indices8);
}

auto compact_merge_table_u64(
  __mmask8 low_mask,
  __m512i low_data,
  int low_count,
  __mmask8 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask8 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = _mm512_permutexvar_epi64(compact_index_lanes_u64(low_mask), low_data);
  auto const compact_mid = _mm512_permutexvar_epi64(compact_index_lanes_u64(mid_mask, low_count), mid_data);
  auto const compact_high = _mm512_permutexvar_epi64(compact_index_lanes_u64(high_mask, low_count + mid_count), high_data);
  auto const packed_low_mask = compact_valid_mask8(low_mask);
  auto const packed_high_mask = static_cast<__mmask8>(compact_valid_mask8(high_mask) << (low_count + mid_count));
  (void)high_count;
  return _mm512_mask_blend_epi64(
    packed_high_mask,
    _mm512_mask_blend_epi64(packed_low_mask, compact_mid, compact_low),
    compact_high
  );
}

auto compact_merge_table_u32(
  __mmask16 low_mask,
  __m512i low_data,
  int low_count,
  __mmask16 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask16 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = _mm512_permutexvar_epi32(compact_index_lanes_u32(low_mask), low_data);
  auto const compact_mid = _mm512_permutexvar_epi32(compact_index_lanes_u32(mid_mask, low_count), mid_data);
  auto const compact_high = _mm512_permutexvar_epi32(compact_index_lanes_u32(high_mask, low_count + mid_count), high_data);
  auto const packed_low_mask = compact_valid_mask16(low_mask);
  auto const packed_high_mask = static_cast<__mmask16>(compact_valid_mask16(high_mask) << (low_count + mid_count));
  (void)high_count;
  return _mm512_mask_blend_epi32(
    packed_high_mask,
    _mm512_mask_blend_epi32(packed_low_mask, compact_mid, compact_low),
    compact_high
  );
}

auto compact_merge_table_u32_u8offset(
  __mmask16 low_mask,
  __m512i low_data,
  int low_count,
  __mmask16 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask16 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = _mm512_permutexvar_epi32(compact_index_lanes_u32_u8offset(low_mask), low_data);
  auto const compact_mid = _mm512_permutexvar_epi32(compact_index_lanes_u32_u8offset(mid_mask, low_count), mid_data);
  auto const compact_high = _mm512_permutexvar_epi32(compact_index_lanes_u32_u8offset(high_mask, low_count + mid_count), high_data);
  auto const packed_low_mask = compact_valid_mask16(low_mask);
  auto const packed_high_mask = static_cast<__mmask16>(compact_valid_mask16(high_mask) << (low_count + mid_count));
  (void)high_count;
  return _mm512_mask_blend_epi32(
    packed_high_mask,
    _mm512_mask_blend_epi32(packed_low_mask, compact_mid, compact_low),
    compact_high
  );
}

auto compact_group_split8_u32(
  __mmask16 mask,
  __m512i data,
  int offset,
  int count
) -> __m512i {
  auto const lower_mask = static_cast<__mmask8>(mask & 0xffu);
  auto const upper_mask = static_cast<__mmask8>((mask >> 8) & 0xffu);
  auto const lower_count = popcount8(lower_mask);
  auto const upper_count = count - lower_count;

  auto const lower_indices = compact_index_lanes_u32_split8(lower_mask, offset, 0);
  auto const upper_indices = compact_index_lanes_u32_split8(upper_mask, offset + lower_count, 8);
  auto const lower_part = _mm512_maskz_permutexvar_epi32(
    lane_mask16(offset, lower_count),
    lower_indices,
    data
  );
  auto const upper_part = _mm512_maskz_permutexvar_epi32(
    lane_mask16(offset + lower_count, upper_count),
    upper_indices,
    data
  );
  return _mm512_or_si512(lower_part, upper_part);
}

auto compact_merge_table_u32_split8(
  __mmask16 low_mask,
  __m512i low_data,
  int low_count,
  __mmask16 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask16 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = compact_group_split8_u32(
    low_mask,
    low_data,
    0,
    low_count
  );
  auto const compact_mid = compact_group_split8_u32(
    mid_mask,
    mid_data,
    low_count,
    mid_count
  );
  auto const compact_high = compact_group_split8_u32(
    high_mask,
    high_data,
    low_count + mid_count,
    high_count
  );
  return _mm512_or_si512(
    _mm512_or_si512(compact_low, compact_mid),
    compact_high
  );
}

auto compact_merge_native_u64(
  __mmask8 low_mask,
  __m512i low_data,
  int low_count,
  __mmask8 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask8 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = _mm512_maskz_compress_epi64(low_mask, low_data);
  auto const compact_mid = _mm512_maskz_compress_epi64(mid_mask, mid_data);
  auto const compact_high = _mm512_maskz_compress_epi64(high_mask, high_data);
  auto result = compact_low;
  result = _mm512_mask_expand_epi64(result, lane_mask8(low_count, mid_count), compact_mid);
  result = _mm512_mask_expand_epi64(result, lane_mask8(low_count + mid_count, high_count), compact_high);
  return result;
}

auto compact_merge_native_u32(
  __mmask16 low_mask,
  __m512i low_data,
  int low_count,
  __mmask16 mid_mask,
  __m512i mid_data,
  int mid_count,
  __mmask16 high_mask,
  __m512i high_data,
  int high_count
) -> __m512i {
  auto const compact_low = _mm512_maskz_compress_epi32(low_mask, low_data);
  auto const compact_mid = _mm512_maskz_compress_epi32(mid_mask, mid_data);
  auto const compact_high = _mm512_maskz_compress_epi32(high_mask, high_data);
  auto result = compact_low;
  result = _mm512_mask_expand_epi32(result, lane_mask16(low_count, mid_count), compact_mid);
  result = _mm512_mask_expand_epi32(result, lane_mask16(low_count + mid_count, high_count), compact_high);
  return result;
}

auto checksum_u64(__m512i value) -> std::uint64_t {
  alignas(64) std::array<std::uint64_t, 8> lanes{};
  _mm512_store_si512(lanes.data(), value);
  std::uint64_t result = 1469598103934665603ULL;
  for (auto const lane : lanes) {
    result ^= lane;
    result *= 1099511628211ULL;
  }
  return result;
}

auto checksum_u32(__m512i value) -> std::uint64_t {
  alignas(64) std::array<std::uint32_t, 16> lanes{};
  _mm512_store_si512(lanes.data(), value);
  std::uint64_t result = 1469598103934665603ULL;
  for (auto const lane : lanes) {
    result ^= lane;
    result *= 1099511628211ULL;
  }
  return result;
}

template <class Case, class Fn>
auto measure_u64(std::vector<Case> const & cases, Fn fn) -> std::pair<std::uint64_t, std::uint64_t> {
  auto const low_data = _mm512_set_epi64(107, 106, 105, 104, 103, 102, 101, 100);
  auto const mid_data = _mm512_set_epi64(207, 206, 205, 204, 203, 202, 201, 200);
  auto const high_data = _mm512_set_epi64(307, 306, 305, 304, 303, 302, 301, 300);
  auto acc = _mm512_setzero_si512();

  auto const start = std::chrono::steady_clock::now();
  for (auto const & c : cases) {
    auto const value = fn(
      c.low_mask,
      low_data,
      c.low_count,
      c.mid_mask,
      mid_data,
      c.mid_count,
      c.high_mask,
      high_data,
      c.high_count
    );
    acc = _mm512_xor_si512(acc, value);
  }
  auto const stop = std::chrono::steady_clock::now();
  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum_u64(acc)};
}

template <class Case, class Fn>
auto measure_u32(std::vector<Case> const & cases, Fn fn) -> std::pair<std::uint64_t, std::uint64_t> {
  auto const low_data = _mm512_set_epi32(115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100);
  auto const mid_data = _mm512_set_epi32(215, 214, 213, 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200);
  auto const high_data = _mm512_set_epi32(315, 314, 313, 312, 311, 310, 309, 308, 307, 306, 305, 304, 303, 302, 301, 300);
  auto acc = _mm512_setzero_si512();

  auto const start = std::chrono::steady_clock::now();
  for (auto const & c : cases) {
    auto const value = fn(
      c.low_mask,
      low_data,
      c.low_count,
      c.mid_mask,
      mid_data,
      c.mid_count,
      c.high_mask,
      high_data,
      c.high_count
    );
    acc = _mm512_xor_si512(acc, value);
  }
  auto const stop = std::chrono::steady_clock::now();
  auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(stop - start).count();
  return {static_cast<std::uint64_t>(elapsed), checksum_u32(acc)};
}

template <class Case>
void verify_u64(std::vector<Case> const & cases) {
  auto const low_data = _mm512_set_epi64(107, 106, 105, 104, 103, 102, 101, 100);
  auto const mid_data = _mm512_set_epi64(207, 206, 205, 204, 203, 202, 201, 200);
  auto const high_data = _mm512_set_epi64(307, 306, 305, 304, 303, 302, 301, 300);
  for (auto const & c : cases) {
    auto const native = compact_merge_native_u64(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    auto const table = compact_merge_table_u64(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    alignas(64) std::array<std::uint64_t, 8> native_lanes{};
    alignas(64) std::array<std::uint64_t, 8> table_lanes{};
    _mm512_store_si512(native_lanes.data(), native);
    _mm512_store_si512(table_lanes.data(), table);
    if (native_lanes != table_lanes) {
      throw std::runtime_error("u64 table implementation does not match native compress/expand");
    }
  }
}

template <class Case>
void verify_u32(std::vector<Case> const & cases) {
  auto const low_data = _mm512_set_epi32(115, 114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100);
  auto const mid_data = _mm512_set_epi32(215, 214, 213, 212, 211, 210, 209, 208, 207, 206, 205, 204, 203, 202, 201, 200);
  auto const high_data = _mm512_set_epi32(315, 314, 313, 312, 311, 310, 309, 308, 307, 306, 305, 304, 303, 302, 301, 300);
  for (auto const & c : cases) {
    auto const native = compact_merge_native_u32(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    auto const table = compact_merge_table_u32(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    auto const table_u8offset = compact_merge_table_u32_u8offset(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    auto const table_split8 = compact_merge_table_u32_split8(c.low_mask, low_data, c.low_count, c.mid_mask, mid_data, c.mid_count, c.high_mask, high_data, c.high_count);
    alignas(64) std::array<std::uint32_t, 16> native_lanes{};
    alignas(64) std::array<std::uint32_t, 16> table_lanes{};
    alignas(64) std::array<std::uint32_t, 16> table_u8offset_lanes{};
    alignas(64) std::array<std::uint32_t, 16> table_split8_lanes{};
    _mm512_store_si512(native_lanes.data(), native);
    _mm512_store_si512(table_lanes.data(), table);
    _mm512_store_si512(table_u8offset_lanes.data(), table_u8offset);
    _mm512_store_si512(table_split8_lanes.data(), table_split8);
    if (native_lanes != table_lanes) {
      throw std::runtime_error("u32 table implementation does not match native compress/expand");
    }
    if (native_lanes != table_u8offset_lanes) {
      throw std::runtime_error("u32 u8-offset table implementation does not match native compress/expand");
    }
    if (native_lanes != table_split8_lanes) {
      throw std::runtime_error("u32 split8 table implementation does not match native compress/expand");
    }
  }
}

void print_result(char const * lane_type, char const * algorithm, std::size_t cases, std::uint64_t elapsed_ns, std::uint64_t checksum) {
  auto const ns_per_case = static_cast<double>(elapsed_ns) / static_cast<double>(cases);
  std::cout << lane_type << '\t'
            << algorithm << '\t'
            << elapsed_ns << '\t'
            << ns_per_case << '\t'
            << checksum << '\n';
}

} // namespace

int main(int argc, char ** argv) {
  try {
    auto const cfg = parse_args(argc, argv);
    auto const cases_u64 = make_cases_u64(cfg.cases, cfg.seed);
    auto const cases_u32 = make_cases_u32(cfg.cases, cfg.seed ^ 0xbf58476d1ce4e5b9ULL);

    std::cout << "lane_type\talgorithm\telapsed_ns\tns_per_case\tchecksum\n";

    verify_u64(cases_u64);
    verify_u32(cases_u32);

    for (std::size_t trial = 0; trial < cfg.trials; ++trial) {
      auto const [native64_ns, native64_sum] = measure_u64(cases_u64, compact_merge_native_u64);
      auto const [table64_ns, table64_sum] = measure_u64(cases_u64, compact_merge_table_u64);
      auto const [native32_ns, native32_sum] = measure_u32(cases_u32, compact_merge_native_u32);
      auto const [table32_ns, table32_sum] = measure_u32(cases_u32, compact_merge_table_u32);
      auto const [table32_u8offset_ns, table32_u8offset_sum] = measure_u32(cases_u32, compact_merge_table_u32_u8offset);
      auto const [table32_split8_ns, table32_split8_sum] = measure_u32(cases_u32, compact_merge_table_u32_split8);

      print_result("u64x8", "compress_expand", cfg.cases, native64_ns, native64_sum);
      print_result("u64x8", "table_permute", cfg.cases, table64_ns, table64_sum);
      print_result("u32x16", "compress_expand", cfg.cases, native32_ns, native32_sum);
      print_result("u32x16", "table_permute", cfg.cases, table32_ns, table32_sum);
      print_result("u32x16", "table_permute_u8idx", cfg.cases, table32_u8offset_ns, table32_u8offset_sum);
      print_result("u32x16", "table_permute_split8", cfg.cases, table32_split8_ns, table32_split8_sum);
    }
    return 0;
  } catch (std::exception const & error) {
    std::cerr << "benchmark failed: " << error.what() << '\n';
    return 1;
  }
}
