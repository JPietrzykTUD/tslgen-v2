# `tslc` Performance Optimization Plan

## Status

Implemented on 2026-07-15. Slices 0 through 5 were accepted. Slice 5 was
initially deferred by the single-profile AVX2 profile, then accepted after the
true full request showed that repeated dependency fixpoints accounted for 31%
of profiled compiler work. The resource-failure condition for Slice 6 was not
met, so that architectural retention rewrite remains deferred.

## Execution Result

The final implementation keeps the original design boundaries and uses bounded
pure-text caches, generation-session-owned state, immutable catalog indexes,
and profile-local dependency indexes. It does not add Python threads, thread
pools, multiprocessing, or mechanical generator conversions.

- Slice 0 added the explicit snapshot capture/compare tool, canonical semantic
  manifests, sequential fresh-process benchmark driver, and an immutable
  original baseline for all five cases under
  `tslctmp/performance-optimize/baseline/`.
- Slice 1 changed parser and TSIL source-position lookup to binary search and
  retained exact offset-oracle coverage.
- Slice 2 added the 4,096-entry immutable TSIL scan cache. The final full
  request uses 1,916 entries.
- Slice 3 creates one dialect per requested backend and caches immutable
  lowering results by the complete selected-slot semantics within one
  generation session. The full request records 87,796 misses and 640,760 hits;
  the equivalent two-profile case records 28,638 misses and 28,638 hits.
- Slice 4 retained one additional optimization: a shared 512-entry pure query
  parse cache. The full request uses 275 entries and records 764,447 hits. The
  AVX2 prototype improved median runtime by 5.4%, clearing the acceptance gate.
- Slice 5 precomputes dependency identities and reverse edges, prunes missing
  dependencies in deterministic waves, and propagates safety, features, and
  implementation state with a changed-node worklist. It also stores the three
  unique signature-role kinds when the immutable catalog is validated instead
  of rediscovering them in specialization loops. Full-request wall time falls
  from 65.91 seconds to 50.20 seconds. Its peak RSS moves from 1.52 GiB to
  1.55 GiB, while the AVX2 and two-profile peaks both fall; the full high-water
  mark includes retained earlier profiles plus the active profile's dependency
  graph. The true full request still completes in one process, so Slice 6's
  two-phase retention redesign remains deferred.

Fresh-process final measurements on the audit host:

| Workload | Audited before | Final wall time | Final peak RSS |
|---|---:|---:|---:|
| Catalog-only check | 5.82 s | 2.04 s | 109 MiB |
| Focused AVX2 `add` closure | 7.98 s | 3.21 s | 139 MiB |
| Full-corpus AVX2 lowering | 20.03 s | 8.72 s | 408 MiB |
| `skylake,cascadelake` reuse | 36.78 s | 10.67 s | 451 MiB |
| Default full request | not previously practical as a benchmark | 50.20 s | 1.55 GiB |

Every final snapshot case (`focused`, `lowering-reuse`,
`all-profiles-shapes`, `profile-diverse`, and the true combined `full`
request) matches the original baseline exactly. The final ordinary Python suite
passes with 1,647 tests and 69 expected default skips. The representative
generated C++/Rust scalar+AVX2 matrix build passes all eight build commands.

The broader explicit generated gate finishes with 60 passes and four existing
full-corpus/allocation failures. Those failures are an unchanged generated ABI
issue: allocation functions are declared as `void**` / `*mut *mut c_void` but
their bodies return `void*` / `*mut c_void`. Exact final-to-original snapshots
prove the performance work did not introduce or alter that output; correcting
the pointer ABI belongs in a separate primitive/compiler slice.

This plan turns the July 2026 performance audit into small, correctness-first
compiler slices. Every optimization must preserve the current generated project
byte for byte and preserve structured diagnostics, coverage, skips, verification
plans, ordering, and source locations. Performance work must exploit the current
pure and immutable compiler boundaries; it must not fuse stages, bypass
validation, parse target-language text, or introduce nondeterministic parallel
execution. Python multithreading is prohibited throughout this optimization
project.

## Outcome

Reduce authoring and generation latency, make repeated work across concrete
slots and profiles reusable, and keep the default full generation matrix within
a practical resource envelope.

The intended first-order results are:

- catalog-only `tslc check` completes in about 2.5 seconds or less on the audit
  host, versus the measured 5.8 seconds;
