// Q1: how do we compare against sorts other people wrote?
//
// The objection a single comparator baseline invites is that it is a straw man,
// and it is a fair one: `std::sort` over row indices is several times slower than
// either of ours on every shape measured, and beating it proves little. Worse, a
// comparison of our *parallel* numbers against a *serial* `std::sort` is not a
// comparison at all. So the baselines here come in matched pairs, and every
// parallel row has a parallel baseline to stand against.
//
// **Same artifact, so the comparison is honest.** Every entrant produces the same
// thing our sorters produce: a permutation of the row indices that orders the rows
// lexicographically by every sort column. Same datasets, same oracle, same
// verify-then-time harness, same nine repetitions. Nothing here is timed unless it
// first produced a permutation whose image matches the reference.
//
//   serial       std::sort, std::stable_sort, ips4o::sort, ours
//   parallel     std::sort(par), ips4o::parallel::sort, ours
//
// **The single-column kernel.** At one sort column the co-sort degenerates to
// exactly one thing: order a column and carry an index. That is the operation
// Intel's x86-simd-sort implements as `avx512_argsort`, so at one column it joins
// the table and the comparison is between partitioning kernels rather than between
// loop structures. It cannot do more than one column, and rows for wider keys are
// emitted as drops with that reason rather than omitted -- a missing row reads as
// "did not compete", and the truth is "cannot express the problem".
//
// Two fairness notes that belong next to the numbers:
//
//   * `avx512_argsort` writes `arrsize_t` (8-byte) indices where ours are 4-byte,
//     so its permutation costs twice the memory traffic on a u32 key. That is its
//     interface, not a handicap we imposed, but it is why a one-column row should
//     not be read as a pure instruction-level comparison.
//   * IPS4o and `std::sort` see the columns only through a comparator, so they
//     cannot exploit equal runs the way our detector seam does. That is precisely
//     the structural advantage the paper claims, and the multi-column rows are
//     where it shows up. Reporting the one-column rows alongside them is what
//     stops that advantage from being mistaken for a faster inner loop.
//
//   ./bench_q1_baselines --shapes skewed_zipf_s1 --cols 1,4,8 --workers 1,24
//
// See docs/benchmark-plan.md.

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <execution>
#include <numeric>
#include <string>
#include <vector>

#if defined(TSL_COSORT_HAVE_IPS4O)
#include "tsl_simd_for.hpp"
#include "ips4o.hpp"
#endif
#if defined(TSL_COSORT_HAVE_XSS)
#include "x86simdsort-static-incl.h"
#endif
#if defined(TSL_COSORT_HAVE_ARROW)
#include <arrow/api.h>
#include <arrow/compute/api_vector.h>
#include <arrow/compute/initialize.h>
#endif

#include "datagen/dataset_catalog.hpp"
#include "datagen/dataset_source.hpp"
#include "paper_harness.hpp"
#include "tuned_config.hpp"
#include "tuned_dispatch.hpp"

