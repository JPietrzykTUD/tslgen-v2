// Reproducible TSL v1 checked-API mechanism benchmark.
// Compile this file against a generated C++ tree with either
// TSL_PROFILE_SCALAR or TSL_PROFILE_AVX2 selected.

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <immintrin.h>
#include <iomanip>
#include <iostream>
#include <string_view>
#include <x86intrin.h>

#include "tsl.hpp"

namespace {

#if defined(TSL_PROFILE_AVX2)
using vec = tsl::simd<std::int32_t, tsl::avx2>;
constexpr std::string_view profile = "avx2";

TSL_FORCE_INLINE auto raw_set1(std::int32_t value) noexcept -> __m256i {
  return _mm256_set1_epi32(value);
}

TSL_FORCE_INLINE auto raw_lane(__m256i value, std::size_t index) noexcept
    -> std::int32_t {
  alignas(32) std::int32_t lanes[8];
  _mm256_store_si256(reinterpret_cast<__m256i *>(lanes), value);
  return lanes[index];
}

TSL_FORCE_INLINE auto raw_div(__m256i dividend, __m256i divisor) noexcept
    -> __m256i {
  alignas(32) std::int32_t left[8];
  alignas(32) std::int32_t right[8];
  alignas(32) std::int32_t result[8];
  _mm256_store_si256(reinterpret_cast<__m256i *>(left), dividend);
  _mm256_store_si256(reinterpret_cast<__m256i *>(right), divisor);
  for (std::size_t lane = 0; lane < 8; ++lane) {
    result[lane] = left[lane] / right[lane];
  }
  return _mm256_load_si256(reinterpret_cast<__m256i const *>(result));
}

TSL_FORCE_INLINE auto raw_load(std::int32_t const *ptr) noexcept -> __m256i {
  return _mm256_load_si256(reinterpret_cast<__m256i const *>(ptr));
}

TSL_FORCE_INLINE auto raw_checksum(__m256i value) noexcept -> std::uint64_t {
  alignas(32) std::int32_t lanes[8];
  _mm256_store_si256(reinterpret_cast<__m256i *>(lanes), value);
  std::uint64_t result = 0;
  for (auto lane : lanes) {
    result += static_cast<std::uint64_t>(lane);
  }
  return result;
}
#elif defined(TSL_PROFILE_SCALAR)
using vec = tsl::simd<std::int32_t, tsl::scalar>;
constexpr std::string_view profile = "scalar";

TSL_FORCE_INLINE auto raw_set1(std::int32_t value) noexcept -> std::int32_t {
  return value;
}

TSL_FORCE_INLINE auto raw_lane(std::int32_t value, std::size_t) noexcept
    -> std::int32_t {
  return value;
}

TSL_FORCE_INLINE auto raw_div(std::int32_t dividend,
                              std::int32_t divisor) noexcept -> std::int32_t {
  return dividend / divisor;
}

TSL_FORCE_INLINE auto raw_load(std::int32_t const *ptr) noexcept
    -> std::int32_t {
  return *ptr;
}

TSL_FORCE_INLINE auto raw_checksum(std::int32_t value) noexcept
    -> std::uint64_t {
  return static_cast<std::uint64_t>(value);
}
#else
#error "Select TSL_PROFILE_SCALAR or TSL_PROFILE_AVX2"
#endif

struct sample {
  std::uint64_t ticks;
  std::uint64_t checksum;
  std::uint64_t errors;
};

template <class Function>
auto measure(std::size_t iterations, Function &&function) -> sample {
  std::uint64_t checksum = 0;
  std::uint64_t errors = 0;
  unsigned auxiliary = 0;
  _mm_lfence();
  const auto begin = __rdtscp(&auxiliary);
  _mm_lfence();
  for (std::size_t iteration = 0; iteration < iterations; ++iteration) {
    checksum = function(iteration, checksum, errors);
    asm volatile("" : "+r"(checksum) : : "memory");
  }
  _mm_lfence();
  const auto end = __rdtscp(&auxiliary);
  _mm_lfence();
  return {end - begin, checksum, errors};
}

void print(std::string_view operation, std::string_view variant, sample result,
           std::size_t iterations) {
  std::cout << profile << '\t' << operation << '\t' << variant << '\t'
            << std::fixed << std::setprecision(3)
            << static_cast<double>(result.ticks) /
                   static_cast<double>(iterations)
            << '\t' << result.checksum << '\t' << result.errors << '\n';
  const auto expected_errors =
      variant == "checked_failure" ? iterations : std::size_t{0};
  if (result.errors != expected_errors) {
    std::exit(3);
  }
}

} // namespace

