# Recommendation: Rust Immediate Dispatch

## Decision

Replace primitive-wide `sImm_type` usage with parameter-scoped metadata for
`sImm` parameters, and move Rust intrinsic const-generic quirks to the backend
intrinsic-call boundary.

Do not introduce a broad `immediate_policy` abstraction yet. Do not add a
`kind` field to `params`. Do not add a source-level `binding` field. Do not
model runtime arguments in this machinery.

The immediate action should be a small, test-backed slice:

```tsl
prim<v:=(v,sImm)> shift_right(data, shift):
  params:
    shift:
      type ui32
      value_range 0..base_bit_width(data)
```

and:

```tsl
prim<v:=(v,v,sImm)>[cast=reinterpret] insert(orig, data, index):
  params:
    index:
      type ui32
      value_range 0..lane_block_count
```

The signature already says `shift` and `index` are immediates through `sImm`.
The `params` block should refine named parameters from the signature. It should
not restate their signature kind.

## Critical Assessment Of The Current Design

The current design works for the first narrow Rust immediate cases, but it has
several structural flaws that are now surfacing in `insert` and `shift_right`.

### 1. `sImm_type` Is Primitive-Wide

Current shape:

```tsl
sImm_type:
  default ui32
  dispatch rust_const_match
  override:
    tsil:
      [sse, sse_vl, avx2, avx2_vl] si32
```

This is too coarse. It assumes there is one immediate-like parameter and one
set of immediate rules for the whole primitive. That is already uncomfortable
for `shift_right`, and it will break down harder if a primitive later has two
`sImm` parameters with different meanings.

The metadata should belong to the parameter name:

```tsl
params:
  shift:
    type ui32
    value_range 0..base_bit_width(data)
```

This is more maintainable because a reader can inspect `shift` or `index`
directly instead of mentally connecting a signature token to a separate
primitive-wide block.

### 2. `sImm_type` Mixes Three Different Concerns

The current block mixes:

- public parameter type, such as `ui32` or `si32`;
- selected implementation constraints, such as SSE/AVX2 vs AVX512 differences;
- Rust rendering strategy, such as `dispatch rust_const_match`.

Those facts change for different reasons. A public parameter type is source API
shape. A Rust intrinsic const type is backend ABI. A match over literal values
is a rendering bridge. Combining them in one source block makes the corpus less
declarative and harder to evolve.

### 3. `dispatch rust_const_match` Is Imperative

`dispatch rust_const_match` tells the backend how to generate code. It does not
describe what the TSL parameter means.

That harms readability and portability. The TSL file should say:

```tsl
params:
  shift:
    type ui32
    value_range 0..base_bit_width(data)
```

Then the Rust backend can decide whether the selected intrinsic can consume the
parameter directly or needs a literal-match bridge.

### 4. The Current Rust Path Is Incomplete

The current Rust const-forwarding logic is tied to `intrin_compose`. `insert`
uses direct `intrin<...>(orig, data, index)` bodies, so it needs the same
immediate handling through a shared intrinsic-call path.

The problem is not only "AVX512 wants `u32` while AVX2 wants `i32`." It is also
"direct intrinsic calls and composed intrinsic calls need one common immediate
argument model."

### 5. The Current Override Strategy Can Fight Rust's Wrapper Shape

Rust emits one public const-generic parameter type for an emitted primitive
shape. If we let extension-specific overrides freely change that public type,
we may end up forcing awkward wrapper splits or incompatible trait shapes.

For many cases, a single public `sImm` type plus a backend bridge is cleaner:

```rust
match shift {
    0 => core::arch::x86_64::_mm512_srli_epi32::<0>(data),
    1 => core::arch::x86_64::_mm512_srli_epi32::<1>(data),
    _ => unreachable!(),
}
```

The literal values are inferred by Rust as the intrinsic's required const type.
That avoids trying to cast a const generic, which stable Rust rejects.

### 6. The Current Design Does Not State A Valid Value Range

Literal-match dispatch needs to know which values are valid. A named `domain`
such as `imm8` hides that information. A backend encoding range such as
`0..=255` is also the wrong source-level contract for `shift_right`: it
describes the x86 immediate field width, not the legal semantic shift count.

Prefer an explicit semantic range:

```tsl
value_range 0..base_bit_width(data)
value_range 0..lane_block_count
```

Use one clear convention:

- `a..b` is half-open: `a <= value < b`;
- `a..=b` is inclusive: `a <= value <= b`.

If the parser cannot accept symbolic range expressions immediately, use a
quoted scalar as a temporary parser-friendly form:

```tsl
value_range "0..base_bit_width(data)"
```

## Recommended Design

### Source-Level Parameter Metadata

Add a `params` block that refines parameter names declared in the primitive
header.

Recommended first supported fields:

```tsl
params:
  <parameter_name>:
    type <type_tag>
    value_range <range_expression>
```

For this slice, only permit entries for parameters whose signature kind is
`sImm`. If `params` names a runtime parameter, emit a diagnostic and do not try
to make runtime values part of this feature.

Runtime values do not need this machinery. If Rust needs a different runtime
type, the TSIL body can cast it.

