# TSL v1.0.0 session recap

Date: 2026-09-10

Branch: `tsl-v1-release`

## Overview

This session moved TSL from an initial funding and product investigation to a
locally release-ready v1.0.0 candidate with an explicit checked-API contract,
complete declared C++ SVE/RVV coverage, a frozen stable Rust surface, exact
support evidence, editor support, deterministic release packaging, and
fail-closed acceptance gates.

The central result is not merely a collection of generated functions. The
compiler, source data, documentation, editor, verification tools, and release
workflow now share explicit ownership of the same product facts:

- `tsldata` owns primitive semantics, valid-call preconditions, and explicit
  caller-safety obligations;
- the typed `tslc` pipeline parses, selects, lowers, accounts for, and projects
  those facts;
- C++ and Rust backends format the already-decided API and safety contract;
- generated manifests, documentation, tests, the language server, and release
  evidence consume compiler-owned facts instead of reconstructing them;
- the VS Code client remains a thin presentation layer; and
- PIVOT remains a one-way downstream consumer and does not become compiler
  policy.

All locally implementable slices in
[`todo/v1-0.md`](todo/v1-0.md) are complete. The final `v1.0.0` tag is not yet
authorized or justified: native SVE evidence, native RVV evidence against the
actual CHORYS checkout, and the remote release-candidate run remain release
gates.

## 1. Funding research and proposal drafts

The session began by becoming familiar with the TSL source corpus and the
`tslc` compiler, then examining public DFG and EU funding routes for research
that extends the existing CHORYS work on RISC-V integration through TSL.

Separate proposal directories were created:

- [`research/proposals/dfg/`](research/proposals/dfg/README.md)
- [`research/proposals/eu/`](research/proposals/eu/README.md)

The DFG drafts cover:

- a kernel-evidence observatory through a KoFI-coordinated Research Grant and
  Research Software Infrastructures route;
- a high-risk, long-horizon one-bit database direction under the Koselleck
  programme; and
- a Research Grant proposal on vector-length-independent query execution.

The EU drafts cover:

- an EIC proof-of-market route for CHORYS-derived RVV readiness;
- an ERC proposal on the portability frontier;
- a Horizon Europe Cluster 4 data call;
- an MSCA Doctoral Network on vector-length-agnostic execution; and
- an MSCA Postdoctoral Fellowship on portable vector-length-independent
  execution.

Each proposal explains the tender fit, the research question, the relationship
to TSL and CHORYS, the expected foreground, and the double-funding boundary.
The shortlist files also record eligibility questions, deadlines known at the
time of research, and source links that must be revalidated before submission.

### Showcase experiments

Every proposal contains a concrete `Showcase experiment` section. These are
falsifiable microbenchmarks rather than generic dissemination demonstrations.
They specify:

- a real workload or kernel;
- scalar, compiler-autovectorized, hand-written ISA, and/or TSL variants;
- target machines and vector-length variants where relevant;
- correctness, throughput, latency, code-size, compilation, and portability
  measurements; and
- a decision rule that can show either that TSL provides leverage or that the
  proposed abstraction does not pay for itself.

The EU proposals explicitly build on the existing CHORYS/TSL/RISC-V baseline
while requiring new research results and experiments. They do not describe
the already-funded integration work as new foreground.

## 2. Generated API and documentation audit

The four requested product surfaces were audited in
[`research/tsl-v1-generated-api-docs-audit.md`](research/tsl-v1-generated-api-docs-audit.md):

1. generated C++ API quality;
2. generated Rust API quality;
3. generated C++ documentation quality; and
4. generated Rust documentation quality.

The audit identified the main pre-v1 risks: hidden safety behavior, incomplete
precondition ownership, language-inappropriate API projections, incomplete
scalable-target evidence, warning-sensitive generated headers, unstable Rust
surface assumptions, and documentation that could drift from the callable
surface.

The resulting work did not add a parallel documentation model. Exact public
declarations, implementation state, safety, checked companions, support status,
and editor facts are projections of typed compiler data. This gives generated
documentation and tools one source of truth.

## 3. Unchecked and checked API contract

