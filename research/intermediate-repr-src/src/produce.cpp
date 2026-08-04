#include "intermediate_repr/kernel_templates.hpp"

namespace intermediate_repr {

#define IRBENCH_INSTANTIATE_MASK_PRODUCER(POLICY, LAYOUT)                 \
    template produced_batch produce_mask_batch<POLICY, LAYOUT>(          \
        const std::int32_t*, std::size_t, std::int32_t, scratch_view);

#define IRBENCH_INSTANTIATE_PRODUCER(POLICY)                              \
    IRBENCH_FOR_EACH_MASK_LAYOUT(IRBENCH_INSTANTIATE_MASK_PRODUCER, POLICY) \
    template produced_batch produce_position_batch<POLICY>(              \
        const std::int32_t*, std::size_t, std::int32_t, scratch_view);

IRBENCH_FOR_EACH_POLICY(IRBENCH_INSTANTIATE_PRODUCER)

#undef IRBENCH_INSTANTIATE_PRODUCER
#undef IRBENCH_INSTANTIATE_MASK_PRODUCER

}  // namespace intermediate_repr
