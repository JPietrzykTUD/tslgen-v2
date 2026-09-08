# TSL v1 checked-API post-implementation design review

Date: 2026-09-08

Reviewed range: `08954770` through Slices 9 and 10 and their replay onto
`tsl-v1-release` after `3d5848e8`, including the integration review/fix loop.

Related documents:

- [original generated API/documentation audit](tsl-v1-generated-api-docs-audit.md)
- [checked-API refactor plan](tsl-v1-checked-api-refactor-plan.md)
- [checked-API census](tsl-v1-checked-api-census.md)
- [Slice 8 release evidence](tsl-v1-checked-api-release-evidence.md)

## Verdict

No blocking design defect remains in the checked-API refactor. Source data owns
public preconditions, the catalog validates and types them, lowering transports
them with explicit call-site dispositions, backends decide language-specific
APIs and exact declaration records, renderers format finalized facts, and the
editor consumes compiler projections. The two former high-severity proof gaps
are closed by Slices 9 and 10. The integration review also corrected the
ordinary/checked dependency-boundary defect described by C-10 and the
AVX-selection regression described by C-11. This verdict does not close the separate
full-header warning debt or unsupported-platform work from the broader v1 audit.

## Findings

### R-01 — High, fixed: transitive callee preconditions have typed dispositions