The design and implementation record is in:

- [`research/tsl-v1-checked-api-refactor-plan.md`](research/tsl-v1-checked-api-refactor-plan.md)
- [`research/tsl-v1-checked-api-post-implementation-review.md`](research/tsl-v1-checked-api-post-implementation-review.md)
- [`research/tsl-v1-checked-api-release-evidence.md`](research/tsl-v1-checked-api-release-evidence.md)
- [`research/tsl-v1-checked-api-census.md`](research/tsl-v1-checked-api-census.md)

### Product rule

The unsuffixed operation is the direct expert path. It does not silently clamp,
sanitize, repair, substitute, or introduce a hidden validation branch.

A `*_checked` companion exists only when:

1. the normal operation has a dynamic caller-controlled precondition;
2. violating it can cause language undefined behavior, memory corruption, an
   invalid instruction, or a process-level fault, trap, or termination;
3. all evidence required to validate the condition can be represented by the
   checked signature;
4. every relevant TSL-owned precondition can be checked before an unsafe effect;
   and
5. forwarded caller obligations are completely discharged.

This intentionally excludes checked companions for already-total operations,
ordinary defined arithmetic outcomes, and hazards that cannot be checked
honestly. A partial guard must be reported as a checked-coverage gap rather
than exposed as a misleading safety promise.

### C++ API shape

For a value-producing primitive, the checked C++ API returns the ordinary
register type and writes the status through a final explicit reference:

```cpp
[[nodiscard]] TSL_FORCE_INLINE auto div_checked<Vec>(
    reg_param_t<Vec> dividend,
    reg_param_t<Vec> divisor,
    tsl::precondition_error& error
) noexcept -> typename Vec::register_type;
```

For a no-value primitive, the checked API returns `precondition_error` directly.
The API helps an expert write safe control flow but does not claim to force the
caller to inspect the error.

The proposed `checked_result<register_type>` aggregate was rejected. Local ABI
probes showed that such aggregates can require an indirect memory result for
SIMD register types in out-of-line calls. The selected form preserves the
ordinary vector return convention while reporting the small scalar error
separately. It does not promise that register pressure can never cause a spill;
it avoids an API design that forces one.

On failure, a value-producing checked wrapper returns a valid initialized but
semantically unspecified placeholder and reports the error. It never invokes
the unsafe operation. The placeholder is not a fallback result and tests do not
depend on its bits.

### Rust API shape

Rust uses its native safety vocabulary:

- total operations remain safe functions;
- an unchecked operation whose misuse can cause undefined behavior is emitted
  as `unsafe fn`; and
- a checked operation returns `Result<T, PreconditionError>` or
  `Result<(), PreconditionError>`.

The C++ expert convention therefore does not make the Rust API unsound. Both
languages implement the same semantic contract through language-appropriate
surface forms.

### Memory operations

Checked memory APIs use an extent-carrying view, span, slice, or equivalent
where the relevant range can be validated. Neither C++ nor TSL can prove that
an arbitrary pointer is live, correctly originated, race-free, or paired with
truthful external metadata. No checked API is generated if a TSL-owned hazard
cannot be fully checked from valid inputs to the richer signature.

### Where safety knowledge lives

Primitive preconditions and catastrophic consequences are typed source facts
in `tsldata`. Implementation metadata describes implementation effects and
explicit caller obligations. Selection and lowering account for those facts;
backends do not infer them from names, raw text, or pointer syntax.

This distinction was corrected late in the session. An implementation that
internally accesses raw memory is not automatically unsafe for its caller. For
example, an opaque pointer may be observed without dereferencing it. The
compiler no longer infers public caller unsafety merely from a pointer-shaped
signature. Existing public memory APIs remain unsafe where their source
implementations explicitly declare caller obligations.

That correction is covered by a synthetic opaque-pointer regression and by a
corpus audit. The current corpus contains 95 implementation entries that use
raw memory internally while retaining a caller-safe contract and 170 entries
that explicitly impose caller-unsafe memory obligations; the two concepts are
no longer conflated.

## 4. Editor and authoring support

