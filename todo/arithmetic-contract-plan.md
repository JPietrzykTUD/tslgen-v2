# Division and Remainder Arithmetic Contract Plan

## Status and authority

This is the implementation plan for making `div`, `mod`, and `mod_imm`
backend-independent arithmetic operations, with a follow-on projection of the
normalized unmasked operations through Rust's `Div` and `Rem` traits.

Implementation status as of 2026-07-22:

- Slices 1 through 5 are implemented, reviewed, validated, and committed.
- Slice 6 is explicitly deferred until the separate generated Rust API work
  provides the owned fixed-lane `Simd<T, N>` facade and its typed facade-planning
  boundary. The current generated Rust `Simd<T, Ext>` is a zero-sized type
  descriptor whose associated `RegisterType` owns the lanes; it is not a sound
  substitute for the planned public value facade.
- No `Div` or `Rem` implementation is projected onto the current descriptor,
  generic storage type, scalar primitives, or hardware register types while
  that prerequisite is absent.

The repository charters, active source data, compiler code, and tests remain
authoritative. This plan records the following settled product decisions:

- `tsldata` owns the language-neutral arithmetic contract. Rust trait names,
  panic APIs, C++ exception types, and intrinsic names do not enter source data.
- The source contract consists of an explicit nonempty operation set, explicit
  parameter-bound operand roles, and atomic guarantees. A declaration may list
  both `division` and `remainder`; no operation is inferred from guarantees.
- Guarantees are partial positive assertions. Applicability and conflicts are
  validated centrally, while each consumer requires the guarantee subset it
  needs.
- Integer quotient rounding is toward zero, and integer remainder has the sign
  of the dividend.
- An integer zero divisor fails before any integer division or remainder is
  evaluated. The operation does not return normally; Rust realizes this as a
  panic.
- Signed `MIN / -1` returns `MIN`, and signed `MIN % -1` returns zero.
- Only active masked lanes participate. An inactive operand cannot affect the
  returned value or trigger arithmetic failure.
- Floating division has IEEE 754 value semantics. Floating remainder has
  truncating-quotient/fmod semantics, including signed-zero, infinity, and NaN
  behavior defined below.
- An integer zero immediate is an invalid static parameter for every
  `mod_imm` form, masked or unmasked, regardless of the runtime mask. An
  all-inactive mask does not make `mod_imm<0>` well-formed.
- Static integer-zero validation is performed after lane-width conversion. A
  nonzero source literal whose converted lane-width bit pattern is zero is
  therefore also rejected. This rule is derived from the zero-divisor guarantee
  and an `sImm` divisor role rather than repeated in `params` metadata.
- A floating zero immediate remains well-formed and produces the normal
  floating-remainder result.
- The Rust facade forwards to normalized primitives. It contains no corrective
  arithmetic, operand sanitation, overflow handling, or failure logic.
- `divident` is corrected to `dividend` throughout the affected `div` family.

The existing [generated Rust API plan](rust-api-plan.md) continues to own the
overall public Rust facade topology. This plan supplies the previously deferred
`Div`/`Rem` semantic prerequisite. Its focused operator integration slice is
deferred until that topology exists; it does not reopen or pre-empt unrelated
Rust API decisions.

## Goal and observable acceptance criteria

After this work:

1. TSL authors can declare explicit arithmetic operations, operand-role
   bindings, and atomic guarantees on a primitive. Batch validation, catalog
   inspection, hover, and completion all project the same immutable catalog
   fact.
2. Every supported scalar, generic, and hardware specialization of `div`,
   `mod`, and `mod_imm` produces the same result or failure for the same active
   lanes.
3. Integer division or remainder by zero fails deterministically before a C++
   undefined operation, Rust native operator panic, or target-specific hardware
   result can occur.
4. Signed `MIN / -1` and `MIN % -1` are ordinary successful operations with
   results `MIN` and zero respectively.
5. Inactive masked lanes can contain zero integer divisors without causing
   failure. Zeroing overloads produce zero in those lanes; pass-through
   overloads preserve their documented source value.
6. Every integer `mod_imm` instantiation whose immediate converts to zero in
   the selected lane type is rejected at compile time, including masked forms
   with a statically or dynamically all-inactive mask. Floating zero-immediate
   instantiations compile.
7. Authored tests express successful values, expected runtime arithmetic
   failure, and expected compile-time rejection without embedding C++ or Rust
   harness syntax.
8. Generated differential cases compare generic and hardware behavior over the
   valid integer domain and cover invalid zero divisors separately.
9. In the deferred Rust facade follow-on, `Div` and `Rem` implementations are
   admitted only for compatible typed contracts and delegate directly to the
   corresponding unmasked primitive.

## Exact source contract

The initial `arithmetic` vocabulary has three explicit, closed fields:

- `operations`: one or more observable arithmetic operations;
- `operand_roles`: bindings from semantic roles to declared parameters;
- `guarantees`: atomic semantic facts asserted by the declaration.

Guarantees are positive, partial assertions: omission means the behavior is not
promised. The affected declarations carry the complete sets shown below, while
consumers validate the particular subset they require.

The compiler never infers an operation from its guarantees, primitive name,
signature position, parameter spelling, prose, or implementation body.

Unmasked `div` declarations use:

```text
arithmetic:
  operations [division]
  operand_roles:
    divisor divisor
  guarantees [
    integer_quotient_toward_zero,
    integer_zero_divisor_fails,
    signed_min_div_neg_one_returns_min,
    floating_division_ieee754_values
  ]
```

