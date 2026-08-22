#pragma once

// Distinct-value frequencies for an arbitrary range, offloaded to the Intel
// In-Memory Analytics Accelerator via QPL.
//
// `distinct_frequencies(data)` returns one entry per distinct value in `data`
// together with how often it occurs. The counting is `scan_eq`: QPL writes a
// one-bit-per-element result vector and the completion record's `sum_value`
// aggregate carries its population count, so one descriptor answers "how many
// copies of v are in this range" without the CPU reading the range.
//
// The file is standalone apart from QPL and the shared pivot rule in
// sort_helpers.hpp. It repeats the small path enum rather than depend on
// iaa_run_detector.hpp, whose detector contract pulls in the co-sort task
// headers, and it makes no assumption about the input being sorted.
//
// -----------------------------------------------------------------------------
// Why the direct formulation is quadratic
// -----------------------------------------------------------------------------
// scan_eq counts matches of a value the caller must already know, so a histogram
// needs the distinct set first and one count per member. Discovering a value,
// scanning the whole range for it and repeating reads the whole range once per
// distinct value: D descriptors over n elements each, O(n*D). At n = 1M and
// D = 1000 that is a billion element reads for an answer one CPU pass produces
// in a million, and it gets worse with cardinality rather than better.
//
// -----------------------------------------------------------------------------
// Three-way partition without the sort
// -----------------------------------------------------------------------------
// A scan_eq only has to read elements that could still match, so the fix is to
// stop handing it elements that cannot. `select` compacts a range through a bit
// mask and a scan produces exactly such a mask, so the accelerator partitions
// its own input:
//
//   w  = a sampled element of the range      pivot: a value known to be present
//   e  = scan_eq(w)      -> frequency of w   final the moment it completes
//   lo = scan_lt(w), select -> elements < w  strictly fewer distinct values
//   hi = scan_gt(w), select -> elements > w
//
// then recurse into `lo` and `hi`. This is Dijkstra's three-way partition with
// the equal bucket replaced by its own population count. The two sides are
// disjoint in value, so no later descriptor ever reads an element that cannot
// match its pivot, and nothing is ever sorted: only the counts are wanted.
//
// Each node resolves exactly one distinct value, so the walk visits at most D
// nodes, and a node costs three scans plus one select per `select_block_elements`
// of each side -- descriptor count is O(D) plus the compaction traffic, against
// the O(D) floor for an answer with D entries. Elements read is O(n * depth),
// the depth being that of a three-way quicksort over D distinct keys: O(log D)
// as long as the pivot splits. Measured over 200k elements on the software path,
// nodes == D up to D = 4096, depth is about 1.4*log2(D) and reads are about
// 4.7*log2(D) per element -- for random, sorted and organ-pipe input alike, the
// last being the shape that defeats a fixed pivot rule (see sort_helpers.hpp).
//
// -----------------------------------------------------------------------------
// What the CPU is allowed to do
// -----------------------------------------------------------------------------
// No comparison and no data movement happens on the CPU: scan compares, select
// moves, and nothing is ever sorted or swapped. What is left is O(1) per
// resolved value -- the nine pivot samples and one map update -- plus the
// elements of a node no larger than `scalar_leaf_elements`, tallied directly
// because a descriptor round trip costs more than a handful of loads. A single
// element is the important case: one load against the three descriptors a split
// would need, and an all-distinct range is nothing but those.
//
// That stays cheap only while the distinct count is small against the range.
// Measured over 200k uint32 elements, the CPU touches 0.1% of the range at
// D = 16, 1.2% at D = 256, 18% at D = 4096, and past D = 60k it performs more
// (scattered) loads than the range has elements, where the per-node sampling
// alone outgrows a linear CPU pass. This is a low-cardinality operation:
// `min_offload_elements` keeps it off short ranges, but nothing keeps it off a
// high-cardinality one.
//
// -----------------------------------------------------------------------------
// Pipelining: one thread, several descriptors in flight
// -----------------------------------------------------------------------------
// Within a node the chain scan_eq -> scan_lt -> select -> scan_gt -> select is
// strictly sequential; every descriptor needs the result of the one before it.
// Running that chain with qpl_execute_job spends one device round trip of thread
// time per descriptor, and a range with D distinct values needs O(D) of them
// back to back: the accelerator does the work, and the caller's thread waits out
// the whole latency chain.
//
// Independent nodes have no such dependency. Children are published only once
// their parent's compactions retire, so the nodes on the work stack and the
// nodes in flight never include both a node and one of its descendants -- they
// are pairwise disjoint in the scratch buffers and can advance at the same time.
// `in_flight_descriptors` slots each own a job and a mask buffer and carry one
// node through its chain, and the walk keeps them fed from the work stack.
//
// qpl_submit_job / qpl_check_job therefore replace qpl_execute_job, and no call
// waits on the device:
//
//   start(data, size)   seeds the walk
//   poll()              retires what completed, submits what it can, and reports
//                       whether the answer is ready -- at most one submission
//                       per slot, so its cost is bounded
//   take()              moves the map out
//
// count() is that loop spun to completion, for a caller that just wants the
// answer. A caller with work of its own calls poll() at its own task boundaries
// instead, and the walk proceeds in the gaps.
//
// On the QPL software path qpl_submit_job runs the job inline and qpl_check_job
// reports it complete at once, so there poll() performs the work rather than
// waiting for it. The pipeline is exercised for correctness on that path; the
// overlap it buys is a hardware-path property.
//
// -----------------------------------------------------------------------------
// Ping-pong buffers
// -----------------------------------------------------------------------------
// `select` cannot write into the range it reads, so a node's two children are
// compacted into the *other* of two scratch buffers, at the offsets the parent
// occupied: left at [offset, offset + below), right after it. Children therefore
// live inside the parent's offset range, siblings hold disjoint ranges, and both
// selects finish before either child is entered -- so a depth-first walk that
// alternates buffers never clobbers pending work, whichever order it takes the
// children in. It takes the smaller child first and leaves the larger on the
// stack, which bounds the stack logarithmically. The caller's range is only ever
// read, and only by the root.
//
// -----------------------------------------------------------------------------
// One QPL defect to work around
// -----------------------------------------------------------------------------
// QPL 1.9.0's software `select` unpacks source-1 and the mask in chunks of
// different sizes and exits its loop on the source stream alone, so once the two
// fall out of phase it drops whatever the last source chunk held past the mask
// it had -- silently, with QPL_STS_OK. Measured on the software path, a select
// never covers more than 16384 elements of input. Compactions are therefore cut
// into `select_block_elements` blocks, and every compaction's element total is
// checked against the population count the scan already reported, so a short
// compaction raises rather than corrupts a count. The hardware path builds one
// descriptor and has no such staging loop; the blocks only bound its descriptor
// size.
//
// Limits:
//   * QPL scan takes `src1_bit_width <= 32`, so 8-byte elements have no
//     single-scan form and fall back to a CPU tally (`fallback_width`).
//   * Ordering is by the raw unsigned bit pattern, which is not the signed order
//     of a signed `DataType`. The partition needs only *an* order and equality
//     is equality in either, so the frequencies are identical; only the shape of
//     the recursion differs.
//   * `TslIaaFrequencyPath::HARDWARE` needs an IAA device;
//     `TslIaaFrequencyPath::SOFTWARE` runs the identical QPL logic on the CPU,
//     which is how the differential test validates this file on a host without
//     one.
//   * A range longer than `region_elements` is cut into regions, because
//     `num_input_elements` and `available_in` are 32-bit fields and the scratch
//     buffers are sized to a region. Frequencies add across regions, so each is
//     walked independently into the same map -- at the cost of one partition
//     tree per region.

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

