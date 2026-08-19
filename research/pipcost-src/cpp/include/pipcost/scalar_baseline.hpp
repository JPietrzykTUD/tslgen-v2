#pragma once

#include "pipcost/query.hpp"

namespace pipcost {

inline PlanResult scalar_filter_sum(const QueryView& query) {
    std::int64_t total = 0;
    for (std::size_t row = 0; row < query.rows; ++row) {
        const std::int64_t active = static_cast<std::int64_t>(
            (query.a[row] < query.p1) & (query.b[row] > query.p2));
        total += active * static_cast<std::int64_t>(query.c[row]);
    }
    return PlanResult{total, 0};
}

}  // namespace pipcost
