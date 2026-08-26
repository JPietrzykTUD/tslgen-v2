#pragma once

// Equal-run detection for a sorted range, offloaded to the Intel In-Memory
// Analytics Accelerator via QPL.
//
// A third implementation of the `tsl_for_each_equal_run` contract in
// equal_runs.hpp -- absolute half-open spans, maximal within [begin, end),
// length > 1 only, ascending -- so it drops into the same detector seam as the
// scalar and DSA backends.
//
// -----------------------------------------------------------------------------
// How scan_eq is used
// -----------------------------------------------------------------------------
// QPL 1.x exposes scan / extract / select / expand. None of them compares an
// element with its neighbour, so the DSA formulation (one `create_delta` over
// the range against itself shifted by one block, see dsa_run_detector.hpp) has
// no IAA counterpart. What IAA can do is count matches of a *known* value:
// `scan_eq` writes a one-bit-per-element result vector and the completion
// record's `sum_value` aggregate carries its population count.
//
// On sorted input that popcount is a run length. Every copy of a value is
// contiguous, so scanning the unencoded tail [cursor, region_end) for the value
// at `cursor` counts exactly the elements of that one run:
//
//   v   = values[cursor]                 one scalar load
//   len = scan_eq(v) over a window       one descriptor, sum_value
//   run = [cursor, cursor + len)         boundary at cursor + len - 1
//   cursor += len                        jump past the run, repeat
//
// The CPU therefore never scans the range: it reads one value per run and does
// the O(1) bookkeeping. That is what makes this a fair measurement of the IAA
// path rather than of a CPU pre-pass.
//
// The window matters more than it looks. Scanning the whole unencoded tail is
// the obvious formulation and it is quadratic: a region of R elements whose runs
// average L holds R/L runs whose tails sum to about R^2/2L, so a 512 KiB region
// of uint32 with L = 64 reads 134M elements to cover 131072 -- a thousandfold
// read amplification, against one pass for DSA's create_delta. Since all matches
// of v are a contiguous prefix of the tail, a bounded window is enough: if the
// window does not fill, sum_value is the exact run length; if it fills, the run
// may continue, and the scan is repeated from where it stopped with the window
// doubled. Sizing the first window from the mean run length observed so far
// makes one descriptor per run the common case, and the reads become linear.
//
// -----------------------------------------------------------------------------
// Why not the batched formulation from the RLE prototype
// -----------------------------------------------------------------------------
// The obvious way to remove the cursor dependency -- take every distinct value
// up front with one vectorized CPU pass, then issue all the scans concurrently
// -- cannot be used here. That pass finds distinct values on sorted data by
// comparing each element against its predecessor, and *that compare mask is the
// boundary set this detector exists to produce*. Having paid for it, the scans
// would be measuring the accelerator's cost to recompute an answer the CPU
// already holds. The prototype needed run lengths as its output, so the trade
// made sense there; a detector needs only boundaries, and consecutive
// boundaries give lengths for free.
//
// Concurrency is therefore taken across *regions* instead of across values: the
// walk above is sequential within a region, and independent between regions,
// which is what the asynchronous form below exploits.
//
// -----------------------------------------------------------------------------
// Boundaries, not runs
// -----------------------------------------------------------------------------
// Like the DSA detector, this one works in boundaries (indices p with
// v[p] != v[p+1]) and converts to spans at the end. A run straddling a region
// seam needs no merge: it is simply the absence of a boundary at the seam. Each
// region reports only the boundaries strictly inside it -- a run that reaches
// the region end yields no boundary there -- and the seam itself is decided by
// one scalar comparison per region pair during the stitch.
//
// -----------------------------------------------------------------------------
// What this backend is for
// -----------------------------------------------------------------------------
// Descriptor count is O(runs), the inverse of DSA's O(1) per region: a
// high-cardinality range costs one descriptor per element and emits no spans at
// all, where `create_delta` costs one descriptor and DSA's CPU refinement does
// the rest. This backend exists to characterize the IAA path on the same axis
// as the others, not because it is expected to beat `rle=scalar`. `min_offload`
// keeps it off ranges too short to be worth a round trip.
//
// Limits:
//   * QPL scan takes `src1_bit_width <= 32`, so 8-byte elements have no
//     single-scan form. `DataType` of 8 bytes falls back to the scalar oracle
//     and reports it as `fallback_width`.
//   * The sorted precondition is the detector's; either direction qualifies,
//     because the argument uses only that equal values are adjacent and
//     unequal values never repeat.
//   * `TslIaaPath::HARDWARE` needs an IAA device; `TslIaaPath::SOFTWARE` runs
//     the identical QPL logic on the CPU, which is how the differential test
//     validates this file on a host without one.

#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "cluster_detection/scalar/equal_runs.hpp"
#include "common/borrow_pool.hpp"
#include "sorting/common/multicolumn_sort_tasks.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"

#ifdef TSL_COSORT_ENABLE_IAA
#include <qpl/qpl.h>
#endif


// Which QPL execution path services a detect() call. SOFTWARE needs no device,
// so a build with TSL_COSORT_ENABLE_IAA on can still exercise every line of
// this file on a host whose accelerator is a DSA.
enum class TslIaaPath { SOFTWARE, HARDWARE };