The right-hand `divisor` in `divisor divisor` is an explicit reference to the
declared parameter. Promotion resolves that reference to its parameter index
and kind; consumers never compare the spelling later.

Masked `div` declarations add one guarantee to the same list:

```text
inactive_lanes_do_not_participate
```

Unmasked `mod` and `mod_imm` declarations use:

```text
arithmetic:
  operations [remainder]
  operand_roles:
    divisor divisor
  guarantees [
    integer_remainder_has_dividend_sign,
    integer_zero_divisor_fails,
    signed_min_rem_neg_one_returns_zero,
    floating_remainder_truncating
  ]
```

Masked `mod` and `mod_imm` declarations likewise add:

```text
inactive_lanes_do_not_participate
```

A primitive that observably produces both division and remainder semantics can
declare both operations and the union of their guarantees:

```text
arithmetic:
  operations [division, remainder]
  operand_roles:
    divisor divisor
  guarantees [
    integer_quotient_toward_zero,
    integer_remainder_has_dividend_sign,
    integer_zero_divisor_fails,
    signed_min_div_neg_one_returns_min,
    signed_min_rem_neg_one_returns_zero,
    floating_division_ieee754_values,
    floating_remainder_truncating
  ]
```

No separate `params` constraint is authored for `mod_imm`. The combination of
`integer_zero_divisor_fails`, an explicit `divisor` role, and an `sImm` binding
implies the settled static well-formedness rule: for an integer specialization,
the immediate's converted lane-width bit pattern must not be zero. This avoids
duplicating the same semantic fact in parameter metadata. It does not reject a
value solely because the selected lane type is floating, and runtime masking
does not exempt an invalid static integer divisor.

### Guarantee definitions

- `integer_quotient_toward_zero`: discard the fractional part of the
  mathematical integer quotient toward zero.
- `integer_remainder_has_dividend_sign`: for a nonzero divisor, remainder is
  consistent with the toward-zero quotient and is zero or has the dividend's
  sign.
- `integer_zero_divisor_fails`: for a runtime divisor, no value is returned when
  a participating integer divisor is zero. The check occurs before `/`, `%`, or
  an intrinsic that has weaker target-specific zero behavior. When the resolved
  divisor role is bound to `sImm`, an integer value whose converted lane-width
  bit pattern is zero is statically ill-formed for every masked and unmasked
  form. Static well-formedness precedes runtime lane participation.
- `signed_min_div_neg_one_returns_min`: the only integral division quotient
  that is not representable, `MIN / -1`, returns `MIN`.
- `signed_min_rem_neg_one_returns_zero`: `MIN % -1` returns zero without
  evaluating a target-language remainder operation that may overflow or panic.
- `floating_division_ieee754_values`: preserve ordinary IEEE 754 returned-value
  behavior for finite values, signed zero, infinities, and NaNs.
- `floating_remainder_truncating`: use `x - trunc(x / y) * y` semantics with
  fmod-style special values. A finite nonzero dividend modulo infinity returns
  the dividend; zero dividends preserve their sign; a zero divisor or infinite
  dividend yields NaN; nonzero finite results have the dividend's sign.
- `inactive_lanes_do_not_participate`: inactive source operands cannot affect
  the returned value or cause arithmetic failure.

The initial floating contract covers result values and classifications. It does
not promise NaN payload/sign preservation, a particular NaN bit pattern,
floating-point status flags, trapping modes, or a non-default rounding mode.
Those require separate evidence and source vocabulary before becoming product
guarantees.

### Structural validation

The compiler must validate this vocabulary without branching on primitive
names or parameter spellings:

- `operations` is a nonempty set containing only `division` and `remainder` in
  the initial vocabulary; both may be present;
- `operand_roles` initially accepts exactly the `divisor` role, whose value
  must reference one declared compatible parameter;
- every division or remainder operation in the initial vocabulary requires a
  resolved divisor role; unsupported multi-divisor shapes receive a
  source-located diagnostic rather than an inferred binding. A future
  reciprocal or fixed-divisor operation must introduce its own explicit
  operation/role rule rather than weaken this one implicitly;
- `guarantees` is a duplicate-free set of registered atomic facts;
- each guarantee has one typed descriptor recording required-all and
  required-any operation sets, numeric domain, mask requirement, prerequisite
  roles, and semantic conflict group. Empty operation sets express an
  operation-independent guarantee;
- quotient and division-overflow guarantees require `division`; remainder-sign
  and remainder-overflow guarantees require `remainder`; the zero-divisor
  guarantee permits either or both;
- `inactive_lanes_do_not_participate` requires a masked declaration and is
  rejected on an unmasked declaration. The affected `div`, `mod`, and
  `mod_imm` families require it on every masked form as a corpus/family
  invariant; the generic schema does not claim that every future masked
  arithmetic contract has this guarantee;
- guarantees are partial positive assertions: omission means "not guaranteed,"
  not an inferred alternative. Catalog validation checks applicability,
  prerequisites, and contradictions, while a consumer such as the Rust facade
  requires the exact facts it needs;
- the existing catalog-owned type-group and selector facts determine whether a
  guarantee is meaningful for any real signed-integer, unsigned-integer, or
  floating slot. Source does not duplicate those domains in another field;
- future alternative guarantees join an existing conflict group. For example,
  a future floor-quotient fact would conflict with
  `integer_quotient_toward_zero`; unused alternatives are not admitted now;
