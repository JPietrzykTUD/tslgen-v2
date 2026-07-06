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
    std::vector<std::int32_t>& input,
    std::vector<std::int32_t>& threshold) {
    for (std::size_t i = 0; i < input.size(); ++i) {
        input[i] = static_cast<std::int32_t>(static_cast<int>((i * 17) % 61) - 30);
        threshold[i] =
            static_cast<std::int32_t>(static_cast<int>((i * 11) % 43) - 21);
    }
}

template <class MaskLayout, class Parallelism>
bool run_masked_selection_case() {
    constexpr std::size_t count = 1003;
    constexpr std::int32_t sentinel = 7654321;
    std::vector<std::int32_t> input(count);
    std::vector<std::int32_t> threshold(count);
    std::vector<std::int32_t> output(count, sentinel);
    fill_inputs(input, threshold);

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
        input.data(),
        threshold.data(),
        masks.get(),
        count);
    if (masks_produced != mask_count) {
        return false;
    }

    const auto produced = tsl::algo::select_masked_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        negative_op{},
        input.data(),
        masks.get(),
        output.data(),
        count);

    std::size_t expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if ((input[i] < threshold[i]) && (input[i] < 0)) {
            if (output[expected_count] != input[i]) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (produced != expected_count) {
        return false;
    }
    for (std::size_t i = produced; i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }

    const auto unary_masks_produced = tsl::algo::predicate_unary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        negative_op{},
        input.data(),
        masks.get(),
        count);
    if (unary_masks_produced != mask_count) {
        return false;
    }

    output.assign(count, sentinel);
    const auto binary_produced = tsl::algo::select_masked_binary<
        Parallelism,
        tsl::algo::alignment::unaligned,
        MaskLayout>(
        less_than_op{},
        input.data(),
        threshold.data(),
        masks.get(),
        output.data(),
        count);

    expected_count = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if ((input[i] < 0) && (input[i] < threshold[i])) {
            if (output[expected_count] != input[i]) {
                return false;
            }
            expected_count += 1;
        }
    }
    if (binary_produced != expected_count) {
        return false;
    }
    for (std::size_t i = binary_produced; i < count; ++i) {
        if (output[i] != sentinel) {
            return false;
        }
    }
    return true;
}

template <class Parallelism>
bool run_layout_cases() {
    return run_masked_selection_case<
               tsl::algo::mask_layout::integral,
               Parallelism>() &&
           run_masked_selection_case<
               tsl::algo::mask_layout::native,
               Parallelism>() &&
           run_masked_selection_case<
               tsl::algo::mask_layout::bytes,
               Parallelism>() &&
           run_masked_selection_case<
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
