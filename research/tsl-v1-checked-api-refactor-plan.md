# TSL v1 unchecked and checked API refactoring plan

Date: 2026-09-02

Status: accepted pre-v1 public-contract plan; Slices 0-3 are implemented and
committed; Slice 4 is next

Related evidence: [TSL v1.0.0 generated API and documentation audit](tsl-v1-generated-api-docs-audit.md)

## Decision

Adopt the following product rule:

> TSL exposes a direct, unchecked operation for expert callers. When the
> operation has a runtime precondition whose violation may cause undefined
> behavior or a process-level fault, and TSL can honestly represent and verify
> that precondition, TSL also exposes a separately named `*_checked` operation.
> The checked operation validates first, reports an explicit failure, and never
> silently repairs, clamps, substitutes, or falls back.

This direction is compatible with the C++ zero-overhead principle and does not
require replacing the compiler pipeline. The repository already owns typed
operation, operand-role, arithmetic, memory, conversion, shift, and
implementation-safety facts. The work should extend those facts with typed
public preconditions and add focused backend projections.

### Checked-companion eligibility

A backend emits a checked companion only when all of the following hold:

1. the ordinary operation has a dynamic, caller-controlled precondition;
2. violating it may cause language undefined behavior, memory corruption, an
   invalid instruction, or a process-level fault, trap, or termination;
3. the backend can represent all evidence needed to check it, using a richer
   checked signature where necessary;
4. every relevant TSL-owned precondition can be checked before the underlying
   operation performs a side effect; and
5. every propagated caller-safety obligation is matched by that complete check
   plan.

This makes catastrophic unchecked behavior a necessary but not sufficient
condition. If the hazard cannot be checked completely, the compiler reports a
checked-coverage gap instead of emitting a misleading function.

Expected precision loss, truncation with declared semantics, IEEE-754 division
by zero, allocation failure already represented by the ordinary return value,
and other defined outcomes do not qualify merely because an application might
dislike them.

A crash observed in a test is evidence of a defect, not the source of this
classification. A segmentation fault is neither portable nor guaranteed: the
same invalid call may appear to work, trap, corrupt memory, or be optimized
unpredictably. Eligibility must therefore be derived from the semantic
valid-call domain and backend language/toolchain rules, never learned by probing
invalid calls.

A naive implementation would become a large refactor: generating a second
specialization body for every function, inferring checks from names or prose,
or forcing C++ and Rust through one textual wrapper mechanism would duplicate
knowledge and further inflate an already very large generated product. This
plan explicitly avoids that design.

## Necessary pushback

### Defined semantics are not optional safety checks

The unchecked API may assume documented caller preconditions. It may not stop
implementing declared operation semantics.

For example, `integer_wrapping` is a result guarantee, not input sanitization.
Ordinary `add`, `sub`, `mul`, and `neg` must still implement modular integer
semantics without C++ undefined behavior. There is no meaningful `add_checked`
that can compensate for an incorrect base implementation.

Likewise, lane order, mask semantics, floating-point behavior, representation
conversion, and inactive-lane behavior remain guarantees of both API forms.

### Rust cannot expose an unsound safe function

The C++ convention cannot be copied literally into Rust's type-safety model. If
violating an unchecked precondition can cause undefined behavior, the Rust
entry point must be `unsafe fn`, even if the corresponding C++ function is an
ordinary function.

The intended mapping is therefore:

| Contract | C++ | Rust |
| --- | --- | --- |
| Total operation with fully defined semantics | `foo(...)` | `foo(...)` |
| Unchecked operation with a potentially unsafe precondition | `foo(...)` | `unsafe fn foo(...)` |
| Checked operation with a value result | `foo_checked(..., precondition_error& error) -> T` | `foo_checked(...) -> Result<T, PreconditionError>` |
| Checked operation with no value result | `foo_checked(...) -> precondition_error` | `foo_checked(...) -> Result<(), PreconditionError>` |

This preserves the requested unsuffixed/`*_checked` pairing without permitting
safe Rust to invoke undefined behavior.

Stable Rust does not currently expose stable `unchecked_div` or
`unchecked_rem` integer operations. Its wrapping division/remainder methods
preserve TSL's signed `MIN / -1` and `MIN % -1` guarantees but retain a
language-provided zero-divisor panic path until optimization can use the unsafe
nonzero assumption. The generated Rust implementation may therefore express
the source precondition as an unsafe optimizer assumption and use the wrapping
operation. Optimized release code must contain no TSL validation branch or
zero-divisor panic path. Debug, unoptimized, or compiler UB-check builds may
retain language/toolchain guards whose diagnostics fire after a caller violates
the unsafe contract; those guards are outside the zero-overhead promise and
must not be described as the checked API. Requiring nightly intrinsics or
target-specific inline assembly merely to suppress those diagnostics would be
a worse v1 contract.

### C++ value results return directly and report errors separately

The C++ API must not use
`checked_result<typename Vec::register_type>` as its public value-result form.
A local x86-64 System V probe with GCC 15 and Clang 21 showed that a raw
`__m128i`, `__m256i`, or `__m512i` result returns in the corresponding SIMD
register, while an aggregate containing that value plus a one-byte error uses a
hidden result pointer and writes to memory when the function is not inlined.
The aggregate sizes were 32, 64, and 128 bytes respectively. GCC also diagnoses
the direct intrinsic-vector template argument under `-Wignored-attributes`,
which makes the naive spelling fail a warnings-as-errors consumer build.

Forced inlining allowed both tested compilers to scalar-replace an immediately
consumed aggregate, but that is an optimization result, not a portable C++ or
ABI guarantee. A second local x86-64 System V probe showed GCC 15 and Clang 21
returning a raw `__m256i` in `ymm0` from a checked function while writing the
one-byte error through a reference. Ordinary register pressure may still spill
even a raw vector, and an out-of-line call may materialize the scalar error
object. TSL must therefore make the narrower, testable performance promise:

> A value-producing C++ checked API returns the same value type as its ordinary
> companion and introduces no ABI-forced value-result aggregate or vector
> output parameter. For the supported compiler/profile matrix, representative
> out-of-line and immediately consumed calls must preserve the platform's raw
> value-return convention and must not materialize the result solely because of
> the checked API representation.

