# Proposal: exact columnar collation through lane-refilled SIMD

**Status:** research proposal, not an established result

**Assessment date:** 2026-08-08

**Decision:** pursue only as a small, kill-gated pilot

## Executive assessment

The strongest research direction found so far is not a broader claim that TSL
can target SIMD, SIMT, and FPGAs. That would primarily be an accelerator-library
engineering program in a field already occupied by portable programming
systems. A stronger database question starts from a semantic operation that
columnar engines still struggle to make cheap:

> **Can a columnar database compile batches or dictionaries of UTF-8 strings
> into exact, versioned collation keys with a dynamically lane-refilled SIMD
> transducer, so that locale-aware ordering, grouping, joining, and range
> filtering approach binary-string performance across fixed- and
> scalable-vector CPUs?**

The proposed name for the technique is **columnar semantic-key compilation**.
The phrase describes a physical database transformation, not a new definition
of a collation key: sort keys and normalized database keys are established
ideas. The proposed contribution is to construct and exploit the keys across
many independent strings at once, preserve exact ICU-equivalent behavior
through conservative fast-path decisions and fallback, place the transformation
at the correct Arrow/Parquet/execution boundary, and study whether one semantic
algorithm remains useful across incompatible vector models.

This is a plausible outstanding idea, but it is deliberately presented as a
**candidate**, not as a novelty certificate. The preliminary search did not
find a publication or open implementation with this complete mechanism and
database integration. It did find substantial adjacent work. A systematic
paper, patent, and production-source audit is therefore the first stop gate in
the implementation plan.

## Why this is a database-systems problem

Collation defines equality and order for text under a locale, strength, and set
of options. It can therefore affect:

- `ORDER BY` and ordered indexes;
- equality and range predicates;
- `GROUP BY`, `DISTINCT`, and duplicate elimination;
- hash and sort-merge joins;
- partitioning, file statistics, and pruning;
- whether cached or persisted derived keys remain valid after a Unicode, CLDR,
  ICU, or tailoring change.

The database question is not merely whether one ICU routine can be made faster.
It is where and for how long semantic work should be materialized:

- transiently for an Arrow batch;
- once per distinct value in an Arrow or Parquet dictionary;
- once per query and reused by several operators;
- as a bounded prefix that resolves common comparisons and falls back on ties;
- or as a full, versioned key when reuse pays for its memory cost.

This placement problem couples language semantics, physical representation,
operator design, caching, and hardware. Those interactions are the intended
database contribution. TSL is the apparatus that makes the cross-ISA part
feasible and auditable.

## The core idea

An Arrow string column already separates offsets from UTF-8 data. The proposed
kernel assigns one independent string to each SIMD lane and keeps per-lane
state: byte cursor, logical row, collation level, pending expansion/context,
output cursor, and status. Active lanes decode their next code point, consult a
versioned collation table, and emit ordering weights. Masks identify completed,
exceptional, and refillable lanes. When a string finishes or leaves the proven
fast domain, another row refills its lane instead of allowing short strings to
idle behind long ones.

The kernel may produce three conservative products:

1. a bounded **ordering prefix** that may determine order only when its first
   differing byte is known to be part of the exact key;
2. an **equality-compatible fingerprint** for which unequal fingerprints prove
   inequality, while a match still requires exact comparison; and
3. a full key for rows or dictionary values where construction and reuse make
   materialization worthwhile.

Every unresolved or unsupported case goes to the pinned ICU reference path.
Prefixes and hashes must never be allowed to invent equality or order. This
makes the proposal an exact accelerator with a measured coverage domain, not an
approximate Unicode algorithm.

For Parquet dictionaries, each distinct string can be compiled once. Operators
then work through the dictionary entry's semantic metadata instead of
reprocessing every occurrence. Raw Parquet dictionary IDs are page-local,
arbitrary codes: they are neither ordered nor comparable across dictionaries.
Any rank or fingerprint must therefore be attached to the exact dictionary and
collation identity, and plain-encoded fallback pages must remain supported.

## Falsifiable hypotheses

The numerical thresholds below are proposed precommit values. They must be
frozen, together with the primary workloads and corpora, before confirmatory
measurements begin.

- **H1 — kernel value.** On realistic corpora from at least three
  language/script families, the TSL lane-refilled fast path plus exact fallback
  generates the required semantic-key product at least **1.8x faster** than a
  correctly configured ICU baseline, with zero semantic mismatches.
- **H2 — database value.** At least two of `ORDER BY`, `GROUP BY`/`DISTINCT`,
  equality or range filtering, and collated joins improve by at least **15%**
  end to end on a preregistered workload region without unacceptable memory
  growth.
