# Draft paper introduction: semantic-key compilation for exact columnar collation

Analytical databases increasingly process text drawn from many languages, yet
their fastest string operations usually compare raw bytes. Binary comparison is
cheap and deterministic, but it does not implement the equality and ordering
that users expect for case, accents, normalization, contractions, numeric
substrings, or locale-specific alphabets. Exact collation is therefore not a
presentation detail: it changes the semantics of filtering, grouping, joining,
sorting, indexing, and pruning. DuckDB's documentation, for example, calls its
binary collation “by far the fastest” while directing regional behavior to ICU.
This gap makes correct multilingual queries an increasingly visible semantic
tax rather than an exotic feature.

Columnar execution should in principle help. An engine already receives
thousands of strings as an Arrow-style offsets array plus a byte buffer, and a
Parquet dictionary may expose thousands or millions of occurrences of the same
distinct values. In practice, however, collation is commonly evaluated through
a scalar library boundary. ICU can compare strings or generate binary-comparable
sort keys, and database systems can subsequently encode key prefixes into
cache-friendly normalized rows. The expensive semantic transformation itself
still precedes that vectorized machinery. DuckDB's relational sorting work
makes this boundary explicit: it vectorizes normalized-key construction but
evaluates string collation before encoding the string prefix. Meanwhile,
high-throughput SIMD Unicode work has focused on validation and transcoding,
which do not have to implement locale tailoring, multi-level weights,
contractions, expansions, or collation equality.

This paper asks whether collation should instead be treated as a columnar
compilation step. We propose **semantic-key compilation**, an exact batch
transformation that assigns one independent UTF-8 string to each SIMD lane and
advances the active strings through a versioned collation transducer. Each lane
maintains its own input cursor, collation state, and output position. Predicate
masks identify completed strings, complex cases, and lanes that need more
input; completed or exceptional lanes are dynamically refilled with new rows.
This organization converts variable-length control flow from a sequence of
scalar calls into a masked, cross-string data-parallel computation.

The transformation produces only information that can be used safely. A fixed
ordering prefix decides a comparison when it contains the first exact
distinguishing weight. An equality-compatible fingerprint can reject unequal
values but cannot establish equality by itself. Full keys are generated when
their expected reuse justifies their memory cost. Prefix ties, fingerprint
collisions, unsupported tailoring rules, and other cases outside the proven
fast domain are resolved by the reference collator. Consequently, the proposed
method is not an approximate ASCII shortcut: every database result must be
identical to the result obtained from the pinned ICU configuration.

Physical placement is central to the design. For transient Arrow batches, the
engine can compile short prefixes just before a consuming operator and discard
them with the batch. For dictionary-encoded Arrow or Parquet data, it can
compile each distinct string once, attach semantic metadata to that dictionary,
and process occurrences through integer indirection. Dictionary codes are not
assumed to be ordered or globally comparable; any derived rank is scoped to the
dictionary and exact collation identity. Plain pages and dictionary changes
remain correct fallback boundaries. This makes string cardinality, reuse,
prefix ambiguity, and collation complexity physical-design parameters whose
interactions can be measured rather than hidden inside a scalar function.

Versioning is equally important. ICU sort keys and ordering behavior can change
with the provider, data tables, tailoring, and configuration. Cached semantic
data must therefore carry a complete collation identity and must be invalidated
or recomputed on mismatch. The issue is becoming relevant beyond an individual
engine: a draft Apache Iceberg proposal inspected in August 2026 introduces
provider- and version-qualified collation bounds for file pruning while leaving
broad execution semantics outside its scope. Efficient exact execution is thus
both an engine problem and a prerequisite for safely exploiting emerging
format metadata.

We use TSL to express the masked gathers, table lookups, compaction/refill, and
vector-length-aware state transitions once and instantiate them for fixed- and
scalable-vector CPUs. TSL is an experimental instrument rather than the paper's
main contribution: the scientific question is whether the semantic algorithm
and its database placement survive architectural differences without
ISA-specific algorithm forks. A negative result—such as lookup-bound execution,
low multilingual fast-path coverage, or key-materialization costs that erase
operator gains—would be equally informative.

The intended contributions are:

1. an exact, lane-refilled SIMD transducer for constructing conservative
   collation prefixes, equality filters, and full keys across independent
   columnar strings;
2. a dictionary-aware integration that chooses among transient Arrow
   compilation, per-dictionary compilation, and direct comparison without ever
   treating raw dictionary IDs as semantic order;
3. an end-to-end study of collated filtering, grouping, joining, and sorting,
   including memory, ambiguity, fallback, and version-invalidation costs; and
4. a portability study across fixed- and scalable-vector ISAs using one
   semantic implementation, with ICU-equivalent correctness as a hard
   constraint.

These are target contributions, not claims of completed results. The work is
worth continuing only if an initial prior-art audit finds a defensible gap, the
fast path covers genuinely multilingual corpora, the kernel materially
outperforms ICU, and the improvement survives inside at least two relational
operators.

## Sources cited in this draft

- [DuckDB collations](https://duckdb.org/docs/lts/sql/expressions/collations)
- [ICU collation architecture](https://unicode-org.github.io/icu/userguide/collation/architecture.html)
- [These Rows Are Made for Sorting](https://hannes.muehleisen.org/publications/ICDE2023-sorting.pdf)
- [Unicode at Gigabytes per Second](https://arxiv.org/abs/2111.08692)
- [Apache Iceberg PR #16972](https://github.com/apache/iceberg/pull/16972)