C++ value-returning checked operations consequently return their value directly
and accept one final `precondition_error&` output parameter. The function
assigns that error on every return path. On success, the returned value is the
ordinary operation result. On failure, the underlying operation is not invoked
and the function returns a fully initialized placeholder whose value has no
TSL-defined semantics. The placeholder is not a successful fallback, must not
be documented as one, and must never be indeterminate or introduce C++ undefined
behavior. A caller may use it as a C++ value, but TSL guarantees no operation
result unless the reported error is `precondition_error::none`.

`[[nodiscard]]` applies to the returned value; it does not prove that the caller
inspected the referenced error. Conversely, a status-returning function plus an
output value would only make common unchecked-status mistakes diagnosable; it
would not enforce correct checking and would force an out-of-line vector result
through memory. The C++ API deliberately helps rather than attempts to force an
expert caller: the error argument is explicit, generated examples inspect it
before relying on the result, and documentation must not claim stronger static
enforcement.

That non-enforcement is an intentional part of the public contract. The
ordinary function remains the concise expert path, and the checked function
lets a caller choose whether and how to react to failure. Neither the API shape
nor its documentation may imply that storing an error status proves it was
inspected. Tooling should diagnose an obviously discarded checked value where
the language supports that warning, but it must not turn the checked companion
into a mandatory control-flow discipline.

The backend-owned checked-wrapper plan chooses the cheapest well-defined
placeholder for each result representation, such as reusing an already-live
same-type operand or constructing a valid zero value. That choice is an ABI and
code-generation detail, not primitive semantics, and therefore does not add a
`tsldata` field. Generated value tests assert the error and absence of unsafe
invocation on failure but never assert placeholder bits. If a backend cannot
produce a valid initialized placeholder for a result type, it reports a
checked-coverage gap for that callable.

Checked wrappers use a backend-owned force-inline portability macro in
optimized builds, backed by out-of-line ABI and optimized call-site assembly
tests. This is not documented as a universal no-spill guarantee, and debug or
unoptimized builds are outside the codegen promise.

### `checked` does not mean omniscient

A C++ function cannot prove that an arbitrary pointer is live, points to the
claimed allocation, remains valid concurrently, satisfies provenance rules, or
has truthful extent metadata. Rust slices establish much more, but no function
can defend against an object whose own language-level validity invariant was
already violated.

Consequently, a `*_checked` function must either:

1. accept a richer argument whose valid-object contract supplies the evidence
   needed for a complete check, such as a slice, extent-carrying range/view, or
   owning handle; or
2. not be generated when a TSL-owned obligation remains unrepresented.

A bare pointer plus a caller-claimed count is not sufficient when pointer
validity itself remains a TSL-owned precondition. Complete means complete
relative to valid values of the checked signature: every declared dynamic
precondition is discharged before invocation. General language rules governing
object lifetime, data races, and forged invalid objects remain language rules,
not partially implemented TSL checks.

The `_checked` suffix is now the planned public spelling. It means “the complete
finalized TSL precondition contract is checked by this overload,” not “all C++
misuse is impossible.” That meaning must be frozen before the first released
implementation.

### Not every operation needs a twin

Generating `add_checked`, `and_checked`, or `compare_checked` when there is no
dynamic precondition adds API noise, code size, documentation burden, and no
contract value. Only a primitive or algorithm satisfying every catastrophic
risk and checkability rule above should receive a checked variant. A defined but
undesirable outcome or noncatastrophic validation need does not automatically
justify the suffix; if TSL wants such validation, it needs a separately named
semantic API.

Compile-time type constraints, impossible template combinations, unsupported
profiles, and invalid compile-time immediates should remain compiler
diagnostics, concepts/traits, or `static_assert`s. They are well-formedness
rules, not hidden runtime sanitization.

## Contract vocabulary

The refactor must keep four kinds of facts distinct.

### 1. Operation semantics

These describe what a valid call computes. Examples include integer wrapping,
signed division rounding, `MIN / -1`, floating-point behavior, lane order,
mask pass-through, and shift-count normalization.

They apply to unchecked and checked forms and must never depend on whether checks
are enabled.

### 2. Static well-formedness constraints

These are decided before execution: supported types, valid immediate ranges,
lane-count relationships, profile availability, target features, and legal
template/policy combinations.

They remain compile-time diagnostics. Removing runtime checks does not justify
accepting malformed generated programs.

### 3. Dynamic caller preconditions

These can vary per call: an index is within the logical lane count, every
active integer divisor is nonzero, a destination has sufficient capacity, a
pointer satisfies an explicitly selected alignment, or selected indices are
within a supplied extent.

The ordinary API assumes all declared dynamic preconditions. Only the subset
that satisfies checked-companion eligibility produces a `*_checked` API. Other
preconditions remain explicit documentation obligations or require a separately
designed API; they do not acquire the suffix merely because they are
representable.

### 4. Implementation hazards

The current `ImplementationSafety` record describes whether generated Rust
needs an internal unsafe boundary, whether callers must uphold an unsafe
contract, and why. Intrinsic use and raw target operations belong here.

This record must remain separate from public semantic preconditions. An AVX2
intrinsic and a scalar loop can implement the same public precondition while
having different internal hazards.

## Behavioral rules for `*_checked`

Every checked operation must satisfy the following rules:

- validate every declared dynamic precondition in the finalized check plan
  before invoking the unchecked operation;
- perform no underlying-operation output writes or other operation side effects
  after a failed validation; assigning the error output and returning a
  placeholder are failure reporting, not operation side effects;
- report a typed error rather than throw, panic, abort, trap, or silently
  continue for caller-supplied invalid data;
- never clamp an index, replace a zero divisor, shorten a count, clear an
  invalid mask lane, switch to an unaligned implementation, or choose a slower
  fallback without an API that explicitly promises that behavior;
- validate only active lanes for masked operations when inactive operands are
  semantically unobserved;
- assign the final C++ error output exactly once on every value-returning path;
- return a fully initialized but semantically unspecified C++ value on failure,
  without exposing its placeholder spelling as a source-data guarantee;
- carry `[[nodiscard]]` on the C++ value or status return and the ordinary
  `Result` must-use behavior in Rust, without claiming that these diagnostics
  enforce error inspection;
- delegate to the ordinary implementation exactly once after validation; and
- document both the checked conditions and any residual obligation that the
  language/runtime cannot prove.