inline auto tsl_iaa_path_name(TslIaaPath path) -> char const * {
  return path == TslIaaPath::HARDWARE ? "iaa_hw" : "iaa_sw";
}

// One descriptor covers at most this many elements, because `num_input_elements`
// is a 32-bit field. Regions are far smaller in practice; the cap is a guard.
inline constexpr std::size_t tsl_iaa_max_region_elements = 0xFFFFFFFFull;
// Default region size. Unlike DSA there is no transfer maximum to respect: a
// region bounds how much a single scan re-reads while walking a run, and how
// much independent work the asynchronous form has to hand out.
inline constexpr std::size_t tsl_iaa_default_region_bytes = 512u * 1024u;
// Below this a scalar pass beats a descriptor round trip.
inline constexpr std::size_t tsl_iaa_default_min_offload = 4096;
// Offload floor, as a mean run length. One descriptor measures one run, so a
// range of R elements whose runs average L costs R/L descriptors -- and at L = 1
// that is one descriptor per element to emit no spans at all. Measured on the
// all-distinct shape: 3.9M elements, 3.9M descriptors, 148x the scalar pass.
// The walk therefore watches the mean run length it is actually seeing and hands
// the rest of the range to the scalar oracle once it falls below this.
inline constexpr std::size_t tsl_iaa_default_run_length_floor = 8;
// Descriptors spent before that verdict is trusted. It has to be a probe rather
// than a budget of R/floor: a budget is fully spent before it concludes
// anything, which on a 3.9M-element range still means half a million wasted
// descriptors, where a probe settles the question in 64 and costs O(1).
inline constexpr std::size_t tsl_iaa_probe_descriptors = 64;
// Smallest scan window. Below this the per-descriptor cost dominates whatever the
// scan saves, so a window is never shrunk past it however short the runs are.
inline constexpr std::size_t tsl_iaa_min_scan_window = 256;

// First window for the next run: enough to cover twice the mean run seen so far,
// so a typical run is measured by one descriptor and reads about twice its own
// length. A run that fills the window is galloped, doubling per descriptor.
inline auto tsl_iaa_first_window(std::size_t mean_run) -> std::size_t {
  auto const wanted = mean_run == 0 ? tsl_iaa_min_scan_window : 2 * mean_run;
  return wanted < tsl_iaa_min_scan_window ? tsl_iaa_min_scan_window : wanted;
}


struct TslIaaRunDetectorMetrics {
  std::size_t ranges = 0;             // detect() calls with >= 2 elements
  std::size_t elements = 0;           // elements those calls covered
  std::size_t offloaded_elements = 0; // elements that reached a descriptor
  std::size_t regions = 0;
  std::size_t descriptors = 0;        // scan_eq ops issued == runs measured
  std::size_t scanned_elements = 0;   // elements the accelerator actually read
  std::size_t seam_comparisons = 0;   // scalar compares spent stitching regions
  std::size_t fallback_small = 0;     // range below the offload threshold
  std::size_t fallback_width = 0;     // 8-byte elements: no single-scan form
  std::size_t fallback_capacity = 0;  // asynchronous: no free range slot
  std::size_t fallback_short_runs = 0;// ranges abandoned mid-walk: runs too short
  std::size_t cpu_finished_elements = 0;// elements those ranges finished on the CPU
  std::size_t spans_emitted = 0;
};


namespace tsl_iaa_detail {

#ifdef TSL_COSORT_ENABLE_IAA

inline auto to_qpl_path(TslIaaPath path) -> qpl_path_t {
  return path == TslIaaPath::HARDWARE ? qpl_path_hardware : qpl_path_software;
}

// An initialized qpl_job plus the buffer it lives in. Movable so a fleet can be
// held in one vector; the moved-from object is neutered so its destructor is a
// no-op.
class qpl_job_handle {
  std::unique_ptr<std::uint8_t[]> buffer_;
  qpl_job * job_ = nullptr;

 public:
  qpl_job_handle() = default;

  explicit qpl_job_handle(TslIaaPath path) {
    auto const qpl_path = to_qpl_path(path);
    std::uint32_t size = 0;
    if (auto const status = qpl_get_job_size(qpl_path, &size); status != QPL_STS_OK) {
      throw std::runtime_error("qpl_get_job_size failed, status " + std::to_string(status));
    }
    buffer_ = std::make_unique<std::uint8_t[]>(size);
    job_ = reinterpret_cast<qpl_job *>(buffer_.get());
    if (auto const status = qpl_init_job(qpl_path, job_); status != QPL_STS_OK) {
      job_ = nullptr;
      throw std::runtime_error(
        std::string("qpl_init_job failed, status ") + std::to_string(status)
        + (path == TslIaaPath::HARDWARE
             ? " (no IAA device, or accel-config work queues are not configured)"
             : "")
      );
    }
  }

  qpl_job_handle(qpl_job_handle const &) = delete;
  auto operator=(qpl_job_handle const &) -> qpl_job_handle & = delete;

  qpl_job_handle(qpl_job_handle && other) noexcept
      : buffer_(std::move(other.buffer_)), job_(other.job_) {
    other.job_ = nullptr;
  }

  auto operator=(qpl_job_handle && other) noexcept -> qpl_job_handle & {
    if (this != &other) {
      if (job_ != nullptr) qpl_fini_job(job_);
      buffer_ = std::move(other.buffer_);
      job_ = other.job_;
      other.job_ = nullptr;
    }
    return *this;
  }

