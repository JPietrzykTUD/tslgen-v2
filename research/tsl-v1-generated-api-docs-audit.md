# TSL v1.0 generated API and documentation audit

Initial audit: 2026-09-02

Release-candidate re-audit: 2026-09-09

Status: no high-severity API or documentation finding remains

Related material:

- [TSL v1 user guide](../docs/tsl-v1-user-guide.md)
- [exact generated support contract](../docs/tsl-v1-support.md)
- [pre-v1 migration guide](../docs/migrating-to-tsl-v1.md)
- [checked-API design review](tsl-v1-checked-api-post-implementation-review.md)
- [C++ quality evidence](../supplementary/release/tsl-v1-cpp-consumer-quality.md)
- [Rust quality evidence](../supplementary/release/tsl-v1-rust-quality.md)

## Executive verdict

The generated TSL library is API/documentation-ready for a v1.0 release
candidate within its published support boundary. The initial audit's critical
signed-arithmetic defect, public-header warning failure, undefined stability
boundary, incomplete references, incorrect Rust profile guidance, package
contamination, pointer-result documentation error, and undocumented algorithm
preconditions have been corrected and ratcheted.

| Surface | Verdict | Principal evidence |
| --- | --- | --- |
| Generated C++ API | Ready within contract | 8,015 exact classified declaration records over 29 profiles; ordinary-include consumers; defined signed wrapping; explicit checked/error ABI |
| Generated Rust API | Ready within contract | 7,201 exact classified declaration records over six profiles; opaque facade; exact `unsafe` projection; Rust 1.89/current-stable gates |
| Generated C++ documentation | Ready | Strict typed-manifest/Doxygen identity coverage includes core types, policies, primitives, overloads, ordinary/checked algorithms, and a CI-compiled example |
| Generated Rust documentation | Ready | Strict missing-doc/link gates; correct target-feature selection model; two executable crate doctests; signature-only fragments labeled as text call forms |

This verdict does not authorize the final tag. Native SVE and RVV/CHORYS
attestations and atomic reproducible release production remain separate release
gates in Slices 13 and 14.

## Scope and method

The re-audit followed the four generated product surfaces from typed owners to
rendered artifacts:

1. source declarations, semantics, preconditions, safety, and extension facts;
2. typed catalog, selection, lowering, dependency closure, and backend plans;
3. exact backend declaration/reachability manifests and generated entry points;
4. C++/Rust consumer builds, strict documentation gates, package contents, and
   checked-in examples.

No target-language parser was used to manufacture semantic facts. Generated
source inspection was used only to confirm that the backend projections and
public manifests were rendered as planned.

The exact support universe is generated from the catalog, machine profiles,
release policy, public-API baseline, and package metadata. It contains 185
primitive callable families, 44 algorithm families, ten scalar element types,
29 C++ profiles, six stable Rust profiles, and explicit runtime-scalable slot
exclusions. The final exact SVE/RVV target ratchet contains 9,239 applicable
slots and 9,994 realization outcomes: every applicable outcome is emitted, and
130 impossible combinations are separately recorded as reviewed exclusions.
Each generated project also carries a scope-exact `public-api.json`.

## Findings, ordered by severity

No critical or high-severity API/documentation finding remains.

### A-01 — Medium: native scalable hardware evidence remains a final-release gate

Full SVE and RVV C++ projects cross-compile and their value suites pass under
QEMU at multiple vector lengths. That establishes compilation and functional
evidence, not native performance or a real CHORYS deployment. Before the final
tag, the same release-candidate artifacts must pass on native SVE and native
RVV/CHORYS machines. If either cannot be obtained, that profile must be labeled
experimental rather than silently retaining the stable claim.

This is a release-evidence gap, not an API/documentation inconsistency: the
support guide and scalable evidence already disclose it.

### A-02 — Medium: the all-profile C++ tree is a poor default distribution unit

The measured all-profile C++ output is roughly 1.73 GB extracted and 50.7 MB as
a gzip archive. Representative consumer translation units still compile in
roughly two to three seconds, so the issue is distribution/indexing cost rather
than an immediate use defect.

