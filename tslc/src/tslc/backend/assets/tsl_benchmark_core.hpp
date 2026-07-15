#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#if (defined(__x86_64__) || defined(__i386__)) && \
    (defined(__GNUC__) || defined(__clang__))
#  include <cpuid.h>
#endif

namespace tsl::benchmark {

using clock = std::chrono::steady_clock;

template <class T>
inline void do_not_optimize(T const& value) {
#if defined(__GNUC__) || defined(__clang__)
    asm volatile("" : : "g"(&value) : "memory");
#else
    volatile auto const* sink = &value;
    (void)sink;
#endif
}

inline std::uint64_t splitmix64(std::uint64_t& state) {
    std::uint64_t value = (state += 0x9e3779b97f4a7c15ULL);
    value = (value ^ (value >> 30U)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27U)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31U);
}

inline std::uint64_t rotating_mask_bits(std::size_t lanes, std::size_t active_lanes,
                                        std::size_t rotation) {
    if (lanes == 0 || lanes > 64 || active_lanes == 0 || active_lanes > lanes) {
        throw std::runtime_error("invalid compact-mask benchmark dimensions");
    }
    std::uint64_t result = 0;
    for (std::size_t offset = 0; offset < active_lanes; ++offset) {
        result |= std::uint64_t{1} << ((rotation + offset) % lanes);
    }
    return result;
}

template <class T>
inline T next_value(std::uint64_t& state) {
    const std::uint64_t bits = splitmix64(state);
    if constexpr (std::is_floating_point_v<T>) {
        const std::int64_t centered = static_cast<std::int64_t>(bits % 20001ULL) - 10000;
        return static_cast<T>(centered) / static_cast<T>(257);
    } else if constexpr (std::is_signed_v<T>) {
        const std::int64_t limit = std::min<std::int64_t>(
            1000, static_cast<std::int64_t>(std::numeric_limits<T>::max()));
        const std::int64_t centered =
            static_cast<std::int64_t>(bits % static_cast<std::uint64_t>(2 * limit + 1)) - limit;
        return static_cast<T>(centered);
    } else {
        const std::uint64_t limit = std::min<std::uint64_t>(
            2000, static_cast<std::uint64_t>(std::numeric_limits<T>::max()));
        return static_cast<T>(bits % (limit + 1));
    }
}

template <class T>
inline T next_nonzero_value(std::uint64_t& state) {
    T value{};
    do {
        value = next_value<T>(state);
    } while (value == T{});
    return value;
}

template <class T>
inline T next_shift_count(std::uint64_t& state) {
    constexpr std::uint64_t lane_bits = sizeof(T) * 8U;
    return static_cast<T>(splitmix64(state) % lane_bits);
}

inline std::uint64_t elapsed_ns(clock::time_point begin, clock::time_point end) {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(end - begin).count());
}

template <class Measure>
inline std::size_t calibrate(Measure&& measure, std::uint64_t minimum_sample_ns) {
    std::size_t iterations = 1;
    while (measure(iterations) < minimum_sample_ns) {
        if (iterations > (std::size_t{1} << 30U)) {
            throw std::runtime_error("benchmark calibration exceeded iteration limit");
        }
        iterations *= 2;
    }
    return iterations;
}