  ~qpl_job_handle() {
    if (job_ != nullptr) qpl_fini_job(job_);
  }

  auto get() const -> qpl_job * { return job_; }
};

// Configure one scan_eq over `count` elements at `source`, matching `value`,
// writing the (never-read) result bit vector into `out`. `out_bytes` must be at
// least ceil(count/8).
template <class DataType>
void configure_scan_eq(
  qpl_job * job,
  DataType const * source,
  std::size_t count,
  DataType value,
  std::uint8_t * out,
  std::size_t out_bytes
) {
  job->op = qpl_op_scan_eq;
  job->parser = qpl_p_le_packed_array;  // densely packed fixed-width integers
  job->src1_bit_width = static_cast<std::uint32_t>(sizeof(DataType) * 8);
  job->num_input_elements = static_cast<std::uint32_t>(count);
  job->next_in_ptr = reinterpret_cast<std::uint8_t *>(const_cast<DataType *>(source));
  job->available_in = static_cast<std::uint32_t>(count * sizeof(DataType));
  job->next_out_ptr = out;
  job->available_out = static_cast<std::uint32_t>(out_bytes);
  job->out_bit_width = qpl_ow_nom;      // nominal bit vector -> sum_value populated
  job->param_low = static_cast<std::uint32_t>(value);
  job->param_high = static_cast<std::uint32_t>(value);
  job->drop_initial_bytes = 0;
  job->initial_output_index = 0;
  // Keep the aggregates (default); skip the checksums nothing here reads.
  job->flags = QPL_FLAG_FIRST | QPL_FLAG_LAST | QPL_FLAG_OMIT_CHECKSUMS;
}

// A momentarily full hardware work queue is back-pressure, not an error.
inline void submit_retrying(qpl_job * job) {
  qpl_status status;
  do {
    status = qpl_submit_job(job);
  } while (status == QPL_STS_QUEUES_ARE_BUSY_ERR);
  if (status != QPL_STS_OK) {
    throw std::runtime_error("qpl_submit_job failed, status " + std::to_string(status));
  }
}

#endif  // TSL_COSORT_ENABLE_IAA

// Tracks the return the offload is getting and decides when to stop. Shared by
// both detectors so the rule has one definition.
class offload_verdict {
  std::size_t floor_;
  std::size_t probe_;
  std::size_t spent_ = 0;      // descriptors issued for this range
  std::size_t consumed_ = 0;   // elements they accounted for

 public:
  offload_verdict() : floor_(1), probe_(0) {}
  offload_verdict(std::size_t floor, std::size_t probe) : floor_(floor), probe_(probe) {}

  void record(std::size_t run_length) {
    ++spent_;
    consumed_ += run_length;
  }

  // Once past the probe, the mean elements per descriptor must justify the cost.
  auto give_up() const -> bool {
    return spent_ >= probe_ && consumed_ < spent_ * floor_;
  }

  // Elements accounted for per descriptor so far, or 0 without evidence.
  auto mean() const -> std::size_t { return spent_ == 0 ? 0 : consumed_ / spent_; }
};

// QPL scan compares at most 32 bits per element.
template <class DataType>
inline constexpr bool scan_supports_width = sizeof(DataType) <= 4;

// Bit-vector bytes a scan over `count` elements needs, plus slack so a partial
// final byte never sits on the boundary.
inline auto scan_out_bytes(std::size_t count) -> std::size_t {
  return (count + 7u) / 8u + 8u;
}

}  // namespace tsl_iaa_detail


// -----------------------------------------------------------------------------
// Synchronous detector: one instance per thread
// -----------------------------------------------------------------------------
// Holds a job and a scratch bit vector and keeps mutable counters, so it cannot
// be shared. `TslIaaDetectorFleet` hands one to each worker.
template <class DataType>
class TslIaaRunDetector {
  static_assert(std::is_integral_v<DataType>, "run detection needs an integral element type");
  static_assert(sizeof(DataType) <= 8, "element width above 8 bytes is not a sort key here");

  TslIaaPath path_;
  std::size_t region_elements_;
  std::size_t min_offload_elements_;
  std::size_t run_length_floor_;
  TslIaaRunDetectorMetrics metrics_{};
#ifdef TSL_COSORT_ENABLE_IAA
  tsl_iaa_detail::qpl_job_handle job_;
  std::vector<std::uint8_t> scan_out_;
#endif

 public:
  explicit TslIaaRunDetector(
    TslIaaPath path = TslIaaPath::HARDWARE,
    std::size_t region_bytes = tsl_iaa_default_region_bytes,
    std::size_t min_offload_elements = tsl_iaa_default_min_offload,
    std::size_t run_length_floor = tsl_iaa_default_run_length_floor
  )
      : path_(path),
        min_offload_elements_(min_offload_elements),
        run_length_floor_(std::max<std::size_t>(run_length_floor, 1)) {
    if (region_bytes == 0 || region_bytes % sizeof(DataType) != 0) {
      throw std::invalid_argument("region_bytes must be a non-zero multiple of the element width");
    }
    region_elements_ = region_bytes / sizeof(DataType);
    if (region_elements_ > tsl_iaa_max_region_elements) {
      throw std::invalid_argument("region_bytes exceeds the addressable scan length");
    }
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (tsl_iaa_detail::scan_supports_width<DataType>) {
      job_ = tsl_iaa_detail::qpl_job_handle(path_);
      scan_out_.assign(tsl_iaa_detail::scan_out_bytes(region_elements_), 0);
    }
#endif
  }

