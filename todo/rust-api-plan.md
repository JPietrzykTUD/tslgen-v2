# Generated Rust API Plan

## Goal

Generate a sound, warning-free Rust library whose ordinary API is expressed in
logical SIMD values rather than architecture extensions. This document records
the settled public contract and the implementation work needed to provide it.

## Implementation Order

1. Establish compiler-warning, Clippy-safety, rustdoc, invalid-value,
   target-feature, and representation-invariant gates.
2. Remove invalid uninitialized-value generation. Keep deferred storage as
   `MaybeUninit<T>` until initialized and give `set_undef` a valid Rust
   representation.
3. Remove the unconstrained safe public `bit_cast`. Restrict internal
   reinterpretation to compiler-proven valid type pairs.
4. Seal representation-bearing traits and remove undocumented mask/layout
   assumptions from their public contracts.
5. Prevent unsupported target instructions from executing. Validate the
   configured machine profile against rustc architecture/features and use the
   generic fallback when an exact hardware mapping is unavailable.
6. Remove remaining compiler and rustdoc warnings at their generator source,
   then apply a small documented Clippy policy without broad crate-level
   suppression.
7. Add the missing source-owned negation and wrapping-shift contracts, then the
   typed facade planner and the public value, mask, memory, conversion,
   primitive-method, operator, packaging, and dispatch projections below.

## Public API Contract

### Crate, features, and distribution

The generated product is one ordinary, pre-generated Cargo library crate. It is
distributed as Rust source through a registry, Git, or a path dependency; a
consumer build never runs `tslc`. Canonical releases contain the supported
generated profiles, while a custom corpus emits the same package layout for
private distribution.

The ordinary facade is available from the crate root:

```rust
use tsl::{Mask, NativeMask, NativeSimd, Simd};
```

Profile and target implementation modules are not required in ordinary imports
or documentation. Existing generated primitive entry points remain available
with their settled visibility and safety.

The library core is unconditionally `#![no_std]`. Cargo features are additive:

```toml
[features]
default = []
std = []
runtime-dispatch = ["std"]
```

- SIMD values, masks, static profile selection, and the complete primitive API
  use only `core`.
- Machine profiles and ISAs are not Cargo features. Static mapping is selected
  from the compilation target's architecture and target features, with
  `Generic<N>` as the fallback.
- The package declares normal edition, `rust-version`, license, repository,
  documentation, and README metadata from release configuration rather than
  hard-coding consumer-local facts.

### Fixed vectors and profile selection

The canonical owned value is:

```rust
Simd<T, N>
```

- `T` is the element type and `N` is the logical lane count.
- `Fixed<N>` is compiler-internal and is not part of the initial public API.
- A shape is public when `N == 1`, or when `N * bits(T)` is a source-authored
  fixed width. The current ordinary widths are 128, 256, and 512 bits.
- An admitted shape maps statically to one exact hardware implementation when
  the compilation target supports it; otherwise it maps to `Generic<N>`.
- A fixed vector is never composed from multiple narrower hardware registers.
- The mapping is fixed for the compiled artifact. There is no runtime
  representation enum and hardware extensions such as AVX2, SSE, or NEON do not
  appear in ordinary signatures.
- Vector and mask size, alignment, and byte layout are private. They have no
  stable layout, serialization, transmute, or direct FFI guarantee.

The public native aliases are:

```rust
NativeSimd<T>
NativeMask<T>
```

They are profile-generated aliases to the selected `Simd<T, N>` and
`Mask<T, N>`. A public sealed `SimdElement` mapping trait exposes the associated
types for generic bounds without allowing downstream implementations. The
initial Rust backend supports fixed-width native mappings only.

### Runtime dispatch

Runtime dispatch is an optional algorithm-level facility behind the
`runtime-dispatch` feature. It does not alter `Simd<T, N>` or place a runtime
tag in vector values.

The explicit API uses a hardware-neutral dispatcher:

```rust
let dispatcher = tsl::Dispatcher::new();
dispatcher.transform_binary::<tsl::primitive::Add>(
    &left,
    &right,
    &mut output,
);
```

