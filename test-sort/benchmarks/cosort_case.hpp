#pragma once

// One measured case: the data it sorts, and the oracle it is checked against.
//
// Data comes from `TslDatasetSource`, so a dataset and its reference image are
// generated once per process and reused by every variant, worker count and
// threshold that shares them. Nothing is read from or written to disk.
//
// The oracle is a byte comparison against the reference image, not the
// lexicographic order invariant. With every column a sort key, two rows that tie
// are byte-identical, so the sorted image is unique however an unstable sort
// breaks ties; `memcmp` is therefore exact where the order invariant is blind to
// a lost row, a duplicated row, or a column permuted independently of the others.

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_reference.hpp"
#include "datagen/dataset_source.hpp"
#include "sorting/quicksort/multicolumn_quicksort.hpp"

// --- working-set sizes ------------------------------------------------------

struct TslCacheSizes {
  std::uint64_t l1 = 32 * 1024;
  std::uint64_t l2 = 1024 * 1024;
  std::uint64_t llc = 8 * 1024 * 1024;
};

inline auto tsl_parse_cache_size(std::string const & text) -> std::uint64_t {
  if (text.empty()) return 0;
  auto const value = std::strtoull(text.c_str(), nullptr, 10);
  switch (text.back()) {
    case 'K': case 'k': return value * 1024ull;
    case 'M': case 'm': return value * 1024ull * 1024ull;
    case 'G': case 'g': return value * 1024ull * 1024ull * 1024ull;
    default: return value;
  }
}

inline auto tsl_detect_caches() -> TslCacheSizes {
  TslCacheSizes caches;
  auto const read = [](std::string const & path) {
    std::ifstream stream(path);
    std::string value;
    if (stream) std::getline(stream, value);
    return value;
  };
  for (int index = 0; index < 10; ++index) {
    auto const base = "/sys/devices/system/cpu/cpu0/cache/index" + std::to_string(index);
    auto const level_text = read(base + "/level");
    if (level_text.empty()) continue;
    auto const level = std::strtol(level_text.c_str(), nullptr, 10);
    auto const type = read(base + "/type");
    auto const size = tsl_parse_cache_size(read(base + "/size"));
    if (size == 0) continue;
    if (level == 1 && type == "Data") caches.l1 = size;
    else if (level == 2) caches.l2 = size;
    else if (level >= 3) caches.llc = size;
  }
  return caches;
}

struct TslSizeLevel {
  char const * name;
  std::uint64_t per_column_bytes;
};

// Bytes per column, not aggregate footprint: a cross-width comparison then holds
// bytes constant and row count differs, which is the convention every plot must
// state.
inline auto tsl_size_levels(TslCacheSizes const & caches) -> std::vector<TslSizeLevel> {
  return {
    {"L1", caches.l1},
    {"L2", caches.l2},
    {"halfLLC", caches.llc / 2},
    {"LLC", caches.llc},
    {"2xLLC", caches.llc * 2},
    {"16xLLC", caches.llc * 16},
  };
}

// --- dataset selection ------------------------------------------------------

// A selector is a prefix of a generated dataset id, so it names a shape together
// with its parameters: `unique_last_g64` matches only that terminal group size.
// An empty selector list accepts the whole catalog.
inline auto tsl_select_datasets(
  std::vector<TslDatasetSpec> const & catalog,
  std::vector<std::string> const & selectors,
  std::size_t element_bytes
) -> std::vector<TslDatasetSpec> {
  if (selectors.empty()) {
    return catalog;
  }
  auto const tail = "_u" + std::to_string(element_bytes * 8) + "_n";
  std::vector<TslDatasetSpec> chosen;
  for (auto const & selector : selectors) {
    for (auto const & spec : catalog) {
      if (spec.id.rfind(selector + tail, 0) == 0) {
        chosen.push_back(spec);
      }
    }
  }
  return chosen;
}

// Short label for the benchmark name: shape plus its parameters, without the
// element width, row count and column count that other name components carry.
inline auto tsl_dataset_label(TslDatasetSpec const & spec) -> std::string {
  auto const tail = "_u" + std::to_string(spec.element_bytes * 8) + "_n";
  auto const cut = spec.id.find(tail);
  return cut == std::string::npos ? spec.id : spec.id.substr(0, cut);
}

