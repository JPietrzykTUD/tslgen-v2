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
  it remains compiler-internal in the initial API. A future higher-level
  algorithm/dispatch layer may introduce a public zero-sized fixed-policy
  marker only when that layer demonstrates a concrete use for it.
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
- The implemented source-owned overload registry distinguishes primary and
  non-primary semantic forms without prescribing Rust spelling. For
  `count_distribution`, Rust exposes the primary `uniform` runtime form as
  `shift_left`/`shift_right` and projects the non-primary `per_lane` form as
  `shift_left_each`/`shift_right_each`. The compiler-oriented phrase
  `per_lane` does not leak into the public Rust method name. Immediate forms
  remain `shift_left_imm`/`shift_right_imm` independently.
- Rust composes comprehensive method-name distinctions in the stable order
  semantic overload form, immediate binding, then mask policy. For example,
  the masked immediate shift is `shift_left_imm_masked`, not
  `shift_left_masked_imm`; a zeroing form would be
  `shift_left_imm_masked_zero`. This ordering is independent of which sibling
  forms a selected profile emits and preserves authored names that already end
  in `_imm`, such as `mul_imm_masked`.
- `Shl` and `Shr` are not added merely to avoid a named overload suffix. Rust's
  portable SIMD supports scalar and vector right-hand sides through the
  operator traits, but masks large counts modulo the lane width; the current
  TSL shift contract instead produces zero or sign-fill values when a count is
  at least the lane width. Operator projection remains deferred until that
  target-independent semantic difference is deliberately resolved.
- The primary safe slice API uses `from_slice` and `copy_to_slice`. Both operate
  on the first logical vector-width elements of a longer slice and panic when
  the slice is too short. Ordinary use does not introduce a public
  `SliceTooShort` error or require `Result` handling.
- The initial API has no `try_from_slice` or `try_copy_to_slice` variants.
  Callers that need recovery can check `slice.len() >= N`; adding recoverable
  conveniences later would be backward-compatible and does not justify an
  initial public error or inconsistent `Option`/`Result` design.
- The source `payload_extent=vector` store is the form used by
  `copy_to_slice`. The non-primary `payload_extent=scalar` store has no vector
  operand and does not become a `Simd<T, N>` method or associated function. If
  the comprehensive primitive layer publicly retains every TSL primitive, it
  exposes scalar store as an explicitly unsafe free function such as
  `primitives::store_scalar(ptr, value)`; its final raw-module path remains a
  separate topology decision.
- Safe slice access selects the unaligned TSL load/store variant because a Rust
  slice guarantees element alignment, not vector alignment. Raw-pointer access
  is separate, explicitly `unsafe`, and documents the caller obligations
  derived from the selected TSL primitive.
- The initial raw-pointer methods are
  `unsafe Simd::<T, N>::from_ptr(*const T) -> Self` and
  `unsafe value.copy_to_ptr(*mut T)`. They read or write exactly `N`
  consecutive initialized `T` values through the vector-unaligned TSL forms;
  callers must provide ordinary `T` alignment and a valid range. No aligned
  raw-pointer variants are initially exposed because the required vector
  alignment follows the private profile-selected representation and has no
  stable public proof or contract yet.
- Rust standard operators are explicit, compiler-owned projections of
  compatible TSL primitives onto the owned vector type. Rust trait names and
  method spellings do not become `tsldata` primitive metadata, and renderers do
  not infer operator compatibility from target text.
- The initial standard-operator surface includes `Add`, `Sub`, and `Mul` for
  their admitted numeric element types, plus integer-only `BitAnd`, `BitOr`,
  `BitXor`, and `Not`. Float bit-pattern operations remain explicitly named
  primitive methods because Rust does not define scalar bitwise traits for
  `f32` or `f64`. Each admitted binary base operator also includes its ordinary
  assignment trait (`AddAssign`, `SubAssign`, `MulAssign`, `BitAndAssign`,
  `BitOrAssign`, or `BitXorAssign`) in the same slice.
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
- Propagate the implemented source-owned `PrimitiveOverload` fact through
  `Catalog.resolve_primitive_overload(...)` into a backend-neutral
  `ResolvedPrimitiveOverload | None` field on `LoweredSpecialization` before
  facade planning. `SelectedImplementation` already preserves the originating
  `Primitive`, so it needs no duplicate field. Do not reconstruct overload
  roles from parameter kinds or primitive-name branches.
- Project non-primary overload values through explicit Rust facade spelling
  policy keyed by typed `(axis, value)`, not by primitive name. The initial
  `count_distribution=per_lane` spelling is `_each`; primary values add no
  overload suffix. Unknown values fail facade validation until their Rust
  presentation is deliberately added.
- Compose the typed facade-name components in one place and in the settled
  order: overload suffix, `_imm`, then `_masked`/`_masked_zero`. Renderers,
  documentation, tests, and benchmark consumers receive the already-finalized
  name and do not repeat this ordering logic.
- Derive ordinary masked-computation receivers from typed parameter kinds: skip
  a leading control mask, select the first ordinary vector operand as `self`,
  and retain the mask as the first explicit method argument. Do not inspect
  parameter names, target text, or human documentation, and do not add
  Rust-specific receiver metadata to source data. Express genuine exceptions
  as explicit typed facade descriptors.
