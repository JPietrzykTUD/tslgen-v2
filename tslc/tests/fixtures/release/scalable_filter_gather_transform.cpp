#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <vector>

#include <tsl.hpp>

namespace {

constexpr std::int32_t canary = 0x1234567;

struct keep_positive {
  template <class Vec>
  auto operator()(typename tsl::reg_param<Vec>::type value) const
      -> typename Vec::mask_type {
    return tsl::greater_than<Vec>(value, tsl::set1<Vec>(0));
  }
};

struct affine_transform {
  template <class Vec>
  auto operator()(typename tsl::reg_param<Vec>::type value) const
      -> typename Vec::register_type {
    return tsl::add<Vec>(tsl::mul<Vec>(value, tsl::set1<Vec>(3)),
                         tsl::set1<Vec>(7));
  }
};

auto input_value(std::size_t index) -> std::int32_t {
  if ((index % 3) == 0) {
    return -static_cast<std::int32_t>(index + 1);
  }
  return static_cast<std::int32_t>(index * 5 + 1);
}

auto digest_values(const std::int32_t* values, std::size_t count)
    -> std::uint64_t {
  std::uint64_t digest = 1469598103934665603ull;
  for (std::size_t i = 0; i < count; ++i) {
    digest ^= static_cast<std::uint32_t>(values[i]);
    digest *= 1099511628211ull;
  }
  return digest;
}

template <class Vec>
auto build_tail_mask(std::size_t active_lanes, int& failure)
    -> typename Vec::mask_type {
  auto active = tsl::mask_false<Vec>();
  for (std::size_t lane = 0; lane < active_lanes; ++lane) {
    tsl::precondition_error error = tsl::precondition_error::none;
    active = tsl::set_mask_lane_checked<Vec>(active, lane, 1, error);
    if (error != tsl::precondition_error::none) {
      failure = 20;
      return tsl::mask_false<Vec>();
    }
  }
  return active;
}

}  // namespace

int main() {
  using Vec =
      tsl::dataparallel::simd_for_t<tsl::dataparallel::native, std::int32_t>;

  const std::size_t lanes = Vec::lane_count();
  if (lanes < 2) {
    return 1;
  }
  const std::size_t input_count = lanes * 3 + 2;
  std::vector<std::int32_t> input_storage(input_count + 2, canary);
  auto* input = input_storage.data() + 1;
  for (std::size_t i = 0; i < input_count; ++i) {
    input[i] = input_value(i);
  }

  std::vector<std::int32_t> filtered_storage(input_count + 2, canary);
  auto* filtered = filtered_storage.data() + 1;
  const std::size_t selected = tsl::algo::select_unary<
      tsl::dataparallel::native,
      tsl::algo::alignment::unaligned>(
      keep_positive{}, input, filtered, input_count);
  if (selected != lanes * 2 + 1 || filtered_storage.front() != canary ||
      filtered_storage.back() != canary) {
    return 2;
  }

  std::vector<std::int32_t> expected_filtered;
  for (std::size_t i = 0; i < input_count; ++i) {
    if (input[i] > 0) {
      expected_filtered.push_back(input[i]);
    }
  }
  if (expected_filtered.size() != selected) {
    return 3;
  }
  for (std::size_t i = 0; i < selected; ++i) {
    if (filtered[i] != expected_filtered[i]) {
      return 4;
    }
  }

  std::vector<std::int32_t> indices(selected);
  for (std::size_t i = 0; i < selected; ++i) {
    indices[i] = static_cast<std::int32_t>(selected - 1 - i);
  }
  std::vector<std::int32_t> gathered_storage(selected + 2, canary);
  auto* gathered = gathered_storage.data() + 1;
  const std::size_t full_count = (selected / lanes) * lanes;
  for (std::size_t offset = 0; offset < full_count; offset += lanes) {
    const auto index_vector = tsl::load<Vec, false>(indices.data() + offset);
    const auto values = tsl::gather<Vec, Vec, sizeof(std::int32_t)>(
        filtered, index_vector);
    tsl::store<Vec, false>(gathered + offset, values);
  }

  const std::size_t tail = selected - full_count;
  if (tail == 0) {
    return 5;
  }
  // Inactive lanes must not access memory. A broken implementation that
  // evaluates these large negative offsets should fault rather than being
  // hidden by an in-bounds sentinel element.
  std::vector<std::int32_t> tail_indices(
      lanes, std::numeric_limits<std::int32_t>::min() / 2);
  for (std::size_t lane = 0; lane < tail; ++lane) {
    tail_indices[lane] = indices[full_count + lane];
  }
  const auto index_vector = tsl::load<Vec, false>(tail_indices.data());
  int mask_failure = 0;
  const auto active = build_tail_mask<Vec>(tail, mask_failure);
  if (mask_failure != 0) {
    return mask_failure;
  }
  const auto tail_values = tsl::gather_mask<Vec, Vec, sizeof(std::int32_t)>(
      active, filtered, index_vector, tsl::set1<Vec>(canary));
  std::vector<std::int32_t> tail_result(lanes, canary);
  tsl::store<Vec, false>(tail_result.data(), tail_values);
  for (std::size_t lane = 0; lane < lanes; ++lane) {
    if (lane < tail) {
      gathered[full_count + lane] = tail_result[lane];
    } else if (tail_result[lane] != canary) {
      return 6;
    }
  }
  if (gathered_storage.front() != canary ||
      gathered_storage.back() != canary) {
    return 7;
  }

  std::vector<std::int32_t> output_storage(selected + 2, canary);
  auto* output = output_storage.data() + 1;
  tsl::algo::transform_unary<
      tsl::dataparallel::native,
      tsl::algo::alignment::unaligned>(
      affine_transform{}, gathered, output, selected);
  if (output_storage.front() != canary || output_storage.back() != canary ||
      input_storage.front() != canary || input_storage.back() != canary) {
    return 8;
  }

  for (std::size_t i = 0; i < selected; ++i) {
    const auto expected = expected_filtered[selected - 1 - i] * 3 + 7;
    if (gathered[i] != expected_filtered[selected - 1 - i] ||
        output[i] != expected) {
      return 9;
    }
  }

  std::printf(
      "{\"runtime_lanes\":%zu,\"input_count\":%zu,\"selected\":%zu,"
      "\"tail\":%zu,\"output_digest\":%llu}\n",
      lanes, input_count, selected, tail,
      static_cast<unsigned long long>(digest_values(output, selected)));
  return 0;
}