- full-corpus AVX2 lowering for C++ and Rust completes in about 11 seconds or
  less, versus the measured 20 seconds;
- two profiles with the same selected lowering inputs reuse immutable lowering
  results rather than repeating every body translation;
- the ordinary generated artifacts and all non-artifact generation facts are
  exactly unchanged;
- the default all-profile request completes on the agreed verification host
  without exhausting memory.

Absolute timing thresholds are review evidence, not portable unit-test
assertions. Correctness tests should assert deterministic values and cache call
counts, never wall-clock time.

## Current Evidence

The audit measured the current dirty working tree with Python 3.14.4 on an
Intel Xeon w5-3425. The corpus contained 42 `.tsl` files totaling roughly
1.7 MiB, 28 machine profiles, and the C++ and Rust backends.

| In-memory workload | Wall time | Peak RSS / notes |
|---|---:|---:|
| Catalog-only full-corpus check | 5.82 s | parser and TSIL validation dominate |
| `add` plus dependency closure, AVX2, both backends | 7.98 s | 6,316 emitted slots |
| All primitives, AVX2, both backends, no rendering | 20.03 s | 420 MiB; 25,198 slots |
| All primitives, AVX2 and scalar, both backends | 29.00 s | 653 MiB; 43,496 slots |
| All primitives, AVX2, both backends, with rendering | 22.38 s | rendering is secondary |

The full 28-profile selection matrix contains 728,566 selected slots. Exact
selected-slot fingerprints collapse those profiles to 16 distinct selection
sets containing 381,226 unique slots, so 347,340 lowering attempts (47.7%) are
currently repeated across profiles.

The concentrated costs were:

- `syntax/parser.py::_line_column` linearly walks an already-computed line-start
  table for every source span;
- `ir/scan.py::_line_column` walks `text[:offset]` for every TSIL segment span;
- source validation scans 1,913 implementation bodies, after which generation
  scans the same selected body for every concrete slot;
- the focused `add` closure made 6,316 generation scan calls for only 161
  distinct `(body text, source span)` pairs;
- the lowerer receives complete typed selected facts but does not reuse an
  identical result in a later profile;
- backend dialects are recreated inside the concrete-slot loop;
- all emitted profiles and coverage entries remain live until project-wide
  validation, value-test planning, benchmark planning, and rendering finish.

Follow-up probes found several highly repeated but individually cheap helpers:

- one focused AVX2 generation made 48,745 query-parser calls for only 86
  distinct normalized query strings, but a bounded `lru_cache` prototype moved
  wall time only from 7.98 seconds to 7.86 seconds, which is within benchmark
  noise without repeated samples;
- the same workload called `split_arg_groups` 16,962 times for 333 distinct
  segment tuples, but an immutable cached representation plus a fresh public
  list moved wall time only from 7.98 seconds to 7.94 seconds;
- backend extension lookup repeatedly scans and sorts the immutable catalog,
  which is better addressed by a catalog- or dialect-owned index than by a
  process-global cache;
- the audit interpreter is a standard GIL-enabled Python 3.14.4 build, while
  source loading is only about 1.7 MiB across 42 files. The measured hot path is
  CPU-bound parsing and lowering rather than parallelizable file I/O.

## Design Constraints

- Keep the pipeline ordering and ownership documented in `tslc/AGENTS.md`.
- Keep parsing, catalog construction, selection, scanning, lowering, and
  rendering semantically pure.
- Cache only immutable values whose complete inputs form the key.
- Bound process-wide caches. Prefer generation-session ownership when a cache
  depends on catalog object identity.
- Keep source locations exact. A faster location lookup that changes a line,
  column, or end position is a correctness failure.
- Preserve deterministic ordering independently of cache hit order.
- Keep filesystem writes in the explicit snapshot maintenance tool and normal
  artifact writer.
- Do not change `profiles=None`, `primitives=None`, partial/strict behavior,
  coverage granularity, or public API result shapes as a performance shortcut.
- Do not add Python multithreading anywhere in the compiler, snapshot harness,
  or benchmark driver. This prohibition includes direct threads, thread pools,
  and helpers that dispatch work to threads. It is a project constraint, not a
  conditional optimization to revisit after profiling.