- Require a genuine owned vector operand before projecting a primitive as a
  `Simd<T, N>` method. A form such as `payload_extent=scalar` store, whose typed
  signature has no vector operand, is either a free function in the separately
  named comprehensive/raw primitive layer or is not publicly projected; it is
  never attached to `Simd<T, N>` merely to provide a namespace.
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
  convenience is deliberately omitted from the initial API; callers may check
  the slice length explicitly.
- Select the existing `aligned=false` TSL primitive for a normal slice. Keep
  the internal unsafe block small: the slice length check proves that the full
  vector-width pointer range is readable or writable.
- Keep raw-pointer load/store entry points separate and explicitly `unsafe`.
  Generate their `# Safety` documentation from the primitive's typed safety
  reasons. Do not expose a safe aligned variant without an alignment-bearing
  input type that can prove the stronger precondition.
- Spell the initial vector-unaligned raw methods `from_ptr` and `copy_to_ptr`,
  mirroring the safe `from_slice`/`copy_to_slice` direction. Do not initially
  emit aligned raw variants; revisit them only with an explicit stable
  alignment contract or alignment-bearing input abstraction.
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
  primitives to `core::ops::Add`, `Sub`, and `Mul`, plus integer-only
  `BitAnd`, `BitOr`, `BitXor`, and `Not`.
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
- Add `AddAssign`, `SubAssign`, `MulAssign`, `BitAndAssign`, `BitOrAssign`, and
  `BitXorAssign` alongside their admitted base operators; assignment does not
  introduce a second arithmetic contract. Named operations such as reductions,
  `min`, `max`, conversions, saturating arithmetic, float bit-pattern
  operations, and masked forms remain explicit methods unless a separate
  compatible mapping is agreed.
- Keep `Shl` and `Shr` out of the initial mapping. Revisit them only after the
  large-count contract is made compatible with the intended Rust operator
  semantics for both scalar and vector right-hand sides.
- Test operator syntax in an external consumer and compare its results with
  direct primitive calls across generic and representative hardware mappings.

## Open Design Questions

These are deliberately not settled by the initial ordering:

- Whether shift counts at least the lane width should retain the current TSL
  zero/sign-fill behavior or change to the modulo-width behavior used by Rust
  portable SIMD, and consequently whether `Shl`/`Shr` can be exposed without
  surprising Rust semantics.
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
- 2026-07-22: Agreed that the implemented source
  `count_distribution=per_lane` value is projected as the more idiomatic Rust
  suffix `_each`, yielding `shift_left_each` and `shift_right_each`; `per_lane`
  remains source/compiler vocabulary. The primary uniform forms remain
  unsuffixed and immediate forms retain `_imm`. `Shl`/`Shr` stay deferred
  because current TSL large-count behavior differs from Rust portable SIMD.
- 2026-07-22: Agreed that comprehensive Rust method names compose semantic
  overload form first, immediate binding second, and mask policy last. The
  resulting spellings include `shift_left_imm_masked` and
  `shift_left_imm_masked_zero`, never `shift_left_masked_imm`; authored `_imm`
  names such as `mul_imm` retain their natural `mul_imm_masked` form.
- 2026-07-22: Agreed that `payload_extent=vector` store feeds the friendly
  `copy_to_slice` method, while `payload_extent=scalar` store does not become a
  `Simd<T, N>` method or associated function because it has no vector operand.
  If retained in the public comprehensive primitive layer, scalar store is an
  explicitly unsafe free function; its final raw-module path remains open.
- 2026-07-22: Agreed that `Fixed<N>` is entirely compiler-internal in the
  initial Rust API. `Simd<T, N>` is the sole fixed-lane value spelling; a future
  algorithm/dispatch layer may add a public policy marker only when it has a
  concrete user-facing role.
- 2026-07-22: Agreed that the initial safe slice API has no
  `try_from_slice`/`try_copy_to_slice` variants. `from_slice` and
  `copy_to_slice` panic on a short slice, and callers needing recovery check
  `len() >= N`; recoverable conveniences can be added later without breaking
  the API.
- 2026-07-22: Agreed that the initial unsafe raw memory methods are
  `Simd::from_ptr` and `Simd::copy_to_ptr`. They use vector-unaligned TSL access
  and require a valid `N`-element range with ordinary `T` alignment. Aligned raw
  variants are deferred until the private profile-selected representation has
  a stable public alignment contract or proof type.
- 2026-07-22: Agreed that the initial standard-operator facade includes
  integer-only `BitAnd`, `BitOr`, `BitXor`, and `Not` in addition to the
  previously selected numeric `Add`, `Sub`, and `Mul`. Every admitted binary
  operator also receives its assignment trait in the same slice. Float
  bit-pattern operations remain named methods. `Shl` and `Shr` remain deferred
  pending their semantic contracts.
- 2026-07-22: The exceptional-value contracts required by Rust `Div` and `Rem`
  are settled and implemented by `arithmetic-contract-plan.md` Slices 1 through
  5. Their trait projection remains deferred until this plan implements the
  owned fixed-lane `Simd<T, N>` facade and its typed facade-planning boundary;
  the current zero-sized `Simd<T, Ext>` descriptor and its associated raw
  register type are not substitute public trait owners.
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