  auto path() const -> TslIaaPath { return path_; }
  auto region_elements() const -> std::size_t { return region_elements_; }
  auto metrics() const -> TslIaaRunDetectorMetrics const & { return metrics_; }

  // Published so a caller can decline a range this detector would decline
  // anyway, before paying to reach the decision. See
  // sorting/common/run_discovery.hpp.
  auto min_offload_elements() const -> std::size_t { return min_offload_elements_; }
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

    if constexpr (!tsl_iaa_detail::scan_supports_width<DataType>) {
      ++metrics_.fallback_width;
      tsl_for_each_equal_run(values, begin, end, counting_emit);
      return;
    } else {
      if (end - begin < min_offload_elements_) {
        ++metrics_.fallback_small;
        tsl_for_each_equal_run(values, begin, end, counting_emit);
        return;
      }
#ifdef TSL_COSORT_ENABLE_IAA
      metrics_.offloaded_elements += end - begin;

      // Boundary sink: turns ascending boundary indices into spans on the fly,
      // so no boundary list is materialized.
      std::size_t run_begin = begin;
      auto on_boundary = [&](std::size_t position) {
        if (position + 1 - run_begin > 1) {
          ++metrics_.spans_emitted;
          emit(TslRunSpan{run_begin, position + 1});
        }
        run_begin = position + 1;
      };

      tsl_iaa_detail::offload_verdict verdict(run_length_floor_, tsl_iaa_probe_descriptors);
      for (auto base = begin; base < end; base += region_elements_) {
        auto const region_end = std::min(base + region_elements_, end);
        ++metrics_.regions;
        auto const stopped_at = walk_region(values, base, region_end, verdict, on_boundary);
        if (stopped_at != region_end) {
          // The runs are too short for a descriptor each. Finish the range on the
          // CPU, still in boundaries so the spans already emitted stay valid and
          // ascending.
          ++metrics_.fallback_short_runs;
          metrics_.cpu_finished_elements += end - stopped_at;
          for (auto position = stopped_at; position + 1 < end; ++position) {
            if (values[position] != values[position + 1]) {
              on_boundary(position);
            }
          }
          break;
        }
        // The seam between this region and the next belongs to neither scan.
        if (region_end < end) {
          ++metrics_.seam_comparisons;
          if (values[region_end - 1] != values[region_end]) {
            on_boundary(region_end - 1);
          }
        }
      }

      if (end - run_begin > 1) {
        ++metrics_.spans_emitted;
        emit(TslRunSpan{run_begin, end});
      }
#else
      tsl_for_each_equal_run(values, begin, end, counting_emit);
#endif
    }
  }

  // Detector seam: same call shape as the scalar and DSA detectors.
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    detect(values, begin, end, std::forward<Emit>(emit));
  }

 private:
#ifdef TSL_COSORT_ENABLE_IAA
  // Sequential walk of one region, reporting only the boundaries strictly
  // inside it. A run reaching `region_end` yields no boundary here; the caller's
  // seam comparison decides that one.
  // Matches of a value are a contiguous prefix of a sorted span, so sum_value
  // over `count` elements is how far that prefix reaches into them.
  auto scan_prefix(DataType const * source, std::size_t count, DataType value) -> std::size_t {
    tsl_iaa_detail::configure_scan_eq<DataType>(
      job_.get(), source, count, value, scan_out_.data(), scan_out_.size()
    );
    if (auto const status = qpl_execute_job(job_.get()); status != QPL_STS_OK) {
      throw std::runtime_error("qpl_execute_job failed, status " + std::to_string(status));
    }
    ++metrics_.descriptors;
    metrics_.scanned_elements += count;
    auto const matched = static_cast<std::size_t>(job_.get()->sum_value);
    if (matched > count) {
      throw std::runtime_error(
        "IAA scan_eq matched " + std::to_string(matched) + " of " + std::to_string(count)
      );
    }
    return matched;
  }

  // Returns where it stopped: `region_end` on completion, otherwise the cursor
  // the caller must resume from on the CPU. `verdict` carries across regions so
  // one range's evidence is pooled.
  template <class OnBoundary>
  auto walk_region(
    DataType const * values,
    std::size_t base,
    std::size_t region_end,
    tsl_iaa_detail::offload_verdict & verdict,
    OnBoundary & on_boundary
  ) -> std::size_t {
    auto cursor = base;
    while (cursor < region_end) {
      if (verdict.give_up()) {
        return cursor;
      }
      auto const value = values[cursor];
      std::size_t run_length = 0;
      auto window = tsl_iaa_first_window(verdict.mean());
      while (true) {
        auto const span = std::min(window, region_end - cursor - run_length);
        if (span == 0) {
          break;  // the run reaches the region end
        }
        auto const matched = scan_prefix(values + cursor + run_length, span, value);
        verdict.record(matched);
        run_length += matched;
        if (matched < span) {
          break;  // the run ended inside this window
        }
        window *= 2;  // still going: gallop rather than pay a descriptor per window
      }
      if (run_length == 0) {
        throw std::runtime_error("IAA scan_eq reported an empty run at a live cursor");
      }
      auto const run_end = cursor + run_length;  // one past the run's last element
      if (run_end < region_end) {
        on_boundary(run_end - 1);
      }
      cursor = run_end;
    }
    return region_end;
  }