- Do not add multiprocessing unless a later profile proves a coarse isolated
  unit of work whose serialization, duplicated memory, deterministic merge,
  and process-start costs still produce a material end-to-end gain.
- Do not mechanically replace materialized deterministic collections with
  generators. Stream only across a boundary whose consumers no longer require
  the complete collection for sorting, validation, closure, planning, or
  rendering.
- Do not edit `tsldata/`, machine-profile data, render assets, or generated
  baselines as part of the optimization slices.

## Optimization Decision Ledger

### Additional Memoization And Indexing

The plan permits more memoization, but not a blanket application of
`@lru_cache`. Every cache must have a pure semantic key, an immutable stored
value, bounded process lifetime or generation-session ownership, focused
hit/miss tests, and a measured end-to-end benefit.

Promising conditional candidates after the primary scan and lowering work are:

- one shared pure `parse_query(text)` cache returning immutable query terms;
- bounded pure-text caches for call, cast, and intrinsic selector parsing;
- an internal immutable result for `split_arg_groups`, while preserving a fresh
  mutable list if that remains its public contract;
- precomputed signature-role lookup in the immutable signature-kind catalog;
- catalog-, session-, or dialect-owned extension/type indexes for repeated
  backend lookup.

Do not cache query evaluation: it depends on the active lowering session,
profile, type, bindings, and catalog. Do not use a process-global cache for a
catalog-dependent result merely because its arguments can be made hashable.
Prefer an owned index when immutable catalog construction already knows the
complete lookup relation.

The measured query and argument-group prototypes are evidence of reuse, not yet
evidence of a worthwhile optimization. They remain conditional until the
post-Slice-3 profile shows that their combined cost is material.

### Parallelism

Python multithreading is prohibited for this plan. The current hot stages are
CPU-bound pure Python under the GIL, so threads add scheduling and
synchronization without parallel execution. Threading source reads would not
help because the input corpus is small and I/O is not material. A future
free-threaded Python support decision would require a separate compiler-support
proposal and does not relax this plan's prohibition.

Multiprocessing is deferred, not treated as an expected slice. Per-profile or
per-file workers would duplicate or serialize large catalogs, lowered results,
coverage facts, and artifacts; this works against the memory goal and adds a
deterministic diagnostic/ordering merge. Reconsider it only after cache and
retention work, with a fresh-process benchmark that includes startup, IPC,
merge time, and aggregate RSS. Build-system parallelism for external CMake or
Cargo verification is controlled by those external tools and is not Python
multithreading inside `tslc`.

### Generators And Streaming

Mechanical `list` or `tuple` to `yield` conversions are rejected. Generators
can add per-item overhead and do not reduce peak memory when the next stage must
materialize the same values for deterministic ordering, duplicate detection,
dependency fixpoints, emitted-name finalization, cross-profile validation,
test/benchmark planning, or artifact sorting.

A generator-shaped change is acceptable only as the conditional full-matrix
retention slice: compile and finish one typed profile unit at a time, emit or
release facts that are genuinely profile-local, retain compact project-wide
facts, and then assemble dispatch, documentation, tests, benchmarks, and
verification metadata. That is a two-phase pipeline design requiring its own
review and full snapshot proof, not a local return-type refactor.

## Snapshot-First Correctness Gate

### Why Artifact Digests Alone Are Insufficient

`ArtifactSet.digest_manifest()` proves generated file contents and paths, but a
performance refactor can also accidentally change selection coverage, skips,
diagnostic locations, benchmark/value-test planning, or verification metadata.
The snapshot must therefore include both the written generated tree and a
canonical semantic manifest.

### Snapshot Tool

Add a focused explicit maintenance module:

```text
tslc/src/tslc/maintenance/generation_snapshot.py
```

It should expose `capture` and `compare` commands. This is a maintenance writer,
not a new compiler stage or general snapshot framework. It should call the
ordinary public generation API and the ordinary artifact writer.

Example use:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.generation_snapshot capture \
  --case full \
  --output tslctmp/performance-optimize/baseline/full

PYTHONPATH=tslc/src python -m tslc.maintenance.generation_snapshot capture \
  --case full \
  --output tslctmp/performance-optimize/candidate-slice-1/full

PYTHONPATH=tslc/src python -m tslc.maintenance.generation_snapshot compare \
  --baseline tslctmp/performance-optimize/baseline/full \
  --candidate tslctmp/performance-optimize/candidate-slice-1/full