Before Slice 9, [`CallDependency`](../tslc/src/tslc/lower/dependencies.py#L38)
recorded the callee, mask policy, source vector, and optional target vector, but
not an applicable catastrophic callee condition, the caller condition that
forwarded it, or an implementation-author assertion that discharged it.

The old call lowerer recorded that edge and locally framed a caller-unsafe Rust
call in `unsafe` at
[`calls.py`](../tslc/src/tslc/lower/region_handlers/calls.py#L118). Dependency
closure then propagated an internal `unsafe_callee` reason, but deliberately
did not make every caller publicly unsafe, at
[`_pipeline_closure.py`](../tslc/src/tslc/_pipeline_closure.py#L480). That is the
right behavior for compiler-sized local arrays and sanitized operands, but the
compiler could not distinguish those sound abstractions from an accidentally
lost caller obligation.

The direct checked-memory admission guard was intentionally conservative in
[`checked_api.py`](../tslc/src/tslc/backend/checked_api.py#L468), but had admitted
the compiler-derived internal `unsafe_callee` framing label so existing sound
masked/composed wrappers would not be deleted. That label was not a transitive
proof.

Current-corpus call sites were reviewed and fall into matching root
preconditions, compile-time nonzero immediates, sanitized divisors, raw-pointer
roots that remain unsafe, or compiler-sized local/fixed arrays. No concrete
unsound public path was found. The remaining risk is architectural: a future
implementation can lose a callee obligation without a structured diagnostic or
checked-coverage failure.

Correction: Slice 9 added source-visible `forward[...]` and `discharge[...]`
call-site dispositions, exact operand-identity validation, typed dependency
origins, conservative unresolved-obligation closure, fail-closed checked
admission, authoring/LSP projections, and a deterministic zero-gap corpus
inventory. No proof is inferred from raw target text or a local unsafe frame.

### R-02 — High, fixed: compatibility reaches exact backend declarations

The v2 baseline correctly freezes source signatures, operand roles, memory and
arithmetic semantics, precondition descriptors, error spellings, algorithm
contracts, and stable root identities. It also says explicitly that selected
per-profile safety and exact emitted declarations are outside its identity level
in
[`public_api_baseline.py`](../tslc/src/tslc/maintenance/public_api_baseline.py#L298).

Consequently, before Slice 10 a renderer could change `noexcept`,
`[[nodiscard]]`, `unsafe`,
visibility, generic bounds, parameter/reference types, result form, overload
identity, or module reachability without necessarily changing the baseline.
The declaration snapshots are useful examples, not exhaustive compatibility
evidence. This falls short of the repository rule that public-output coverage
must ratchet exact identities and relevant content rather than aggregate counts.

Correction: Slice 10 added backend-owned frozen declaration records, render
holes driven from those records, exact ordinary/checked and definition/reexport
relationships, typed Rust selection reachability, deterministic per-project
manifests, and the schema-v3 scalar/AVX2 baseline. Every exported named surface
is stable, unstable, or implementation detail; stable overload sets are
rejected. Parity tests use record/hole inventories and generated manifest
equality without parsing or hashing target text. Its review/fix loop also caught
and corrected a missing stable `crate::profile::algo` module, incomplete C++
static-support classifications and reachability, and duplicate renderer-side
signature reconstruction.

### R-03 — Medium, open and outside this refactor: full C++ headers are not warning-clean

The checked API's native-mask classification warning was fixed, and its focused
GCC/Clang `-Werror` regression fixture passes. A full AVX2 umbrella-header probe
still reports unrelated existing warnings, including unused source operands,
always-false unsigned comparisons, and uninitialized placeholder variables in
other primitive implementations. The documentation example itself passes
`-Wall -Wextra -Werror` under GCC and Clang when the generated library is treated
as a system include, which is the same boundary used by the release evidence;
the umbrella implementation is not itself warning-clean as a normal `-I`
include.

This does not invalidate the checked-API ownership design and was already
excluded from its scope, but it remains product-quality work from the original
v1 audit. It must not be reported as fixed merely because external consumers
use `-isystem`.

## Corrected findings

### C-01 — Critical, fixed: indexed checks used the wrong lane domain

The first irregular-memory implementation assumed every indexed operation
consumed one index per result-vector lane. That is wrong for
`gather_narrow_partial`, which consumes only the supplied wider index-vector
lanes and zero-fills the rest of the result. A check using the result lane count
could inspect beyond the materialized index array before reaching the ordinary
operation.

The source contract now requires `memory.indexed_lanes`, with the closed
`vector` and `index_vector` meanings owned by
[`catalog/memory.py`](../tslc/src/tslc/catalog/memory.py#L39). Promotion requires
the field exactly for indexed memory and reports source-located errors in
[`memory_promotion.py`](../tslc/src/tslc/catalog/memory_promotion.py#L32).
Normal gather/scatter declarations select `vector`, while
[`gather_narrow_partial`](../tsldata/primitives/load_store/rnd_access.tsl#L627)
selects `index_vector`.

C++ and Rust checks now validate the appropriate lane-count relation before
materializing or indexing lane arrays. Focused consumers cover the valid partial
case, too-short and too-wide index vectors, negative indices, misalignment,
address overflow, masked inactive invalid indices, and scatter canaries.

### C-02 — Critical, fixed: compacted aligned memory omitted a condition

`compress_store` and `expand_load` originally carried only active-lane capacity.
An aligned specialization with at least one active lane could therefore receive
a misaligned range through its supposedly checked API.

Both source declarations now carry `compacted_memory_extent` and
`selected_memory_alignment`, for example
[`pack_expand.tsl`](../tsldata/primitives/load_store/pack_expand.tsl#L1). The
descriptor explicitly states that alignment applies only when the operation
accesses at least one element in
[`preconditions.py`](../tslc/src/tslc/catalog/preconditions.py#L227). C++ and
Rust guards skip alignment for an all-inactive mask and otherwise validate
vector alignment before dispatch. Tests exercise undersized, misaligned,
aligned, and empty/all-inactive ranges and verify output canaries.

### C-03 — High, fixed: a range signature could erase unrelated caller unsafety

The initial admission rule treated a complete memory-range check as sufficient
whenever a specialization was caller-unsafe. That could silently bless a new
authored reason unrelated to extent or alignment.

[`_caller_unsafety_is_range_only`](../tslc/src/tslc/backend/checked_api.py#L468)
now requires the exact discharged `raw_pointer` obligation and a closed set of
reviewed implementation-only labels. Unknown labels, `unchecked_index`, and
generic `unsafe_operation` reasons fail closed. Collision validation uses the
same applicable checked plan, so an inapplicable floating-point condition no
longer creates a false `*_checked` collision.

The remaining `unsafe_callee` caveat is R-01 rather than being concealed by this
direct guard.

### C-04 — High, fixed: Rust checked-facade logic crossed the render boundary

The comprehensive Rust renderer previously re-created a facade-specific checked
condition record, re-looked up descriptor prose, selected guards, chose slice
adaptation, and computed alignment. That duplicated backend semantics in a
formatting module and allowed compacted payload alignment to drift.

The duplicate record was removed. `RustComprehensiveMethod` now carries the
shared finalized `CheckedConditionPlan`; Rust translation lives in
[`backend/rust_facade_checked.py`](../tslc/src/tslc/backend/rust_facade_checked.py#L1);
and
[`render/rust_facade_comprehensive.py`](../tslc/src/tslc/render/rust_facade_comprehensive.py#L48)
formats those decisions. Scalar payloads use scalar alignment, vector and
active-lane payloads use the selected representation's vector alignment, and
all-inactive compacted calls skip the alignment test.

### C-05 — High, fixed: algorithm semantics depended on parameter names

Parts of checked algorithm generation inferred slice mutability, pointer
direction, range count, or selected-kernel shape from names such as `output`,
`indices`, and `masks`. A harmless source rename could therefore change
semantics.

[`AlgorithmRangeRole`](../tslc/src/tslc/backend/algorithm_contracts.py#L92) now
owns those meanings. C++ and Rust algorithm translation dispatch on the role;
names are used only for public spelling. Additive rename tests show that changed
names preserve check and forwarding behavior in both backends.

### C-10 — High, fixed: optional checked guards pruned ordinary callables

The initial integration put compiler-created checked-guard calls into the same
closure edge set as calls made by the ordinary implementation body. If a guard
helper was unavailable for a profile, closure consequently removed the
ordinary specialization even though its body did not call that helper. This
regressed ordinary SVE `scatter` and AVX/AVX-512 division/remainder coverage and
violated the central contract that checked companions are optional additions to
the direct API.

[`pipeline.py`](../tslc/src/tslc/pipeline.py) now discovers both edge kinds but
passes only implementation-body edges into pruning and transitive propagation.
After ordinary closure stabilizes,
[`_pipeline_closure.py`](../tslc/src/tslc/_pipeline_closure.py) records missing
checked-guard dependencies on the surviving lowered specialization, and
[`checked_api.py`](../tslc/src/tslc/backend/checked_api.py) suppresses only that
companion. `tslc explain` presents body and checked-guard callees separately.
Focused generation proves that SVE `scatter` remains callable while its
currently unrepresentable checked twin is absent; focused AVX2 C++ and Rust
generation proves that ordinary `mod`/`mod_imm` remain buildable.

### C-11 — High, fixed: an AVX fallback shadowed the native AVX2 compare

The first repair for the ordinary AVX division/remainder closure added a
composed integer `equal` body under the `avx2` source extension with more direct
required features than the native AVX2 body. The selector correctly treats more
requirements as more specialized, so that fallback won even on AVX2 and
replaced `_mm256_cmpeq_epi32` with two SSE-half calls.

The composed body now declares only its direct AVX requirement and appears
after the native body. The native body wins the existing earlier-source
tiebreak when both are usable; on an AVX-only profile it is rejected for its
missing AVX2 feature and the composed body remains available. Transitive
closure, rather than duplicated source requirements, carries the SSE callee
features. Existing intrinsic-selection tests and focused strict AVX/AVX2 checks
prove both outcomes.

### C-06 — Medium, fixed: checked planning retained partial or duplicated facts

The Rust facade used a second checked-condition dataclass with weaker invariants,
and documentation sometimes re-looked up prose from the global descriptor
registry after planning. The shared plan now owns finalized descriptions,
unchecked consequences, applicable type tags, error sets, operand positions,
mask/index/scale bindings, and complete memory facts in
[`checked_api.py`](../tslc/src/tslc/backend/checked_api.py#L52).

Cross-condition memory identity now includes every relevant binding, including
the compacted mask and indexed operands. Documentation consumes a small protocol
over the finalized facts and no longer reconstructs backend meaning. Tests reject
partial memory plans, duplicate errors, inconsistent condition domains, and
disagreeing shared memory bindings.

### C-07 — Medium, fixed: the public baseline overclaimed its coverage

The first baseline was largely a name inventory while its prose implied a
stronger compatibility guarantee. Version 2 now records typed source-family
semantics and states its exact limitation at
[`public_api_baseline.py`](../tslc/src/tslc/maintenance/public_api_baseline.py#L310).
The checked census likewise distinguishes exact typed caller-unsafe identities,
honest omissions, and lexical runtime-site evidence. It does not present text
scanning as compiler semantics.

### C-08 — Medium, fixed: editor projections could become stale or duplicate semantics

The Python authoring path now derives completion, hover, references, semantic
tokens, stage dumps, and explorer precondition names from the parser/schema and
typed catalog registries. When an overlay parses but fails semantic validation,
[`workspace.py`](../tslc/src/tslc/lsp/workspace.py#L220) rebuilds occurrence
locations against the last valid typed catalog rather than presenting stale
spans.

The TypeScript client receives and generically displays compiler-owned
precondition names; it contains no copied precondition vocabulary or availability
rules. `preconditions` remains source metadata and was not added to the generated
TSIL keyword grammar.

### C-09 — Low, fixed: native mask classification instantiated the wrong trait

The C++ algorithm helper classified masks with `std::is_integral` on intrinsic
vector types, which GCC diagnoses as ignored attributes. It now uses the
compiler-owned `Vec::mask_is_bitset` representation fact in
[`tsl_algorithm_detail_core.hpp`](../tslc/src/tslc/backend/assets/tsl_algorithm_detail_core.hpp#L230).
A native-mask code-generation fixture compiles the affected public header with
warnings as errors.

## Architecture boundary audit

| Layer | Final owner | Review result |
| --- | --- | --- |
| Source | `tsldata` declares catastrophic preconditions and the otherwise non-derivable indexed-lane extent | Correct; no backend spelling or check code in source metadata |
| Parse/catalog | parser nodes preserve syntax; frozen catalog enums/dataclasses validate roles, applicability, memory shape, and source locations | Correct; loose mappings stop at input/maintenance serialization boundaries |
| Lowering | `LoweredPrimitiveSemantics` transports typed catalog facts; dependency edges carry selected callee identities and explicit forwarded/discharged obligations; ordinary body edges are distinct from optional checked-guard edges | Correct after Slice 9 and integration fix C-10 |
| Backend-neutral policy | checked-condition and algorithm-contract records own eligibility and language-neutral relations | Correct; deterministic, typed, and independent of target text |
| C++ backend | owns span/error ABI, direct-result/error-output convention, constraints, guards, and C++ documentation facts | Correct for implemented families |
| Rust backend | owns `unsafe`/`Result`, slice adaptation, trait bounds, representation alignment, and facade admission | Correct after C-04 |
| Render | formats finalized backend/project records and declaration holes; emits per-project manifests from the same records | Correct after Slice 10 |
| Authoring/LSP | projects parser and catalog registries, including current source spans | Correct; no second semantic registry |
| VS Code | displays protocol facts and owns UI text only | Correct; no copied TSL semantics |
| Maintenance | serializes typed baselines and scans text only as explicitly labeled evidence | Correct; no maintenance result feeds compilation |

No compiler stage parses generated C++ or Rust to recover semantics. The only
target-text inspection added by this work is evidence gathering in maintenance
tests/reports, and it has no path back into selection, lowering, or generation.

## Slice-by-slice disposition

| Slice | Review disposition |
| --- | --- |
| 0 — census and policy | Corrected to separate typed identities from lexical evidence and to state exact omissions |
| 1 — wrapping arithmetic | Defined wrapping helpers remove signed C++ UB without adding validation to ordinary calls |
| 2 — lane access | Checked twins are restricted to runtime catastrophic indices; total/static forms remain unsuffixed only |
| 3 — division/remainder | Runtime integer zero is a precondition, floating zero remains valid, masked checks inspect active lanes, and inapplicable collisions are ignored |
| 4 — contiguous memory | Checked spans/slices validate exact typed extents and selected alignment; unknown safety reasons fail closed |
| 5 — algorithms | Typed range roles drive capacity/address/alias checks and raw forwarding; name coupling was removed |
| 6 — irregular/compacted memory | Indexed lane domains and compacted conditional alignment were corrected; pointer-index narrow gather remains an honest omission |
| 7 — remaining memory | Random output and widening-load twins are checkable; mask-layout, deallocation-provenance, and raw-copy gaps remain explicit rather than receiving dishonest twins |
| 8 — docs/editor/release evidence | Documentation, package reproducibility, editor projection, typed baseline, census, and showcase gates are present; Slices 9 and 10 close the two proof gaps identified by its first review |
| 9 — transitive preconditions | Exact forwarding and explicit author discharge are typed, source-visible, projected to authoring tools, and ratcheted with zero unresolved current-corpus obligations; checked-guard dependencies cannot prune the ordinary API |
| 10 — exact declarations | Backend-owned exact records drive stable declarations and deterministic manifests; non-stable surfaces are explicitly classified |

## Coverage and validation

The reviewed census is deterministic at:

- 185 typed primitive callable families;
- 33 exact source identities with at least one caller-unsafe implementation;
- 22 identities with an admitted checked source contract and 11 explicit
  no-honest-twin omissions;
- 154 lexical runtime-failure sites; and
- 138 safety-metadata suggestions, of which 26 require caller unsafety.

Completed validation on the corrected tree:

| Gate | Result |
| --- | --- |
| Python byte compilation | Passed |
| Mypy | Passed on the original reviewed tree: 355 source files |
| Full corpus `tslc check` | Passed: 43 source documents |
| Typed public baseline | Passed after integration: 185 primitive families; 813 exact C++ and 4,953 exact Rust declaration records |
| Checked census baseline | Passed: 154 runtime sites, 33 caller-unsafe identities, 138 metadata suggestions |
| Focused architecture/backend suite | Passed: 221; skipped: 18 |
| Checked generated/ABI suite | Passed: 59; skipped: 1 |
| Full generated C++/Rust build and value matrix | 83 generated build/value gates passed in one 51m44s run; the sole failure was a stale exact parity set for two new C++-only Clang cases, and that full-corpus parity gate passed after correction |
| Python LSP suite | Passed: 29 |
| VS Code unit and grammar suites | Passed: 23 + 2 |
| VS Code integration suite | Passed: 2 |
| Linux x64 bundled-runtime smoke/package verification | Passed: 192-file, 15.26 MB VSIX |
| Strict Doxygen, Rustdoc, Sphinx, and site build | Passed: 50,984 specializations and 93 artifacts |
| Rust doctests | Passed: 2 executed; 205 deliberately ignored comprehensive snippets |
| Checked C++ documentation example | Passed with GCC and Clang under strict consumer warnings, generated headers as system includes |
| Full ordinary Python suite | Passed after the integration fix loop: 2,759 passed, 124 expected skips |
| PIVOT downstream suite | Passed: 86; exact baseline contains 17,080 definitions and 35,849 skips |
| Integrated call-precondition audit | Passed: 132 dispositions (11 forward, 121 discharge), zero unresolved |

The generated full-matrix run covers all repository-supported build/value gates;
unavailable hardware and emulator paths remain gated rather than becoming hidden
host dependencies. MSVC and non-x86 hardware were not available on this host.

## Residual risks and next work

Release work, in order:

1. re-run the complete release matrix on each supported release platform,
   including native supported platforms and
   MSVC where available; and
2. address the broader full-corpus C++ warning debt before claiming normal
   include-path warning cleanliness.

Non-blocking implementation-quality observations remain:

- the Rust AVX2 showcase exposes an existing cross-crate inlining cost;
- C++ value-result failure requires a default/value-initializable placeholder,
  which is tested for current register/result types but not a universal future
  type guarantee;
- compacted aligned checks may scan the mask once for alignment and again for
  capacity;
- indexed wrappers currently map the authored index vector to the first and only
  free SIMD type parameter; the exact-one validation is safe, but a future
  multi-vector signature needs an explicit role-to-type-parameter binding;
- the C++ and lower-level Rust emitters remain large modules despite the focused
  checked-planning extractions; and
- the 49-minute full generated matrix is valuable release evidence but expensive
  enough that focused per-slice gates must remain the normal development path.

These observations do not justify hidden fallback behavior or weaker checks.
They are optimization/extensibility work after the two now-complete release
proofs above.
