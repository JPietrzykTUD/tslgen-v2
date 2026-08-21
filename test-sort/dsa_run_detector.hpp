#pragma once

// Equal-run detection for a sorted range, offloaded to the Intel Data
// Streaming Accelerator via DML's `create_delta`.
//
// This is a second implementation of the `tsl_for_each_equal_run` contract in
// equal_runs.hpp: absolute half-open spans, maximal within [begin, end),
// length > 1 only, ascending. Anything consuming that contract can consume this
// instead, which is what makes the backend switch a one-line change at the call
// site.
//
// -----------------------------------------------------------------------------
// How create_delta is used
// -----------------------------------------------------------------------------
// `create_delta` compares two regions in fixed 8-byte blocks and emits one
// record per block that differs. It requires both sources to be 8-byte aligned
// and the transfer size to be a whole number of blocks.
//
// The obvious formulation -- compare the range against itself shifted by one
// *element* -- only satisfies that alignment rule when sizeof(T) == 8. For
// narrower types a one-element shift moves the address by sizeof(T) bytes,
// which is not a multiple of 8 and is rejected. That is normally worked around
// by first copying the shifted view into an aligned scratch buffer, costing a
// second (dependent) descriptor and a full-size write per region.
//
// We avoid the copy by exploiting the fact that our input is *sorted*: compare
// the range against itself shifted by one whole 8-byte *block*
// (`block_elements = 8 / sizeof(T)` elements), which keeps both sources 8-byte
// aligned for every width.
//
//   source_1 = values + base + block_elements   (byte offset +8)
//   source_2 = values + base
//
// Claim: for monotonic data, block `i` fires **iff** at least one run boundary
// has its left index in [g*i, g*i + g - 1], where g = block_elements.
//
//   Boundary => fires: let p be in [g*i, g*i+g-1] with v[p] != v[p+1]. With
//   j = p - g*i the compare includes v[g*i+j] = v[p] against v[g*i+g+j] =
//   v[p+g]. Monotonicity and p+g >= p+1 give v[p+g] != v[p], so block i fires.
//
//   Fires => a boundary exists in [g*i, g*i+2g-2], which is covered by the CPU
//   refinement of blocks i and i+1.
//
// So a fired block is refined by g scalar comparisons -- the same per-block
// refinement the copy-based formulation needs anyway -- and the copy
// disappears. One descriptor per region, every width. For sizeof(T) == 8,
// g == 1 and the scheme degenerates to a plain shift-by-one-element compare
// with no refinement.
//
// Monotonicity is the precondition. `detect` is only valid on a range already
// sorted by the column being scanned (ascending or descending both qualify --
// the argument only uses that equal values are adjacent and unequal values
// never repeat). test_dsa_run_detector.cpp checks every emitted span set
// against the scalar oracle for both orders and all widths.
//
// -----------------------------------------------------------------------------
// Boundaries, not runs
// -----------------------------------------------------------------------------
// The detector works in *boundaries* (indices p with v[p] != v[p+1]) and only
// converts to spans at the very end. A run that straddles a region boundary
// therefore needs no cross-region merge: it is simply the absence of a boundary
// at the seam. The one thing that must not be forgotten is the seam index
// itself -- the boundary between the last element of one region and the first
// of the next belongs to neither region's delta compare -- and the tail loop
// covers it by running one index past the region end.
//
// This detector holds a scratch buffer and mutable counters: use one instance
// per thread.

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <mutex>
#include <new>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "equal_runs.hpp"
#include "multicolumn_sort_types.hpp"

#ifdef TSL_COSORT_ENABLE_DSA
#include <dml/dml.hpp>
#endif


// Which implementation services a detect() call. SCALAR needs no DML and is
// always available, so a build with TSL_COSORT_ENABLE_DSA on can still compare
// against the CPU path in the same binary.
enum class TslRleBackend { SCALAR, DML_SOFTWARE, DSA_HARDWARE };

inline auto tsl_rle_backend_name(TslRleBackend backend) -> char const * {
  switch (backend) {
    case TslRleBackend::SCALAR: return "scalar";
    case TslRleBackend::DML_SOFTWARE: return "dml_sw";
    case TslRleBackend::DSA_HARDWARE: return "dsa_hw";
  }
  return "?";
}

// `create_delta`'s output record: a 16-bit block offset (in units of 8-byte
// blocks, not elements) plus the 8 payload bytes the delta would apply. We only
// ever read `offset`. Defined here rather than reused from elsewhere so this
// header stands alone against DML.
struct __attribute__((packed)) TslDsaDeltaRecord {
  std::uint16_t offset;
  std::uint8_t payload[8];
};
static_assert(sizeof(TslDsaDeltaRecord) == 10, "delta record must be tightly packed");