```

The command must refuse to overwrite an existing snapshot unless an explicit
replacement option is supplied. Baseline replacement is never part of an
optimization slice.

### Canonical Snapshot Contents

Each case directory contains:

```text
case-name/
  snapshot.json
  generated/
    .tslc-manifest.json
    cpp/...
    rust/...
```

`snapshot.json` uses a versioned, sorted JSON representation with no timestamps,
elapsed times, hostnames, temporary paths, object IDs, or absolute repository
paths. It records:

- normalized generation request: primitives, profiles, types, backends,
  generation mode, harness/fuzz/warning flags, and rendering mode;
- repository-relative SHA-256 input manifest for all loaded `.tsl` files, the
  machine-profile file, grammar, and render assets;
- artifact logical path, SHA-256 digest, byte count, media type, and sorted
  metadata;
- structured diagnostics with severity, code, message, and repository-relative
  source location;
- every coverage entry, including source primitive, signature-kind facts, mask
  policy, axes, and variant names;
- every skipped entry, including status, reason, and its structured diagnostics;
- the rendered verification plan and the stable, semantically relevant
  value-test and benchmark plan facts not already represented by artifacts;
- counts for quick review, but never as a substitute for the full records.

Serializers should explicitly handle the frozen domain values. Do not use
`repr`, pickle, or a recursive "serialize anything" helper. Reuse
`ArtifactSet.digest_manifest()`, artifact metadata, diagnostic sorting, and the
coverage-ratchet slot vocabulary where their granularity is sufficient.

### Input Freeze

Capture the baseline from the exact source-data state on which implementation
will proceed. The current worktree already contains unrelated user changes, so
the snapshot tool must record input digests rather than assuming `HEAD` is the
input state.

Comparison must fail before comparing outputs if any `.tsl`, machine-profile,
grammar, or render-asset input digest differs. Compiler Python files are
expected to differ and are recorded only as review provenance, not as frozen
inputs. If a required source or asset change appears during this work, stop and
restart the baseline intentionally rather than accepting an output diff.

### Snapshot Matrix

All cases use partial generation, no external formatting, no compilation, no
runner, and no fuzzing unless a case explicitly says otherwise. Disabling
formatters keeps external tool versions out of the byte comparison.

| Case | Primitives | Profiles | Types | Backends | Purpose |
|---|---|---|---|---|---|
| `full` | all | all configured profiles | all default arithmetic types | C++, Rust | Authoritative combined-project output and full profile aggregation |
| `profile-diverse` | all | `scalar,avx2,sve128,wasm32-simd128` | all default arithmetic types | C++, Rust | Scalar, fixed-width, fixed-SVE, WebAssembly, and backend differences |
| `lowering-reuse` | all | `skylake,cascadelake` | all default arithmetic types | C++, Rust | Exact selected-slot reuse with distinct profile names/features/metadata |
| `all-profiles-shapes` | shape set below | all configured profiles | `si32,f32` | C++, Rust | All-profile dispatch and metadata without the full primitive matrix |
| `focused` | `add` | `avx2` | `si32` | C++ | Fast edit loop, dependency closure, and one concrete backend slot |

The `all-profiles-shapes` primitive set should cover ordinary arithmetic,
masked memory, representation changes, immediates, generic SIMD parameters,
reductions, and free functions. Start with:

```text
add, load, store, cast, gather, shift_left, equal, hadd,
to_integral, from_array, to_array, allocate, deallocate
```

Confirm every name against the current catalog when implementing the harness.
If a name is unavailable or policy-deferred for a case, replace it with the
closest current primitive of the same typed shape and document that choice in
the case definition.

### Baseline Capture Protocol

1. Run `tslc check` and stop if the frozen input corpus has errors.
2. Capture `focused`, `all-profiles-shapes`, `profile-diverse`, and
   `lowering-reuse` twice into separate directories.
3. Compare each first capture to its second capture. Any difference is a
   pre-existing nondeterminism blocker.
4. Capture `full` twice and compare the captures before changing compiler code.
5. If the current full request cannot complete on the available host, do not
   represent a union of per-profile trees as a full snapshot: aggregate
   dispatch, documentation, tests, benchmark plans, and build metadata would
   be missing. Record the resource failure and obtain the baseline on a host
   with enough memory. Smaller slices may be developed against subset
   snapshots, but the optimization project cannot be declared complete without
   the real full before/after comparison.
6. Mark the accepted baseline directory read-only by convention and never use
   it as an output root again.

### Comparison Protocol

For every candidate case:

1. verify exact normalized request equality;
2. verify frozen input-manifest equality;
3. compare the canonical semantic manifest record by record;
4. compare artifact path sets and digests;
5. compare every generated file byte for byte, including the writer manifest;
6. report added, removed, and changed logical paths and the first semantic
   record difference;
7. exit nonzero on any difference.

Optimization commits must not update the baseline to make a difference pass.
An intentional output change belongs in a separate vertical slice with a new
baseline and its own rationale.

## Benchmark Protocol

Keep performance measurements separate from semantic snapshots. Add a small
maintenance benchmark driver or a repository-local command script that invokes
the same typed cases but does not write generated trees. Record wall time,
process CPU time, peak RSS, coverage count, skipped count, artifact count, and
cache hit/miss counts where applicable.

- Use the same Python executable and host for before/after comparisons.
- Record Python version, CPU model, logical CPU count, and current input
  manifest digest.
- Use a fresh process for every measured sample.
- Run `check` and `focused` at least five times and report the median.
- Run AVX2 full-corpus generation at least three times and report the median.
- Run `lowering-reuse` at least twice when memory permits.
- A single `full` run is acceptable because of cost, but record peak RSS and
  treat it as directional rather than a stable microbenchmark.
- Do not include import time in API-stage measurements; report CLI cold-start
  separately if it is measured.
- Do not include formatting, artifact writing, compilation, or verification in
  compiler-stage timings.
- Retain cProfile output under `tslctmp/performance-optimize/profiles/`, not in
  source control.

Suggested acceptance targets on the audit host:

| Workload | Target |
|---|---:|
| Catalog-only check | median <= 2.5 s and at least 50% faster |
| Focused AVX2 `add` closure | median <= 4.0 s and at least 40% faster |
| Full-corpus AVX2 lowering | median <= 11.5 s; peak RSS <= 450 MiB |
| `skylake,cascadelake` lowering reuse | median <= 14 s; peak RSS <= 550 MiB |
| Default full request | completes on the verification host; no correctness diff |

If a target is missed, re-profile rather than stacking speculative
abstractions. A correctness-preserving improvement can still be accepted when
the profile explains the smaller gain and the code remains simpler than the
measured cost it removes.

## Implementation Slices

### Slice 0: Build And Prove The Snapshot Harness

Goal: establish immutable before-state evidence before optimizing compiler
logic.

Changes:

- add `tslc.maintenance.generation_snapshot` with typed case definitions,
  explicit serializers, capture, and compare;
- keep snapshot writes under caller-provided `tslctmp/...` roots;
- add focused tests for deterministic serialization, input mismatch,
  artifact-content mismatch, coverage mismatch, skip mismatch, diagnostic
  location mismatch, and verification-plan mismatch;
- capture and self-compare the complete baseline matrix.

Tests:

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_determinism.py \
  tslc/tests/test_coverage_ratchet.py \
  tslc/tests/test_generation_snapshot.py
```

