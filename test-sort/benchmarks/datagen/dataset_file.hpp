#pragma once

// Binary container for one generated dataset.
//
// Column-major with a fixed 64-byte header, so a consumer can read one column
// straight into an aligned buffer without consulting the manifest:
//
//   offset  size  field
//   0       8     magic "TSLDSET1"
//   8       4     format version
//   12      4     element bytes (4 or 8)
//   16      8     rows
//   24      4     columns
//   28      4     reserved (zero)
//   32      8     generator seed
//   40      24    zero padding to the payload offset
//   64      rows * columns * element_bytes   column 0, then column 1, ...
//
// The header is written field by field in little-endian order rather than as a
// struct copy: the file is read by other tools, so its layout must not depend on
// this compiler's padding choices.

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

inline constexpr std::uint32_t tsl_dataset_version = 1;
inline constexpr std::size_t tsl_dataset_payload_offset = 64;
inline constexpr char tsl_dataset_magic[9] = "TSLDSET1";

struct TslDatasetHeader {
  std::uint32_t version = tsl_dataset_version;
  std::uint32_t element_bytes = 4;
  std::uint64_t rows = 0;
  std::uint32_t columns = 0;
  std::uint64_t seed = 0;
};

namespace tsl_dataset_detail {

template <class Value>
void put_le(std::array<unsigned char, tsl_dataset_payload_offset> & buffer,
            std::size_t offset, Value value) {
  for (std::size_t byte = 0; byte < sizeof(Value); ++byte) {
    buffer[offset + byte] = static_cast<unsigned char>((value >> (8 * byte)) & 0xffu);
  }
}

template <class Value>
auto get_le(std::array<unsigned char, tsl_dataset_payload_offset> const & buffer,
            std::size_t offset) -> Value {
  Value value = 0;
  for (std::size_t byte = 0; byte < sizeof(Value); ++byte) {
    value |= static_cast<Value>(buffer[offset + byte]) << (8 * byte);
  }
  return value;
}

}  // namespace tsl_dataset_detail

// FNV-1a over the payload. Written into the manifest so that a repeated
// generator run can be compared byte-for-byte without keeping both trees.
inline auto tsl_dataset_checksum_update(std::uint64_t hash, void const * data, std::size_t bytes)
  -> std::uint64_t {
  auto const * cursor = static_cast<unsigned char const *>(data);
  for (std::size_t index = 0; index < bytes; ++index) {
    hash ^= cursor[index];
    hash *= 0x100000001b3ull;
  }
  return hash;
}

inline constexpr std::uint64_t tsl_dataset_checksum_seed = 0xcbf29ce484222325ull;

template <class DataType>
auto tsl_dataset_checksum(std::vector<std::vector<DataType>> const & columns) -> std::uint64_t {
  auto hash = tsl_dataset_checksum_seed;
  for (auto const & column : columns) {
    hash = tsl_dataset_checksum_update(hash, column.data(), column.size() * sizeof(DataType));
  }
  return hash;
}

template <class DataType>
void tsl_dataset_write(
  std::string const & path,
  std::vector<std::vector<DataType>> const & columns,
  std::uint64_t seed
) {
  if (columns.empty()) {
    throw std::invalid_argument("dataset must have at least one column");
  }
  auto const rows = columns.front().size();
  for (auto const & column : columns) {
    if (column.size() != rows) {
      throw std::invalid_argument("dataset columns must have equal length");
    }
  }

  std::array<unsigned char, tsl_dataset_payload_offset> header{};
  std::memcpy(header.data(), tsl_dataset_magic, 8);
  tsl_dataset_detail::put_le<std::uint32_t>(header, 8, tsl_dataset_version);
  tsl_dataset_detail::put_le<std::uint32_t>(header, 12, static_cast<std::uint32_t>(sizeof(DataType)));
  tsl_dataset_detail::put_le<std::uint64_t>(header, 16, static_cast<std::uint64_t>(rows));
  tsl_dataset_detail::put_le<std::uint32_t>(header, 24, static_cast<std::uint32_t>(columns.size()));
  tsl_dataset_detail::put_le<std::uint32_t>(header, 28, 0u);
  tsl_dataset_detail::put_le<std::uint64_t>(header, 32, seed);

  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  if (!out) {
    throw std::runtime_error("cannot open for writing: " + path);
  }
  out.write(reinterpret_cast<char const *>(header.data()), static_cast<std::streamsize>(header.size()));
  for (auto const & column : columns) {
    out.write(
      reinterpret_cast<char const *>(column.data()),
      static_cast<std::streamsize>(column.size() * sizeof(DataType))
    );
  }
  out.flush();
  if (!out) {
    throw std::runtime_error("write failed: " + path);
  }
}

inline auto tsl_dataset_read_header(std::string const & path) -> TslDatasetHeader {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("cannot open for reading: " + path);
  }
  std::array<unsigned char, tsl_dataset_payload_offset> buffer{};
  in.read(reinterpret_cast<char *>(buffer.data()), static_cast<std::streamsize>(buffer.size()));
  if (!in) {
    throw std::runtime_error("truncated header: " + path);
  }
  if (std::memcmp(buffer.data(), tsl_dataset_magic, 8) != 0) {
    throw std::runtime_error("not a TSL dataset: " + path);
  }
  TslDatasetHeader header;
  header.version = tsl_dataset_detail::get_le<std::uint32_t>(buffer, 8);
  header.element_bytes = tsl_dataset_detail::get_le<std::uint32_t>(buffer, 12);
  header.rows = tsl_dataset_detail::get_le<std::uint64_t>(buffer, 16);
  header.columns = tsl_dataset_detail::get_le<std::uint32_t>(buffer, 24);
  header.seed = tsl_dataset_detail::get_le<std::uint64_t>(buffer, 32);
  if (header.version != tsl_dataset_version) {
    throw std::runtime_error("unsupported dataset version in " + path);
  }
  if (header.element_bytes != 4 && header.element_bytes != 8) {
    throw std::runtime_error("unsupported element width in " + path);
  }
  return header;
}

template <class DataType>
auto tsl_dataset_read(std::string const & path, TslDatasetHeader const & header)
  -> std::vector<std::vector<DataType>> {
  if (header.element_bytes != sizeof(DataType)) {
    throw std::runtime_error("element width mismatch for " + path);
  }
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("cannot open for reading: " + path);
  }
  in.seekg(static_cast<std::streamoff>(tsl_dataset_payload_offset));
  std::vector<std::vector<DataType>> columns(header.columns);
  for (auto & column : columns) {
    column.resize(static_cast<std::size_t>(header.rows));
    in.read(
      reinterpret_cast<char *>(column.data()),
      static_cast<std::streamsize>(column.size() * sizeof(DataType))
    );
    if (!in) {
      throw std::runtime_error("truncated payload: " + path);
    }
  }
  return columns;
}