- all declarations with the same primitive name either carry a contract or do
  not. Their operation sets, semantically corresponding operand-role bindings,
  and non-mask guarantees agree; an affected masked declaration adds its
  required mask-local guarantee. Family comparison uses the bound parameter's
  non-mask ordinal and kind, not its absolute index, because a leading mask
  shifts declaration-local indices;
- `integer_zero_divisor_fails` plus a divisor role bound to `sImm` derives one
  static integer-nonzero precondition after lane-width conversion. No source
  author repeats that constraint under `params`.

The guarantee descriptor table is compiler-owned, closed, and typed; it is not
a source-defined guarantee registry. The initial implementation does not add
inheritance, arbitrary predicates, or an expression language. A future
operation or alternative guarantee adds the next proven enum value, descriptor,
and tests in a separate slice.

## Typed ownership and data flow

```text
primitive arithmetic block
        |
        v
parsed primitive field -> closed schema validation -> ArithmeticContract
                                                    on catalog Primitive
        |                                                |
        |                                                +-> check/show/hover/completion
        |                                                |
        |                                                +-> Rust operator eligibility
        v
source TSIL body -> selected implementation -> normalized backend helper calls
                                                    |
                                                    v
                                         C++ and Rust helper assets

operations + guarantees + resolved sImm divisor role
        |
        v
derived lowered arithmetic precondition -> C++ static assertion / Rust const assertion

authored test outcome -> typed case plan -> backend capability -> rendered test
```

The canonical owner is a frozen, slotted `ArithmeticContract` in the catalog,
preferably in a focused `tslc/src/tslc/catalog/arithmetic.py` module with its
closed enum types and invariant helpers. `Primitive` carries
`arithmetic: ArithmeticContract | None`.

The typed vocabulary is:

- `ArithmeticOperation`: initially `DIVISION` and `REMAINDER`;
- `ArithmeticOperandRole`: initially `DIVISOR`;
- `ArithmeticOperandBinding`: role plus the resolved parameter name, index, and
  signature kind;
- `ArithmeticGuarantee`: the eight atomic guarantees above;
- `ArithmeticGuaranteeSpec`: required-all/required-any operation sets plus the
  domain/mask/role/conflict metadata for one guarantee;
- `ArithmeticContract`: frozen operation and guarantee sets plus resolved
  operand bindings.

If `ArithmeticOperandBinding` would merely wrap a tuple without owning
validation or resolved identity, keep the binding as a small frozen tuple-like
value rather than creating a class family. The `ArithmeticContract` must still
offer direct predicates for consumers, deterministic ordering for projections,
and a comparison that excludes mask-local guarantees for same-name family
validation.

The integer nonzero immediate rule is a derived lowered arithmetic precondition,
not an authored `ImmediateParam` field. Lowering derives it only when the typed
contract contains `integer_zero_divisor_fails` and the resolved divisor binding
has kind `sImm`. Backend renderers consume that decided precondition; templates
only format the corresponding assertion.

No consumer may recover arithmetic semantics from `div`, `mod`, `mod_imm`,
`dividend`, parameter position, prose, raw TSIL, C++, Rust, or intrinsic names.
The authored operand-role reference may happen to target a parameter spelled
`divisor`, but consumers use its resolved binding. An explicit Rust presentation
table may associate the known canonical primitive with a Rust trait, but
eligibility must verify the typed operations, guarantees, roles, and signature.

## Current evidence and design findings

- Primitive fields are closed in
  [`_schema_primitives.py`](../tslc/src/tslc/catalog/validation/_schema_primitives.py),
  and [`Primitive`](../tslc/src/tslc/catalog/model.py) has no arithmetic owner.
  Adding source annotations alone would fail catalog validation.
- Current `div` documentation delegates rounding and exceptional behavior to
  the backend and type in
  [`complex.tsl`](../tsldata/primitives/arithmetic/complex.tsl).
- Scalar division uses raw `/`; the C++ remainder helper uses raw `%`; and the
  Rust remainder helper uses `%`. Guards must precede these operations so C++
  never enters undefined behavior and Rust does not apply its native
  `MIN % -1` panic behavior.
- Several masked vector bodies compute an unmasked operation and blend only
  afterward. They therefore evaluate inactive zero divisors today.
- The current SVE floating remainder body reconstructs remainder through
  division and a float-to-integer quotient conversion. That is not an honest
  implementation for NaN, infinity, zero divisors, or quotients outside the
  integer conversion range.
- `mod_imm` broadcasts a cast immediate and delegates to `mod`; its current
  catalog data does not identify the arithmetic divisor role or carry the
  zero-divisor guarantee from which post-conversion static rejection can be
  derived.
- Authored test roles currently cover value and compile-success behavior, not
  expected runtime failure or compile rejection.
- Masked and immediate value-test patterns do not currently compose, so the
  existing masked `mod_imm` authored cases are not generated.
- Automatic differential fuzz uses unconstrained full-width integer operands.
  After deterministic zero failure, it must avoid zero in participating lanes
  and test failure through a dedicated outcome.
- Automatic differential coverage currently does not provide the requested
  masked and immediate equivalence evidence.
- Correcting `divident` affects exact lowering/string tests and downstream
  generated baselines even though it does not alter positional call behavior.

## Scope

### In scope

- typed `arithmetic` schema, promotion, invariants, diagnostics, and source
  spans;
- catalog CLI and compiler-owned editor projections of the same typed fact;
- a derived typed static precondition for an `sImm` divisor when the contract
  guarantees integer zero-divisor failure;