// A 16-bit block offset caps one descriptor at 65536 blocks, which is also
// create_delta's 512 KiB transfer maximum.
inline constexpr std::size_t tsl_dsa_max_region_bytes = 512u * 1024u;
// Measured best on this host across every width and cardinality: descriptor
// cost dominates below it (32 KiB regions run at roughly half the throughput of
// 512 KiB ones on hardware). An asynchronous caller may want smaller regions for
// finer completion granularity and should say so explicitly.
inline constexpr std::size_t tsl_dsa_default_region_bytes = tsl_dsa_max_region_bytes;


struct TslDsaRunDetectorMetrics {
  std::size_t ranges = 0;             // detect() calls with >= 2 elements
  std::size_t elements = 0;           // elements those calls covered
  std::size_t offloaded_elements = 0; // elements that reached a descriptor
  std::size_t regions = 0;
  std::size_t descriptors = 0;
  std::size_t fired_blocks = 0;
  std::size_t refined_elements = 0;   // scalar comparisons spent refining
  std::size_t prologue_elements = 0;  // scalar comparisons before 8-byte alignment
  std::size_t tail_elements = 0;      // scalar comparisons past the last full block
  std::size_t fallback_small = 0;     // range below the offload threshold
  std::size_t spans_emitted = 0;
};


namespace tsl_dsa_detail {

// 64-byte aligned scratch. create_delta requires the delta buffer to be 8-byte
// aligned; 64 keeps it off shared cache lines as well.
class aligned_bytes {
  void * ptr_ = nullptr;
  std::size_t size_ = 0;

 public:
  aligned_bytes() = default;

  explicit aligned_bytes(std::size_t bytes) {
    size_ = (bytes + 63u) & ~std::size_t{63};
    ptr_ = std::aligned_alloc(64, size_);
    if (ptr_ == nullptr) {
      throw std::bad_alloc();
    }
  }

  aligned_bytes(aligned_bytes const &) = delete;
  auto operator=(aligned_bytes const &) -> aligned_bytes & = delete;

  aligned_bytes(aligned_bytes && other) noexcept
      : ptr_(other.ptr_), size_(other.size_) {
    other.ptr_ = nullptr;
    other.size_ = 0;
  }

  auto operator=(aligned_bytes && other) noexcept -> aligned_bytes & {
    if (this != &other) {
      std::free(ptr_);
      ptr_ = other.ptr_;
      size_ = other.size_;
      other.ptr_ = nullptr;
      other.size_ = 0;
    }
    return *this;
  }

  ~aligned_bytes() { std::free(ptr_); }

  auto data() const -> void * { return ptr_; }
  auto size() const -> std::size_t { return size_; }
};

}  // namespace tsl_dsa_detail


template <class DataType>
class TslDsaRunDetector;


// A pool of detectors, borrowed for one call, so the sort can use the
// accelerator-backed detector as a drop-in for `scalar_run_detector`.
//
// A detector owns a scratch buffer and mutable counters, so it cannot be used by
// two threads at once. It is *not* bound to a thread for its lifetime, though,
// and must not be: the executor starts fresh workers on every parallel sort while
// the fleet is constructed once per case, so a scheme that gives each new thread
// its own permanent slot needs as many slots as (sorts x workers) rather than as
// many as run concurrently, and fails on the second sort. Borrowing bounds the
// pool by concurrency instead. The mutex is held only across the handover, never
// across the scan.
template <class DataType>
class TslDsaDetectorFleet {
  std::vector<std::unique_ptr<TslDsaRunDetector<DataType>>> detectors_;
  std::vector<TslDsaRunDetector<DataType> *> available_;
  mutable std::mutex mutex_;
  std::condition_variable released_;

  // Returns a detector to the pool however the borrower left the scope.
  class lease {
    TslDsaDetectorFleet * fleet_;
    TslDsaRunDetector<DataType> * detector_;

   public:
    lease(TslDsaDetectorFleet & fleet, TslDsaRunDetector<DataType> * detector)
        : fleet_(&fleet), detector_(detector) {}
    lease(lease const &) = delete;
    auto operator=(lease const &) -> lease & = delete;
    ~lease() {
      {
        std::lock_guard<std::mutex> lock(fleet_->mutex_);
        fleet_->available_.push_back(detector_);
      }
      fleet_->released_.notify_one();
    }
    auto get() const -> TslDsaRunDetector<DataType> & { return *detector_; }
  };

  auto borrow() -> lease {
    std::unique_lock<std::mutex> lock(mutex_);
    // Only waits if more threads call concurrently than the pool was sized for,
    // which the executor's worker count makes unexpected rather than impossible.
    released_.wait(lock, [this] { return !available_.empty(); });
    auto * detector = available_.back();
    available_.pop_back();
    return lease(*this, detector);
  }

