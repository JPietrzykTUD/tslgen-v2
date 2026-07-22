# Generated Rust API Plan

## Goal

Generate a sound, warning-free Rust library whose ordinary API is expressed in
logical SIMD values rather than architecture extensions. This document records
the settled public contract and the implementation work needed to provide it.

## Ownership Boundary

This work is a compiler-owned Rust projection over the existing TSL product; it
is not a second SIMD library or a second primitive implementation path.

- `tsldata` owns which primitives exist, their language-neutral operations,
  signatures, operand and overload roles, safety, exact behavior, generic and
  hardware implementations, tests, and availability. Required new primitives
  or metadata land as separate projection-neutral source-data slices and must
  work through the ordinary C++ and Rust primitive APIs before the facade uses
  them.
- Compiler core owns the typed schema, validation, selection, lowering, and
  propagation of those facts. It may define semantic enum vocabulary, but it
  never decides which primitive has a meaning by inspecting its name,
  parameter names, documentation, or target text.
- The Rust backend owns only Rust spelling and boundary adaptation: public
  types, receiver placement, trait and method names, ownership forwarding,
  bounds or length checks, packaging, and dispatch presentation. It maps typed
  source semantic facts to Rust conventions and delegates to the same finalized
  primitive implementation used by the lower-level generated API.
- Facade code must not contain lane-wise primitive algorithms, arithmetic edge
  handling, count normalization, conversion rules, mask representation logic,
  ISA selection, or a parallel registry keyed by primitive names. If a needed
  fact is absent, extend `tsldata` and its typed compiler model first.

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
7. Complete and independently verify the missing projection-neutral source
   contracts and primitives, including negation, wrapping shifts, lane-preserving
   conversion, and runtime lane access. Only then add the typed facade planner
   and the public projections below.

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
- Generic code expresses that compile-time constraint through the public sealed
  `SupportedSimd<const N: usize>` marker implemented by supported element
  types:

  ```rust
  fn process<T, const N: usize>(value: Simd<T, N>)
  where
      T: SimdElement + SupportedSimd<N>,
  {
      // ...
  }
  ```

  Downstream crates may use the bound but cannot add shapes. Representation
  selection remains private and is not part of the trait's stable contract.
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
dispatcher.transform_binary(
    tsl::ops::Add,
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
- An operation is an explicit value. Generated built-ins such as `tsl::ops::Add`
  are zero-sized values; a stateful user operation can be passed by mutable
  reference. Both use the existing typed algorithm-kernel contracts rather than
  a hand-maintained runtime list.

Convenience functions expose the same algorithms without an explicit value:

```rust
tsl::algorithms::transform_binary(
    tsl::ops::Add,
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
- `lane(&self, index) -> T` and `set_lane(&mut self, index, value) -> ()`
  panic when `index >= N`. The initial facade has no functional `with_lane`
  sibling.
- They delegate to target-independent runtime-index source primitives
  `extract_value_at` and `insert_value_at`; the mutating wrapper assigns the
  returned vector to `self`. The existing compile-time-indexed `extract_value`
  and `insert_value` remain unchanged.
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

- `test(&self, index) -> bool` and `set(&mut self, index, value) -> ()` panic
  when `index >= N`; `count_ones` returns `usize`. The initial facade has no
  functional mask setter.
- `set` delegates to a target-independent value-returning `set_mask_lane`
  source primitive and assigns its result to `self`; `test` uses the existing
  integral-mask conversion and `test_imask` contracts.
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
floating negation toggles only the sign bit. Thus signed zero and infinity swap
sign, while every other NaN payload bit is preserved and its sign bit is
toggled. Unsigned vectors do not implement `Neg`.

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

Shift operators accept every owned or borrowed integer scalar right-hand-side
type in the generated Rust scalar vocabulary. Per-lane counts use an owned or
borrowed `Simd<T, N>` matching the shifted value and follow the ordinary four
owned/borrowed vector combinations. Assignment accepts every corresponding
scalar or per-lane form. The source primitive family owns the supported scalar
count types and defines the effective count as the unsigned count bit pattern
modulo `bits(T)`, including for negative signed counts. Operator wrappers only
forward the typed count; they do not truncate, reduce, or otherwise normalize it.

### Conversion

Friendly numeric conversion preserves the logical lane count:

```rust
let result: Simd<U, N> = value.cast::<U>();
```

- `Simd<U, N>` must be an admitted shape.
- A new target-independent `convert_lanes` source primitive takes an explicit
  target vector type, requires equal source and target lane counts, and owns the
  generic baseline plus any hardware specializations. The source/compiler
  return model must therefore represent a target SIMD type rather than only a
  target base type within the source extension.
- The source primitive spells the exact language-neutral per-lane conversion
  rules, including integer truncation or extension, integer/float rounding,
  truncating and saturating float-to-integer conversion, and `NaN -> 0` for
  float-to-integer conversion. The Rust facade documents this contract as
  matching scalar `as`; neither the facade nor the Rust backend implements it.
- The current register-width `cast`, which may change lane count and has
  backend-dependent edge behavior, remains available through the existing
  generated primitive API and is not the facade method's semantic owner.

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

The ordinary facade is profile-invariant. A method is included when a generic
implementation exists. The selected profile may replace that baseline with a
hardware implementation; if it lacks the specialization, the call falls back
to generic. A primitive without a generic baseline remains available only
through the profile-specific lower-level generated API.

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
- Curated traits and methods are selected from source-authored typed operation,
  guarantee, operand-role, overload, conversion, memory, and safety facts. The
  Rust backend may map those semantic enums to Rust spellings, but it has no
  primitive-name-to-facade table.
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
   typed selection and lowering together with the semantic operation,
   guarantee, operand-role, conversion, memory, and safety facts consumed by
   the facade. Add `ResolvedPrimitiveOverload | None` to
   `LoweredSpecialization`; do not reconstruct source facts in the Rust backend.
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
9. Add the projection-neutral target-vector return and scalar-count type
   capabilities required by `convert_lanes` and wrapping shifts, and carry them
   through selection, lowering, backend validation, and generated value tests.
10. Emit curated facade items only when their required typed source operations,
    roles, guarantees, primitives, and implementations are present. Every
    canonical wrapper performs only its documented Rust boundary adaptation and
    then calls the finalized primitive implementation; it never synthesizes TSL
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
- Each new source prerequisite passes ordinary generated C++ and Rust
  build/value verification before facade projection tests are added.
- Owner-equivalence tests prove that facade eligibility and naming consume the
  typed source facts, and an additive or rename probe proves that no primitive
  name classifier or second registry exists.
- Generated-wrapper tests prove that canonical facade bodies contain only
  bounds/length checks, ownership or type forwarding, and delegation to one
  finalized primitive implementation; edge semantics remain covered by the
  source primitive value tests.
- Representative generic and hardware profiles must produce identical
  target-independent results.
- Hardware/toolchain-dependent checks remain explicit, injectable, or reported
  as skipped.
