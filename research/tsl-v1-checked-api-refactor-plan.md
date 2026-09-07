# TSL v1 unchecked and checked API refactoring plan

Date: 2026-09-02

Status: Slices 0 through 10 are implemented and have completed their focused
review/fix loops; broader product-quality findings outside this refactor remain
tracked separately before TSL v1.0.0

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

### Caller agency, not mandatory inspection

The checked API assists an expert caller but does not attempt to impose a
mandatory control-flow discipline. In C++, a value-producing checked function
returns the ordinary value type and accepts one explicit final
`precondition_error&` output. A no-value checked function returns the status.
This makes the failure channel visible, keeps examples and tooling able to show
the correct branch, and preserves the ordinary value-return ABI; it does not
prove that the caller read or acted on the status.

`[[nodiscard]]` remains useful assistance: on a value-producing function it
warns when the complete computed value is discarded, and on a status-returning
function it warns when the status is discarded. It is not described as an
error-inspection guarantee. TSL documentation, hover, examples, and tests teach
callers to inspect `error` before relying on a returned value, while leaving the
decision and response policy with the caller. Rust retains its idiomatic
`Result` surface and `must_use` diagnostic under the same principle: a warning
helps the programmer but does not claim to force correct handling.

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
conservative `ImplementationSafety` propagation remains in force. For a direct
caller-unsafe memory specialization, checked admission now requires the
reviewed `raw_pointer` obligation, a complete root-level typed memory
precondition plan, and no safety-reason labels beyond the narrow
implementation-mechanism set observed on the reviewed corpus. Unknown labels,
unchecked indexing, and generic unsafe operations fail closed. The current
lowerer classifies `value_reinterpretation` and `unsafe_callee` as internal-only
framing effects, so those labels do not by themselves block a wrapper. This
guard must not be mistaken for a transitive proof: Slice 9 must make every
callee condition explicitly forwarded or discharged. No stage may try to
prove either fact from opaque target text.

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

Goal: establish a reviewed semantic baseline before changing generated APIs.

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
- record representative C++ and Rust declaration-shape examples. These examples
  support review and focused generation tests; they are not an exhaustive
  compatibility ratchet.

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

Design decision after the C++17 compiler probe: use a small trivially copyable
`tsl::span<T>` with pointer-plus-size and array constructors, `data()`, and
`size()`. Its constructor does not attempt pointer validation. The public
contract requires every constructed span to denote an addressable range of its
declared element type for its complete lifetime; the checked wrapper can then
honestly validate the facts represented by that object: payload extent and the
selected alignment. Rust uses `&[T]` for readable memory and `&mut [T]` for
writable memory, which provide the corresponding language-level validity
evidence.

This slice adds exactly two source precondition values:

- `contiguous_memory_extent`; and
- `selected_memory_alignment`.

They bind to the existing typed memory source or destination according to the
declared `memory.access`, require `memory.addressing=contiguous`, and derive a
scalar-versus-vector payload extent from the typed signature/operand contract.
No source field describes C++ spans, Rust slices, error spellings, or checked
generation policy. Masked contiguous operations deliberately require the full
scalar/vector payload extent; the checked API does not derive a shorter sparse
range from mask bits. Mask-representation operations remain a separate family
for the later irregular/raw-memory slices.

`load_scalar` is not folded into this slice: the current typed `load` operation
deliberately requires a vector result, and weakening that invariant would hide
a distinct scalar-memory semantic shape. It remains in the later raw-memory
classification slice. The existing typed `store` overload family already owns
both scalar and vector payload extents and is covered here.

The public shapes are:

- C++ value loads replace the raw pointer with
  `tsl::span<const typename Vec::base_type>` and retain the final
  `precondition_error&` value-result convention;
- C++ stores replace the raw pointer with
  `tsl::span<typename Vec::base_type>` and return `precondition_error` because
  there is no operation value to return;
- Rust value loads accept `&[S::BaseType]` and return `Result<Value,
  PreconditionError>`; and
- Rust stores accept `&mut [S::BaseType]` and return `Result<(),
  PreconditionError>`.

The ordered errors are `insufficient_extent` before `misaligned`. An aligned
scalar payload requires the base element alignment; an aligned vector payload
requires the selected vector alignment. Unaligned variants perform no address
alignment test. Neither backend clamps the range, changes the selected
alignment policy, or invokes the ordinary raw-pointer function after failure.

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

