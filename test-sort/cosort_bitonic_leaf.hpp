#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <type_traits>
#include <vector>

#include <tsl.hpp>

#include "multicolumn_sort_types.hpp"


// -----------------------------------------------------------------------------
// Co-sorting bitonic leaf (prototype).
//
// A flat sorting network needs register lane permutations; TSL exposes them as
// tsl::permute_lanes (tsldata misc/swizzle.tsl), so this leaf is TSL-native and
// works for any element type whose native SIMD width is a power of two (tested
// for u32 and u64). It sorts up to `capacity` elements with an ascending Batcher
// bitonic network, precomputing the per-comparator control (permutation index
// vectors and take-max masks) once instead of rebuilding it every call, and
// co-sorts a runtime number of payload columns via record-and-replay: the key
// sort records each comparator's exchange mask, and every payload column replays
// those masks (permute + blend). Shorter inputs are padded with the type max.
// Descending output copies the valid key and payload ranges out in reverse
// order; this avoids both an extra in-place reverse pass and treating an
// in-band type minimum as distinguishable padding.
//
// `rows` is fixed so the resident key bank stays within the register file; the
// capacity therefore scales with the chosen extension's lane count -- e.g. u32:
// 256 (16 lanes) / 128 (8) / 64 (4); u64: 128 (8) / 64 (4) / 32 (2). SimdStyle
// selects the extension, defaulting to the native (widest) one.
// -----------------------------------------------------------------------------
template <class DataType = std::uint32_t,
          class SimdStyle = tsl::dataparallel::simd_for_t<tsl::dataparallel::native, DataType>>
class TslCoSortBitonicLeaf {
  using Vec = SimdStyle;
  static_assert(std::is_same_v<typename SimdStyle::base_type, DataType>,
                "SimdStyle::base_type must match DataType");
  using register_type = typename Vec::register_type;
  using mask_type = typename Vec::mask_type;
  using imask_type = typename Vec::imask_type;

  static constexpr std::size_t lanes = Vec::lane_count_v;
  static constexpr std::size_t rows = 16;
  static_assert((lanes & (lanes - 1)) == 0, "lane count must be a power of two");

  static constexpr std::size_t log2_of(std::size_t value) {
    std::size_t result = 0;
    while (value > 1) { value >>= 1; ++result; }
    return result;
  }
  static constexpr std::size_t perm_count = log2_of(lanes);  // intra strides 1 .. lanes/2

 public:
  static constexpr std::size_t capacity = lanes * rows;

 private:
  static constexpr std::size_t count_comparators() {
    std::size_t comparators = 0;
    for (std::size_t span = 2; span <= capacity; span <<= 1) {
      for (std::size_t stride = span >> 1; stride != 0; stride >>= 1) {
        if (stride < lanes) {
          comparators += rows;
        } else {
          for (std::size_t row = 0; row < rows; ++row) {
            if ((row ^ (stride / lanes)) > row) ++comparators;
          }
        }
      }
    }
    return comparators;
  }
  static constexpr std::size_t comparator_count = count_comparators();

  struct bitonic_op {
    bool intra;
    std::uint8_t row;
    std::uint8_t partner;   // cross only
    bool ascending;         // cross only
    std::uint8_t perm_id;   // intra only (stride = 1 << perm_id)
    mask_type take_max;     // intra only
  };

  static auto intra_perms() -> std::array<register_type, perm_count> const & {
    static std::array<register_type, perm_count> const perms = [] {
      std::array<register_type, perm_count> result{};
      alignas(64) std::array<DataType, lanes> buffer{};
      for (std::size_t id = 0; id < perm_count; ++id) {
        auto const stride = std::size_t{1} << id;
        for (std::size_t lane = 0; lane < lanes; ++lane) {
          buffer[lane] = static_cast<DataType>(lane ^ stride);
        }
        result[id] = tsl::load<Vec, true>(buffer.data());
      }
      return result;
    }();
    return perms;
  }