#endif
};


// -----------------------------------------------------------------------------
// Fleet: a pool of synchronous detectors, borrowed for one call
// -----------------------------------------------------------------------------
// A detector owns a QPL job and a scratch buffer and keeps mutable counters, so
// it cannot be used by two threads at once. It is *not* bound to a thread for
// its lifetime, though, and must not be: the executor starts fresh workers on
// every `sort_columns_parallel` call while the detector is constructed once per
// case, so a scheme that hands each new thread its own permanent slot needs as
// many slots as (iterations x workers) rather than as many as run concurrently.
// Borrowing instead bounds the pool by concurrency: a caller takes a detector
// for the duration of one detect() call and returns it. The mutex is held only
// across the handover, never across the scan, and a detect() call costs at
// least one accelerator round trip, so the handover is noise.
template <class DataType>
class TslIaaDetectorFleet {
  using detector_type = TslIaaRunDetector<DataType>;
  TslBorrowPool<detector_type> pool_;
  std::size_t min_offload_elements_;

 public:
  TslIaaDetectorFleet(
    TslIaaPath path,
    std::size_t worker_count,
    std::size_t region_bytes = tsl_iaa_default_region_bytes,
    std::size_t min_offload_elements = tsl_iaa_default_min_offload
  )
      // One spare: the caller's thread may also run work inline.
      : pool_(worker_count + 1, [&](std::size_t) {
          return std::make_unique<detector_type>(path, region_bytes,
                                                 min_offload_elements);
        }),
        min_offload_elements_(min_offload_elements) {}

  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    auto held = pool_.borrow();
    held->detect(values, begin, end, std::forward<Emit>(emit));
  }

  // The lease above is what a caller saves by declining a short range itself.
  auto min_offload_elements() const -> std::size_t { return min_offload_elements_; }

  auto aggregate_metrics() const -> TslIaaRunDetectorMetrics {
    TslIaaRunDetectorMetrics total{};
    pool_.for_each([&](detector_type const & detector) {
      auto const & m = detector.metrics();
      total.ranges += m.ranges;
      total.elements += m.elements;
      total.offloaded_elements += m.offloaded_elements;
      total.regions += m.regions;
      total.descriptors += m.descriptors;
      total.scanned_elements += m.scanned_elements;
      total.seam_comparisons += m.seam_comparisons;
      total.fallback_small += m.fallback_small;
      total.fallback_width += m.fallback_width;
      total.fallback_capacity += m.fallback_capacity;
      total.fallback_short_runs += m.fallback_short_runs;
      total.cpu_finished_elements += m.cpu_finished_elements;
      total.spans_emitted += m.spans_emitted;
    });
    return total;
  }

  void reset_metrics() {
    pool_.for_each([](detector_type & detector) { detector.reset_metrics(); });
  }
};


// -----------------------------------------------------------------------------
// Asynchronous detector
// -----------------------------------------------------------------------------
// Hands a sorted range to the accelerator and returns, so the calling worker
// goes back to sorting while the device scans. Concurrency comes from regions,
// which are independent of each other: `depth` of a range's regions have a scan
// in flight at once, and up to `slots` ranges are open concurrently.
//
// No thread waits on the device: `qpl_check_job` is a status read, and every
// worker calls `poll()` at its task boundaries. A range's spans are buffered per
// region and flushed in index order once all of its regions finish, which keeps
// the emitted order ascending even though regions complete out of order.
//
// On `TslIaaPath::SOFTWARE` this form is *not* asynchronous and its timings mean
// nothing: `qpl_submit_job` runs the scan on the calling thread there, so a
// submission costs a whole scan, and the queue bookkeeping it pays for buys
// nothing back. Measured on the software path it lands well behind the
// synchronous detector, which is expected rather than a defect -- the software
// path exists so this code can be proven correct without a device. Only
// `TslIaaPath::HARDWARE`, where a submission is a descriptor enqueue that
// returns immediately, makes the overlap real.
//
// Lifetime rules, as for the DSA asynchronous detector:
//   1. `emit` outlives the caller's frame -- it is stored and invoked later, on
//      whichever worker observes the last completion. It must be self-contained.
//   2. The range must stay sorted and immutable until the range completes. On
//      the post-sort path a task owns its range, descendants only write later
//      columns, and rows permuted inside an equal run carry identical values in
//      this column, so the bytes the device reads never change.
template <class DataType>
class TslIaaAsyncRunDetector {
  static_assert(std::is_integral_v<DataType>, "run detection needs an integral element type");

  struct region_state {
    std::size_t base = 0;
    std::size_t end = 0;
    std::size_t cursor = 0;
    std::vector<std::size_t> boundaries;  // strictly inside the region, ascending
    bool finished = false;
    bool scan_out = false;    // a scan for this region is in flight
    bool cpu_finish = false;  // offload abandoned; boundaries from `cursor` on are
                              // recovered by the CPU during the flush
  };

