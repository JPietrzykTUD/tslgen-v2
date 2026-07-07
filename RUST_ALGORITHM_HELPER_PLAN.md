# Rust Algorithm Helper Plan

This plan captures the current design direction for Rust algorithm helpers. It
is intentionally separate from `CPP_ALGORITHM_HELPER_PLAN.md`: the goal is the
same, but Rust needs a different API shape and a different generated/static
asset split.

## Goal

The helper API should decouple user-written algorithm code from a concrete
hardware extension.

Today, a Rust user calling generated TSL primitives generally names the profile
module and SIMD extension directly:

```rust
use tsl::profile::{add, set1, Avx2};
use tsl::tsl_core::Simd;

type VecI32 = Simd<i32, Avx2>;

let left = set1::<VecI32>(1);
let right = set1::<VecI32>(2);
let result = add::<VecI32>(left, right);
```

That is precise, but it couples algorithm code to `Avx2`. Algorithm authors are
usually more interested in one of these policies:

- a fixed degree of data parallelism, such as `fixed::<8>()`;
- the native vector width selected by the generated profile, such as
  `native()`;
- an explicitly portable fallback, such as `generic::<8>()`.

The desired API should let users express the parallelism policy and let the
generated profile map that policy to the concrete SIMD type.

## Design Direction

Rust helpers should feel conceptually similar to the C++ helpers, but they
should not copy the C++ template surface.

Settled direction:

- Provide Rust-shaped helpers rather than C++ templates translated literally.
- Prefer safe slice APIs for ordinary users.
- Keep raw pointer/count APIs as `unsafe` low-level entry points.
- Keep in-place transforms separate, because Rust slices encode aliasing rules.
- Use a trait-based operation contract rather than relying on generic closures.
- Make `native` mean compile-time profile-native, not runtime CPU dispatch.
- Add generated per-profile mapping facts for `T + parallelism policy -> Vec`.
- Keep reusable helper machinery static where possible.
- Generate only the profile-specific facts and any profile-local adapter needed
  to call generated primitives.

## Current Rust Boundary

Generated Rust primitives are profile-module scoped. A generated package exposes
modules such as:

```text
tsl_core
tsl_scalar
tsl_sse
tsl_avx2
...
```

Within a profile module, a primitive is exposed as a generic wrapper:

```rust
pub fn add<S: detail::primitives::AddImpl>(
    left: S::RegisterType,
    right: S::RegisterType,
) -> S::RegisterType
```

The caller chooses `S`, for example `Simd<i32, Avx2>`. The selected `S` defines:

- `S::BaseType`
- `S::RegisterType`
- `S::MaskType`
- `S::ImaskType`
- `S::ELEMENT_COUNT`
- `S::ALIGN`

This is a good low-level primitive boundary. The helper layer should sit above
it and choose `S` from a parallelism policy.

## C++ Comparison

C++ can keep most helper logic static because generated profile headers add
specializations such as:

```cpp
template <>
struct simd_for<fixed<8>, int32_t> {
    using type = ::tsl::simd<int32_t, ::tsl::avx2>;
};

template <>
struct simd_for<native, int32_t> {
    using type = ::tsl::simd<int32_t, ::tsl::avx2>;
};
```

The static C++ algorithm helper can then ask for
`tsl::dataparallel::simd_for_t<tsl::dataparallel::fixed<ParallelN>, T>` or
`tsl::dataparallel::simd_for_t<tsl::dataparallel::native, T>`.

Rust does not have stable trait specialization or C++-style partial
specialization fallback. The Rust equivalent must be an explicit generated trait
mapping.

## Static And Generated Split

The Rust design needs both static helper assets and generated profile-scoped
facts.

Implemented split:

