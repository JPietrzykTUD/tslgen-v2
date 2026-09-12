// Profile-independent public core types. This is an implementation header;
// consumers include the stable `tsl_core.hpp` facade.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <type_traits>

// Loop-unroll hint for `loop<backend, unroll>`. A no-op by default (a real
// unroll pragma is compiler-specific and only a hint); kept as a macro so
// generated bodies always compile.
#ifndef TSL_UNROLL
#define TSL_UNROLL(n)
#endif

#ifndef TSL_FORCE_INLINE
#if defined(_MSC_VER)
#if defined(_DEBUG)
#define TSL_FORCE_INLINE inline
#else
#define TSL_FORCE_INLINE __forceinline
#endif
#elif defined(__GNUC__) || defined(__clang__)
#if defined(__OPTIMIZE__)
#define TSL_FORCE_INLINE inline __attribute__((always_inline))
#else
#define TSL_FORCE_INLINE inline
#endif
#else
#define TSL_FORCE_INLINE inline
#endif
#endif

namespace tsl {

/**
 * Coarse compiler-owned realization state for a selected specialization.
 *
 * `unknown` is the fail-closed result when typed evidence is incomplete. The
 * state describes implementation structure; it is not an instruction-count or
 * performance guarantee.
 */
@{core_declaration_implementation_state}

/** Error written or returned before a checked operation invokes its ordinary twin. */
@{core_declaration_precondition_error}

/**
 * A non-owning contiguous range used by checked memory APIs.
 *
 * Constructing a span does not validate its pointer. The caller must ensure
 * that a non-empty `data` denotes `size` live, addressable `T` objects for every
 * operation performed through the span and that the range remains valid for
 * the span's use. An empty span may carry a null pointer. Checked TSL operations
 * validate their own extent and selected alignment requirements after that
 * language-level range invariant has been established.
 */
@{core_declaration_span} {
 public:
@{core_span_alias_element_type};

@{core_span_constructor_pointer}
      : data_(data), size_(size) {}

@{core_span_constructor_array} : data_(data), size_(Size) {}

@{core_span_constructor_conversion}
      : data_(other.data()), size_(other.size()) {}

@{core_span_method_data} { return data_; }
@{core_span_method_size} { return size_; }

 private:
  T* data_;
  std::size_t size_;
};

/** Wraps an immediate value for implementation-state queries. */
template <auto Value>
struct value_arg {
    static constexpr auto value = Value;
};

/**
 * Compile-time implementation-state query; generated profiles specialize it.
 * An unsupported or unrecognized query remains `implementation_state::unknown`.
 */
template <class Primitive, class... Args>
struct implementation_state_of {
    static constexpr implementation_state value = implementation_state::unknown;
};

template <class Primitive, class... Args>
inline constexpr implementation_state implementation_state_v =
    implementation_state_of<Primitive, Args...>::value;

/**
 * Vector descriptor specialized by generated profiles.
 *
 * A specialization exposes its scalar, register, mask, integral-mask, lane,
 * and alignment types and constants. Register layout is backend-specific.
 */
@{core_declaration_simd};

/** Scalar extension tag, always available. */
struct scalar {};

/** One-lane scalar vector descriptor. */
template <class T>
struct simd<T, scalar> {
    using base_type = T;
    using extension_type = scalar;
    using register_type = T;
    using mask_type = bool;
    static constexpr bool mask_is_bitset = true;
    // Integral mask: a fixed unsigned scalar (to_integral packs the 0/1 mask into it).
    using imask_type = std::uint64_t;
    template <class ToBase>
    using with_base_type = simd<ToBase, scalar>;
    template <class ToExtension>
    using with_extension = simd<T, ToExtension>;
    static constexpr bool has_static_lane_count_v = true;
    static constexpr std::size_t lane_count_v = 1;
    static constexpr std::size_t vector_element_count = lane_count_v;
    static constexpr std::size_t lane_count() noexcept {
        return lane_count_v;
    }
    static constexpr std::size_t vector_alignment = alignof(T);
    static constexpr std::size_t simd_register_alignment_v = vector_alignment;
};

/** Parameter-passing type selected for a vector register. */
@{core_declaration_reg_param} {
@{core_reg_param_alias_type};
};

// A fixed-size, over-aligned array buffer (the `s[]` kind). Wraps std::array so
// `.data()`/`operator[]`/`.fill()` are uniform with the Rust counterpart; `Align`
// over-aligns the storage so an aligned store into it (via `assume_aligned`) is valid.
// `Align` defaults to the element alignment (the scalar case, length 1).
/** Fixed-size owned lane buffer with explicit storage alignment. */
@{core_declaration_array_type} {
@{core_array_field_storage};
@{core_array_method_data_mut} { return _storage.data(); }
@{core_array_method_data_const} { return _storage.data(); }
@{core_array_method_as_ptr} { return _storage.data(); }
@{core_array_method_as_mut_ptr} { return _storage.data(); }
@{core_array_method_index_mut} { return _storage[i]; }
@{core_array_method_index_const} { return _storage[i]; }
@{core_array_method_fill} { _storage.fill(value); }
};

// The array type a vector lowers to (to_array's owned result / from_array's read-only
// input): one element per lane, over-aligned to the register. Derived from the register/base
// sizes, so it matches the body's explicit `array_type<base, length, alignment>`.
template <class Vec>
struct array_for {
    // Element-aligned (not register-aligned) so the array type is identical across extensions
    // of the same (base, lane-count) — `to_array<A>`'s result is what `from_array<B>` accepts,
    // for the cross-extension delegation round-trip. The buffer is fed unaligned load/store.
    using type = array_type<typename Vec::base_type,
                            sizeof(typename Vec::register_type) / sizeof(typename Vec::base_type),
                            alignof(typename Vec::base_type)>;
};

template <class Vec>
struct array_param {
    using type = const typename array_for<Vec>::type &;
};

// The `generic` portable vector: a sized, array-backed register parameterized by its lane
// count. The tag carries `LANES` (a non-type template parameter), so `simd<T, generic<N>>`
// stays an ordinary two-argument specialization. Its register is an indexable `array_type`,
// so emulated bodies can `result[i] = ...` and delegate per lane to scalar. Always available
// (no hardware feature), hence defined here in the static core rather than per profile.
/** Portable array-backed extension tag with `LANES` logical lanes. */
template <std::size_t LANES>
struct generic {};

/** Portable array-backed vector descriptor. */
template <class T, std::size_t LANES>
struct simd<T, generic<LANES>> {
    // The generic vector models a portable register, so its total width must be a whole number of
    // 128-bit registers — the size ladder a size-changing primitive is monomorphized over. This
    // rejects a stray `generic<3>` / a 64-bit `generic<8>` of `int8_t` at instantiation.
    static_assert((LANES * sizeof(T)) % 16 == 0,
                  "tsl::generic<LANES>: LANES * sizeof(T) must be a multiple of 16 bytes (128 bits)");
    using base_type = T;
    using extension_type = generic<LANES>;
    using register_type = array_type<T, LANES>;
    // Emulated mask: a bitset, one bit per lane (≤64 lanes covers all real widths).
    using mask_type = std::uint64_t;
    static constexpr bool mask_is_bitset = true;
    // Integral mask: the same 64-bit bitset (LANES is a template param, so the lane count
    // can't size a smaller integer at this point).
    using imask_type = std::uint64_t;
    template <class ToBase>
    using with_base_type = simd<ToBase, generic<LANES>>;
    template <class ToExtension>
    using with_extension = simd<T, ToExtension>;
    static constexpr bool has_static_lane_count_v = true;
    static constexpr std::size_t lane_count_v = LANES;
    static constexpr std::size_t vector_element_count = lane_count_v;
    static constexpr std::size_t lane_count() noexcept {
        return lane_count_v;
    }
    static constexpr std::size_t vector_alignment = alignof(register_type);
    static constexpr std::size_t simd_register_alignment_v = vector_alignment;
};

template <class T, std::size_t LANES>
struct reg_param<simd<T, generic<LANES>>> {
    using type = const typename simd<T, generic<LANES>>::register_type &;
};


}  // namespace tsl