namespace {

auto split(std::string const & text, char separator) -> std::vector<std::string> {
  std::vector<std::string> parts;
  std::size_t start = 0;
  while (start <= text.size()) {
    auto const cut = text.find(separator, start);
    auto const end = cut == std::string::npos ? text.size() : cut;
    if (end > start) {
      parts.push_back(text.substr(start, end - start));
    }
    if (cut == std::string::npos) {
      break;
    }
    start = cut + 1;
  }
  return parts;
}

TslTunedConfig g_samplesort_config;
TslTunedConfig g_quicksort_config;
std::map<std::string, TslTunedConfig> g_tuned;

template <class Key>
auto image_matches(std::vector<std::vector<Key>> const & columns,
                   std::vector<std::vector<Key>> const & reference,
                   std::vector<Key> const & index) -> bool {
  std::vector<char> seen(index.size(), 0);
  for (auto const row : index) {
    auto const at = static_cast<std::size_t>(row);
    if (at >= seen.size() || seen[at] != 0) {
      return false;
    }
    seen[at] = 1;
  }
  for (std::size_t column = 0; column < columns.size(); ++column) {
    for (std::size_t at = 0; at < index.size(); ++at) {
      if (columns[column][static_cast<std::size_t>(index[at])]
          != reference[column][at]) {
        return false;
      }
    }
  }
  return true;
}

// The lexicographic order every comparator-based entrant sorts by. One function so
// they cannot accidentally disagree about what "sorted" means.
template <class Key>
struct Lexicographic {
  Key const * const * columns;
  std::size_t count;
  auto operator()(Key left, Key right) const -> bool {
    for (std::size_t column = 0; column < count; ++column) {
      auto const a = columns[column][static_cast<std::size_t>(left)];
      auto const b = columns[column][static_cast<std::size_t>(right)];
      if (a != b) {
        return a < b;
      }
    }
    return false;  // equal keys: no order, so the sort may be unstable
  }
};

template <class Key>
void run_shape(TslPaperResults & results, TslDatasetSource<Key> & source,
               TslDatasetSpec const & spec,
               std::vector<std::size_t> const & worker_counts) {
  // The cell this binary was built for: intr/512 unless
  // TSL_COSORT_MEASURE_STYLE/WIDTH say otherwise. Q0 checks that default against
  // the nine cells it measured, so a host where it is the wrong choice says so
  // rather than reporting a quietly suboptimal number.
  using Simd = tsl_measure_simd_t<Key>;
  auto const pristine = source.pristine(spec);
  auto const reference = source.reference(spec, TslDirection::Ascending);

  std::vector<Key const *> raw;
  std::vector<TslSortColumn<Key>> specs;
  for (auto const & column : *pristine) {
    raw.push_back(column.data());
    specs.push_back(TslSortColumn<Key>{const_cast<Key *>(column.data()),
                                       TslSortOrder::ASCENDING});
  }
  Lexicographic<Key> const less{raw.data(), spec.columns};

  auto blank = results.make_row();
  // Labelled the way Q2 labels the same dataset, so a figure can join the two.
  blank.shape = spec.id.substr(0, spec.id.find("_u"));
  blank.shape_params = spec.external_path.empty() ? "generated" : "measured";
  blank.rows = spec.rows;
  blank.columns = spec.columns;
  blank.element_bytes = sizeof(Key);
  blank.detector = "scalar";

  std::vector<Key> index(spec.rows);
  auto const identity = [&] {
    std::iota(index.begin(), index.end(), Key{0});
  };
  auto const correct = [&] { return image_matches(*pristine, *reference, index); };

  // One entrant: name, whether it is parallel, and the body. Everything goes
  // through the same measure call so no entrant gets a different methodology.
  auto measure = [&](char const * algorithm, char const * variant,
                     std::size_t workers, auto && body) {
    auto row = blank;
    row.algorithm = algorithm;
    row.variant = variant;
    row.workers = workers;
    auto const [ok, stats] = tsl_paper_measure(
      [&] { identity(); body(); }, correct, spec.rows);
    if (!ok) {
      results.drop(row, "did not produce a correct permutation");
      return;
    }
    row.verified = true;
    row.ns_per_element = stats;
    results.add(std::move(row));
  };

  for (auto const workers : worker_counts) {
    bool const many = workers > 1;

    // --- ours -----------------------------------------------------------------
    {
      auto row = blank;
      row.algorithm = "samplesort";
      row.variant = g_samplesort_config.describe_samplesort()
                    + (g_samplesort_config.from_file ? " (tuned)" : " (default)");
      row.workers = workers;
      bool ok = false;
      TslPaperStats stats{};
      auto const dispatched = with_samplesort<Key, Simd>(
        g_samplesort_config, [&](auto sorter) {
          auto const measured = tsl_paper_measure(
            [&] {
              TslIndexScalarDetector<Key> detector;
              if (many) {
                sorter.sort_index_parallel(specs.data(), spec.columns, index.data(),
                                           spec.rows, detector, workers);
              } else {
                sorter.sort_index(specs.data(), spec.columns, index.data(),
                                  spec.rows, detector);
              }
            }, correct, spec.rows);
          ok = measured.first;
          stats = measured.second;
        });
      if (!dispatched) {
        results.drop(row, "tuned samplesort configuration is not instantiated here");
      } else if (!ok) {
        results.drop(row, "sorted wrongly");
      } else {
        row.verified = true;
        row.ns_per_element = stats;
        results.add(std::move(row));
      }
    }
    {
      auto row = blank;
      row.algorithm = "quicksort";
      row.variant = g_quicksort_config.describe_quicksort()
                    + (g_quicksort_config.from_file ? " (tuned)" : " (default)");
      row.workers = workers;
      bool ok = false;
      TslPaperStats stats{};
      auto const dispatched = with_quicksort_leaf<Key, Simd>(
        g_quicksort_config, [&](auto sorter) {
          auto const measured = tsl_paper_measure(
            [&] {
              TslIndexScalarDetector<Key> detector;
              if (many) {
                sorter.sort_index_parallel(specs.data(), spec.columns, index.data(),
                                           spec.rows, g_quicksort_config.discovery,
                                           detector, workers,
                                           g_quicksort_config.partition_threshold);
              } else {
                sorter.sort_index(specs.data(), spec.columns, index.data(),
                                  spec.rows, g_quicksort_config.discovery, detector);
              }
            }, correct, spec.rows);
          ok = measured.first;
          stats = measured.second;
        });
      if (!dispatched) {
        results.drop(row, "tuned quicksort configuration is not instantiated here");
      } else if (!ok) {
        results.drop(row, "sorted wrongly");
      } else {
        row.verified = true;
        row.ns_per_element = stats;
        results.add(std::move(row));
      }
    }

    // --- the standard library -------------------------------------------------
    if (!many) {
      measure("std::sort", "lexicographic comparator", workers,
              [&] { std::sort(index.begin(), index.end(), less); });
      measure("std::stable_sort", "lexicographic comparator", workers,
              [&] { std::stable_sort(index.begin(), index.end(), less); });
    } else {
      // The like-for-like parallel baseline. Its thread count is the library's to
      // choose, which is why the row records the workers we asked *ours* for and
      // the variant says so: this is "the standard parallel sort on this machine",
      // not "the standard parallel sort restricted to N threads".
      measure("std::sort", "execution::par, library-chosen threads", workers,
              [&] { std::sort(std::execution::par, index.begin(), index.end(), less); });
    }

    // --- IPS4o ---------------------------------------------------------------
#if defined(TSL_COSORT_HAVE_IPS4O)
    if (!many) {
      measure("ips4o::sort", "lexicographic comparator", workers,
              [&] { ips4o::sort(index.begin(), index.end(), less); });
    } else {
      measure("ips4o::parallel::sort", "lexicographic comparator", workers,
              [&] {
                ips4o::parallel::sort(index.begin(), index.end(), less,
                                      static_cast<int>(workers));
              });
    }
#else
    {
      auto row = blank;
      row.algorithm = "ips4o::sort";
      row.workers = workers;
      results.drop(row, "not built: configure with -DTSL_COSORT_ENABLE_BASELINES=ON");
    }
#endif

    // --- x86-simd-sort, one column only --------------------------------------
    {
      auto row = blank;
      row.algorithm = "avx512_argsort";
      row.variant = "x86-simd-sort, 8-byte indices";
      row.workers = workers;
#if !defined(TSL_COSORT_HAVE_XSS)
      results.drop(row, "not built: configure with -DTSL_COSORT_ENABLE_BASELINES=ON");
#else
      if (spec.columns != 1) {
        results.drop(row, "single column only: an argsort cannot express a "
                          "lexicographic key over several columns");
      } else if (many) {
        // Its argsort does have a parallel path, gated on XSS_COMPILE_OPENMP.
        // This build has no libomp for clang, so the honest reason is that the
        // parallel path is not compiled in -- not that the library lacks one.
        results.drop(row, "parallel argsort needs XSS_COMPILE_OPENMP; this build "
                          "has no OpenMP runtime for clang");
      } else {
        // The static API dispatches on the ISA the translation unit was built
        // for, so on this host it resolves to the AVX-512 argsort.
        // The caller owns the initial permutation: argsort early-exits on an
        // already-sorted input and leaves `arg` untouched, so an unseeded buffer
        // silently yields garbage. Seeding is inside the timed body because every
        // other index-based entrant pays for its iota too.
        std::vector<std::size_t> wide(spec.rows);
        auto const [ok, stats] = tsl_paper_measure(
          [&] {
            std::iota(wide.begin(), wide.end(), std::size_t{0});
            x86simdsortStatic::argsort<Key>(raw[0], wide.data(), spec.rows, false,
                                            false);
          },
          [&] {
            // Its indices are wider than ours, so the permutation is narrowed
            // before the shared oracle checks it. The narrowing is outside the
            // timed body.
            for (std::size_t at = 0; at < spec.rows; ++at) {
              index[at] = static_cast<Key>(wide[at]);
            }
            return correct();
          },
          spec.rows);
        if (!ok) {
          results.drop(row, "did not produce a correct permutation");
        } else {
          row.verified = true;
          row.ns_per_element = stats;
          results.add(std::move(row));
        }
      }
#endif
    }

    // --- Arrow SortIndices ---------------------------------------------------
    // The semantically equal baseline: a multi-column lexicographic indirect
    // sort returning a permutation, which is exactly the operation and exactly
    // the artifact. Nothing here is adapted or restricted, so if it wins, it
    // wins on the same problem.
    {
      auto row = blank;
      row.algorithm = "arrow::SortIndices";
      row.workers = workers;
#if !defined(TSL_COSORT_HAVE_ARROW)
      results.drop(row, "not built: configure with -DTSL_COSORT_ENABLE_BASELINES=ON");
#else
      row.variant = "table, one SortKey per column";
      if (many) {
        // SortIndices runs on the calling thread; Arrow parallelises across
        // ExecPlan nodes, not inside this kernel. Reported rather than omitted so
        // its absence from the parallel table is a stated fact.
        results.drop(row, "single-threaded kernel: Arrow parallelises across plan "
                          "nodes, not within SortIndices");
      } else {
        // The table wraps our buffers without copying, and it is built outside the
        // timed region: a system would build it once and sort many times, and
        // charging Arrow for construction would be the straw man this file exists
        // to avoid.
        std::vector<std::shared_ptr<arrow::Field>> fields;
        std::vector<std::shared_ptr<arrow::ChunkedArray>> arrays;
        auto const type = sizeof(Key) == 4 ? arrow::uint32() : arrow::uint64();
        bool built = true;
        for (std::size_t column = 0; column < spec.columns; ++column) {
          auto const name = "c" + std::to_string(column);
          fields.push_back(arrow::field(name, type));
          auto buffer = arrow::Buffer::Wrap(raw[column], spec.rows);
          auto data = arrow::ArrayData::Make(
            type, static_cast<std::int64_t>(spec.rows), {nullptr, buffer});
          auto array = arrow::MakeArray(data);
          if (array == nullptr) {
            built = false;
            break;
          }
          arrays.push_back(std::make_shared<arrow::ChunkedArray>(array));
        }
        if (!built) {
          results.drop(row, "could not wrap the columns as an Arrow table");
        } else {
          auto const table = arrow::Table::Make(arrow::schema(fields), arrays,
                                                static_cast<std::int64_t>(spec.rows));
          std::vector<arrow::compute::SortKey> keys;
          for (std::size_t column = 0; column < spec.columns; ++column) {
            keys.emplace_back("c" + std::to_string(column),
                              arrow::compute::SortOrder::Ascending);
          }
          arrow::compute::SortOptions const options(keys);
          std::shared_ptr<arrow::Array> permutation;
          auto const [ok, stats] = tsl_paper_measure(
            [&] {
              auto result = arrow::compute::SortIndices(arrow::Datum(table), options);
              permutation = result.ok() ? *result : nullptr;
            },
            [&] {
              if (permutation == nullptr) {
                return false;
              }
              auto const & wide =
                static_cast<arrow::UInt64Array const &>(*permutation);
              if (static_cast<std::size_t>(wide.length()) != spec.rows) {
                return false;
              }
              // Narrowed outside the timed body, as for argsort.
              for (std::size_t at = 0; at < spec.rows; ++at) {
                index[at] = static_cast<Key>(wide.Value(
                  static_cast<std::int64_t>(at)));
              }
              return correct();
            },
            spec.rows);
          if (!ok) {
            results.drop(row, "did not produce a correct permutation");
          } else {
            row.verified = true;
            row.ns_per_element = stats;
            results.add(std::move(row));
          }
        }
      }
#endif
    }
  }
}

// Every shape at one key width. Templated so 4-byte and 8-byte keys go through
// exactly the same entrants and the same oracle; a baseline that only ever sees
// 32-bit keys would leave the wider key -- where a lane holds half as many
// elements and the permutation costs twice the traffic -- unmeasured.
template <class Key>
void run_all(TslPaperResults & results, std::vector<std::string> const & shapes,
             std::vector<std::size_t> const & column_counts,
             std::vector<std::size_t> const & worker_counts, std::size_t rows,
             std::string const & tpcds_dir) {
  TslDatasetSource<Key> source(12ull << 30);
  for (auto const columns : column_counts) {
    auto const catalog = tsl_default_catalog(rows, columns, sizeof(Key));
    auto const tail = "_u" + std::to_string(sizeof(Key) * 8) + "_n";
    for (auto const & shape : shapes) {
      TslDatasetSpec const * spec = nullptr;
      for (auto const & candidate : catalog) {
        if (candidate.id.rfind(shape + tail, 0) == 0) {
          spec = &candidate;
          break;
        }
      }
      if (spec == nullptr) {
        auto row = results.make_row();
        row.shape = shape;
        row.rows = rows;
        row.columns = columns;
        row.element_bytes = sizeof(Key);
        row.algorithm = "-";
        results.drop(row, "no such dataset at this size and column count");
        continue;
      }
      std::printf("\n-- %s, %zu rows, %zu columns, u%zu --\n", spec->id.c_str(),
                  spec->rows, spec->columns, sizeof(Key) * 8);
      run_shape<Key>(results, source, *spec, worker_counts);
    }
  }

  // Measured keys, at their own width. The baselines matter most here: a real
  // key's skew is what a comparator-based sort cannot exploit.
  for (auto const & spec : tsl_external_catalog(tpcds_dir, sizeof(Key))) {
    std::printf("\n-- %s, %zu rows, %zu columns, u%zu (measured) --\n",
                spec.id.c_str(), spec.rows, spec.columns, sizeof(Key) * 8);
    run_shape<Key>(results, source, spec, worker_counts);
  }
}

}  // namespace