```text
tsl_core.rs
  Static SIMD traits and register model.

tsl_algorithm.rs
  Static helper vocabulary:
  - parallelism policy markers
  - operation traits
  - selected-vector mapping traits
  - profile load/store adapter trait
  - profile masked-store adapter trait
  - profile mask-to-integral adapter trait
  - profile integral-to-mask adapter trait
  - shared `transform_unary` / `transform_unary_raw` loop kernels
  - shared `transform_binary` / `transform_binary_raw` loop kernels
  - shared `for_each_chunk` / `for_each_chunk_raw` enumeration kernels
  - shared `predicate_unary` / `predicate_unary_raw` loop kernels
  - shared `predicate_binary` / `predicate_binary_raw` loop kernels
  - shared `transform_where_unary` / `transform_where_unary_raw` loop kernels
  - shared `transform_where_binary` / `transform_where_binary_raw` loop kernels
  - shared `consume_unary` / `consume_unary_raw` loop kernels
  - shared `consume_binary` / `consume_binary_raw` loop kernels
  - shared `aggregate_unary` / `aggregate_unary_raw` loop kernels
  - shared `aggregate_binary` / `aggregate_binary_raw` loop kernels
  - shared `consume_masked_unary` / `consume_masked_unary_raw` loop kernels
  - shared `consume_masked_binary` / `consume_masked_binary_raw` loop kernels
  - shared `aggregate_masked_unary` / `aggregate_masked_unary_raw` loop kernels
  - shared `aggregate_masked_binary` / `aggregate_masked_binary_raw` loop kernels
  - shared `count_unary` / `count_unary_raw` loop kernels
  - shared `count_binary` / `count_binary_raw` loop kernels
  - shared `count_masked_unary` / `count_masked_unary_raw` loop kernels
  - shared `count_masked_binary` / `count_masked_binary_raw` loop kernels
  - shared `select_indices_unary` / `select_indices_unary_raw` loop kernels
  - shared `select_indices_binary` / `select_indices_binary_raw` loop kernels
  - shared `select_masked_indices_unary` /
    `select_masked_indices_unary_raw` loop kernels
  - shared `select_masked_indices_binary` /
    `select_masked_indices_binary_raw` loop kernels

tsl_<profile>.rs
  Generated primitives for that profile.
  Generated algorithm mapping facts for that profile.
  A profile-local `pub mod algo` facade that can call sibling primitives such
  as `load` and `store`.
```

The important boundary is fixed:

- generic helper vocabulary is static;
- `T + policy -> concrete Simd<T, Extension>` mappings are generated;
- profile-local glue is generated because Rust primitives live inside profile
  modules rather than one shared namespace;
- the pipeline pulls `load`, `store`, `to_integral`, and `to_mask` into Rust
  generation as helper support primitives, mirroring the C++ helper-support root
  mechanism.

## Parallelism Policies

The public vocabulary should include at least these policies:

```rust
pub mod parallelism {
    pub struct Native;
    pub struct Fixed<const N: usize>;
    pub struct Generic<const N: usize>;

    pub fn native() -> Native;
    pub fn fixed<const N: usize>() -> Fixed<N>;
    pub fn generic<const N: usize>() -> Generic<N>;
}
```

Semantics:

- `native()` selects the best compile-time native SIMD type emitted for the
  current generated profile and element type. If no better concrete vector is
  available for that profile/type, it maps to `Simd<T, Scalar>`.
- `fixed::<N>()` selects a generated hardware-backed mapping for exactly `N`
  lanes when one is known for the profile and element type.
- `generic::<N>()` selects `Simd<T, Generic<N>>`, the portable fallback.

Pushback baked into the design:

- `native()` is not runtime CPU detection.
- `fixed::<N>()` should not silently mean "whatever works". If the generated
  profile has no hardware-backed `T, N` mapping, it should fail at compile time.
- Portable fallback should be explicit through `generic::<N>()`.

## Profile Mapping Traits

A profile needs generated traits or generated implementations that express the
mapping from user intent to concrete vector type.

Sketch:

```rust
pub struct Profile;

pub trait NativeSimd<T> {
    type Vec: StaticSimdVector<BaseType = T>;
}

pub trait FixedSimd<T, const N: usize> {
    type Vec: StaticSimdVector<BaseType = T>;
}

pub trait GenericSimd<T, const N: usize> {
    type Vec: StaticSimdVector<BaseType = T>;
}
```

