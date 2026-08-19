#include "pipcost/scalar_baseline.hpp"

namespace pipcost {

#if defined(__GNUC__) || defined(__clang__)
__attribute__((noinline))
#endif
PlanResult scalar_autovec(const QueryView& query, Scratch&) {
    return scalar_filter_sum(query);
}

}  // namespace pipcost