inline double median(std::vector<double> values) {
    if (values.empty()) {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    const std::size_t middle = values.size() / 2;
    if ((values.size() & 1U) != 0U) {
        return values[middle];
    }
    return (values[middle - 1] + values[middle]) / 2.0;
}

inline std::string json_escape(std::string const& value) {
    std::string result;
    result.reserve(value.size() + 8);
    for (char ch : value) {
        switch (ch) {
        case '\\': result += "\\\\"; break;
        case '"': result += "\\\""; break;
        case '\n': result += "\\n"; break;
        case '\r': result += "\\r"; break;
        case '\t': result += "\\t"; break;
        default: result += ch; break;
        }
    }
    return result;
}

inline std::string read_file(std::string const& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open policy file: " + path);
    }
    return std::string(
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

inline void write_file(std::string const& path, std::string const& content) {
    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("cannot write benchmark artifact: " + path);
    }
    output << content;
    if (!output) {
        throw std::runtime_error("cannot finish benchmark artifact: " + path);
    }
}

inline std::string json_string_field(std::string const& document,
                                     std::string const& field,
                                     std::size_t begin = 0,
                                     std::size_t limit = std::string::npos) {
    if (limit == std::string::npos) {
        limit = document.size();
    }
    const std::string key = "\"" + field + "\"";
    std::size_t position = document.find(key, begin);
    if (position == std::string::npos || position >= limit) {
        throw std::runtime_error("policy is missing field '" + field + "'");
    }
    position = document.find(':', position + key.size());
    if (position == std::string::npos || position >= limit) {
        throw std::runtime_error("policy field '" + field + "' has no value");
    }
    position = document.find('"', position + 1);
    if (position == std::string::npos || position >= limit) {
        throw std::runtime_error("policy field '" + field + "' is not a string");
    }
    const std::size_t end = document.find('"', position + 1);
    if (end == std::string::npos || end > limit) {
        throw std::runtime_error("unterminated policy string field '" + field + "'");
    }
    return document.substr(position + 1, end - position - 1);
}

inline std::size_t substring_count(std::string const& document,
                                   std::string const& needle) {
    std::size_t count = 0;
    std::size_t position = 0;
    while ((position = document.find(needle, position)) != std::string::npos) {
        ++count;
        position += needle.size();
    }
    return count;
}

inline std::string cpu_id() {
#if (defined(__x86_64__) || defined(__i386__)) && \
    (defined(__GNUC__) || defined(__clang__))
    unsigned int eax = 0, ebx = 0, ecx = 0, edx = 0;
    if (__get_cpuid(0, &eax, &ebx, &ecx, &edx) == 0) {
        return "x86:unknown";
    }
    char vendor[13] = {};
    std::memcpy(vendor, &ebx, 4);
    std::memcpy(vendor + 4, &edx, 4);
    std::memcpy(vendor + 8, &ecx, 4);
    if (__get_cpuid(1, &eax, &ebx, &ecx, &edx) == 0) {
        return std::string("x86:") + vendor + ":unknown";
    }
    const unsigned int stepping = eax & 0xfU;
    const unsigned int base_model = (eax >> 4U) & 0xfU;
    const unsigned int base_family = (eax >> 8U) & 0xfU;
    const unsigned int model = base_model |
        ((base_family == 0x6U || base_family == 0xfU) ? ((eax >> 12U) & 0xf0U) : 0U);
    const unsigned int family = base_family == 0xfU
        ? base_family + ((eax >> 20U) & 0xffU)
        : base_family;
    return std::string("x86:") + vendor + ":" + std::to_string(family) + ":" +
           std::to_string(model) + ":" + std::to_string(stepping);
#elif defined(__aarch64__)
    return "aarch64";
#elif defined(__wasm__)
    return "wasm";
#else
    return "unknown-architecture";
#endif
}

struct RawSample {
    std::string stable_id;
    std::string scenario;
    std::string candidate;
    std::size_t round = 0;
    std::size_t iterations = 0;
    std::uint64_t elapsed = 0;
};

struct Decision {
    std::string stable_id;
    std::string selected;
    std::string status;
    double minimum_improvement = 0.0;
};

inline Decision reduce_candidate_set(
    std::string const& stable_id,
    std::vector<std::string> const& candidates,
    std::vector<std::string> const& scenarios,
    std::vector<RawSample> const& samples,
    double threshold) {
    Decision best{stable_id, "default", "inconclusive", 0.0};
    for (std::size_t candidate_index = 1; candidate_index < candidates.size();
         ++candidate_index) {
        bool dominates = true;
        double minimum_improvement = 1.0;
        for (auto const& scenario : scenarios) {
            std::vector<double> improvements;
            std::size_t wins = 0;
            for (auto const& alternative : samples) {
                if (alternative.stable_id != stable_id ||
                    alternative.scenario != scenario ||
                    alternative.candidate != candidates[candidate_index]) {
                    continue;
                }
                auto const found = std::find_if(
                    samples.begin(), samples.end(), [&](RawSample const& baseline) {
                        return baseline.stable_id == stable_id &&
                               baseline.scenario == scenario &&
                               baseline.candidate == "default" &&
                               baseline.round == alternative.round;
                    });
                if (found == samples.end() || found->elapsed == 0 ||
                    found->iterations == 0 || alternative.iterations == 0) {
                    continue;
                }
                const double baseline_ns =
                    static_cast<double>(found->elapsed) / found->iterations;
                const double alternative_ns =
                    static_cast<double>(alternative.elapsed) / alternative.iterations;
                const double improvement =
                    (baseline_ns - alternative_ns) / baseline_ns;
                improvements.push_back(improvement);
                if (improvement > 0.0) {
                    ++wins;
                }
            }
            if (improvements.size() < 3) {
                dominates = false;
                break;
            }
            const double central = median(improvements);
            std::vector<double> deviations;
            deviations.reserve(improvements.size());
            for (double improvement : improvements) {
                deviations.push_back(std::abs(improvement - central));
            }
            const double dispersion = median(std::move(deviations));
            const std::size_t required_wins = (2 * improvements.size() + 2) / 3;
            if (central < threshold || wins < required_wins ||
                dispersion > std::max(0.02, central * 0.75)) {
                dominates = false;
                break;
            }
            minimum_improvement = std::min(minimum_improvement, central);
        }
        if (dominates && minimum_improvement > best.minimum_improvement) {
            best.selected = candidates[candidate_index];
            best.status = "selected";
            best.minimum_improvement = minimum_improvement;
        }
    }
    return best;
}

inline void reducer_self_test() {
    const std::vector<std::string> candidates{"default", "alternative"};
    const std::vector<std::string> scenarios{"throughput", "latency"};
    auto samples = [&](std::vector<std::uint64_t> const& throughput,
                       std::vector<std::uint64_t> const& latency) {
        std::vector<RawSample> result;
        for (std::size_t scenario = 0; scenario < scenarios.size(); ++scenario) {
            auto const& alternative = scenario == 0 ? throughput : latency;
            for (std::size_t round = 0; round < alternative.size(); ++round) {
                result.push_back(RawSample{
                    "self", scenarios[scenario], "default", round, 1, 100});
                result.push_back(RawSample{
                    "self", scenarios[scenario], "alternative", round, 1,
                    alternative[round]});
            }
        }
        return result;
    };
    const Decision stable = reduce_candidate_set(
        "self", candidates, scenarios, samples({80, 80, 80}, {80, 80, 80}), 0.05);
    const Decision conflicting = reduce_candidate_set(
        "self", candidates, scenarios, samples({80, 80, 80}, {120, 120, 120}), 0.05);
    const Decision noisy = reduce_candidate_set(
        "self", candidates, scenarios, samples({80, 120, 40}, {80, 80, 80}), 0.05);
    const Decision incomplete = reduce_candidate_set(
        "self", candidates, scenarios, samples({80, 80}, {80, 80}), 0.05);
    if (stable.selected != "alternative" || conflicting.selected != "default" ||
        noisy.selected != "default" || incomplete.selected != "default") {
        throw std::runtime_error("benchmark reducer self-test failed");
    }
}

}  // namespace tsl::benchmark