The checked API could not be a generator-only feature. The compiler-owned
authoring/LSP services and the VS Code extension were updated so users can see
the new semantics while editing source data.

The compiler now supplies the editor with typed facts for:

- public preconditions and consequences;
- ordinary versus checked companions;
- C++ and Rust safety differences;
- callable identities after selection and dependency closure; and
- implementation-aware support state.

Hover, completion, diagnostics, explorer views, navigation, and related editor
features consume those facts. The TypeScript extension does not parse target
language bodies or independently decide which API is safe.

## 5. Scalable C++ SVE and RVV support

The v1 support claim was narrowed and made testable. “Full support” means full
coverage of the declared stable TSL callable/type/profile contract, not every
instruction or optional subextension in either ISA.

### Shape and profile semantics

The compiler now distinguishes runtime-scalable vectors from fixed-width
SVE128, SVE256, and SVE512 profiles. Runtime-scalable vectors do not fabricate a
compile-time lane count, hide an allocation, or reuse fixed-array APIs that
cannot honestly represent their shape.

Register multiplicity for conversion operations is typed. Fixed-width SVE
profiles are isolated from incompatible physical-extension dependencies, and
scalable operations use runtime lane queries where their semantics require
them.

### Exact target-support ratchet

Support is measured from selector-owned expected callable slots rather than
only from successful generation attempts. Every declared SVE/RVV slot is
classified as emitted or as an exact reviewed exclusion. Emitted results carry
an implementation state such as `native`, `composed`, `fallback`, or `unknown`.

The final release evidence records:

- 9,239 applicable exact SVE/RVV callable slots;
- 9,994 emitted realization outcomes;
- no absent, deferred, pruned, or unresolved stable slot; and
- 130 exact reviewed impossible combinations outside the stable callable
  universe.

Scalable SVE strict lowering covers 19,648 specializations, with 30 reviewed
fixed-shape exclusions. RVV covers 1,753 callable slots and 1,904 outcomes:
374 native, 944 composed, and 586 reviewed fallbacks, with no unknown state.

### Multi-vector-length verification

The same generated scalable binary is exercised at several runtime vector
lengths. QEMU verification covers 128-, 256-, and 512-bit vector lengths, and
the RVV generated value binary executes 4,448 cases at each configured VLEN.
Runner variants are typed profile-owned verification inputs rather than
workflow-only special cases.

QEMU establishes repeatable semantic coverage, not native performance or full
hardware confidence. The final release therefore still requires one native
SVE run and one native RVV run tied to the actual CHORYS consumer.

## 6. Generated C++ product quality

The stable C++ contract contains 29 release profiles, including the declared
SVE, fixed-width SVE, and RVV profiles.

The generated product was hardened as a normal consumer include rather than
relying on system-header treatment to suppress warnings. Release gates cover
supported GCC, Clang, cross-compilation, and WebAssembly paths, exact public
declaration manifests, executable value cases, documentation, compile time, and
artifact size. MSVC is not locally available on this Linux host, so its release
proof comes from the automatic Windows CI quality matrix; all three exhaustive
`/W4 /WX` shards now pass.

The first automatic branch runs exposed real portability defects rather than a
profile-selector regression. The fixes keep target selection profile-owned,
make compiler-dependent horizontal-reduction eligibility an explicit backend
capability, preserve external OneAPI headers as a typed system-header boundary,
and represent compile-known primitive branches with typed TSIL control. The
last warning slice also makes scalar/register overload conversion explicit at
the generated C++ implementation boundary without type-trait inspection of
intrinsic register types or forced register copies.

The next automatic MSVC run showed two remaining exhaustive-project issues.
Immediate-shift normal paths now live inside the `switch<compile>` fallback arm,
so C++ emits a complete `if constexpr`/`else` for those immediate-bound
decisions. The generated CMake project also applies `/bigobj` privately to its
exhaustive MSVC smoke and value targets; ordinary consumers and the public
generated interface do not inherit that verification-only flag.

