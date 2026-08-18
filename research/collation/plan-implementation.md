# Implementation plan: semantic-key compilation

## Status and decision

This document plans a prototype for the research question defined in
[`README.md`](README.md) and the design in
[`technical-proposal.md`](technical-proposal.md). It creates no implementation
code.

If the first research gates pass, source code should live under:

```text
research/collation-src/
```

Generated TSL projects, third-party build trees, benchmark output, profiles,
corpora that cannot be committed, and all other runtime artifacts should live
under:

```text
tslctmp/collation/
```

The proposal documents remain under `research/collation/`. The prototype is a
downstream TSL consumer. It is not a `tslc` stage, backend, command, or semantic
projection, and it does not authorize changes to `tslc` or `tsldata`.

## Goal

Implement the smallest exact system that can establish or falsify this claim:

> Across independent columnar UTF-8 strings, a dynamically lane-refilled SIMD
> transducer can generate conservative collation-key products faster than ICU,
> reuse those products at Arrow/Parquet boundaries, and improve real collated
> relational operators without changing semantics or forking the algorithm per
> ISA.

The plan intentionally spends little engineering effort before the central
premises are tested. A complete Unicode implementation, broad database fork,
Parquet reader, GPU backend, or FPGA design must not be started speculatively.

## Decision discipline

### Gate outcomes

Every gate ends in one of four recorded outcomes:

- **continue:** the preregistered condition passed;
- **narrow:** a secondary claim failed but a smaller explicit question remains;
- **stop:** the central paper premise failed;
- **repeat once:** an identified implementation or measurement defect invalidated
  the run; fix it and rerun the same frozen condition.

Thresholds, primary corpora, workloads, and machine roles must be frozen before
the first performance run that can answer the corresponding hypothesis. A
threshold may be changed only by declaring the old gate failed and starting a
new, visibly exploratory study.

### Breakthrough and stop gates

These are deliberately early. `G0` through `G3` should be answerable before a
database-engine patch or complete Parquet integration exists.

| Gate | Earliest question | Evidence required to continue | Failure action |
| --- | --- | --- | --- |
| **G0: claim survives** | Is the mechanism actually unoccupied? | A claim matrix covering papers, theses, patents, and named production engines finds no equivalent system that combines exact cross-string SIMD collation, dynamic lane refill, and relational/format placement. The remaining claim is reviewed by someone other than its implementer. | Stop the headline claim. Narrow only if a concrete non-overlapping mechanism remains. |
| **G1: database wall exists** | Is exact collation important enough? | On preregistered real engine queries, collation/key construction consumes at least 25% of single-thread CPU in at least two operator families, and the binary-collation control or Amdahl calculation leaves room for a 15% end-to-end improvement. | Stop the database paper. Retain only a library experiment if independently worthwhile. |
| **G2: exact fast domain exists** | Can a conservative table/transducer cover real non-ASCII text? | For one pinned tertiary-strength configuration, the scalar candidate plus ICU fallback has zero mismatches on in-scope conformance cases and at least one million generated/adversarial comparisons; at least 80% of rows in one preregistered non-ASCII corpus complete in the candidate domain. | Stop if exactness is unclear. Reframe as a narrow Latin engineering path if coverage is only ASCII/simple Latin; do not claim multilingual research. |
| **G3: SIMD breakthrough exists** | Does the proposed execution structure beat strong baselines? | On the primary pilot corpus, one TSL SIMD realization is at least 1.8x faster than correctly buffered ICU key generation and at least 1.5x faster than the scalar implementation of the same transducer, including fallback and output cost. Lane refill has an explainable benefit under realistic length skew or is explicitly removed from the claim. | Stop before Arrow/Parquet or engine integration if neither SIMD nor the state organization pays. |
| **G4: multilingual coverage survives** | Is the result broader than one friendly locale? | Zero mismatches and useful fast-path coverage on at least three preregistered language/script families, including non-Latin data and hard cases; per-corpus kernel performance still meets H1's threshold. | Stop the broad paper or state a much narrower domain. An ASCII-only result is not sufficient. |
| **G5: one operator wins** | Does the kernel survive database overheads? | The first operator selected by `G1` improves preregistered end-to-end latency by at least 15%, with peak memory no more than the frozen acceptable budget and no correctness differences. | Stop broad integration. Diagnose the erased gain; continue only if one bounded fix can test a clear cause. |
| **G6: format placement matters** | Do Arrow/Parquet boundaries create a research choice? | Transient, dictionary, full-key, and direct-ICU candidates have at least two repeatable winning regions, and a simple held-out policy reduces regret relative to every fixed policy. | Remove the placement-policy/Parquet claim. This does not kill a successful kernel/operator paper. |
| **G7: algorithm transfers** | Is TSL demonstrating semantic portability rather than source reuse? | A second materially different vector family uses the same state machine/table/key contract, passes identical tests, and beats its scalar same-algorithm baseline. A scalable-vector claim additionally requires real SVE or RVV hardware. | Narrow the portability claim to the verified targets; if an algorithm fork is required, report it and do not call the approach architecture-neutral. |
| **G8: paper threshold** | Is there an outstanding systems result? | H1 holds across three families, two distinct operators meet H2, the placement result either meets H3 or is removed, H4 is scoped to real verified machines, and the prior-art ledger remains clear. | Publish a narrower or negative result only if it explains a general boundary; otherwise stop. |

