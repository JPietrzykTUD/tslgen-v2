#include "intermediate_repr/kernel_templates.hpp"

namespace intermediate_repr {

#define IRBENCH_INSTANTIATE_MASK_CONSUMER_COUNT(POLICY, LAYOUT, COUNT)         \
  template consumed_batch consume_mask_batch<POLICY, LAYOUT, COUNT>(           \
      const std::int32_t *, const std::int32_t *, std::size_t, std::int32_t,   \
      scratch_view);

#define IRBENCH_INSTANTIATE_MASK_CONSUMER(POLICY, LAYOUT)                      \
  IRBENCH_INSTANTIATE_MASK_CONSUMER_COUNT(POLICY, LAYOUT, 1)                   \
  IRBENCH_INSTANTIATE_MASK_CONSUMER_COUNT(POLICY, LAYOUT, 4)                   \
  IRBENCH_INSTANTIATE_MASK_CONSUMER_COUNT(POLICY, LAYOUT, 8)

#define IRBENCH_INSTANTIATE_POSITION(POLICY, COUNT)                            \
  template consumed_batch consume_position_batch<POLICY, COUNT>(               \
      const std::int32_t *, const std::int32_t *, std::size_t, std::int32_t,   \
      scratch_view);

#define IRBENCH_INSTANTIATE_CONSUMER(POLICY)                                   \
  IRBENCH_FOR_EACH_MASK_LAYOUT(IRBENCH_INSTANTIATE_MASK_CONSUMER, POLICY)      \
  IRBENCH_INSTANTIATE_POSITION(POLICY, 1)                                      \
  IRBENCH_INSTANTIATE_POSITION(POLICY, 4)                                      \
  IRBENCH_INSTANTIATE_POSITION(POLICY, 8)

IRBENCH_FOR_EACH_POLICY(IRBENCH_INSTANTIATE_CONSUMER)

#undef IRBENCH_INSTANTIATE_CONSUMER
#undef IRBENCH_INSTANTIATE_POSITION
#undef IRBENCH_INSTANTIATE_MASK_CONSUMER_COUNT
#undef IRBENCH_INSTANTIATE_MASK_CONSUMER

} // namespace intermediate_repr
