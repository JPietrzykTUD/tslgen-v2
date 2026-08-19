#pragma once

// Equal-run detector backends, selected by the `rle=` axis.
//
// The sorter takes any detector through the templated
// `sort_columns_parallel(..., DetectRuns &, ...)` overload, so a backend is just a
// callable plus a factory. This header is the one place that knows which backends
// a build has, so adding an accelerator touches nothing else.
//
// ---------------------------------------------------------------------------
// The contract a detector must satisfy
// ---------------------------------------------------------------------------
//
//   template <class Emit>
//   void operator()(DataType const * values, std::size_t begin, std::size_t end,
//                   Emit && emit);
//
// It emits every maximal equal run of length > 1 in [begin, end) as absolute
// half-open spans, in increasing index order -- the `tsl_for_each_equal_run`
// contract. Input is already sorted in the column being scanned.
//
// An asynchronous detector additionally exposes
//
//   void bind(TslPendingWork & executor);   // register in-flight work
//   void poll();                            // check completions
//
// which the sorter detects through `tsl_detector_wants_executor` and wires to the
// task executor. Asynchronous detection is therefore parallel-only: it needs the
// executor both for pending-work accounting and to be polled.
//
// Optionally a detector exposes `aggregate_metrics()`, whose fields are published
// as `rle_*` counters.
//
// ---------------------------------------------------------------------------
// Per-machine builds
// ---------------------------------------------------------------------------
//
// The two accelerators are independent build options, because a host has one or
// the other:
//
//   -DTSL_COSORT_ENABLE_DSA=ON   Intel DSA via DML: dml_sw, dsa_hw and their
//                                asynchronous forms. `dml_sw` needs no device.
//   -DTSL_COSORT_ENABLE_IAA=ON   Intel IAA via QPL: expects iaa_run_detector.hpp
//                                to provide TslIaaRunDetector<T> and, for the
//                                asynchronous form, TslIaaAsyncRunDetector<T>,
//                                both satisfying the contract above.
//
// `rle=` is always present in a benchmark name, so a result says which detector
// produced it and rows from two differently-equipped machines never collide.
// Absolute times are not comparable across machines; what is comparable is each
// machine's ratio of a backend to its own `rle=scalar` row.

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include "equal_runs.hpp"
#include "multicolumn_sort_types.hpp"

#if defined(TSL_COSORT_HAVE_DSA)
#include "dsa_async_run_detector.hpp"
#include "dsa_run_detector.hpp"
#endif

#if defined(TSL_COSORT_HAVE_IAA)
// Provided by the IAA host: see the contract above.
#include "iaa_run_detector.hpp"
#endif

enum class TslDetectorBackend {
  Scalar,
  DmlSoftware,
  DsaHardware,
  DmlSoftwareAsync,
  DsaHardwareAsync,
  IaaHardware,
  IaaHardwareAsync,
};

inline auto tsl_detector_name(TslDetectorBackend backend) -> char const * {
  switch (backend) {
    case TslDetectorBackend::Scalar: return "scalar";
    case TslDetectorBackend::DmlSoftware: return "dml_sw";
    case TslDetectorBackend::DsaHardware: return "dsa_hw";
    case TslDetectorBackend::DmlSoftwareAsync: return "dml_sw_async";
    case TslDetectorBackend::DsaHardwareAsync: return "dsa_hw_async";
    case TslDetectorBackend::IaaHardware: return "iaa_hw";
    case TslDetectorBackend::IaaHardwareAsync: return "iaa_hw_async";
  }
  return "unknown";
}

inline auto tsl_detector_from_name(std::string const & name) -> TslDetectorBackend {
  for (auto backend : {
    TslDetectorBackend::Scalar, TslDetectorBackend::DmlSoftware,
    TslDetectorBackend::DsaHardware, TslDetectorBackend::DmlSoftwareAsync,
    TslDetectorBackend::DsaHardwareAsync, TslDetectorBackend::IaaHardware,
    TslDetectorBackend::IaaHardwareAsync,
  }) {
    if (name == tsl_detector_name(backend)) return backend;
  }
  throw std::invalid_argument("unknown detector backend: " + name);
}

// Asynchronous backends need the task executor, so they exist only on the
// parallel execution path.
inline auto tsl_detector_is_async(TslDetectorBackend backend) -> bool {
  return backend == TslDetectorBackend::DmlSoftwareAsync
      || backend == TslDetectorBackend::DsaHardwareAsync
      || backend == TslDetectorBackend::IaaHardwareAsync;
}

// Was this backend compiled into the binary? Reported at startup and used to drop
// unavailable cases with a reason rather than omitting them silently.
inline auto tsl_detector_compiled(TslDetectorBackend backend) -> bool {
  switch (backend) {
    case TslDetectorBackend::Scalar:
      return true;
    case TslDetectorBackend::DmlSoftware:
    case TslDetectorBackend::DsaHardware:
    case TslDetectorBackend::DmlSoftwareAsync:
    case TslDetectorBackend::DsaHardwareAsync:
#if defined(TSL_COSORT_HAVE_DSA)
      return true;
#else
      return false;
#endif
    case TslDetectorBackend::IaaHardware:
    case TslDetectorBackend::IaaHardwareAsync:
#if defined(TSL_COSORT_HAVE_IAA)
      return true;
#else
      return false;
#endif
  }
  return false;
}