- `div`, masked `div`, `mod`, masked `mod`, `mod_imm`, and masked `mod_imm` in
  `tsldata/primitives/arithmetic/complex.tsl`;
- language-neutral helper calls and the C++/Rust helper assets they select;
- scalar, generic, Clang-vector, x86, NEON, SVE, Wasm, and oneAPI FPGA slots
  currently selected for the affected declarations;
- authored value, runtime-failure, and compile-failure cases;
- masked-immediate planning, valid-domain differential fuzz, and masked or
  immediate generic-versus-hardware evidence;
- generated C++ and Rust build/value verification;
- a deferred forwarding-only Rust `Div`/`Rem` facade slice after the owned
  fixed-lane Rust facade exists;
- the mechanical `divident` to `dividend` correction and directly affected
  tests/baselines.

### Out of scope

- arithmetic contracts for `add`, `sub`, `mul`, shifts, or unrelated
  primitives;
- a general numeric semantics framework, guarantee inheritance, or
  source-defined arithmetic guarantee registry;
- parsing or rewriting raw target-language expressions;
- preserving NaN payloads/signs or specifying the floating-point environment;
- optimizing a correct scalarized fallback before semantic equivalence is
  proven;
- changing benchmark operand-domain ownership or using benchmark metadata as a
  value-test oracle;
- Rust corrective arithmetic in methods, traits, templates, or facade
  renderers;
- unrelated Rust facade topology, assignment traits, dispatch policy, or public
  type work;
- unrelated PIVOT behavior. A generated PIVOT baseline may be refreshed only
  if the parameter spelling change requires it, after reading the tool-local
  instructions and proving no semantic export change.

## Decision gate: C++ realization of `fail`

The target-independent contract is settled as "does not return normally," and
Rust uses `panic!`. Before implementing runtime-failure rendering, confirm the
C++ realization across every advertised C++ target.

The preferred host implementation is a small `[[noreturn]]` helper that throws
`std::domain_error` with a stable integer-zero-divisor marker. It permits an
authored failure case to catch and validate the failure inline, analogous to
Rust `catch_unwind` in generated tests.

Rust failure verification must likewise respect the selected panic strategy:
`catch_unwind` is valid for `panic=unwind`; a `panic=abort` build requires an
isolated subprocess or an explicit verifier capability. This affects the test
harness, not the source contract.

If an advertised no-exception, device, or FPGA path cannot compile that helper,
stop before mixing failure mechanisms. Choose one explicit alternative:

- a backend capability selecting an available non-returning trap/abort helper,
  with generated failure cases isolated in subprocesses; or
- an honest structured unsupported result for the affected target slots.

Do not leave raw `/` or `%` as an implicit C++ failure mechanism, use `assert`
that disappears under `NDEBUG`, or silently give one extension a different
zero-divisor result.

## Vertical slices

The dependency order is:

```text
typed contract
    -> normalized div
    -> normalized mod/mod_imm
    -> runtime-failure and differential test support
    -> derived static immediate rejection and compile-failure verification
    -> [owned Rust facade prerequisite, separate plan]
    -> deferred Rust Div/Rem facade
```

Each slice must leave the repository in a coherent state and include focused
tests at its owning boundary.

### Slice 1 — typed arithmetic contract and authoring projection

**Outcome:** the compiler accepts, validates, stores, reports, and offers
authoring support for the closed arithmetic vocabulary. Production primitives
are not annotated until their bodies conform in the next slices.

**Work:**

1. Add `arithmetic` to the known primitive fields in syntax/parser and catalog
   validation. The generic outer grammar should require no new production.
2. Validate exactly the `operations`, `operand_roles`, and `guarantees` members.
   Diagnose unknown members, operations, roles, or guarantees; duplicates;
   missing/invalid parameter references; guarantee prerequisite or conflict
   violations; illegal mask use; unsupported role shapes; and inconsistent
   same-name declarations with precise source spans.
3. Promote operations, resolved operand bindings, and guarantees into frozen
   enum-backed catalog types, validate them through the compiler-owned
   descriptor table, and attach the resulting `ArithmeticContract` to
   `Primitive`.
4. Resolve the explicitly authored divisor parameter reference to its
   declaration-local index, non-mask ordinal, and signature kind. Never infer
   the role from its name or position.
5. Add representative valid and invalid catalog fixtures, including a
   synthetic next primitive name and a valid combined
   `operations [division, remainder]` contract, to prove the implementation is
   not keyed to `div` or `mod` and does not force mutual exclusion.
6. Project operation and guarantee values plus valid in-scope parameter
   references through completion, semantic tokens, hover/catalog index, and
   `tslc show primitive`. The editor client must not copy the vocabulary.
7. Document the new typed owner in `tslc/DESCRIPTION.md` if the implementation
   changes the described catalog/authoring architecture.

**Likely files:**