#if __cplusplus >= 202002L && __has_include(<span>)
#include <span>
#define TSL_IAA_FREQUENCY_HAVE_SPAN 1
#endif

#ifdef TSL_COSORT_ENABLE_IAA
#include <qpl/qpl.h>
#endif

#include "sorting/common/sort_helpers.hpp"


// Which QPL execution path services a count() call. SOFTWARE needs no device,
// so a build with TSL_COSORT_ENABLE_IAA on can still exercise every line of this
// file on a host whose accelerator is a DSA.
enum class TslIaaFrequencyPath { SOFTWARE, HARDWARE };

inline auto tsl_iaa_frequency_path_name(TslIaaFrequencyPath path) -> char const * {
  return path == TslIaaFrequencyPath::HARDWARE ? "iaa_hw" : "iaa_sw";
}

// Default region length. A region bounds the scratch buffers and the reach of
// one descriptor; it is not a transfer maximum, so it is chosen for memory
// rather than for the hardware.
inline constexpr std::size_t tsl_iaa_frequency_default_region_elements = 1u << 24;
// Below this a CPU tally beats a descriptor round trip.
inline constexpr std::size_t tsl_iaa_frequency_default_min_offload = 4096;
// A node no larger than this is tallied by the CPU rather than partitioned.
inline constexpr std::size_t tsl_iaa_frequency_default_scalar_leaf = 8;
// Elements one select job may cover. See the note on QPL's software select at
// the top of this file: past its staging buffer it drops the rest of its input
// and still reports QPL_STS_OK, so a compaction is cut into jobs this long.
// Must be a multiple of 8 so every block starts on a mask byte.
inline constexpr std::size_t tsl_iaa_frequency_default_select_block = 16u * 1024u;
// Nodes carried through their descriptor chains at once. Within a node every
// descriptor waits on the one before it, so this is the only thing that keeps
// more than one descriptor in flight.
inline constexpr std::size_t tsl_iaa_frequency_default_in_flight = 8;