- `Dispatcher::new()` is infallible because the generic implementation is
  always available.
- A dispatchable algorithm is emitted only when it has a generic baseline;
  every table slot then selects the best detected implementation or that
  baseline.
- Detection occurs once per dispatcher and selects a table of whole-algorithm
  entry points. Profile-specific vector types remain inside those entry points.
- Dispatch never occurs per vector operation or per loop iteration.
- The concrete algorithm names and operation tags come from the existing typed
  algorithm facade rather than a hand-maintained runtime list.

Convenience functions expose the same algorithms without an explicit value:

```rust
tsl::algorithms::transform_binary::<tsl::primitive::Add>(
    &left,
    &right,
    &mut output,
);
```

They delegate to one process-global cached `Dispatcher`; they do not own a
second detection, selection, or implementation table.

### Vector construction and observation

```rust
Simd::<T, N>::LANES
Simd::<T, N>::splat(value)
Simd::<T, N>::from_array(values)
value.to_array()
value.lane(index)
value.set_lane(index, new_value)
```

- `From<[T; N]> for Simd<T, N>` and `From<Simd<T, N>> for [T; N]` are provided.
- `lane` and `set_lane` panic when `index >= N`.
- There is no `Index`, `IndexMut`, `as_array`, `as_mut_array`, `AsRef`, or
  `AsMut`; these would require references into private selected storage.
- Vectors implement logical `Copy`, `Clone`, array-style `Debug`, zero-valued
  `Default`, and whole-vector `PartialEq`. Integer vectors also implement `Eq`.
- `Hash` and iteration traits are not part of the initial facade.

### Masks

The fixed mask is:

```rust
Mask<T, N>
```

`T` and `N` match the associated `Simd<T, N>`. It is an opaque owned `Copy`
value with private profile-selected storage.

The initial mask API provides:

```rust
Mask::splat(value)
Mask::from_array(values)
mask.to_array()
mask.test(index)
mask.set(index, value)
mask.any()
mask.all()
mask.count_ones()
mask.select(true_values, false_values)
Mask::from_bitmask(bits)
mask.to_bitmask()
mask.cast::<U>()
```

- `test` and `set` panic when `index >= N`; `count_ones` returns `usize`.
- Bit `i` corresponds to lane `i`. Input bits above `N` are ignored and output
  bits above `N` are zero.
- `cast::<U>()` preserves logical lanes and requires an admitted
  `Mask<U, N>`. Native masks are convertible only when their resolved lane
  counts match.
- Masks implement logical `Copy`, `Clone`, `Debug`, `Default`, `PartialEq`,
  `Eq`, `&`, `|`, `^`, `!`, and the corresponding assignment traits.
- There is no mask indexing, ordering, slice API, or raw-representation API.

### Memory

The ordinary safe API is:

```rust
Simd::<T, N>::from_slice(source)
value.copy_to_slice(destination)
```

- Both use the first `N` elements and panic when the slice is shorter.
- A longer store modifies only the first `N` elements.
- They use the source `aligned=false` primitives because a Rust slice proves
  element alignment, not private vector alignment.
- There is no initial `SliceTooShort`, `try_from_slice`, or
  `try_copy_to_slice`; recovering callers can check `len() >= N`.

The curated raw-pointer API is:

```rust
unsafe { Simd::<T, N>::from_ptr(source) }
unsafe { value.copy_to_ptr(destination) }
```

Each operation reads or writes exactly `N` initialized `T` values and requires
ordinary `T` alignment and a valid range. No aligned raw variant is exposed
until the selected representation has a stable public alignment proof.

The source `payload_extent=vector` store backs `copy_to_slice`. A scalar-payload
store has no vector receiver and remains an explicitly unsafe generated free
function.

### Comparisons and selection

- `simd_eq`, `simd_ne`, `simd_lt`, `simd_le`, `simd_gt`, and `simd_ge` return
  `Mask<T, N>`.
- `PartialEq` has ordinary whole-value meaning: `a == b` requires every lane to
  compare equal; `a != b` is its negation.