  struct range_state {
    DataType const * values = nullptr;
    std::size_t begin = 0;
    std::size_t end = 0;
    std::vector<region_state> regions;
    std::function<void(TslRunSpan)> emit;
    std::size_t regions_finished = 0;
    tsl_iaa_detail::offload_verdict verdict;
    bool active = false;
  };

#ifdef TSL_COSORT_ENABLE_IAA
  // One in-flight scan: a job, its output buffer, and which region it advances.
  struct scan_slot {
    tsl_iaa_detail::qpl_job_handle job;
    std::vector<std::uint8_t> out;
    range_state * range = nullptr;
    std::size_t region = 0;
    // The run being measured. A run longer than the window takes several
    // descriptors, and those land in different poll() calls, so the partial
    // measurement lives here rather than on the stack.
    DataType value{};         // value opening the run
    std::size_t run_base = 0; // absolute index the run starts at
    std::size_t matched = 0;  // elements of it confirmed so far
    std::size_t window = 0;   // elements this scan covers
    bool busy = false;
  };
  std::vector<scan_slot> scans_;
#endif

  TslIaaPath path_;
  std::size_t region_elements_;
  std::size_t min_offload_elements_;
  std::size_t run_length_floor_;
  std::size_t depth_;
  std::vector<std::unique_ptr<range_state>> ranges_;
  // Read by poll() before it takes the lock. Every worker polls at every task
  // boundary, and the overwhelmingly common answer is "nothing in flight", so
  // that answer must not cost a mutex acquisition and a walk of the slot table.
  std::atomic<std::size_t> in_flight_{0};
  TslPendingWork * pending_ = nullptr;
  mutable std::mutex mutex_;
  TslIaaRunDetectorMetrics metrics_{};

 public:
  TslIaaAsyncRunDetector(
    TslIaaPath path = TslIaaPath::HARDWARE,
    std::size_t slots = 16,
    std::size_t depth = 4,
    std::size_t region_bytes = tsl_iaa_default_region_bytes,
    std::size_t min_offload_elements = tsl_iaa_default_min_offload,
    std::size_t run_length_floor = tsl_iaa_default_run_length_floor
  )
      : path_(path),
        min_offload_elements_(min_offload_elements),
        run_length_floor_(std::max<std::size_t>(run_length_floor, 1)),
        depth_(std::max<std::size_t>(depth, 1)) {
    if (region_bytes == 0 || region_bytes % sizeof(DataType) != 0) {
      throw std::invalid_argument("region_bytes must be a non-zero multiple of the element width");
    }
    region_elements_ = region_bytes / sizeof(DataType);

    auto const range_slots = std::max<std::size_t>(slots, 1);
    ranges_.reserve(range_slots);
    for (std::size_t slot = 0; slot < range_slots; ++slot) {
      ranges_.push_back(std::make_unique<range_state>());
    }
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (tsl_iaa_detail::scan_supports_width<DataType>) {
      // Total in-flight descriptors: `depth` per open range.
      auto const scan_slots = range_slots * depth_;
      scans_.reserve(scan_slots);
      for (std::size_t slot = 0; slot < scan_slots; ++slot) {
        scan_slot entry;
        entry.job = tsl_iaa_detail::qpl_job_handle(path_);
        entry.out.assign(tsl_iaa_detail::scan_out_bytes(region_elements_), 0);
        scans_.push_back(std::move(entry));
      }
    }
#endif
  }

  void bind(TslPendingWork & pending) { pending_ = &pending; }

  // See sorting/common/run_discovery.hpp.
  auto min_offload_elements() const -> std::size_t { return min_offload_elements_; }

  auto path() const -> TslIaaPath { return path_; }

  auto aggregate_metrics() const -> TslIaaRunDetectorMetrics {
    std::lock_guard<std::mutex> lock(mutex_);
    return metrics_;
  }

  // Detector seam. `emit` is retained past this call.
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    if (end - begin < 2) {
      return;
    }

    auto inline_scalar = [&](std::size_t & counter) {
      {
        std::lock_guard<std::mutex> lock(mutex_);
        ++metrics_.ranges;
        metrics_.elements += end - begin;
        ++counter;
      }
      tsl_for_each_equal_run(values, begin, end, [&](TslRunSpan span) {
        {
          std::lock_guard<std::mutex> lock(mutex_);
          ++metrics_.spans_emitted;
        }
        emit(span);
      });
    };