Stop if any case is nondeterministic or if the full baseline cannot be obtained
on the designated verification host.

### Slice 1: Make Source Position Lookup Logarithmic

Goal: remove repeated linear prefix walks without changing any parsed or TSIL
source span.

Changes:

- replace `syntax/parser.py::_line_column`'s line-start loop with
  `bisect_right` over the existing tuple;
- compute one root-body line-start table in `ir/scan.py` and use binary search
  in `_span_for` rather than iterating `text[:offset]`;
- make `_skip_opaque` inspect the current and next character before calling
  comment/string scanners, avoiding two `startswith` calls at ordinary
  characters;
- keep scanner-recursion and malformed-region ownership unchanged.

Focused correctness tests:

- compare the new parser lookup against the old linear oracle at every offset
  in empty, one-line, multiline, trailing-newline, and Unicode samples;
- assert token, tree, header, inline-string, and multiline-string spans;
- retain and expand nested TSIL span tests across comments, strings, blocks,
  `else`, loops, and switch arms;
- assert malformed-region diagnostic locations exactly.

Snapshot gate:

- compare all five candidate cases to the original baseline;
- require the real `full` comparison before merging the slice.

Performance gate:

- catalog check should improve by at least 45%;
- no measured workload may regress by more than 5%.

### Slice 2: Reuse Immutable TSIL Scans