- `PartialOrd` is not implemented; ordering operators do not silently choose an
  all-lanes or any-lane reduction.
- Selection uses `(true_values, false_values)` on a mask. Active lanes choose
  the first argument:

```rust
mask.select(true_values, false_values)
```

The source primitive must likewise be
`select(mask, true_values, false_values)`, replacing the former reversed
`blend(mask, false_values, true_values)` contract.

### Standard operators

The initial vector operator set is:

- Numeric: `Add`, `Sub`, `Mul`, `Div`, and `Rem`.
- Signed-integer and floating: unary `Neg`.
- Integer-only: `BitAnd`, `BitOr`, `BitXor`, `Not`, `Shl`, and `Shr`.
- Every binary operator also has its assignment trait.
- Float bit-pattern operations remain named methods.

Every binary vector and fixed-mask operator supports:

```rust
Simd op Simd
&Simd op Simd
Simd op &Simd
&Simd op &Simd
```

Assignment accepts an owned or borrowed right-hand side. All forwarding
implementations delegate to the canonical owned operation.

Unary `Neg` accepts an owned or borrowed value. It delegates to a new
target-independent source `neg` primitive rather than constructing `0 - value`
in the facade. Signed integer negation is wrapping, including `MIN -> MIN`;
floating negation follows an explicit source contract covering signed zero and
NaN behavior. Unsigned vectors do not implement `Neg`.

Integer `add`, `sub`, and `mul` must have exact wrapping semantics in
`tsldata` before their traits are emitted. The implemented arithmetic contracts
for `div` and `mod` provide truncating integer behavior, defined signed
`MIN / -1` and `MIN % -1` results, zero-divisor failure, IEEE floating
division, truncating floating remainder, and active-lane-only masked behavior.
The facade delegates to those primitives and does not reimplement the contract.

The existing `shift_left` and `shift_right` primitives retain their established
large-count contracts: zeroing for left shift and the source-selected sign- or
zero-filling behavior for right shift. New target-independent
`shift_left_wrapping` and `shift_right_wrapping` primitives reduce uniform and
per-lane counts modulo the lane bit width. `Shl`, `Shr`, `ShlAssign`, and
`ShrAssign` delegate only to the wrapping primitives. Signed right shift is
arithmetic and unsigned right shift is logical. Immediate and floating
bit-pattern shifts remain named methods rather than operators.

### Conversion

Friendly numeric conversion preserves the logical lane count:

```rust
let result: Simd<U, N> = value.cast::<U>();
```

- `Simd<U, N>` must be an admitted shape.
- A new or normalized target-independent source primitive must define exact
  scalar-style overflow, rounding, saturation, and NaN behavior.
- The current register-width `cast`, which may change lane count and has
  backend-dependent edge behavior, remains available through the existing
  generated primitive API and is not used to implement this method.

Friendly bit-pattern conversion is limited initially to same-width pairs:

```rust
Simd<f32, N>::to_bits() -> Simd<u32, N>
Simd<f32, N>::from_bits(Simd<u32, N>)
Simd<f64, N>::to_bits() -> Simd<u64, N>
Simd<f64, N>::from_bits(Simd<u64, N>)
```

General register reinterpretation remains available through the existing
generated primitive API. The facade exposes no unconstrained public `bit_cast`.

### Comprehensive primitive methods

Existing generated primitive functions retain their current visibility,
caller-safety, target gating, and ownership.

A representable vector or mask primitive with a coherent receiver is
additionally exposed as an inherent method; no extension-trait import is
required. A caller-unsafe primitive remains an `unsafe fn` with its existing
typed safety contract. A primitive without a coherent receiver remains a
generated free function.

Receiver and naming rules are uniform:

- For an ordinary mask-first vector operation, the mask remains the first
  explicit argument and the first ordinary vector operand becomes `self`.
- Pass-through masked forms use `_masked`; zeroing forms use `_masked_zero`.
- A sole active-lane masked form uses `_masked`.
- An `sImm` operand is a const generic and always contributes `_imm`.
- The source overload `count_distribution=per_lane` contributes `_each`;
  its primary uniform sibling contributes no suffix.