The v1 user contract now recommends profile/type/primitive slices and labels the
monolithic tree a reference/stress ceiling. Slice 13 must make the archive
layout match that stated boundary; documentation alone does not make a large
monolithic release artifact acceptable.

### A-03 — Low: C++ compatibility is bounded by the verified compiler matrix

Generated C++ requires C++17 and its generated CMake project requires CMake
3.16. GCC 15.2, Clang 21, WASI Clang 22.1, cross GCC for SVE/RVV, and the CI
MSVC/IntelLLVM lanes define current evidence. The project does not promise that
arbitrarily older compiler releases work. This is now stated as a tested matrix
rather than an implied universal minimum-version guarantee.

### A-04 — Low: advanced Rust substrate modules remain publicly reachable

`tsl_core` and `tsl_algorithm` remain public because generated signatures depend
on them. They are hidden from the stable landing page and are classified as
advanced substrate rather than representation-stable ABI. The exact manifest
distinguishes stable entry points and implementation detail. Making these
modules physically private would require a larger signature redesign and is
not justified for v1.

## 1. Generated C++ API

### Public boundary and compatibility

The stable entry point is `tsl.hpp`. The compatibility surface contains the
reachable `tsl` vector/span/error types, primitive wrappers, checked companions,
data-parallel policies, algorithm functions, and public policy tags. Physical
profile headers, implementation structs, `detail` namespaces, and selection
macros are excluded.

The schema-v3 typed baseline records 8,015 exact declarations across the 29 C++
release profiles. It includes owner, callable identity, template parameters,
runtime parameters and roles, result, qualifiers, overload identity,
checked/ordinary relationship, reachability, stable members, and stability
classification. CI compares these facts rather than hashing formatted C++.

### Semantics and safety

Signed wrapping arithmetic uses defined modular semantics under an ordinary
consumer build; it no longer depends on the generated value test's historical
`-fwrapv` setting. Scalar/generic edge tests, sanitizer probes, and C++/Rust
differential cases cover overflow boundaries.

Unsuffixed operations perform no hidden sanitization. C++ keeps the ordinary
zero-overhead convention and documents caller obligations. A generated checked
twin exists only for a complete catastrophic runtime condition. Value-returning
checked functions preserve the ordinary return type and append
`precondition_error&`; void functions return the error. Failure occurs before
ordinary dispatch and yields only an initialized, semantically unspecified
placeholder for value results.

The chosen form avoids `checked_result<register_type>` and therefore avoids
imposing an aggregate-return ABI that could force vector register spilling. The
compiler cannot force callers to inspect an error reference, so documentation,
`[[nodiscard]]`, examples, and review remain part of correct use.

### Profiles and scalable vectors

The generated CMake interface exports `tsl::tsl` and selects one generated
profile. Native `auto` selection probes ungated profiles; cross builds use the
fallback unless the consumer supplies `TSL_PROFILE` explicitly. Target features
and compiler-capability probes are separate typed decisions.

Runtime-scalable SVE and RVV use runtime lane and predicate semantics. The fixed
SVE128/SVE256/SVE512 profiles are separate fixed-shape compatibility contracts.
The exact support projection excludes only reviewed operations whose signatures
intrinsically require ordered fixed register widths/fixed arrays, fixed-SVE
representation changes for which the compilation mode contains no distinct
same-family width, or source types with no wider/narrower target scalar. It does
not fabricate a static lane count or return an uncontracted heap container.

The re-audit initially found 292 no-candidate records in the three fixed-SVE
profiles. Of these, 247 represented the impossible combinations above and are
now typed policy exclusions. The remaining 45 source slots were a real gap in
base-width `extract_imask`/`insert_imask`. Fixed SVE now implements those
operations by walking and rebuilding native predicates through typed mask
primitives. That path is explicitly classified as reviewed fallback, and
predicate-aware authored cases compile and pass under QEMU for SVE128, SVE256,
and SVE512. CI now runs the target ratchet with `--require-complete`, preventing
recorded gaps from being accepted merely because they appeared in the prior
baseline.

### C++ API verdict

No blocking finding remains. The residual risks are release packaging size and
native scalable attestation, not an untracked C++ declaration or semantic
defect.