### Parameter Type

`type` is the public immediate parameter type. It replaces `sImm_type.default`
for that named parameter.

Examples:

```tsl
params:
  shift:
    type ui32
```

```tsl
params:
  index:
    type ui32
```

This should become the Rust const-generic type and the C++ non-type template
parameter type unless a later, explicit wrapper-splitting design says
otherwise.

### Value Range

`value_range` is the allowed value range of the immediate. It is not a Rust
type and not a backend dispatch strategy.

Examples:

```tsl
value_range 0..base_bit_width(data)
value_range 0..lane_block_count
value_range 1..=32
```

For shifts, the recommended range is half-open: valid shift counts are
`0 <= shift < base_bit_width(data)`. This avoids exposing x86's wider `imm8`
encoding range as portable TSL semantics. If the project later wants to expose
x86-style overshift behavior, that should be a separate, explicit semantic
decision because scalar/generic implementations cannot safely implement
`data >> 255` with ordinary target-language operators.

The first implementation may support only integer literal bounds after
generation-time resolution. Symbolic bounds such as `base_bit_width(data)` and
`lane_block_count` can be accepted early with a diagnostic boundary if the
selected primitive cannot resolve them yet.

### Scoped Parameter Metadata

Scoped metadata is useful, but it should scope declarative parameter facts, not
Rust dispatch commands.

The useful rule is:

- top-level parameter metadata applies to every selected implementation;
- extension-level metadata refines it for every type selected under that
  extension;
- type-group metadata under an extension refines it for that specific selected
  extension and type group.

That gives the corpus the shape the question asks for without making
`literal_match` a source-language instruction.

Possible future shape:

```tsl
params:
  shift:
    type ui32
    value_range 0..base_bit_width(data)
    overrides:
      avx512:
        value_range 0..base_bit_width(data)
      avx2:
        ?i16:
          value_range 0..base_bit_width(data)
```

The example is intentionally redundant for `shift_right`, because
`base_bit_width(data)` already captures the type-specific range generically.
That is the preferred outcome: use symbolic parameter facts when they express
the rule once; use scoped overrides only when the source semantics really differ
by selected extension or type group.

For the current Rust immediate problem, the need for a `match` bridge is not a
source semantic difference. It is inferred from:

- the selected backend;
- the selected intrinsic name;
- the selected extension/type specialization;
- the public `sImm` parameter type;
- the Rust intrinsic const-generic ABI fact.

So yes, the generated dispatch happens only for specific selected
extension/type combinations. No, that does not mean the TSL source should spell
`dispatch literal_match` at those paths.

### Backend Intrinsic ABI Metadata

Rust intrinsic const-generic type requirements should be backend facts, not
primitive source facts.

A minimal typed fact is enough:

```text
RustIntrinsicImmediateAbi(
  intrinsic = "_mm512_srli_epi32",
  argument_index = 1,
  const_type = "ui32",
)
```

Equivalent facts are needed for direct `intrin<...>` and `intrin_compose<...>`
after the intrinsic name has been selected.

This is reusable because it applies to any primitive that calls the intrinsic,
not only to `shift_right`. It also naturally scopes to the selected
implementation: if an AVX2 implementation calls an intrinsic whose const type
matches the public parameter, it renders direct; if an AVX512 implementation
calls an intrinsic whose const type differs, it renders a literal-match bridge.

### Rust Bridge Selection

The Rust backend should infer the bridge:

1. If the public `sImm` type matches the selected intrinsic const type, emit a
   direct turbofish:

   ```rust
   _mm256_srli_epi32::<shift>(data)
   ```

2. If the public `sImm` type does not match, but `value_range` is finite and
   enumerable, emit literal-match dispatch:

   ```rust
   match shift {
       0 => _mm512_srli_epi32::<0>(data),
       1 => _mm512_srli_epi32::<1>(data),
       // ...
       _ => unreachable!(),
   }
   ```

3. If neither is possible, skip or error with a diagnostic that says which
   immediate parameter, intrinsic, and selected extension caused the problem.

Do not expose `bridge direct` or `bridge literal_match` as source fields in the
first slice. They are generated-code strategies, not domain facts.

## Rejected Alternatives

### Reject: `kind immediate`

Do not add this:

```tsl
params:
  shift:
    kind immediate
```

The signature already says this:

```tsl
prim<v:=(v,sImm)> shift_right(data, shift):
```

Restating the kind adds redundancy and creates a future consistency problem:
what happens if the signature says `s` but `params` says `kind immediate`?

### Reject: Runtime Parameter Binding

Do not model runtime arguments here. A `runtime_arg` bridge or `binding runtime`
does not help this problem.

Runtime arguments can be cast normally in Rust. The hard Rust limitation is
specifically about const generic parameters: stable Rust does not allow
`::<{ N as u32 }>` or `::<{ N as i32 }>` when `N` is a const generic.

### Reject: Source-Level `binding`

Do not add:

```tsl
params:
  shift:
    binding rust_const_generic
```

For `sImm`, compile-time binding is implied. C++ uses a non-type template
parameter and Rust uses a const generic. The source language does not need to
spell that unless a later feature introduces more than one valid public API
shape for `sImm`.