The automatic run proved `/bigobj` fixed C1128, but its three MSVC warning
shards still found C4702. Although diagnostics pointed at transitive callers
such as `popcnt` and `permute_lanes_mask`, the repeated instantiations led back
to signed `shift_right` implementations whose return-producing
`if constexpr (PreserveSign)` branches were followed by unconditional code.
Those branches now have explicit typed compile-time alternatives across SSE,
AVX2, AVX-512, and RVV. Unsigned generation remains direct, the large logical
16-bit implementation is shared through the existing unsigned specialization,
and scalar cases with genuine runtime fallthrough remain open. The fix is
source semantics, not warning suppression or a compiler-specific backend rule.

Conversion-index diagnostics and exact all-profile declarations were made
typed and deterministic. Representative clean generated projects build in
ordinary consumer configurations.

## 7. Generated Rust product quality

The stable Rust surface is deliberately smaller than C++ and consists of six
release profiles. Stable Rust SVE/RVV are explicit exclusions rather than
partially working promises.

The release gates cover:

- Rust 1.89 as the stated minimum supported Rust version;
- the current stable toolchain;
- warning-free builds and Clippy;
- Rustdoc and doctests;
- generated value tests;
- package assembly; and
- clean external consumers of the packaged crate.

Exact Rust declarations and documentation come from the same backend-owned
public API records used by manifests and verification.

## 8. Implementation-aware portability contract

The proposal in [`todo/pre-v1-0-todo.md`](todo/pre-v1-0-todo.md) was assessed as
a sound product and research direction but too broad to make one v1.0 release
gate. It combines a richer implementation contract, schema changes, new public
APIs, analysis, editor UX, and research evaluation.

For v1.0, the repository freezes the coarse, useful foundation:

- exact callable identity;
- exact supported target/profile/type slots;
- direct versus dependency-closure views; and
- `native`, `composed`, `fallback`, or `unknown` realization state.

Richer hazard contracts, cost certificates, and implementation selection
policies remain incremental v1.x or research work. This avoids destabilizing
the v1 surface while retaining the key implementation-aware direction.

## 9. Documentation and release contract

The generated support facts, migration guidance, changelog, examples, API
manifests, and four-way API/documentation audit were reconciled. The generated
TSL library has the `1.0.0` product contract; `tslc` and the VS Code extension
retain independent package versions and compatibility policies.

Release production is owned by one atomic workflow. It:

- invokes the required component workflows;
- assembles deterministic archives;
- records exact manifests and checksums;
- verifies embedded package identities and clean consumers;
- refuses to replace an existing release asset;
- stages a draft before verification; and
- promotes only after every required gate succeeds.

Deployment packaging was changed from one impractically large generated tree
to one release asset containing a standalone project for each C++ release
profile and one combined Rust crate. The final local bundle contains 30 bundles
and is deterministic; its archive was 56,997,715 bytes in the recorded run.

Native acceptance evidence is fail-closed. Versioned JSON schemas and templates
bind an attestation to compiler inputs, the release bundle index, target
manifest, machine and toolchain identities, commands, value/differential
results, and the required showcase. RVV/CHORYS evidence must identify and run
the actual CHORYS repository revision; a generated approximation cannot satisfy
that gate.

## 10. PIVOT downstream evidence

PIVOT remained an independently packaged downstream tool. Its frozen v1
baseline was refreshed only after classifying every difference:

- 20 replacements were semantically equivalent scalar `custom_sequence`
  bodies in C++ and Rust after removal of an unused local;
- 54 C++ definitions were additive SVE division and fixed-wrapper exports;
- no other definition records disappeared; and
- collision groups and body-quality rules remained stable.

The updated deterministic baseline contains 17,134 definitions: 10,261 C++ and
6,873 Rust definitions. All 86 PIVOT tests pass. No PIVOT production behavior
was changed to accommodate the compiler.

The `3ae5e615` MSVC-warning slice refreshed this downstream evidence once more.
Definition counts, identities, direct hashes, collision multiplicities, and the
typed-body semantic digest remained exact. Only `interleave_lo` skip taxonomy
changed—from an unsupported render value to residual target statements after
generation-time parity branches became direct lane-pair assignments—and source
locations moved. The guarded updater's reviewed override was used only after
that comparison.

