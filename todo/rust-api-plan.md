# Generated Rust API Plan

## Purpose

This is the decision record and implementation plan for making the generated
Rust library sound, warning-clean, and straightforward for Rust programmers.
It is intentionally updated as design discussions settle decisions; open
questions are not treated as commitments.

The primary public fixed-lane value is `Simd<T, N>`, where `T` is the element
type and `N` is the logical lane count. Architecture extensions such as AVX2,
SSE, or NEON are implementation choices and must not be the ordinary user's
API.

## Agreed Direction

- The ordinary generated API is safe and expressed in logical SIMD concepts,
  especially element type and fixed parallel lane count.
- `Simd<T, N>` is the canonical owned fixed-lane type and means exactly `N`
  logical lanes of `T`. `Fixed<N>` is not part of that value's public spelling;
  it may remain an internal mapping concept or a higher-level algorithm marker.
- A public `(T, N)` shape is admitted only when `N == 1` for the scalar shape or
  `N * bits(T)` is one of the source-authored fixed vector widths. The current
  ordinary width ladder is 128, 256, and 512 bits; it is not an arbitrary
  `1..=64` lane range.
- Public shape validity is a source-owned, typed compiler fact. The Rust backend
  must not derive it from a `u64` mask representation, currently emitted
  hardware types, or target-text spellings. Adding a future width extends the
  source-owned ladder and its typed projections.
- Once a `Simd<T, N>` shape is admitted, it maps at compile time to a directly
  supported generated hardware vector when one exists for the compilation
  target; otherwise it falls back to the same-shape `Generic<N>`. It does not
  compose multiple narrower hardware registers.
- The more permissive generic substrate may remain an internal or advanced
  implementation facility for other whole-128-bit widths; those widths do not
  thereby become ordinary public `Simd<T, N>` shapes.
- `Native` maps at compile time, for the element type and compilation target,
  to the preferred directly supported generated vector implementation. Native
  vector values are ordinary statically typed values and may cross public
  function boundaries. The public spellings are `NativeSimd<T>` and
  `NativeMask<T>`.
- `NativeSimd<T>` and `NativeMask<T>` are profile-generated aliases, not new
  wrapper representations. A generated, documented, sealed mapping resolves
  them to the corresponding `Simd<T, N>` and `Mask<T, N>` for that element type
  and compiled machine profile. The public mapping trait is `SimdElement`; users
  may name it in generic bounds but cannot implement it. The current Rust
  backend admits only fixed-width extensions, so every native Rust alias has a
  compile-time lane count; future scalable Rust support is a separate
  API-design slice.
- The TSL machine profile is chosen once during generation or build
  configuration. Vector policy mappings and owned vector representations are
  static for that compiled artifact; they do not change at runtime. Hardware
  abstraction means that the same Rust source API can be recompiled for a
  different configured machine profile without naming its ISA extensions.
- Hardware-extension selection stays behind the compiler-owned representation
  mapping. A hardware-backed mapping exists only when its architecture and
  required target features are enabled for the compilation target; otherwise
  an admitted `Simd<T, N>` uses its generic implementation.
- Runtime CPU detection and dispatch belong to the higher-level helper or
  algorithm layer. That layer dispatches once into a statically specialized
  kernel rather than adding runtime representation choice to every vector
  operation.
- Statically targeted, architecture-specific operations may eventually exist
  in an explicitly advanced raw API, but their CPU preconditions must not leak
  into the ordinary fixed-lane API.
- Compiler-owned mappings select vector representations at compile time. Owned
  vector values own construction, lane data, arithmetic, comparisons,
  conversions, and storing themselves. Masks remain opaque logical values whose
  hardware representation is compiler-owned.
- The canonical fixed-lane mask spelling is `Mask<T, N>`, where `T` is exactly
  the element type of the corresponding `Simd<T, N>` and `N` is the same
  logical lane count.
- `Mask<T, N>` is an opaque owned `Copy` value. It does not borrow a vector or
  capability token, and passing or assigning it by value leaves the original
  usable. Its fields and hardware representation are private and fixed for the
  compiled profile; there is no runtime representation enum.
- Mask size, alignment, and byte layout are not stable API or FFI guarantees.
  Users do not transmute masks, serialize their raw bytes, or pass them directly
  through C FFI; `to_bitmask` and `to_array` provide explicit stable logical
  boundaries instead.
