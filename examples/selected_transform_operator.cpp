#include <cstddef>
#include <cstdint>
#include <vector>

#include <tsl.hpp>

struct square_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type value) const {
        return tsl::mul<Vec>(value, value);
    }
};

struct add_op {
    template <class Vec>
    typename Vec::register_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        return tsl::add<Vec>(left, right);
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 13) % 47) - 23);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 7) % 31) - 15);
    }
}

std::vector<std::size_t> make_selection(std::size_t count) {
    std::vector<std::size_t> indices;
    for (std::size_t i = count; i > 0; --i) {
        const std::size_t row = i - 1;
        if ((row % 3) == 0 || (row % 5) == 0) {
            indices.push_back(row);
        }
    }
    return indices;
}

template <std::size_t ParallelN, std::size_t Scale = 0>
bool run_selected_transform_pointer_case() {
    constexpr std::size_t count = 1003;
    constexpr std::int32_t sentinel = 7654321;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);

    std::vector<std::int32_t> output(count, sentinel);
    tsl::algo::transform_selected_unary<ParallelN, Scale>(
        square_op{},
        left.data(),
        indices.data(),
        output.data(),
        indices.size());
    for (std::size_t i = 0; i < indices.size(); ++i) {
        const auto value = left[indices[i]];
        if (output[i] != value * value) {
            return false;
        }
    }
    for (std::size_t i = indices.size(); i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }

    output.assign(count, sentinel);
    tsl::algo::transform_selected_binary<ParallelN, Scale>(
        add_op{},
        left.data(),
        right.data(),
        indices.data(),
        output.data(),
        indices.size());
    for (std::size_t i = 0; i < indices.size(); ++i) {
        const auto row = indices[i];
        if (output[i] != left[row] + right[row]) {
            return false;
        }
    }
    for (std::size_t i = indices.size(); i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }

    return true;
}

template <std::size_t ParallelN>
bool run_selected_transform_range_case() {
    constexpr std::size_t count = 257;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);

    std::vector<std::int32_t> output(indices.size());
    tsl::algo::transform_selected_binary<ParallelN>(
        add_op{},
        left,
        right,
        indices,
        output);
    for (std::size_t i = 0; i < indices.size(); ++i) {
        const auto row = indices[i];
        if (output[i] != left[row] + right[row]) {
            return false;
        }
    }
    return true;
}

template <std::size_t ParallelN>
bool run_selected_transform_cases() {
    return run_selected_transform_pointer_case<ParallelN>() &&
           run_selected_transform_range_case<ParallelN>();
}

int main() {
    if (!run_selected_transform_cases<1>()) {
        return 1;
    }
    if (!run_selected_transform_cases<4>()) {
        return 2;
    }
    if (!run_selected_transform_cases<8>()) {
        return 3;
    }
    if (!run_selected_transform_cases<16>()) {
        return 4;
    }
    if (!run_selected_transform_pointer_case<4, sizeof(std::int32_t)>()) {
        return 5;
    }
    return 0;
}
