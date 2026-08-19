// Generates the synthetic dataset catalog of description_datasets.md.
//
//   ./generate_datasets [--rows N] [--columns M] [--elements 4,8]
//                       [--out DIR] [--only SHAPE] [--list]
//
// One binary file per (shape, parameter set, element width), plus manifest.tsv
// and manifest.json describing every instance and its measured descriptor.
// Verification lives in verify_datasets.cpp, which recomputes the descriptor from
// the written bytes rather than trusting this program.

#include <chrono>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_descriptor.hpp"
#include "dataset_file.hpp"
#include "dataset_manifest.hpp"

#ifndef TSL_DATASET_DEFAULT_DIR
#define TSL_DATASET_DEFAULT_DIR "data"
#endif

namespace {

struct Options {
  std::size_t rows = 262144;
  std::size_t columns = 3;
  std::vector<std::size_t> element_bytes{4, 8};
  std::string out_dir = TSL_DATASET_DEFAULT_DIR;
  std::string only;
  bool list_only = false;
};

auto parse_size_list(std::string const & text) -> std::vector<std::size_t> {
  std::vector<std::size_t> values;
  std::size_t start = 0;
  while (start <= text.size()) {
    auto const comma = text.find(',', start);
    auto const token = text.substr(start, comma - start);
    if (!token.empty()) {
      values.push_back(std::stoull(token));
    }
    if (comma == std::string::npos) {
      break;
    }
    start = comma + 1;
  }
  return values;
}

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
    if (argument == "--rows") {
      options.rows = std::stoull(value());
    } else if (argument == "--columns") {
      options.columns = std::stoull(value());
    } else if (argument == "--elements") {
      options.element_bytes = parse_size_list(value());
    } else if (argument == "--out") {
      options.out_dir = value();
    } else if (argument == "--only") {
      options.only = value();
    } else if (argument == "--list") {
      options.list_only = true;
    } else if (argument == "--help" || argument == "-h") {
      std::cout << "usage: generate_datasets [--rows N] [--columns M] "
                   "[--elements 4,8] [--out DIR] [--only SHAPE] [--list]\n";
      std::exit(0);
    } else {
      throw std::runtime_error("unknown argument: " + argument);
    }
  }
  for (auto width : options.element_bytes) {
    if (width != 4 && width != 8) {
      throw std::runtime_error("element width must be 4 or 8");
    }
  }
  if (options.columns == 0 || options.rows < 2) {
    throw std::runtime_error("need at least two rows and one column");
  }
  return options;
}

template <class DataType>
auto emit(TslDatasetSpec const & spec, std::string const & out_dir,
          TslDatasetDescriptor & descriptor) -> TslManifestEntry {
  auto const columns = tsl_generate_dataset<DataType>(spec);
  descriptor = tsl_describe_dataset(columns);
  auto const seed = tsl_spec_seed(spec);
  auto const file = spec.id + ".bin";
  tsl_dataset_write(out_dir + "/" + file, columns, seed);

  TslManifestEntry entry;
  entry.id = spec.id;
  entry.file = file;
  entry.shape = tsl_shape_name(spec.shape);
  entry.element_bytes = sizeof(DataType);
  entry.rows = spec.rows;
  entry.columns = spec.columns;
  entry.seed = seed;
  entry.checksum = tsl_dataset_checksum(columns);
  entry.params = spec.params;
  entry.measured = tsl_serialize_descriptor(descriptor);
  return entry;
}

}  // namespace

int main(int argc, char ** argv) try {
  auto const options = parse_options(argc, argv);

  std::vector<TslDatasetSpec> specs;
  for (auto width : options.element_bytes) {
    for (auto const & spec : tsl_default_catalog(options.rows, options.columns, width)) {
      if (options.only.empty() || tsl_shape_name(spec.shape) == options.only) {
        specs.push_back(spec);
      }
    }
  }
  if (specs.empty()) {
    throw std::runtime_error("no dataset matched --only " + options.only);
  }

  if (options.list_only) {
    for (auto const & spec : specs) {
      std::cout << spec.id << '\t' << tsl_shape_name(spec.shape) << '\t'
                << tsl_format_params(spec.params) << '\n';
    }
    return 0;
  }

  std::filesystem::create_directories(options.out_dir);
  std::cout << "writing " << specs.size() << " datasets to " << options.out_dir
            << " (rows=" << options.rows << ", columns=" << options.columns << ")\n";

  std::vector<TslManifestEntry> entries;
  std::vector<TslDatasetDescriptor> descriptors;
  entries.reserve(specs.size());
  descriptors.reserve(specs.size());
  auto const started = std::chrono::steady_clock::now();
  std::uint64_t total_bytes = 0;

  for (auto const & spec : specs) {
    TslDatasetDescriptor descriptor;
    auto entry = spec.element_bytes == 4
      ? emit<std::uint32_t>(spec, options.out_dir, descriptor)
      : emit<std::uint64_t>(spec, options.out_dir, descriptor);
    total_bytes += static_cast<std::uint64_t>(spec.rows) * spec.columns * spec.element_bytes;

    std::cout << "  " << std::left << std::setw(52) << entry.id << std::right
              << " D=[";
    for (std::size_t level = 0; level < descriptor.distinct_prefixes.size(); ++level) {
      std::cout << (level == 0 ? "" : ",") << descriptor.distinct_prefixes[level];
    }
    std::cout << "] scan=" << std::fixed << std::setprecision(2)
              << descriptor.scan_volume / static_cast<double>(spec.rows) << "N"
              << " W=" << std::setprecision(3) << descriptor.weighted_work / 1e6 << "M"
              << " dup=" << std::setprecision(2) << descriptor.duplicate_tuple_fraction
              << '\n';

    entries.push_back(std::move(entry));
    descriptors.push_back(std::move(descriptor));
  }

  tsl_write_manifest_tsv(options.out_dir + "/manifest.tsv", entries);
  tsl_write_manifest_json(options.out_dir + "/manifest.json", entries, descriptors);

  auto const elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now() - started
  ).count();
  std::cout << "wrote " << entries.size() << " datasets, "
            << std::fixed << std::setprecision(1)
            << static_cast<double>(total_bytes) / (1024.0 * 1024.0) << " MiB payload, in "
            << elapsed << " ms\n";
  return 0;
} catch (std::exception const & error) {
  std::cerr << "generate_datasets failed: " << error.what() << '\n';
  return 1;
}
