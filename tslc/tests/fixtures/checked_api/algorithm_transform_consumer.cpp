#include "tsl.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

struct counting_unary {
  int* calls;

  template <class Vec>
  typename Vec::register_type operator()(
      typename ::tsl::reg_param<Vec>::type value) const {
    ++*calls;
    return value;
  }
};

struct counting_binary {
  int* calls;

  template <class Vec>
  typename Vec::register_type operator()(
      typename ::tsl::reg_param<Vec>::type left,
      typename ::tsl::reg_param<Vec>::type) const {
    ++*calls;
    return left;
  }
};

struct false_binary_predicate {
  int* calls;

  template <class Vec>
  typename Vec::mask_type operator()(
      typename ::tsl::reg_param<Vec>::type,
      typename ::tsl::reg_param<Vec>::type) const {
    ++*calls;
    return {};
  }
};

struct counting_binary_aggregate {
  int* calls;

  template <class Vec>
  void operator()(
      typename ::tsl::reg_param<Vec>::type,
      typename ::tsl::reg_param<Vec>::type) {
    ++*calls;
  }

  int finalize() const { return *calls; }
};

template <class T>
struct range_view {
  T* pointer;
  std::size_t count;

  T* data() const noexcept { return pointer; }
  std::size_t size() const noexcept { return count; }
};

int main() {
  using policy = ::tsl::dataparallel::fixed<1>;
  using alignment = ::tsl::algo::alignment::unaligned;
  std::vector<std::int32_t> input{1, 2, 3};
  std::vector<std::int32_t> right{4, 5, 6, 77};
  std::vector<std::int32_t> output{91, 92, 93, 94};
  std::vector<std::int32_t> short_output{81, 82};
  std::vector<std::int32_t> short_right{7, 8};
  int calls = 0;

  auto error = ::tsl::algo::transform_unary_checked<policy>(
      counting_unary{&calls}, input, short_output);
  if (error != ::tsl::precondition_error::insufficient_output || calls != 0 ||
      short_output != std::vector<std::int32_t>({81, 82})) {
    return 1;
  }

  error = ::tsl::algo::transform_binary_checked<policy>(
      counting_binary{&calls}, input, short_right, output);
  if (error != ::tsl::precondition_error::insufficient_input || calls != 0 ||
      output != std::vector<std::int32_t>({91, 92, 93, 94})) {
    return 2;
  }

  error = ::tsl::algo::transform_binary_checked<policy>(
      counting_binary{&calls}, input, right, short_output);
  if (error != ::tsl::precondition_error::insufficient_output || calls != 0 ||
      short_output != std::vector<std::int32_t>({81, 82})) {
    return 3;
  }

  error = ::tsl::algo::transform_binary_checked<policy>(
      counting_binary{&calls}, input, right, output);
  if (error != ::tsl::precondition_error::none || calls != 3 ||
      output != std::vector<std::int32_t>({1, 2, 3, 94})) {
    return 4;
  }

  std::int32_t overlap_storage[]{10, 11, 12, 13};
  range_view<const std::int32_t> overlap_input{overlap_storage, 3};
  range_view<std::int32_t> overlap_output{overlap_storage + 1, 3};
  calls = 0;
  error = ::tsl::algo::transform_unary_checked<policy>(
      counting_unary{&calls}, overlap_input, overlap_output);
  if (error != ::tsl::precondition_error::overlapping_ranges || calls != 0 ||
      overlap_storage[0] != 10 || overlap_storage[1] != 11 ||
      overlap_storage[2] != 12 || overlap_storage[3] != 13) {
    return 5;
  }

  calls = 0;
  ::tsl::algo::transform_unary<policy, alignment>(
      counting_unary{&calls}, input.data(), output.data(), input.size());
  if (calls != 3 || output != std::vector<std::int32_t>({1, 2, 3, 94})) {
    return 6;
  }

  calls = 0;
  error = ::tsl::algo::transform_unary_checked<policy>(
      counting_unary{&calls}, input, input);
  if (error != ::tsl::precondition_error::none || calls != 3 ||
      input != std::vector<std::int32_t>({1, 2, 3})) {
    return 7;
  }

  calls = 0;
  const auto count = ::tsl::algo::count_binary_checked<policy>(
      false_binary_predicate{&calls}, input, short_right, error);
  if (error != ::tsl::precondition_error::insufficient_input || count != 0 ||
      calls != 0) {
    return 8;
  }

  calls = 0;
  const auto aggregate = ::tsl::algo::aggregate_binary_checked<policy>(
      counting_binary_aggregate{&calls}, input, short_right, error);
  if (error != ::tsl::precondition_error::insufficient_input || aggregate != 0 ||
      calls != 0) {
    return 9;
  }

  const std::vector<std::size_t> indices{2, 0};
  std::vector<std::int32_t> selected_output{71, 72, 73};
  calls = 0;
  error = ::tsl::algo::transform_selected_unary_checked<1>(
      counting_unary{&calls}, input, indices, selected_output);
  if (error != ::tsl::precondition_error::none || calls != 2 ||
      selected_output != std::vector<std::int32_t>({3, 1, 73})) {
    return 10;
  }

  const std::vector<std::size_t> bad_indices{0, 3};
  selected_output.assign({71, 72, 73});
  calls = 0;
  error = ::tsl::algo::transform_selected_unary_checked<1>(
      counting_unary{&calls}, input, bad_indices, selected_output);
  if (error != ::tsl::precondition_error::index_out_of_bounds || calls != 0 ||
      selected_output != std::vector<std::int32_t>({71, 72, 73})) {
    return 11;
  }

  const std::vector<std::size_t> scaled_indices{0, 1};
  calls = 0;
  error = ::tsl::algo::transform_selected_unary_checked<1, 1>(
      counting_unary{&calls}, input, scaled_indices, selected_output);
  if (error != ::tsl::precondition_error::misaligned || calls != 0) {
    return 12;
  }

  const std::vector<std::size_t> overflowing_indices{
      (std::numeric_limits<std::size_t>::max)()};
  calls = 0;
  error = ::tsl::algo::transform_selected_unary_checked<
      1, static_cast<std::size_t>(0xffffffffu)>(
      counting_unary{&calls}, input, overflowing_indices, selected_output);
  if (error != ::tsl::precondition_error::address_overflow || calls != 0) {
    return 13;
  }
  return 0;
}