- `tslc/src/tslc/syntax/parser.py`
- `tslc/src/tslc/catalog/arithmetic.py` (new, if it remains cohesive)
- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/_builder_primitives.py`
- `tslc/src/tslc/catalog/validation/_schema_primitives.py`
- the focused catalog invariant module used by the builder
- `tslc/src/tslc/authoring_completion.py`
- `tslc/src/tslc/catalog_authoring_index.py`
- `tslc/src/tslc/catalog_index.py`
- `tslc/src/tslc/catalog_cli.py`
- focused catalog, validation, completion, hover/index, and CLI tests

**Acceptance:**

- a valid synthetic contract survives parse and promotion unchanged;
- a combined division-and-remainder contract is valid and retains both
  operations;
- every malformed nearby form has one deterministic actionable diagnostic;
- batch check, catalog show, hover, and completion agree on values and ordering;
- no backend, selector, or primitive-name branch is needed;
- no production arithmetic declaration claims semantics its body does not yet
  implement.

### Slice 2 — normalize the complete `div` family

**Outcome:** unmasked and masked `div` have the authored contract on every
supported implementation and pass ordinary edge-value verification.

**Work:**

1. Add a language-neutral `helper<arith_div>` mapping in the C++ and Rust
   translation data and implement the corresponding backend helpers.
2. For integers, guard zero and signed `MIN / -1` before using native `/` or a
   target intrinsic. Return `MIN` for the signed overflow pair.
3. For floating types, preserve native IEEE returned-value division without an
   integer-zero precheck.
4. Make scalar and generic paths terminate in the normalized helper.
5. Audit every selected hardware slot. Keep a direct intrinsic only when its
   complete active-lane behavior matches the contract; otherwise precheck and
   correct, compose semantic primitives, scalarize, or leave a deterministic
   unsupported slot.
6. Rewrite eager masked paths so original inactive operands never reach the
   normalized operation. The preferred vector recipe is to select safe inactive
   operands (`0` dividend and `1` divisor), evaluate, and then apply the
   documented zero or pass-through result. Scalar paths may branch per lane;
   exact predicated instructions may remain when they satisfy the contract.
7. Add the exact division operation, divisor-role binding, and guarantee set to
   every `div` declaration and replace the backend-dependent prose/semantics
   with the normalized contract.
8. Correct `divident` to `dividend` throughout this family and update exact
   source/lowering expectations separately from semantic assertions.
9. Add ordinary authored cases for quotient signs, signed `MIN / -1`, floating
   signed zero, finite divided by zero, zero divided by zero, infinities, and
   NaNs. Runtime integer-zero failure cases wait for Slice 4.

**Likely files:**

- `tsldata/primitives/arithmetic/complex.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tslc/src/tslc/backend/assets/tsl_core.hpp`
- `tslc/src/tslc/backend/assets/tsl_core.rs`
- focused selection/lowering/backend-helper tests
- exact-string and generated baseline tests affected by the spelling repair

**Acceptance:**

- C++ cannot reach integer `/` with zero or the signed overflow pair;
- Rust does not rely on native `/` to define the overflow pair;
- an inactive zero divisor cannot reach the unmasked operation;
- floating zero division remains a value operation, not `fail`;
- scalar, generic, and each available hardware profile agree on ordinary edge
  values in both generated languages;
- unsupported or unverified hardware slots are explicit.

### Slice 3 — normalize `mod` and `mod_imm` runtime semantics

**Outcome:** unmasked and masked remainder implementations have one result and
runtime-failure contract. `mod_imm` runtime bodies are normalized; static
rejection is completed in Slice 5.

**Work:**

1. Strengthen `helper<arith_rem>` for integer zero and signed `MIN % -1` before
   native `%`; return zero for the signed overflow pair.
2. Keep floating remainder on fmod-equivalent helpers. Replace the SVE
   division/float-to-integer reconstruction with an honest helper-backed or
   per-lane implementation.
3. Make scalar/generic and scalarized hardware paths terminate in the same
   normalized helper.
4. Audit direct or composed hardware implementations for zero behavior,
   quotient overflow, sign, and special floating values. A target-specific
   divide/multiply/subtract recipe is legal only if it implements the whole
   contract.
5. Apply the same safe-inactive-operand strategy to every masked zeroing and
   pass-through `mod` body.
6. Keep `mod_imm` as semantic composition through `mod` after broadcasting the
   converted immediate; do not duplicate remainder correction in the immediate
   wrapper.
7. Add the exact remainder operation, divisor-role binding, and guarantee set
   to all `mod` and `mod_imm` declarations and normalize their documentation.
8. Add ordinary authored cases for positive/negative dividend and divisor
   combinations, signed `MIN % -1`, signed floating remainder, signed zero,
   finite modulo infinity, infinity modulo finite, zero divisor NaNs, and NaN
   inputs.

**Acceptance:**

- C++ cannot reach integer `%` with zero or `MIN/-1`;
- Rust does not rely on native `%` to define `MIN%-1`;
- SVE floating remainder has no float-to-integer quotient conversion;
- inactive integer zero divisors do not fail in masked `mod`;
- `mod_imm` contains no independent corrective arithmetic;
- ordinary scalar, generic, and available hardware results agree in C++ and
  Rust.

### Slice 4 — runtime-failure, masked-immediate, and differential tests

**Outcome:** authored tests can prove active-lane failure, inactive-lane
non-failure, masked-immediate values, and generic-versus-hardware equivalence.

**Authored test vocabulary:**

Add language-neutral failure roles rather than backend harness text. The
recommended initial forms are:

```text
role "runtime_failure"
case {inputs [...], failure "integer_zero_divisor"}
```

and, for Slice 5:

```text
role "compile_failure"
case {inputs [...], failure "integer_zero_divisor"}
```

Value cases retain `expected`; failure cases require `failure` and reject
`expected`. The initial closed failure reason is `integer_zero_divisor`.

**Work:**

1. Extend test schema and promotion with typed runtime/compile failure roles and
   a typed failure reason. Preserve source spans and deterministic validation.
   `failure "integer_zero_divisor"` is legal only when the contract contains
   `integer_zero_divisor_fails`, resolves a divisor role, and selects an integer
   lane type. The `runtime_failure` role requires that binding to be a runtime
   operand; `compile_failure` requires an `sImm` binding and the derived static
   precondition. Reject a role that cannot exercise its stated failure phase.
2. Add a backend-neutral runtime-failure case plan and renderer capability.
   C++ and Rust renderers check the selected backend realization without
   embedding backend syntax in source data. A runtime-failure case must not
   terminate the rest of the generated suite.
3. Generalize the existing immediate pattern to accept the existing mask
   component when the signature contains one mask plus an immediate. Reuse the
   `immediate` case kind if its typed requirements remain honest; add a new kind
   only if distinct invariants are required. Every currently authored masked
   `mod_imm` case must become planned or receive a structured reason.
4. Make differential fuzz consume `integer_zero_divisor_fails` and the divisor
   role's resolved declaration-local index. For integer success cases, generate
   nonzero participating divisors; deliberately permit zero in inactive masked
   lanes. Do not consult benchmark domains, parameter names, or an assumed
   final operand position.
5. Add deterministic edge seeds for `MIN/-1` and negative quotient/remainder
   cases in addition to random valid-domain cases.
6. Extend differential planning to the masked and immediate shapes needed by
   this family. Compare each hardware result/failure against generic with the
   same inputs and mask.
7. Add authored active-zero failure cases for unmasked and masked `div`/`mod`,
   plus ordinary value cases proving an inactive zero does not fail for both
   zeroing and pass-through mask policies.
8. Add coverage assertions so no affected authored case is silently
   `authored_unplanned` or `backend_unsupported` without an explicit expected
   reason.

**Likely files:**

- `tslc/src/tslc/catalog/model.py`
- `tslc/src/tslc/catalog/test_promotion.py`
- `tslc/src/tslc/catalog/validation/_schema_tests.py`
- `tslc/src/tslc/value_tests/_pattern_core.py`
- `tslc/src/tslc/value_tests/patterns.py`
- `tslc/src/tslc/value_tests/case_components.py`
- `tslc/src/tslc/value_tests/case_capabilities.py`
- `tslc/src/tslc/value_tests/case_plan.py`
- focused case-conversion/fuzz planners
- C++ and Rust value-test renderers
- `tslc/src/tslc/value_tests/coverage.py`
- `tslc/tests/test_value_test_planning.py`
- `tslc/tests/test_fuzz_value_tests.py`
- backend capability and generated value-test tests

**Acceptance:**

- an active integer zero case is observed as the intended failure in both
  generated languages;
- the same zero in an inactive lane is an ordinary successful case;
- all existing masked `mod_imm` cases are planned and rendered;
- successful differential fuzz never fails merely because it generated an
  active integer zero divisor;
- explicit failure cases do not masquerade as differential value cases;
- masked and immediate generic-versus-hardware comparisons are represented by
  typed plans, not renderer inference.

### Slice 5 — derived static immediate rejection and negative compilation

**Outcome:** invalid integer immediates fail deterministically at compilation
for every `mod_imm` form, while valid integer and all floating immediates retain
their defined behavior.

**Work:**

1. Add one typed lowered arithmetic precondition derived exactly when
   `integer_zero_divisor_fails` is present and the resolved divisor role is
   bound to an `sImm` parameter. Do not add another authored guarantee or a
   `params` constraint.
2. Resolve the selected lane domain during ordinary lowering. The derived
   precondition applies to every integer specialization and is absent for every
   floating specialization.
3. Preserve the same derived precondition for scalar, generic, hardware,
   masked, and unmasked specializations. Runtime mask values never participate
   in static well-formedness.
4. Emit a C++ `static_assert` and Rust const assertion that compare the
   lane-width integer representation of the immediate with zero. Use unsigned
   lane-width conversion or equivalent modulo-width logic so signed narrowing
   is not implementation-defined. Use one stable diagnostic marker. Emit no
   assertion for floating specializations.
5. Place the assertion at the common generated implementation boundary so all
   scalar, generic, hardware, masked, and unmasked paths receive it without
   duplicating arithmetic semantics in each body or facade.
6. Isolate expected compile-failure cases from normal generated translation
   units/targets. A negative case passes only when compilation fails for the
   stable derived-precondition marker, not for an unrelated compiler error.
7. Add authored compile-failure cases for unmasked integer `mod_imm<0>` and a
   masked integer `mod_imm<0>` with an all-inactive mask. Add a positive float
   zero-immediate case whose expected remainder is NaN where appropriate.
8. Add a narrow-lane case where a lexically nonzero immediate converts to zero,
   proving that validation uses the selected lane domain.

**Likely files:**

- `tslc/src/tslc/catalog/arithmetic.py`
- `tslc/src/tslc/lower/lowerer.py` and the lowered specialization model
- C++ and Rust primitive-wrapper/implementation rendering
- generated project/test target planning
- `tslc/src/tslc/output/` negative compile verification
- catalog, lowering, rendering, build-verification, and authored value-test
  tests

**Acceptance:**

- integer zero is rejected for unmasked and masked `mod_imm` before runtime;
- an all-inactive mask does not exempt a masked integer zero immediate;
- a nonzero immediate that converts to zero in a narrow integer lane is
  rejected;
- floating `mod_imm<0>` compiles and produces floating truncating remainder;
- valid nonzero integer immediates still build and run across both backends;
- negative compilation cannot pass because of an unrelated syntax or toolchain
  failure.

### Slice 6 — deferred forwarding-only Rust `Div` and `Rem`

**Status:** deferred until `rust-api-plan.md` has implemented the owned
fixed-lane `Simd<T, N>` facade and its typed facade-planning boundary. Do not
approximate this slice by implementing standard traits on the current
zero-sized `Simd<T, Ext>` descriptor, `ArrayStorage`, scalar primitives, or
architecture register types. Resume this slice as part of, or after, that
separate Rust API work.

**Outcome:** admitted owned fixed-lane Rust vectors support `/` and `%` through
standard traits with no facade-local arithmetic corrections.

**Work:**

1. Carry the resolved arithmetic contract to the typed Rust facade-planning
   boundary only when that consumer is added. Avoid adding a parallel backend
   enum or string metadata.
2. Add explicit Rust presentation mappings for the canonical unmasked
   `(v, v) -> v` `div` and `mod` primitives.
3. Require that `operations` contains the mapped trait operation, the required
   guarantee subset is present without a conflicting guarantee, the divisor
   role resolves to the compatible right-hand parameter, the result/parameter
   shape is compatible, the call is caller-safe, the element domain is
   supported, and the underlying primitive is emitted. A missing or mismatched
   fact is a structured facade exclusion/diagnostic, not a name-based guess.
   Merely declaring `operations [division, remainder]` does not make a combined
   result eligible for either binary trait; that would require an unambiguous
   typed result projection, which the initial contract does not add.
4. Render `core::ops::Div` and `core::ops::Rem` implementations as one direct
   primitive call. Do not precheck divisors, sanitize lanes, catch/rethrow
   failures, handle `MIN/-1`, or reproduce floating remainder logic.
5. Keep masked and immediate operations as named methods; they do not map to
   binary operator traits.
6. Add renderer tests proving the generated trait body contains only the
   forwarding call and that a near-matching synthetic contract is rejected.
7. Add an external-consumer build/run test comparing `/` and `%` with direct
   primitive calls over ordinary, negative, `MIN/-1`, floating-special, and
   panic cases.

Assignment traits are not silently added by this plan. If `DivAssign` and
`RemAssign` are required by the authoritative Rust API plan at implementation
time, add them as equally thin forwarding assignments in the same facade slice
and state that scope explicitly before editing.

**Acceptance:**

- Rust `/` and `%` match direct normalized primitive calls;
- integer zero panics through the primitive implementation;
- `MIN/-1` produces the settled values;
- floating edge behavior matches the direct primitive;
- facade source contains no corrective arithmetic branch or backend-specific
  semantic inference.

## Authored test matrix

The corpus should include compact cases covering the following behaviors. Use
representative lane widths without duplicating every value at every width;
generated differential and fuzz coverage broadens the matrix.

| Operation/form | Integer cases | Floating cases | Expected mode |
|---|---|---|---|
| `div(v,v)` | signs, truncation, `MIN/-1`, active zero | `+0`, `-0`, finite/zero, zero/zero, infinities, NaN | integer: value/runtime failure; float: value |
| masked zeroing `div` | active zero, inactive zero, mixed signs | inactive special values, signed active results | integer: value/runtime failure; float: value |
| masked pass-through `div` | active zero, inactive zero, preserved lanes | inactive special values, preserved lanes | integer: value/runtime failure; float: value |
| `mod(v,v)` | both divisor signs, dividend-sign result, `MIN%-1`, active zero | signed result, signed zero, zero divisor, infinity, NaN | integer: value/runtime failure; float: value |
| masked zeroing/pass-through `mod` | active zero, inactive zero, `MIN%-1` | inactive special values, signed active result | integer: value/runtime failure; float: value |
| `mod_imm` | ordinary nonzero, narrow-lane converted zero, literal zero | ordinary nonzero, zero immediate | integer: value/compile failure; float: value |
| masked `mod_imm` | ordinary nonzero, all-inactive literal zero | ordinary nonzero, all-inactive float zero | integer: value/compile failure; float: value |
| differential | generic vs each selected hardware slot over valid domain | generic vs hardware specials and ordinary values | generated comparison |

NaN assertions check the NaN class, not a payload or sign. Signed-zero cases
must use the existing bit-aware value comparison so `+0` and `-0` remain
distinct.

## Validation matrix

Run focused checks after each slice and broaden at cross-stage completion.

### Catalog and authoring

```bash
PYTHONPATH=tslc/src python -m tslc check
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog.py \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_authoring_completion.py \
  tslc/tests/test_catalog_index_authoring.py \
  tslc/tests/test_authoring_tools.py
