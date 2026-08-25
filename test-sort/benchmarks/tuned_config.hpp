#pragma once

// The tuned configuration, written by `bench_q0_tune` and read by every driver
// that reports a number.
//
// This exists because the alternative is worse: hard-coding "K=16, network leaf,
// fill 50" in each driver puts the tuning result in source rather than in the
// results, so re-tuning on new hardware becomes a code change and the paper's
// figures stop being reproducible from one command. Here `run_paper.sh` runs the
// descent first and every later driver reads what it found.
//
// One row per (algorithm, style, width, element bytes), because the descent is
// re-run per style and width -- whether the best algorithmic configuration
// depends on the register width is itself one of the questions.

#include <cstddef>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "cosort_plan.hpp"
#include "sorting/sample_sort/samplesort_multicolumn.hpp"


// Every knob the descent varies. Defaults are the starting point of the descent
// and the fallback when no tuning file exists, so a driver run on its own still
// produces something sensible and says which it used.
struct TslTunedConfig {
  // samplesort
  int k = 16;
  TslSampleSortBuckets buckets = TslSampleSortBuckets::Adaptive;
  TslSampleSortBase base_policy = TslSampleSortBase::Network;
  std::size_t base_case = 256;
  std::size_t fill_percent = 50;
  TslSampleSortIds ids = TslSampleSortIds::Byte;
  TslSampleSortMovement movement = TslSampleSortMovement::OutOfPlace;
  // quicksort
  TslPartitionKind partition = TslPartitionKind::THREE_WAY;
  TslLeafKind leaf = TslLeafKind::NETWORK;
  bool hybrid_leaf = false;
  TslRunDiscoveryKind discovery = TslRunDiscoveryKind::POST_SORT;
  std::size_t partition_threshold = 16384;
  // provenance
  bool from_file = false;

  auto describe_samplesort() const -> std::string {
    std::string out = "K=" + std::to_string(k);
    out += buckets == TslSampleSortBuckets::Adaptive ? "/adaptive" : "/ordered";
    out += base_policy == TslSampleSortBase::Network ? "/net" : "/ins";
    out += "/base" + std::to_string(base_case);
    out += "/fill" + std::to_string(fill_percent);
    out += ids == TslSampleSortIds::Byte ? "/byteid" : "/wideid";
    out += movement == TslSampleSortMovement::InPlace ? "/inplace" : "/oop";
    return out;
  }

  auto describe_quicksort() const -> std::string {
    std::string out = partition == TslPartitionKind::TWO_WAY ? "2way" : "3way";
    out += hybrid_leaf ? "/hyb" : (leaf == TslLeafKind::NETWORK ? "/net" : "/ins");
    out += discovery == TslRunDiscoveryKind::POST_SORT ? "/post" : "/incremental";
    return out;
  }
};


inline auto tsl_tuned_key(std::string const & algorithm, TslStyle style,
                          std::size_t width, std::size_t element_bytes) -> std::string {
  return algorithm + "|" + tsl_style_name(style) + "|" + std::to_string(width) + "|"
         + std::to_string(element_bytes);
}


// `algorithm|style|width|element_bytes  knob=value knob=value ...`
inline void tsl_write_tuned(std::string const & path,
                            std::map<std::string, TslTunedConfig> const & configs) {
  std::ofstream out(path);
  out << "# written by bench_q0_tune; read by the reporting drivers\n";
  out << "# key: algorithm|style|width|element_bytes\n";
  for (auto const & [key, config] : configs) {
    out << key << '\t'
        << "k=" << config.k
        << " buckets=" << (config.buckets == TslSampleSortBuckets::Adaptive
                             ? "adaptive" : "ordered")
        << " base_policy=" << (config.base_policy == TslSampleSortBase::Network
                                 ? "net" : "ins")
        << " base_case=" << config.base_case
        << " fill=" << config.fill_percent
        << " ids=" << (config.ids == TslSampleSortIds::Byte ? "byte" : "wide")
        << " movement=" << (config.movement == TslSampleSortMovement::InPlace
                              ? "inplace" : "oop")
        << " partition=" << (config.partition == TslPartitionKind::TWO_WAY
                               ? "2way" : "3way")
        << " leaf=" << (config.hybrid_leaf ? "hyb"
                          : (config.leaf == TslLeafKind::NETWORK ? "net" : "ins"))
        << " discovery=" << (config.discovery == TslRunDiscoveryKind::POST_SORT
                               ? "post" : "incremental")
        << " partition_threshold=" << config.partition_threshold
        << '\n';
  }
}


inline auto tsl_read_tuned(std::string const & path)
  -> std::map<std::string, TslTunedConfig> {
  std::map<std::string, TslTunedConfig> configs;
  std::ifstream in(path);
  if (!in) {
    return configs;
  }
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line.front() == '#') {
      continue;
    }
    auto const tab = line.find('\t');
    if (tab == std::string::npos) {
      continue;
    }
    auto const key = line.substr(0, tab);
    TslTunedConfig config;
    config.from_file = true;
    std::istringstream fields(line.substr(tab + 1));
    std::string field;
    while (fields >> field) {
      auto const equals = field.find('=');
      if (equals == std::string::npos) {
        continue;
      }
      auto const name = field.substr(0, equals);
      auto const value = field.substr(equals + 1);
      if (name == "k") config.k = std::stoi(value);
      else if (name == "buckets") config.buckets = value == "ordered"
        ? TslSampleSortBuckets::Ordered : TslSampleSortBuckets::Adaptive;
      else if (name == "base_policy") config.base_policy = value == "ins"
        ? TslSampleSortBase::Insertion : TslSampleSortBase::Network;
      else if (name == "base_case") config.base_case = std::stoul(value);
      else if (name == "fill") config.fill_percent = std::stoul(value);
      else if (name == "ids") config.ids = value == "wide"
        ? TslSampleSortIds::KeyWidth : TslSampleSortIds::Byte;
      else if (name == "movement") config.movement = value == "inplace"
        ? TslSampleSortMovement::InPlace : TslSampleSortMovement::OutOfPlace;
      else if (name == "partition") config.partition = value == "2way"
        ? TslPartitionKind::TWO_WAY : TslPartitionKind::THREE_WAY;
      else if (name == "leaf") {
        config.hybrid_leaf = value == "hyb";
        config.leaf = value == "ins" ? TslLeafKind::INSERTION : TslLeafKind::NETWORK;
      }
      else if (name == "discovery") config.discovery = value == "incremental"
        ? TslRunDiscoveryKind::INCREMENTAL : TslRunDiscoveryKind::POST_SORT;
      else if (name == "partition_threshold")
        config.partition_threshold = std::stoul(value);
    }
    configs.emplace(key, config);
  }
  return configs;
}


// The configuration for one cell, or the defaults when the descent has not run.
inline auto tsl_tuned_for(std::map<std::string, TslTunedConfig> const & configs,
                          std::string const & algorithm, TslStyle style,
                          std::size_t width, std::size_t element_bytes)
  -> TslTunedConfig {
  auto const found = configs.find(tsl_tuned_key(algorithm, style, width, element_bytes));
  return found == configs.end() ? TslTunedConfig{} : found->second;
}
