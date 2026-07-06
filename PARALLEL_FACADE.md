# Data-Parallel Primitive Facade Plan

## Purpose

This document captures the agreed direction for making data-parallel vector
selection a first-class generated TSL concept, not only an implementation detail
of the algorithm helpers.

The current low-level primitive API is explicit and precise: users call a
primitive by naming a concrete generated SIMD vector type.

```cpp
using vec = tsl::simd<std::int32_t, tsl::avx2>;
auto result = tsl::add<vec>(left, right);
```

That API should remain the ground truth. The facade described here is a
convenience layer above it:

- keep `Vec` / `Simd<T, Extension>` as the canonical primitive selector;
- add a policy-based API that maps user intent to `Vec`;
- make the policy vocabulary canonical under `tsl::dataparallel`;
- allow helpers and primitive convenience wrappers to share the same mapping
  facts.

The goal is to decouple user-written algorithm code from concrete hardware
extension names without pretending that every backend can be represented by a
compile-time lane count.

## Settled Decisions

### `Vec` Remains The Primitive Ground Truth

Generated primitive implementations are specialized for a concrete vector type.
That should not change.

The canonical primitive form remains:

```cpp
tsl::add<Vec>(left, right)
```

and in Rust:

```rust
tsl::add::<Vec>(left, right)
```

This is the most precise and least surprising API. It exposes the actual
generated implementation selected by the caller and keeps all primitive
signatures anchored to the vector type that defines:

- element/base type;
- register type;
- mask type;
- integral-mask type;
- alignment;
- static or dynamic lane-count properties.

The new facade must forward to this ground-truth API. It should not replace it.

### `(T, Policy) -> Vec` Is A Convenience Layer

Users often think in terms of an element type and data-parallel shape rather
than a hardware extension.

Examples:

- "use native profile width for `std::int32_t`";
- "use exactly 8 lanes for `float`";
- "force the generic 16-lane fallback for a portable test".

The facade should express that as:

```cpp
tsl::dataparallel::native
tsl::dataparallel::fixed<8>
tsl::dataparallel::generic<16>
```

Those policies map to a generated vector type for a concrete element type:

```text
(std::int32_t, tsl::dataparallel::fixed<8>) -> tsl::simd<std::int32_t, tsl::avx2>
(std::int32_t, tsl::dataparallel::native)   -> profile-native vector for i32
(std::int32_t, tsl::dataparallel::generic<8>) -> tsl::simd<std::int32_t, tsl::generic<8>>
```

The exact mapping is profile-specific and generated.

### The Canonical Namespace Is `tsl::dataparallel`

The policy vocabulary is broader than algorithms. It describes how generated
TSL selects a data-parallel vector shape.

Therefore the canonical C++ namespace should be:

```cpp
namespace tsl::dataparallel {
struct native;
template <std::size_t N> struct fixed;
template <std::size_t N> struct generic;
}
```

The canonical Rust module should mirror it:

```rust
tsl::dataparallel::native()
tsl::dataparallel::fixed::<8>()
tsl::dataparallel::generic::<8>()
```

Algorithm helpers should consume that vocabulary directly. They should not
re-export it through `tsl::algo`, because that would create multiple public
spellings for the same concept:

```cpp
tsl::dataparallel::fixed<8>
tsl::algo::dataparallel::fixed<8>
```

The design target is one canonical spelling:

```cpp
tsl::algo::transform_binary(
    tsl::dataparallel::fixed<8>{},
    op,
    left,
    right,
    output,
    count);
```

Existing helper examples that use helper-local `parallelism` should be
migrated. Avoid adding `tsl::algo::dataparallel` or
`tsl::algo::parallelism` as long-term compatibility aliases.

### `native` Is The Maximum Generated Hardware Vector

`native` does not mean runtime CPU dispatch.

It means: select the maximum-width hardware vector type that this generated
profile makes available for the element type.

