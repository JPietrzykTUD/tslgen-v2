#include <algorithm>
#include <array>
#include <bit>
#include <bitset>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <limits>
#include <ostream>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>
#include <immintrin.h>

#ifndef TSL_FORCE_INLINE
#define TSL_FORCE_INLINE inline
#endif

#ifndef TSL_UNROLL
#define TSL_UNROLL(x)
#endif

#ifndef VectorProcessingStyle
#define VectorProcessingStyle typename
#endif

namespace tsl {

struct scalar;
struct avx2;

template <typename T, typename Ext>
struct simd;

namespace detail {

template <typename Vec>
struct reg_param {
  using type = const typename Vec::register_type;
};

}  // namespace detail
}  // namespace tsl