Goal: scan one `(body text, source span)` once per bounded cache lifetime rather
than once per concrete slot.

Changes:

- add a private bounded memoization layer for `ir.scan.scan` keyed by the exact
  body text and immutable `SourceSpan`;
- use a capacity near the measured corpus body count (start at 4,096) and
  justify it with cache-size and RSS measurements;
- keep malformed-region discovery and shell validation behavior unchanged;
- ensure default bodies, implementation variants, and auxiliary expressions
  use the same cached scanner entry point where their inputs are identical;
- do not move scanned segments into the catalog or change the documented scan
  stage merely to obtain reuse.

Focused correctness tests:

- identical text and source return equal immutable segment trees;
- identical text at different source spans does not share incorrect locations;
- different body text at the same span cannot collide;
- nested region and variant source spans remain exact;
- bounded eviction does not change results;
- a counting test proves repeated calls invoke the underlying scanner once,
  without timing assertions.

Snapshot gate:

- compare all cases to the original pre-optimization baseline, not to Slice 1;
- pay particular attention to `profile-diverse`, which exercises different
  generation-time branches over shared source bodies.

Performance gate:

- full-corpus AVX2 lowering should improve by at least 15% relative to Slice 1;
- peak RSS may increase by no more than 10 MiB for the AVX2 case;
- report cache hits, misses, capacity, and current size.

### Slice 3: Reuse Dialects And Identical Lowering Results Across Profiles

Goal: lower an exact selected slot once per generation session and share the
frozen result across profiles.

Changes:

- construct one backend dialect per requested backend after catalog loading,
  not inside the concrete selected-slot loop;
- add a frozen private `_LoweringCacheKey` representing every lowering input;
- use a session-owned identity table to assign deterministic local identities
  to the exact frozen `Primitive`, `Implementation`, and `Extension` instances;
  never serialize object IDs or let them influence output ordering;
- include backend, selected primitive and implementation identities, extension,
  type, required features, concrete target, concrete lanes, SIMD-type base
  bindings, and fixed fallback extension in the key;
- cache the complete immutable `LoweringResult` before profile-specific
  coverage/skip recording;
- keep profile names, original feature sets, compile modes, flags, runner
  metadata, and profile-family metadata outside the lowering cache;
- allow dependency propagation to replace a profile-local `_LoweredSlot.spec`
  without mutating the cached specialization.

Do not key only by body text. The same body can lower differently for backend,
extension, type, target, attributes, lanes, generic bindings, or fixed fallback.

Focused correctness tests:

- exact repeated selected slots hit once and return the same immutable result;
- changing each key axis individually forces a miss;
- C++ and Rust never share a lowering result;
- a skip/error result is reusable while its profile-specific `SkippedEntry`
  remains correctly scoped;
- `skylake` and `cascadelake` retain distinct generated metadata even when all
  selected lowerings hit the cache;
- dependency propagation in one profile cannot mutate another profile's cached
  base specialization;
- artifact and diagnostic ordering is independent of hit/miss order.

Snapshot gate:

- `lowering-reuse` is the primary focused gate;
- compare `all-profiles-shapes`, `profile-diverse`, and `full` to the original
  baseline as mandatory gates;
- compare both backend-specific generated subtrees, not only the top-level
  artifact manifest.

Performance gate:

- the second same-selection profile should produce lowering-cache hits for
  essentially every selected slot;
- `lowering-reuse` should improve wall time and peak RSS by at least 25%;
- AVX2 single-profile performance must not regress by more than 5%.

### Slice 4: Re-profile Before Adding Micro-Caches Or Lookup Indexes

Goal: accept only small memoization and indexing changes that remain material
after scan and lowering reuse have removed the dominant repeated work.

Capture a new cProfile report plus cache/call-count instrumentation after Slice
3. Examine query parsing, selector parsing, `split_arg_groups`, signature-role
lookup, extension-by-ISA lookup, and backend type lookup. Continue only when the
candidate or a coherent group of candidates accounts for at least 5% of the
target workload, or an isolated prototype demonstrates a repeatable end-to-end
improvement of at least 3% across the required fresh-process sample count.