For fixed-width hardware profiles, the default rule should be: choose the
maximum static data-parallel width emitted by the profile for `T`. In practice,
this is the widest emitted hardware vector for that element type, not the
generic fallback and not an arbitrary profile-name choice. The profile defines
the available hardware feature set; `native` chooses the widest fixed-size
hardware vector within that generated set. If multiple emitted
hardware vectors have the same lane count, use deterministic target ranking as
a tie-breaker.

The generated profile's extension set is the source of truth, not the profile
name alone. A profile for a Skylake client target may only expose AVX2 and
therefore map `native` to AVX2. A profile for a Skylake server / AVX-512 target
may expose AVX-512 and therefore map `native` to AVX-512.

For example, an AVX2 profile may map:

```text
(i32, native) -> Simd<i32, Avx2>
```

A profile that represents a target with AVX-512 support may map:

```text
(i32, native) -> Simd<i32, Avx512>
```

A scalar-only profile may map:

```text
(i32, native) -> Simd<i32, Scalar>
```

For scalable hardware profiles such as SVE, `native` may map to the scalable
hardware vector instead of a fixed `N`-lane vector:

```text
(i32, native) -> Simd<i32, Sve>
```

Runtime CPU dispatch can be designed later as a separate layer. It should not
be smuggled into `native`.

### `fixed<N>` Means Static Lane Count

`fixed<N>` means exactly `N` data elements per vector, known as a compile-time
property of the selected vector type.

For C++ this implies:

```cpp
Vec::has_static_lane_count_v == true
Vec::vector_element_count == N
```

For Rust this implies:

```rust
Vec::ELEMENT_COUNT == N
```

If no generated hardware-backed mapping exists for `(T, fixed<N>)`, the call
should fail at compile time. It should not silently choose a different lane
count.

Portable fallback should be explicit:

```cpp
tsl::dataparallel::generic<8>
```

and:

```rust
tsl::dataparallel::generic::<8>()
```

### SVE And Other Scalable Vectors Require Policy, Not `size_t N`

SVE does not fit a plain `template <class T, std::size_t N>` model for native
vectors. The lane count is vector-length agnostic and not a stable compile-time
constant for the generated vector type.

Therefore:

- `fixed<N>` should not map to scalable SVE/RVV-style vectors;
- `native` may map to scalable vectors;
- algorithms that require static chunk sizes must explicitly reject scalable
  `native` vectors or use a runtime-lane loop shape;
- pure register-to-register primitive facades can support scalable `native`
  vectors because they do not need to know the static lane count.

This is the main reason the facade should be policy-based rather than only
`T,N`-based.

## Why Not `add<T, N>` As The Main API?

The original sketch was:

```cpp
template <typename T, std::size_t ParallelismN>
auto add(...);
```

That spelling is attractive for fixed-width SIMD, but it has two problems.

First, it cannot honestly represent native scalable vectors:

```text
SVE native != fixed compile-time N
```

Second, the register parameter type depends on the selected vector, and the
selected vector depends on both `T` and `N`.

In C++, this is technically expressible:

```cpp
template <class Policy, class T>
using dataparallel_simd_t = /* generated mapping */;

template <class Policy, class T>
using dataparallel_reg_t =
    typename dataparallel_simd_t<Policy, T>::register_type;
```

but `T` is usually not deducible from a SIMD register type. On x86, many
different element types share the same underlying register type, for example
`__m256i`. So calls should expect explicit type/policy spelling:

```cpp
tsl::add<tsl::dataparallel::fixed<8>, std::int32_t>(left, right);
```

not magical inference from `left` and `right`.

Rust has the same issue in a stricter form. The parameter type can depend on
`Policy` and `T` through associated types, but associated types are not
generally reversible for type inference. Some calls will need explicit type
annotation or turbofish syntax.

So the settled direction is:

- keep `add<Vec>` as the simple canonical primitive call;
- offer `(Policy, T)` convenience wrappers where they genuinely improve
  ergonomics;
- do not make `T,N` the only or primary spelling.

## C++ Design Sketch

### Static Policy Vocabulary

The generated C++ library should ship a static policy asset, likely included by
`tsl.hpp` and by the algorithm helper headers.

Possible asset:

```text
cpp/include/tsl_dataparallel.hpp
```