The initial two-week-sized pilot should target `G0`–`G3`, not a full DBMS
integration. `G5` is the first large-investment gate.

## Proposed source layout

Create this only after `G0` and `G1` pass:

```text
research/collation-src/
  README.md                    # local contract, commands, supported semantics
  CMakeLists.txt
  cmake/
  include/collation/
    identity.hpp
    arrow_view.hpp
    semantic_product.hpp
    scalar_transducer.hpp
    simd_transducer.hpp
    operator_contract.hpp
  src/
    identity.cpp
    table_loader.cpp
    scalar_transducer.cpp
    simd_transducer.cpp
    icu_reference.cpp
    arrow_adapter.cpp
    dictionary_adapter.cpp
  tablegen/
    README.md
    ...                         # reproducible Unicode/CLDR table generation
  tests/
    unit/
    differential/
    conformance/
    operator/
  benchmarks/
    kernel/
    operator/
    scenarios/
  integration/
    duckdb/                     # isolated pinned patch/extension if needed
    parquet/
  tools/
    fetch_explicit.sh           # optional, user-invoked and version-pinned
    run_matrix.py
    summarize.py
  manifests/
    dependencies.lock
    corpora.toml
    experiments.toml
```

Do not commit downloaded corpora or build products by default. Commit license
and checksum manifests, small legally distributable edge fixtures, scenario
definitions, and code needed to reproduce derived data.

## Milestone 0: freeze the claim and experiment contract

### 0.1 Build a closest-prior-art ledger

Record for every candidate source:

- bibliographic identity and date;
- exact mechanism and semantic scope;
- whether it is a paper, patent, production source, issue, or proposal;
- fixed versus scalable SIMD behavior;
- correctness/fallback model;
- database and format integration;
- overlap with each proposed contribution;
- evidence excerpt or source location;
- conclusion: collision, adjacent, or irrelevant.

Search at least ACM, IEEE, DBLP, Google Scholar or an equivalent scholarly
index, dissertation catalogs, Google Patents/Espacenet, and public source/docs
for ICU, Arrow, DataFusion, DuckDB, Velox, ClickHouse, PostgreSQL,
MySQL/MariaDB, and any accessible SQL Server description. Include non-database
Unicode libraries and SIMD string-processing work. Use citation chaining from
the closest papers.

### 0.2 Write a one-page claim matrix