struct TslIaaFrequencyOptions {
  TslIaaFrequencyPath path = TslIaaFrequencyPath::HARDWARE;
  std::size_t region_elements = tsl_iaa_frequency_default_region_elements;
  std::size_t min_offload_elements = tsl_iaa_frequency_default_min_offload;
  std::size_t scalar_leaf_elements = tsl_iaa_frequency_default_scalar_leaf;
  std::size_t select_block_elements = tsl_iaa_frequency_default_select_block;
  std::size_t in_flight_descriptors = tsl_iaa_frequency_default_in_flight;
};


// Accumulated across count() calls, so a benchmark can read one total.
struct TslIaaFrequencyMetrics {
  std::size_t calls = 0;              // count() calls over a non-empty range
  std::size_t elements = 0;           // elements those calls covered
  std::size_t offloaded_elements = 0; // elements that reached a descriptor
  std::size_t regions = 0;
  std::size_t nodes = 0;              // partition nodes visited == values resolved
  std::size_t equality_scans = 0;     // scan_eq: one per node, the counting op
  std::size_t pivot_scans = 0;        // scan_lt / scan_gt: the partition masks
  std::size_t selects = 0;            // compactions
  std::size_t scanned_elements = 0;   // elements the accelerator read
  std::size_t moved_elements = 0;     // elements select wrote
  std::size_t uniform_nodes = 0;      // nodes one scan_eq finished
  std::size_t scalar_leaves = 0;      // nodes the CPU tallied instead
  std::size_t scalar_elements = 0;    // elements those nodes held
  std::size_t max_depth = 0;
  std::size_t max_in_flight = 0;      // peak nodes advancing at once
  std::size_t distinct_values = 0;
  std::size_t fallback_small = 0;     // range below the offload threshold
  std::size_t fallback_width = 0;     // 8-byte elements: no single-scan form
  std::size_t fallback_disabled = 0;  // built without TSL_COSORT_ENABLE_IAA

  auto descriptors() const -> std::size_t {
    return equality_scans + pivot_scans + selects;
  }
};


namespace tsl_iaa_frequency_detail {

#ifdef TSL_COSORT_ENABLE_IAA

inline auto to_qpl_path(TslIaaFrequencyPath path) -> qpl_path_t {
  return path == TslIaaFrequencyPath::HARDWARE ? qpl_path_hardware : qpl_path_software;
}

// An initialized qpl_job plus the buffer it lives in. Movable so the moved-from
// object is neutered and its destructor is a no-op.
class qpl_job_handle {
  std::unique_ptr<std::uint8_t[]> buffer_;
  qpl_job * job_ = nullptr;

 public:
  qpl_job_handle() = default;