- Name components are composed once in this order: overload, `_imm`, mask
  policy. Examples include `shift_left_each`,
  `shift_left_imm_masked`, and `mul_imm_masked`.
- Primitive names, parameter names, target text, and documentation prose are
  never inspected to infer roles or semantics.
- Curated inherent names are reserved. A collision with a mechanically
  projected method is a deterministic facade-planning error.

The comprehensive surface does not gain bespoke Rust aliases primitive by
primitive. Curated treatment is limited to established Rust traits and
conventions, construction or observation of public values, or cases where a
direct projection would be unsafe or materially misleading.

### Rust API conventions

- Pure functions that return a value, mask, conversion, or scalar observation
  are `#[must_use]`; mutation and store operations returning `()` are not.
- Thin facade methods, operator implementations, and forwarding functions are
  `#[inline]`. `#[inline(always)]` requires a demonstrated target-feature or
  code-generation need and is not emitted as a blanket policy.
- Panicking facade boundaries such as lane access, short-slice operations, and
  checked arithmetic use `#[track_caller]`.
- Rustdoc shows the logical API and includes examples plus accurate `# Panics`
  and `# Safety` sections. `Debug` exposes logical lanes, never private storage.
- `Send`, `Sync`, `Unpin`, and `'static` arise from the representation and are
  verified with compile tests; the facade adds no unnecessary manual unsafe
  implementations.
- CI denies compiler, rustdoc, and the selected Clippy warnings. The distributed
  crate does not use `#![deny(warnings)]` and does not hide generator defects
  behind broad crate-level lint suppressions.

## Compiler Implementation

1. Carry source-owned fixed shapes and the implemented overload facts through
   typed selection and lowering. Add `ResolvedPrimitiveOverload | None` to
   `LoweredSpecialization`; do not reconstruct it in the Rust backend.
2. Introduce small frozen Rust facade descriptors that consume finalized
   primitive signature, attributes, receiver roles, caller safety, lane shape,
   overload, and profile availability.
3. Finalize receiver placement and public names once before rendering. Rust
   source, rustdoc, tests, and benchmarks consume the same finalized facts.
4. Reject incompatible shapes, missing primitives, unknown overload spellings,
   unsafe/safe mismatches, target-feature mismatches, and name collisions before
   templates run.
5. Generate the sealed shape/native mappings, owned values, masks, curated
   methods, comprehensive inherent methods, and standard traits.
6. Keep target-specific types and implementation traits behind the public
   facade while preserving existing generated primitive entry points.
7. Render the root facade and additive Cargo features once from finalized
   profile facts. Do not use mutually exclusive ISA/profile Cargo features.
8. Build the explicit dispatcher and global convenience functions from one
   typed algorithm/profile dispatch plan. Runtime code must not rediscover
   requirements from profile names, primitive names, or target text.
9. Emit `Neg`, `Shl`, and `Shr` only when their exact source primitives and
   arithmetic contracts are present; the facade never synthesizes their
   semantics.

## Verification

- Generated Rust must build without compiler or rustdoc warnings.
- External-consumer tests cover the public API rather than only internal
  generated functions.
- Shape tests prove compile-time rejection, exact hardware selection when
  enabled, and same-shape generic fallback otherwise.
- Cargo checks cover the no-default-feature core and the additive `std` and
  `runtime-dispatch` configurations. External consumers do not require `tslc`.
- Dispatch tests use injected CPU facts to prove one-time selection, generic
  fallback, explicit/convenience equivalence, and that unsupported instructions
  are never entered.
- Value tests cover arrays, lanes, masks, slices, misalignment, conversions,
  operators, borrowed operands, integer overflow, wrapping and zeroing shift
  edges, negation edges, division failure, and logical formatting/equality.
- Representative generic and hardware profiles must produce identical
  target-independent results.
- Hardware/toolchain-dependent checks remain explicit, injectable, or reported
  as skipped.
