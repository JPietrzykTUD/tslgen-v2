#pragma once

#include <cstddef>
#include <cstdint>
#include <iterator>
#include <type_traits>
#include <utility>

namespace tsl::algo {

/** Adapt an explicit vector type for an algorithm parallelism parameter. */
@{algorithm_declaration_vector_tag} {
@{algorithm_vector_tag_alias_type};
};

namespace alignment {
/** Detect usable alignment at runtime without assuming an alignment promise. */
@{algorithm_declaration_alignment_detect} {};
/** Perform unaligned memory access. */
@{algorithm_declaration_alignment_unaligned} {};
/** Require every relevant range to satisfy the selected vector alignment. */
@{algorithm_declaration_alignment_assume_aligned} {};
/** Require input ranges to satisfy the selected vector alignment. */
@{algorithm_declaration_alignment_assume_inputs_aligned} {};
/** Require output ranges to satisfy the selected vector alignment. */
@{algorithm_declaration_alignment_assume_output_aligned} {};
/** Process a scalar prefix before using aligned vector accesses. */
@{algorithm_declaration_alignment_peel_to_aligned} {};
}  // namespace alignment

namespace mask_layout {
/** Store one packed integral mask word per vector chunk. */
@{algorithm_declaration_mask_layout_integral} {};
/** Store masks in the selected vector extension's native representation. */
@{algorithm_declaration_mask_layout_native} {};
/** Store one byte per logical input element. */
@{algorithm_declaration_mask_layout_bytes} {};
/** Store one packed bit per logical input element. */
@{algorithm_declaration_mask_layout_bits} {};
}  // namespace mask_layout

}  // namespace tsl::algo