```

Add the closest hover, semantic-token, LSP, and catalog-CLI files actually
touched by the projection. The TypeScript editor suite is necessary only if a
client or generated grammar artifact changes.

### Selection, lowering, and backend rendering

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_select_and_lower_backends.py \
  tslc/tests/test_select_and_lower_extensions.py \
  tslc/tests/test_lower_text.py \
  tslc/tests/test_masks_and_calls.py \
  tslc/tests/test_render_model.py
```

Use the exact existing test filenames if the local split differs; do not create
empty compatibility test modules merely to match this command list.

### Value-test planning and verification

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_value_test_planning.py \
  tslc/tests/test_fuzz_value_tests.py \
  tslc/tests/test_backend_target_capability.py \
  tslc/tests/test_coverage.py

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py
```

Run the smallest useful generated matrix while iterating:

```bash
./dev.sh check --primitive div --profile scalar --extension scalar --backend cpp --type si32
./dev.sh check --primitive mod --profile scalar --extension scalar --backend rust --type si32
./dev.sh build --primitives div,mod,mod_imm --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives div,mod,mod_imm --profiles scalar,avx2 --backends cpp,rust
```

Then cover representative AVX-512 floating division, NEON, SVE, Wasm, and
generic profiles where the configured compiler/runner exists. Use SDE or QEMU
through the existing verifier paths; record unavailable hardware/toolchains as
explicit skips rather than treating them as passing evidence.

### Full compiler checks

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

The Rust facade slice additionally runs its focused facade renderer/planner
tests and an external consumer Cargo build/test through the existing generated
verification infrastructure.

## Risks and controls

| Risk | Control |
|---|---|
| Float zero is accidentally routed through integer failure | Domain-qualified guarantees, selected-base checks, explicit float-zero cases |
| A nonzero immediate narrows to zero | Derive the lane-width check from `integer_zero_divisor_fails` plus the `sImm` divisor role and add a narrow-lane compile-failure case |
| Inactive lanes still execute dangerous operands | Sanitize before eager operations and add inactive-zero cases for every mask guarantee |
| C++ reaches undefined `/` or `%` first | Guard inside the lowest shared helper before any native operator or intrinsic |
| Rust's native overflow panic leaks through | Detect `MIN/-1` before native `/` or `%` and assert settled results |
| Hardware zero/overflow behavior differs | Precheck/correct or scalarize; retain direct intrinsic only with complete semantic evidence |
| SVE floating remainder mishandles specials | Remove float-to-integer reconstruction and compare against helper/generic cases |
| Correctness fallback regresses performance | Establish semantic gates first; benchmark and optimize only as a later evidence-backed slice |
| Differential fuzz now aborts on random zero | Use the declaration-local index resolved from the divisor role to generate the valid domain and isolate failure cases |
| Expected failure hides an unrelated crash/panic | Match a stable failure category/marker and keep one case per generated invocation |
| Compile-failure test passes for the wrong error | Isolate negative targets and require the stable derived-precondition diagnostic marker |
| NaN tests overpromise representation | Assert classification only; test signed zero by bits |
| C++ exception policy is incompatible with a target | Resolve the failure-mechanism gate before test rendering; use a capability or explicit unsupported slot |
| Typo cleanup obscures semantic changes | Keep spelling updates mechanical and review baseline diffs for content equivalence |
| Source metadata becomes an unused duplicate | Require catalog/authoring projection immediately and typed facade/test consumption before completion |
| A combined division-and-remainder contract is projected to the wrong Rust result | Require a compatible single-result shape and reject combined results without a typed result projection |

## Stop conditions

Stop the affected slice and report the blocker if:

- no single C++ failure realization or typed backend capability can cover the
  advertised target set honestly;
- a target intrinsic cannot meet the contract and no safe semantic
  composition, scalar fallback, or explicit unsupported result exists;
- stable Rust cannot express the required concrete const assertion at the
  generated implementation boundary without changing the public immediate
  model substantially;
- post-conversion immediate validation exposes an unresolved cross-language
  immediate conversion difference;
- expected-failure cases cannot be isolated from the generated suite or cannot
  distinguish the intended arithmetic failure from an unrelated failure;
- a proposed helper primitive would be public vocabulary without maintainer
  approval or would introduce a primitive-call cycle;
- hardware verification is required for a claimed supported slot but no native
  runner, SDE, QEMU, or injectable substitute is available;
- the contract implementation begins growing into a general guarantee or
  predicate framework not required by `div`, `mod`, or `mod_imm`.

## Completion criteria

The arithmetic normalization and verification phase (Slices 1 through 5) is
complete only when:

- every affected declaration carries the correct operation set, resolved
  divisor role, and guarantee set, and every malformed contract has
  deterministic diagnostics;
- catalog inspection and editor surfaces project the catalog owner without a
  parallel vocabulary;
- all selected scalar, generic, and hardware implementations either meet the
  same contract or remain explicitly unsupported;
- active integer zero fails and inactive integer zero does not fail for masked
  runtime operations;
- signed `MIN/-1`, negative results, floating specials, and signed remainder
  pass generated C++ and Rust value tests;
- integer zero immediates, including all-inactive masked calls and values that
  narrow to zero, fail compilation for the intended diagnostic;
- floating zero immediates compile and return the documented floating result;
- every affected authored case is planned, intentionally unsupported with a
  typed reason, or verified—none disappear silently;
- valid-domain generic-versus-hardware comparisons cover unmasked, masked, and
  immediate forms supported by the test infrastructure;
- the `divident` spelling is absent from the active family and all required
  baseline changes are explained;
- focused tests, the full Python suite, mypy, compileall, generated build/value
  gates, and `git diff --check` pass, with unavailable hardware checks reported
  explicitly.

The deferred Rust facade follow-on (Slice 6) is complete only when:

- the separately owned fixed-lane Rust facade prerequisite exists;
- Rust `Div`/`Rem` bodies contain only typed forwarding and pass external
  consumer tests; and
- every Slice 6 acceptance criterion above passes without projecting traits
  onto the current descriptor or raw register types.

The complete plan remains open until that deferred follow-on is implemented;
deferral closes the current arithmetic phase without claiming Slice 6 is done.