- The initial fixed-mask surface provides `splat`, `from_array`, `to_array`,
  `test`, `set`, `any`, `all`, `count_ones`, and
  `select(true_values, false_values)`, plus the standard `&`, `|`, `^`, and `!`
  operators. Lane indexing is a method rather than `Index<usize>` because a
  hardware mask representation cannot in general return a borrowed `bool`.
- `test(index)` and `set(index, value)` panic when `index >= N`, and
  `count_ones()` returns `usize`. `select` accepts and returns the exactly
  corresponding `Simd<T, N>`; selection of another element type requires an
  explicit mask cast first.
- Fixed masks implement `Copy`, `Clone`, logical `Debug`, `PartialEq`, `Eq`, and
  `Default`, where the default has every lane inactive. They also implement
  `BitAndAssign`, `BitOrAssign`, and `BitXorAssign` alongside the base bitwise
  operators. Equality and debug formatting observe logical lanes, never raw
  hardware representation bits.
- The initial mask facade has no `Index`, ordering, raw-representation access,
  or mask slice API. Arrays and normalized bitmasks are its explicit interchange
  forms; conveniences such as `first_set` may be added later without changing
  this contract.
- Fixed masks provide lossless `from_bitmask(u64)` and `to_bitmask() -> u64`
  for the agreed fixed shapes. Lane `i` maps to bit `i`; input bits above `N`
  are ignored and output bits above `N` are zero.
- Fixed masks with the same `N` are safely and explicitly convertible between
  element types through `cast::<U>()`. Conversion preserves every logical lane
  even when the source and destination use different selected representations;
  it is available only when the destination `Mask<U, N>` shape is admitted.
  Conversion between `NativeMask<T>` aliases is consequently available only
  when their resolved lane counts are equal.
- `tsldata` owns target-independent primitive semantics, signatures,
  attributes, and safety contracts. The typed compiler pipeline owns resolved
  primitive, profile, lane-count, and safety facts. The Rust facade owns only
  Rust-specific presentation such as slice methods and standard-library trait
  implementations.
- When a sound or complete language facade needs a semantic distinction that
  the typed model cannot express, extend the primitive data in `tsldata` and
  promote it to a validated, target-independent compiler fact. Such data may
  be motivated and initially consumed by Rust even when C++ overloading did not
  require it. The admission criterion is that the fact describes the primitive
  rather than Rust spelling; a backend must not recover it from primitive
  names, parameter names, prose, or target text.
- Rust method receiver placement is likewise backend presentation and does not
  add `receiver` or other Rust-specific annotations to `tsldata`. For an
  ordinary masked vector computation, the typed Rust projection treats the
  leading mask as an explicit control argument and uses the first ordinary
  vector operand as `self`. Mask-only algebra, constructors, semantic facade
  exceptions such as `select`, and pointer-oriented operations use their
  separately validated placements.
- Comprehensive masked method names encode their semantic policy unconditionally
  and independently of which sibling overloads happen to be emitted:
  `<primitive>_masked` preserves the receiver in inactive lanes, while
  `<primitive>_masked_zero` writes zero there. An active-lane operation with no
  pass-through/zeroing pair also uses `<primitive>_masked`. Low-level `_mask`
  and `_maskz` spellings are not part of the Rust facade.
- A primitive form with an `sImm` operand always uses the stable Rust suffix
  `_imm`, even when no runtime sibling currently exists. The immediate is a
  const generic rather than a runtime argument. An authored name that already
  ends in `_imm` is not suffixed again.
- The primary safe slice API uses `from_slice` and `copy_to_slice`. Both operate
  on the first logical vector-width elements of a longer slice and panic when
  the slice is too short. Ordinary use does not introduce a public
  `SliceTooShort` error or require `Result` handling.
- Safe slice access selects the unaligned TSL load/store variant because a Rust
  slice guarantees element alignment, not vector alignment. Raw-pointer access
  is separate, explicitly `unsafe`, and documents the caller obligations
  derived from the selected TSL primitive.
- Rust standard operators are explicit, compiler-owned projections of
  compatible TSL primitives onto the owned vector type. Rust trait names and
  method spellings do not become `tsldata` primitive metadata, and renderers do
  not infer operator compatibility from target text.