Generated inside `tsl_avx2` or its profile-local `algo` module:

```rust
impl NativeSimd<i32> for Profile {
    type Vec = Simd<i32, Avx2>;
}

impl FixedSimd<i32, 8> for Profile {
    type Vec = Simd<i32, Avx2>;
}

impl FixedSimd<i32, 4> for Profile {
    type Vec = Simd<i32, Sse>;
}

impl<const N: usize> GenericSimd<i32, N> for Profile {
    type Vec = Simd<i32, Generic<N>>;
}
```

The concrete generated mappings should use the same selection preference as the
C++ `inferred_simd`/`native_simd` registration:

- prefer available concrete register extensions over generic fallback;
- choose the best registered extension for the profile, type, and lane count;
- keep output deterministic by sorting emitted impls.

## Helper API Shape

The high-level call should be profile-module scoped:

```rust
use tsl::profile::algo;

algo::transform_unary(
    algo::parallelism::fixed::<8>(),
    &mut square,
    &input,
    &mut output,
);

algo::transform_unary(
    algo::parallelism::native(),
    &mut square,
    &input,
    &mut output,
);
```

An unsafe low-level form may also exist:

```rust
unsafe {
    algo::transform_unary_raw(
        algo::parallelism::fixed::<8>(),
        &mut square,
        input.as_ptr(),
        output.as_mut_ptr(),
        input.len(),
    );
}
```

Safe slice contract:

- `input.len()` must equal `output.len()`, or the helper should assert/panic.
- `count == 0` is a no-op.
- Dense out-of-place transform takes `&[T]` and `&mut [T]`.
- Exact in-place transform should use a separate helper, for example
  `transform_unary_in_place`.
- Overlapping-but-not-identical input/output ranges should not be accepted by a
  safe API.

## Operation Contract

Rust closures cannot express "generic over `Vec`" the way a C++ templated call
operator can. This matters because a helper usually needs both:

- a vector operation for the SIMD loop;
- a scalar operation for the tail.

A normal closure is monomorphic and cannot naturally be called for both
`Simd<T, Avx2>` and `Simd<T, Scalar>`.

Preferred operation contract:

```rust
pub trait UnaryKernel<V: StaticSimdVector> {
    fn apply(
        &mut self,
        value: V::RegisterType,
    ) -> V::RegisterType;
}
```

A reusable operation is implemented once for all vector types that provide the
needed generated primitive:

```rust
use tsl::profile;
use tsl::tsl_core::StaticSimdVector;

struct Square;

impl<V> profile::algo::UnaryKernel<V> for Square
where
    V: StaticSimdVector + profile::detail::primitives::MulImpl,
{
    fn apply(&mut self, value: V::RegisterType) -> V::RegisterType {
        profile::mul::<V>(value, value)
    }
}
```

Then the helper can require:

```rust
Op: UnaryKernel<VectorVec> + UnaryKernel<ScalarVec>
```

where:

- `VectorVec` is selected from the parallelism policy;
- `ScalarVec` is `Simd<T, Scalar>` for the scalar tail.

This is less lambda-friendly than C++, but it is honest Rust and keeps the tail
semantics type-safe.

Binary transforms use the same pattern with a two-input operation:

```rust
pub trait BinaryKernel<V: StaticSimdVector> {
    fn apply(
        &mut self,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType;
}
```

Predicate helpers use register-level operations that return the selected
vector's mask type. The helper owns conversion to the integral mask stream:

```rust
pub trait UnaryPredicateKernel<V: StaticSimdVector> {
    fn test(&mut self, value: V::RegisterType) -> V::MaskType;
}

pub trait BinaryPredicateKernel<V: StaticSimdVector> {
    fn test(
        &mut self,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::MaskType;
}
```

The profile-local facade implements a static `IntegralMask<V>` bridge through
the generated `to_integral::<V>` primitive when that primitive is present.
The first Rust predicate slice supports integral mask chunks only; native,
byte, and packed-bit mask layouts remain separate future slices.