Conceptual contents:

```cpp
namespace tsl::dataparallel {

struct native {};

template <std::size_t N>
struct fixed {
  static constexpr std::size_t lanes = N;
};

template <std::size_t N>
struct generic {
  static constexpr std::size_t lanes = N;
};

}  // namespace tsl::dataparallel
```

This asset should not know profile-specific mappings. It only owns vocabulary.

### Generated Mapping Facts

C++ already has helper-oriented mapping machinery:

```cpp
tsl::inferred_simd_t<T, N>
tsl::native_simd_t<T>
```

Those facts should become first-class data-parallel mapping facts rather than
being treated as algorithm-helper-only support.

The plan should converge toward names like:

```cpp
namespace tsl::dataparallel {

template <class Policy, class T>
struct simd_for;

template <class Policy, class T>
using simd_for_t = typename simd_for<Policy, T>::type;

template <class Policy, class T>
using register_t = typename simd_for_t<Policy, T>::register_type;

}  // namespace tsl::dataparallel
```

Profile generation then emits specializations such as:

```cpp
template <>
struct tsl::dataparallel::simd_for<
    tsl::dataparallel::fixed<8>,
    std::int32_t> {
  using type = ::tsl::simd<std::int32_t, ::tsl::avx2>;
};
```

and:

```cpp
template <>
struct tsl::dataparallel::simd_for<
    tsl::dataparallel::native,
    std::int32_t> {
  using type = ::tsl::simd<std::int32_t, ::tsl::avx2>;
};
```

The existing `inferred_simd_t<T, N>` and `native_simd_t<T>` names can remain as
compatibility aliases:

```cpp
template <class T, std::size_t N>
using inferred_simd_t =
    dataparallel::simd_for_t<dataparallel::fixed<N>, T>;

template <class T>
using native_simd_t =
    dataparallel::simd_for_t<dataparallel::native, T>;
```

### Primitive Convenience Wrapper Shape

For a pure binary register primitive such as `add`, the canonical generated
primitive remains:

```cpp
template <class Vec>
typename Vec::register_type add(
    typename tsl::reg_param<Vec>::type left,
    typename tsl::reg_param<Vec>::type right);
```

A policy facade can be generated beside it:

```cpp
template <class Policy, class T>
typename tsl::dataparallel::simd_for_t<Policy, T>::register_type add(
    typename tsl::reg_param<
        tsl::dataparallel::simd_for_t<Policy, T>>::type left,
    typename tsl::reg_param<
        tsl::dataparallel::simd_for_t<Policy, T>>::type right);
```

The wrapper body simply computes `Vec` and forwards:

```cpp
using vec = tsl::dataparallel::simd_for_t<Policy, T>;
return tsl::add<vec>(left, right);
```

The intended call is explicit:

```cpp
auto out = tsl::add<tsl::dataparallel::fixed<8>, std::int32_t>(left, right);
auto native = tsl::add<tsl::dataparallel::native, std::int32_t>(left, right);
```

This is less concise than `add<T, N>`, but it keeps scalable vectors honest and
keeps the policy dimension extensible.

### Function Parameters And Deduction

Do not promise full type deduction for register primitives.

For register-to-register functions, `T` generally appears only inside a
dependent parameter type:

```cpp
typename dataparallel::simd_for_t<Policy, T>::register_type
```

That is a non-deduced context. Even if C++ could attempt deduction, the
underlying register type is often shared by multiple element types.

Therefore the facade should be documented as explicit:

```cpp
tsl::add<tsl::dataparallel::fixed<8>, std::int32_t>(left, right)
```

For primitives whose ordinary parameters contain `T` directly, such as scalar
construction helpers, more deduction may be possible. That should be treated as
a convenience of that primitive shape, not as a universal API rule.

### Which Primitives Should Get Facades?

Do not try to wrap every primitive in the first slice.

The safest initial family is pure register primitives:

- unary register -> register;
- binary register/register -> register;
- register predicates -> mask;
- simple mask operations where the mask type belongs to the selected `Vec`.