 public:
  TslDsaDetectorFleet(
    TslRleBackend backend,
    std::size_t worker_count,
    std::size_t region_bytes = tsl_dsa_default_region_bytes,
    std::size_t min_offload_elements = 4096
  ) {
    // One spare: the caller's thread may also run work inline.
    auto const size = worker_count + 1;
    detectors_.reserve(size);
    available_.reserve(size);
    for (std::size_t slot = 0; slot < size; ++slot) {
      detectors_.push_back(std::make_unique<TslDsaRunDetector<DataType>>(
        backend, region_bytes, min_offload_elements
      ));
      available_.push_back(detectors_.back().get());
    }
  }

  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    auto held = borrow();
    held.get().detect(values, begin, end, std::forward<Emit>(emit));
  }

  // Call only after the sort has joined its workers.
  auto aggregate_metrics() const -> TslDsaRunDetectorMetrics {
    std::lock_guard<std::mutex> lock(mutex_);
    TslDsaRunDetectorMetrics total{};
    for (auto const & detector : detectors_) {
      auto const & m = detector->metrics();
      total.ranges += m.ranges;
      total.elements += m.elements;
      total.offloaded_elements += m.offloaded_elements;
      total.regions += m.regions;
      total.descriptors += m.descriptors;
      total.fired_blocks += m.fired_blocks;
      total.refined_elements += m.refined_elements;
      total.prologue_elements += m.prologue_elements;
      total.tail_elements += m.tail_elements;
      total.fallback_small += m.fallback_small;
      total.spans_emitted += m.spans_emitted;
    }
    return total;
  }

  void reset_metrics() {
    std::lock_guard<std::mutex> lock(mutex_);
    for (auto & detector : detectors_) {
      detector->reset_metrics();
    }
  }
};


template <class DataType>
class TslDsaRunDetector {
  static_assert(std::is_integral_v<DataType>, "run detection needs an integral element type");
  static_assert(sizeof(DataType) <= 8 && (8u % sizeof(DataType)) == 0,
                "element width must divide the 8-byte create_delta block");

  // Elements covered by one create_delta block.
  static constexpr std::size_t block_elements = 8u / sizeof(DataType);

  TslRleBackend backend_;
  std::size_t region_bytes_;
  std::size_t region_elements_;
  std::size_t min_offload_elements_;
  tsl_dsa_detail::aligned_bytes deltas_;
  TslDsaRunDetectorMetrics metrics_{};

 public:
  // `min_offload_elements` keeps short ranges on the CPU: below it the scalar
  // pass finishes in less time than a descriptor round trip.
  explicit TslDsaRunDetector(
    TslRleBackend backend,
    std::size_t region_bytes = tsl_dsa_default_region_bytes,
    std::size_t min_offload_elements = 4096
  )
      : backend_(backend),
        region_bytes_(region_bytes),
        min_offload_elements_(min_offload_elements) {
    if (region_bytes_ % 8u != 0 || region_bytes_ == 0) {
      throw std::invalid_argument("region_bytes must be a non-zero multiple of 8");
    }
    if (region_bytes_ > tsl_dsa_max_region_bytes) {
      throw std::invalid_argument("region_bytes exceeds the create_delta 512 KiB transfer maximum");
    }
    region_elements_ = region_bytes_ / sizeof(DataType);

    if (backend_ != TslRleBackend::SCALAR) {
      // Worst case every block fires: one 10-byte record per 8 input bytes.
      // Sizing for that makes delta-record overflow structurally impossible,
      // which matters because a truncated record set would silently drop
      // boundaries and merge two distinct-value runs into one span.
      auto const max_records = region_bytes_ / 8u;
      auto const bytes = std::max<std::size_t>(max_records * sizeof(TslDsaDeltaRecord), 128u);
      deltas_ = tsl_dsa_detail::aligned_bytes(bytes);
    }
  }

  auto backend() const -> TslRleBackend { return backend_; }
  auto region_bytes() const -> std::size_t { return region_bytes_; }
  auto metrics() const -> TslDsaRunDetectorMetrics const & { return metrics_; }
  void reset_metrics() { metrics_ = {}; }