Where helpers consume integral mask chunks and preserve inactive output lanes
using generated `to_mask::<V>` and `store_mask::<V, false>` primitives:

```rust
pub trait MaskedUnaryKernel<V: StaticSimdVector> {
    fn apply(
        &mut self,
        active: V::MaskType,
        value: V::RegisterType,
    ) -> V::RegisterType;
}

pub trait MaskedBinaryKernel<V: StaticSimdVector> {
    fn apply(
        &mut self,
        active: V::MaskType,
        left: V::RegisterType,
        right: V::RegisterType,
    ) -> V::RegisterType;
}
```

Rust does not auto-detect a plain `UnaryKernel`/`BinaryKernel` for where
helpers. Operations that do not need the mask implement the masked trait and
ignore the `active` argument.

Chunk enumeration uses a pointer-metadata operation because the helper does not
own memory effects for this escape hatch:

```rust
pub trait ChunkKernel<V: StaticSimdVector> {
    unsafe fn apply(
        &mut self,
        ptr: *const V::BaseType,
        offset: usize,
        count: usize,
    );
}
```

The safe helper upholds the pointer/count validity precondition from a slice.
The operation remains responsible for any unsafe load/store it performs.

Consume helpers use stateful sink operations. The helper owns loading,
partitioning, and scalar tail handling, while the operation updates its own
state and returns no helper-owned value:

```rust
pub trait UnaryConsumeKernel<V: StaticSimdVector> {
    fn consume(&mut self, value: V::RegisterType);
}

pub trait BinaryConsumeKernel<V: StaticSimdVector> {
    fn consume(
        &mut self,
        left: V::RegisterType,
        right: V::RegisterType,
    );
}
```

Aggregate helpers use the same accumulation shape but return the operation's
final value through a Rust trait method:

```rust
pub trait UnaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(&mut self, value: V::RegisterType);
    fn finalize(&self) -> Self::Output;
}

pub trait BinaryAggregateKernel<V: StaticSimdVector> {
    type Output;

    fn accumulate(
        &mut self,
        left: V::RegisterType,
        right: V::RegisterType,
    );
    fn finalize(&self) -> Self::Output;
}
```

Possible convenience layer later:

- monomorphic closure helpers for operations that only need one vector type and
  have no scalar tail;
- separate vector and scalar closures;
- small operation adapter macros if the trait syntax is too noisy in practice.

These should be convenience additions, not the core contract.

## Loading, Storing, And Alignment

The helper owns partitioning, loading, storing, and tail handling. The operation
owns only transformation logic.

For the first Rust slice:

- use unaligned load/store by default;
- keep alignment policy names aligned with C++ vocabulary where practical;
- make any aligned raw-pointer API `unsafe`;
- do not rely on Rust stable `assume_aligned` behavior for optimization claims;
- use generated `load::<Vec, false>` and `store::<Vec, false, _>` primitives
  where available.

Alignment can be extended later with policies similar to C++:

- `alignment::detect`
- `alignment::unaligned`
- `alignment::assume_aligned`
- `alignment::assume_inputs_aligned`
- `alignment::assume_output_aligned`
- `alignment::peel_to_aligned`

For safe slices, alignment policy needs careful wording because a Rust slice
only guarantees alignment for `T`, not necessarily for the selected SIMD
register alignment.

## Runtime Dispatch Boundary

This helper plan does not introduce runtime CPU dispatch.

Profile module choice remains a build-time or call-site choice:

```rust
tsl::profile::algo::transform_unary(...)
tsl::profile::algo::transform_unary(...)
```

`native()` means "native for this generated profile module." It does not mean
"detect the current machine at runtime and choose an implementation."

Runtime dispatch could be built as a separate layer later, but it should not be
mixed into the first helper design.

## First Slice

The first implemented slice is deliberately narrow:

1. Add static Rust helper vocabulary for:
   - parallelism policies;
   - `UnaryKernel<V>`;
   - selected-vector mapping traits.
2. Generate per-profile mapping impls equivalent to C++ `inferred_simd` and
   `native_simd`.
