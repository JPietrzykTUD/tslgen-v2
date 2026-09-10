// Memory and address runtime support for the stable `tsl_core.hpp` facade.
#pragma once

#include "tsl_core_detail_types.hpp"

#include <cstdlib>
#include <limits>
#include <type_traits>

#if defined(_MSC_VER)
#include <malloc.h>
#endif

namespace tsl {
namespace detail {

// Keep the allocation family paired on each C++ runtime. MSVC does not expose
// C11 aligned_alloc, and memory returned by _aligned_malloc must be released
// with _aligned_free. The public deallocate contract accepts only pointers
// returned by the TSL allocation family, so both Windows allocation paths use
// the matching aligned runtime. Reject invalid requests before either runtime
// can apply a platform-specific invalid-parameter policy, and round valid
// aligned sizes without changing the requested usable byte count.
inline void* mem_alloc(std::size_t count_bytes) {
    if (count_bytes == 0) {
        return nullptr;
    }
#if defined(_MSC_VER)
    return _aligned_malloc(count_bytes, alignof(std::max_align_t));
#else
    return std::malloc(count_bytes);
#endif
}

inline void* mem_alloc_aligned(
    std::size_t alignment,
    std::size_t count_bytes
) {
    if (count_bytes == 0 || alignment == 0 || (alignment & (alignment - 1)) != 0) {
        return nullptr;
    }
    const std::size_t minimum_alignment = alignof(void*);
    const std::size_t effective_alignment =
        alignment < minimum_alignment ? minimum_alignment : alignment;
    if (count_bytes >
        std::numeric_limits<std::size_t>::max() - (effective_alignment - 1)) {
        return nullptr;
    }
    const std::size_t allocation_size =
        ((count_bytes + effective_alignment - 1) / effective_alignment) *
        effective_alignment;
#if defined(_MSC_VER)
    return _aligned_malloc(allocation_size, effective_alignment);
#else
    return std::aligned_alloc(effective_alignment, allocation_size);
#endif
}

inline void mem_free(void* ptr) {
#if defined(_MSC_VER)
    _aligned_free(ptr);
#else
    std::free(ptr);
#endif
}

template <class Element, class Index>
inline precondition_error indexed_memory_address_error(
    Index raw_index,
    std::size_t scale,
    std::size_t extent) noexcept {
    using index_type = std::remove_cv_t<Index>;
    static_assert(std::is_integral_v<index_type>,
                  "checked indexed-memory indices must be integral");
    if constexpr (std::is_signed_v<index_type>) {
        if (raw_index < 0) {
            return precondition_error::index_out_of_bounds;
        }
    }
    constexpr auto max_size = (std::numeric_limits<std::size_t>::max)();
    using unsigned_index = std::make_unsigned_t<index_type>;
    const auto unsigned_raw = static_cast<unsigned_index>(raw_index);
    if constexpr (sizeof(unsigned_index) > sizeof(std::size_t)) {
        if (unsigned_raw > static_cast<unsigned_index>(max_size)) {
            return precondition_error::address_overflow;
        }
    }
    const auto index = static_cast<std::size_t>(unsigned_raw);
    if (scale != 0 && index > max_size / scale) {
        return precondition_error::address_overflow;
    }
    if (extent > max_size / sizeof(Element)) {
        return precondition_error::address_overflow;
    }
    const auto offset = index * scale;
    const auto bytes = extent * sizeof(Element);
    if (offset % alignof(Element) != 0) {
        return precondition_error::misaligned;
    }
    if (offset > bytes || sizeof(Element) > bytes - offset) {
        return precondition_error::index_out_of_bounds;
    }
    return precondition_error::none;
}

}  // namespace detail

// Aligned-pointer hint for aligned load/store. `__builtin_assume_aligned` (gcc/clang)
// keeps this C++17-compatible; it is only an optimizer hint, so a plain return is also
// correct if the builtin is unavailable.
template <std::size_t N, class T>
inline T *assume_aligned(T *ptr) noexcept {
#if defined(__GNUC__) || defined(__clang__)
    return static_cast<T *>(__builtin_assume_aligned(ptr, N));
#else
    return ptr;
#endif
}

// Pointer-offset helpers used by the generic vector's element-wise load/store loops.
template <class T>
inline T *ptr_add_mut(T *p, std::size_t i) {
    return p + i;
}
template <class T>
inline const T *ptr_add(const T *p, std::size_t i) {
    return p + i;
}

// The byte offset of a gather/scatter index: `index * scale` (scale in {1,2,4,8}). Used by the
// fallback loops over a byte-reinterpreted base pointer.
template <class Idx>
inline std::size_t idx_offset(Idx index, std::size_t scale) {
    return static_cast<std::size_t>(index) * scale;
}

}  // namespace tsl