Memory primitives required more care:

- load/store have pointer validity and alignment policy questions;
- gather/scatter involve index-vector type, scale, and memory safety;
- mask load/store families need clear inactive-lane semantics;
- conversion/narrow/widen primitives may have source and target element types,
  so a single `(Policy, T)` may not be enough.

The implementation used `add` as the first proof, then expanded by primitive
shape. Plain unmasked contiguous load/store are now covered because their
pointer and alignment contract is explicit. Advanced memory families remain
separate future work because they need additional semantic parameters.

## Rust Design Sketch

### Static Policy Vocabulary

Rust should expose the same canonical concept as a generated crate module:

```rust
tsl::dataparallel::native()
tsl::dataparallel::fixed::<8>()
tsl::dataparallel::generic::<8>()
```

Earlier helper drafts used a helper-local `parallelism` module. That vocabulary
has moved to canonical `dataparallel` naming. The generated crate exposes it at
the crate level, while profile-local `algo` modules consume it without
re-exporting it.

Possible long-term module split:

```text
rust/src/tsl_dataparallel.rs
  Static policy marker structs and constructors.

rust/src/tsl_algorithm.rs
  Static algorithm helper traits and loop kernels that consume dataparallel
  policies.
```

The current implementation keeps the policy implementation in
`tsl_algorithm.rs` while `lib.rs` exposes a canonical crate-level module:

```rust
pub use tsl_algorithm::dataparallel;
```

The ownership rule is more important than the exact file: users should not have
to think "algorithm helper" when they choose a primitive vector policy, and
`algo` should not provide a second spelling for that policy.

### Generated Mapping Facts

Rust cannot use C++-style partial specialization. It needs trait impls.

The current helper direction already has a mapping trait:

```rust
pub trait VectorFor<Profile, T> {
    type Vec: StaticSimdVector<BaseType = T>;
}
```

That concept should become the first-class generated mapping for
`dataparallel` policies.

Conceptually:

```rust
impl VectorFor<Profile, i32> for dataparallel::Fixed<8> {
    type Vec = Simd<i32, Avx2>;
}

impl VectorFor<Profile, i32> for dataparallel::Native {
    type Vec = Simd<i32, Avx2>;
}

impl<Profile, T, const N: usize> VectorFor<Profile, T>
    for dataparallel::Generic<N>
where
    Simd<T, Generic<N>>: StaticSimdVector<BaseType = T>,
{
    type Vec = Simd<T, Generic<N>>;
}
```

The trait may stay in `tsl_algorithm.rs` at first if that keeps the slice small,
but the API should be documented as generated-TSL vector mapping, not
algorithm-helper-private vocabulary.

### Primitive Convenience Wrapper Shape

The canonical primitive call remains:

```rust
tsl::add::<Vec>(left, right)
```

A policy facade is possible but heavier:

```rust
pub fn add<Policy, T>(
    _policy: Policy,
    left: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType,
    right: <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType,
) -> <<Policy as VectorFor<Profile, T>>::Vec as SimdVector>::RegisterType
where
    Policy: VectorFor<Profile, T>,
    <Policy as VectorFor<Profile, T>>::Vec:
        StaticSimdVector<BaseType = T> + detail::primitives::AddImpl,
{
    crate::tsl_profile::add::<<Policy as VectorFor<Profile, T>>::Vec>(
        left,
        right,
    )
}
```

The implemented facade lives in the generated profile-local `algo` module. The
important part is the same as C++: compute `Vec` from `(Profile, Policy, T)`,
then forward to the canonical `add::<Vec>`.

### Rust Ergonomics Caveat

Rust can express parameter types that depend on `Policy` and `T`, but inference
will not always infer `T` from an associated register type.

That means this may need explicit type annotation:

```rust
let out = tsl::profile::algo::add::<_, i32>(
    tsl::dataparallel::fixed::<8>(),
    left,
    right,
);
```

or another explicit spelling chosen during implementation.

This is a real ergonomics limitation. It does not make the design impossible,
and the first Rust primitive facades have been validated with real examples.
Future Rust facade expansion should still be judged by call-site clarity rather
than by expressibility alone.