3. Add `transform_unary` for safe out-of-place slices.
4. Add `transform_unary_raw` as an unsafe pointer/count form if needed by tests.
5. Use unaligned load/store only.
6. Require the operation to implement both vector and scalar `UnaryKernel`
   instances.
7. Add one Rust example matching the C++ unary operator example.
8. Wire the Rust example into generated package consumer/example verification.

The Rust unary example lives under `examples/rust` and is exercised by the
generated-package consumer verification script. It uses a square operation and
verifies `native()`, `fixed::<1>()`, and explicit `generic::<8>()` under the
scalar profile.

Out of scope for the first slice:

- masked transforms;
- selection vectors;
- reductions;
- runtime CPU dispatch;
- alignment peeling;
- in-place transforms;
- generated value-test expansion for helper examples.

## Second Slice

The second implemented slice adds dense binary transforms:

1. Add static Rust helper vocabulary for `BinaryKernel<V>`.
2. Add safe `transform_binary` and unsafe `transform_binary_raw`.
3. Reuse the existing profile-local vector mapping and `LoadStore` facts.
4. Require the operation to implement both vector and scalar `BinaryKernel`
   instances.
5. Add a Rust example matching the C++ binary operator example's add kernel for
   the safe out-of-place slice contract.
6. Wire the Rust binary example into generated package consumer verification.

Still out of scope for this slice:

- in-place binary transforms, because safe Rust slices encode exclusive output
  borrowing;
- alignment policies beyond unaligned load/store;
- masked binary transforms;
- selected-row binary transforms;
- reductions and consume helpers.

## Third Slice

The third implemented slice adds chunk enumeration:

1. Add static Rust helper vocabulary for `ChunkKernel<V>`.
2. Add safe `for_each_chunk` over `&[T]` and unsafe `for_each_chunk_raw`.
3. Reuse the existing profile-local vector mapping facts.
4. Tail with `Simd<T, Scalar>`, matching the C++ helper contract.
5. Add a Rust example matching the C++ chunk operator example's pointer
   metadata validation and `load` + `hadd` sum.
6. Wire the Rust chunk example into generated package consumer verification.

Still out of scope for this slice:

- mutable chunk enumeration;
- range convenience wrappers beyond Rust slices;
- alignment policies;
- helpers that own masks, reductions, or selected rows.

## Fourth Slice

The fourth implemented slice adds dense consume helpers:

1. Add static Rust helper vocabulary for `UnaryConsumeKernel<V>` and
   `BinaryConsumeKernel<V>`.
2. Add safe `consume_unary` and `consume_binary` over slices.
3. Add unsafe `consume_unary_raw` and `consume_binary_raw` pointer/count forms.
4. Reuse the existing profile-local vector mapping and `LoadStore` facts.
5. Tail with `Simd<T, Scalar>`, matching the dense transform helper contract.
6. Add a Rust example matching the C++ consume operator example's stateful
   unary and binary sinks.
7. Wire the Rust consume example into generated package consumer verification.

Still out of scope for this slice:

- non-integral mask layout variants for consume helpers;
- selected-row consume helpers;
- aggregate helpers with a helper-owned return value;
- alignment policies beyond unaligned load/store.

## Fifth Slice

The fifth implemented slice adds dense aggregate helpers:

1. Add static Rust helper vocabulary for `UnaryAggregateKernel<V>` and
   `BinaryAggregateKernel<V>`.
2. Add safe `aggregate_unary` and `aggregate_binary` over slices.
3. Add unsafe `aggregate_unary_raw` and `aggregate_binary_raw` pointer/count
   forms.
4. Reuse the existing profile-local vector mapping and `LoadStore` facts.
5. Tail with `Simd<T, Scalar>`, matching the dense transform/consume contract.
6. Return the selected-vector aggregate trait's `Output` from `finalize()`.
7. Add a Rust example matching the C++ aggregation operator example's unary and
   binary sum operations.
8. Wire the Rust aggregation example into generated package consumer
   verification.

Still out of scope for this slice:

- masked aggregate helpers;
- selected-row aggregate helpers;
- count helpers;
- alignment policies beyond unaligned load/store.

