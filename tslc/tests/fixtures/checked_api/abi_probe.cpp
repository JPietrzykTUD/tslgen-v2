#include <cstdint>
#include <immintrin.h>

#if defined(_MSC_VER)
#define TSL_ABI_NOINLINE __declspec(noinline)
#define TSL_ABI_FORCE_INLINE __forceinline
#else
#define TSL_ABI_NOINLINE __attribute__((noinline))
#define TSL_ABI_FORCE_INLINE __attribute__((always_inline)) inline
#endif

enum class precondition_error : std::uint8_t {
    none,
    rejected,
};

struct aggregate_result {
    __m256i value;
    precondition_error error;
};

extern "C" TSL_ABI_NOINLINE auto raw_return(__m256i value) noexcept -> __m256i {
    return _mm256_add_epi32(value, _mm256_set1_epi32(1));
}

extern "C" TSL_ABI_NOINLINE auto checked_return(
    __m256i value,
    precondition_error& error
) noexcept -> __m256i {
    error = precondition_error::none;
    return _mm256_add_epi32(value, _mm256_set1_epi32(1));
}

extern "C" TSL_ABI_NOINLINE auto aggregate_return(
    __m256i value
) noexcept -> aggregate_result {
    return {
        _mm256_add_epi32(value, _mm256_set1_epi32(1)),
        precondition_error::none,
    };
}

extern "C" TSL_ABI_NOINLINE auto status_with_value_output(
    __m256i value,
    __m256i& output
) noexcept -> precondition_error {
    output = _mm256_add_epi32(value, _mm256_set1_epi32(1));
    return precondition_error::none;
}

TSL_ABI_FORCE_INLINE auto checked_inline(
    __m256i value,
    precondition_error& error
) noexcept -> __m256i {
    error = precondition_error::none;
    return _mm256_add_epi32(value, _mm256_set1_epi32(1));
}

extern "C" auto consume_checked_inline(__m256i value) noexcept -> int {
    precondition_error error;
    const __m256i result = checked_inline(value, error);
    return _mm256_extract_epi32(result, 0) + static_cast<int>(error);
}