  static auto ops() -> std::vector<bitonic_op> const & {
    static std::vector<bitonic_op> const table = [] {
      std::vector<bitonic_op> result;
      for (std::size_t span = 2; span <= capacity; span <<= 1) {
        for (std::size_t stride = span >> 1; stride != 0; stride >>= 1) {
          if (stride < lanes) {
            auto const perm_id = static_cast<std::uint8_t>(log2_of(stride));
            for (std::size_t row = 0; row < rows; ++row) {
              imask_type take_max = 0;
              for (std::size_t lane = 0; lane < lanes; ++lane) {
                auto const global_index = row * lanes + lane;
                bool const ascending = (global_index & span) == 0;
                bool const lower_endpoint = (global_index & stride) == 0;
                if (ascending ? !lower_endpoint : lower_endpoint) {
                  take_max |= static_cast<imask_type>(imask_type{1} << lane);
                }
              }
              result.push_back({true, static_cast<std::uint8_t>(row), 0, false, perm_id, tsl::to_mask<Vec>(take_max)});
            }
          } else {
            auto const row_distance = stride / lanes;
            for (std::size_t row = 0; row < rows; ++row) {
              auto const partner = row ^ row_distance;
              if (row >= partner) continue;
              bool const ascending = ((row * lanes) & span) == 0;
              result.push_back({false, static_cast<std::uint8_t>(row), static_cast<std::uint8_t>(partner), ascending, 0, tsl::mask_false<Vec>()});
            }
          }
        }
      }
      return result;
    }();
    return table;
  }

  static void load_block(register_type * bank, DataType const * buffer) {
    for (std::size_t row = 0; row < rows; ++row) bank[row] = tsl::load<Vec, true>(buffer + row * lanes);
  }
  static void store_block(DataType * buffer, register_type const * bank) {
    for (std::size_t row = 0; row < rows; ++row) tsl::store<Vec, true>(buffer + row * lanes, bank[row]);
  }

 public:
  template <TslSortOrder Order = TslSortOrder::ASCENDING>
  static void sort(DataType * keys, DataType * const * columns, std::size_t column_count, std::size_t count) {
    if (count < 2) return;

    auto const & operations = ops();
    std::array<mask_type, comparator_count> exchange{};

    alignas(64) std::array<DataType, capacity> buffer;
    buffer.fill(std::numeric_limits<DataType>::max());
    for (std::size_t index = 0; index < count; ++index) buffer[index] = keys[index];

    register_type bank[rows];
    load_block(bank, buffer.data());
    std::size_t op_index = 0;
    for (auto const & op : operations) {
      if (op.intra) {
        auto const value = bank[op.row];
        auto const partner = tsl::permute_lanes<Vec, Vec>(value, intra_perms()[op.perm_id]);
        auto const minimum = tsl::min<Vec>(value, partner);
        auto const maximum = tsl::max<Vec>(value, partner);
        auto const result = tsl::blend<Vec>(op.take_max, minimum, maximum);
        exchange[op_index++] = tsl::nequal<Vec>(result, value);
        bank[op.row] = result;
      } else {
        auto const a = bank[op.row];
        auto const b = bank[op.partner];
        auto const minimum = tsl::min<Vec>(a, b);
        auto const maximum = tsl::max<Vec>(a, b);
        auto const new_row = op.ascending ? minimum : maximum;
        auto const new_partner = op.ascending ? maximum : minimum;
        exchange[op_index++] = tsl::nequal<Vec>(new_row, a);
        bank[op.row] = new_row;
        bank[op.partner] = new_partner;
      }
    }
    store_block(buffer.data(), bank);
    if constexpr (Order == TslSortOrder::DESCENDING) {
      for (std::size_t index = 0; index < count; ++index) {
        keys[index] = buffer[count - 1 - index];
      }
    } else {
      for (std::size_t index = 0; index < count; ++index) {
        keys[index] = buffer[index];
      }
    }

    for (std::size_t column = 0; column < column_count; ++column) {
      alignas(64) std::array<DataType, capacity> payload;
      payload.fill(DataType{0});
      for (std::size_t index = 0; index < count; ++index) payload[index] = columns[column][index];
      register_type pay_bank[rows];
      load_block(pay_bank, payload.data());
      std::size_t replay = 0;
      for (auto const & op : operations) {
        if (op.intra) {
          auto const value = pay_bank[op.row];
          auto const partner = tsl::permute_lanes<Vec, Vec>(value, intra_perms()[op.perm_id]);
          pay_bank[op.row] = tsl::blend<Vec>(exchange[replay++], value, partner);
        } else {
          auto const a = pay_bank[op.row];
          auto const b = pay_bank[op.partner];
          auto const mask = exchange[replay++];
          pay_bank[op.row] = tsl::blend<Vec>(mask, a, b);
          pay_bank[op.partner] = tsl::blend<Vec>(mask, b, a);
        }
      }
      store_block(payload.data(), pay_bank);
      if constexpr (Order == TslSortOrder::DESCENDING) {
        for (std::size_t index = 0; index < count; ++index) {
          columns[column][index] = payload[count - 1 - index];
        }
      } else {
        for (std::size_t index = 0; index < count; ++index) {
          columns[column][index] = payload[index];
        }
      }
    }
  }
};
