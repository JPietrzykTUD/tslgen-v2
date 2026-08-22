#pragma once

#include <cstddef>
#include <type_traits>
#include <utility>


enum class TslSortOrder { ASCENDING, DESCENDING };
enum class TslRunDiscoveryKind { POST_SORT, INCREMENTAL };

template <class DataType>
struct TslSortColumn {
  DataType * data;
  TslSortOrder order;
};

struct TslRunSpan {
  std::size_t begin;
  std::size_t end;
};

// One half-open row range to sort by `column` and by every column after it.
// The root range, a discovered next-column equal run, and a quicksort partition
// of the active column offloaded to another worker all share this shape, so no
// task kind discriminator is required.
struct TslColumnSortTask {
  std::size_t column;
  std::size_t begin;
  std::size_t end;
};

struct TslMultiColumnSortMetrics {
  std::size_t rle_values_scanned = 0;
  std::size_t direct_equal_bands = 0;
  std::size_t direct_equal_band_rows = 0;
  std::size_t tasks_submitted = 0;
  std::size_t tasks_executed_inline = 0;
  std::size_t max_outstanding_tasks = 0;
  std::size_t partition_tasks_submitted = 0;
  // Times a worker woke on the pending-work deadline instead of a notification.
  // Non-zero means the starvation safeguard was actually needed.
  std::size_t idle_poll_wakeups = 0;
};


// True when a detector wants to see a range *before* it is sorted, so it can
// start work whose answer does not depend on order -- value frequencies, for
// instance. Detected the same way the executor hook is, so a detector without
// `prepare` is unaffected and a caller needs no per-backend branch.
template <class Detector, class DataType, class = void>
struct tsl_detector_wants_prepare : std::false_type {};

template <class Detector, class DataType>
struct tsl_detector_wants_prepare<
  Detector,
  DataType,
  decltype(
    std::declval<Detector &>().prepare(
      std::declval<DataType const *>(), std::size_t{}, std::size_t{}
    ),
    void()
  )
> : std::true_type {};
