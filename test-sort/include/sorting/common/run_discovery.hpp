#pragma once

// How a sorter asks for run discovery over one range.
//
// A detector that can offload declines any range below its own threshold and
// scans it inline instead -- the right answer, since a short range cannot repay a
// descriptor. What that costs is the *reaching* of the decision: the synchronous
// fleet takes a pool lease per call so the borrowed detector is not shared, and
// the asynchronous one takes its metrics lock. Both are per-call synchronisation,
// and a multi-column sort asks about a range per equal run per column -- millions
// of them, from every worker at once.
//
// Measured on 2.6M rows over three columns at 1024 distinct values, six workers,
// against the scalar scan: the index quicksort made 748k sub-threshold calls per
// run and paid 5.0x through the synchronous fleet and 3.4x through the
// asynchronous detector, for scans it performed itself anyway. With the range
// declined here instead, the same cell is 1.04x either way. So the caller declines
// them: a detector then only ever sees a range it could actually offload, its
// fallback_small counter is zero by construction, and "the offload did not pay"
// stops meaning "the offload was never tried".
//
// Detectors without a threshold -- the scalar scan, a test double -- are called
// unchanged: the trait below is what a detector opts in with, exactly as
// `tsl_detector_wants_executor` and `tsl_detector_wants_prepare` work.

#include "cluster_detection/scalar/equal_runs.hpp"
#include "sorting/common/multicolumn_sort_types.hpp"

#include <cstddef>
#include <type_traits>
#include <utility>


// True when a detector advertises the range length below which it declines to
// offload, so a caller can decline first and save the call.
template <class Detector, class = void>
struct tsl_detector_has_offload_threshold : std::false_type {};

template <class Detector>
struct tsl_detector_has_offload_threshold<
  Detector,
  decltype(
    static_cast<std::size_t>(
      std::declval<Detector const &>().min_offload_elements()),
    void()
  )
> : std::true_type {};


// Discovery for one range: the detector when it could offload, the scalar scan
// when it would only decline.
template <class Detector, class DataType, class Emit>
void tsl_detect_runs(
  Detector & detector,
  DataType const * values,
  std::size_t begin,
  std::size_t end,
  Emit && emit
) {
  if constexpr (tsl_detector_has_offload_threshold<Detector>::value) {
    if (end - begin < detector.min_offload_elements()) {
      tsl_for_each_equal_run(values, begin, end, emit);
      return;
    }
  }
  detector(values, begin, end, std::forward<Emit>(emit));
}
