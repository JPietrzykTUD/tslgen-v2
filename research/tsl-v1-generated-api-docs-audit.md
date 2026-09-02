# TSL v1.0.0 generated API and documentation audit

Date: 2026-09-02

Status: release-readiness review; no implementation changes are included

Related plan: [TSL unchecked and checked API refactoring plan](tsl-v1-checked-api-refactor-plan.md)

## Executive verdict

The generated TSL product is not ready to be labeled v1.0.0. The compiler
architecture and the generated Rust facade are strong foundations, but one
confirmed C++ semantic defect, one C++ consumer-integration defect, and major
documentation/public-boundary gaps must be resolved first.

| Surface | Verdict | Principal reason |
| --- | --- | --- |
| Generated C++ API | Blocked | Signed integer wrapping invokes undefined behavior, and GCC non-scalar headers fail under `-Werror` |
| Generated Rust API | Conditional | The opaque facade is promising, but the stable public boundary and package contents are not controlled |
| Generated C++ documentation | Blocked | Core types, policies, algorithms, and important overload contracts are absent |
| Generated Rust documentation | Blocked | The landing page contradicts implementation, public documentation is incomplete, and examples are not compiled |

## Scope and method

The review covered the current source corpus, compiler/backend ownership,
release-style generated artifacts, generated consumer projects, Doxygen input,
rustdoc output, and package construction. The principal generated audit tree is
workspace-local at `tslctmp/audit-v1/generated` and is intentionally not
tracked.

The review exercised:

- release-style C++ and Rust generation;
- the repository's generated-consumer verification script;
- minimal scalar, AVX2, and Clang-overlay C++ consumers;
- GCC and Clang warnings-as-errors probes;
- a C++ UBSan signed-overflow probe;
- strict Rust compiler warnings;
- the repository's intended Clippy correctness/suspicious gate;
- a full `-D warnings` Clippy diagnostic run;
- rustdoc warning and missing-documentation checks;
- Rust doctests;
- clean and post-documentation Cargo packaging; and
- the complete generated documentation build.

The release-style generation produced 678,053 specializations across 439
artifacts. It is useful evidence that the pipeline completes, but successful
generation alone does not prove the API contract.

## Findings

### F-01 — Critical: scalar C++ violates the integer-wrapping contract