- Lane-wise comparisons remain explicitly SIMD operations: `simd_eq`,
  `simd_ne`, `simd_lt`, and the corresponding ordering methods return an opaque
  mask. `PartialEq` has the ordinary Rust whole-value meaning: `a == b` is true
  exactly when every corresponding lane is equal, and `a != b` is true when any
  corresponding lane is unequal. Ordering operators are not given an analogous
  reduction implicitly.
- Target-independent conditional selection uses the semantic argument order
  `(mask, true_values, false_values)`: an active lane selects `true_values` and
  an inactive lane selects `false_values`. Replace the current source-level
  `blend(mask, false_values, true_values)` operation with
  `select(mask, true_values, false_values)`, swapping the value arguments at
  every migrated call site so behavior is preserved.
- Integer lane addition, subtraction, and multiplication have deterministic
  wrapping semantics across backends. That target-independent contract must be
  made exact in `tsldata` before the corresponding Rust operators become part
  of the public API.
- Work is delivered as small coherent compiler/backend slices with focused
  generated-output and external-consumer tests.

## Initial Work Order

### 1. Establish diagnostic and release gates

Inventory and classify diagnostics before doing broad mechanical cleanup. This
step establishes the checks and baselines; it does not postpone soundness work
until every stylistic lint is fixed.

- Generated Rust compiler warnings should ultimately be zero.
- Safety-related Clippy diagnostics must be zero as part of the corresponding
  safety slice.
- Style-related Clippy lints need an explicit curated policy; not every lint is
  automatically a generated-code requirement.
- Rustdoc warnings should ultimately be zero.
- Add focused checks capable of rejecting invalid-value generation, unsafe
  target-feature execution, and unsafe representation assumptions.

### 2. Fix uninitialized-value generation

- Stop emitting initialized Rust integers, arrays, registers, or other values
  from `MaybeUninit::uninit().assume_init()`.
- Keep storage as `MaybeUninit<T>` until it is genuinely initialized where
  deferred initialization is necessary.
- Give `set_undef` a valid Rust representation while preserving its documented
  unspecified-value semantics.
- Remove allowances that hide invalid-value diagnostics.

The slice is complete when generated safe code cannot materialize an invalid
uninitialized Rust value and the representative generated value tests still
pass.

### 3. Fix `bit_cast`

- Remove the unconstrained safe public same-size transmute operation.
- Keep bit reinterpretation internal and restrict it to compiler-proven valid
  type pairs, or give any unavoidable unsafe helper an explicit internal
  contract.
- Prevent downstream safe code from constructing invalid values or duplicating
  ownership through generated support APIs.

### 4. Seal representation-bearing traits

- Seal `SimdVector`, `StaticSimdVector`, and other compiler-owned traits whose
  correctness depends on generated register, mask, or layout invariants.
- Remove the default mask implementation's undocumented assumption that any
  downstream `MaskType` can be inspected as initialized lane bytes.
- Put representation-specific mask behavior in compiler-owned generated
  implementations.

This slice addresses the current representation safety issue. The broader
question of which dispatch traits should remain visible in the final public API
is part of later API design.

### 5. Enforce static target features and isolate runtime dispatch

- The user requests an admitted logical `Simd<T, N>` shape, not AVX2, SSE,
  NEON, or another hardware extension.
- Promote the source-authored fixed vector-width or lane-shape declarations to
  one typed compiler owner. Generate sealed Rust support mappings only for the
  corresponding `(T, N)` pairs, including the scalar `N == 1` shape.
- Reject shapes outside that catalog at compile time without exposing
  architecture-specific bounds. In the current source model, for example,
  `Simd<i32, 4>`, `Simd<i32, 8>`, and `Simd<i32, 16>` are admitted while
  `Simd<i32, 17>` is not.
- Map each admitted `Simd<T, N>` to one directly supported generated hardware
  vector at compile time when an exact implementation exists for the element
  type and compilation target. Otherwise map it to the same-shape `Generic<N>`.
- Do not implement a fixed public vector by composing multiple narrower
  hardware registers. The portable fallback is the explicit generic vector
  implementation.
- Map `Native` at compile time for each element type and compilation target.
- Resolve both fixed and native representations from the configured TSL machine
  profile. For example, `Simd<i32, 8>` may select AVX2 or an AVX-512 256-bit
  implementation on matching x86 profiles, `Generic<8>` on an SSE-only or NEON
  profile, and a matching fixed-width SVE implementation on an SVE-256 profile.
