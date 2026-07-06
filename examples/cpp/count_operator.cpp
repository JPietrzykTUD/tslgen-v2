#include <cstddef>
#include <cstdint>
#include <memory>
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

struct left_negative_binary_op {
    template <class Vec>
    typename Vec::mask_type operator()(
        typename tsl::reg_param<Vec>::type left,
        typename tsl::reg_param<Vec>::type right) const {
        (void)right;
        return tsl::less_than<Vec>(
            left,
            tsl::set1<Vec>(static_cast<typename Vec::base_type>(0)));
    }
};

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 23) % 71) - 35);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 13) % 53) - 26);
    }
}

template <class Predicate>
std::size_t expected_count(std::size_t count, Predicate predicate) {
    std::size_t produced = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (predicate(i)) {
            produced += 1;
        }
    }
    return produced;
}

std::vector<std::uint32_t> make_selection(std::size_t count) {
    std::vector<std::uint32_t> indices;
    for (std::size_t i = count; i > 0; --i) {
        const std::size_t row = i - 1;
        if ((row % 3) == 0 || (row % 11) == 0) {
            indices.push_back(static_cast<std::uint32_t>(row));
        }
    }
    return indices;
}

template <class Predicate>
std::size_t expected_selected_count(
    const std::vector<std::uint32_t>& indices,
    Predicate predicate) {
    std::size_t produced = 0;
    for (const auto row : indices) {
        if (predicate(static_cast<std::size_t>(row))) {
            produced += 1;
        }
    }
    return produced;
}

template <class Parallelism>
bool run_dense_count_cases() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    const auto unary = tsl::algo::count_unary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        left.data(),
        count);
    if (unary != expected_count(count, [&](std::size_t i) { return left[i] < 0; })) {
        return false;
    }

    const auto binary = tsl::algo::count_binary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        less_than_op{},
        left.data(),
        right.data(),
        count);
    if (binary !=
        expected_count(count, [&](std::size_t i) { return left[i] < right[i]; })) {
        return false;
    }

    const auto range_binary = tsl::algo::count_binary<Parallelism>(
        less_than_op{},
        left,
        right);
    return range_binary ==
           expected_count(count, [&](std::size_t i) { return left[i] < right[i]; });
}

template <class MaskLayout, class Parallelism>
bool run_masked_count_cases() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    using mask_type =
        tsl::algo::mask_storage_type<MaskLayout, Parallelism, std::int32_t>;
    const auto mask_count =
        tsl::algo::mask_chunk_count<MaskLayout, Parallelism, std::int32_t>(count);
    std::unique_ptr<mask_type[]> masks(new mask_type[mask_count]);

    const auto masks_produced = tsl::algo::predicate_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.get(),
        count);
    if (masks_produced != mask_count) {
        return false;
    }

    const auto unary = tsl::algo::count_masked_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        negative_op{},
        left.data(),
        masks.get(),
        count);
    if (unary != expected_count(
                     count,
                     [&](std::size_t i) {
                         return (left[i] < right[i]) && (left[i] < 0);
                     })) {
        return false;
    }

    const auto binary = tsl::algo::count_masked_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        left_negative_binary_op{},
        left.data(),
        right.data(),
        masks.get(),
        count);
    if (binary != expected_count(
                      count,
                      [&](std::size_t i) {
                          return (left[i] < right[i]) && (left[i] < 0);
                      })) {
        return false;
    }

    return true;
}

template <std::size_t ParallelN>
bool run_selected_count_cases() {
    constexpr std::size_t count = 1003;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);
    const auto indices = make_selection(count);

    const auto unary = tsl::algo::count_selected_unary<ParallelN>(
        negative_op{},
        left.data(),
        indices.data(),
        indices.size());
    if (unary !=
        expected_selected_count(indices, [&](std::size_t row) { return left[row] < 0; })) {
        return false;
    }

    const auto binary = tsl::algo::count_selected_binary<ParallelN>(
        less_than_op{},
        left.data(),
        right.data(),
        indices.data(),
        indices.size());
    if (binary != expected_selected_count(
                      indices,
                      [&](std::size_t row) { return left[row] < right[row]; })) {
        return false;
    }

    const auto range_binary = tsl::algo::count_selected_binary<ParallelN>(
        less_than_op{},
        left,
        right,
        indices);
    return range_binary == expected_selected_count(
                               indices,
                               [&](std::size_t row) {
                                   return left[row] < right[row];
                               });
}

template <class Parallelism, std::size_t SelectedN>
bool run_count_cases() {
    return run_dense_count_cases<Parallelism>() &&
           run_masked_count_cases<tsl::algo::mask_layout::integral, Parallelism>() &&
           run_masked_count_cases<tsl::algo::mask_layout::native, Parallelism>() &&
           run_masked_count_cases<tsl::algo::mask_layout::bytes, Parallelism>() &&
           run_masked_count_cases<tsl::algo::mask_layout::bits, Parallelism>() &&
           run_selected_count_cases<SelectedN>();
}

int main() {
    if (!run_count_cases<tsl::dataparallel::fixed<1>, 1>()) {
        return 1;
    }
    if (!run_count_cases<tsl::dataparallel::generic<4>, 4>()) {
        return 2;
    }
    if (!run_count_cases<tsl::dataparallel::generic<16>, 16>()) {
        return 3;
    }
    return 0;
}