inline auto tsl_compiled_detectors() -> std::vector<TslDetectorBackend> {
  std::vector<TslDetectorBackend> backends;
  for (auto backend : {
    TslDetectorBackend::Scalar, TslDetectorBackend::DmlSoftware,
    TslDetectorBackend::DsaHardware, TslDetectorBackend::DmlSoftwareAsync,
    TslDetectorBackend::DsaHardwareAsync, TslDetectorBackend::IaaHardware,
    TslDetectorBackend::IaaHardwareAsync,
  }) {
    if (tsl_detector_compiled(backend)) backends.push_back(backend);
  }
  return backends;
}

// Tuning knobs shared by the accelerator backends. Defaults match the dedicated
// DSA harness so its numbers stay comparable.
struct TslDetectorConfig {
  std::size_t workers = 1;
  std::size_t region_bytes = 512 * 1024;
  std::size_t min_offload = 4096;
  std::size_t slots = 16;   // asynchronous: concurrent ranges in flight
  std::size_t depth = 4;    // asynchronous: descriptors per range
};

// The portable detector: `tsl_for_each_equal_run` behind the same call shape as
// the accelerator fleets, so one code path serves every backend.
template <class DataType>
struct TslScalarDetector {
  template <class Emit>
  void operator()(DataType const * values, std::size_t begin, std::size_t end, Emit && emit) {
    tsl_for_each_equal_run(values, begin, end, std::forward<Emit>(emit));
  }
};

// Constructs the detector for `backend` and hands it to `body`. `body` is called
// with a mutable reference to a concrete detector type, so it must be a generic
// lambda. Throws if the backend was not compiled in -- registration is expected to
// have dropped those cases already.
template <class DataType, class Body>
void tsl_with_detector(TslDetectorBackend backend, TslDetectorConfig const & config, Body && body) {
  switch (backend) {
    case TslDetectorBackend::Scalar: {
      TslScalarDetector<DataType> detector;
      body(detector);
      return;
    }
#if defined(TSL_COSORT_HAVE_DSA)
    case TslDetectorBackend::DmlSoftware:
    case TslDetectorBackend::DsaHardware: {
      auto const hardware = backend == TslDetectorBackend::DsaHardware;
      TslDsaDetectorFleet<DataType> detector(
        hardware ? TslRleBackend::DSA_HARDWARE : TslRleBackend::DML_SOFTWARE,
        config.workers, config.region_bytes, config.min_offload
      );
      body(detector);
      return;
    }
    case TslDetectorBackend::DmlSoftwareAsync:
    case TslDetectorBackend::DsaHardwareAsync: {
      auto const hardware = backend == TslDetectorBackend::DsaHardwareAsync;
      TslDsaAsyncRunDetector<DataType> detector(
        hardware ? TslRleBackend::DSA_HARDWARE : TslRleBackend::DML_SOFTWARE,
        config.slots, config.depth, config.region_bytes, config.min_offload
      );
      body(detector);
      return;
    }
#endif
#if defined(TSL_COSORT_HAVE_IAA)
    case TslDetectorBackend::IaaHardware: {
      TslIaaRunDetector<DataType> detector(
        config.workers, config.region_bytes, config.min_offload
      );
      body(detector);
      return;
    }
    case TslDetectorBackend::IaaHardwareAsync: {
      TslIaaAsyncRunDetector<DataType> detector(
        config.slots, config.depth, config.region_bytes, config.min_offload
      );
      body(detector);
      return;
    }
#endif
    default:
      throw std::runtime_error(
        std::string("detector backend ") + tsl_detector_name(backend)
        + " is not compiled into this binary"
      );
  }
}

// True when a detector reports offload statistics. `if constexpr` cannot guard an
// optional member on its own -- the condition must already be well formed -- so the
// member is detected with a trait.
template <class Detector, class = void>
struct tsl_detector_has_metrics : std::false_type {};

template <class Detector>
struct tsl_detector_has_metrics<
  Detector,
  decltype(void(std::declval<Detector const &>().aggregate_metrics()))
> : std::true_type {};

// Publishes whatever `rle_*` counters a detector exposes. A detector without them
// contributes none, which keeps the scalar rows free of empty columns.
template <class Detector, class Sink>
void tsl_publish_detector_metrics(Detector const & detector, Sink && sink) {
  if constexpr (tsl_detector_has_metrics<Detector>::value) {
    auto const metrics = detector.aggregate_metrics();
    sink("rle_ranges", static_cast<double>(metrics.ranges));
    sink("rle_elements", static_cast<double>(metrics.elements));
    sink("rle_offloaded_elements", static_cast<double>(metrics.offloaded_elements));
    sink("rle_descriptors", static_cast<double>(metrics.descriptors));
    sink("rle_offloaded_frac", metrics.elements == 0
      ? 0.0
      : static_cast<double>(metrics.offloaded_elements) / static_cast<double>(metrics.elements));
  } else {
    (void)detector;
    (void)sink;
  }
}
