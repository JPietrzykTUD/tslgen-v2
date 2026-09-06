#pragma once

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <utility>

namespace tsl::algo {

/** Adapt an explicit vector type for an algorithm parallelism parameter. */
template <class Vec>
struct vector_tag {
    using type = Vec;
};

namespace alignment {
/** Detect usable alignment at runtime without assuming an alignment promise. */
struct detect {};
/** Perform unaligned memory access. */
struct unaligned {};
/** Require every relevant range to satisfy the selected vector alignment. */
struct assume_aligned {};
/** Require input ranges to satisfy the selected vector alignment. */
struct assume_inputs_aligned {};
/** Require output ranges to satisfy the selected vector alignment. */
struct assume_output_aligned {};
/** Process a scalar prefix before using aligned vector accesses. */
struct peel_to_aligned {};
}  // namespace alignment

namespace mask_layout {
/** Store one packed integral mask word per vector chunk. */
struct integral {};
/** Store masks in the selected vector extension's native representation. */
struct native {};
/** Store one byte per logical input element. */
struct bytes {};
/** Store one packed bit per logical input element. */
struct bits {};
}  // namespace mask_layout

}  // namespace tsl::algo