The unsuffixed C++ pointer and range overloads remain unchecked and take their
driving count from the explicit count or first driving range. In Rust, an
unsuffixed algorithm whose slice relations are safety preconditions denotes the
existing `unsafe` raw-pointer kernel; its `*_checked` companion owns the safe
slice signature and returns `Result`. The descriptive `_raw` spelling may
remain as a compatibility alias, but it is not the canonical v1 name. Algorithms
whose only range is already made valid by a Rust slice and which have no
cross-range, capacity, selected-index, or scale precondition remain total safe
functions and receive no checked twin.

One frozen backend-owned algorithm contract registry declares the driving
range, secondary inputs, masks, indexes, outputs, required extent relations,
selected-address rules, ordered errors, and result category. C++ and Rust
renderers project that registry into target-specific guard fragments and API
documentation; static loop assets retain loop mechanics but do not own or
infer the check policy. Asset placeholders and registry entries are validated
for exact coverage so adding an algorithm cannot silently omit one backend.

Extent conditions mean “covers the driving count,” not “has exactly the same
length.” A longer secondary input, mask store, index output, or value output is
valid and remains untouched beyond the produced/driving extent. Failures use
`insufficient_input` for a secondary input or mask store,
`insufficient_output` for a writable output/index range,
`index_out_of_bounds` for a selected row outside a represented input, and
`address_overflow` or `misaligned` when a non-default byte scale cannot form a
valid aligned in-range element address. Every guard runs before dispatch, so a
failure performs no output write and does not invoke a stateful operation.

For selected-row algorithms, the default checked spelling validates ordinary
element indexes. C++ also validates its existing compile-time `Scale` template
argument's address arithmetic; Rust exposes an explicit
`*_scaled_checked<const SCALE: u32>` companion alongside the default
`*_checked` form. A scale that cannot fit the generated immediate remains a
compile-time diagnostic. Runtime index multiplication overflow, resulting
misalignment, and an address outside either represented input are distinct
checked failures.

C++ count results use zero as the failure placeholder. Generic aggregate
results follow the repository-wide direct-value/error-output convention and
therefore require a default-constructible result type; the generated wrapper
states that constraint explicitly. Rust `Result` needs no placeholder.

C++ checked range wrappers do not accept caller alignment promises. They
dispatch through `alignment::detect`, so an incorrect `assume_*_aligned`
template argument cannot preserve undefined behavior behind a checked name.
The unsuffixed expert overloads retain every explicit alignment policy.

Implement `transform_unary` and `transform_binary` as the vertical pilot, run
the design-review/fix loop, and only then migrate predicate, masked, selected,
aggregate, and consume families through the same registry. Runtime dispatch
uses the same binary contract rather than keeping an independent equality
assertion.

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

Observed Slice 6 evidence:

- `indexed_memory_address_valid` and `compacted_memory_extent` are typed source
  preconditions over the new indexed/compacted memory-addressing facts; the
  source corpus contains no backend result, span, slice, or error spelling.
- Checked vector-index gather/scatter, partial narrow gather, compress-store,
  and expand-load validate complete enriched spans/slices before the unchecked
  operation. Signed-negative indexes, scaled-address overflow, misalignment,
  active-lane-only masked access, exact/short compacted capacity, empty inactive
  masks, and destination canaries are covered by generated C++ and Rust
  consumers.
- Post-implementation review found that vector-indexed wrappers validated the
  index vector's lane count even where the ordinary operation consumes one
  index per result-vector lane. `memory.indexed_lanes` now owns that distinction
  in source data; catalog validation, lowering, editor projections, both
  backends, documentation, stage dumps, and generated consumers project it.
- The same review found that compacted wrappers checked capacity but omitted
  the source-selected aligned-memory contract. `compress_store` and
  `expand_load` now declare both compacted extent and selected alignment;
  wrappers reject misalignment before nonempty access while preserving valid
  all-inactive empty operations.
- Pointer-indexed `gather_narrow` remains an explicit coverage gap: a checked
  form needs both a base view and a second extent-carrying index view, which the
  current signature cannot honestly provide.