Rows are the four proposed contributions; columns are closest sources. State
the exact delta without words such as “first” or “novel.” Ask an independent
database or text-processing researcher to challenge the matrix.

### 0.3 Freeze semantic scope

Choose and record:

- ICU and Unicode/CLDR versions;
- primary locale/tailoring and strength;
- normalization, case, numeric, alternate, and reorder settings;
- invalid UTF-8 behavior;
- null and tie-breaking behavior;
- ordering-prefix length(s) and fingerprint algorithm;
- pilot corpora and their licenses/checksums;
- primary machine/compiler and secondary-machine roles.

### 0.4 Inventory TSL capability

For the intended C++ profile and types, use public `tslc`/`dev.sh` commands to
inspect and then build the minimal candidate roots. The initial list should
cover loads, masks, comparisons, shifts, gather/masked gather,
compress/expand or compress-store/expand-load, mask population count, and safe
tail stores.

Record emitted, built, value-tested, implementation-state, and skipped status
separately. Do not patch a missing primitive in this milestone.

### Deliverables and validation

- `research/collation-src/` is **not** yet required.
- A prior-art ledger, reviewed claim matrix, semantic manifest, and TSL
  capability record exist in a workspace-local research log.
- Every source link resolves and every proposed claim has a named closest work.
- `G0` has a recorded outcome.

If `G0` fails, stop here.

## Milestone 1: establish database headroom

### 1.1 Pin production baselines

Build or obtain one pinned DuckDB revision with its ICU extension and one pinned
ICU4C. Record compiler, optimization flags, linkage, CPU affinity, and collator
configuration. Use binary collation only as an upper-bound/control, never as a
semantic baseline.

### 1.2 Construct minimal real queries

For a column of multilingual strings, measure:

- `ORDER BY` with sufficient rows to exercise key generation and comparison;
- `GROUP BY` or `DISTINCT` with controlled cardinality;
- one equality/range predicate with a collated constant; and
- one equijoin if the engine actually applies the intended collation semantics.

Confirm the engine's semantics before timing. If an operator silently falls
back to binary comparison or does not support collation, it cannot be used as
evidence.

### 1.3 Attribute CPU cost

Use engine profiling plus a sampling profiler or hardware counter tool to
separate:

- UTF decoding/normalization and collation-element lookup;
- sort-key generation;
- comparison;
- hashing;
- allocation and key copying;
- the rest of the operator.

Measure direct ICU compare and correctly buffered ICU sort-key generation in a
standalone harness on the same strings. Avoid the known anti-pattern of calling
the key function twice merely to size and then fill every key.

### 1.4 Decide the first operator

Select the operator with the largest repeatable improvable collation fraction,
not the most convenient integration. Freeze its primary scenario before
candidate measurements.

### Deliverables and gate

- A provenance-rich baseline record and flame/profile evidence.
- An Amdahl-style maximum-improvement calculation per operator.
- A selected first operator and its frozen scenario.
- A recorded `G1` result.

If `G1` fails, do not build the transducer as a database project.

## Milestone 2: build the exact scalar semantic path

### 2.1 Implement immutable identities and products

Implement `CollationIdentity`, stable serialization/digesting, prefix metadata,
fingerprint metadata, full-key ownership, and explicit row statuses. Unit-test
identity mismatch, option changes, and key-format changes before optimization.

### 2.2 Wrap the ICU oracle

Expose reference compare, equality, complete sort key, and streaming/partial key
operations behind one small module. It owns buffer sizing and reports ICU
errors. Candidate code may not call ICU except through this wrapper and the
declared fallback queue.

### 2.3 Build the first versioned table

Implement a reproducible generator for one simple, explicitly stated domain.
Emit:

- source-data and configuration digests;
- lookup data;
- fast/context/fallback classifications;
- generated invariants and table-size statistics;
- a human-readable coverage report.

The generator must fail on an unknown or ambiguous source form rather than
guessing.

### 2.4 Implement a scalar copy of the proposed transducer