## 2. Generated Rust API

### Public boundary and representation

The stable Rust surface is the opaque root `Simd<T, N>`/`Mask<T, N>` facade,
reviewed root re-exports, and the compile-target-selected `profile` primitive
surface. Private representations are sealed behind traits; normal users cannot
construct invalid vector storage through the stable facade.

The exact typed baseline records 7,201 declarations for `sse`, `sse2`, `sse3`,
`avx`, `avx2`, and `knl`, including their shared generic fallback. Stable Rust
SVE/RVV is explicitly unsupported because the current implementation would
depend on unstable/private compiler facilities. This is a deliberate v1 scope,
not a silent generation gap.

### Safety boundary

Rust `unsafe fn` is driven by an outstanding `caller_unsafe` obligation after
dependency closure. It is not driven merely by implementation mechanics. The
current checked census contains 33 exact source callable identities with at
least one caller-unsafe implementation. Every caller-unsafe path carrying
`raw_memory` also carries `raw_pointer`; implementations that use raw-memory
staging internally without an outstanding caller obligation remain publicly
safe. Other unsafe public paths arise from typed catastrophic conditions such
as unchecked runtime lane indices or invalid integer division operands.

This separation is important:

- `internal_unsafe` says generated Rust needs a local unsafe-operation frame;
- `caller_unsafe` says correctness depends on the public caller;
- `raw_memory` describes a mechanism and is not sufficient for the second; and
- `raw_pointer` records a caller-owned validity/provenance boundary.

When every catastrophic runtime condition is representable, the safe checked
twin returns `Result<T, PreconditionError>` or
`Result<(), PreconditionError>`. Range/slice checks cannot validate forged
references, object lifetime, provenance, or concurrent invalidation. Honest
omissions remain explicit in the census.

### Profile selection, MSRV, and packaging

Normal Cargo builds use compile-target `cfg(target_feature)` selection with an
exact generated generic fallback. There are no per-profile Cargo features;
`runtime-dispatch` is a separate optional `std` feature. The crate declares
edition 2021 and Rust 1.89 as its MSRV. Both 1.89 and current stable pass the
release build/lint/doc/value matrix.

Cargo uses an explicit include list. Its package-owned file list is identical
before and after local documentation generation, so generated Rustdoc and
checkout-local files cannot contaminate the crate archive.

### Rust API verdict

No blocking finding remains within the six-profile stable scope. Rust
scalable-vector support is a disclosed future capability, not an implied v1
promise.

## 3. Generated C++ documentation

Doxygen consumes a documentation-only primitive facade plus the stable core,
data-parallel, algorithm-tag, ordinary-algorithm, and checked-algorithm headers.
Strict validation joins generated identities to typed public manifests and
rejects missing prose, duplicate identities, incomplete overloads, invalid
checked relationships, or absent stable type/algorithm records.

The reference states parameter/result types from the same backend projection as
the actual declarations. Pointer-return documentation therefore no longer adds
an erroneous pointer level. Each overload owns its own documentation record,
and repeated free specializations are deduplicated by callable identity rather
than rendered text.

Algorithm documentation states secondary-range, mask, selected-index, output
capacity, alignment, and overlap preconditions. The shared checked API page
documents direct calls, error handling, failure placeholders, and residual C++
object obligations. Its literal C++ example is compiled warning-clean against
the generated scalar library by the package consumer workflow.

### C++ documentation verdict

The complete promised stable surface is reachable from `tsl.hpp` and present in
the generated reference. No blocking documentation finding remains.

## 4. Generated Rust documentation

Rustdoc presents the opaque facade and selected `profile` API as the stable
surface. The landing page correctly describes compile-target feature selection,
the generic fallback, the distinction from runtime dispatch, unsuffixed unsafe
calls, checked `Result`, and the status of lower-level substrate modules.

Strict builds deny Rustdoc warnings, missing public documentation, broken
intra-doc links, and bare URLs. The two crate-level ordinary/checked examples
are complete executable doctests. The former 3,524 context-free fragments were
not executable examples: they referred to parameter names without constructing
values and were silently marked `ignore`. They are now labeled `Call form` and
rendered as text. This leaves no ignored snippet masquerading as a tested
example.