The exhaustive-MSVC follow-up moved source locations again while restructuring
immediate-shift control. PIVOT accepted that refresh without an override: all
17,134 definition records, direct hashes, collision multiplicities, skip counts,
and the typed-body semantic digest remained unchanged. Only source hashes and
locations changed.

Closing the remaining signed-shift compile-time branches moved those locations
once more. The guarded updater again accepted the refresh without an override;
the 17,134 definitions, semantic digest, skip counts, body-quality summary, and
collision inventory remain unchanged.

## 11. Local validation completed

The latest broad validation after closing the generated shift branches
produced:

| Gate | Result |
| --- | --- |
| Full ordinary `tslc` test suite | 2,921 passed, 129 expected skips |
| Python compilation | passed |
| `tslc` mypy | 367 source files passed |
| Corpus `check` | passed |
| Checked-API census | 156 runtime sites, 33 caller-unsafe paths, 138 explicit metadata gaps |
| Focused warning-clean C++/Rust build | 37,962 specializations, 92 artifacts, 36 commands passed |
| Focused generated C++/Rust values | 65 build/test commands passed |
| Focused RVV values | 2,244 specializations, 49 artifacts, 9 commands passed at VLEN 128/256/512 |
| Exact coverage ratchet | 174,602 emitted slot-variants; no changes or regressions |
| Exact SVE/RVV target ratchet | 9,239 applicable slots; no changes or regressions |
| C++ benchmark ratchet | 14,138 selected slots; evidence current |
| Rust benchmark ratchet | 4,938 selected slots; evidence current |
| PIVOT suite | 86 passed |
| PIVOT mypy | 17 source files passed |
| Whitespace/error-marker check | passed |

Earlier slice-specific gates additionally exercised full generated projects,
Rust package consumers, C++ warning matrices, SVE/RVV QEMU multi-vector-length
value suites, deterministic packaging, archive consumers, editor/LSP behavior,
and release evidence validation. Exact commands and results live in the linked
release evidence and post-implementation review documents.

## 12. Implemented slices and commits

The v1 branch contains the following reviewed slices after baseline
`dbac54a9`, in execution order:

| Commit | Change |
| --- | --- |
| `3d5848e8` | Restore main verification gates and guarded publication behavior |
| `228f8d23` | Audit the checked-API baseline |
| `ed3a7998` | Define wrapping arithmetic semantics |
| `9d6420f7` | Add the checked lane API pilot |
| `8e3553bd` | Add checked division and remainder APIs |
| `01900be5` | Add checked contiguous-memory APIs |
| `5920658a` | Add checked algorithm-range APIs |
| `2635348b` | Add checked irregular-memory APIs |
| `8ceb5c10` | Add the remaining checked memory APIs |
| `5079a6d9` | Complete checked-API release gates |
| `c1a6ba61` | Audit the checked design and release evidence |
| `8d06ba10` | Add explicit transitive call-precondition accounting |
| `1d86888b` | Add exact backend public API manifests |
| `7bb5046c` | Freeze the TSL v1 support contract |
| `c0442e88` | Reconcile the checked API with current main |
| `3b68f5f6` | Add the exact scalable-target ratchet |
| `83f0d800` | Define scalable vector shapes and register multiplicity |
| `eba59633` | Isolate fixed-width SVE profiles |
| `65f1e66c` | Complete scalable SVE semantic coverage |
| `f1c753ad` | Complete scalable RVV semantic coverage |
| `427ecdf4` | Add scalable multi-vector-length attestations |
| `1f7e096d` | Make generated C++ normal consumers warning-clean |
| `9f3b4f09` | Gate the stable Rust surface and quality |
| `6f8327d2` | Freeze implementation-awareness ownership and projection rules |
| `3025ea1f` | Reconcile the v1 product and documentation contract |
| `b66f0740` | Make release production atomic |
| `806b756a` | Add fail-closed v1 acceptance evidence |
| `ab8a7e32` | Package deployment-oriented v1 bundles |
| `e29eba22` | Keep pointer caller-safety contracts source-owned |
| `03fed88f` | Refresh reviewed PIVOT v1 export evidence |
| `396177b5` | Reconcile the release plan with completed local gates |
| `a06b496d` | Add the first complete session recap |
| `b2c3649d` | Fix generated C++ MSVC portability defects |
| `c66778ab` | Keep generated x86 activation profile-exact |
| `178d6ea5` | Test editor profile-activation semantics |
| `8ce798f7` | Model the OneAPI external system-header boundary |
| `7ced4216` | Exclude unsupported Rust SVE profiles from scheduling |
| `b12e65d8` | Refresh exact release and benchmark evidence |
| `0b25bda1` | Refresh PIVOT evidence after type canonicalization |
| `76b609f2` | Fix Clang uniform-shift result typing |
| `a33ee33a` | Make MSVC narrow-reduction selection capability-aware |
| `fe9c16db` | Stabilize initial LSP workspace indexing |
| `3ae5e615` | Eliminate the remaining generated MSVC warning sources |
| `cf1000b1` | Make exhaustive generated MSVC verification portable |
| `f358e5b4` | Close generated shift compile-time return branches |

