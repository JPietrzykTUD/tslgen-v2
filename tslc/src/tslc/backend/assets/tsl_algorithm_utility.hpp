#pragma once

#include "tsl_algorithm_detail_mask.hpp"

namespace tsl::algo {

@{algorithm_alias_vector_type}

@{algorithm_alias_integral_mask_type}

@{algorithm_alias_native_mask_type}

@{algorithm_alias_mask_storage_type}

@{algorithm_alias_byte_mask_type}

@{algorithm_alias_bit_mask_type}

@{algorithm_alias_fixed_integral_mask_type}

@{algorithm_alias_fixed_native_mask_type}

@{algorithm_alias_fixed_mask_storage_type}

@{algorithm_alias_fixed_byte_mask_type}

@{algorithm_alias_fixed_bit_mask_type}

@{algorithm_declaration_integral_mask_chunk_count_2}
    using vec = vector_type<Parallelism, T>;
    detail::validate_integral_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

@{algorithm_declaration_integral_mask_chunk_count_1}
    return integral_mask_chunk_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_native_mask_chunk_count_2}
    using vec = vector_type<Parallelism, T>;
    detail::validate_native_mask_layout<vec>();
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

@{algorithm_declaration_native_mask_chunk_count_1}
    return native_mask_chunk_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_mask_chunk_count_2}
    using vec = vector_type<Parallelism, T>;
    detail::validate_mask_layout<MaskLayout, vec>();
    if constexpr (std::is_same<MaskLayout, mask_layout::bytes>::value) {
        return count;
    } else if constexpr (std::is_same<MaskLayout, mask_layout::bits>::value) {
        return detail::packed_bit_mask_count(count);
    }
    const std::size_t lanes = detail::lane_count<vec>();
    return (count + lanes - 1) / lanes;
}

@{algorithm_declaration_mask_chunk_count_1}
    return mask_chunk_count<MaskLayout, ::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_byte_mask_count_2}
    return mask_chunk_count<mask_layout::bytes, Parallelism, T>(count);
}

@{algorithm_declaration_byte_mask_count_1}
    return byte_mask_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

@{algorithm_declaration_bit_mask_count_2}
    return mask_chunk_count<mask_layout::bits, Parallelism, T>(count);
}

@{algorithm_declaration_bit_mask_count_1}
    return bit_mask_count<::tsl::dataparallel::fixed<ParallelN>, T>(count);
}

}  // namespace tsl::algo