## Sixth Slice

The sixth implemented slice adds dense predicate materialization helpers:

1. Add static Rust helper vocabulary for `UnaryPredicateKernel<V>` and
   `BinaryPredicateKernel<V>`.
2. Add an `IntegralMask<V>` profile adapter that converts `V::MaskType` to
   `V::ImaskType` through generated `to_integral::<V>`.
3. Add `integral_mask_chunk_count`, safe `predicate_unary` and
   `predicate_binary` over slices, and unsafe pointer/count raw forms.
4. Store one integral mask chunk per vector chunk, including a packed scalar
   tail chunk when `count` is not divisible by the selected lane count.
5. Require the integral mask storage type to have at least one bit per lane.
6. Add a Rust example matching the C++ predicate operator example's unary
   negative and binary less-than predicates.
7. Wire the Rust predicate example into generated package consumer
   verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- mask-consuming transform helpers beyond predicate materialization;
- compacting selection helpers.

## Seventh Slice

The seventh implemented slice adds dense where transforms over integral masks:

1. Add static Rust helper vocabulary for `MaskedUnaryKernel<V>` and
   `MaskedBinaryKernel<V>`.
2. Add `MaskFromIntegral<V>` and `MaskedStore<V>` profile adapters backed by
   generated `to_mask::<V>` and `store_mask::<V, false>`.
3. Add safe `transform_where_unary` and `transform_where_binary` over slices,
   plus unsafe pointer/count raw forms.
4. Consume one integral mask chunk per vector chunk and preserve inactive
   output lanes through masked stores.
5. Tail with `Simd<T, Scalar>`, applying the operation only for active tail
   lanes.
6. Add a Rust example matching the C++ where operator example's unary square
   and binary add operations.
7. Wire the Rust where example into generated package consumer verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- selection helpers.

## Eighth Slice

The eighth implemented slice adds masked full-store transforms over integral
masks:

1. Reuse `MaskedUnaryKernel<V>` and `MaskedBinaryKernel<V>` from the where
   slice.
2. Reuse `MaskFromIntegral<V>` to convert integral mask chunks to the selected
   vector mask type.
3. Add safe `transform_masked_unary` and `transform_masked_binary` over slices,
   plus unsafe pointer/count raw forms.
4. Consume one integral mask chunk per vector chunk, call the operation with
   the converted activity mask, and store every output lane with ordinary
   unmasked stores.
5. Tail with `Simd<T, Scalar>`, passing a true or false scalar mask per row so
   the operation owns inactive-row values.
6. Add a Rust example matching the C++ masked operator example's unary
   square-or-original and binary add-or-left operations.
7. Wire the Rust masked example into generated package consumer verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- masked aggregation helpers;
- selection helpers.

## Ninth Slice

The ninth implemented slice adds masked consume helpers over integral masks:

1. Add static Rust helper vocabulary for `MaskedUnaryConsumeKernel<V>` and
   `MaskedBinaryConsumeKernel<V>`.
2. Reuse `MaskFromIntegral<V>` to convert integral mask chunks to the selected
   vector mask type.
3. Add safe `consume_masked_unary` and `consume_masked_binary` over slices,
   plus unsafe pointer/count raw forms.
4. Consume one integral mask chunk per vector chunk, call the operation with
   the converted activity mask, and leave all side effects to the sink
   operation.
5. Tail with `Simd<T, Scalar>`, passing a true or false scalar mask per row so
   the sink can apply the same masking logic as the vector path.
6. Add a Rust example matching the C++ masked consume example's unary masked
   sum and binary masked pair-sum operations for the integral-mask layout.
7. Wire the Rust masked consume example into generated package consumer
   verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- selected-row consume helpers;
- selection helpers.

## Tenth Slice

The tenth implemented slice adds masked aggregate helpers over integral masks:

1. Add static Rust helper vocabulary for `MaskedUnaryAggregateKernel<V>` and
   `MaskedBinaryAggregateKernel<V>`.
2. Reuse `MaskFromIntegral<V>` to convert integral mask chunks to the selected
   vector mask type.