The scalar candidate uses the same table, canonical stream, prefix rules,
fingerprint, and fallback contract intended for SIMD. It isolates algorithmic
changes from vectorization. Instrument reason-specific fallback and output
bytes.

### 2.5 Differentially validate

Compare candidate and ICU on:

- all in-scope authoritative conformance cases;
- empty, short, long, and boundary strings;
- canonical equivalents and combining marks;
- selected contractions and expansions;
- strings that differ only at each enabled strength level;
- random valid Unicode and targeted adversarial generators;
- every row that crosses from fast path to fallback.

Any mismatch is a correctness defect, not measurement noise.

### Deliverables and gate

- Scalar candidate and oracle agree on the frozen suite.
- Coverage/fallback reasons are reported on the pilot corpus.
- At least one million pairwise decisions pass with zero mismatches.
- `G2` has a recorded result.

Do not write SIMD code until `G2` passes.

## Milestone 3: implement one-ISA TSL kernel

### 3.1 Generate a minimal TSL C++ product

Pin the exact repository revision, source digest, machine profile, backend,
compiler, and build flags. Generate only the dependency-closed roots needed by
the kernel. Store generated and build output under
`tslctmp/collation/tsl/<evidence-digest>/`.

### 3.2 Implement structure-of-arrays lane state

Start with fixed-size prefix output and stream hash; defer arbitrary full-key
arenas. Keep row IDs so lane movement never changes logical output order.
Implement safe tails and empty strings first.

### 3.3 Implement all three schedulers

- no refill;
- masked refill;
- compact-and-refill.

Use exactly the same semantic step function. Scheduler identity is a benchmark
factor, not a compile-time accident.

### 3.4 Implement masked decode, lookup, and emission

Vectorize one code point/expansion step at a time. Bounds-check before every
gather. Route unsupported conditions to a compacted exception row list. Use the
scalar candidate and ICU to validate every output mode.

### 3.5 Add explanatory counters

Record:

- active lanes per iteration;
- bytes/code points/strings processed;
- compactions and refills;
- lookup classes;
- prefix completions and ties;
- exception counts by reason;
- output bytes and arena growth;
- candidate and fallback time separately and together.

Counters must be removable or separately timed so instrumentation does not
distort the primary result.

### 3.6 Run the kernel pilot

Compare:

- direct ICU compare when relevant;
- optimized ICU full/partial key generation;
- scalar same-algorithm transducer;
- SIMD no-refill;
- SIMD masked-refill;
- SIMD compact-and-refill.

Charge input setup, fallback, and required output writes to every candidate.

### Deliverables and gate

- All SIMD outputs pass the identical differential suite.
- Disassembly or compiler reports confirm that intended generated TSL operations
  are present; this is explanatory evidence, not a correctness oracle.
- The frozen pilot produces a recorded `G3` outcome.

If `G3` fails, do not hide the result by adding Parquet reuse or changing the
primary corpus. Diagnose once; stop if the proposed execution model is the
cause.

## Milestone 4: broaden the semantic domain

Only after `G3`:

1. add one real tailoring with contraction/expansion behavior;
2. add two non-Latin language/script families selected before tuning;
3. add normalization-sensitive data;
4. evaluate primary and tertiary strength; and
5. add numeric or French-secondary handling only if it is common in the chosen
   workloads, otherwise preserve exact fallback.

For each addition:

- extend the table compiler rather than hand-editing generated tables;
- add conformance and adversarial fixtures first;
- report incremental table size, cache footprint, fast coverage, and speed;
- rerun all previous identities to prevent regression.

`G4` determines whether the project can retain a multilingual claim. If the
candidate wins only on ASCII, stop the broad proposal.

## Milestone 5: integrate Arrow buffers

### 5.1 Define a zero-copy view

Accept Arrow-compatible validity, offsets, and data buffers without taking
ownership. Validate offset monotonicity and bounds in debug/test builds. Support
32-bit offsets first; add large-string offsets only after the basic path works.

