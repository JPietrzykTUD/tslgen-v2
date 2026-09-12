#include "tsl.hpp"

#include <cstdint>

using Vec = ::tsl::simd<std::int32_t, ::tsl::avx2>;

static_assert(::tsl::algo::detail::native_mask_can_represent_vec<Vec>());

int main() { return 0; }
