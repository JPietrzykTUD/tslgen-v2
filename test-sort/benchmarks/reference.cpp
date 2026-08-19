// Builds the reference sorted images the benchmark compares its output against.
//
//   ./reference [--data-dir DIR] [--out DIR] [--directions asc,desc,alternating]
//               [--only SUBSTRING] [--jobs N] [--verify]
//
// For every dataset in the data directory's manifest and every requested
// direction pattern, this writes the lexicographically sorted column image to
// <data>/reference/<dataset>__<direction>.bin, in the same container format as
// the datasets themselves.
//
// Why images and not hashes: with every column a sort key, two rows that tie are
// byte-identical, so the sorted image is unique no matter how an unstable sort
// breaks ties. A byte comparison against this file is therefore an exact oracle
// with no collision probability, and it names the first differing row when it
// fails. Verification stays outside the timed region and costs one sequential
// pass.
//
// The reference must be obviously correct rather than fast: it sorts an index
// vector with std::stable_sort under a plain per-column comparator and gathers.
// Nothing here shares code with the implementation under test.
//
// Direction patterns follow benchmark_multicolumn_gbench: `asc` is all
// ascending, `desc` all descending, and `alternating` has column 0 ascending,
// column 1 descending, and so on.

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <exception>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "dataset_file.hpp"
#include "dataset_manifest.hpp"
#include "dataset_reference.hpp"

#ifndef TSL_DATASET_DEFAULT_DIR
#define TSL_DATASET_DEFAULT_DIR "data"
#endif

namespace {

struct Options {
  std::string data_dir = TSL_DATASET_DEFAULT_DIR;
  std::string out_dir;
  std::vector<TslDirection> directions{
    TslDirection::Ascending, TslDirection::Descending, TslDirection::Alternating
  };
  std::string only;
  std::size_t jobs = 0;
  bool verify = false;
};

auto parse_options(int argc, char ** argv) -> Options {
  Options options;
  for (int index = 1; index < argc; ++index) {
    std::string const argument = argv[index];
    auto const value = [&]() -> std::string {
      if (index + 1 >= argc) {
        throw std::runtime_error("missing value for " + argument);
      }
      return argv[++index];
    };
    if (argument == "--data-dir") {
      options.data_dir = value();
    } else if (argument == "--out") {
      options.out_dir = value();
    } else if (argument == "--only") {
      options.only = value();
    } else if (argument == "--jobs") {
      options.jobs = std::stoull(value());
    } else if (argument == "--verify") {
      options.verify = true;
    } else if (argument == "--directions") {
      options.directions.clear();
      auto const text = value();
      std::size_t start = 0;
      while (start <= text.size()) {
        auto const comma = text.find(',', start);
        auto const token = text.substr(start, comma - start);
        if (!token.empty()) {
          options.directions.push_back(tsl_direction_from_name(token));
        }
        if (comma == std::string::npos) {
          break;
        }
        start = comma + 1;
      }
    } else if (argument == "--help" || argument == "-h") {
      std::cout << "usage: reference [--data-dir DIR] [--out DIR] "
                   "[--directions asc,desc,alternating] [--only SUBSTRING] "
                   "[--jobs N] [--verify]\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + argument);
    }
  }
  if (options.out_dir.empty()) {
    options.out_dir = options.data_dir + "/reference";
  }
  if (options.directions.empty()) {
    throw std::runtime_error("no direction pattern selected");
  }
  if (options.jobs == 0) {
    options.jobs = std::max(1u, std::thread::hardware_concurrency());
  }
  return options;
}

struct Job {
  TslManifestEntry entry;
  TslDirection direction;
  std::string file;
  std::uint64_t reference_checksum = 0;
  std::string note;
  bool ok = false;
};

template <class DataType>
void run_job(Job & job, Options const & options) {
  auto const source_path = options.data_dir + "/" + job.entry.file;
  auto const header = tsl_dataset_read_header(source_path);
  auto const source = tsl_dataset_read<DataType>(source_path, header);
  if (tsl_dataset_checksum(source) != job.entry.checksum) {
    throw std::runtime_error("source dataset does not match its manifest checksum: " + job.entry.file);
  }

  auto const ascending = tsl_direction_ascending(job.direction, source.size());
  auto const image = tsl_sorted_image(source, ascending);
  tsl_require_ordered(image, ascending);
  job.reference_checksum = tsl_dataset_checksum(image);

  auto const path = options.out_dir + "/" + job.file;
  if (options.verify) {
    auto const stored_header = tsl_dataset_read_header(path);
    if (stored_header.rows != header.rows || stored_header.columns != header.columns ||
        stored_header.element_bytes != header.element_bytes) {
      throw std::runtime_error("stored reference has a different shape: " + job.file);
    }
    auto const stored = tsl_dataset_read<DataType>(path, stored_header);
    auto const [column, row] = tsl_first_difference(stored, image);
    if (column != stored.size()) {
      throw std::runtime_error("stored reference differs at column " + std::to_string(column) +
                               ", row " + std::to_string(row));
    }
    job.note = "matches recomputation";
  } else {
    tsl_dataset_write(path, image, header.seed);
    job.note = "written";
  }
  job.ok = true;
}

}  // namespace