## Relationship To Algorithm Helpers

Algorithm helpers already need `(T, data-parallel policy) -> Vec`.

The difference is that helpers own the loop:

```cpp
tsl::algo::transform_binary(policy, op, left, right, output, count);
```

whereas primitive facades only choose the vector for one primitive operation:

```cpp
tsl::add<tsl::dataparallel::fixed<8>, std::int32_t>(left_reg, right_reg);
```

Both should consume the same mapping facts.

The helper layer should stop owning the policy vocabulary. Public helper calls
should use the canonical namespace directly:

```cpp
tsl::algo::transform_binary(
    tsl::dataparallel::fixed<8>{},
    op,
    left,
    right,
    output,
    count);
```

Existing helper examples using `parallelism` should migrate to
`dataparallel`. Do not add helper-local aliases merely for ergonomics.

## Generation And Ownership Boundaries

### Static Assets

Static assets should own stable vocabulary and reusable helpers:

- C++ `tsl_dataparallel.hpp` or equivalent;
- Rust crate-level `dataparallel` module or equivalent top-level exposure;
- type aliases and traits that do not depend on profile contents;
- helper-loop code that operates through generated mapping traits.

### Generated Profile Facts

The compiler should generate profile-specific facts:

- fixed lane mappings;
- native mappings;
- whether a vector has static lane count;
- concrete `Simd<T, Extension>` chosen for a policy;
- required primitive support roots for helper/facade code.

These facts should be deterministic and generated from the same selected
specializations already used for current helper mappings.

### Primitive Facade Wrappers

Primitive wrappers should be generated from primitive render models, not
hand-written as large raw strings.

Reason: primitive signatures differ:

- unary/binary register operations;
- masks;
- immediates;
- source/target type conversions;
- memory access;
- gather/scatter;
- reductions;
- operations with special target vector types.

A hand-maintained static wrapper asset for every primitive would become the
same maintainability problem that the Rust helper facade just had.

The implementation started with one generated wrapper family, proved the shape,
then expanded by primitive category. Future categories should follow the same
path.

## Risks And Pushbacks

### Do Not Hide Hardware Semantics Too Much

The facade should decouple user code from extension names, but it should not
hide meaningful differences:

- `fixed<N>` is not `native`;
- `native` is not runtime dispatch;
- scalable vectors are not fixed-lane vectors;
- `generic<N>` is an explicit fallback, not an implicit rescue path.

### Do Not Promise Inference That Cannot Work

Register types are not enough to infer element type.

C++ and Rust should both document that register primitive facades usually need
explicit `T` or explicit `Vec`.

### Avoid Ambiguous Overloads

C++ overloads must not make this ambiguous:

```cpp
tsl::add<Vec>(left, right)
```

The convenience form should have a distinct template shape:

```cpp
tsl::add<Policy, T>(left, right)
```

where `Policy` is one of the `tsl::dataparallel` policy types.

### Rust May Not Benefit Enough For Every Primitive

Rust can model the facade, but the syntax may be heavy.

The design should be validated with real examples. If Rust primitive facades
are not ergonomic, Rust can still benefit from first-class `dataparallel`
policies through helpers and type aliases while keeping direct primitive calls
mostly `add::<Vec>`.

### Keep Expansion Shape-Gated

The first implementation used `add` to prove the shape before broadening.
Future expansion should keep the same discipline.

Every new family should prove:

- namespace/module placement;
- generated mappings;
- overload/trait bounds;
- static/scalable rejection rules;
- examples;
- generated build verification.

## Incremental Implementation Plan

### Current Implementation State

The current implementation has the foundational policy vocabulary and mapping
facts in place:

- C++ exposes `tsl::dataparallel::{native, fixed<N>, generic<N>}` and
  `simd_for_t<Policy, T>`.
- Rust exposes the canonical crate-level `dataparallel` module and generated
  `VectorFor` mappings.
- Algorithm helpers consume the canonical policy vocabulary directly and do not
  re-export helper-local `parallelism`.
