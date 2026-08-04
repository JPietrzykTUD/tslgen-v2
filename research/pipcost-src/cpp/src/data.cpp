#include "pipcost/data.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace pipcost {
namespace {

class SplitMix64 {
  public:
    explicit SplitMix64(std::uint64_t seed) : state_(seed) {}

    std::uint64_t next() {
        std::uint64_t value = (state_ += 0x9e3779b97f4a7c15ULL);
        value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
        value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
        return value ^ (value >> 31U);
    }

  private:
    std::uint64_t state_;
};

std::size_t exact_count(std::size_t rows, double selectivity) {
    if (!(selectivity >= 0.0 && selectivity <= 1.0)) {
        throw std::invalid_argument("selectivity must be within [0, 1]");
    }
    return static_cast<std::size_t>(
        std::floor(static_cast<double>(rows) * selectivity + 0.5));
}

void deterministic_shuffle(
    std::vector<std::size_t>& values,
    SplitMix64& random) {
    for (std::size_t i = values.size(); i > 1; --i) {
        const std::size_t other =
            static_cast<std::size_t>(random.next() % i);
        std::swap(values[i - 1], values[other]);
    }
}

std::uint64_t fnv1a(
    std::uint64_t digest,
    const std::int32_t* values,
    std::size_t count) {
    constexpr std::uint64_t prime = 1099511628211ULL;
    const auto* bytes = reinterpret_cast<const unsigned char*>(values);
    for (std::size_t i = 0; i < count * sizeof(std::int32_t); ++i) {
        digest ^= bytes[i];
        digest *= prime;
    }
    return digest;
}

}  // namespace

DataSet generate_data(const DataSpec& spec) {
    if (spec.pattern != "random" && spec.pattern != "clustered") {
        throw std::invalid_argument("pattern must be random or clustered");
    }

    DataSet result;
    result.a.assign(spec.rows, 1);
    result.b.assign(spec.rows, -1);
    result.c.resize(spec.rows);

    result.first_matches = exact_count(spec.rows, spec.first_selectivity);
    result.combined_matches =
        exact_count(result.first_matches, spec.conditional_selectivity);

    std::vector<std::size_t> order(spec.rows);
    for (std::size_t i = 0; i < spec.rows; ++i) {
        order[i] = i;
    }
    SplitMix64 random(spec.seed);
    if (spec.pattern == "random") {
        deterministic_shuffle(order, random);
    } else if (spec.rows != 0) {
        const std::size_t start =
            static_cast<std::size_t>(random.next() % spec.rows);
        for (std::size_t i = 0; i < spec.rows; ++i) {
            order[i] = (start + i) % spec.rows;
        }
    }

    for (std::size_t i = 0; i < result.first_matches; ++i) {
        result.a[order[i]] = -1;
    }

    std::vector<std::size_t> first_rows(
        order.begin(),
        order.begin() + static_cast<std::ptrdiff_t>(result.first_matches));
    if (spec.pattern == "random") {
        deterministic_shuffle(first_rows, random);
    }
    for (std::size_t i = 0; i < result.combined_matches; ++i) {
        result.b[first_rows[i]] = 1;
    }

    for (std::size_t i = 0; i < spec.rows; ++i) {
        result.c[i] =
            static_cast<std::int32_t>(static_cast<int>(random.next() % 201U) - 100);
    }

    std::uint64_t digest = 1469598103934665603ULL;
    digest = fnv1a(digest, result.a.data(), result.a.size());
    digest = fnv1a(digest, result.b.data(), result.b.size());
    result.digest = fnv1a(digest, result.c.data(), result.c.size());
    return result;
}

}  // namespace pipcost