### 5.2 Add batch-owned result arenas

Implement bounded prefix/fingerprint arrays and, separately, complete-key
arenas. Account for initialization, allocation, and destruction. Test empty
batches, tails smaller than one vector, all-null batches, and highly skewed
lengths.

### 5.3 Validate against Arrow/reference results

Round-trip logical row IDs after compaction, compare null handling, and verify
operator results on Arrow arrays. The standalone view should not require the
full Arrow C++ dependency; add the production adapter as a thin integration
layer.

## Milestone 6: implement dictionary and Parquet reuse

This milestone is conditional: execute it only if the kernel is useful and
`G1` showed workloads with meaningful dictionary potential.

### 6.1 Add dictionary products

Compile every distinct string into per-entry prefix/fingerprint/full-key status.
Optionally build a local collation rank for ordering. Include dictionary content
identity and `CollationIdentity` in the cache key.

### 6.2 Correctly handle collation-equivalent entries

Test dictionaries containing byte-distinct entries that collate equal. Grouping
and join consumers must merge them after exact confirmation. Ordering rank may
share a rank for equivalent values while stable tie-breaking remains separate.

### 6.3 Connect one production Parquet reader

Use its public dictionary/plain page outputs; do not implement a Parquet decoder.
Test standard files from at least two writers, mixed dictionary/plain chunks,
multiple dictionaries, nulls, and dictionary resets. Charge reader-to-view
adaptation and metadata gathers.

### 6.4 Implement cache invalidation

Demonstrate hits for identical content/identity and misses for changes in ICU
version, locale, strength, options, dictionary contents, or key format.

### Deliverables and gate

- Differentially correct dictionary/plain execution.
- Amortization curves over cardinality and reuse.
- A recorded `G6` result after held-out placement evaluation.

If only one policy always wins, remove the policy contribution and simplify the
system.

## Milestone 7: integrate one real database operator

### 7.1 Build a standalone operator model first

Implement the selected operator over Arrow-compatible buffers with the same
semantic contract as the target engine. This catches algorithm/data-structure
errors without a large engine build.

### 7.2 Choose the smallest faithful engine hook

Prefer a loadable extension or public execution hook if it can actually replace
the collation path being measured. A scalar UDF that bypasses the real operator
is not sufficient. If an engine fork is necessary, pin one DuckDB revision and
keep the patch small and isolated under `integration/duckdb/`.

Do not upstream or publish behavioral changes during the experiment. The
integration is a local research artifact until semantics and evidence are
stable.

### 7.3 Integrate products without changing SQL semantics

Preserve the engine's collation binding, null rules, stability, spill behavior,
parallelism setting, and error policy. For the first gate, use one worker and
in-memory data unless `G1` identified a different critical path. Add fallback
calls to the same collator as the baseline.

### 7.4 Run the frozen first-operator experiment

Measure binary control, unmodified ICU behavior, candidate with all costs, and
ablation variants. Report latency, memory, fallback, prefix ties, and time by
operator phase.

### Deliverables and gate

- Bit-for-bit or semantically exact result equivalence with the engine baseline.
- A minimal reproducible engine patch/extension.
- A recorded `G5` result.

Only if `G5` passes should a second, structurally different operator be added.
For example, follow a successful `ORDER BY` with `GROUP BY` or join, not another
sorting variant.

## Milestone 8: learn the placement boundary

Run the complete candidate matrix over cardinality, reuse, length, prefix
ambiguity, fast-domain coverage, and operator reuse. For each scenario:

1. measure every valid candidate;
2. record the measured oracle choice;
3. fit a small threshold policy or shallow tree on the training split;
4. freeze it;
5. report chosen-plan regret on held-out corpora, scenarios, and at least one
   machine.

Compare against fixed direct-ICU, fixed transient-prefix, and fixed full-key
policies. If winner regions are unstable or the policy cannot beat fixed
choices, fail `G6` and remove the optimizer claim.

