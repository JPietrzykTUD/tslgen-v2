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

template <VectorProcessingStyle Vec>
struct add_binary {
  using return_type = typename Vec::register_type;
  template <typename... Args>
  static return_type apply(Args&&...);
};

template <>
struct add_binary<simd<int32_t, scalar>> {
  using Vec = simd<int32_t, scalar>;
  using return_type = typename Vec::register_type;

  static constexpr bool has_return_value() {
    return true;
  }

  static constexpr bool native_supported() {
    return true;
  }

  [[nodiscard]]
  TSL_FORCE_INLINE
  static typename Vec::register_type apply(
      typename reg_param<Vec>::type left,
      typename reg_param<Vec>::type right
  ) {
    return left + right;
  }
};

template <>
struct add_binary<simd<uint32_t, scalar>> {
  using Vec = simd<uint32_t, scalar>;
  using return_type = typename Vec::register_type;

  static constexpr bool has_return_value() {
    return true;
  }

  static constexpr bool native_supported() {
    return true;
  }

  [[nodiscard]]
  TSL_FORCE_INLINE
  static typename Vec::register_type apply(
      typename reg_param<Vec>::type left,
      typename reg_param<Vec>::type right
  ) {
    return left + right;
  }
};

template <>
struct add_binary<simd<float, avx2>> {
  using Vec = simd<float, avx2>;
  using return_type = typename Vec::register_type;

  static constexpr bool has_return_value() {
    return true;
  }

  static constexpr bool native_supported() {
    return true;
  }

  [[nodiscard]]
  TSL_FORCE_INLINE
  static typename Vec::register_type apply(
      typename reg_param<Vec>::type left,
      typename reg_param<Vec>::type right
  ) {
    return _mm256_add_ps(left, right);
  }
};

}  // namespace detail

template <typename Vec>
TSL_FORCE_INLINE auto add(
    typename detail::reg_param<Vec>::type left,
    typename detail::reg_param<Vec>::type right
) -> decltype(::tsl::detail::add_binary<Vec>::apply(left, right)) {
  return ::tsl::detail::add_binary<Vec>::apply(left, right);
}
}  // namespace tsl