- The design-review/fix loop found and corrected two projection defects. The
  authored hover initially displayed only the primary error for a multi-error
  condition, and Rust mask-lane testing initially treated compact native masks
  as register-lane masks. Hover now consumes every descriptor-owned error, and
  vector registrations project compact-bitset versus register-mask storage for
  the shared lane test. No precondition vocabulary was copied into the VS Code
  client.
- For the focused `gather`, `gather_narrow_partial`, `scatter`,
  `compress_store`, and `expand_load` AVX2 C++/Rust roots, generated
  specializations increased from 7,458 to 8,698, output from 27,946,905 bytes
  (687,380 lines) to 31,046,046 bytes (760,487 lines), generation time from
  18.350 s to 28.018 s, and build time from 30.536 s to 40.029 s. The primary
  increase is the portable masked indexed-check dependency closure; keeping it
  representation-neutral is preferred to embedding mask-layout rules in the
  wrapper renderer. Slice 8 must report this cost against the complete
  pre-refactor release baseline.
- Focused compiler, C++/Rust consumer, sanitizer, documentation, census,
  authoring, and editor gates pass. The ordinary suite passes with 2,673 tests
  and 119 expected skips; the generated build/value matrix passes all 84 gates.

### Slice 7 — Remaining raw-memory and allocation APIs

Goal: classify allocation, deallocation, copy, random-output, and other raw
memory operations without overclaiming.

Outcomes:

- ordinary allocation failure does not create a checked twin because the base
  return already represents it;
- `allocate_aligned` likewise has no checked twin: its current implementations
  are caller-safe and return the ordinary null failure representation rather
  than declaring a catastrophic caller precondition;
- `memory_cp` has no honest checked twin for its current signature. Although
  the count is semantically bytes, count and copy kind are vector-base scalars
  (including signed and floating domains), and bare pointers establish neither
  capacity nor non-overlap. A future byte-view API must first define those
  contracts;
- a raw-pointer deallocator cannot validate allocation provenance and should
  not receive a misleading checked twin; and
- an owning allocation/RAII API, if desired, is a separate v1 feature decision
  rather than a suffix wrapper.

Validation: exact checked-coverage report plus focused allocator/copy tests. Do
not broaden this slice into a general memory-management library.

Observed Slice 7 evidence:

- Source data now declares typed scalar-load, widening-load, and random-output
  contracts. `load_scalar` and `random_step` have dedicated operation kinds;
  widening load reuses the load operation and projects a typed `target_vector`
  payload extent from its result-target relationship.
- C++ emits direct-value/error-output checked companions over spans, and Rust
  emits safe `Result` companions over slices. Scalar load and random output
  require one element; widening load requires exactly the target vector's
  logical lane count. Empty/one-short failure paths do not invoke the ordinary
  operation, while valid generated consumers verify the loaded values and the
  hardware-random status.
- Allocation, aligned allocation, deallocation, `memory_cp`, mask
  representation storage, and pointer-indexed `gather_narrow` receive no
  misleading checked twin. The census records the exact reason for each
  omission. It now contains 33 caller-unsafe callable identities, of which 11
  remain checked-source coverage gaps, plus 138 applicable safety-metadata
  gaps (26 caller-visible).
- The design-review/fix loop found and corrected three integration defects:
  widening loads were initially admitted into the ordinary load/store policy
  facade, the C++ checked free function was emitted in two definition stages,
  and Rust unaligned store specializations initially lost required overload
  helper methods. It also corrected the raw-copy census rationale to preserve
  the declared byte unit while identifying its actual size-domain, capacity,
  and overlap gaps.
- Compiler-owned operation completion exposes `load_scalar` and `random_step`
  without client-side vocabulary. Focused Doxygen, rustdoc, Sphinx, generated
  GCC/Clang consumers, Rust consumers, allocator/copy builds, and the VS Code
  unit/grammar suite pass. The ordinary compiler suite passes with 2,682 tests
  and 121 expected skips; the complete generated build/value matrix passes all
  84 gates.
- For the focused `load_scalar`, `load_convert_up`, `random_step`, and
  `to_array` AVX2 C++/Rust roots, the specialization/artifact counts remain
  4,206/54. Output increases from 15,155,944 bytes (369,249 lines) to
  15,230,370 bytes (370,361 lines), a 74,426-byte/1,112-line increase.
  Generation measured 12.11 s before and 11.02 s after; build verification
  measured 21.52 s before and 20.87 s after. The timing differences are noise,
  not a claimed speedup; no focused compile-time regression was observed.