#if defined(_MSC_VER)
#define TSL_SHOWCASE_NOINLINE __declspec(noinline)
#else
#define TSL_SHOWCASE_NOINLINE __attribute__((noinline))
#endif

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_raw_lane(vec::register_type data, std::size_t index) noexcept
    -> std::int32_t {
  return raw_lane(data, index);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_unchecked_lane(vec::register_type data, std::size_t index) noexcept
    -> std::int32_t {
  return tsl::extract_value_at<vec>(data, index);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_checked_lane(vec::register_type data, std::size_t index) noexcept
    -> std::int32_t {
  tsl::precondition_error error{};
  const auto candidate = tsl::extract_value_at_checked<vec>(data, index, error);
  return error == tsl::precondition_error::none ? candidate : 0;
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_raw_div(vec::register_type dividend,
                 vec::register_type divisor) noexcept -> vec::register_type {
  return raw_div(dividend, divisor);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_unchecked_div(vec::register_type dividend,
                       vec::register_type divisor) noexcept
    -> vec::register_type {
  return tsl::div<vec>(dividend, divisor);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_checked_div(vec::register_type dividend,
                     vec::register_type divisor) noexcept
    -> vec::register_type {
  tsl::precondition_error error{};
  const auto candidate = tsl::div_checked<vec>(dividend, divisor, error);
  return error == tsl::precondition_error::none ? candidate : raw_set1(0);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_raw_load(std::int32_t const *source) noexcept -> vec::register_type {
  return raw_load(source);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_unchecked_load(std::int32_t const *source) noexcept
    -> vec::register_type {
  return tsl::load<vec, true>(source);
}

extern "C" TSL_SHOWCASE_NOINLINE auto
showcase_checked_load(std::int32_t const *source, std::size_t extent) noexcept
    -> vec::register_type {
  tsl::precondition_error error{};
  const auto candidate = tsl::load_checked<vec, true>(
      tsl::span<std::int32_t const>(source, extent), error);
  return error == tsl::precondition_error::none ? candidate : raw_set1(0);
}

int main(int argc, char **argv) {
  constexpr std::size_t storage_size = 2048;
  const std::size_t iterations =
      argc > 1 ? static_cast<std::size_t>(std::strtoull(argv[1], nullptr, 10))
               : 200000;
  const std::size_t valid_lane =
      argc > 2 ? std::strtoull(argv[2], nullptr, 10) % vec::lane_count() : 0;
  const std::size_t valid_extent =
      argc > 3 ? std::strtoull(argv[3], nullptr, 10) : vec::lane_count();
  const std::int32_t divisor_value =
      argc > 4 ? static_cast<std::int32_t>(std::strtol(argv[4], nullptr, 10))
               : 3;
  if (iterations == 0 || valid_extent != vec::lane_count() ||
      divisor_value == 0) {
    return 2;
  }

  alignas(64) std::array<std::int32_t, storage_size> storage{};
  for (std::size_t index = 0; index < storage.size(); ++index) {
    storage[index] = static_cast<std::int32_t>((index % 97) + 1000000);
  }
  const auto value = raw_set1(storage[valid_lane] + argc);
  volatile std::size_t runtime_lane = valid_lane;
  volatile std::size_t failure_lane = vec::lane_count();
  volatile std::size_t runtime_extent = valid_extent;
  volatile std::size_t failure_extent = 0;
  volatile std::int32_t runtime_divisor = divisor_value;
  volatile std::int32_t zero_divisor = 0;

  std::cout
      << "profile\toperation\tvariant\tcycles_per_call\tchecksum\terrors\n";

  print("lane", "raw",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto input = raw_load(storage.data() + offset);
                  return sum + static_cast<std::uint64_t>(
                                   raw_lane(input, runtime_lane));
                }),
        iterations);
  print("lane", "unchecked",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto input = raw_load(storage.data() + offset);
                  return sum +
                         static_cast<std::uint64_t>(
                             tsl::extract_value_at<vec>(input, runtime_lane));
                }),
        iterations);
  print("lane", "checked_valid",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &errors) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto input = raw_load(storage.data() + offset);
                  tsl::precondition_error error{};
                  const auto candidate = tsl::extract_value_at_checked<vec>(
                      input, runtime_lane, error);
                  if (error != tsl::precondition_error::none) {
                    ++errors;
                    return sum;
                  }
                  return sum + static_cast<std::uint64_t>(candidate);
                }),
        iterations);
  print("lane", "checked_failure",
        measure(iterations,
                [&](std::size_t, auto sum, auto &errors) {
                  tsl::precondition_error error{};
                  const auto candidate = tsl::extract_value_at_checked<vec>(
                      value, failure_lane, error);
                  if (error == tsl::precondition_error::index_out_of_bounds) {
                    ++errors;
                    return sum;
                  }
                  if (error != tsl::precondition_error::none) {
                    return sum;
                  }
                  return sum + static_cast<std::uint64_t>(candidate);
                }),
        iterations);

  print("div", "raw",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto dividend = raw_load(storage.data() + offset);
                  const auto divisor = raw_set1(runtime_divisor);
                  const auto candidate = raw_div(dividend, divisor);
                  return sum + raw_checksum(candidate);
                }),
        iterations);
  print("div", "unchecked",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto dividend = raw_load(storage.data() + offset);
                  const auto divisor = raw_set1(runtime_divisor);
                  const auto candidate = tsl::div<vec>(dividend, divisor);
                  return sum + raw_checksum(candidate);
                }),
        iterations);
  print("div", "checked_valid",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &errors) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto dividend = raw_load(storage.data() + offset);
                  const auto divisor = raw_set1(runtime_divisor);
                  tsl::precondition_error error{};
                  const auto candidate =
                      tsl::div_checked<vec>(dividend, divisor, error);
                  if (error != tsl::precondition_error::none) {
                    ++errors;
                    return sum;
                  }
                  return sum + raw_checksum(candidate);
                }),
        iterations);
  print("div", "checked_failure",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &errors) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto dividend = raw_load(storage.data() + offset);
                  const auto divisor = raw_set1(zero_divisor);
                  tsl::precondition_error error{};
                  const auto candidate =
                      tsl::div_checked<vec>(dividend, divisor, error);
                  if (error == tsl::precondition_error::zero_divisor) {
                    ++errors;
                    return sum;
                  }
                  if (error != tsl::precondition_error::none) {
                    return sum;
                  }
                  return sum + raw_checksum(candidate);
                }),
        iterations);

  const auto load_loop = [&](auto operation) {
    return measure(iterations, [&](std::size_t iteration, auto sum,
                                   auto &errors) {
      const auto offset =
          (iteration * vec::lane_count()) & (storage_size - vec::lane_count());
      const auto candidate = operation(storage.data() + offset, errors);
      return sum + raw_checksum(candidate);
    });
  };
  print("load", "raw",
        load_loop([&](auto ptr, auto &) { return raw_load(ptr); }), iterations);
  print("load", "unchecked",
        load_loop([&](auto ptr, auto &) { return tsl::load<vec, true>(ptr); }),
        iterations);
  print("load", "checked_valid",
        measure(iterations,
                [&](std::size_t iteration, auto sum, auto &errors) {
                  const auto offset = (iteration * vec::lane_count()) &
                                      (storage_size - vec::lane_count());
                  const auto ptr = storage.data() + offset;
                  tsl::precondition_error error{};
                  const auto candidate = tsl::load_checked<vec, true>(
                      tsl::span<std::int32_t const>(ptr, runtime_extent),
                      error);
                  if (error != tsl::precondition_error::none) {
                    ++errors;
                    return sum;
                  }
                  return sum + raw_checksum(candidate);
                }),
        iterations);
  print("load", "checked_failure",
        measure(iterations,
                [&](std::size_t, auto sum, auto &errors) {
                  tsl::precondition_error error{};
                  const auto candidate = tsl::load_checked<vec, true>(
                      tsl::span<std::int32_t const>(storage.data(),
                                                    failure_extent),
                      error);
                  if (error == tsl::precondition_error::insufficient_extent) {
                    ++errors;
                    return sum;
                  }
                  if (error != tsl::precondition_error::none) {
                    return sum;
                  }
                  return sum + raw_checksum(candidate);
                }),
        iterations);
  return 0;
}