### Reject For Now: Named `immediate_policy`

Do not build this first:

```tsl
immediate_policy x86_shift_imm:
  type ui32
  value_range 0..base_bit_width(data)
```

This may become useful later if several primitives repeat the same metadata.
Today it is extra language surface before the base concept has proven itself.

The right sequence is:

1. implement `params.<name>.type`;
2. implement `params.<name>.value_range`;
3. prove Rust immediate dispatch on `shift_right` and `insert`;
4. only then factor repeated metadata into a named policy if repetition is
   painful.

### Avoid: Extension-Scoped Public Type Overrides As The First Tool

Scoped overrides are tempting:

```tsl
params:
  shift:
    type ui32
    overrides:
      rust:
        [sse, sse_vl, avx2, avx2_vl]:
          type si32
```

But they may make the public Rust wrapper shape vary by selected implementation.
That is likely heavier than needed.

Prefer one public immediate type plus backend literal-match bridging. Add
scoped public type overrides only if a concrete primitive cannot be represented
cleanly with a stable public type. Scoped metadata itself is not rejected; using
scoped metadata to encode backend dispatch strategy is what should be avoided.

## Recommended Implementation Plan

### Step 1: Add Parsed Parameter Metadata

Teach the outer parser/catalog builder to accept:

```tsl
params:
  shift:
    type ui32
    value_range 0..base_bit_width(data)
```

Build a typed value such as:

```text
ImmediateParameter(
  name = "shift",
  type_tag = "ui32",
  value_range = SymbolicRange(0, "base_bit_width(data)", inclusive_end = false),
)
```

Diagnostics:

- unknown parameter name;
- `params` metadata on a non-`sImm` parameter;
- duplicate parameter metadata;
- malformed range;
- unsupported symbolic range.

### Step 2: Keep `sImm_type` As Compatibility Input

Do not remove `sImm_type` immediately. Treat it as legacy corpus input:

- if `params` exists, it wins;
- otherwise, convert `sImm_type.default` into metadata for the single `sImm`
  parameter;
- diagnose if `sImm_type` is used on a primitive with zero or multiple `sImm`
  parameters.

This keeps the first change small and avoids rewriting the whole corpus in one
step.

### Step 3: Share Rust Immediate Rendering Across Intrinsic Forms

Create one Rust helper used by both:

- direct `intrin<...>`;
- composed `intrin_compose<...>`.

The helper should receive:

- selected intrinsic name;
- rendered argument list;
- parameter metadata;
- Rust intrinsic immediate ABI fact, if any.

It should return either a direct intrinsic call or a literal-match call.

### Step 4: Add Minimal Rust Intrinsic ABI Facts

Add only the facts required for the failing cases first:

- AVX2/SSE immediate shifts requiring `si32`/Rust `i32`;
- AVX512 immediate shifts requiring `ui32`/Rust `u32`;
- direct insert intrinsics requiring const immediate handling.

Do not attempt to model every intrinsic in the corpus in the first slice.

### Step 5: Generate Literal Match Only For Finite Ranges

Literal-match dispatch must not silently generate unbounded code.

Accepted first ranges could be:

- literal ranges such as `0..32` after resolving `base_bit_width(data)` for a
  selected `si32` or `ui32` specialization;
- small symbolic ranges already known at selection time.

If a selected bridge needs literal-match dispatch and no finite range is known,
emit a diagnostic instead of guessing.

### Step 6: Prove With Focused Tests

Required tests:

- parser/catalog test for `params.shift.type` and `value_range`;
- diagnostic tests for bad parameter names and malformed ranges;
- Rust lowering test proving AVX2 direct const forwarding;
- Rust lowering test proving AVX512 literal-match bridge;
- direct `intrin<...>` test for `insert`;
- build test for a small `shift_right` and `insert` profile slice.

## Expected Corpus Shape After The First Slice

`shift_right`:

```tsl
prim<v:=(v,sImm)> shift_right(data, shift):
  params:
    shift:
      type ui32
      value_range 0..base_bit_width(data)
```

`insert`:

```tsl
prim<v:=(v,v,sImm)>[cast=reinterpret] insert(orig, data, index):
  params:
    index:
      type ui32
      value_range 0..lane_block_count
```

`sImm_type` can remain temporarily for other primitives until each is migrated.

## Why This Recommendation Is Better

Maintainability:

The metadata is next to the parameter name it describes. The source no longer
uses a primitive-wide block for parameter-specific facts.

Expressiveness:

Multiple immediates can be represented naturally because each parameter has its
own metadata.

Extensibility:

Rust ABI quirks live in backend intrinsic metadata. If another backend needs a
different immediate-call rule, it can add backend facts without changing the
meaning of the primitive source.

Consistency:

Direct `intrin<...>` and `intrin_compose<...>` use the same immediate rendering
helper.

Smallness:

The first slice adds only the fields needed by the current problem:

- `type`;
- `value_range`;
- backend intrinsic const type facts;
- inferred Rust bridge selection.

It deliberately postpones named policies, public type override machinery, and
runtime parameter modeling.