- Focused execution used native x86-64 AVX2. The valid RDRAND branch was gated
  by runtime feature detection; the empty checked failure path is executable
  without invoking RDRAND. Cross-family runtime behavior remains limited to
  the supported toolchains/runners exercised by the complete generated matrix.

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
- a typed public-contract baseline plus representative declaration-shape
  examples; and
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

Observed after implementation:

- The generated overviews and shared checked-API guide define the same
  unsuffixed/checked contract, residual span/reference obligations, C++ direct
  value plus error-reference convention, and Rust `Result` convention.
  Doxygen now consumes the facade and stable core/algorithm headers, and its
  strict validator checks public types, every algorithm family, primitive
  prose, callable identity uniqueness, and ordinary twins for checked names.
- The typed v1 public baseline freezes 181 primitive families, 44 C++ algorithm
  families, 35 C++ checked-algorithm families, 174 Rust algorithm names,
  stable root/core identities, source signature semantics, checked-condition
  descriptors, checked error spellings, and algorithm contracts. The checked
  census remains exact at 33 caller-unsafe identities, including eleven
  explicit no-honest-twin gaps. It does not yet ratchet every exact emitted
  backend declaration.
- Post-implementation review tightened checked-memory admission: a range
  signature may discharge the reviewed `raw_pointer` obligation, but it cannot
  silently erase unknown safety labels, unchecked indexing, generic unsafe
  operations. Compiler-derived internal-only value-reinterpretation and
  unsafe-callee framing effects remain compatible; this does not resolve the
  transitive callee condition, which remains Slice 9's release gate. The
  current corpus remains admitted without treating an unclassified direct
  caller obligation as discharged.
- Strict Rustdoc, two executable overview doctests, strict Doxygen, the Sphinx
  site, GCC/Clang documentation consumers, the Python LSP suite, VS Code unit
  and integration suites, and the bundled Linux x64 runtime-package smoke gate
  pass. Building full Rustdoc leaves the 68-file Cargo publish set byte-for-byte
  identical at the package-list level.
- Against `08954770`, the explicit release corpus grows by 45,523,654 bytes
  (+2.678%) and 187,557 lines (+0.463%); generation changes from 152.63 s to
  157.17 s. The compressed Rust package grows from 2,553,107 to 2,662,921
  bytes (+4.301%).
- The maintained scalar/AVX2 C++ and Rust mechanism consumers execute raw,
  unsuffixed, checked-valid, and checked-failure cases for lane extraction,
  integer division, and aligned load. C++ unsuffixed timings and codegen track
  the raw paths, checked call sites preserve direct register returns, and every
  failure avoids the operation. The experiment also exposes a pre-existing
  Rust AVX2 cross-crate inlining cost independent of checking. Full commands,
  measurements, disassembly fingerprints, and limitations are in
  [the release evidence](tsl-v1-checked-api-release-evidence.md).
- Final gates pass with 2,689 ordinary compiler tests, 46 checked-API
  generated/ABI tests, and all 84 generated build/value tests; the expected
  skips are recorded in the release evidence.

### Slice 9 — Explicit transitive-precondition accounting

Goal: make every call from one generated primitive to a dynamically
preconditioned primitive carry a source-visible, typed disposition.

The current compiler records the selected callee identity and wraps a call to a
caller-unsafe Rust primitive in a local `unsafe` block. Dependency closure then
propagates the need for an internal unsafe frame, but intentionally does not
make the caller's public function unsafe. This is correct for calls over
compiler-sized local arrays and for calls whose arguments have been sanitized;
blindly propagating caller unsafety would make those sound abstractions unsafe.
It is not sufficient as a v1 proof, however: `CallDependency` does not record
which callee precondition was forwarded or discharged, so the compiler cannot
distinguish those cases from an accidentally lost caller obligation.

Deliverables:

- extend the recognized TSIL call semantics with a minimal source-authored,
  typed disposition for every applicable catastrophic callee precondition;
- represent each disposition in the call region and lowered dependency model,
  with the callee condition, source span, and either an explicit matching root
  precondition or an explicit implementation-author discharge assertion;
- validate forwarded conditions from typed operand identities and reject
  ambiguous or unmatched forwarding rather than interpreting raw C++ or Rust
  expressions;