- Never select an implementation merely because its representation appears in
  generated profile data; it must be executable and support the requested
  operation.
- Gate public hardware-backed mappings by target architecture and Rust target
  features rather than treating a Cargo profile feature as proof of CPU
  support. When the hardware mapping is unavailable, verify that fixed-shape
  selection behind `Simd<T, N>` resolves to `Generic<N>` and cannot execute
  target-specific instructions.
- Make the Rust build integration validate that the configured TSL machine
  profile and rustc target architecture/features agree. This is a build-profile
  consistency check, not runtime vector selection.
- Keep architecture-specific types and target-feature functions behind the
  public value facade.
- Put runtime CPU detection in higher-level helpers and algorithms. Those
  helpers select a compatible statically specialized kernel before calling its
  target-feature implementation.
- Add selection and external-consumer tests proving shape rejection and both
  representation branches for an admitted `Simd<T, N>`: exact hardware mapping
  when enabled and `Generic<N>` fallback when it is not. Add deterministic
  helper-dispatch tests using injectable CPU capabilities or emulation.

The primitive-versus-helper dispatch boundary is settled. The exact public
helper/algorithm dispatch spelling remains an open design question.

### 6. Remove remaining warnings under the agreed policy

- Eliminate remaining Rust compiler warnings at their translation or rendering
  source rather than applying broad crate-level suppression.
- Make Rustdoc warning-free.
- Apply the curated Clippy policy, fixing generator patterns such as redundant
  returns, casts, parentheses, assignments, and unsafe blocks when the resulting
  source is clearer and the compiler boundary remains simple.
- Keep focused allowances only where generated code has a documented reason.

## Public Rust Facade Slices

These slices follow the initial soundness and target-feature work. They are a
compiler-owned projection: they consume resolved compiler facts without
becoming another owner of primitive selection or semantics.

### 1. Establish the typed Rust facade boundary

- Introduce small frozen facade descriptors for safe memory methods and Rust
  operator mappings. Resolve them against canonical primitive identities and
  lowered specializations before rendering.
- Consume the selected primitive signature, attributes, caller-safety,
  lane-count, vector type, and profile availability from their existing typed
  owners. The Rust projection may decide Rust method and trait spellings,
  receiver placement, and documented slice failure behavior.
- Add source-owned semantic primitive or operand forms when signatures alone
  cannot identify stable overload roles. Parse and validate those forms into
  typed catalog facts before facade planning; do not add primitive-name
  branches to compensate for missing source semantics.
- Derive ordinary masked-computation receivers from typed parameter kinds: skip
  a leading control mask, select the first ordinary vector operand as `self`,
  and retain the mask as the first explicit method argument. Do not inspect
  parameter names, target text, or human documentation, and do not add
  Rust-specific receiver metadata to source data. Express genuine exceptions
  as explicit typed facade descriptors.
- Reject a facade before rendering when its primitive is missing or has an
  incompatible signature, attributes, safety contract, result type, or profile
  availability. Templates only format validated facade models.
- Replace or subsume the current Rust memory-facade name branches rather than
  adding another parallel classifier.
- Add owner-equivalence tests showing that facade availability follows the
  finalized emitted primitive facts, plus an additive probe for the next
  compatible primitive shape.

### 2. Add the safe slice memory API

- Generate `from_slice(&[T]) -> Self` on an owned vector and
  `copy_to_slice(self, &mut [T])` on a vector value.
- Require at least the logical lane count, operate on the first lane count of a
  longer slice, and use ordinary bounds-check panics for shorter slices.
- Do not add `SliceTooShort` to the primary public API. A recoverable
  `try_from_slice` or `try_copy_to_slice` convenience may be considered later
  without changing the primary contract.
- Select the existing `aligned=false` TSL primitive for a normal slice. Keep
  the internal unsafe block small: the slice length check proves that the full
  vector-width pointer range is readable or writable.
- Keep raw-pointer load/store entry points separate and explicitly `unsafe`.
  Generate their `# Safety` documentation from the primitive's typed safety
  reasons. Do not expose a safe aligned variant without an alignment-bearing
  input type that can prove the stronger precondition.