3. Add safe `aggregate_masked_unary` and `aggregate_masked_binary` over slices,
   plus unsafe pointer/count raw forms.
4. Consume one integral mask chunk per vector chunk, call the operation with
   the converted activity mask, and return the selected-vector aggregate
   trait's `Output` from `finalize()`.
5. Tail with `Simd<T, Scalar>`, passing a true or false scalar mask per row so
   the aggregate operation can apply the same masking logic as the vector path.
6. Add a Rust example matching the C++ masked aggregation example's unary
   masked sum and binary masked pair-sum operations for the integral-mask
   layout.
7. Wire the Rust masked aggregation example into generated package consumer
   verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- selected-row aggregate helpers;
- count helpers;
- selection helpers.

## Eleventh Slice

The eleventh implemented slice adds dense and integral-masked count helpers:

1. Reuse `UnaryPredicateKernel<V>` and `BinaryPredicateKernel<V>` from the
   predicate slice.
2. Reuse `IntegralMask<V>` to convert operation-produced predicate masks into
   integral masks.
3. Add safe `count_unary` and `count_binary` over slices, plus unsafe
   pointer/count raw forms.
4. Add safe `count_masked_unary` and `count_masked_binary` over slices with
   caller-owned integral mask chunks, plus unsafe pointer/count raw forms.
5. Count full vector chunks by population-counting the predicate integral mask,
   or the bitwise intersection of the caller mask and predicate integral mask
   for masked helpers.
6. Tail with `Simd<T, Scalar>`, preserving the same predicate and mask
   semantics lane by lane.
7. Add a Rust example matching the dense and integral-mask parts of the C++
   count operator example.
8. Wire the Rust count example into generated package consumer verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- selected-row count helpers;
- count helpers over existing selection vectors.

## Twelfth Slice

The twelfth implemented slice adds selection-vector production over contiguous
inputs and integral masks:

1. Reuse `UnaryPredicateKernel<V>` and `BinaryPredicateKernel<V>` from the
   predicate slice.
2. Reuse `IntegralMask<V>` to convert operation-produced predicate masks into
   integral masks.
3. Add safe `select_indices_unary` and `select_indices_binary` over slices,
   plus unsafe pointer/count raw forms.
4. Add safe `select_masked_indices_unary` and
   `select_masked_indices_binary` over slices with caller-owned integral mask
   chunks, plus unsafe pointer/count raw forms.
5. Write selected row ids as `usize`, matching the planned Rust selected-row
   index type.
6. Keep output storage caller-owned; safe APIs require at least `input.len()`
   output slots because every input row may be selected.
7. Tail with `Simd<T, Scalar>`, preserving predicate and mask semantics lane
   by lane.
8. Add a Rust example matching the dense and integral-mask parts of the C++
   selection-vector example.
9. Wire the Rust selection-vector example into generated package consumer
   verification.

Still out of scope for this slice:

- native mask storage layout;
- byte mask storage layout;
- packed-bit mask storage layout;
- compacting value selection helpers;
- selected-row refinement helpers over existing selection vectors.

## Validation Plan

Focused Python/render validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_render_model.py \
  tslc/tests/test_generation_conditionals.py
```

Generated build validation when the slice touches generated Rust output:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py
```

Consumer/example validation should cover:

- scalar profile;
- at least one x86 SIMD profile, preferably AVX2;
- `native()`;
- `fixed::<N>()` where `N` maps to a concrete hardware vector;
- `generic::<N>()` as an explicit portable fallback;
- scalar tail handling for counts that are not multiples of the vector lane
  count.

Always consider:

```bash
python -m compileall -q tslc/src/tslc
git diff --check
```

## Open Questions

- How noisy is the `UnaryKernel<V>` trait implementation in real user code?
- Do we want convenience adapters for separate vector/scalar closures in the
  first release, or only after the trait contract proves itself?
- Should `fixed::<N>()` ever fall back to `Generic<N>`, or should portable
  fallback always remain explicit through `generic::<N>()`? The current plan
  favors explicit fallback.