  explicit qpl_job_handle(TslIaaFrequencyPath path) {
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
        + (path == TslIaaFrequencyPath::HARDWARE
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

// QPL scan compares at most 32 bits per element.
template <class DataType>
inline constexpr bool scan_supports_width = sizeof(DataType) <= 4;

// Bit-vector bytes a scan over `count` elements needs, plus slack so a partial
// final byte never sits on the boundary.
inline auto mask_bytes_for(std::size_t count) -> std::size_t {
  return (count + 7u) / 8u + 8u;
}

}  // namespace tsl_iaa_frequency_detail


// -----------------------------------------------------------------------------
// Counter: one instance per thread
// -----------------------------------------------------------------------------
// Holds a fleet of QPL jobs, two scratch buffers and mutable counters, so it
// cannot be shared. Keep one alive across calls to reuse the allocations.
//
// `count()` is the convenience form for a caller that only wants the answer.
// `start()` / `poll()` / `take()` is the same walk with the waiting handed back:
// poll() harvests what completed and submits what it can, then returns.
template <class DataType>
class TslIaaDistinctFrequencies {
 public:
  using value_type = std::remove_cv_t<DataType>;
  using map_type = std::unordered_map<value_type, std::size_t>;

 private:
  static_assert(std::is_integral_v<value_type>, "frequency counting needs an integral element type");
  static_assert(!std::is_same_v<value_type, bool>, "bool is not a packed-array element type");
  static_assert(sizeof(value_type) <= 8, "element width above 8 bytes is not a sort key here");

  // Partitioning orders by the raw bit pattern, which is what QPL compares.
  using raw_type = std::make_unsigned_t<value_type>;

  static constexpr bool offloadable = tsl_iaa_frequency_detail::scan_supports_width<value_type>;
  // Buffer id of the caller's range, which is read but never written.
  static constexpr unsigned caller_buffer = 2u;

  struct node {
    unsigned buffer;
    std::size_t offset;
    std::size_t count;
    std::size_t depth;
  };

#ifdef TSL_COSORT_ENABLE_IAA
  // Where one node stands in its own descriptor chain.
  enum class stage : unsigned char {
    idle,
    equality,      // scan_eq: the pivot's frequency
    below_scan,    // scan_lt: the low side's mask and size
    below_select,  // compacting the low side, one block per submission
    above_scan,    // scan_gt: the high side's mask
    above_select   // compacting the high side
  };

  // One node in flight: the job carrying its current descriptor, the mask that
  // descriptor produced or consumes, and where the chain has got to.
  struct slot {
    tsl_iaa_frequency_detail::qpl_job_handle job;
    std::vector<std::uint8_t> mask;
    stage phase = stage::idle;
    node work{};
    raw_type pivot{};
    std::size_t equal = 0;
    std::size_t below = 0;
    std::size_t above = 0;
    unsigned child = 0;
    std::size_t block_start = 0;  // input elements the current side has submitted
    std::size_t written = 0;      // output elements it has produced
  };
#endif

  TslIaaFrequencyPath path_;
  std::size_t region_elements_;
  std::size_t min_offload_elements_;
  std::size_t scalar_leaf_elements_;
  std::size_t select_block_elements_;
  std::size_t in_flight_slots_;
  TslIaaFrequencyMetrics metrics_{};
  map_type result_{};
  bool running_ = false;
#ifdef TSL_COSORT_ENABLE_IAA
  std::vector<slot> slots_{};
  std::vector<node> stack_{};
  std::array<std::vector<raw_type>, 2> scratch_{};
  std::size_t capacity_ = 0;
  std::size_t busy_ = 0;
  raw_type const * caller_ = nullptr;      // the region the root node walks
  raw_type const * input_ = nullptr;       // the whole range, as raw bit patterns
  std::size_t input_size_ = 0;
  std::size_t next_region_ = 0;            // elements already handed to a region
#endif

 public:
  explicit TslIaaDistinctFrequencies(TslIaaFrequencyOptions const & options = {})
      : path_(options.path),
        region_elements_(options.region_elements),
        min_offload_elements_(options.min_offload_elements),
        scalar_leaf_elements_(std::max<std::size_t>(options.scalar_leaf_elements, 1)),
        select_block_elements_(options.select_block_elements),
        in_flight_slots_(std::max<std::size_t>(options.in_flight_descriptors, 1)) {
    if (region_elements_ == 0) {
      throw std::invalid_argument("region_elements must be non-zero");
    }
    // available_in / available_out are byte counts in a 32-bit field.
    if (region_elements_ > 0xFFFFFFFFull / sizeof(raw_type)) {
      throw std::invalid_argument("region_elements exceeds the addressable scan length");
    }
    if (select_block_elements_ == 0 || select_block_elements_ % 8 != 0) {
      throw std::invalid_argument("select_block_elements must be a non-zero multiple of 8");
    }
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (offloadable) {
      slots_.reserve(in_flight_slots_);
      for (std::size_t index = 0; index < in_flight_slots_; ++index) {
        slot entry;
        entry.job = tsl_iaa_frequency_detail::qpl_job_handle(path_);
        slots_.push_back(std::move(entry));
      }
    }
#endif
  }

  TslIaaDistinctFrequencies(TslIaaDistinctFrequencies const &) = delete;
  auto operator=(TslIaaDistinctFrequencies const &) -> TslIaaDistinctFrequencies & = delete;

  // A job still in flight would write into a freed completion record, so the
  // counter cannot be dropped mid-walk without waiting the device out.
  ~TslIaaDistinctFrequencies() {
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (offloadable) {
      drain();
    }
#endif
  }

  auto path() const -> TslIaaFrequencyPath { return path_; }
  auto region_elements() const -> std::size_t { return region_elements_; }
  auto in_flight_capacity() const -> std::size_t { return in_flight_slots_; }
  auto metrics() const -> TslIaaFrequencyMetrics const & { return metrics_; }
  void reset_metrics() { metrics_ = {}; }

  // One entry per distinct value in [data, data + size), mapped to its count.
  // Spins the non-blocking walk to completion.
  auto count(DataType const * data, std::size_t size) -> map_type {
    start(data, size);
    while (!poll()) {
    }
    return take();
  }

  // Seeds a walk over [data, data + size), which must stay alive and unchanged
  // until the walk finishes. A range that never reaches the accelerator -- an
  // 8-byte element width, a range below the offload threshold, a build without
  // QPL -- is answered here, and poll() then reports done immediately.
  void start(DataType const * data, std::size_t size) {
    if (running_) {
      throw std::logic_error("a count is already in progress");
    }
    result_.clear();
    if (size == 0) {
      return;
    }
    ++metrics_.calls;
    metrics_.elements += size;

    if constexpr (!offloadable) {
      ++metrics_.fallback_width;
      tally_range(data, size, result_);
    } else {
#ifdef TSL_COSORT_ENABLE_IAA
      if (size < min_offload_elements_) {
        ++metrics_.fallback_small;
        tally_range(data, size, result_);
        return;
      }
      metrics_.offloaded_elements += size;
      // Permitted aliasing: an integer object may be read through the
      // corresponding unsigned type, and QPL reads it as bytes regardless.
      input_ = reinterpret_cast<raw_type const *>(data);
      input_size_ = size;
      next_region_ = 0;
      stack_.clear();
      running_ = true;
#else
      ++metrics_.fallback_disabled;
      tally_range(data, size, result_);
#endif
    }
  }

  // Advances the walk by one sweep: every slot whose descriptor has retired
  // moves one stage on, and every free slot picks up a node. Returns whether the
  // answer is ready. Never waits on the device.
  auto poll() -> bool {
#ifdef TSL_COSORT_ENABLE_IAA
    if constexpr (offloadable) {
      if (!running_) {
        return true;
      }
      try {
        harvest();
        fill();
      } catch (...) {
        drain();
        throw;
      }
      if (busy_ == 0 && stack_.empty() && next_region_ >= input_size_) {
        running_ = false;
      }
      return !running_;
    }
#endif
    return true;
  }

  auto running() const -> bool { return running_; }

  // Moves the finished answer out.
  auto take() -> map_type {
    if (running_) {
      throw std::logic_error("take() called before the count finished");
    }
    auto answer = std::move(result_);
    result_.clear();
    metrics_.distinct_values += answer.size();
    return answer;
  }

 private:
  void tally_range(DataType const * data, std::size_t size, map_type & frequencies) const {
    for (std::size_t index = 0; index < size; ++index) {
      ++frequencies[data[index]];
    }
  }

  static auto to_value(raw_type raw) -> value_type {
    value_type value;
    std::memcpy(&value, &raw, sizeof(value));
    return value;
  }

#ifdef TSL_COSORT_ENABLE_IAA
  void reserve(std::size_t region) {
    if (capacity_ >= region) {
      return;
    }
    capacity_ = region;
    for (auto & buffer : scratch_) {
      buffer.assign(region, raw_type{0});
    }
  }

  auto buffer_of(unsigned id) const -> raw_type const * {
    return id == caller_buffer ? caller_ : scratch_[id].data();
  }

  // The root reads the caller's range and compacts into scratch 0; every deeper
  // node compacts into the buffer it does not occupy.
  static auto child_buffer(unsigned id) -> unsigned { return id == 0u ? 1u : 0u; }

  void tally_leaf(raw_type const * data, std::size_t count, map_type & frequencies) {
    ++metrics_.scalar_leaves;
    metrics_.scalar_elements += count;
    for (std::size_t index = 0; index < count; ++index) {
      ++frequencies[to_value(data[index])];
    }
  }

  // -- work list ---------------------------------------------------------------

  // The next region becomes work only once the current one has drained: the
  // scratch buffers are sized to one region and indexed by offsets inside it, and
  // reserve() may move them.
  auto seed_region() -> bool {
    if (next_region_ >= input_size_) {
      return false;
    }
    auto const region = std::min(region_elements_, input_size_ - next_region_);
    ++metrics_.regions;
    reserve(region);
    caller_ = input_ + next_region_;
    next_region_ += region;
    stack_.push_back(node{caller_buffer, 0, region, 0});
    return true;
  }

  // Pops the next node needing a descriptor, tallying the small ones on the way.
  auto take_work(node & taken) -> bool {
    for (;;) {
      if (stack_.empty()) {
        if (busy_ != 0 || !seed_region()) {
          return false;
        }
        continue;
      }
      auto const candidate = stack_.back();
      stack_.pop_back();
      if (candidate.count == 0) {
        continue;
      }
      ++metrics_.nodes;
      metrics_.max_depth = std::max(metrics_.max_depth, candidate.depth);
      if (candidate.count <= scalar_leaf_elements_) {
        tally_leaf(buffer_of(candidate.buffer) + candidate.offset, candidate.count, result_);
        continue;
      }
      taken = candidate;
      return true;
    }
  }

  void fill() {
    for (auto & entry : slots_) {
      if (entry.phase != stage::idle) {
        continue;
      }
      node next{};
      if (!take_work(next)) {
        return;
      }
      begin_node(entry, next);
    }
  }

  // -- the chain ---------------------------------------------------------------

  void begin_node(slot & entry, node const & work) {
    entry.work = work;
    entry.equal = 0;
    entry.below = 0;
    entry.above = 0;
    entry.block_start = 0;
    entry.written = 0;
    auto const needed = tsl_iaa_frequency_detail::mask_bytes_for(work.count);
    if (entry.mask.size() < needed) {
      entry.mask.assign(needed, 0);
    }
    // A value known to be present, chosen to split the node rather than peel
    // one value off it. Seeding the sample from the node's own coordinates
    // keeps it reproducible: the same range always yields the same pivot.
    auto const seed = work.offset * 0x9E3779B1ull + work.count * 31ull + work.depth;
    entry.pivot = tsl_pivot_of(buffer_of(work.buffer) + work.offset, work.count, seed);
    ++busy_;
    metrics_.max_in_flight = std::max(metrics_.max_in_flight, busy_);
    submit_scan(entry, qpl_op_scan_eq, stage::equality);
  }

  void release(slot & entry) {
    entry.phase = stage::idle;
    --busy_;
  }

  // Children become work only here, after both compactions have retired: until
  // then the node's own elements are still the source of a descriptor, and the
  // children's buffer range overlaps them.
  void publish(slot & entry) {
    auto const depth = entry.work.depth + 1;
    node const low{entry.child, entry.work.offset, entry.below, depth};
    node const high{entry.child, entry.work.offset + entry.below, entry.above, depth};
    auto const & smaller = entry.below <= entry.above ? low : high;
    auto const & larger = entry.below <= entry.above ? high : low;
    // Larger first, so the smaller side is on top and the walk stays depth-first.
    if (larger.count != 0) {
      stack_.push_back(larger);
    }
    if (smaller.count != 0) {
      stack_.push_back(smaller);
    }
  }

  void harvest() {
    for (auto & entry : slots_) {
      if (entry.phase == stage::idle) {
        continue;
      }
      auto const status = qpl_check_job(entry.job.get());
      if (status == QPL_STS_BEING_PROCESSED) {
        continue;
      }
      if (status != QPL_STS_OK) {
        throw std::runtime_error("qpl_check_job failed, status " + std::to_string(status));
      }
      advance(entry);
    }
  }

  // Retires the descriptor that just completed and submits the next one in the
  // node's chain, or frees the slot. One stage per call, so a poll() sweep costs
  // at most one submission per slot.
  void advance(slot & entry) {
    auto * job = entry.job.get();
    switch (entry.phase) {
      case stage::equality: {
        auto const matched = static_cast<std::size_t>(job->sum_value);
        if (matched == 0) {
          throw std::runtime_error("IAA scan_eq found no copy of a value taken from the range");
        }
        if (matched > entry.work.count) {
          throw std::runtime_error(
            "IAA scan_eq matched " + std::to_string(matched) + " of "
            + std::to_string(entry.work.count)
          );
        }
        entry.equal = matched;
        result_[to_value(entry.pivot)] += matched;
        if (matched == entry.work.count) {
          ++metrics_.uniform_nodes;
          release(entry);
          return;
        }
        entry.child = child_buffer(entry.work.buffer);
        // Nothing is below the smallest representable pivot, so that scan is
        // knowledge the walk already has.
        if (entry.pivot != raw_type{0}) {
          submit_scan(entry, qpl_op_scan_lt, stage::below_scan);
          return;
        }
        entry.below = 0;
        begin_high(entry);
        return;
      }
      case stage::below_scan: {
        entry.below = static_cast<std::size_t>(job->sum_value);
        if (entry.below > entry.work.count - entry.equal) {
          throw std::runtime_error(
            "IAA scan_lt matched " + std::to_string(entry.below) + ", above the "
            + std::to_string(entry.work.count - entry.equal) + " elements left"
          );
        }
        if (entry.below != 0) {
          entry.block_start = 0;
          entry.written = 0;
          submit_select(entry, entry.work.offset, stage::below_select);
          return;
        }
        begin_high(entry);
        return;
      }
      case stage::below_select: {
        entry.written += job->total_out / sizeof(raw_type);
        if (entry.block_start < entry.work.count) {
          submit_select(entry, entry.work.offset, stage::below_select);
          return;
        }
        check_compaction(entry.written, entry.below);
        metrics_.moved_elements += entry.written;
        begin_high(entry);
        return;
      }
      case stage::above_scan: {
        auto const matched = static_cast<std::size_t>(job->sum_value);
        if (matched != entry.above) {
          throw std::runtime_error(
            "IAA scan_gt matched " + std::to_string(matched) + ", expected "
            + std::to_string(entry.above)
          );
        }
        entry.block_start = 0;
        entry.written = 0;
        submit_select(entry, entry.work.offset + entry.below, stage::above_select);
        return;
      }
      case stage::above_select: {
        entry.written += job->total_out / sizeof(raw_type);
        if (entry.block_start < entry.work.count) {
          submit_select(entry, entry.work.offset + entry.below, stage::above_select);
          return;
        }
        check_compaction(entry.written, entry.above);
        metrics_.moved_elements += entry.written;
        publish(entry);
        release(entry);
        return;
      }
      case stage::idle:
        return;
    }
  }

  // The low side is settled; take the high side, or finish the node.
  void begin_high(slot & entry) {
    entry.above = entry.work.count - entry.equal - entry.below;
    if (entry.above != 0) {
      submit_scan(entry, qpl_op_scan_gt, stage::above_scan);
      return;
    }
    publish(entry);
    release(entry);
  }

  static void check_compaction(std::size_t written, std::size_t expected) {
    if (written != expected) {
      throw std::runtime_error(
        "IAA select compacted " + std::to_string(written) + " elements, expected "
        + std::to_string(expected)
      );
    }
  }

  // -- descriptors -------------------------------------------------------------

  // One scan over the whole node against its pivot, leaving its bit vector in
  // the slot's mask for the compaction that follows. The population count is
  // read on retirement; for scan_eq it is the pivot's frequency.
  void submit_scan(slot & entry, qpl_operation op, stage phase) {
    auto const count = entry.work.count;
    auto * job = entry.job.get();
    job->op = op;
    job->parser = qpl_p_le_packed_array;  // densely packed fixed-width integers
    job->src1_bit_width = static_cast<std::uint32_t>(sizeof(raw_type) * 8);
    job->num_input_elements = static_cast<std::uint32_t>(count);
    job->next_in_ptr = source_bytes(entry, 0);
    job->available_in = static_cast<std::uint32_t>(count * sizeof(raw_type));
    job->next_src2_ptr = nullptr;
    job->available_src2 = 0;
    job->src2_bit_width = 0;
    job->next_out_ptr = entry.mask.data();
    job->available_out = static_cast<std::uint32_t>(entry.mask.size());
    job->out_bit_width = qpl_ow_nom;  // nominal bit vector -> sum_value populated
    job->param_low = static_cast<std::uint32_t>(entry.pivot);
    job->param_high = static_cast<std::uint32_t>(entry.pivot);
    job->drop_initial_bytes = 0;
    job->initial_output_index = 0;
    job->flags = QPL_FLAG_FIRST | QPL_FLAG_LAST | QPL_FLAG_OMIT_CHECKSUMS;

    if (op == qpl_op_scan_eq) {
      ++metrics_.equality_scans;
    } else {
      ++metrics_.pivot_scans;
    }
    metrics_.scanned_elements += count;
    tsl_iaa_frequency_detail::submit_retrying(job);
    entry.phase = phase;
  }

  // Compacts one block of the node through the mask the preceding scan wrote,
  // appending to what the earlier blocks of this side produced. Select compacts
  // in input order, so the blocks concatenate into the whole compaction, and each
  // starts on a mask byte because the block length is a multiple of 8.
  void submit_select(slot & entry, std::size_t destination_offset, stage phase) {
    auto const start = entry.block_start;
    auto const block = std::min(select_block_elements_, entry.work.count - start);
    auto * destination =
      scratch_[entry.child].data() + destination_offset + entry.written;
    auto const room = capacity_ - destination_offset - entry.written;

    auto * job = entry.job.get();
    job->op = qpl_op_select;
    job->parser = qpl_p_le_packed_array;
    job->src1_bit_width = static_cast<std::uint32_t>(sizeof(raw_type) * 8);
    job->num_input_elements = static_cast<std::uint32_t>(block);
    job->next_in_ptr = source_bytes(entry, start);
    job->available_in = static_cast<std::uint32_t>(block * sizeof(raw_type));
    job->next_src2_ptr = entry.mask.data() + start / 8;
    job->available_src2 = static_cast<std::uint32_t>((block + 7) / 8);
    job->src2_bit_width = 1;  // source-2 is the scan's bit vector
    job->next_out_ptr = reinterpret_cast<std::uint8_t *>(destination);
    job->available_out = static_cast<std::uint32_t>(room * sizeof(raw_type));
    job->out_bit_width = qpl_ow_nom;
    job->param_low = 0;
    job->param_high = 0;
    job->drop_initial_bytes = 0;
    job->initial_output_index = 0;
    // Nothing here reads select's aggregates, and QPL computes them over the
    // output as if it were a bit vector anyway.
    job->flags =
      QPL_FLAG_FIRST | QPL_FLAG_LAST | QPL_FLAG_OMIT_CHECKSUMS | QPL_FLAG_OMIT_AGGREGATES;

    entry.block_start = start + block;
    ++metrics_.selects;
    metrics_.scanned_elements += block;
    tsl_iaa_frequency_detail::submit_retrying(job);
    entry.phase = phase;
  }

  auto source_bytes(slot const & entry, std::size_t skip) -> std::uint8_t * {
    auto const * source = buffer_of(entry.work.buffer) + entry.work.offset + skip;
    return reinterpret_cast<std::uint8_t *>(const_cast<raw_type *>(source));
  }

  // Waits every in-flight descriptor out and forgets the walk. The only case
  // that has to wait: a completion record must not outlive its job.
  void drain() noexcept {
    for (auto & entry : slots_) {
      if (entry.phase == stage::idle) {
        continue;
      }
      while (qpl_check_job(entry.job.get()) == QPL_STS_BEING_PROCESSED) {
      }
      entry.phase = stage::idle;
    }
    busy_ = 0;
    stack_.clear();
    running_ = false;
  }
#endif  // TSL_COSORT_ENABLE_IAA
};


// One-shot form: builds a counter, answers, throws it away. Prefer the class
// when counting repeatedly, so the QPL jobs and the scratch buffers are reused,
// or when the caller wants poll() rather than a spin.
template <class DataType>
auto distinct_frequencies(
  DataType const * data,
  std::size_t size,
  TslIaaFrequencyOptions const & options = {}
) -> std::unordered_map<std::remove_cv_t<DataType>, std::size_t> {
  TslIaaDistinctFrequencies<DataType> counter(options);
  return counter.count(data, size);
}

#ifdef TSL_IAA_FREQUENCY_HAVE_SPAN
template <class DataType>
auto distinct_frequencies(
  std::span<DataType> data,
  TslIaaFrequencyOptions const & options = {}
) -> std::unordered_map<std::remove_cv_t<DataType>, std::size_t> {
  return distinct_frequencies(data.data(), data.size(), options);
}
#endif