    if constexpr (!tsl_iaa_detail::scan_supports_width<DataType>) {
      inline_scalar(metrics_.fallback_width);
      return;
    } else {
#ifdef TSL_COSORT_ENABLE_IAA
      if (end - begin < min_offload_elements_ || pending_ == nullptr) {
        inline_scalar(metrics_.fallback_small);
        return;
      }

      // The whole claim-register-submit sequence runs under one lock. It must:
      // add_pending before the range becomes visible to poll(), or a completion
      // could resolve a count that does not exist yet; and submit before
      // releasing, or a range could sit active with no descriptor in flight and
      // nothing scheduled to start one. Taking the executor's lock from inside
      // this one cannot deadlock, because the executor calls poll() without
      // holding its own.
      range_state * range = nullptr;
      std::vector<range_state *> completed;
      {
        std::lock_guard<std::mutex> lock(mutex_);
        ++metrics_.ranges;
        metrics_.elements += end - begin;
        for (auto & candidate : ranges_) {
          if (!candidate->active) {
            range = candidate.get();
            break;
          }
        }
        if (range == nullptr) {
          // Every slot is open. Falling back keeps the sort progressing instead
          // of blocking a worker on the device.
          ++metrics_.fallback_capacity;
        } else {
          metrics_.offloaded_elements += end - begin;
          pending_->add_pending(1);
          prepare_range(*range, values, begin, end, std::forward<Emit>(emit));
          try {
            fill_scan_slots(completed);
          } catch (...) {
            // Undo the registration before reporting, or the executor waits on
            // a unit that will never complete.
            release_range(*range);
            pending_->resolve_pending(1);
            pending_->fail(std::current_exception());
            return;
          }
        }
      }

      if (range == nullptr) {
        tsl_for_each_equal_run(values, begin, end, [&](TslRunSpan span) {
          {
            std::lock_guard<std::mutex> lock(mutex_);
            ++metrics_.spans_emitted;
          }
          emit(span);
        });
      }
      // A range abandoned before any descriptor went out is already complete
      // here, so nothing else will flush it.
      for (auto * finished : completed) {
        flush_range(*finished);
      }
#else
      inline_scalar(metrics_.fallback_small);
#endif
    }
  }

  // Folded into work the executor already does; never blocks.
  void poll() {
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (!tsl_iaa_detail::scan_supports_width<DataType>) {
      return;
    } else {
      if (in_flight_.load(std::memory_order_acquire) == 0) {
        return;
      }
      std::vector<range_state *> completed;
      try {
        std::lock_guard<std::mutex> lock(mutex_);
        for (auto & scan : scans_) {
          if (!scan.busy) {
            continue;
          }
          auto const status = qpl_check_job(scan.job.get());
          if (status == QPL_STS_BEING_PROCESSED) {
            continue;
          }
          if (status != QPL_STS_OK) {
            throw std::runtime_error("qpl_check_job failed, status " + std::to_string(status));
          }
          if (auto * range = retire_scan(scan); range != nullptr) {
            completed.push_back(range);
          }
        }
        fill_scan_slots(completed);
      } catch (...) {
        if (pending_ != nullptr) pending_->fail(std::current_exception());
        return;
      }

      // Flushing outside the lock: `emit` schedules sort tasks, and holding the
      // detector's mutex across that would serialize the executor on it.
      for (auto * range : completed) {
        flush_range(*range);
      }
    }
#endif
  }

 private:
#ifdef TSL_COSORT_ENABLE_IAA
  template <class Emit>
  void prepare_range(
    range_state & range,
    DataType const * values,
    std::size_t begin,
    std::size_t end,
    Emit && emit
  ) {
    range.values = values;
    range.begin = begin;
    range.end = end;
    range.emit = std::forward<Emit>(emit);
    range.regions_finished = 0;
    range.verdict = tsl_iaa_detail::offload_verdict(
      run_length_floor_, tsl_iaa_probe_descriptors
    );
    range.regions.clear();
    for (auto base = begin; base < end; base += region_elements_) {
      region_state region;
      region.base = base;
      region.end = std::min(base + region_elements_, end);
      region.cursor = base;
      range.regions.push_back(std::move(region));
    }
    metrics_.regions += range.regions.size();
    range.active = true;
  }

  // Gives every idle scan slot the next unstarted step of an open range, at most
  // `depth_` concurrent scans per range. Appends any range that this call itself
  // completed -- abandoning an offload can finish the last of a range's regions
  // with no scan in flight to notice it -- so the caller can flush it after
  // releasing the lock. Caller holds the mutex.
  void fill_scan_slots(std::vector<range_state *> & completed) {
    std::size_t scan_index = 0;
    for (auto & range_owner : ranges_) {
      auto & range = *range_owner;
      // A range whose regions are all finished is waiting to be flushed by
      // whoever completed it; touching it again would report it twice.
      if (!range.active || range.regions_finished == range.regions.size()) {
        continue;
      }
      std::size_t in_flight = 0;
      for (auto const & scan : scans_) {
        if (scan.busy && scan.range == &range) ++in_flight;
      }
      // The runs are too short to be worth a descriptor each: hand every
      // unfinished region to the CPU.
      if (range.verdict.give_up()) {
        if (abandon_offload(range)) {
          completed.push_back(&range);
        }
        continue;
      }
      for (std::size_t region_index = 0;
           region_index < range.regions.size() && in_flight < depth_;
           ++region_index) {
        auto & region = range.regions[region_index];
        if (region.finished || region.cpu_finish || region.cursor >= region.end) {
          continue;
        }
        if (region.scan_out) {
          continue;  // this region already has its one sequential scan out
        }
        while (scan_index < scans_.size() && scans_[scan_index].busy) {
          ++scan_index;
        }
        if (scan_index == scans_.size()) {
          return;  // no idle slot left
        }
        submit_scan(scans_[scan_index], range, region_index);
        ++in_flight;
      }
    }
  }

  // Marks every unfinished region of `range` for CPU completion. A region with a
  // scan still in flight keeps it -- the result is recorded normally and the
  // remainder of that region is picked up by the flush. Caller holds the mutex.
  // Returns true when this completed the range, i.e. no scan remains in flight.
  auto abandon_offload(range_state & range) -> bool {
    bool abandoned = false;
    for (auto & region : range.regions) {
      if (region.finished || region.cpu_finish) {
        continue;
      }
      region.cpu_finish = true;
      metrics_.cpu_finished_elements += region.end - region.cursor;
      abandoned = true;
      if (!region.scan_out) {
        ++range.regions_finished;
      }
    }
    if (!abandoned) {
      return false;
    }
    ++metrics_.fallback_short_runs;
    return range.regions_finished == range.regions.size();
  }

  // Starts measuring the run at a region's cursor. Caller holds the mutex.
  void submit_scan(scan_slot & scan, range_state & range, std::size_t region_index) {
    auto & region = range.regions[region_index];
    scan.range = &range;
    scan.region = region_index;
    scan.value = range.values[region.cursor];
    scan.run_base = region.cursor;
    scan.matched = 0;
    issue(scan, tsl_iaa_first_window(range.verdict.mean()));
  }

  // Issues one scan_eq for the slot's current run, covering at most `window`
  // elements and never past the region end. Caller holds the mutex.
  void issue(scan_slot & scan, std::size_t window) {
    auto const & region = scan.range->regions[scan.region];
    auto const from = scan.run_base + scan.matched;
    scan.window = std::min(window, region.end - from);
    tsl_iaa_detail::configure_scan_eq<DataType>(
      scan.job.get(), scan.range->values + from, scan.window, scan.value,
      scan.out.data(), scan.out.size()
    );
    scan.busy = true;
    scan.range->regions[scan.region].scan_out = true;
    in_flight_.fetch_add(1, std::memory_order_relaxed);
    ++metrics_.descriptors;
    metrics_.scanned_elements += scan.window;
    tsl_iaa_detail::submit_retrying(scan.job.get());
  }

  // Records a finished scan and advances its region. Returns the range when that
  // scan completed the last of its regions. Caller holds the mutex.
  auto retire_scan(scan_slot & scan) -> range_state * {
    auto & range = *scan.range;
    auto & region = range.regions[scan.region];

    auto const matched = static_cast<std::size_t>(scan.job.get()->sum_value);
    scan.busy = false;
    region.scan_out = false;
    in_flight_.fetch_sub(1, std::memory_order_relaxed);
    if (matched > scan.window) {
      throw std::runtime_error(
        "IAA scan_eq matched " + std::to_string(matched) + " of "
        + std::to_string(scan.window)
      );
    }
    range.verdict.record(matched);
    scan.matched += matched;

    // The window filled and the region has more to give: the run may continue,
    // so gallop instead of concluding it here.
    auto const from = scan.run_base + scan.matched;
    if (matched == scan.window && from < region.end) {
      issue(scan, scan.window * 2);
      return nullptr;
    }
    if (scan.matched == 0) {
      throw std::runtime_error("IAA scan_eq reported an empty run at a live cursor");
    }

    auto const run_end = scan.run_base + scan.matched;
    if (run_end < region.end) {
      region.boundaries.push_back(run_end - 1);
    }
    region.cursor = run_end;
    if (region.cursor >= region.end || region.cpu_finish) {
      region.finished = region.cursor >= region.end;
      ++range.regions_finished;
      if (range.regions_finished == range.regions.size()) {
        return &range;
      }
    }
    return nullptr;
  }

  // Returns a range slot to the free pool. Caller holds the mutex.
  void release_range(range_state & range) {
    range.emit = nullptr;
    range.regions.clear();
    range.values = nullptr;
    range.active = false;
  }

  // Converts a completed range's per-region boundaries into ascending spans.
  // Called without the mutex; the range slot is still marked active, so nothing
  // else can claim it until this returns.
  void flush_range(range_state & range) {
    auto const * values = range.values;
    auto run_begin = range.begin;
    std::size_t spans = 0;
    std::size_t seams = 0;

    auto on_boundary = [&](std::size_t position) {
      if (position + 1 - run_begin > 1) {
        ++spans;
        range.emit(TslRunSpan{run_begin, position + 1});
      }
      run_begin = position + 1;
    };

    for (std::size_t index = 0; index < range.regions.size(); ++index) {
      auto const & region = range.regions[index];
      for (auto position : region.boundaries) {
        on_boundary(position);
      }
      if (region.cpu_finish && region.cursor < region.end) {
        // The offload gave up here: recover the rest of this region's
        // boundaries with the scalar comparison, still in ascending order.
        for (auto position = region.cursor; position + 1 < region.end; ++position) {
          if (values[position] != values[position + 1]) {
            on_boundary(position);
          }
        }
      }
      // The seam between two regions belongs to neither region's scans.
      if (region.end < range.end) {
        ++seams;
        if (values[region.end - 1] != values[region.end]) {
          on_boundary(region.end - 1);
        }
      }
    }
    if (range.end - run_begin > 1) {
      ++spans;
      range.emit(TslRunSpan{run_begin, range.end});
    }

    auto * pending = pending_;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      metrics_.spans_emitted += spans;
      metrics_.seam_comparisons += seams;
      release_range(range);
    }
    // After every child of this unit has been scheduled, never before.
    if (pending != nullptr) {
      pending->resolve_pending(1);
    }
  }
#endif
};