- Test slices shorter than, equal to, and longer than the lane count; verify
  that longer stores modify only the prefix. Include element-aligned but
  vector-misaligned storage and representative `Simd<T, N>`, native, hardware,
  and generic mappings.

### 3. Normalize arithmetic semantics for public operators

- Change the target-independent `tsldata` contracts for integer lane `add`,
  `sub`, and `mul` from backend-dependent overflow behavior to modular wrapping
  behavior.
- Reconcile every scalar, generic, C++, and Rust implementation with that
  contract; do not rely on C++ signed overflow or Rust build-mode overflow
  behavior.
- Add authored overflow cases and differential generated value tests that prove
  identical results for generic and hardware implementations.

### 4. Add Rust standard operators

- Define an explicit typed Rust operator mapping from compatible canonical TSL
  primitives to traits such as `core::ops::Add`, `Sub`, and `Mul`.
- Admit a mapping only when the resolved primitive has the required unmasked
  homogeneous shape, returns the same logical vector type, needs no unexpressed
  attribute or immediate, and is caller-safe.
- Generate the trait implementations on the owned public vector type and route
  them through the selected generated primitive. The safe trait implementation
  must not expose extension types or caller-unsafe primitive details.
- Keep lane-wise, mask-producing comparisons as named SIMD methods such as
  `simd_eq` and `simd_lt`; Rust comparison traits cannot express a mask result.
- Implement `PartialEq` separately as a whole-vector reduction of the scalar
  lane equality contract. `==` is true when all lane comparisons are true;
  `!=` is its ordinary negation and therefore true when any lane comparison is
  false. Do not give `<`, `<=`, `>`, or `>=` an implicit all-lanes or any-lane
  reduction through `PartialOrd`.
- Add assignment traits only after their base operators are established.
  Named operations such as reductions, `min`, `max`, conversions, saturating
  arithmetic, and masked forms remain explicit methods unless a separate
  compatible mapping is agreed.
- Test operator syntax in an external consumer and compare its results with
  direct primitive calls across generic and representative hardware mappings.

## Open Design Questions

These are deliberately not settled by the initial ordering:

- Whether `Fixed<N>` remains public solely as a higher-level algorithm-selection
  marker or becomes entirely compiler-internal.
- Whether optional recoverable `try_from_slice`/`try_copy_to_slice` methods are
  useful in addition to the primary panicking API.
- The exact naming and stability promise for advanced raw-pointer and aligned
  memory entry points.
- Which additional named primitives should receive Rust standard-operator or
  assignment-trait projections after `Add`, `Sub`, and `Mul`.
- The exact target-independent source shape and form vocabulary for overloaded
  primitive families that a non-overloading backend must expose under distinct
  names, including uniform and per-lane shift counts.
- The public helper/algorithm API that performs runtime CPU dispatch into a
  statically specialized kernel.
- Whether the C++ `dataparallel::fixed<N>` mapping should be updated to the same
  generic fallback contract. The active C++ base mapping currently provides
  scalar `fixed<1>` and generated exact hardware specializations, but no general
  `fixed<N> -> generic<N>` fallback.
- Which operations belong in a future advanced raw API and what stability
  promise that API receives.
- The final crate topology, feature model, package metadata, and distribution
  mechanism.

## Decision Log

- 2026-07-20: Agreed that the first work covers diagnostics, uninitialized
  values, `bit_cast`, representation-trait safety, unsupported instructions,
  and remaining warning cleanup in the order recorded above.
- 2026-07-20: Agreed that ordinary users request fixed logical SIMD lanes and
  that hardware extensions stay behind that API.
- 2026-07-20: Clarified that fixed and native representations are statically
  resolved. An admitted fixed shape uses an exact hardware implementation when
  available and otherwise falls back to `Generic<N>`; it does not compose
  narrower hardware vectors.
- 2026-07-20: Agreed that runtime CPU detection belongs to higher-level helpers
  and algorithms, which dispatch once into statically specialized kernels. It
  is not part of each primitive vector value or operation.
- 2026-07-20: Agreed that compiler-owned mappings select representations while
  opaque owned vector values own construction and ordinary value operations;
  masks keep compiler-owned representations.
- 2026-07-20: Clarified that hardware abstraction is source/API portability
  across generated or configured machine profiles. A compiled artifact has one
  static policy mapping and vector representation; primitive vector values do
  not change implementation at runtime.