The unchecked operation must not contain TSL-authored runtime assertions,
throws, panics, or validation branches. Optimized supported builds must not
retain a validation branch introduced solely for the public precondition.
Natural hardware traps and target-language or compiler UB-check behavior are
not a substitute for a contract and must be documented as possible consequences
of violating the precondition, not as the checked API. The stable-Rust
division/remainder limitation above is the deliberate unoptimized-build
exception; it does not permit ordinary safe Rust APIs for hazardous calls.

## Proposed public API shape

The direct-value/error-output convention is fixed for value-producing C++
operations. Checked operations without a value result return the status. The
first pilot freezes only the remaining concrete spelling, including the
force-inline macro, failure-placeholder projection, and range/view type, rather
than editing templates speculatively.

### Lane access

```cpp
auto extract_value_at<Vec>(typename Vec::register_type value, std::size_t index)
  -> typename Vec::base_type; // precondition: index < Vec::lane_count()

[[nodiscard]] TSL_FORCE_INLINE auto extract_value_at_checked<Vec>(
    typename Vec::register_type value,
    std::size_t index,
    tsl::precondition_error& error
) noexcept -> typename Vec::base_type;
```

```rust
pub unsafe fn extract_value_at<T, const N: usize>(
    value: Simd<T, N>,
    index: usize,
) -> T;

pub fn extract_value_at_checked<T, const N: usize>(
    value: Simd<T, N>,
    index: usize,
) -> Result<T, PreconditionError>;
```

### Runtime integer division

```cpp
auto div<Vec>(reg_param_t<Vec> dividend, reg_param_t<Vec> divisor)
  -> typename Vec::register_type; // precondition: active integer divisors != 0

[[nodiscard]] TSL_FORCE_INLINE auto div_checked<Vec>(
    reg_param_t<Vec> dividend,
    reg_param_t<Vec> divisor,
    tsl::precondition_error& error
) noexcept -> typename Vec::register_type;
```

For floating-point lanes, zero is valid IEEE-754 input and must not be rejected.
The checked overload must be unavailable when its selected vector has a
floating-point lane type; a shared generic backend surface uses a type-domain
constraint, while concrete facades omit the checked method entirely.
For masked integer division, only active divisor lanes are checked. The existing
defined `MIN / -1 -> MIN` behavior remains a semantic guarantee, not an error.

### Contiguous load

```cpp
auto load<Vec>(const typename Vec::base_type* source)
  -> typename Vec::register_type;

[[nodiscard]] TSL_FORCE_INLINE auto load_checked<Vec>(
    tsl::span<const typename Vec::base_type> source,
    tsl::precondition_error& error
) noexcept -> typename Vec::register_type;
```

The C++17 range/view or small generated `tsl::span` must establish an
addressable extent as part of its valid-object contract; a bare
pointer-plus-count does not. The chosen range type and the
direct-value/error-output call must be compile-probed under the supported GCC,
Clang, and MSVC matrix before they are made public.

Rust should use a slice for the checked form and a raw pointer for the unchecked
form:

```rust
pub unsafe fn load<T, const N: usize>(source: *const T) -> Simd<T, N>;

pub fn load_checked<T, const N: usize>(
    source: &[T],
) -> Result<Simd<T, N>, PreconditionError>;
```

An `aligned=true` checked call reports an alignment error when the address is
misaligned. It must not silently switch to the unaligned implementation.

### Range algorithms

The ordinary C++ range algorithms continue to take the first input's size as
their unchecked count. Their contracts explicitly require every secondary
input, mask, and output to cover that count. Corresponding `*_checked` overloads
compare all extents first and report a typed error before dispatch.

Rust checked algorithms should consume slices and return `Result`; raw-pointer
algorithm kernels remain `unsafe`. Existing assertions on caller-controlled
lengths and indexes migrate to the checked result path rather than remaining
hidden panics in the unchecked path.

## Error model

The C++ representation decision is a no-allocation, no-exception C++17 direct
value return plus error reference for value-producing operations. Operations
without a value result return the status directly. The first two precondition
slices require only this shared semantic error vocabulary:

- `none`;
- `index_out_of_bounds`; and
- `zero_divisor`.

Later memory slices may add `insufficient_input`, `insufficient_output`,
`misaligned`, and `address_overflow` when a concrete checked signature can
produce them. `invalid_alignment` is added only if the allocation census finds
an eligible catastrophic runtime condition. `invalid_scale` is not introduced
for a compile-time immediate; it remains a static diagnostic unless a later
public API has a genuine runtime scale precondition.

C++ exposes a stable `enum class precondition_error`. A checked operation with
a value result returns that value and accepts one final mutable error reference;
a checked operation without a value returns the `[[nodiscard]]` status. The
value-returning function always writes `precondition_error::none` or one
specific failure to the error reference. On failure it performs no operation
side effects and returns an initialized placeholder with no TSL-defined value.
This convention is uniform for scalar and register results; do not select among
aggregates, `bool`, `optional`, exceptions, and value output parameters per
primitive.

The canonical generated C++ example checks the error before relying on the
result:

```cpp
tsl::precondition_error error;
auto quotient = div_checked<Vec>(dividend, divisor, error);
if (error == tsl::precondition_error::none) {
    consume(quotient);
} else {
    handle(error);
}
```

The API does not claim to force that branch. Passing the required error lvalue,
the `*_checked` name, hover/documentation, and compiling examples are the
deliberate assistance provided to an expert C++ caller.

Rust exposes a non-exhaustive or otherwise evolution-safe `PreconditionError`
and standard `Result<T, PreconditionError>`. Rust's result layout and ABI are
not assumed to be register-only: optimized monomorphized call sites receive the
same codegen inspection as C++, while the public Rust surface remains
idiomatic unless evidence demonstrates an unacceptable cost.

## Checkability matrix