- C++ emits primitive policy facades for pure unary/binary register transforms,
  unmasked predicates, mask-only operations, data-parallel reductions, and
  target-base conversions, plus plain contiguous memory access, such as
  `add<Policy, T>`, `mul<Policy, T>`,
  `less_than<Policy, T>`, `unequal_zero<Policy, T>`,
  `mask_true<Policy, T>`, `mask_binary_and<Policy, T>`,
  `hadd<Policy, T>`, `count_matches<Policy, T>`, and
  `cast<Policy, FromT, ToT>`, `load<Policy, T, Aligned>`, and
  `store<Policy, T, Aligned>`. The canonical `primitive<Vec>` form remains
  unchanged.
- Rust emits experimental profile-local facades for pure unary/binary register
  transforms, unmasked predicates, mask-only operations, data-parallel
  reductions, target-base conversions, and plain contiguous memory access, such
  as
  `tsl_profile::algo::add(policy, left, right)`,
  `tsl_profile::algo::mul(policy, factor1, factor2)`,
  `tsl_profile::algo::less_than(policy, left, right)`,
  `tsl_profile::algo::hadd(policy, vec)`, and
  `tsl_profile::algo::cast(policy, data)`,
  `tsl_profile::algo::load(policy, ptr)`, and
  `tsl_profile::algo::store(policy, ptr, data)`. The canonical
  `primitive::<Vec>` form remains unchanged.

The facade still intentionally excludes masked value operations, scalar-only
utilities, windowing conversions with immediates, masked/gather/scatter/
compress memory operations, and load-convert forms. Rust keeps a different call
shape because Rust cannot overload the existing `primitive::<Vec>` function.

### Slice 1: Canonical Policy Vocabulary

Introduce canonical `dataparallel` vocabulary without changing behavior.

C++:

- add static policy namespace under `tsl::dataparallel`;
- update helper APIs and examples to consume `tsl::dataparallel` directly;
- do not add `tsl::algo::dataparallel` or `tsl::algo::parallelism` aliases.

Rust:

- expose a canonical crate-level `dataparallel` module or equivalent top-level
  spelling;
- update helper APIs and examples to consume canonical `dataparallel`;
- do not re-export `dataparallel` through profile-local `algo` modules.

Validation:

- generated C++ and Rust projects contain the canonical policy vocabulary;
- helper examples build after migrating to canonical `dataparallel` spelling.

### Slice 2: Promote Mapping Facts

Move the conceptual ownership of vector mappings from helper-only support to
generated TSL data-parallel support.

C++:

- add `tsl::dataparallel::simd_for_t<Policy, T>`;
- keep `inferred_simd_t<T, N>` and `native_simd_t<T>` as aliases.

Rust:

- document and expose `VectorFor<Profile, T>` as the generated mapping trait
  for `dataparallel` policies;
- adjust names only if the migration can remain small and clear.

Validation:

- mapping tests for scalar, fixed hardware vector, native vector, and generic
  vector;
- static assertions for C++ fixed-lane mappings;
- Rust generated module assertions for `VectorFor` impls.

### Slice 3: C++ `add` Facade

Generate a policy facade for one pure binary primitive:

```cpp
tsl::add<tsl::dataparallel::fixed<8>, std::int32_t>(left, right)
tsl::add<tsl::dataparallel::native, std::int32_t>(left, right)
```

Keep `tsl::add<Vec>` unchanged.

Validation:

- one C++ example using the facade;
- scalar and AVX2 generated build;
- negative or static-assert coverage for unsupported fixed mappings where
  practical.

### Slice 4: Rust `add` Facade Experiment

Try the equivalent Rust facade for `add`.

The goal is not only "can it compile?" but "does it feel worth exposing?".

Validation:

- one Rust example with `fixed::<N>()`;
- one Rust example with `native()`;
- compare call-site clarity against `add::<Vec>`.

Decision point:

- if ergonomic enough, proceed to additional primitive families;
- if too noisy, keep Rust primitive-level policy facade limited and focus
  policy usage on helpers.

### Slice 5: Expand By Primitive Shape