If justified, apply the smallest ownership-correct change:

- make pure query parsing a module-level bounded cache shared across region
  handlers, rather than duplicating a cache on each parser instance;
- cache selector parsing only by complete source text and only when the result
  is immutable;
- cache an immutable tuple form of argument groups and preserve a fresh list at
  any mutable API boundary;
- build catalog-dependent indexes in the catalog, generation session, or
  backend dialect that owns their inputs rather than using global memoization;
- expose cache counters only through benchmark instrumentation, not public
  generation results.

Focused tests must prove key separation, bounded eviction, immutability, and
unchanged context-dependent evaluation. In particular, evaluate the same
parsed query under different types, profiles, and bindings and prove the parse
tree may be shared while the evaluated result is not.

Run every snapshot case for an accepted change. Remove the cache or index if it
does not retain the measured gain after integration, or if it requires a new
general cache abstraction. It is acceptable—and currently expected—for this
slice to produce no code change.

### Slice 5: Re-profile Dependency Closure Before Changing It

Goal: decide whether call-fact propagation remains material after reuse is in
place.

The initial full-corpus AVX2 profile attributed 7.4% to this stage, so the slice
was correctly deferred for that workload. A later profile of the true combined
full request attributed 48.1 of 153.3 profiled compiler seconds (31%) to
`_prune_unresolved`, including 42.2 seconds in
`_propagate_transitive_call_facts`. That full-request evidence cleared the
threshold and activated this slice.

Implemented changes:

- precompute deterministic dependency edges and reverse caller edges once;
- propagate safety, required features, and implementation state through a
  changed-node worklist rather than sorting and scanning every slot on every
  fixpoint pass;
- preserve the current policy-aware slot and call-fact identities;
- retain explicit support for multiple lowered bodies behind one dependency
  key;
- do not assume the graph is acyclic merely because source authoring rules
  prohibit cycles; retain a safe fixpoint behavior and deterministic order.

Tests should cover chains, diamonds, multiple variants, unsafe propagation,
feature unions, state joins, unresolved pruning cascades, and a defensive cycle.
Run every snapshot case if this conditional slice is implemented.

### Slice 6: Make Full-Matrix Retention Practical If Caching Is Insufficient

Goal: close the default all-profile memory risk without changing public
generation semantics.

This is a separate architectural slice and is required only if the real `full`
candidate still cannot complete within the agreed memory budget after the
cache and indexing decisions through Slice 4. Do not begin it based only on
extrapolation.

Preferred investigation order:

1. Measure which retained values dominate RSS: lowered specializations,
   profile-local replacements, emitted-name finalization, coverage entries,
   value-test plans, benchmark plans, or artifact contents.
2. Check how much immutable specialization sharing survives dependency-fact
   propagation and `EmittedProfile` finalization.
3. Introduce a typed profile-compilation core only if multiple profiles have an
   identical complete selected/dependency graph. The core may own shared
   finalized specializations and selected extensions; each `EmittedProfile`
   must still own its distinct machine-profile metadata.
4. If unique profiles still dominate, evaluate incremental per-profile
   planning/rendering while retaining the project-wide facts required for
   dispatch, documentation, value tests, benchmarks, and verification.

Do not replace the true full request with a union of independently generated
profiles, do not drop coverage entries, and do not change the default request
to a smaller matrix. Those would change observable behavior rather than
optimize it.

This slice needs a short design review before implementation because it crosses
selection/lowering retention, backend validation, planning, and rendering.

## Validation Matrix

After every completed slice:

```bash
python -m compileall -q tslc/src/tslc

PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_parse_arithmetic.py \
  tslc/tests/test_tsil_scan.py \
  tslc/tests/test_catalog_validation.py \
  tslc/tests/test_select_and_lower*.py \
  tslc/tests/test_determinism.py \
  tslc/tests/test_generation_snapshot.py

PYTHONPATH=tslc/src python -m tslc check

(cd tslc && python -m mypy)

git diff --check
```

