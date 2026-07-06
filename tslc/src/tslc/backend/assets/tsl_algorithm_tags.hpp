#pragma once

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <utility>

namespace tsl::algo {

template <class Vec>
struct vector_tag {
    using type = Vec;
};

namespace alignment {
struct detect {};
struct unaligned {};
struct assume_aligned {};
struct assume_inputs_aligned {};
struct assume_output_aligned {};
struct peel_to_aligned {};
}  // namespace alignment

namespace mask_layout {
struct integral {};
struct native {};
struct bytes {};
struct bits {};
}  // namespace mask_layout

namespace parallelism {
struct native {};

template <std::size_t N>
struct fixed {
    static_assert(N > 0, "tsl::algo::parallelism::fixed<N> requires N > 0");
    static constexpr std::size_t lanes = N;
};
}  // namespace parallelism

}  // namespace tsl::algo