Only after `add` proves the boundary, expand by shape:

1. pure unary/binary register transforms. Implemented for primitives with
   `v := v` or `v := (v, v)` shape and no target/type/immediate/generic
   parameters;
2. predicates. Implemented for unmasked predicates with `m := v` or
   `m := (v, v)` shape and no target/type/immediate/generic parameters;
3. mask operations. Implemented for mask-only operations with `m := ()`,
   `m := m`, or `m := (m, m)` shape and no target/type/immediate/generic
   parameters;
4. reductions. Implemented for data-parallel reduction shapes `s := v`,
   `s := (m, v)`, `s := (v, s)`, and `usize := m` with no
   target/type/immediate/generic parameters. Scalar-only utilities such as
   `usize := s` are intentionally excluded;
5. target-base conversions. Implemented for same-extension target-base
   representation changes with `v := v`, no immediate/axis/type/generic
   parameters, and a target vector obtained by rebinding the source vector base
   type. This covers `cast<Policy, FromT, ToT>` and
   `reinterpret<Policy, FromT, ToT>`. Windowing conversions such as
   `convert_up`/`convert_down`, extension-changing `extract`/`insert`, and
   load-convert forms remain pending because they need immediate and lane-window
   semantics in the facade contract;
6. plain contiguous memory operations. Implemented for unmasked
   `load<Policy, T, Aligned = false>(T const*)` and register
   `store<Policy, T, Aligned = false>(T*, register)` in C++, and unsafe
   profile-local Rust `algo::load::<_, T, ALIGNED>(policy, ptr)` /
   `algo::store::<_, T, ALIGNED>(policy, ptr, register)`. The alignment flag is
   an explicit compile-time promise. Masked load/store, gather/scatter,
   compress store, and load-convert forms remain pending because they need
   inactive-lane, index-vector, scale, and source/target-vector semantics in
   the facade contract.

Each category should add generator logic and tests at the same boundary.

## Resolved Decisions

- C++ uses `primitive<Policy, T>(...)` for source-only primitives and
  `primitive<Policy, FromT, ToT>(...)` for target-base conversions. This keeps
  the policy dimension first and mirrors helper call sites.
- Rust exposes primitive facades in profile-local `algo` modules. This avoids
  overloading the canonical `primitive::<Vec>` functions and keeps the
  profile-specific `VectorFor<Profile, T>` mapping in scope.
- `dataparallel` is canonical at the generated-library level. Algorithm modules
  consume it but do not re-export helper-local aliases.
- C++ `tsl::dataparallel::native` is a type marker. Helpers consume policy
  types directly and keep `std::size_t ParallelN` overloads as compatibility
  adapters that forward to `tsl::dataparallel::fixed<ParallelN>`.
- The first broad expansion includes pure register transforms, unmasked
  predicates, mask-only operations, reductions, target-base conversions, and
  plain unmasked contiguous load/store. It excludes masked value operations,
  scalar-only utilities, windowing conversions with immediates, masked/gather/
  scatter/compress memory operations, and load-convert forms.

## Future Work

- Masked value operations need an explicit inactive-lane contract before they
  get facades.
- Gather/scatter facades need an explicit index-vector, index-pointer, and
  scale contract. Existing helper-selected-row loading may continue to use
  `gather_narrow` internally without exposing a general primitive facade.
- Masked load/store and compress store need explicit inactive-lane and output
  mutation semantics.
- Windowing conversions, `convert_up`/`convert_down`, `extract`/`insert`, and
  load-convert forms need source/target lane-window semantics.
- Runtime CPU dispatch remains a separate layer and must not be hidden behind
  `dataparallel::native`.

## Current Recommendation

Keep `Vec`-based primitives as the ground truth and keep the implemented
policy facade as a thin generated convenience layer:

```text
(Policy, T) -> Vec -> existing primitive implementation
```

Continue expanding only by explicit primitive shape. Keep SVE/scalable vectors
represented through `native`, not `fixed<N>`, and keep advanced memory and
windowing conversions out of the facade until their contracts are explicit.
