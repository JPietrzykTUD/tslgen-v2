#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace pipcost {

struct DataSpec {
    std::size_t rows;
    double first_selectivity;
    double conditional_selectivity;
    std::string pattern;
    std::uint64_t seed;
};

struct DataSet {
    std::vector<std::int32_t> a;
    std::vector<std::int32_t> b;
    std::vector<std::int32_t> c;
    std::int32_t p1 = 0;
    std::int32_t p2 = 0;
    std::size_t first_matches = 0;
    std::size_t combined_matches = 0;
    std::uint64_t digest = 0;
};

DataSet generate_data(const DataSpec& spec);
std::int64_t scalar_reference(const DataSet& data);

}  // namespace pipcost
