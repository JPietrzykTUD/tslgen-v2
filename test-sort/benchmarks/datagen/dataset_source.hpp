#pragma once

// In-memory dataset provider for consumers that do not want files.
//
// A benchmark sorts the same dataset once per algorithm, per worker count and per
// threshold, so generating it -- and its reference image -- per case would repeat
// work that is far more expensive than the sort being measured. This class
// produces both on first request and keeps them under a byte budget, so a sweep
// pays for a dataset once and reuses it across every case that shares it.
//
//   TslDatasetSource<std::uint32_t> source(8ull << 30);
//   auto const specs = tsl_default_catalog(rows, columns, sizeof(std::uint32_t));
//   auto pristine  = source.pristine(specs[0]);
//   auto reference = source.reference(specs[0], TslDirection::Ascending);
//   // sort a copy of *pristine, then memcmp against *reference
//
// Handles are shared_ptr because a later request may evict an earlier entry; a
// held handle keeps its data alive regardless.
//
// Files remain useful for cross-process and cross-host comparison, and the
// standalone tools still write them. Nothing here reads or writes a file: at the
// sizes where materializing hurts, generation is cheap next to a benchmark run
// (a few seconds for a dataset that will be sorted hundreds of times).

#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_descriptor.hpp"
#include "dataset_reference.hpp"

template <class DataType>
class TslDatasetSource {
 public:
  using Image = std::vector<std::vector<DataType>>;
  using Handle = std::shared_ptr<Image const>;

  explicit TslDatasetSource(std::size_t budget_bytes = 8ull * 1024 * 1024 * 1024)
      : budget_bytes_(budget_bytes) {}

  auto pristine(TslDatasetSpec const & spec) -> Handle {
    return fetch(spec.id, [&spec] {
      return std::make_shared<Image>(tsl_generate_dataset<DataType>(spec));
    });
  }

  auto reference(TslDatasetSpec const & spec, TslDirection direction) -> Handle {
    auto const key = spec.id + "__" + tsl_direction_name(direction);
    return fetch(key, [&] {
      auto const source = pristine(spec);
      auto const ascending = tsl_direction_ascending(direction, source->size());
      auto image = std::make_shared<Image>(tsl_sorted_image(*source, ascending));
      tsl_require_ordered(*image, ascending);
      return image;
    });
  }

  auto descriptor(TslDatasetSpec const & spec) -> TslDatasetDescriptor {
    auto const found = descriptors_.find(spec.id);
    if (found != descriptors_.end()) {
      return found->second;
    }
    auto value = tsl_describe_dataset(*pristine(spec));
    descriptors_.emplace(spec.id, value);
    return value;
  }

  auto resident_bytes() const -> std::size_t { return resident_bytes_; }
  auto generated() const -> std::size_t { return generated_; }
  auto served_from_cache() const -> std::size_t { return hits_; }

  void clear() {
    entries_.clear();
    descriptors_.clear();
    resident_bytes_ = 0;
  }

 private:
  struct Entry {
    Handle image;
    std::size_t bytes = 0;
    std::uint64_t last_used = 0;
  };

  template <class Produce>
  auto fetch(std::string const & key, Produce && produce) -> Handle {
    auto found = entries_.find(key);
    if (found != entries_.end()) {
      found->second.last_used = ++clock_;
      ++hits_;
      return found->second.image;
    }
    Handle image = produce();
    ++generated_;
    auto const bytes = image->empty()
      ? std::size_t{0}
      : image->size() * image->front().size() * sizeof(DataType);
    // Evict least-recently-used entries until the new one fits. A single image
    // larger than the whole budget is still served; it is simply not retained.
    while (resident_bytes_ + bytes > budget_bytes_ && !entries_.empty()) {
      auto victim = entries_.begin();
      for (auto cursor = entries_.begin(); cursor != entries_.end(); ++cursor) {
        if (cursor->second.last_used < victim->second.last_used) {
          victim = cursor;
        }
      }
      resident_bytes_ -= victim->second.bytes;
      entries_.erase(victim);
    }
    if (bytes <= budget_bytes_) {
      entries_.emplace(key, Entry{image, bytes, ++clock_});
      resident_bytes_ += bytes;
    }
    return image;
  }

  std::size_t budget_bytes_;
  std::map<std::string, Entry> entries_;
  std::map<std::string, TslDatasetDescriptor> descriptors_;
  std::size_t resident_bytes_ = 0;
  std::size_t generated_ = 0;
  std::size_t hits_ = 0;
  std::uint64_t clock_ = 0;
};
