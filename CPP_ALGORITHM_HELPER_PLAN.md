# C++ Algorithm Helper Plan

## Purpose

Capture the plan for a fixed C++ helper asset that makes the generated TSL
library easier to use for span-like data-parallel loops.

This is intentionally not a new `tslc` compiler stage. The compiler still reads
TSL source data and emits primitive wrappers/specializations. The helper is a
C++ header shipped with the generated C++ project that consumes the public
generated primitive API. Its required primitive roots are part of C++ generation
policy, not source data or TSIL semantics.

The plan is written from desired user outcome back toward integration so it can
be refined incrementally.

## Desired Outcome

A C++ user can write only the lane/register transformation logic and hand it to
a helper that owns the repetitive data-parallel loop shape:

1. Partition contiguous input into vector-width chunks.
2. Load a chunk through generated TSL primitives.
3. Invoke the user operation for the selected vector type.
4. Store the result through generated TSL primitives.
5. Process the remaining tail elements with the scalar TSL vector type.
6. Return nothing, an output range/container, or eventually a reduced scalar.

Initial outcome should be modest:

```cpp
struct square {
  template <class Vec>
  typename Vec::register_type operator()(
      typename tsl::reg_param<Vec>::type value) const {
    return tsl::mul<Vec>(value, value);
  }
};

tsl::algo::transform_unary<8>(square{}, input, output, count);
```

The helper deduces `T=float` from the pointer arguments and maps
`T=float, ParallelN=8` to the concrete generated SIMD vector type internally,
for example `tsl::simd<float, tsl::avx2>` in a profile where that is the
selected eight-lane float vector.

The first version should be useful for simple transform loops, not a complete
algorithm framework.

## Non-Goals

- Do not add TSIL syntax.
- Do not add catalog/source-data concepts.
- Do not change primitive selection, lowering, backend translation, or template
  rendering semantics beyond adding C++-only helper support roots for required
  public helper primitives.
- Do not add Rust support in the initial design.
- Do not require `std::span`; generated C++ currently targets C++17.
- Do not start with containers, allocation, runtime CPU dispatch, threading,
  strided views, gather/scatter, stencil/window operations, or broad execution
  policies.
- Do not make the user operation responsible for ordinary contiguous load/store
  in the basic transform helpers.

## Terminology

- **C++ backend**: the compiler backend that emits C++ artifacts.
- **Vector type / `Vec`**: generated-library execution type such as
  `tsl::simd<T, tsl::avx2>` or `tsl::simd<T, tsl::scalar>`.
- **`ParallelN`**: non-type template parameter naming the desired number of
  data elements processed per vector chunk. It is a lane count, not a byte or
  bit width.
- **Profile**: generated project profile selected by `TSL_PROFILE_*`.
- **Helper asset**: fixed C++ header copied into the generated C++ project.
- **Operation / `Op`**: user-supplied function object that performs register or
  scalar transformation logic.

Avoid calling `Vec` or `ParallelN` a backend in user-facing helper APIs. In
this repository, backend already means the generated language target (`cpp`,
`rust`).

## Core Design Boundary

The helper owns loop mechanics:

- iteration;
- vector chunk size;
- pointer arithmetic;
- generated primitive calls for load/store;
- tail handling;
- optional alignment policy;
- future mask construction for tail-valid lanes;
- future reduction orchestration.

The operation owns value logic:

- transform a register into a register;
- combine registers for binary transforms;
- eventually combine accumulators for reductions;
- optionally receive a mask only in explicit masked helper families.

The default operation must not see pointers, spans, or containers. Once `Op`
does its own memory access, the helper can no longer reliably own alignment,
tail behavior, output layout, or element coverage.

## Public API Shape

Prefer public free functions under `tsl::algo`.

Rationale:

- Users want to perform an algorithm, not manage an executor object.
- Free functions keep the generated library approachable.
- Public structs invite premature questions about lifetime, stored spans,
  reusable executors, dispatch state, and policy objects.
- Internal `detail` structs are acceptable if they simplify implementation.

Candidate namespace and header:

```cpp
#include <tsl.hpp>

namespace tsl::algo {

template <class Vec>
struct vector_tag {
  using type = Vec;
};

namespace alignment {
struct detect {};
struct unaligned {};
struct assume_aligned {};
struct assume_inputs_aligned {};
struct assume_output_aligned {};
struct peel_to_aligned {};
}  // namespace alignment

namespace parallelism {
struct native {};
template <std::size_t N> struct fixed {};
}  // namespace parallelism

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
void transform_unary(
    Op&& op,
    T const* input,
    T* output,
    std::size_t count);

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
void transform_unary(
    Op&& op,
    T const* input,
    T* output,
    std::size_t count);

template <
    class Parallelism = parallelism::native,
    class Alignment = alignment::detect,
    class Op,
    class T>
void transform_binary(
    Op&& op,
    T const* left,
    T const* right,
    T* output,
    std::size_t count);

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
void transform_binary(
    Op&& op,
    T const* left,
    T const* right,
    T* output,
    std::size_t count);

}  // namespace tsl::algo
```

`Op` appears first in the function argument list so the call reads as "apply
this operation to these ranges." `T` is deduced from the pointer arguments and
`Op` is deduced from the callable argument. `Op&&` is a forwarding reference
here: lvalue operations are referenced, and rvalue operations are bound for the
duration of the algorithm call without an extra copy.

