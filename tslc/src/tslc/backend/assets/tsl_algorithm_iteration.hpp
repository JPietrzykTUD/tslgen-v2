#pragma once

#include "tsl_algorithm_utility.hpp"
#include "tsl_algorithm_detail_iteration.hpp"

namespace tsl::algo {

@{algorithm_declaration_for_each_chunk_4}
    using value_type = typename std::remove_cv<T>::type;
    using vec = typename detail::vector_for_parallelism<Parallelism, value_type>::type;

    detail::validate_vector_for_parallelism<Parallelism, vec, value_type>();
    detail::for_each_chunk_loop<vec>(op, data, count);
}

@{algorithm_declaration_for_each_chunk_2}
    for_each_chunk<::tsl::dataparallel::fixed<ParallelN>>(
        std::forward<Op>(op), data, count);
}

@{algorithm_declaration_for_each_chunk_3}
    for_each_chunk<Parallelism>(
        std::forward<Op>(op),
        detail::range_data(data),
        detail::range_size(data));
}

@{algorithm_declaration_for_each_chunk_1}
    for_each_chunk<::tsl::dataparallel::fixed<ParallelN>>(std::forward<Op>(op), data);
}

}  // namespace tsl::algo