inline auto tsl_dataset_params(TslDatasetSpec const & spec) -> std::string {
  std::string text;
  for (auto const & entry : spec.params) {
    if (!text.empty()) text += ",";
    text += entry.first + "=";
    auto value = std::to_string(entry.second);
    // Trim the trailing zeros std::to_string leaves on an integral double.
    while (value.size() > 1 && value.back() == '0') value.pop_back();
    if (!value.empty() && value.back() == '.') value.pop_back();
    text += value;
  }
  return text.empty() ? "none" : text;
}

// --- the case ---------------------------------------------------------------

template <class DataType>
auto tsl_shared_source(std::size_t budget_bytes) -> TslDatasetSource<DataType> & {
  static TslDatasetSource<DataType> source(budget_bytes);
  return source;
}

template <class DataType>
class TslBenchCase {
 public:
  TslBenchCase(TslDatasetSpec const & spec, TslDirection direction, std::size_t budget_bytes)
      : spec_(spec), direction_(direction) {
    auto & source = tsl_shared_source<DataType>(budget_bytes);
    pristine_ = source.pristine(spec_);
    reference_ = source.reference(spec_, direction_);
    auto const ascending = tsl_direction_ascending(direction_, pristine_->size());
    work_.assign(pristine_->begin(), pristine_->end());
    for (std::size_t column = 0; column < work_.size(); ++column) {
      orders_.push_back(ascending[column] ? TslSortOrder::ASCENDING : TslSortOrder::DESCENDING);
    }
    specs_.resize(work_.size());
    refresh();
  }

  // Restores the input. Vector assignment may reallocate, so the sorter's column
  // pointers are refreshed with it.
  void reset() {
    for (std::size_t column = 0; column < work_.size(); ++column) {
      work_[column] = (*pristine_)[column];
    }
    refresh();
  }

  auto specs() -> TslSortColumn<DataType> * { return specs_.data(); }
  auto column_count() const -> std::size_t { return work_.size(); }
  auto rows() const -> std::size_t { return work_.empty() ? 0 : work_.front().size(); }

  // Row-index buffer for the indirect sorter. Allocated on first use so the
  // direct cases never pay for it; the sorter fills it with the identity itself.
  auto index() -> DataType * {
    if (index_.size() != rows()) {
      index_.assign(rows(), 0);
    }
    return index_.data();
  }

  // Oracle for the indirect sorter, which leaves the columns alone and produces
  // a permutation instead. The permutation is not unique -- tied rows may come
  // out in any order -- so this compares the values it selects against the
  // reference image, which is unique because every column is a sort key.
  auto verify_index() const -> std::string {
    if (index_.size() != rows()) {
      return "index buffer was never produced";
    }
    for (std::size_t column = 0; column < work_.size(); ++column) {
      auto const & source = work_[column];
      auto const & expected = (*reference_)[column];
      for (std::size_t row = 0; row < index_.size(); ++row) {
        auto const selected = source[static_cast<std::size_t>(index_[row])];
        if (selected != expected[row]) {
          return "permutation selects the wrong value at column " + std::to_string(column)
               + ", row " + std::to_string(row);
        }
      }
    }
    return {};
  }

  // Exact oracle. Returns an empty string on success, else what differed.
  auto verify() const -> std::string {
    auto const [column, row] = tsl_first_difference(work_, *reference_);
    if (column == work_.size()) {
      return {};
    }
    return "output differs from the reference image at column " + std::to_string(column)
         + ", row " + std::to_string(row);
  }

 private:
  void refresh() {
    for (std::size_t column = 0; column < work_.size(); ++column) {
      specs_[column] = {work_[column].data(), orders_[column]};
    }
  }

  TslDatasetSpec spec_;
  TslDirection direction_;
  typename TslDatasetSource<DataType>::Handle pristine_;
  typename TslDatasetSource<DataType>::Handle reference_;
  std::vector<std::vector<DataType>> work_;
  std::vector<DataType> index_;
  std::vector<TslSortOrder> orders_;
  std::vector<TslSortColumn<DataType>> specs_;
};
