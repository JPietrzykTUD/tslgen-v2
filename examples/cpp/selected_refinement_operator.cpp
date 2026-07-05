#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct less_than_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::less_than<Vec>(left, right);
    }
};

struct negative_op {
    template <class Vec>
    typename Vec::mask_type operator()(typename tsl::reg_param<Vec>::type value) const {
        return tsl::less_than<Vec>(
            value,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 19) % 67) - 33);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 5) % 37) - 18);
    }
}

std::vector<std::uint32_t> make_selection(std::size_t count) {
    std::vector<std::uint32_t> indices;
    for (std::size_t i = count; i > 0; --i) {
        const std::size_t row = i - 1;
        if ((row % 2) == 0 || (row % 7) == 0) {
            indices.push_back(static_cast<std::uint32_t>(row));
        }
    }
    return indices;
}

template <class IndexT, class Predicate>
bool verify_refined_indices(
    const std::vector<std::uint32_t>& input_indices,
    const std::vector<IndexT>& output_indices,
    std::size_t produced,
    Predicate predicate) {
    constexpr IndexT sentinel = static_cast<IndexT>(999999);
    std::size_t expected_count = 0;
    for (const auto row : input_indices) {
        if (predicate(static_cast<std::size_t>(row))) {
            if (output_indices[expected_count] != static_cast<IndexT>(row)) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (produced != expected_count) {
        return false;
    }
    for (std::size_t i = produced; i < output_indices.size(); ++i) {
        if (output_indices[i] != sentinel) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_selected_refinement_pointer_case() {
    constexpr std::size_t count = 1003;
    constexpr std::uint32_t sentinel = 999999;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);

    std::vector<std::uint32_t> refined(indices.size(), sentinel);
    auto produced = tsl::algo::select_selected_indices_unary<ParallelN>(
        negative_op{},
        left.data(),
        indices.data(),
        refined.data(),
        indices.size());
    if (!verify_refined_indices(
            indices,
            refined,
            produced,
            [&](std::size_t row) { return left[row] < 0; })) {
        return false;
    }

    refined.assign(indices.size(), sentinel);
    produced = tsl::algo::select_selected_indices_binary<ParallelN>(
        less_than_op{},
        left.data(),
        right.data(),
        indices.data(),
        refined.data(),
        indices.size());
    if (!verify_refined_indices(
            indices,
            refined,
            produced,
            [&](std::size_t row) { return left[row] < right[row]; })) {
        return false;
    }

    return true;
}

template <std::size_t ParallelN>
bool run_selected_refinement_range_case() {
    constexpr std::size_t count = 257;
    constexpr std::uint32_t sentinel = 999999;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);

    std::vector<std::uint32_t> refined(indices.size(), sentinel);
    const auto produced = tsl::algo::select_selected_indices_binary<ParallelN>(
        less_than_op{},
        left,
        right,
        indices,
        refined);
    return verify_refined_indices(
        indices,
        refined,
        produced,
        [&](std::size_t row) { return left[row] < right[row]; });
}

template <std::size_t ParallelN>
bool run_selected_refinement_cases() {
    return run_selected_refinement_pointer_case<ParallelN>() &&
           run_selected_refinement_range_case<ParallelN>();
}

int main() {
    if (!run_selected_refinement_cases<1>()) {
        return 1;
    }
    if (!run_selected_refinement_cases<4>()) {
        return 2;
    }
    if (!run_selected_refinement_cases<16>()) {
        return 3;
    }
    return 0;
}
