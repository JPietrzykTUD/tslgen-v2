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

void fill_inputs(
    std::vector<std::int32_t>& left,
    std::vector<std::int32_t>& right) {
    for (std::size_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 61) - 30);
        right[i] = static_cast<std::int32_t>(static_cast<int>((i * 11) % 43) - 21);
    }
}

template <class IndexT, class Predicate>
bool verify_indices(
    const std::vector<IndexT>& indices,
    std::size_t produced,
    std::size_t count,
    Predicate predicate) {
    constexpr IndexT sentinel = static_cast<IndexT>(999999);
    std::size_t expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (predicate(i)) {
            if (indices[expected_count] != static_cast<IndexT>(i)) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (produced != expected_count) {
        return false;
    }
    for (std::size_t i = produced; i < count; ++i) {
        if (indices[i] != sentinel) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_selection_vector_cases() {
    constexpr std::size_t count = 1003;
    constexpr std::uint32_t sentinel = 999999;
    std::vector<std::int32_t> left(count);
    std::vector<std::int32_t> right(count);
    fill_inputs(left, right);

    std::vector<std::uint32_t> indices(count, sentinel);
    auto produced = tsl::algo::select_indices_unary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        negative_op{},
        left.data(),
        indices.data(),
        count);
    if (!verify_indices(
            indices,
            produced,
            count,
            [&](std::size_t i) { return left[i] < 0; })) {
        return false;
    }

    indices.assign(count, sentinel);
    produced = tsl::algo::select_indices_binary<
        Parallelism,
        tsl::algo::alignment::unaligned>(
        less_than_op{},
        left.data(),
        right.data(),
        indices.data(),
        count);
    if (!verify_indices(
            indices,
            produced,
            count,
            [&](std::size_t i) { return left[i] < right[i]; })) {
        return false;
    }

    return true;
}

template <class MaskLayout, class Parallelism>
bool run_masked_selection_vector_cases() {
    constexpr std::size_t count = 1003;
    constexpr std::uint32_t sentinel = 999999;
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

    std::vector<std::uint32_t> indices(count, sentinel);
    auto produced = tsl::algo::select_masked_indices_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        negative_op{},
        left.data(),
        masks.get(),
        indices.data(),
        count);
    if (!verify_indices(
            indices,
            produced,
            count,
            [&](std::size_t i) { return (left[i] < right[i]) && (left[i] < 0); })) {
        return false;
    }

    indices.assign(count, sentinel);
    produced = tsl::algo::select_masked_indices_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        less_than_op{},
        left.data(),
        right.data(),
        masks.get(),
        indices.data(),
        count);
    if (!verify_indices(
            indices,
            produced,
            count,
            [&](std::size_t i) { return left[i] < right[i]; })) {
        return false;
    }

    return true;
}

template <class Parallelism>
bool run_layout_cases() {
    return run_selection_vector_cases<Parallelism>() &&
           run_masked_selection_vector_cases<
               tsl::algo::mask_layout::integral,
               Parallelism>() &&
           run_masked_selection_vector_cases<
               tsl::algo::mask_layout::native,
               Parallelism>() &&
           run_masked_selection_vector_cases<
               tsl::algo::mask_layout::bytes,
               Parallelism>() &&
           run_masked_selection_vector_cases<
               tsl::algo::mask_layout::bits,
               Parallelism>();
}

int main() {
    if (!run_layout_cases<tsl::dataparallel::fixed<1>>()) {
        return 1;
    }
    if (!run_layout_cases<tsl::dataparallel::generic<4>>()) {
        return 2;
    }
    if (!run_layout_cases<tsl::dataparallel::generic<16>>()) {
        return 3;
    }
    return 0;
}