int main(int argc, char ** argv) try {
  auto const options = parse_options(argc, argv);
  auto const entries = tsl_read_manifest_tsv(options.data_dir + "/manifest.tsv");

  std::vector<Job> jobs;
  for (auto const & entry : entries) {
    if (!options.only.empty() && entry.id.find(options.only) == std::string::npos) {
      continue;
    }
    for (auto direction : options.directions) {
      Job job;
      job.entry = entry;
      job.direction = direction;
      job.file = entry.id + "__" + tsl_direction_name(direction) + ".bin";
      jobs.push_back(std::move(job));
    }
  }
  if (jobs.empty()) {
    throw std::runtime_error("no dataset matched --only " + options.only);
  }

  if (!options.verify) {
    std::filesystem::create_directories(options.out_dir);
  }
  std::cout << (options.verify ? "verifying " : "building ") << jobs.size()
            << " reference images in " << options.out_dir << " using " << options.jobs
            << " threads\n";

  std::atomic<std::size_t> next{0};
  std::vector<std::exception_ptr> failures(jobs.size());
  auto const worker = [&] {
    for (;;) {
      auto const index = next.fetch_add(1);
      if (index >= jobs.size()) {
        return;
      }
      try {
        if (jobs[index].entry.element_bytes == 4) {
          run_job<std::uint32_t>(jobs[index], options);
        } else {
          run_job<std::uint64_t>(jobs[index], options);
        }
      } catch (...) {
        failures[index] = std::current_exception();
      }
    }
  };

  auto const started = std::chrono::steady_clock::now();
  std::vector<std::thread> threads;
  threads.reserve(options.jobs);
  for (std::size_t index = 0; index < options.jobs; ++index) {
    threads.emplace_back(worker);
  }
  for (auto & thread : threads) {
    thread.join();
  }
  auto const elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now() - started
  ).count();

  // Report and manifest are assembled in job order, so output does not depend on
  // how the work was scheduled.
  std::size_t failed = 0;
  for (std::size_t index = 0; index < jobs.size(); ++index) {
    if (failures[index] == nullptr) {
      continue;
    }
    ++failed;
    try {
      std::rethrow_exception(failures[index]);
    } catch (std::exception const & error) {
      std::cout << "  FAIL " << jobs[index].file << ": " << error.what() << '\n';
    }
  }

  if (!options.verify && failed == 0) {
    std::ofstream manifest(options.out_dir + "/manifest.tsv", std::ios::trunc);
    if (!manifest) {
      throw std::runtime_error("cannot write the reference manifest");
    }
    manifest << "dataset_id\tdirection\tfile\trows\tcolumns\telement_bytes"
                "\tsource_checksum\treference_checksum\n";
    for (auto const & job : jobs) {
      manifest << job.entry.id << '\t' << tsl_direction_name(job.direction) << '\t' << job.file
               << '\t' << job.entry.rows << '\t' << job.entry.columns << '\t'
               << job.entry.element_bytes << '\t' << job.entry.checksum << '\t'
               << job.reference_checksum << '\n';
    }
  }

  std::uint64_t bytes = 0;
  for (auto const & job : jobs) {
    bytes += static_cast<std::uint64_t>(job.entry.rows) * job.entry.columns * job.entry.element_bytes;
  }
  std::cout << (failed == 0 ? "OK" : "FAILED") << ": " << jobs.size() - failed << "/" << jobs.size()
            << (options.verify ? " reference images match recomputation" : " reference images written")
            << ", " << std::fixed << std::setprecision(1)
            << static_cast<double>(bytes) / (1024.0 * 1024.0) << " MiB, in " << elapsed << " ms\n";
  return failed == 0 ? 0 : 1;
} catch (std::exception const & error) {
  std::cerr << "reference failed: " << error.what() << '\n';
  return 1;
}
