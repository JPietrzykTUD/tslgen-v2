#pragma once

// Manifest for a generated dataset directory.
//
// Two files are written: manifest.tsv, which the verifier parses, and
// manifest.json for plotting and human reading. The TSV carries the measured
// descriptor as one canonical string; the verifier recomputes the descriptor from
// the payload it reads back and compares the strings, so a single comparison
// covers every measured quantity. Doubles are formatted with 17 significant
// digits, which round-trips exactly, so equal data yields equal strings.

#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "dataset_catalog.hpp"
#include "dataset_descriptor.hpp"

inline auto tsl_format_double(double value) -> std::string {
  std::ostringstream out;
  out << std::setprecision(17) << value;
  return out.str();
}

inline auto tsl_format_params(std::map<std::string, double> const & params) -> std::string {
  std::string text;
  for (auto const & entry : params) {
    if (!text.empty()) {
      text += ',';
    }
    text += entry.first + '=' + tsl_format_double(entry.second);
  }
  return text.empty() ? "-" : text;
}

inline auto tsl_parse_params(std::string const & text) -> std::map<std::string, double> {
  std::map<std::string, double> params;
  if (text == "-" || text.empty()) {
    return params;
  }
  std::istringstream stream(text);
  std::string item;
  while (std::getline(stream, item, ',')) {
    auto const split = item.find('=');
    if (split == std::string::npos) {
      throw std::runtime_error("malformed parameter: " + item);
    }
    params[item.substr(0, split)] = std::stod(item.substr(split + 1));
  }
  return params;
}

namespace tsl_manifest_detail {

template <class Values>
auto join(Values const & values) -> std::string {
  std::string text;
  for (auto const & value : values) {
    if (!text.empty()) {
      text += '|';
    }
    text += tsl_format_double(static_cast<double>(value));
  }
  return text.empty() ? "-" : text;
}

}  // namespace tsl_manifest_detail

// Canonical one-line form of everything the descriptor measured.
inline auto tsl_serialize_descriptor(TslDatasetDescriptor const & descriptor) -> std::string {
  std::ostringstream out;
  out << "D=" << tsl_manifest_detail::join(descriptor.distinct_prefixes);
  out << ",R=" << tsl_manifest_detail::join(descriptor.tied_rows);
  out << ",maxg=" << tsl_manifest_detail::join(descriptor.max_group);
  out << ",ntg=" << tsl_manifest_detail::join(descriptor.nontrivial_groups);
  out << ",card=" << tsl_manifest_detail::join(descriptor.column_cardinality);
  out << ",minv=" << tsl_manifest_detail::join(descriptor.column_min);
  out << ",maxv=" << tsl_manifest_detail::join(descriptor.column_max);
  out << ",inorder=" << tsl_manifest_detail::join(descriptor.prefix_in_order_fraction);
  out << ",fill=" << tsl_manifest_detail::join(descriptor.leaf_fill_ratio);
  out << ",fillranges=" << tsl_manifest_detail::join(descriptor.leaf_ranges);
  out << ",W=" << tsl_format_double(descriptor.weighted_work);
  out << ",scan=" << tsl_format_double(descriptor.scan_volume);
  out << ",runs=" << descriptor.ascending_runs;
  out << ",kendall=" << tsl_format_double(descriptor.kendall_normalized);
  out << ",ldisp=" << tsl_format_double(descriptor.mean_displacement);
  out << ",ladj=" << tsl_format_double(descriptor.adjacency_fraction);
  out << ",duptuple=" << tsl_format_double(descriptor.duplicate_tuple_fraction);
  for (std::size_t level = 0; level < descriptor.group_histogram.size(); ++level) {
    out << ",hist" << (level + 1) << "=" << tsl_manifest_detail::join(descriptor.group_histogram[level]);
  }
  return out.str();
}

struct TslManifestEntry {
  std::string id;
  std::string file;
  std::string shape;
  std::size_t element_bytes = 0;
  std::size_t rows = 0;
  std::size_t columns = 0;
  std::uint64_t seed = 0;
  std::uint64_t checksum = 0;
  std::map<std::string, double> params;
  std::string measured;

  auto spec() const -> TslDatasetSpec {
    TslDatasetSpec value;
    value.id = id;
    value.shape = tsl_shape_from_name(shape);
    value.rows = rows;
    value.columns = columns;
    value.element_bytes = element_bytes;
    value.params = params;
    return value;
  }
};

inline constexpr char const * tsl_manifest_header =
  "id\tfile\tshape\telement_bytes\trows\tcolumns\tseed\tchecksum\tparams\tmeasured";