Every implementation slice was followed by a focused design review, fixes for
identified boundary or maintainability problems, proportionate validation, and
a separate commit before moving to the next slice.

## 13. Remaining work before the final v1.0.0 tag

The following are external execution gates, not locally hidden TODOs:

1. Run the exact packaged SVE artifact on supported native SVE hardware and
   provide the schema-valid, traceable attestation.
2. Run the exact packaged RVV artifact on supported native RVV hardware.
3. Build and execute the declared showcase against the actual CHORYS repository
   and revision, then provide the combined RVV/CHORYS native attestation.
4. Run the non-publishing release-candidate workflow when explicitly authorized.
5. Review all remote and native evidence. Fix branch-owned failures through the
   same review/validation/commit loop.
6. Only after every required gate is green, authorize and create the final
   `v1.0.0` tag and allow the atomic workflow to publish it.

The automatic run for `fe9c16db` passed editor, Python, coverage, Clang, Rust,
benchmark, scalable-showcase, and generated build/value jobs. Its only failures
were three MSVC warning shards. `3ae5e615` removed their C4127/C4244 warnings;
its automatic run then reported only C4702 unreachable code and C1128 section
count exhaustion in those shards. `cf1000b1` fixed C1128, but automatic run
`34428614416` showed C4702 still originating in transitively instantiated
runtime/vector signed shifts. `f358e5b4` closes those branches. These historical
results are diagnosis evidence; all three automatic MSVC warning shards for the
current commit pass under `/W4 /WX`. Generated Build and Values passed all 49
jobs in run `34433042041`; Python Logic (`34433042052`), Coverage Ratchet
(`34433042044`), and TSL Editor (`34433042045`) also completed successfully.
Those workflows started automatically from the normal push; none was manually
dispatched or rerun.

If native evidence cannot be obtained, the affected scalable profile must be
marked experimental for the release. The evidence requirement must not be
silently waived.

## 14. Working-tree note

At the time this recap was written, `.gitignore`, `bench_sorting.log`, and
`xxx` were pre-existing user work outside these release slices. They were not
modified, staged, or committed by this work.

## 15. Navigation

The most useful handoff documents are:

- [`todo/v1-0.md`](todo/v1-0.md) — authoritative release progress and gates;
- [`research/tsl-v1-generated-api-docs-audit.md`](research/tsl-v1-generated-api-docs-audit.md) — four-surface quality audit;
- [`research/tsl-v1-checked-api-refactor-plan.md`](research/tsl-v1-checked-api-refactor-plan.md) — checked-API decision record and slice plan;
- [`research/tsl-v1-checked-api-post-implementation-review.md`](research/tsl-v1-checked-api-post-implementation-review.md) — architectural review;
- [`research/tsl-v1-checked-api-release-evidence.md`](research/tsl-v1-checked-api-release-evidence.md) — detailed verification evidence;
- [`research/proposals/dfg/`](research/proposals/dfg/README.md) — DFG opportunity shortlist and drafts; and
- [`research/proposals/eu/`](research/proposals/eu/README.md) — EU opportunity shortlist and drafts.