```cpp
tsl::algo::transform_unary(op, input, output, count);    // native profile width
tsl::algo::transform_unary<8>(op, input, output, count);
```

Alignment is a type-dispatch template parameter rather than a boolean. This
makes the opt-in call site read like a contract, while keeping `Op` and `T`
deduced:

```cpp
tsl::algo::transform_unary<8>(op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::unaligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_inputs_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_output_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::peel_to_aligned>(
    op, input, output, count);
```

The direct `ParallelN` overload is the user-facing exact-lane spelling. It
forwards to the policy form `parallelism::fixed<ParallelN>`. The policy form
also permits a no-template-argument default that maps to
`parallelism::native`.

Use `class Alignment = alignment::detect` for the template parameter name, not
`class aligned = alignment::unaligned`, so the parameter does not shadow or
confuse the policy tag types.

The public API is intentionally not templated on `Vec`. The helper derives a
concrete vector type from `T` and `ParallelN`, then calls the user operation with
that internal `Vec`:

```cpp
using vec =
    tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<ParallelN>, T>;
```

In the current generated C++ support code, the public alias is
`tsl::dataparallel::simd_for_t<Policy, T>`, backed by profile-specialized
`tsl::dataparallel::simd_for<Policy, T>`.

## Vector Inference Contract

`T` and `ParallelN` define the public data-parallel shape. The generated library
already turns that shape into the selected vector type:

```cpp
using vec =
    tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<ParallelN>, T>;
```

Inference constraints:

- `ParallelN > 0`.
- The resulting `Vec::base_type` must be `T`.
- The resulting static lane count must equal `ParallelN`, unless a future policy
  explicitly allows a different implementation width.
- `ParallelN == 1` should map to `tsl::simd<T, tsl::scalar>`.
- Non-scalar `ParallelN` should map to an extension struct available in the
  selected generated C++ profile when a profile-specific specialization exists.
- Otherwise non-scalar `ParallelN` should fall back to
  `tsl::simd<T, tsl::generic<ParallelN>>`. That fallback is still subject to the
  generic-vector width invariant, currently `ParallelN * sizeof(T)` being a
  multiple of 16 bytes.

This removes the largest mapping burden from the algorithm helper. The helper
should not duplicate profile-selection rules already expressed by
`tsl::dataparallel::simd_for_t`.

## Operation Invocation Contract

`Op` should not be limited to a functor with a templated call operator. The
helper should invoke operations through a small C++17 detection adapter:

1. Prefer `op.template operator()<Vec>(value)` when available.
2. Else use `op(tsl::algo::vector_tag<Vec>{}, value)` when available.
3. Else use `op(value)` when available.
4. Otherwise fail with a focused `static_assert`.

This keeps the high-control functor form:

```cpp
struct square {
  template <class Vec>
  typename Vec::register_type operator()(
      typename tsl::reg_param<Vec>::type value) const {
    return tsl::mul<Vec>(value, value);
  }
};
```

It also gives C++17 users a lambda-friendly form that still has access to
`Vec`:

```cpp
auto square = [](auto tag, auto value) {
  using Vec = typename decltype(tag)::type;
  return tsl::mul<Vec>(value, value);
};
```

And it permits plain callables for operations that do not need the vector type:

```cpp
auto negate = [](auto value) {
  return -value;
};
```

Sketch:

```cpp
namespace detail {

template <class...>
struct always_false : std::false_type {};

template <class Op, class Vec, class Arg, class = void>
struct can_call_typed : std::false_type {};

template <class Op, class Vec, class Arg>
struct can_call_typed<
    Op,
    Vec,
    Arg,
    std::void_t<decltype(
        std::declval<Op&>().template operator()<Vec>(std::declval<Arg>()))>>
    : std::true_type {};

template <class Op, class Vec, class Arg, class = void>
struct can_call_tagged : std::false_type {};

template <class Op, class Vec, class Arg>
struct can_call_tagged<
    Op,
    Vec,
    Arg,
    std::void_t<decltype(
        std::declval<Op&>()(vector_tag<Vec>{}, std::declval<Arg>()))>>
    : std::true_type {};

template <class Op, class Arg, class = void>
struct can_call_plain : std::false_type {};

template <class Op, class Arg>
struct can_call_plain<
    Op,
    Arg,
    std::void_t<decltype(std::declval<Op&>()(std::declval<Arg>()))>>
    : std::true_type {};

template <class Vec, class Op, class Arg>
decltype(auto) invoke_op(Op& op, Arg&& arg) {
  if constexpr (can_call_typed<Op, Vec, Arg&&>::value) {
    return op.template operator()<Vec>(std::forward<Arg>(arg));
  } else if constexpr (can_call_tagged<Op, Vec, Arg&&>::value) {
    return op(vector_tag<Vec>{}, std::forward<Arg>(arg));
  } else if constexpr (can_call_plain<Op, Arg&&>::value) {
    return op(std::forward<Arg>(arg));
  } else {
    static_assert(
        always_false<Op, Vec, Arg>::value,
        "Op must be callable as op.template operator()<Vec>(value), "
        "op(tsl::algo::vector_tag<Vec>{}, value), or op(value)");
  }
}

}  // namespace detail
```