| Operation family | Unchecked contract | Checked form | Important limit |
| --- | --- | --- | --- |
| Total arithmetic, bitwise, comparison | Fully defined input domain | No twin | Base semantics must already avoid language UB where TSL promises a result |
| Runtime lane/mask index | Index is in range | Check index against logical lane count | Scalable profiles need a runtime lane-count fact |
| Runtime integer division/remainder | Every active divisor is nonzero | Test active lanes before evaluation | Floating zero remains valid; immediate zero remains a compile-time error |
| Contiguous load/store | Source/destination is a valid range with sufficient extent and selected alignment | Accept a valid extent-carrying range/view and check length/alignment | A bare pointer or pointer-plus-claimed-count cannot establish the range invariant |
| Gather/scatter | Every active computed address is within a valid base range | Accept a valid base view and validate active indexes/scale before address formation | Index arithmetic must be validated without first forming an invalid pointer |
| Compress/expand memory | A valid range has capacity for the active-lane count | Compute required count and compare capacity | Masked active-lane semantics must be exact |
| Range algorithms | All participating valid ranges cover the driving count and meet alias rules | Compare all range lengths and selected indexes | Any TSL-owned no-alias rule must be encoded by the signature or checked; otherwise omit the twin |
| Allocation | The ordinary return already represents allocation failure | No automatic checked twin | Invalid alignment qualifies only if its violation is catastrophic for the backend and can be completely prechecked |
| Deallocation | Pointer has matching live allocation provenance | No honest pointer-only checked twin | Requires an owning allocation type, which is a separate API design |
| Raw copy | Valid source/destination ranges satisfy the overlap rule | Potential range/view overload with an explicit overlap check | Omit the twin if the signature cannot establish range validity and the complete overlap contract |
| CPU/profile availability | Caller/build selected a supported target | Existing compile-target selection/dispatch | Not a per-call `*_checked` concern |

If an operation remains in the “important limit” column without a signature
that represents enough evidence, the compiler must omit its checked variant and
document the coverage gap. It must not emit a misleading stub.

The semantic check contract is declared once. Emission may differ between C++
and Rust when their type systems make different evidence representable, but it
must not fluctuate accidentally with a selected profile or implementation.
Implementation-specific hazards may conservatively suppress a companion and
produce a coverage diagnostic; they must not silently invent a public check. For
a public overload family, severity follows the worst consequence permitted by
its contract across supported implementations, not whether one current body
happens to mask or trap the invalid input deterministically.

## Compiler ownership

### Source data

Yes: the language-neutral knowledge that a call has a restricted valid domain
belongs in the primitive declaration in `tsldata`. It belongs next to the
operation, arithmetic, operand-role, memory, conversion, and shift contracts.
It must not be inferred from primitive names, parameter spellings, prose, or
target-language bodies.

The ownership split is:

| Fact | Canonical owner |
| --- | --- |
| Which inputs form a valid call and which semantic operand/attribute they constrain | Primitive declaration in `tsldata` |
| Closed precondition meaning, required operand roles, compatible domains, and language-neutral hazard class | Typed descriptor registry in `tslc.catalog` |
| Internal intrinsic/raw-operation hazards and conservatively propagated caller unsafety | Existing `ImplementationSafety` on implementations/lowered calls |
| Whether violation is UB/faulting for C++ or Rust, whether a complete check is expressible, checked signature, and error spelling | Backend API planner |
| Range/slice contracts for generated algorithms that are not TSL primitives | Backend-owned typed algorithm contract |

The initial declarations must come from a reviewed migration census: structured
operation and operand-role semantics, current prose preconditions, existing
runtime assertions/panics, language and intrinsic contracts, and propagated
`ImplementationSafety` evidence. A maintainer may inspect implementations during
that census, but production compiler behavior must not infer contracts from raw
bodies. Sanitizers and faulting experiments verify the classification; they do
not define it. Once curated, the typed declaration and descriptor become the
source of truth.

`tsldata` should declare the precondition, not its generated policy. It should
not contain `checked true`, `causes_segfault`, `cpp_ub`, a C++ result type, or a
Rust error name. Those are derived projection facts and can differ by backend.

The checked-API refactor introduces exactly one outer-TSL primitive field:

```text
preconditions [...]
```

This is source metadata, not a TSIL body region, so no TSIL keyword is added.
The initial closed condition vocabulary, added incrementally by the lane and
division slices, is deliberately limited to:

- `lane_index_in_range`; and
- `active_divisor_nonzero`.

These names are enum values under the `preconditions` field rather than new
parser tokens. They are added to the parser's known primitive-field projection,
schema, typed catalog promotion, validation, authoring facts, and lowering as
one coherent source-data shape. There is no separate `checked`, `hazard`,
`error`, `safe`, or backend-specific source field.

The smallest additive source shape can reuse existing typed operand roles. For
example, the current `extract_value_at` declaration already identifies an
`extract_lane` operation and an `index` operand, so it should only need a closed
condition such as:

```text
preconditions [lane_index_in_range]
```

Runtime integer division already identifies the divisor through its arithmetic
operand-role contract. Its typed mask mode and mask-argument signature identify
which lanes participate, so it can declare:

```text
preconditions [active_divisor_nonzero]
```

For an unmasked declaration, every lane is active. For a masked declaration,
only active lanes must have nonzero integer divisors. The condition is
inapplicable to floating lanes. The existing
`integer_zero_divisor_fails` arithmetic guarantee must be removed when this
precondition is introduced: the ordinary operation assumes valid input rather
than promising a hidden failure mechanism. Compile-time immediate-zero
rejection remains a static well-formedness rule.

Presence matters. `test_imask`, for example, defines an out-of-range position
as returning zero and therefore must not declare `lane_index_in_range`, even
though it has an index operand. Backend planners must stop treating an operation
identity as sufficient evidence for a check.

A compiler-owned descriptor table then validates that the required index or
divisor binding exists, classifies the unchecked hazard, and states what
additional evidence a backend needs. A memory precondition may, for example,
require the checked signature to add an accessible element count or range.

Do not predeclare a speculative flat memory vocabulary in the lane-index
slice. Before checked gather, scatter, compress, expand, copy, allocation, or
deallocation work, extend the existing typed operation, operand-role, and
memory-addressing coverage for those actual families. Reuse existing roles such
as memory source, memory destination, control mask, index, and count; add a
role such as scale only where the corpus proves it is needed. Introduce
condition values for source/destination extent, selected alignment, active
address validity, overlap, or allocation provenance only with the vertical
slice that validates and consumes each condition. A provenance condition may
remain documentation-only when no backend signature can discharge it.