- 2026-07-20: Agreed that the primary safe memory API is
  `from_slice`/`copy_to_slice`, operates on a slice prefix, panics when the
  slice is too short, defaults to unaligned access, and keeps raw-pointer access
  separately unsafe. No `SliceTooShort` error is part of ordinary use.
- 2026-07-20: Agreed that named `simd_*` comparisons return lane masks, while
  `Simd<T, N>` implements whole-vector `PartialEq`: `==` requires every lane to
  compare equal and `!=` is true when any lane does not.
- 2026-07-20: Agreed that conditional selection uses
  `(mask, true_values, false_values)`, with active lanes choosing the first
  value. Replace `blend(mask, false_values, true_values)` with
  `select(mask, true_values, false_values)` and migrate call sites by swapping
  their value arguments to preserve behavior.
- 2026-07-20: Agreed on `Mask<T, N>`, with `T` and `N` matching the associated
  fixed `Simd<T, N>`, and on the initial construction, lane access, reduction,
  selection, and bitwise-operation surface recorded above.
- 2026-07-20: Agreed that fixed masks expose normalized, lossless `u64` bitmask
  conversion for the current fixed shapes and allow explicit conversion between
  element types whenever the logical lane count is unchanged and the
  destination mask shape is admitted.
- 2026-07-20: Agreed that masks are opaque owned `Copy` values with private,
  compile-time profile-selected storage and no stable raw layout or direct FFI
  contract. Stable logical interchange uses arrays or normalized bitmasks.
- 2026-07-20: Agreed that same-lane-count fixed mask conversion is spelled
  `cast::<U>()`. The destination shape must be admitted; native-mask aliases are
  convertible only when their resolved lane counts match.
- 2026-07-20: Agreed on `NativeSimd<T>` and `NativeMask<T>` as generated aliases
  to the profile-selected `Simd<T, N>` and `Mask<T, N>`, resolved through a
  documented sealed `SimdElement` mapping rather than a second wrapper
  representation.
- 2026-07-20: Completed the initial mask contract: lane access is bounds-checked,
  `count_ones` returns `usize`, `select` requires the matching vector element
  type, logical masks implement the ordinary copy/equality/debug/default and
  bitwise-assignment traits, and raw/indexed/slice mask access remains outside
  the initial facade.
- 2026-07-20: Agreed that Rust receiver placement remains a typed facade
  decision, not `tsldata` metadata. Ordinary mask-first vector computations use
  the first ordinary vector operand as `self` and keep the control mask as the
  first explicit argument; semantic exceptions are explicit facade mappings.
- 2026-07-20: Agreed that comprehensive Rust masked methods use the stable
  semantic suffixes `_masked` for pass-through or sole active-lane forms and
  `_masked_zero` for zeroing forms. Public names never expose `_maskz` and do
  not change when sibling overload availability changes.
- 2026-07-20: Agreed that every `sImm` form uses an unconditional `_imm`
  suffix and exposes the immediate as a Rust const generic. Existing `_imm`
  source names are not doubled, and adding a runtime sibling cannot rename the
  immediate method.
- 2026-07-20: Agreed that `tsldata` may and should gain further
  target-independent primitive metadata when a language facade needs semantic
  facts that are not yet representable, following implementation safety as an
  existing precedent. A Rust-only need is sufficient motivation when the fact
  itself describes the primitive rather than Rust spelling. The compiler
  promotes and validates those facts; Rust and C++ may present them
  differently, but neither backend may reconstruct them through
  primitive-specific special cases.
- 2026-07-20: Agreed that slice conveniences and Rust standard traits are typed
  Rust-backend projections over compiler-owned primitive facts rather than
  Rust-specific metadata in `tsldata` or renderer inference.
- 2026-07-20: Agreed to make integer lane `add`, `sub`, and `mul` explicitly
  wrapping and backend-independent in `tsldata` before exposing them through
  Rust's standard operator traits.
- 2026-07-20: Agreed that `Simd<T, N>` is the canonical fixed-lane owned value.
  Ordinary public shapes are the scalar case plus `(T, N)` pairs from the
  source-authored 128/256/512-bit width ladder, not every lane count through 64.
  An admitted shape maps statically to exact hardware or same-shape generic
  storage; other whole-128-bit generic widths may remain advanced-only.