The operation result must be store-compatible with the active `Vec`.

The public algorithm should accept `Op&&` and pass the named callable to detail
loops as `Op&`. The helper calls the operation many times and must not move from
it inside the loop. This avoids copying large or stateful callables while keeping
temporaries alive for the duration of the algorithm call.

## Unmasked Transform Contract

For `transform_unary<ParallelN, Alignment>`:

- `input` points to at least `count` readable elements.
- `output` points to at least `count` writable elements.
- `T` is deduced from the pointer arguments and is the element type.
- Full chunks use `Vec`.
- `Vec` is derived from `T` and `ParallelN`.
- Tail elements use `tsl::simd<T, tsl::scalar>`.
- `Op` must be invocable for both vector and scalar forms through the operation
  invocation adapter unless a separate scalar operation is supplied.
- `Alignment` must be `tsl::algo::alignment::detect`,
  `tsl::algo::alignment::unaligned`,
  `tsl::algo::alignment::assume_aligned`, or
  `tsl::algo::alignment::assume_inputs_aligned`,
  `tsl::algo::alignment::assume_output_aligned`, or
  `tsl::algo::alignment::peel_to_aligned` for dense transform helpers.
- `alignment::detect` is the public default. It checks the input and output start
  addresses once, then dispatches to a detail loop with independent static
  load/store alignment tags.
- `alignment::unaligned` forces unaligned load/store.
- `alignment::assume_aligned` is an all-operands-aligned caller promise.
- `alignment::assume_inputs_aligned` promises dense transform input loads are
  aligned, but makes no alignment promise for the output store. For binary
  transforms, both left and right input columns are promised aligned.
- `alignment::assume_output_aligned` promises the dense transform output store
  is aligned, but makes no alignment promise for input loads.
- `alignment::peel_to_aligned` is an explicit scalar-prologue policy for dense
  transforms. It uses aligned vector load/store only when all operands can
  become aligned at the same element index; otherwise it falls back to the
  unaligned vector loop.

Sketch:

```cpp
namespace detail {

template <class Vec, class Ptr>
bool is_aligned_for(Ptr ptr) noexcept {
  auto const address = reinterpret_cast<std::uintptr_t>(ptr);
  return (address % Vec::vector_alignment) == 0;
}

template <
    class Vec,
    class InputAlignment,
    class OutputAlignment,
    class Op,
    class T>
void transform_unary_loop(Op& op, T const* input, T* output, std::size_t count) {
  using scalar_vec = tsl::simd<T, tsl::scalar>;
  constexpr bool input_aligned =
      std::is_same<InputAlignment, tsl::algo::alignment::assume_aligned>::value;
  constexpr bool output_aligned =
      std::is_same<OutputAlignment, tsl::algo::alignment::assume_aligned>::value;

  constexpr std::size_t lanes = Vec::vector_element_count;
  std::size_t const chunk_count = count / lanes;
  std::size_t i = 0;
  for (std::size_t chunk = 0; chunk < chunk_count; ++chunk, i += lanes) {
    auto x = tsl::load<Vec, input_aligned>(input + i);
    auto y = detail::invoke_op<Vec>(op, x);
    tsl::store<Vec, output_aligned>(output + i, y);
  }
  for (; i < count; ++i) {
    auto x = tsl::load<scalar_vec, false>(input + i);
    auto y = detail::invoke_op<scalar_vec>(op, x);
    tsl::store<scalar_vec, false>(output + i, y);
  }
}

}  // namespace detail

template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class Op,
    class T>
void transform_unary(Op&& op, T const* input, T* output, std::size_t count) {
  using vec =
      tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<ParallelN>, T>;

  static_assert(ParallelN > 0, "ParallelN must be greater than zero");
  static_assert(
      detail::is_supported_transform_alignment_policy<Alignment>::value,
      "Alignment must be tsl::algo::alignment::detect, unaligned, "
      "assume_aligned, or peel_to_aligned");
  static_assert(
      std::is_same<T, typename vec::base_type>::value,
      "dataparallel fixed mapping must preserve T as Vec::base_type");
  static_assert(
      vec::vector_element_count == ParallelN,
      "dataparallel fixed mapping must produce exactly ParallelN lanes");

  if constexpr (std::is_same<Alignment, alignment::detect>::value) {
    bool const input_aligned = detail::is_aligned_for<vec>(input);
    bool const output_aligned = detail::is_aligned_for<vec>(output);
    if (input_aligned && output_aligned) {
      detail::transform_unary_loop<
          vec,
          alignment::assume_aligned,
          alignment::assume_aligned>(op, input, output, count);
      return;
    }
    if (input_aligned) {
      detail::transform_unary_loop<
          vec,
          alignment::assume_aligned,
          alignment::unaligned>(op, input, output, count);
      return;
    }
    if (output_aligned) {
      detail::transform_unary_loop<
          vec,
          alignment::unaligned,
          alignment::assume_aligned>(op, input, output, count);
      return;
    }
    detail::transform_unary_loop<
        vec,
        alignment::unaligned,
        alignment::unaligned>(op, input, output, count);
  } else if constexpr (std::is_same<Alignment, alignment::assume_aligned>::value) {
    detail::transform_unary_loop<
        vec,
        alignment::assume_aligned,
        alignment::assume_aligned>(op, input, output, count);
  } else if constexpr (std::is_same<Alignment, alignment::peel_to_aligned>::value) {
    detail::transform_unary_loop_peel_to_aligned<vec>(op, input, output, count);
  } else {
    detail::transform_unary_loop<
        vec,
        alignment::unaligned,
        alignment::unaligned>(op, input, output, count);
  }
}
```