TSL declares `integer_wrapping` for addition and related operations in
[`fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl#L2), but
the generated scalar C++ specialization evaluates signed addition as ordinary
`left + right`. Signed overflow is undefined behavior in C++.

The generated evidence is visible in
`tslctmp/audit-v1/generated/cpp/include/tsl_scalar.hpp` around line 8217. A
small UBSan consumer calling `tsl::add` with `INT_MAX` and `1` reported signed
integer overflow at runtime. Rust explicitly implements the same contract with
`wrapping_add` in
[`tsl_core.rs`](../tslc/src/tslc/backend/assets/tsl_core.rs#L272).

The generated CMake project adds `-fwrapv` only to its own value-test target in
[`cpp_cmakelists.txt.tmpl`](../tslc/src/tslc/backend/assets/cpp_cmakelists.txt.tmpl#L192).
That makes the differential test agree with hardware SIMD but does not change
the semantics seen by a normal header-library consumer.

This is not a safety-check policy question. Wrapping is a declared operation
semantic and the ordinary function must implement it without relying on a
consumer compiler flag. The same audit must cover subtraction, multiplication,
negation, reductions, and masked variants carrying the guarantee.

Smallest correction:

- lower signed wrapping operations through defined unsigned-bit arithmetic or
  an equivalent backend-owned helper;
- remove the test-only assumption that `-fwrapv` represents consumer behavior;
- add scalar/generic UBSan cases at minimum, maximum, and masked inactive-lane
  edges; and
- require C++ and Rust differential agreement on the declared modular result.

Release evidence required: the overflow probe must return the modular value
without a sanitizer diagnostic under an ordinary consumer build.

### F-02 — High: GCC non-scalar public headers are not warning-clean

A minimal AVX2 consumer built with GCC 15 emits repeated
`-Wignored-attributes` diagnostics and fails when the application enables
`-Werror`. The immediate source is a standard type-trait instantiation on an
intrinsic vector mask type in
[`tsl_core.hpp`](../tslc/src/tslc/backend/assets/tsl_core.hpp#L592):

```cpp
using MaskT = typename Vec::mask_type;
if constexpr (std::is_integral_v<MaskT>) {
```

Types such as `__m256i` trigger the diagnostic. The same AVX2/Clang-overlay
probe passed with Clang 21 and `-Werror`, so this is a GCC-facing public-header
problem rather than a general inability to compile the profile.

The external generated-consumer check currently selects only the scalar C++
profile in
[`verify_generated_consumers.sh`](../supplementary/ci/verify_generated_consumers.sh#L49).
It therefore cannot detect warning failures in advertised native profiles.

Smallest correction:

- classify mask representation without instantiating inappropriate standard
  traits on intrinsic vector types; and
- add external GCC and Clang consumers for scalar and at least one native
  profile with warnings treated as errors.

### F-03 — High: the C++ reference omits most of the public API

Doxygen consumes only a synthetic primitive-declaration header. The configured
input boundary is visible in
[`Doxyfile.in`](../supplementary/docs/cpp/Doxyfile.in#L1), and
[`test_maintenance_documentation.py`](../tslc/tests/test_maintenance_documentation.py#L61)
explicitly asserts that the real generated include directory is not an input.

The resulting Doxygen index contains one namespace, one file, and 210 function
entries, but no documented classes or structs. It consequently omits central
public concepts such as:

- `tsl::simd` and `tsl::reg_param`;
- `dataparallel::native`, `fixed`, `generic`, and compiler overlays;
- alignment and mask-layout policies;
- the complete `tsl::algo` API;
- mask/storage helper types; and
- public preconditions and result/error conventions.

The algorithm API begins in
[`tsl_algorithm.hpp`](../tslc/src/tslc/backend/assets/tsl_algorithm.hpp#L1), but
none of it appears in the generated C++ reference. There is also no generated
C++ README or equivalent getting-started guide.

Primitive documentation is generally useful: it contains a brief description,
detailed semantics, pseudocode, parameters, feature requirements, and safety
facts. That good primitive projection should be retained while the actual
public type and algorithm surface is added.

Smallest correction:

- define the intended stable C++ surface first;
- project its types, policies, algorithms, overloads, and preconditions into a
  typed documentation model;
- keep implementation-detail headers excluded; and
- add a completeness gate over exact intended public identities rather than an
  aggregate Doxygen count.

### F-04 — High: Rust documentation states the wrong profile-selection model

The Rust landing page says that normal builds select a machine profile through
Cargo features and that target-feature auto-selection is not implemented in
[`rust_api.rst.in`](../supplementary/docs/site/rust_api.rst.in#L12).

The generated crate instead selects a profile using compile-target
`cfg(target_feature)` branches with an exact generic fallback. This is also the
documented compiler contract in
[`DESCRIPTION.md`](../tslc/DESCRIPTION.md#L503). The generated Cargo feature
set contains `default`, `std`, and runtime-dispatch controls, not one feature
per machine profile.

This is a user-visible correctness defect: following the documentation leads
to the wrong integration model.

Smallest correction: generate the Rust landing-page selection explanation from
the same backend-owned profile-selection facts used by `lib.rs`, or keep a
short hand-authored description with a test that asserts the relevant claims
against the generated feature and cfg model.

### F-05 — High: the v1 public compatibility boundary is undefined

The generated Rust crate publicly exposes `tsl_core`, `tsl_algorithm`, the
opaque facade, `profile`, and optional runtime dispatch. The public module and
re-export boundary is assembled by the Rust project renderer and templates;
the intended facade ownership is described in
[`DESCRIPTION.md`](../tslc/DESCRIPTION.md#L521).

In the audited artifact, the root facade exported 44 free functions while the
profile-neutral primitive module exported 142. `tsl_core` and `tsl_algorithm`
also expose large public trait and helper surfaces. It is not stated which of
these names are covered by the future 1.x compatibility promise.

C++ similarly exposes primitive wrappers, core helpers, policy types,
algorithms, and macros without a formal stability classification or API
baseline.

The opaque Rust `Simd<T, N>` and `Mask<T, N>` facade is the strongest current
candidate for the stable Rust interface. It provides owned logical values,
operator integration, checked slice conveniences, `#[must_use]`, and explicit
unsafe raw-pointer boundaries. The lower-level profile and substrate APIs may
still be valuable, but they should be explicitly stable, experimental, or
private rather than accidentally becoming a semver commitment.

Smallest correction:

- publish a backend-specific stable-surface manifest;
- hide or clearly classify everything outside it; and
- ratchet exact generated declarations/signatures in CI before assigning
  version 1.0.0.

### F-06 — High: Rust package contents depend on local documentation history

The documentation task writes rustdoc output below the crate at
`rust/docs/target`, as shown in
[`documentation.py`](../tslc/src/tslc/maintenance/documentation.py#L333). The
Cargo manifest template has neither an `include` whitelist nor an `exclude`
rule in
[`rust_cargo.toml.tmpl`](../tslc/src/tslc/backend/assets/rust_cargo.toml.tmpl#L1).

Measured package contents were:

| State | Files | Unpacked | Compressed |
| --- | ---: | ---: | ---: |
| Clean generated crate | 78 | 144.0 MiB | 3.8 MiB |
| After official docs build | 1,141 | 387.5 MiB | 30.5 MiB |

The same source therefore creates materially different packages depending on
whether documentation was built in place. This is a release-reproducibility
defect.

Smallest correction:

- build rustdoc outside the package root;
- define explicit Cargo package contents;
- test `cargo package --list` before and after documentation generation; and
- add missing package metadata, including a description.

### F-07 — High: the generated distribution is exceptionally large

The audited release tree contained approximately:

- 1.4 GiB and 36.6 million lines of C++ headers;
- 145–149 MiB of Rust source;
- 38 MiB and 1.23 million formatted lines in `tsl_facade.rs` alone; and
- individual C++ overlay headers near 33 MiB.

Formatting the full generated project remained CPU-bound for more than eleven
minutes. Minimal selected-profile compilation was much smaller in practice:
approximately 0.70 seconds for scalar C++, 1.27 seconds for GCC AVX2, and 2.65
seconds for the Clang AVX2/overlay probe on the audit host.

This is not automatically a correctness blocker, but it is a v1 product and
maintenance risk for downloads, source indexing, package registries, release
CI, and compiler diagnostics. Adding a naive checked twin for every concrete
specialization would make it materially worse.

Smallest correction: choose and document whether v1 ships a monolithic
all-profile SDK, per-profile products, or consumer-selected slices. Checked
wrappers should be emitted once per public callable family and delegate to the
ordinary implementation rather than duplicate specialization bodies.

### F-08 — Medium: all Rust documentation examples are disabled

`cargo test --doc` discovered 3,156 examples, of which zero ran and all 3,156
were ignored. The comprehensive facade renderer emits every example as
` ```ignore ` in
[`rust_facade_comprehensive.py`](../tslc/src/tslc/render/rust_facade_comprehensive.py#L376).

Smallest correction:

- provide hidden setup for representative examples;
- use ordinary doctests when they can execute generically;
- use `no_run` when the compile check is meaningful but execution is target
  dependent; and
- reserve `ignore` for explicitly justified cases.

### F-09 — Medium: 227 public Rust documentation obligations are missing

`RUSTDOCFLAGS='-D missing_docs' cargo doc` failed with 227 diagnostics. They
include the crate root, public core/algorithm modules, traits, functions, and
helper modules. The crate also has no `//!` overview and its generated README is
only a short package description.

This count depends on the unresolved public-boundary decision. Hiding internal
substrates may remove legitimate obligations; anything retained in the stable
surface should pass `-D missing_docs`.

### F-10 — Medium: pointer result documentation adds an extra pointer level

The generated C++ allocation signature returns `void*`, while its prose says
`void**`. Rust similarly returns `*mut c_void` while documenting
`*mut *mut c_void`.

The documentation result projection calls the free-result type formatter
without preserving the original pointer base identity in
[`cpp_documentation.py`](../tslc/src/tslc/backend/cpp_documentation.py#L123) and
[`rust_documentation.py`](../tslc/src/tslc/backend/rust_documentation.py#L101).

Smallest correction: use the same typed result projection as the actual
signature renderers and add pointer/free-function equivalence tests for both
backends.

### F-11 — Medium: C++ overload documentation is incomplete and duplicated

The canonical vector primitive declaration receives documentation, while the
adjacent policy overload does not. The behavior originates in
[`cpp.py`](../tslc/src/tslc/backend/cpp.py#L439), which attaches one block only
to the vector declaration.

Free functions such as allocation are also emitted repeatedly for different
specialization contexts. The C++ documentation renderer deduplicates complete
rendered strings rather than callable identity in
[`cpp_project.py`](../tslc/src/tslc/render/cpp_project.py#L252), so Doxygen
merges repeated declarations and prose into noisy entries.

Smallest correction: create one documentation record per public callable
identity, attach overload-specific facts, and reject conflicting duplicate
records before formatting.

### F-12 — Medium: C++ range-algorithm preconditions are unstated

Range overloads obtain a count from the first input and pass raw data pointers
for secondary inputs and outputs. For example, `transform_unary` in
[`tsl_algorithm.hpp`](../tslc/src/tslc/backend/assets/tsl_algorithm.hpp#L215)
uses the input size without checking output capacity. Binary, predicate, and
masked families have analogous relationships.

An unchecked C++ algorithm is a legitimate design, but its preconditions must
be part of the public contract. The current C++ documentation omits the
algorithm API entirely, so a caller is not told that secondary inputs, masks,
or outputs must be large enough.

The agreed direction is to retain a zero-overhead unchecked form and add an
explicit checked variant. The detailed design and necessary limitations are in
the related refactoring plan.

## Positive evidence

- Release-style generation completed successfully for the requested
  profile/backend matrix.
- The repository consumer workflow passed a minimal scalar CMake consumer, 21
  Rust examples, and 21 C++ examples/tests.
- A Clang AVX2/overlay consumer passed with warnings treated as errors.
- Rust passed `-D warnings`, `-D invalid-value`, private-interface/bounds
  warnings, and rustdoc `-D warnings`.
- The intended Clippy gate for `correctness` and `suspicious` passed.
- Rust's opaque value facade has a strong safety boundary and idiomatic owned
  `Simd`/`Mask` types.
- Primitive prose and semantic pseudocode are generally useful.
- The compiler already carries typed arithmetic, operation, memory, conversion,
  shift, safety, profile, and target facts through lowering. Corrections can be
  additive to these owners rather than based on parsing generated target text.

## Validation results

| Check | Result |
| --- | --- |
| Release-style generation | Passed; 678,053 specializations, 439 artifacts |
| Full generated documentation build | Passed |
| Generated C++/Rust consumer workflow | Passed |
| Minimal scalar C++ consumer | Passed |
| Minimal GCC AVX2 consumer | Compiled with repeated warnings; failed under `-Werror` |
| Minimal Clang AVX2/overlay consumer | Passed under `-Werror` |
| C++ signed-overflow UBSan probe | Failed with signed-overflow diagnostic |
| Rust strict compiler warnings | Passed |
| Intended Rust Clippy correctness/suspicious gate | Passed |
| Full Clippy `-D warnings` | Failed with 2,523 generated-code style diagnostics |
| Rustdoc `-D warnings` | Passed |
| Rustdoc `-D missing_docs` | Failed with 227 diagnostics |
| Rust doctests | 3,156 ignored; zero compiled as tests |
| `git diff --check` | Passed |

The full Clippy style count is technical debt rather than a demonstrated
correctness defect because the repository deliberately enforces a narrower
correctness/suspicious lint contract today.

## Audit limitations

- The audit compiled representative scalar and x86 native profiles rather than
  executing every generated target/profile combination.
- Hardware-specific ARM, SVE, WASM, FPGA, and emulator paths were not executed.
- The artifact-size observations are measurements on the selected release
  matrix, not a package-registry compatibility claim.
- No API compatibility baseline exists yet, so stability was assessed from
  exposed declarations and repository documentation rather than versioned
  historical comparisons.

## Decisions required before v1.0.0

1. Which Rust names are stable: only the opaque facade, or also `profile`,
   `tsl_core`, `tsl_algorithm`, and runtime dispatch?
2. Which C++ helpers, policies, algorithms, and macros are stable?
3. Is the distributed product monolithic, profile-specific, or generated per
   requested application slice?
4. What exact compiler/version/profile matrix is supported and warning-clean?
5. Which dynamic preconditions receive generated checked variants, and which
   obligations cannot honestly be checked?

## Release recommendation

Do not assign v1.0.0 until at least the following gates pass:

1. declared C++ arithmetic semantics pass sanitizer and cross-backend tests;
2. supported external C++ consumers are warning-clean on scalar and native
   profiles;
3. both stable public surfaces are explicitly enumerated and ratcheted;
4. C++ and Rust documentation cover those surfaces and describe actual profile
   selection;
5. checked and unchecked preconditions are explicit and tested;
6. representative documentation examples compile;
7. Cargo package contents are identical before and after docs generation; and
8. the intended distribution size and profile packaging policy are recorded.