Checked functions have `# Errors`; unsafe functions have `# Safety`; panic
conditions are separate. The documentation-only union emits each callable once
without implying that every concrete profile implements every declaration.
Concrete availability and implementation state remain in the specialization
reference.

### Rust documentation verdict

Every actual generated example runs under the doctest gate, and every stable
declaration is represented through the stable reference boundary. No blocking
documentation finding remains.

## Initial finding resolution table

| Initial finding | Re-audit disposition |
| --- | --- |
| F-01 critical — C++ signed wrapping UB | Fixed with defined modular lowering and sanitizer/differential gates |
| F-02 high — GCC native headers fail `-Werror` | Fixed; all-profile ordinary-include quality target added |
| F-03 high — C++ reference omits stable types/algorithms | Fixed through typed stable documentation manifests and expanded Doxygen input |
| F-04 high — Rust docs claim Cargo profile features | Fixed; all user surfaces describe compile-target `cfg` selection |
| F-05 high — compatibility boundary undefined | Fixed by exact backend declaration/reachability manifests and stability classes |
| F-06 high — Cargo contents depend on docs history | Fixed by explicit package contents and before/after package-list gate |
| F-07 high — monolithic distribution size | Reduced to A-02: measured, disclosed, and assigned to Slice 13 archive design |
| F-08 medium — all Rust examples ignored | Fixed: two real doctests execute; signature fragments are non-example text |
| F-09 medium — missing Rust public docs | Fixed under `-D missing-docs` |
| F-10 medium — pointer results documented with extra indirection | Fixed by shared typed result projection |
| F-11 medium — incomplete/duplicated C++ overload docs | Fixed by exact callable documentation identities |
| F-12 medium — C++ algorithm preconditions unstated | Fixed by ordinary/checked algorithm contracts and reference coverage |

## Validation evidence

The four-way conclusion is supported by the maintained release gates, not only
manual inspection:

| Gate | Result |
| --- | --- |
| Exact public family and backend declaration baselines | 185 primitive families; 44 algorithms; 8,015 C++; 7,201 Rust |
| Full ordinary compiler suite after Slice 12 | 2,827 passed; 126 expected skips |
| C++ representative all-family quality matrix | 49 verifier commands passed |
| Rust 1.89 and current-stable release matrices | 93 commands per toolchain passed |
| Full Rust generated facade doctests before call-form correction | 2 executable examples passed; 3,524 non-executable fragments identified |
| Slice 12 full-corpus scalar C++/Rust quality and values | 21,802 specializations, 77 artifacts, 26 commands; 1,657 Rust values and two doctests passed |
| Slice 12 strict generated documentation | Doxygen, Rustdoc, specialization site, and Sphinx passed; documented C++ checked example compiled under `-Werror` |
| Exact SVE/RVV support | 9,239 applicable slots; 9,994 emitted outcomes; zero absent/deferred/pruned outcomes; 130 reviewed impossible combinations |
| Fixed-SVE integral-mask conversions | Predicate-aware extraction/insertion values passed under QEMU for SVE128, SVE256, and SVE512 |
| Scalable values | SVE and RVV passed under QEMU at three vector lengths; native attestations pending |
| External checked/unchecked consumers | C++ family matrix and Rust path/archive consumers passed |
| Strict generated references | Doxygen identity validation and Rustdoc warning/missing-doc/link gates passed |

Slice 12 additionally reruns the focused release-contract, Rust facade,
documentation, declaration-manifest, generated quality, doctest, C++ documented
example, corpus, type-checking, and full Python gates after the documentation
changes. The committed slice records the final command results in
[`todo/v1-0.md`](../todo/v1-0.md).

## Recommendation

Accept the four generated API/documentation surfaces for the v1 release
candidate. Do not cut the final tag until Slice 13 proves deterministic atomic
artifacts and Slice 14 supplies native SVE and RVV/CHORYS attestations. If those
hardware gates cannot be met, narrow the corresponding release status rather
than weakening the documented contract.