The actual implementation needs `<type_traits>` and `<utility>` for operation
dispatch helpers, and may need small type helpers to handle generated
`reg_param<Vec>` conventions cleanly. It also needs `<cstdint>` for
`std::uintptr_t`; pointer-to-integer conversion must use
`reinterpret_cast<std::uintptr_t>(ptr)`, not `static_cast<std::size_t>(ptr)`.

## Alignment Policy

Default helper behavior should use runtime alignment inference through
`Alignment = alignment::detect`.

Rationale:

- Plain pointers and most container `.data()` values do not carry a reliable
  vector-alignment proof.
- Runtime address checks can safely choose between aligned and unaligned
  generated load/store primitives for the current call.
- The branch cost is paid once before the vector loop, not inside the hot loop.
- An incorrect aligned load/store promise can be undefined behavior or a hard
  target fault, depending on the generated primitive and hardware.
- The safe default should still work for ordinary contiguous memory without
  requiring custom allocators.

The first API should use tag types:

```cpp
tsl::algo::transform_unary<8>(op, input, output, count); // alignment::detect
tsl::algo::transform_unary<8, tsl::algo::alignment::unaligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_inputs_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::assume_output_aligned>(
    op, input, output, count);
tsl::algo::transform_unary<8, tsl::algo::alignment::peel_to_aligned>(
    op, input, output, count);
```

Contract for `Alignment = tsl::algo::alignment::detect`:

- The helper checks `input` and `output` against the alignment required by the
  derived `Vec`.
- Unary transform dispatches to one of four detail loops:
  `assume_aligned/assume_aligned`, `assume_aligned/unaligned`,
  `unaligned/assume_aligned`, or `unaligned/unaligned`.
- The detail loop has static load/store alignment booleans, so generated
  primitive calls stay compile-time-selected.
- The check uses the generated `Vec::vector_alignment` static data
  member, the same vector alignment concept used by generated aligned
  load/store.
- An implementation may skip runtime alignment checks when `count` contains no
  full vector chunk, because only scalar tail handling can run.
- This is not scalar-prologue peeling. It only detects whether the current start
  addresses are already aligned.

Contract for `Alignment = tsl::algo::alignment::unaligned`:

- The helper uses unaligned load/store for all memory operands.
- The helper performs no runtime alignment checks.
- This is the predictable baseline for tiny ranges or callers that do not want
  dispatch branches.

Contract for `Alignment = tsl::algo::alignment::assume_aligned`:

- `input` is aligned to the alignment required by the derived `Vec`.
- `output` is aligned to the alignment required by the derived `Vec`.
- Every vector chunk address remains aligned because chunks advance by
  `ParallelN * sizeof(T)` bytes.
- The caller owns the proof; the helper does not dynamically repair a bad
  promise.

Contract for `Alignment = tsl::algo::alignment::assume_inputs_aligned`:

- Dense transform input pointers are aligned to the alignment required by the
  derived `Vec`.
- Unary transform uses aligned input loads and unaligned output stores.
- Binary transform uses aligned loads for both input columns and unaligned
  output stores.
- The caller owns the proof; use `alignment::detect` when only some binary
  input operands are known aligned.

Contract for `Alignment = tsl::algo::alignment::assume_output_aligned`:

- Dense transform output is aligned to the alignment required by the derived
  `Vec`.
- Input loads use the unaligned load path.
- The caller owns the proof; the helper does not dynamically repair a bad
  promise.

Contract for `Alignment = tsl::algo::alignment::peel_to_aligned`:

- This policy is accepted by dense `transform_unary` and `transform_binary`
  only. Other helper families continue to accept only `detect`, `unaligned`,
  and `assume_aligned` until they get their own explicit peeling contract.
- The helper compares the operands' addresses modulo `Vec::vector_alignment`.
- If all operands have the same residue, scalar iterations run until the first
  vector address is aligned, then the aligned vector loop handles full chunks
  and the existing scalar tail handles the final remainder.
- If operands have incompatible residues, the helper falls back to the
  unaligned vector loop for the whole range.

This means the public `assume_aligned` tag denotes "all memory operands are
aligned." Common mixed input/output alignment can use
`assume_inputs_aligned` or `assume_output_aligned` without exposing separate
public input/output template parameters. Binary callers with only one aligned
input should use `alignment::detect` or `alignment::unaligned`.

Binary transform has the same principle, but the default runtime dispatch has
three memory operands (`left`, `right`, `output`) and therefore eight static
alignment combinations. The implementation should avoid hand-written branching
ladders if a small helper can keep that readable.

A three-phase "peel to alignment" loop is now available for dense transform
helpers through `alignment::peel_to_aligned`:

1. Run scalar iterations until the vector loop address is aligned.
2. Run the vector loop with aligned load/store.
3. Run scalar iterations for the final remainder.