- **H3 — format placement.** String cardinality, dictionary reuse, string
  length, prefix ambiguity, and collation complexity define repeatable regions
  in which transient Arrow compilation, Parquet-dictionary compilation, or
  direct ICU comparison is best. A small policy predicts the winning placement
  with materially lower regret than one fixed policy.
- **H4 — semantic portability.** The same state machine, table format, and
  correctness contract is competitive on at least two materially different
  vector families. A fixed-width x86 result alone cannot support a claim about
  scalable-vector portability.

These hypotheses fail if ICU is already near the attainable machine limit, the
fast domain collapses outside simple ASCII/Latin text, table gathers dominate,
key materialization overwhelms saved comparisons, database operators show no
end-to-end gain, or each ISA needs a different algorithm.

## What could be novel—and what is already occupied

The preliminary novelty screen is intentionally conservative.

| Established result or artifact | What it already establishes | Remaining question in this proposal |
| --- | --- | --- |
| [Unicode Collation Algorithm](https://www.unicode.org/reports/tr10/) and [ICU collation](https://unicode-org.github.io/icu/userguide/collation/) | Exact, configurable collation and binary-comparable sort keys already exist. | Can exact key construction be reorganized as a cross-string, lane-refilled columnar SIMD transducer? |
| [ICU collation architecture](https://unicode-org.github.io/icu/userguide/collation/architecture.html) | ICU already optimizes Latin processing, supports partial sort keys, and documents key reuse and version sensitivity. | Does a conservative batch algorithm beat this strong baseline on multilingual database data, and where should its products live? |
| [These Rows Are Made for Sorting](https://hannes.muehleisen.org/publications/ICDE2023-sorting.pdf) | DuckDB vectorizes normalized-key construction and uses fixed string prefixes; collation is evaluated before that encoding. Normalized keys themselves date back much further. | Can the expensive semantic transformation before normalized-key encoding itself become an exact vectorized columnar stage? |
| [Unicode at Gigabytes per Second](https://arxiv.org/abs/2111.08692) | SIMD Unicode validation and transcoding can reach very high throughput. | Collation additionally requires locale tailoring, contractions, expansions, normalization interactions, multiple weight levels, and exact database equality/order. |
| [Arrow collation request ARROW-12046](https://issues.apache.org/jira/browse/ARROW-12046) | There is longstanding engineering demand for locale-aware sorting in Arrow. | Demand is not a research result; the issue does not establish a vectorized exact algorithm or relational evaluation. |
| [Apache Arrow columnar format](https://arrow.apache.org/docs/format/Columnar.html) and [Parquet encodings](https://parquet.apache.org/docs/file-format/data-pages/encodings/) | Offset/data arrays and dictionary encodings are standard physical representations. | When should collation work be compiled per batch, per dictionary, or not materialized at all? |
| [Apache Iceberg PR #16972](https://github.com/apache/iceberg/pull/16972), inspected as a draft on 2026-08-08 | The proposal makes collation and provider version relevant to schema annotations and file bounds, while leaving broader equality, hashing, partition, and sort semantics outside its scope. | Can an engine execute exact versioned semantics efficiently, and can it safely exploit format-level reuse and statistics? |

The search did **not** establish that no proprietary engine, patent, thesis, or
non-English publication contains the proposed mechanism. The first research
phase must inspect at least PostgreSQL, MySQL/MariaDB, SQL Server public
materials, DuckDB, ClickHouse, Velox, DataFusion/Arrow, ICU, `parquet-rs`, and
relevant patent and dissertation indexes. If an equivalent method is found,
the main claim must be stopped or narrowed before implementation grows.

## Exactness and versioning are part of the contribution

A fast result is useful only if it preserves the engine's declared semantics.
The prototype must pin and record:

- collation provider and provider version;
- locale or tailoring identity;
- Unicode/CLDR data version where applicable;
- strength, case level/order, numeric mode, alternate handling, normalization,
  and any reordering options;
- UTF-8 validation/error policy;
- null and stable-sort tie-breaking semantics.

Keys from different identities must never be compared as though they were
compatible. A version mismatch invalidates cached semantic data and selects a
correct fallback or recompilation. This is particularly important for persisted
format metadata: the Iceberg discussion explicitly illustrates why collation
statistics and keys need a version contract.

## Arrow and Parquet are useful, but not the paper by themselves

The earlier generic idea “build a SIMD Parquet/Arrow reader with TSL” is too
crowded. Production readers already vectorize important decoding paths, and
recent work covers format comparisons, encoded predicate pushdown, null
representation, nested reconstruction, compression layouts, and random access.

Arrow and Parquet become useful here because they expose two different reuse
boundaries for a new semantic problem:

- **Arrow strings:** offsets and bytes provide the batch input for one-string-
  per-lane execution. Materialized prefixes are likely short-lived.
- **Arrow/Parquet dictionaries:** collation can be compiled once per distinct
  value and amortized over many codes and possibly several operators.
- **Parquet plain pages:** they provide the no-reuse control and ensure the
  design does not depend on dictionary encoding.
- **Iceberg metadata:** it motivates versioned collation identity and pruning,
  but the draft proposal is not assumed to be an adopted standard.

Thus “formats” are an experimental factor and integration point, not a novelty
claim.

## Why TSL is genuinely needed

The algorithm stresses exactly the vector mechanisms whose expression differs
between fixed- and scalable-vector ISAs:

- gathered and masked loads from independent byte streams and lookup tables;
- predicate masks for decode class, completion, exceptions, and output space;
- compress/expand or equivalent lane-state compaction and refill;
- mask population counts and prefix positions;
- per-lane state updates and bounded scattered output;
- vector-length-aware termination without assuming a compile-time lane count.

The current corpus contains relevant building blocks in
[`rnd_access.tsl`](../../tsldata/primitives/load_store/rnd_access.tsl),
[`pack_expand.tsl`](../../tsldata/primitives/load_store/pack_expand.tsl),
[`compress_expand.tsl`](../../tsldata/primitives/misc/compress_expand.tsl), and
[`bitwise.tsl`](../../tsldata/primitives/mask/bitwise.tsl). Their actual
availability, implementation state, and performance must be inventoried per
profile; their presence in source data is not evidence that every desired slot
is native or verified.

The intended scientific contribution is the collation algorithm and database
placement result. TSL and `tslc` provide controlled realizations across ISAs,
make implementation gaps visible, and reduce the temptation to silently change
the algorithm between machines. The first prototype must remain a downstream
consumer. Any missing general-purpose primitive should be proposed as a
separate projection-neutral TSL slice rather than making the compiler own
collation semantics.

## Why not broaden TSL to SIMD, SIMT, and FPGA first

That expansion remains a possible long-term product direction, but it weakens
this paper for three reasons:

1. “One accelerator API” is a broad and heavily occupied claim.
2. SIMT and FPGA implementations usually need different memory ownership,
   scheduling, and state-machine structures, so sharing surface syntax is not
   evidence of a shared algorithm.
3. Building backends before finding an important workload risks producing a
   large artifact without a falsifiable database result.

An FPGA or GPU follow-on becomes defensible only after profiling identifies a
stable operation—for example table lookup plus lane refill plus key emission—
whose semantics really survive the change in execution model. The CPU SIMD
pilot should establish that operation first.

## Decision rule

This proposal is worth pursuing only if it earns a sequence of early
breakthroughs:

1. the precise claim survives a serious novelty audit;
2. exact collation is a material wall in real columnar operators;
3. a conservative fast domain covers multilingual, not merely ASCII, data;
4. a TSL kernel beats both ICU and a scalar implementation of the same method;
5. at least one operator improves end to end before broad integration;
6. the same algorithm transfers to a second vector family.

Failure at any point is useful evidence and should stop or reframe the work.
The exact gates and thresholds are specified in
[`plan-implementation.md`](plan-implementation.md) and
[`plan-evaluation.md`](plan-evaluation.md).

## Proposal documents

- [`paper-introduction.md`](paper-introduction.md) is a short draft paper
  introduction.
- [`technical-proposal.md`](technical-proposal.md) defines the semantic and
  architectural design: what should happen, how, and why.
- [`plan-implementation.md`](plan-implementation.md) gives the staged
  implementation plan and explicit breakthrough/stop gates.
- [`plan-evaluation.md`](plan-evaluation.md) defines hypotheses, baselines,
  workloads, correctness checks, metrics, analysis, and publication criteria.

## Backup direction

If the collation claim collides with prior art or fails the first performance
gates, the best risk-adjusted fallback remains the narrower question already
described in
[`database-research-meta-study.md`](../database-research-meta-study.md): hold
standard Parquet bytes fixed and measure whether its encoding state machines
impose a vector-length-dependent decode tax across fixed and scalable CPUs.
That project is less distinctive, but it has a clearer incremental path than a
general SIMD/SIMT/FPGA library claim.