  // Emits every maximal equal run of length > 1 in [begin, end), ascending.
  // `values` must be sorted (either order) over that range.
  template <class Emit>
  void detect(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    if (end - begin < 2) {
      return;
    }
    ++metrics_.ranges;
    metrics_.elements += end - begin;

    auto counting_emit = [&](TslRunSpan span) {
      ++metrics_.spans_emitted;
      emit(span);
    };

    if (backend_ == TslRleBackend::SCALAR) {
      tsl_for_each_equal_run(values, begin, end, counting_emit);
      return;
    }
    if (end - begin < min_offload_elements_) {
      ++metrics_.fallback_small;
      tsl_for_each_equal_run(values, begin, end, counting_emit);
      return;
    }

#ifdef TSL_COSORT_ENABLE_DSA
    // Boundary sink: converts ascending boundary indices into spans on the fly,
    // so no boundary list is ever materialized.
    std::size_t run_begin = begin;
    auto on_boundary = [&](std::size_t position) {
      if (position + 1 - run_begin > 1) {
        ++metrics_.spans_emitted;
        emit(TslRunSpan{run_begin, position + 1});
      }
      run_begin = position + 1;
    };

    // Scalar prologue until the source pointer is 8-byte aligned. At most
    // block_elements - 1 comparisons, and none at all for 8-byte types.
    std::size_t position = begin;
    while (
      position + 1 < end
      && (reinterpret_cast<std::uintptr_t>(values + position) % 8u) != 0
    ) {
      if (values[position] != values[position + 1]) {
        on_boundary(position);
      }
      ++position;
      ++metrics_.prologue_elements;
    }

    // Regions advance by a whole number of blocks, so every region after the
    // first inherits the 8-byte alignment established above.
    while (position + 1 < end) {
      auto const region_elems = std::min(region_elements_, end - position);
      encode_region(values, position, region_elems, end, on_boundary);
      position += region_elems;
    }

    if (end - run_begin > 1) {
      ++metrics_.spans_emitted;
      emit(TslRunSpan{run_begin, end});
    }
#else
    tsl_for_each_equal_run(values, begin, end, counting_emit);
#endif
  }

 private:
#ifdef TSL_COSORT_ENABLE_DSA
  template <class OnBoundary>
  void encode_region(
    DataType const * values,
    std::size_t base,
    std::size_t region_elems,
    std::size_t end,
    OnBoundary & on_boundary
  ) {
    ++metrics_.regions;

    // Largest whole number of blocks that still leaves one block of headroom
    // for the shift, so source_1 stays inside the region.
    std::size_t delta_elems = 0;
    if (region_elems > block_elements) {
      delta_elems = ((region_elems - block_elements) / block_elements) * block_elements;
    }

    if (delta_elems > 0) {
      auto const fired = run_create_delta(values + base, delta_elems);
      metrics_.fired_blocks += fired;
      metrics_.offloaded_elements += delta_elems;

      auto const * records = static_cast<TslDsaDeltaRecord const *>(deltas_.data());
      for (std::size_t index = 0; index < fired; ++index) {
        auto const block_base = base + std::size_t{records[index].offset} * block_elements;
        // Every candidate here is < base + delta_elems <= end - block_elements,
        // so position + 1 is always in range.
        for (std::size_t offset = 0; offset < block_elements; ++offset) {
          auto const position = block_base + offset;
          if (values[position] != values[position + 1]) {
            on_boundary(position);
          }
        }
        metrics_.refined_elements += block_elements;
      }
    }

    // Boundaries the compare did not cover: the ragged tail, plus the seam
    // index shared with the next region (hence `position < base + region_elems`
    // rather than `< base + region_elems - 1`).
    for (
      auto position = base + delta_elems;
      position + 1 < end && position < base + region_elems;
      ++position
    ) {
      if (values[position] != values[position + 1]) {
        on_boundary(position);
      }
      ++metrics_.tail_elements;
    }
  }

  // Returns the number of fired blocks; their indices land in deltas_.
  auto run_create_delta(DataType const * page, std::size_t delta_elems) -> std::size_t {
    ++metrics_.descriptors;

    auto const * source_1 = page + block_elements;  // shifted by one 8-byte block
    auto const * source_2 = page;
    auto * delta_out = static_cast<std::uint8_t *>(deltas_.data());

    auto const run = [&](auto path_tag) {
      using path_t = decltype(path_tag);
      return dml::execute<path_t>(
        dml::create_delta.block_on_fault(),
        dml::make_view(source_1, delta_elems),
        dml::make_view(source_2, delta_elems),
        dml::make_view(delta_out, deltas_.size())
      );
    };

    auto const result = (backend_ == TslRleBackend::DSA_HARDWARE)
      ? run(dml::hardware{})
      : run(dml::software{});

    if (result.status != dml::status_code::ok) {
      throw std::runtime_error(
        "create_delta failed with DML status "
        + std::to_string(static_cast<std::uint32_t>(result.status))
        + " (" + tsl_rle_backend_name(backend_) + ", "
        + std::to_string(delta_elems * sizeof(DataType)) + " bytes)"
      );
    }
    // Structurally impossible given the buffer sizing above, but a silent
    // truncation here would corrupt the sort, so it is checked rather than
    // assumed.
    if (result.delta_record_size > deltas_.size()) {
      throw std::runtime_error("create_delta reported more delta bytes than the buffer holds");
    }
    return result.delta_record_size / sizeof(TslDsaDeltaRecord);
  }
#endif
};