int main(int argc, char ** argv) {
  std::vector<std::string> shapes{"skewed_zipf_s1", "low_cardinality_d4",
                                  "independent_uniform_c1024", "unique_first"};
  std::vector<std::size_t> column_counts{1, 4, 8};
  std::vector<std::size_t> worker_counts{1, 24};
  std::size_t rows = 1u << 22;
  std::string csv_path;
  std::string tuned_path = "best_config.tsv";
  std::string tpcds_dir;
  std::vector<std::size_t> element_byte_list{4, 8};

  for (int i = 1; i < argc; ++i) {
    auto const flag = std::string(argv[i]);
    auto const value = [&]() -> std::string { return i + 1 < argc ? argv[++i] : ""; };
    auto const list = [&](std::vector<std::size_t> & into) {
      into.clear();
      for (auto const & part : split(value(), ',')) {
        into.push_back(std::strtoull(part.c_str(), nullptr, 10));
      }
    };
    if (flag == "--shapes") {
      shapes = split(value(), ',');
    } else if (flag == "--cols") {
      list(column_counts);
    } else if (flag == "--workers") {
      list(worker_counts);
    } else if (flag == "--rows") {
      rows = std::strtoull(value().c_str(), nullptr, 10);
    } else if (flag == "--element-bytes") {
      list(element_byte_list);
    } else if (flag == "--tuned") {
      tuned_path = value();
    } else if (flag == "--tpcds-dir") {
      tpcds_dir = value();
    } else if (flag == "--csv") {
      csv_path = value();
    } else {
      std::printf("unknown argument: %s\n", flag.c_str());
      return 2;
    }
  }

  TslPaperResults results("Q1 baselines", "bench_q1_baselines");
  {
    auto const tuned = tsl_read_tuned(tuned_path);
    if (tuned.empty()) {
      std::printf("no %s: ours run at their defaults, rows labelled (default)\n",
                  tuned_path.c_str());
    }
    // Q0 tunes u32 only, so a u64 run reuses the u32 configuration. That is a
    // proxy, not a tuned value, and the row's variant already says "(tuned)" --
    // so it is stated here and in docs/benchmark-plan.md rather than implied.
    g_tuned = tuned;
  }
#if defined(TSL_COSORT_HAVE_IPS4O)
  std::printf("ips4o: built in\n");
#else
  std::printf("ips4o: NOT built in; its rows will be drops\n");
#endif
#if defined(TSL_COSORT_HAVE_XSS)
  std::printf("x86-simd-sort: built in (one-column rows only)\n");
#else
  std::printf("x86-simd-sort: NOT built in; its rows will be drops\n");
#endif
#if defined(TSL_COSORT_HAVE_ARROW)
  // Arrow 23 keeps the compute kernels in libarrow_compute and registers them on
  // demand: without this the registry has no "sort_indices" at all, and the
  // failure surfaces as a wrong permutation rather than a missing function.
  {
    auto const status = arrow::compute::Initialize();
    std::printf("arrow: built in, compute init %s (serial rows only)\n",
                status.ok() ? "OK" : status.ToString().c_str());
  }
#else
  std::printf("arrow: NOT built in; its rows will be drops\n");
#endif

  for (auto const element_bytes : element_byte_list) {
    if (element_bytes == 4) {
      tsl_select_tuned<std::uint32_t>(g_tuned, g_samplesort_config,
                                      g_quicksort_config);
      run_all<std::uint32_t>(results, shapes, column_counts, worker_counts, rows,
                             tpcds_dir);
    } else if (element_bytes == 8) {
      tsl_select_tuned<std::uint64_t>(g_tuned, g_samplesort_config,
                                      g_quicksort_config);
      run_all<std::uint64_t>(results, shapes, column_counts, worker_counts, rows,
                             tpcds_dir);
    } else {
      std::printf("unsupported element width: %zu\n", element_bytes);
    }
  }

  std::printf("\n%s\n", results.summary().c_str());
  if (!csv_path.empty()) {
    results.write_csv(csv_path);
  }
  return 0;
}