After Slices 2 and 3, and after any accepted micro-cache, closure, or retention
change, run the full Python suite:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
```

At the final gate, write and build a small generated matrix so exact snapshots
are backed by real toolchain evidence:

```bash
./dev.sh build \
  --primitives add,load,store,cast,gather,shift_left \
  --profiles scalar,avx2 \
  --backends cpp,rust

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  tslc/tests/test_value_tests.py
```

Report missing compilers, runners, or unsupported generated cases as explicit
verification gaps. Do not treat a skip as a pass.

## Expected File Ownership

Likely touched files by slice:

- snapshot harness: `tslc/src/tslc/maintenance/generation_snapshot.py` and
  `tslc/tests/test_generation_snapshot.py`;
- parser lookup: `tslc/src/tslc/syntax/parser.py` and parser/span tests;
- scanner lookup/cache: `tslc/src/tslc/ir/scan.py`, possibly a small private
  source-map helper, and TSIL scan tests;
- lowering reuse: `tslc/src/tslc/pipeline.py`, selected-slot identity support
  only if needed in `tslc/src/tslc/select/selector.py`, and focused pipeline
  tests;
- micro-caches/indexes, conditionally: `tslc/src/tslc/lower/_query_model.py`,
  the owning selector modules, `tslc/src/tslc/ir/region_syntax.py`, or the
  catalog/backend owner of a measured lookup, plus focused cache-context tests;
- dependency worklist, conditionally: `tslc/src/tslc/_pipeline_closure.py` and
  closure/safety tests;
- full-matrix retention, conditionally: pipeline, emitted-profile, planning,
  and render ownership determined by the memory profile.

Do not update charters or architecture documentation for private lookup and
memoization changes. Update `tslc/DESCRIPTION.md` only if Slice 6 changes the
observable pipeline orchestration or introduces a new substantive retained
profile-compilation value.

## Risks And Stop Conditions

- **Stale cache entries:** process-wide scanner caching must be keyed by text
  and source span and bounded. Catalog-dependent lowering caching must remain
  generation-session-local.
- **Context leakage:** parsed query/selector syntax may be shared, but query
  evaluation and catalog-dependent lookup results must remain scoped to their
  complete session inputs.
- **Mutable cached values:** never return a shared mutable list or dictionary
  from a cache; store immutable values and copy only at an existing mutable
  boundary.
- **Parallel memory amplification:** report aggregate worker RSS, not only the
  parent process, if multiprocessing is ever reconsidered.
- **Fake streaming:** do not count a generator as a memory improvement when a
  downstream stage immediately materializes it or when it weakens deterministic
  ordering and validation.
- **Incomplete lowering key:** a missing target, binding, lane, backend, or
  fallback field can silently reuse wrong target text. Key-axis tests and
  snapshot diversity are mandatory.
- **Profile metadata leakage:** identical selected bodies do not make machine
  profiles identical. Cache lowered semantics only.
- **Source-location drift:** binary-search edge behavior at newline and EOF
  offsets must match the current linear implementation exactly.
- **Hidden nondeterminism:** compare two baseline captures before attributing a
  later difference to optimization work.
- **Input movement:** fail snapshot comparison when source/profile/asset hashes
  differ; do not normalize away a real input change.
- **Full baseline resource failure:** do not call per-profile output a full
  snapshot. Obtain a real combined baseline elsewhere or report the project
  blocked at the full correctness gate.
- **Broad rewrite:** stop if a lookup/cache slice starts changing public result
  types, stage ownership, or rendering semantics.
- **Unproven optimization:** remove or simplify a cache/abstraction that does
  not produce a material measured improvement after the preceding slices.

## Completion Criteria

The performance project is complete when:

- every baseline snapshot case, including the true full combined request,
  compares exactly against the final candidate;
- focused and full test suites pass, mypy passes, and `git diff --check` is
  clean;
- the selected generated build/value gates pass or their toolchain gaps are
  explicitly reported;
- before/after benchmark results and peak RSS are recorded for all audit
  workloads;
- the default full request completes on the designated verification host;
- caches are bounded or session-owned, their keys cover all semantic inputs,
  and tests prove both hit reuse and miss separation;
- no Python multithreading was introduced; multiprocessing and streaming remain
  excluded unless their separate conditional evidence gates are met, and
  mechanical generator conversions are not counted as completed optimization
  work;
- no source data, machine profiles, render assets, or committed coverage
  baselines changed as part of the optimization;
- the final review packet lists each slice, snapshot comparisons, tests,
  performance results, memory results, and any intentionally deferred
  full-matrix retention work.