This separation is necessary because the current
[`ImplementationSafety`](../tslc/src/tslc/catalog/model.py#L149) is
implementation-local and its reasons are free-form labels such as `intrinsic`,
`raw_pointer`, and `raw_memory`. It does not model every public invalid-call
domain: runtime lane access has a prose precondition in
[`array.tsl`](../tsldata/primitives/load_store/array.tsl#L791) while its
implementations currently say `caller_unsafe false`. Conversely, intrinsic use
alone does not imply that a public checked companion is useful.

The Rust facade currently derives bounds checks by recognizing typed operation
identities in
[`rust_api_comprehensive.py`](../tslc/src/tslc/backend/rust_api_comprehensive.py#L295).
That proves the required facts already exist in part, but the public precondition
should be promoted once and shared rather than remaining a Rust-only policy.
Existing `ImplementationSafety` remains a conservative eligibility constraint;
its free-form reasons must not be converted into public checks by string
matching.

### Catalog and validation

Add a small frozen precondition vocabulary under `tslc.catalog`, with source
spans and resolved operand bindings. Catalog validation must reject:

- unknown precondition kinds;
- missing or duplicate bindings;
- bindings to absent parameters or incompatible signature kinds;
- lane-index rules on operations without a logical lane owner;
- divisor rules on non-arithmetic or incompatible operations;
- memory extents without a typed memory contract; and
- disagreement among same-name overload declarations that are expected to
  share one public contract.

This is domain vocabulary that carries a real invariant, not plumbing.

### Lowering

Carry promoted preconditions unchanged through `LoweredPrimitiveSemantics`,
resolving only specialization facts such as element type, lane count,
alignment mode, active mask binding, and immediate-versus-runtime status.

Lowering must not render checks or target-language expressions. Existing
conservative `ImplementationSafety` propagation remains in force. A checked root
is eligible only when every propagated caller obligation is covered by an
explicit root-level typed precondition and backend check plan; an unmatched
obligation produces a checked-coverage gap. The initial design must not attempt to
prove from opaque target text that an implementation discharged a callee
precondition.

### Backend API planning

Each backend converts lowered preconditions into a typed public wrapper plan:

- whether an unchecked public entry is safe or `unsafe` in that language;
- whether a complete checked wrapper can be offered;
- additional extent/range parameters;
- ordered validation steps;
- public result/status convention, including the C++ error-output binding;
- the backend-owned initialized C++ failure-placeholder expression for a value
  result, without promoting that expression into semantic source data;
- invocation of the already-emitted ordinary wrapper; and
- exact documentation facts and residual obligations.

Rust should extend its existing finalized facade plan rather than add checks in
the renderer. C++ should gain a focused checked-wrapper record/planner consumed
by the existing primitive emitter. That plan carries the direct result type,
final error-output binding, initialized failure-placeholder expression, ordered
checks, error mapping, and force-inline policy; it does not need a rewrite of
every C++ function model.

### Rendering

Renderers format the finalized validation and wrapper records. They do not
recognize primitive names, inspect raw TSIL/C++/Rust bodies, or independently
decide which inputs need checking.

A checked wrapper delegates to the unsuffixed wrapper. No second intrinsic or
generic specialization body is generated. This is essential for determinism,
DRY behavior, and generated-size control.

### Algorithms

The generated algorithms are backend-owned static APIs rather than source
primitives. Their extent, mask-storage, selected-index, and alignment contracts
should therefore live in focused typed backend algorithm plans or static
contract tables, not be fabricated as TSL primitive declarations.

C++ and Rust algorithm contracts may share language-neutral concepts, but each
backend owns its public range/slice signature and error spelling.

### Documentation and authoring

The same typed precondition and wrapper plans must drive:

- unchecked precondition sections;
- checked-function checked-condition sections;
- C++ result/error-output documentation, including the rule that a value is an
  operation result only when the reported error is `none`;
- Rust `# Safety` sections for unchecked `unsafe fn`s;
- Rust `# Errors` sections for `*_checked` functions;
- authored primitive hover/explorer facts;
- concrete checked-availability and checked-coverage facts; and
- checked-API coverage diagnostics.

Documentation must never infer precondition coverage from `*_checked` spelling
alone.

Editor support is a compiler-owned authoring projection. The ordinary live
snapshot must expose source-declared preconditions without lowering or backend
planning:

- complete `preconditions` as a primitive field from the parser/schema-owned
  field vocabulary;
- complete condition values from the same typed precondition descriptor
  registry used by catalog validation;
- publish structured unknown, duplicate, missing-role, incompatible-operation,
  and same-family diagnostics with exact source spans;
- index each condition item as a registry-backed enum occurrence so references,
  hover, and semantic tokens consume one identity;
- render descriptor-owned meaning, required roles, numeric/mask applicability,
  and unchecked consequence in hover; and
- show declared preconditions in authored primitive hover and explorer records.

Completions may narrow compatible conditions when the current declaration has a
valid typed context, but must fall back to the deterministic complete registry
while an overlay is incomplete. A temporarily invalid document retains current
diagnostics and its last successful catalog/index facts under the existing
workspace snapshot rules.

Whether a particular C++ or Rust `*_checked` callable can be emitted is not a
catalog-only fact. It depends on finalized lowering, propagated safety, and the
backend checked-wrapper plan. Ordinary live hover and completion must not infer
that availability from an operation name or run the generation pipeline. If
the editor displays concrete checked availability or an omission reason, it
does so through an explicit, cancellable, saved-corpus compiler analysis or
preview projection that consumes the finalized backend plan.

For a concrete C++ value-returning checked callable, that projection also owns
the direct result type, mutable error-output parameter, possible error values,
and conditional result-validity text. The editor presents those finalized facts
without claiming that C++ enforces inspection of the referenced error and
without exposing the backend's failure-placeholder expression as API semantics.

The TypeScript VS Code client remains limited to LSP transport and presentation;
it contains no precondition names, compatibility rules, hazard classification,
or checked-eligibility logic. The TextMate grammar already colors arbitrary
outer TSL fields structurally. `preconditions` and its condition values must
not be added to the generated TSIL-region keyword inventory, because they are
outer TSL metadata rather than TSIL body regions. No client or grammar change is
required unless a new editor-neutral protocol or presentation record is
actually introduced.

## Migration slices

Each slice below delivers one observable behavior and can be reviewed and
validated independently. Do not implement the entire corpus in one branch.

### Slice 0 — Freeze the public policy and census current checks

Goal: establish an exact baseline before changing generated APIs.

Deliverables:

- freeze the approved `*_checked` spelling and catastrophic-risk eligibility;
- record the approved C++ direct-value/error-output and Rust `Result` mapping
  above;
- convert the exploratory intrinsic-vector ABI case into a maintained
  warnings-as-errors, out-of-line ABI, and optimized-call-site codegen fixture
  for the supported compiler matrix;
- inventory every generated runtime assertion, throw, panic, trap helper, and
  `caller_unsafe` public path;
- classify each item as semantic guarantee, static well-formedness constraint,
  dynamic precondition, implementation hazard, or tooling-only validation;
- record the backend consequence and complete-check feasibility for every
  dynamic precondition;
- record which public operations can and cannot receive an honest checked form;
  and
- freeze representative C++ and Rust declaration snapshots.

Out of scope: changing generated behavior.

Validation: deterministic inventory identities, not only counts; independent
review of every item classified as “uncheckable”; GCC, Clang, and available
MSVC compile probes comparing raw value return, the chosen value-plus-error-out
form, a rejected value-owning result aggregate, and a rejected
status-plus-value-output form. The probes must record the raw value return
location, scalar error transport, and any result-only memory traffic.

Stop if the team cannot agree what `checked` promises or whether Rust may expose
unchecked operations as `unsafe fn`.

### Slice 1 — Repair wrapping semantics independently

Goal: make ordinary C++ wrapping arithmetic implement its existing contract.

Deliverables:

- defined scalar/generic wrapping for add, subtract, multiply, and negate;
- no reliance on consumer `-fwrapv`;
- active/inactive masked edge coverage; and
- C++/Rust differential agreement.

This slice adds no `*_checked` API because wrapping arithmetic has no invalid
runtime input.

Validation:

```bash
PYTHONPATH=tslc/src python -m tslc check --primitive add --profile scalar --backend cpp --type si32
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Also run focused UBSan consumers for every affected operation family.

### Slice 2 — Lane-index vertical pilot

Goal: prove the complete source-to-C++/Rust checked-wrapper path with
`extract_value_at` before generalizing it.

Deliverables:

- one typed lane-index precondition in source/catalog/lowering;
- a finalized C++ checked-wrapper plan using the uniform C++17
  direct-value/error-output convention;
- a backend-owned force-inline portability macro with warnings-as-errors
  compiler probes and an explicit unoptimized-build fallback;
- an unchecked C++ `extract_value_at` with a documented precondition and no
  injected check;
- a Rust unchecked form marked `unsafe` if invalid indexing can cause UB;
- C++ `extract_value_at_checked` returning the scalar value, assigning an
  explicit out-of-range error, and returning a fully initialized but
  semantically unspecified placeholder on failure;
- Rust `extract_value_at_checked` returning an explicit out-of-range error;
- compiler-owned completion for the `preconditions` field and condition values,
  sourced from the parser/schema and typed descriptor registry rather than a
  parallel authoring table;
- live catalog diagnostics, hover, registry-backed references, and semantic
  tokens for exact precondition-item spans, including incomplete and
  temporarily invalid overlays;
- authored primitive hover/explorer records that list declared preconditions
  without claiming backend checked availability;
- no precondition vocabulary or checked-eligibility logic in the TypeScript
  client, and no addition to the generated TSIL-region keyword inventory;
- generated documentation for both forms; and
- positive, boundary, failure-without-invocation, and generated-name-collision
  tests.

Add `insert_value_at` and mask-lane set only after the first operation passes.
Use `test_imask` as the negative/total-operation probe: preserve its defined
out-of-range-zero result, remove the Rust-only inferred assertion, declare no
lane-index precondition, and generate no checked twin. Together these cases
prove that the generic path follows source preconditions rather than operation
identity.

Validation:

- catalog malformed/unknown/binding diagnostics;
- deterministic authoring completion tests for the field and both initial
  condition values;
- catalog-index hover, occurrence/reference, semantic-token, exact-span, and
  invalid-overlay snapshot tests;
- LSP completion, diagnostics, hover, references, and semantic-token tests;
- VS Code client tests proving the generic LSP records require no copied
  semantic vocabulary;
- selection/lowering preservation tests;
- backend render-model tests;
- scalar and AVX2 generated builds for C++ and Rust;
- checked calls at index `0`, `N - 1`, `N`, and `SIZE_MAX`;
- ASan/UBSan on checked failure cases; and
- an optimized object/assembly check showing no checked-validation branch or check
  helper in the unsuffixed wrapper.

Run the focused compiler authoring suites and the VS Code unit tests in this
slice. Run the VS Code integration gate when the bundled server or an
editor-neutral protocol/presentation record changes; otherwise record that no
client artifact changed. Regenerating the TextMate grammar must produce no new
TSIL keyword for `preconditions`.

Stop rather than generalize if the C++ convention cannot return the ordinary
value through the supported platform ABI, any path leaves the error unassigned,
the failure placeholder is indeterminate or acquires public semantics, or the
planner must recognize the primitive name.

### Slice 3 — Runtime division and remainder

Goal: move runtime zero-divisor validation out of the ordinary API and into
checked variants without losing the remaining arithmetic semantics.

Deliverables:

- express runtime active-divisor nonzero as a typed precondition;
- remove `integer_zero_divisor_fails` from arithmetic guarantees and migrate
  its prose and authored runtime-failure case to the unchecked-precondition and
  checked-error contracts;
- preserve compile-time rejection of an invalid immediate divisor;
- preserve signed `MIN / -1` and `MIN % -1` result guarantees;
- remove TSL-authored throw/panic checks from ordinary runtime
  division/remainder;
- generate `div_checked` and `mod_checked`;
- check only active lanes in masked variants; and
- establish the first real register-output codegen gate: an optimized valid
  checked call consumed by a subsequent vector operation must not materialize a
  result aggregate, a vector output parameter, or a result-only stack slot; an
  out-of-line fixture must return the raw register through the supported
  platform's ordinary vector return convention.

Validation:

- zero in active and inactive lanes;
- signed and unsigned element widths;
- floating zero and NaN/infinity controls;
- no side effects or unchecked invocation on checked failure;
- correct C++ error assignment on success and failure, with no assertion about
  failure-placeholder bits beyond their being fully initialized;
- GCC, Clang, and available MSVC warnings-as-errors builds plus inspected
  optimized call-site assembly for representative fixed-width registers;
- exception-disabled C++ builds; and
- optimized Rust IR or assembly proving that the unsafe nonzero assumption
  removes the stable wrapping operation's zero-divisor panic path; and
- differential generated value tests.

### Slice 4 — Contiguous load/store checked signatures

Goal: offer meaningful checked memory entry points without pretending that a
bare pointer is self-validating.

Deliverables:

- choose an extent-carrying range/view or a small C++17 span after compiler
  probes;
- require its valid-object contract to establish addressable storage rather than
  trust a second caller-supplied count;
- use Rust slices for checked loads/stores and raw pointers for unchecked
  operations;
- validate extent and explicitly selected alignment before invocation;
- report errors rather than switching alignment policy; a checked C++ load
  returns only a semantically unspecified initialized placeholder on failure,
  while a checked store performs no destination write;
- document the argument-object validity invariants and general language rules
  that remain outside dynamic checking; and
- cover scalar, fixed-width native, and one scalable-vector plan even when the
  latter requires an emulator or compile-only gate.

Validation: zero/short/exact/long extent, aligned/misaligned addresses,
read-only versus writable ranges, ASan canaries, and no write on failure.

### Slice 5 — Algorithm range contracts

Goal: split generated algorithms into explicit unchecked and checked forms.

Deliverables:

- typed backend-owned contracts for input, secondary-input, mask, index, and
  output extents;
- ordinary paths without runtime validation;
- `*_checked` range/slice paths that validate every extent before dispatch;
- checked selected-index and scale handling; and
- complete C++ and Rust algorithm documentation.

Start with `transform_unary`, then use `transform_binary` as the additive probe
for multiple related extents. Migrate predicate, masked, selected, aggregate,
and consume families only after those two establish the design.

Validation: mismatched lengths at each operand independently, aliasing cases
allowed by the contract, zero-length inputs, tails, masks, selected indices,
and output preservation on failure.

### Slice 6 — Irregular and compacted memory

Goal: add checked variants only where gather, scatter, compress, and expand can be
checked from an enriched signature.

Deliverables:

- explicit base extent/capacity;
- overflow-safe index/scale validation before pointer arithmetic;
- active-lane-only address checks;
- compacted-output capacity based on mask population; and
- structured coverage gaps for shapes whose memory validity cannot be
  represented.

Validation must include negative/signed indexes where admitted, maximum scale,
address-calculation overflow, all-inactive masks, exact capacity, one-short
capacity, and canary-protected buffers.

### Slice 7 — Remaining raw-memory and allocation APIs

Goal: classify allocation, deallocation, copy, random-output, and other raw
memory operations without overclaiming.

Likely outcomes:

- ordinary allocation failure does not create a checked twin because the base
  return already represents it;
- an invalid alignment request qualifies only on a backend where violating it
  is catastrophic and every validity condition can be checked before allocation;
- copy receives a checked twin only if valid range arguments establish extent
  and the overlap rule can be checked or encoded by the signature;
- a raw-pointer deallocator cannot validate allocation provenance and should
  not receive a misleading checked twin; and
- an owning allocation/RAII API, if desired, is a separate v1 feature decision
  rather than a suffix wrapper.

Validation: exact checked-coverage report plus focused allocator/copy tests. Do
not broaden this slice into a general memory-management library.

### Slice 8 — Documentation, coverage, and release gates

Goal: make the two-path contract independently understandable and prevent
regression.

Deliverables:

- C++ and Rust overview documentation defining semantic guarantees,
  unchecked preconditions, checked errors, and residual obligations;
- one documentation record per unchecked/checked callable identity;
- compiling examples for both paths, with every value-returning C++ checked
  example inspecting the error before relying on the returned value;
- an exact checked-API coverage inventory with reasons for omissions;
- bundled-editor smoke coverage for precondition completion, diagnostics,
  hover, references, and semantic tokens from the packaged Python server;
- public API declaration baselines; and
- package-size and generated-size comparison against the pre-refactor
  baseline.

Validation:

- `RUSTDOCFLAGS='-D warnings -D missing_docs' cargo doc` on the declared stable
  surface;
- Rust doctests with representative checked and unchecked examples;
- compiled C++ documentation examples;
- Doxygen identity/completeness assertions;
- GCC/Clang warnings-as-errors external consumers;
- VS Code unit/integration tests plus the applicable verified runtime-package
  gate; and
- reproducible package contents before and after documentation generation.

## Performance and correctness showcase

The refactor needs a genuine experiment demonstrating the intended lever.

### Question

Does the ordinary path remain zero-overhead while the checked path incurs only
the explicit checks selected by the caller?

### Microbenchmark

Generate scalar and AVX2 C++ plus Rust for three representative contracts:

1. runtime lane extraction;
2. integer vector division with nonzero valid inputs; and
3. contiguous vector load from a valid aligned buffer.

For each operation, benchmark:

- a raw intrinsic or minimal handwritten baseline;
- the TSL unsuffixed operation;
- the TSL `*_checked` operation with valid input; and
- checked failure input separately, outside the throughput comparison.

Record compiler, flags, target, disassembly hash, branches, instructions,
cycles/call, and generated code size. Use dependency chains for latency and
independent batches for throughput. Prevent dead-code elimination and keep
validation inputs runtime-visible.

For each value-returning C++ case, compile an immediately consuming call-site
fixture in which the caller checks the reported error and the valid checked
result then feeds the next scalar or vector operation. Inspect that caller, not
only the wrapper body. Add a separate non-inlined fixture to observe the
platform ABI. Record the raw result-return location, scalar error transport,
hidden result pointers, dedicated result stack slots, and any store/reload
attributable solely to the checked representation. Keep both the rejected
value-owning aggregate and rejected status-return/value-output forms as
benchmark-only negative controls so the direct-value/error-output lever remains
visible; neither is a generated API candidate. Run the corresponding
monomorphized Rust `Result` call-site inspection rather than assuming its layout
is cost-free.

### Required interpretation

- Unsuffixed TSL must generate no validation call or conditional branch beyond
  what the underlying operation requires. For the pilot, its optimized
  instruction sequence should be equivalent to the handwritten baseline after
  normal register-allocation differences.
- The checked path must show the expected validation work and report the
  specified error on invalid input without invoking the underlying operation.
- In supported optimized C++ configurations, a valid immediately consumed
  register result must use the ordinary raw-register return convention, must
  not use an aggregate-return ABI or vector output parameter, and must not
  materialize a result-only stack slot. Scalar error-output traffic and stack
  traffic genuinely required by validation are recorded separately and are not
  mislabeled as result transport.
- C++ failure cases must assign the exact error, avoid the underlying operation,
  and return a fully initialized placeholder. Tests and benchmarks must not
  treat the placeholder bits as a promised fallback value.
- Any measurable checked-path overhead is acceptable as an explicit caller
  choice; it must be reported rather than hidden.
- If the unsuffixed path regresses, stop the rollout and repair the planner or
  renderer before migrating another family.

Correctness runs use ASan/UBSan for C++, ordinary Rust tests plus generic-profile
interpreter/sanitizer coverage where supported, and generated differential
tests across backends. Invalid input is executed only through the checked path;
tests must not deliberately execute an unchecked call outside its contract.

## Validation matrix for every implementation slice

Run the smallest focused owner tests first, then broaden in proportion to the
slice:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_lower_*.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_maintenance_documentation.py
(cd tslc && python -m mypy)
git diff --check
```

For generated behavior:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

When a slice adds or changes precondition source vocabulary or editor
projections:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_authoring_check.py tslc/tests/test_authoring_completion.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_index_authoring.py tslc/tests/test_lsp_*.py
(cd editors/vscode-tsl && npm test)
```

Run the VS Code integration and verified packaging gates when the bundled
server, protocol, client presentation, or packaged runtime changes. A source
metadata field must not be added to the generated TSIL keyword inventory.

Every slice must report unavailable hardware/emulator coverage explicitly.

## Risks and controls

### False confidence from the suffix

Control: checked variants exist only with a typed complete check plan; docs list
checked and residual obligations separately; uncovered operations produce a
coverage gap rather than a stub.

### API and artifact explosion

Control: generate checked wrappers only for catastrophically hazardous call
families with a complete typed check plan, once per public overload family,
delegating to existing specializations. Track
artifact bytes, lines, formatting time, and consumer compile time per slice.

### C++ checked result loses the ordinary value-return convention

Control: reject both the value-owning aggregate and status-return/value-output
forms for the public value-result API. Use one uniform
direct-value/error-output convention, a backend-owned force-inline macro, and
warnings-as-errors plus out-of-line ABI and optimized call-site codegen gates
for GCC, Clang, and available MSVC configurations. State the limited performance
contract precisely: the checked function preserves the ordinary value return
type and tested platform return convention, with no result-only materialization
in the supported matrix. This is not a universal promise that registers never
spill, and a scalar error output may be materialized across an out-of-line call.

### C++ failure placeholder is mistaken for a fallback result

Control: the wrapper assigns the error before returning, never invokes the
unsafe operation after failed validation, and returns only a fully initialized
backend-owned placeholder. Source data, public docs, editor facts, tests, and
benchmarks assign no semantic value to its bits. Examples inspect `error` before
using the result, while explicitly acknowledging that C++ does not enforce that
inspection. A real fallback or adaptive operation requires a separately named
API.

### Rust becomes unidiomatic or unsound

Control: every unchecked UB-capable operation is `unsafe fn`; every checked
operation uses references/slices or other sound types and returns `Result`.
The naming tradeoff is documented before v1 rather than hidden.

### Checks drift from operation semantics

Control: source-authored typed preconditions and operand roles are the single
semantic owner. Backends translate finalized check plans; renderers do not
reclassify operations.

### Editor support becomes a second semantics implementation

Control: completion, diagnostics, hover, occurrences, references, tokens, and
authored explorer facts project the parser/schema and typed catalog descriptor
registry. Backend checked availability is shown only from a finalized compiler
analysis plan. The TypeScript client owns presentation only, and
`preconditions` never enters the generated TSIL-region keyword inventory.

### Transitive calls leak or lose obligations

Control: retain conservative caller-safety propagation and require every
transitive obligation to match an explicit root precondition before generating a
checked wrapper. Add call-closure tests for matched and unmatched obligations; do
not invent proof or discharge semantics from raw target text.

### Masked operations reject irrelevant lanes

Control: the lowered check plan carries the control-mask binding and explicitly
selects active-lane validation. Tests cover invalid inactive lanes.

### Checked wrappers acquire hidden fallback behavior

Control: a failed validation reports an error without dispatch. Any returned
C++ placeholder is initialized but semantically unspecified and is never
presented as an operation result. Adaptive behavior requires a separately named
and documented API and is outside this plan.

## Out of scope

This plan does not itself resolve every finding in the v1 audit. Separate
release slices are still required for:

- the GCC intrinsic-mask warning;
- complete C++ and Rust API documentation beyond safety contracts;
- Rust package-content reproducibility;
- general generated-artifact size reduction;
- stable-public-surface selection and semver ratcheting; and
- unsupported hardware/profile implementation gaps.

It also does not introduce exceptions, a global runtime safety mode, a compile
flag that silently changes all API behavior, pointer ownership tracking, a
general allocator, a target-language parser, a nonportable calling convention,
or a universal register-residency guarantee.

## Definition of done

The refactor is complete when:

1. every stable public operation is classified as total, statically
   constrained, dynamically preconditioned, or unsafe/uncheckable;
2. every dynamic precondition has one source declaration and one typed compiler
   descriptor, with an explicit backend consequence mapping;
3. unsuffixed C++ calls contain no compiler-injected runtime validation;
4. unchecked Rust calls remain soundly marked `unsafe` where required;
5. every emitted `*_checked` function checks its complete finalized TSL
   precondition contract, reports a typed error, and performs no operation side
   effects on failure;
6. operations without an honest checked form are explicitly documented as such;
7. semantic guarantees hold identically for unchecked and checked calls;
8. generated docs and examples cover both forms;
9. exact API and checked-coverage baselines prevent silent loss or accidental
   exposure;
10. the showcase demonstrates zero added checking overhead in the ordinary
    path for supported optimized builds and quantifies the chosen checked-path
    cost;
11. C++ value-returning checked APIs return the ordinary value type and accept a
    final error reference, use no value-owning result aggregate or vector output
    parameter, assign the error on every path, and return only an initialized
    semantically unspecified placeholder on failure;
12. supported C++ out-of-line ABI and optimized call-site gates preserve the
    raw value-return convention and show no checked-representation-only result
    materialization; and
13. compiler-owned editor surfaces complete, diagnose, index, and explain
    source preconditions from the typed registry, while the TypeScript client
    and TSIL grammar contain no copied precondition semantics.