## Milestone 9: test semantic portability

### 9.1 Add a second fixed-width family

After the primary x86 profile, prefer a real Arm NEON machine to distinguish ISA
family effects. AVX-512 is useful as a vector-width/compaction comparison but is
not by itself cross-family evidence.

### 9.2 Add one scalable-vector machine

Use real SVE or RVV hardware if available. Emulation may compile and run the
correctness suite but cannot support throughput, efficiency, or portability
claims. Record actual runtime vector length.

### 9.3 Keep semantic source fixed

Permit profile selection and TSL's primitive implementation differences. Any
change to the state machine, table layout, fast domain, key format, or scheduler
semantics is an algorithm fork and must be reported as such.

### 9.4 Explain gaps

Relate performance to gather latency, compaction realization, vector length,
cache capacity, lane occupancy, fallback, and generated implementation state.
Do not normalize away a slow target.

`G7` determines the final portability wording.

## Milestone 10: harden and package the evidence

### Required tests

- deterministic table generation and identity digests;
- unit tests for safe prefix and fingerprint decision rules;
- ICU differential and authoritative conformance tests;
- fuzz/property tests for UTF-8 boundaries and lane-state movement;
- AddressSanitizer and UndefinedBehaviorSanitizer runs;
- empty/tail/all-null/all-exception batches;
- dictionary resets and collation-equivalent dictionary entries;
- operator result tests;
- compile/build/value checks for each advertised TSL profile;
- reproducibility tests for scenario expansion and result summarization.

### Evidence record

Each run should contain:

```text
experiment/schema version
git revision and dirty-state digest
TSL source/artifact digest and profile
compiler, flags, linker, and build type
ICU/Unicode/CLDR and Arrow/Parquet/engine versions
complete CollationIdentity
machine/OS/CPU/vector-length/topology facts
corpus/scenario digests
candidate and scheduler identity
correctness status and fallback reasons
raw timing/counter samples
summary version
```

Never fold “generated,” “compiled,” “executed,” and “correct” into one success
flag.

### Reproduction interface

Provide explicit commands to:

1. inspect prerequisites without downloading;
2. fetch pinned optional dependencies/corpora with user intent;
3. generate the TSL slice;
4. build debug, sanitizer, and release configurations;
5. run correctness-only tests;
6. run one smoke benchmark;
7. run the frozen primary matrix; and
8. summarize existing raw data without rerunning experiments.

No test should require hidden network access or unannounced hardware.

## Dependency order

The critical path is:

```text
G0 novelty
  -> G1 database headroom
    -> G2 exact scalar domain
      -> G3 one-ISA SIMD breakthrough
        -> G4 multilingual domain
          -> Arrow adapter
            -> G5 first real operator
              -> second operator
              -> G6 dictionary/placement (independent after Arrow)
              -> G7 second/scalable ISA (independent after G4)
                -> G8 paper decision
```

Dictionary/Parquet and cross-ISA work can proceed independently after the core
kernel is exact and useful, but neither should consume effort before `G3`.

## Explicitly deferred work

- full arbitrary ICU tailoring support;
- persistent semantic keys in Parquet or Iceberg;
- distributed cache/version coordination;
- parallel/NUMA execution before the single-thread effect is understood;
- spill and external sorting before in-memory `ORDER BY` succeeds;
- automatic SQL rewrite or a general optimizer;
- Rust backend comparison;
- GPU/SIMT or FPGA implementations;
- `tslc`/`tsldata` changes not independently required by a general TSL gap.

## Final implementation success condition

Implementation is complete for the proposed paper only when all advertised
semantic identities pass exact differential evaluation, at least two real
operators meet their frozen end-to-end threshold, every performance claim names
real hardware and the actual TSL implementation evidence, raw data is
reproducible, and `G8` has a recorded positive outcome. Completing code without
those conditions is an artifact milestone, not completion of the research goal.