- require an explicit discharge assertion for internally established facts such
  as compiler-sized local storage or sanitized nonzero divisors; the assertion
  is the implementation author's unsafe proof boundary and is visible to audit
  tooling;
- make checked-wrapper admission fail closed when dependency closure contains an
  unresolved applicable obligation;
- expose the new call-site semantics through compiler-owned diagnostics, hover,
  references, completion, stage dumps, and the primitive explorer, without
  copying the vocabulary into the TypeScript client; and
- annotate and ratchet every current call to `div`, `mod`, `load`, and `store`
  that carries a catastrophic dynamic precondition.

Validation: focused closure tests for direct and recursive forwarding,
explicit discharge, masked type applicability, immediate compile-time
discharge, compiler-sized local memory, ambiguous overloads, and source-located
missing/stale annotations; generated Rust safety tests; and a deterministic
maintenance report with no unresolved current-corpus obligations.

Stop release if the implementation requires parsing raw target-language text,
silently treats a local `unsafe` block as proof, or propagates caller unsafety
through every abstraction regardless of an explicit discharge.

Implementation and review evidence:

- `call<...>` now accepts canonical `forward[...]` and `discharge[...]` bags.
  The parser retains their exact source occurrences, catalog validation resolves
  them against typed callee contracts, and lowering attaches the resulting
  obligations to typed dependency origins. Compiler-created checked-guard and
  fixed-native edges carry distinct typed origins rather than pretending to be
  source assertions.
- Exact forwarding requires an unchanged vector identity, exact caller/callee
  parameter identities, the same mask identity for mask-sensitive conditions,
  and the same typed memory addressing, payload, and indexed-lane context.
  Calls that transform any of those facts require an explicit author
  `discharge[...]`; no raw target text is parsed to infer a proof.
- Closure propagates unresolved obligations conservatively across alternatives
  and duplicate lowered identities, and checked-wrapper planning refuses any
  specialization group containing such a gap. Invalid source claims also fail
  lowering at their exact condition span.
- The validated corpus contains 127 dispositions: 9 exact forwards and 118
  explicit discharges, with zero unresolved obligations. The deterministic,
  schema-versioned inventory is available through
  `tslc audit call-preconditions --format json` and is ratcheted by an exact
  corpus test.
- Compiler-owned completion, diagnostics, hover/references, semantic tokens,
  explorer records, explain output, and lowered-stage dumps expose the same
  facts. The TypeScript client renders opaque compiler-provided strings and
  contains no condition vocabulary or proof rules.
- The design-review/fix loop rejected forwarding across changed vector and
  memory-payload identities. That review exposed an SVE `f32`-to-`f64`
  widening implementation whose internal full-width load could require more
  input than the public target-vector extent. It now uses a predicate-limited
  load owned by a typed read/load primitive contract; the ownership regression
  test keys off those semantic facts rather than a primitive-name allowlist.
- Validation passes: 2,731 ordinary compiler tests with 122 expected skips;
  all 84 generated build/value tests; 453 focused compiler/authoring tests with
  16 expected skips; 23 VS Code unit tests plus both grammar tests; complete
  scalar/AVX2 C++ and Rust generation (50,984 specializations, 91 artifacts);
  and focused SVE C++ cross-build/value execution under QEMU (3,363 generated
  specializations and six successful build/test commands). `compileall`, mypy,
  corpus check, shell syntax, and diff-whitespace gates also pass.

### Slice 10 — Exact backend public-declaration manifest

Goal: make public compatibility exact without parsing or hashing rendered target
text.

The typed source-family baseline added in Slice 8 protects the semantic inputs
to generation, and focused compile tests protect representative declarations.
Neither proves that every emitted C++ and Rust public declaration is stable: a
renderer could still change a qualifier, generic bound, overload, visibility,
module reachability, parameter type, or checked result form without changing
the current baseline. The reviewed `.snap` files are examples and must not be
treated as exhaustive release ratchets.

Deliverables:

- backend-owned frozen declaration records for every stable C++ and Rust public
  item, including public name and owner, reachability, template/type/const
  parameters and bounds, parameter types and roles, qualifiers and safety,
  result/error form, ordinary/checked relationship, and overload identity;
- renderers that format those finalized records rather than independently
  reconstructing declaration semantics;