This is not the default contract. It is only safe when all memory
operands can become aligned at the same element index. For unary transform that
means `input + i` and `output + i` must both satisfy the derived `Vec`
alignment after the same scalar prologue length. If the input and output
addresses have incompatible alignment offsets, no scalar prologue can make both
the load and store aligned. Binary transform tightens this further because
`left + i`, `right + i`, and `output + i` must converge together.

The implementation keeps peeling as an explicit policy and falls back to the
unaligned vector loop when operands cannot be jointly aligned. It should not
silently turn an unsafe aligned access into a guessed optimization.

## Masked Transform Contract

Masked helpers should be a separate API family, not a parameter bolted onto the
default transform.

There are multiple meanings of "mask":

- tail-validity mask: lanes in the final partial vector that correspond to real
  elements;
- user/data mask: caller-provided predicate that controls which elements are
  updated;
- algorithm mask: a predicate produced by the operation itself.

Those meanings must not be collapsed.

Candidate masked transform contract:

```cpp
template <
    std::size_t ParallelN,
    class Alignment = alignment::detect,
    class MaskLayout = mask_layout::integral,
    class Op,
    class T,
    class MaskStorage>
void transform_masked_unary(
    Op&& op,
    T const* input,
    MaskStorage const* masks,
    T* output,
    std::size_t count);
```

The helper derives the concrete `Vec` from `T` and `ParallelN`, then loads or
combines any per-chunk active mask internally. Mask-consuming helper families
take explicit mask storage plus a `mask_layout` policy, while still avoiding
`Vec` in the public template parameter list.

Candidate operation shape:

```cpp
struct op {
  template <class Vec>
  typename Vec::register_type operator()(
      typename Vec::mask_type active,
      typename tsl::reg_param<Vec>::type value) const;
};
```

Contract:

- `active` means lanes the operation is allowed to affect.
- Helper owns mask loading and the selected output policy.
- Inactive result lanes are don't-care only if the helper performs masked store.
- Aggregation and consume operations cannot treat inactive lanes as don't-care;
  the operation must neutralize or ignore inactive lanes before updating state.
- Where transforms preserve inactive output lanes with masked store.
- Masked full-store transforms write every output lane, so the operation must
  supply meaningful inactive-lane values.

## Reduction Contract

The implemented aggregation helpers use a stateful operation contract rather
than a helper-owned reducer:

```cpp
struct sum_op {
  std::int64_t total = 0;

  template <class Vec>
  void operator()(typename tsl::reg_param<Vec>::type value);

  std::int64_t finalize() const;
};
```

The helper calls the operation once per vector chunk and once per scalar tail
element, then returns `op.finalize()`. Empty input is therefore defined by the
operation's initial state and finalizer.

This deliberately leaves the following choices with the operation:

- Reduction changes observable behavior for floating-point unless the user opts
  into relaxed associativity.
- Integer overflow, signed overflow, NaN handling, identity values, and empty
  ranges need explicit contracts.
- Tail lanes need neutral values, not don't-care values.
- A vector accumulator often needs a final horizontal reduction primitive.

Possible future helper-owned reducers remain separate features:

```cpp
tsl::algo::reduce<ParallelN>(input, count, init, reduce_op);
tsl::algo::transform_reduce<ParallelN>(input, count, init, transform_op, reduce_op);
```

## Rust Applicability

Rust support remains out of scope for the first slice, but the C++ design gives
useful guidance.

Avoiding operation copies is possible in Rust, but the model is different:

```rust
pub fn transform_unary<T, const PARALLEL_N: usize, F>(
    op: &mut F,
    input: *const T,
    output: *mut T,
    count: usize,
)
where
    F: /* operation trait or FnMut shape */,
{
    // helper calls op repeatedly by mutable reference
}
```

Taking `op: F` by value would move the closure/functor into the helper, not
clone it. That is often fine and matches Rust iterator style, but `&mut F`
allows callers to reuse a stateful operation after the transform and avoids even
moving a large operation object.

The harder part is the operation contract. Rust closures cannot express "generic
over `Vec`" in the same ergonomic way as the C++ `vector_tag<Vec>` lambda form.
A Rust version likely needs one of these shapes:

1. A trait with a generic method, implemented by a user struct:

   ```rust
   trait UnaryOp {
       fn apply<Vec>(&mut self, value: <Vec as SimdVector>::Register)
           -> <Vec as SimdVector>::Register
       where
           Vec: SimdVector;
   }
   ```

2. Separate vector and scalar callables, because each callable is monomorphic.
3. A lower-level chunk helper where advanced users write the vector-specific
   loop body directly.

So the same ownership idea is possible in Rust, but the same callable ergonomics
are not. Rust should be designed as its own helper API later instead of copied
from the C++ surface.

## Asset Integration

Candidate fixed assets:

```text
tslc/src/tslc/backend/assets/tsl_algorithm.hpp
tslc/src/tslc/backend/assets/tsl_algorithm_tags.hpp
tslc/src/tslc/backend/assets/tsl_algorithm_detail_core.hpp
tslc/src/tslc/backend/assets/tsl_algorithm_detail_mask.hpp
tslc/src/tslc/backend/assets/tsl_algorithm_detail_loops.hpp
```

Generated output:

```text
cpp/include/tsl_algorithm.hpp
cpp/include/tsl_algorithm_tags.hpp
cpp/include/tsl_algorithm_detail_core.hpp
cpp/include/tsl_algorithm_detail_mask.hpp
cpp/include/tsl_algorithm_detail_loops.hpp
```