inline void tsl_write_manifest_tsv(std::string const & path,
                                   std::vector<TslManifestEntry> const & entries) {
  std::ofstream out(path, std::ios::trunc);
  if (!out) {
    throw std::runtime_error("cannot write " + path);
  }
  out << tsl_manifest_header << '\n';
  for (auto const & entry : entries) {
    out << entry.id << '\t' << entry.file << '\t' << entry.shape << '\t'
        << entry.element_bytes << '\t' << entry.rows << '\t' << entry.columns << '\t'
        << entry.seed << '\t' << entry.checksum << '\t'
        << tsl_format_params(entry.params) << '\t' << entry.measured << '\n';
  }
}

inline auto tsl_read_manifest_tsv(std::string const & path) -> std::vector<TslManifestEntry> {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("cannot read " + path);
  }
  std::string line;
  if (!std::getline(in, line)) {
    throw std::runtime_error("empty manifest: " + path);
  }
  if (line != tsl_manifest_header) {
    throw std::runtime_error("unexpected manifest header in " + path);
  }
  std::vector<TslManifestEntry> entries;
  while (std::getline(in, line)) {
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> fields;
    std::istringstream stream(line);
    std::string field;
    while (std::getline(stream, field, '\t')) {
      fields.push_back(field);
    }
    if (fields.size() != 10) {
      throw std::runtime_error("manifest line has " + std::to_string(fields.size()) + " fields");
    }
    TslManifestEntry entry;
    entry.id = fields[0];
    entry.file = fields[1];
    entry.shape = fields[2];
    entry.element_bytes = std::stoull(fields[3]);
    entry.rows = std::stoull(fields[4]);
    entry.columns = std::stoull(fields[5]);
    entry.seed = std::stoull(fields[6]);
    entry.checksum = std::stoull(fields[7]);
    entry.params = tsl_parse_params(fields[8]);
    entry.measured = fields[9];
    entries.push_back(std::move(entry));
  }
  return entries;
}

inline void tsl_write_manifest_json(
  std::string const & path,
  std::vector<TslManifestEntry> const & entries,
  std::vector<TslDatasetDescriptor> const & descriptors
) {
  std::ofstream out(path, std::ios::trunc);
  if (!out) {
    throw std::runtime_error("cannot write " + path);
  }
  auto const array = [&out](char const * name, auto const & values) {
    out << "      \"" << name << "\": [";
    for (std::size_t index = 0; index < values.size(); ++index) {
      out << (index == 0 ? "" : ", ") << tsl_format_double(static_cast<double>(values[index]));
    }
    out << "]";
  };
  out << "{\n  \"datasets\": [\n";
  for (std::size_t index = 0; index < entries.size(); ++index) {
    auto const & entry = entries[index];
    auto const & measured = descriptors[index];
    out << "    {\n";
    out << "      \"id\": \"" << entry.id << "\",\n";
    out << "      \"file\": \"" << entry.file << "\",\n";
    out << "      \"shape\": \"" << entry.shape << "\",\n";
    out << "      \"section\": " << tsl_shape_section(tsl_shape_from_name(entry.shape)) << ",\n";
    out << "      \"element_bytes\": " << entry.element_bytes << ",\n";
    out << "      \"rows\": " << entry.rows << ",\n";
    out << "      \"columns\": " << entry.columns << ",\n";
    out << "      \"seed\": " << entry.seed << ",\n";
    out << "      \"checksum\": " << entry.checksum << ",\n";
    out << "      \"params\": {";
    bool first = true;
    for (auto const & parameter : entry.params) {
      out << (first ? "" : ", ") << "\"" << parameter.first << "\": "
          << tsl_format_double(parameter.second);
      first = false;
    }
    out << "},\n";
    array("distinct_prefixes", measured.distinct_prefixes); out << ",\n";
    array("tied_rows", measured.tied_rows); out << ",\n";
    array("max_group", measured.max_group); out << ",\n";
    array("nontrivial_groups", measured.nontrivial_groups); out << ",\n";
    array("column_cardinality", measured.column_cardinality); out << ",\n";
    array("prefix_in_order_fraction", measured.prefix_in_order_fraction); out << ",\n";
    array("leaf_fill_ratio", measured.leaf_fill_ratio); out << ",\n";
    array("leaf_capacities", tsl_network_capacities); out << ",\n";
    out << "      \"weighted_work\": " << tsl_format_double(measured.weighted_work) << ",\n";
    out << "      \"scan_volume\": " << tsl_format_double(measured.scan_volume) << ",\n";
    out << "      \"ascending_runs\": " << measured.ascending_runs << ",\n";
    out << "      \"kendall_normalized\": " << tsl_format_double(measured.kendall_normalized) << ",\n";
    out << "      \"mean_displacement\": " << tsl_format_double(measured.mean_displacement) << ",\n";
    out << "      \"adjacency_fraction\": " << tsl_format_double(measured.adjacency_fraction) << ",\n";
    out << "      \"duplicate_tuple_fraction\": "
        << tsl_format_double(measured.duplicate_tuple_fraction) << "\n";
    out << "    }" << (index + 1 == entries.size() ? "\n" : ",\n");
  }
  out << "  ]\n}\n";
}