- one deterministic manifest serializer over the same records, with an
  intentional schema-version bump and readable compatibility diffs;
- classification of every emitted public item as stable, explicitly unstable,
  or implementation detail, with no unclassified exported declaration; and
- exact parity tests proving that each stable rendered declaration is owned by
  exactly one manifest record for C++, the Rust opaque facade, profile
  callables, and stable algorithm entry points.

The declaration records belong in their respective backends because C++
`noexcept`, `[[nodiscard]]`, reference/output conventions, and overload sets are
not Rust `unsafe`, slice, const-generic, or `Result` semantics. Shared lowered
facts remain backend-neutral inputs. The maintenance command may serialize the
records but must not re-derive signatures, inspect source bodies, regex-parse
target code, or make render decisions.

Validation: deterministic manifests under repeated generation and source-order
perturbation; one-record/one-declaration coverage; negative tests for qualifier,
visibility, bound, parameter, result, checked-twin, and reachability drift;
strict generated C++/Rust compilation and documentation; and the full public
baseline, checked-census, generated-build, and editor/package gates.

Stop release if either backend cannot name a single typed owner for a stable
declaration fact. Do not paper over that ownership gap with whole-artifact
hashes or target-language parsing.

Implementation and review evidence:

- Frozen C++ and Rust backend records now own exact primitive wrappers, checked
  twins, algorithms, opaque-facade types and callables, stable static types and
  members, root reexports, language-specific qualifiers/safety, and typed
  selection reachability. Rust definition identities are distinct from their
  crate-root reexports.
- Stable declaration heads are rendered through named asset holes or directly
  from those records. The compatibility tests no longer regex-parse algorithm
  assets or hash a complete Rust module; static and algorithm holes are checked
  against their record inventories.
- Every remaining exported surface is classified stable, unstable, or
  implementation detail. Recursive defaults are restricted to explicitly
  non-stable module/type subtrees; stable exceptions still require exact
  records, and stable overload sets are rejected.
- Each generated project ships a deterministic `public-api.json`. The v3
  reviewed baseline contains 797 C++ and 4,937 Rust records for scalar/AVX2;
  Rust correctly records the selected AVX2 surface plus its generic fallback.
- The review/fix loop removed checked/result inference from target spelling and
  name suffixes, made declaration relations resolve one exact owner, separated
  Rust facade definitions from root reexports, modeled `crate::profile` as its
  actual target-selected reexport and `crate::profile::algo` as its stable child
  module, added exact C++ `span`/`array_type`/policy member declarations, removed
  duplicate signature construction from renderers, and made Rust algorithm
  support reexports backend-owned rather than renderer literals.
- Focused negative tests cover C++ specifiers, bounds, parameter declarations,
  results, `noexcept`, method qualifiers, and reachability; Rust visibility,
  bounds, parameters, results, `unsafe`, and reachability; plus missing or
  non-ordinary checked twins and illegal coarse stable records.

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

Resolved control: Slice 9 adds an explicit typed forwarded/discharged
disposition for every applicable catastrophic callee condition. Exact
forwarding is compiler-validated from typed identities; transformed and local
proofs remain visible author discharges. Dependency closure propagates any
unresolved obligation and checked-wrapper admission fails closed. No proof is
inferred from raw target text or from a local unsafe frame.

### Masked operations reject irrelevant lanes

Control: the lowered check plan carries the control-mask binding and explicitly
selects active-lane validation. Tests cover invalid inactive lanes.

### Checked wrappers acquire hidden fallback behavior

Control: a failed validation reports an error without dispatch. Any returned
C++ placeholder is initialized but semantically unspecified and is never
presented as an operation result. Adaptive behavior requires a separately named
and documented API and is outside this plan.

## Out of scope

This refactor does not resolve every finding in the broader v1 audit. Remaining
work outside this plan includes:

- unrelated warnings in full-corpus native generated headers (the checked-API
  mask-layout trait warning was fixed during post-implementation review);
- general generated-artifact size reduction;
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

Post-implementation review validates all thirteen items for the declared v1
surface after the corrections recorded above. Slice 9 supplies explicit
transitive catastrophic-precondition accounting; Slice 10 classifies and
ratchets exact backend declarations and selection reachability. Broader warning
cleanliness, unsupported hardware/profile coverage, and artifact-size work from
the original product audit remain outside this refactor's definition of done.