Likely include strategy:

- Copy the algorithm helper header bundle as static C++ assets alongside
  `tsl_core.hpp`.
- Keep `tsl_algorithm.hpp` as the public umbrella. Internal helper headers are
  implementation-detail assets used to keep policy tags, core detail plumbing,
  mask storage mechanics, and loop bodies owned by separate files.
- Include it from generated `cpp/include/tsl.hpp` after the selected profile
  header has been included, because the helper consumes generated primitive
  wrappers.
- Treat inclusion from `tsl.hpp` as the final integration model. Users should not
  need to remember a separate algorithm-helper include once the asset is
  integrated.

Important integration risks:

1. `tsl.hpp` include order must declare core `simd`, `tsl::dataparallel`, the
   selected profile types, and required primitive wrappers before
   `tsl_algorithm.hpp`.
2. Unsupported `(T, ParallelN)` combinations should fail with a clear
   substitution/static-assert diagnostic from native profile inference or the
   generic-vector fallback.
3. Because `tsl_algorithm.hpp` names generated wrappers such as `tsl::load` and
   `tsl::store` in template bodies, a generated project that includes the helper
   from `tsl.hpp` should also emit those helper-owned primitive wrappers.
4. Primitives named only by the user operation, such as `tsl::mul`, remain
   ordinary user dependencies; failures there happen when the operation is
   instantiated.

Decision:

- C++ generation treats the generated wrappers `load`, `store`, `store_mask`,
  `to_integral`, `to_mask`, `gather_narrow`, `compress_store`,
  `mask_population_count`, and `mask_binary_and` as the helper support surface
  whenever the C++ backend is requested. `store_mask` is emitted by selecting
  the `store` source primitive and splitting its pass-through masked form during
  C++ emitted-name finalization; it is not a separate source primitive name.
- Those roots are lowered only for the C++ backend; Rust generation should not
  inherit them merely because the C++ helper exists.
- The C++ renderer copies the algorithm helper header bundle as static assets
  and includes `tsl_algorithm.hpp` from `tsl.hpp` only when every rendered C++
  profile contains the required `load`, `store`, `store_mask`, `to_integral`,
  `to_mask`, `gather_narrow`, `compress_store`, `mask_population_count`, and
  `mask_binary_and` wrappers.
- Forward declarations in the helper are intentionally avoided. The public
  dispatch header should expose `tsl::algo` only when the generated primitive API
  it uses is actually present.
- Predicate count helpers use the existing support-root set: dense count needs
  `mask_population_count` and scalar-tail `to_integral`, while masked count
  additionally uses `mask_binary_and` to combine input activity with the
  operation predicate.
- Selection-vector inputs and outputs use unsigned integral row-id element
  types. `std::size_t` is the canonical row-id spelling; `std::uint32_t` is
  accepted for compact row-id streams. Signed integers and `bool` are rejected
  because casting negative row ids to byte offsets is never a meaningful helper
  contract.
- Selected-row consumers use `gather_narrow` for pointer-backed 32-bit and
  64-bit row-id streams. `Scale == 0` means `sizeof(T)`, preserving the default
  element-index contract; an explicit `Scale` is a byte scale passed through to
  the generated gather primitive. Narrower unsigned integral row-id types remain
  a portable generic fallback case.

Vector selection stays delegated to `tsl::dataparallel::simd_for_t`.

## First Implementation Slice

Goal:

Ship a fixed C++ asset with dense `transform_unary` and `transform_binary`
helpers for contiguous pointer ranges.

Scope:

- Add `tsl_algorithm.hpp` fixed asset.
- Copy it into generated C++ artifacts.
- Include it from generated `tsl.hpp` after generated primitive wrappers.
- Support unary `N -> N` transforms with one input column and one output column.
- Support binary `N -> N` transforms with two input columns and one output
  column.
- Ensure `load` and `store` are emitted as C++ support roots when the helper is
  included, and keep the `tsl.hpp` include gated as a defensive check when those
  wrappers are absent.
- Default transform helpers to `alignment::detect`: runtime-check input/output
  alignment once, then dispatch to a static-alignment detail loop.
- Keep explicit `alignment::unaligned` and `alignment::assume_aligned` policies
  for callers that want no runtime alignment checks or can prove all operands
  are aligned.
- Add the operation invocation adapter so C++17 users can write either a typed
  functor, a `vector_tag<Vec>` generic lambda, or a plain callable.
- Keep scalar-prologue alignment peeling as an explicit
  `alignment::peel_to_aligned` policy for dense transforms; do not make it
  default behavior.
- Add generated C++ smoke/value-style tests that instantiate simple unary and
  binary operations for scalar/generic profiles.

Out of scope:

- Rust.
- Reductions.
- Masked transforms.
- Containers.
- Runtime CPU/profile dispatch.
- Threading.
- New TSIL/catalog/lowering concepts.

Expected dependencies:

- `tsl::algo::parallelism::native` maps to
  `tsl::dataparallel::simd_for_t<tsl::dataparallel::native, T>`.
- `tsl::algo::parallelism::fixed<N>` maps to
  `tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<N>, T>`,
  falling back to `tsl::generic<N>` when no native profile specialization
  exists.
- `Vec::vector_element_count` or `Vec::lane_count()` is available for chunk
  sizing and validation.
- `Vec::vector_alignment` is available for runtime alignment checks.
- `load<Vec, aligned>` for the derived `Vec`.
- `store<Vec, aligned>` for the derived `Vec`.
- `tsl::simd<T, tsl::scalar>` for tail handling.
- Operation invocable for `Vec` and scalar vector through `detail::invoke_op`.

Validation:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_build_verify.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py
git diff --check
```

Generated build tests matter because this feature is a C++ asset and public
header integration feature, not a pure Python compiler behavior.

## Implemented Helper Surface

Implemented after the dense first slice:

- `predicate_unary` / `predicate_binary` for contiguous `N -> N` predicate
  output using `mask_layout::integral`, `mask_layout::native`, or
  `mask_layout::bytes`, or `mask_layout::bits`.
- `transform_where_unary` / `transform_where_binary` for integral-mask,
  native-mask, byte-mask, or packed-bit-mask input and
  inactive-output-preserving `N -> N` transforms.
- `transform_masked_unary` / `transform_masked_binary` for integral-mask,
  native-mask, byte-mask, or packed-bit-mask input and masked full-store
  `N -> N` transforms where the operation supplies inactive lane values.
- `select_unary` / `select_binary` for contiguous selection/compaction, where
  the operation produces a predicate mask and the helper compacts active left
  input values to output. For `select_binary`, the predicate sees both input
  registers but the compacted value stream is the left input.
- `select_masked_unary` / `select_masked_binary` for mask-consuming
  selection/compaction, where the helper combines an input mask with the
  operation-produced predicate mask and compacts only left-input lanes active
  in both masks.
- `select_indices_unary` / `select_indices_binary` for selection-vector
  production, where the helper writes selected row ids to a caller-owned
  unsigned integral output range and returns the produced count.
- `select_masked_indices_unary` / `select_masked_indices_binary` for
  mask-consuming selection-vector production, where the helper combines the
  input mask with the operation-produced predicate and writes row ids active in
  both masks.
- `select_selected_indices_unary` / `select_selected_indices_binary` for
  selection-vector refinement, where the helper reads caller-owned row ids,
  evaluates a predicate on selected rows using `gather_narrow` for 32-bit and
  64-bit pointer-backed row-id streams, and writes a new dense row-id stream
  containing the original row ids that passed the predicate.
- `transform_selected_unary` / `transform_selected_binary` for
  selection-vector consumption, where the helper reads caller-owned row ids,
  loads selected values in row-id order using `gather_narrow` for 32-bit and
  64-bit pointer-backed row-id streams, applies the operation, and writes dense
  selected output values.
- `aggregate_selected_unary` / `aggregate_selected_binary` for selected-row
  aggregation, where the helper reads caller-owned row ids, loads selected
  values in row-id order using the same selected-row load policy, and the
  operation owns accumulator state plus `finalize()`.
- `consume_selected_unary` / `consume_selected_binary` for selected-row sink
  operations, where the helper reads caller-owned row ids and invokes a
  stateful operation for selected rows without helper-owned output.
- `count_unary` / `count_binary` for contiguous predicate cardinality, where
  the helper counts operation-produced active lanes without materializing a
  mask, compacted values, or row ids.
- `count_masked_unary` / `count_masked_binary` for mask-consuming predicate
  cardinality, where the helper combines the input mask with the
  operation-produced predicate before counting active lanes.
- `count_selected_unary` / `count_selected_binary` for selection-vector
  predicate cardinality, where the helper reads caller-owned row ids, evaluates
  a predicate on selected rows using the portable scalar/generic fallback, and
  returns the number of selected rows that passed.
- `aggregate_unary` / `aggregate_binary` for contiguous aggregation, where the
  helper owns partitioning/loading/tail handling and the operation owns
  accumulator state plus a `finalize()` result.
- `aggregate_masked_unary` / `aggregate_masked_binary` for mask-consuming
  aggregation, where the helper owns mask/value loading and tail handling, and
  the operation must account for inactive lanes before finalization.
- `consume_unary` / `consume_binary` for contiguous sink operations where the
  helper owns partitioning/loading/tail handling and the operation owns side
  effects or external state.
- `consume_masked_unary` / `consume_masked_binary` for mask-consuming sink
  operations where the helper owns mask/value loading and tail handling, and
  the operation must account for inactive lanes in its side effects or external
  state.
- `for_each_chunk` as a low-level escape hatch where the helper owns vector
  type inference and chunk/tail enumeration, while the operation owns memory
  effects using the provided chunk pointer, offset, and lane count.
- C++17 range overloads for implemented helper families. These accept objects
  compatible with `std::data(range)` and `std::size(range)` and forward to the
  pointer+count APIs without allocating or resizing storage.
- `integral_mask_type<Parallelism, T>`,
  `fixed_integral_mask_type<ParallelN, T>`, and
  `integral_mask_chunk_count` helpers for caller-owned mask storage.
- `native_mask_type<Parallelism, T>`,
  `fixed_native_mask_type<ParallelN, T>`, and `native_mask_chunk_count` helpers
  for caller-owned native mask chunk storage.
- `byte_mask_type<Parallelism, T>`, `fixed_byte_mask_type<ParallelN, T>`, and
  `byte_mask_count` helpers for caller-owned one-byte-per-row mask storage.
- `bit_mask_type<Parallelism, T>`, `fixed_bit_mask_type<ParallelN, T>`, and
  `bit_mask_count` helpers for caller-owned packed-bit mask storage.

Still-later slices:

1. Consider runtime profile dispatch only as a separate feature.

## Design Risks

- The helper can accidentally become a generic C++ algorithm framework.
- "Span-like" can drag in C++20 or custom view semantics before the core loop is
  proven.
- Tail and mask semantics can become ambiguous if inactive lanes are not
  specified per helper family.
- The user operation may not be valid for scalar tail handling.
- `ParallelN` may not correspond to an available native extension in the
  selected generated profile.
- Helper-owned primitive availability can make generated `tsl.hpp` fail for
  small primitive subsets unless `load`/`store` are always emitted with the
  helper or the helper is gated out.
- Alignment policy can be misused if the helper does not make caller promises
  explicit.
- Runtime alignment inference adds a few branches before the loop; tiny ranges
  may prefer explicit `alignment::unaligned`.
- `alignment::detect` requires a trustworthy generated vector-alignment value and
  must use correct pointer-to-integer conversion.
- Operation invocation detection can make diagnostics noisy if no supported
  call form matches; the helper needs focused `static_assert` messages.
- A single public all-operands-aligned tag stays too coarse for callers that want
  to promise only input or only output alignment without runtime checks.
- Scalar-prologue alignment peeling only works when every memory operand can be
  aligned at the same element index; otherwise an aligned vector loop would be
  unsafe.
- Floating-point reductions can silently change results if reduction order is
  not explicit.
- Overlapping input/output ranges are supported only for exact dense-transform
  in-place aliasing. Shifted or otherwise partial overlaps are a caller error.

## Settled Decisions

- Operation arguments use generated `tsl::reg_param<Vec>::type` conventions so
  the helper follows each vector specialization's preferred ABI instead of
  forcing `Vec::register_type` by value.
- Operation invocation precedence is typed functor first, then
  `vector_tag<Vec>` callable, then plain callable.
- There is no separate scalar-tail operation. The same operation must be valid
  for both the selected vector type and `tsl::simd<T, tsl::scalar>`.
- `count == 0` is a no-op for transforms, predicates, selection, consume, and
  chunk iteration. Aggregation returns `op.finalize()`, so empty-input behavior
  is defined by the operation's initial state.
- `alignment::peel_to_aligned` is accepted only by dense `transform_unary` and
  `transform_binary`. It peels scalar work only when all memory operands have
  compatible vector-alignment residues; otherwise it falls back to the
  unaligned vector loop.
- `alignment::assume_inputs_aligned` and
  `alignment::assume_output_aligned` are accepted only by dense
  `transform_unary` and `transform_binary`. They avoid the `detect` pre-loop
  alignment checks for common mixed input/output alignment promises without
  adding separate input/output template parameters.
- Dense `transform_unary` allows exact in-place operation where `input ==
  output`. Dense `transform_binary` allows exact in-place operation where
  `output == left` or `output == right`. The helper loads all input registers
  for a chunk before storing the output register, so these exact aliases are
  well-defined.
- Partial overlaps are not supported by dense transforms. Examples include
  `output == input + 1`, `output + 1 == input`, or any shifted overlap between
  binary inputs and output. The helper iterates forward and does not implement
  `memmove`-style direction selection or temporary buffering.
- The C++ helper support surface is `load`, `store`, `store_mask`,
  `to_integral`, `to_mask`, `gather_narrow`, `compress_store`,
  `mask_population_count`, and `mask_binary_and`. `store_mask` is the emitted
  wrapper for the pass-through masked form of the `store` source primitive.
- `gather_narrow` is the selected-row load support root for pointer-backed
  row-id streams. A lane-count match is not sufficient by itself to use plain
  `gather`: plain `gather` consumes an index register, so the generated library
  must also provide/prove the index-register construction path (`load`/array
  conversion for the index vector type) without corrupting dependency closure.
  Keep plain `gather` outside the helper support-root set until a helper
  consumes an index register or the compiler has a typed extra-index-vector
  support policy.
- Unsupported fixed-width vector inference diagnostics are intentionally split
  by failure point: `parallelism::fixed<N>` rejects `N == 0`,
  `validate_vector_for_parallelism` rejects non-static or wrong-width mappings,
  and the portable `tsl::generic<N>` fallback rejects total widths that are not
  a multiple of 16 bytes.
- If a future helper needs a primitive outside the support-root set, pause the
  helper work and decide explicitly whether to add that primitive to `tsldata`
  and C++ generation policy.
- Plain `gather` is not part of the current algorithm-helper support-root set.
  It is a valid generated primitive, but it consumes a prebuilt index register
  (`vidx`) whose concrete SIMD type is a separate free type parameter. A helper
  that consumes native index-register chunks would therefore need a separate
  public row-source contract and either expose an index-vector type parameter
  or add typed compiler support for constructing that vector. That is a future
  feature, not an automatic replacement for pointer-backed selected-row helpers.

## Future Work

- A native index-register row source may be added as a separate helper family
  once its public API is explicit. It should consume caller-owned index-register
  chunks and call plain `gather`, rather than trying to infer that path from a
  pointer-backed row-id stream.
