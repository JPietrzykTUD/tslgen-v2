# One Bit, One Database

**Status:** high-risk research proposal, not an established result

**Assessment date:** 2026-08-08

**Working name:** relational truth-table execution

## The idea in one sentence

Build a bounded SQL model checker in which each bit represents one complete
small database instance, so that a SIMD instruction evaluates a relational
operation over hundreds of databases at once and a differing result bit can be
decoded into a concrete counterexample.

This is a testing and verification engine. It is not intended to replace the
normal query executor used to analyze a large production database.

## The problem

A query optimizer routinely replaces one relational expression with another.
For example, it might remove a join, push a predicate, decorrelate a subquery,
or replace one aggregation plan with another. The replacement is correct only
if both expressions return the same result for every legal database:

```text
for every database D: Q_original(D) = Q_rewritten(D)
```

Testing the expressions on one database does not establish this property. A
bug may require an unusual combination of duplicates, missing tuples, nulls,
or join partners. Random DBMS testing has found many such bugs, but it cannot
say that every database up to a given size was tested. Solver-based tools such
as [VeriEQL](https://arxiv.org/abs/2403.03193) reason symbolically and can
produce bounded counterexamples, but solving expressive SQL constraints is
expensive and unpredictable.

The proposed research asks whether very small database instances can instead
be checked by dense, exhaustive execution on modern data-parallel hardware.

## The inversion

Normal SIMD query execution assigns a data item from one database to each
lane:

```text
lane 0 = row 0 of database D
lane 1 = row 1 of database D
lane 2 = row 2 of database D
...
```

Relational truth-table execution transposes this mapping:

```text
bit 0 = database D0
bit 1 = database D1
bit 2 = database D2
...
```

A 512-bit vector can therefore carry one Boolean fact about 512 different
databases. Longer bitsets, processed as a sequence of vectors, can represent
millions of databases.

The fact carried by a bitset is usually:

> Does tuple `t` exist at this point in the query when the query is evaluated
> on database `Di`?

There is one such bitset for every possible tuple in an intermediate or output
relation.

## A complete four-database example

Assume a schema with one set-valued table:

```sql
CREATE TABLE R(x INTEGER);
```

Restrict the domain to the values `1` and `2`. There are two possible ground
facts, `R(1)` and `R(2)`. Each fact can be absent or present, so there are four
possible databases:

| World | Contents of `R` |
| --- | --- |
| `D0` | `{}` |
| `D1` | `{R(1)}` |
| `D2` | `{R(2)}` |
| `D3` | `{R(1), R(2)}` |

Consider these two queries:

```sql
-- QA
SELECT DISTINCT 1 AS v
FROM R;

-- QB
SELECT DISTINCT 1 AS v
FROM R
WHERE x = 1;
```

Their results in the four worlds are:

| World | `QA` contains `(1)` | `QB` contains `(1)` |
| --- | ---: | ---: |
| `D0` | 0 | 0 |
| `D1` | 1 | 1 |
| `D2` | 1 | 0 |
| `D3` | 1 | 1 |

Writing bits from `D0` through `D3`, the output membership masks are:

```text
QA(1) = 0 1 1 1
QB(1) = 0 1 0 1
XOR   = 0 0 1 0
```

The set bit in the XOR identifies `D2`. Decoding its index gives the concrete
counterexample:

```text
R = { (2) }
```

On that database, `QA` returns `(1)` and `QB` returns no row. Nothing was
sampled and no solver had to guess this database: all four databases were
represented and evaluated together.

## How relational operators act on the masks

Under set semantics, the core operations become bitwise operations:

| Relational operation | Operation over world masks |
| --- | --- |
| Selection | retain the tuple mask if its predicate is true; otherwise clear it |
| Projection | OR the masks of all input tuples that project to the same output tuple |
| Join | AND the masks of matching input tuples, then OR alternative witnesses |
| Union | OR corresponding tuple masks |
| Intersection | AND corresponding tuple masks |
| Difference | left mask AND NOT right mask |

For example, if a left tuple exists in worlds `L` and a matching right tuple
exists in worlds `R`, their joined tuple exists in `L AND R`. If several tuple
pairs derive the same output tuple, their masks are combined with OR.

Primary keys, foreign keys, and other integrity constraints are represented by
another bitset. Bit `i` of this validity mask is one exactly when database `Di`
satisfies the constraints. Invalid worlds are removed with AND before query
results are compared.

## Why this is not the same as running the query millions of times

A naive exhaustive tester constructs a database, invokes a query engine,
collects the result, clears the database, and repeats. It pays parsing,
planning, data-structure, and control-flow costs for every world.

The proposed engine stores the truth table in transposed form. One bitwise AND
per vector replaces hundreds of independent join-witness checks. The query
plan is interpreted or compiled once, and all represented worlds follow that
plan together. The approach resembles bit-parallel logic simulation more than
ordinary database execution.

The complete `2^n` state space need not be materialized at once. It can be
processed in fixed-size world tiles:

```text
for each tile of database worlds:
    generate the base-fact masks for this tile
    compute the legal-world mask
    evaluate QA over the tile
    evaluate QB over the tile
    compare their output masks
    stop and decode if a difference exists
```

Tiling bounds memory consumption. It does not remove the exponential running
time required to exhaust all worlds.

## What the system would solve

The proposed system could provide:

- bounded validation of optimizer rewrite rules;
- counterexamples for incorrect hand-written or LLM-generated SQL rewrites;
- exhaustive small-scope testing of SQL compiler and logical-plan lowering;
- deterministic regression tests for previously discovered optimizer bugs;
- small input databases that explain why two queries differ; and
- a fast pre-pass or companion to an SMT-based equivalence checker.

The most direct first application is testing a pair consisting of an original
logical plan and the plan produced by one optimizer transformation. If their
bounded truth tables differ, the resulting database can be replayed against a
real DBMS.

## What it would not solve

The proposal does **not** claim:

- unbounded equivalence for arbitrary SQL;
- that absence of a bounded counterexample proves unrestricted equivalence;
- efficient execution of normal analytical queries over production data;
- verification of every instruction in an existing DBMS binary;
- that exhaustive enumeration will beat symbolic solvers at large bounds; or
- immediate support for the full SQL standard.

The output `bounded equivalent at scope S` must never be reported simply as
`equivalent` unless a separate theorem establishes a sufficient small-model
bound for the supported query class.

## Why the exponential state space may still be useful

With `n` independent Boolean ground facts there are `2^n` databases. This is a
hard limit, not a detail to hide. The research bet rests on three observations:

1. Incorrect transformations often have small counterexamples. This is the
   motivation behind Alloy's
   [small-scope hypothesis](https://alloytools.org/tutorials/online/maintext-FS-1.html).
2. A bit-transposed executor performs very little work per world: common
   relational operations become dense Boolean kernels.
3. Counterexample search can stop at the first differing bit; only a bounded
   equivalence result must exhaust the selected space.

The decisive scientific question is therefore not whether exponential growth
exists. It is where the crossover lies between exhaustive data-parallel
execution and symbolic search, and whether that crossover covers useful
optimizer and SQL bugs.

## Precise novelty boundary

Several nearby ideas are already established:

- Possible-world databases represent alternative database instances.
- Provenance systems represent how output tuples depend on input tuples.
- [SIMD-PAC-DB](https://arxiv.org/abs/2603.15023) stores membership in 128
  stochastic database subsamples as bits and evaluates rewritten SQL once.
- [VeriEQL](https://arxiv.org/abs/2403.03193) performs bounded SQL equivalence
  checking using SMT.
- [SQLancer](https://github.com/sqlancer/sqlancer) generates databases and
  applies specialized test oracles to find DBMS bugs.
- Hardware verification uses parallel simulation and equivalence checking;
  [EQUIPE](https://doi.org/10.1109/ICCD.2010.5647645) is one example.

Consequently, neither “possible worlds,” “bits as worlds,” “bounded SQL
checking,” nor “parallel equivalence checking” is a novelty claim by itself.
The candidate contribution is their specific database-systems realization:

> A relational truth-table executor that maps every database in a bounded
> universe to a bit position, evaluates SQL algebra exhaustively over those
> positions, and extracts a counterexample directly from a result difference.

The preliminary search found no published database system with this exact
physical representation and purpose. That is not proof that no such work
exists. A systematic scholarly, patent, dissertation, and production-source
audit is the first implementation gate.

## Why TSL is genuine experimental infrastructure

The hot representation consists of long, aligned bitsets. Its operations need
bitwise Boolean primitives, loads and stores, mask handling, population count,
first-set-bit detection, and eventually bit-sliced arithmetic. TSL can express
the same semantic kernels for fixed- and scalable-vector targets while `tslc`
provides implementation provenance and generated verification.

TSL is therefore useful for measuring how far different vector machines can
push the bounded state space without maintaining unrelated AVX2, AVX-512,
NEON, SVE, and RVV implementations. A limited handwritten implementation is
still required as an abstraction-overhead control.

The prototype should remain a downstream research consumer of generated TSL.
SQL semantics, world enumeration, relational operators, and counterexample
decoding do not belong in `tslc` or `tsldata`. A missing general-purpose TSL
primitive would be proposed separately and justified independently.

GPU or FPGA execution is a conditional second study. It becomes scientifically
motivated only if the CPU prototype establishes that truth-table execution is
useful. The research claim is the world-parallel relational algebra, not a
generic claim that one library can hide SIMD, SIMT, and FPGA execution models.

## The first go/no-go result

The smallest credible prototype needs only:

- finite integer domains;
- set semantics;
- selection, projection, join, union, and difference;
- tiled enumeration of at most roughly 16--24 independent ground facts;
- one independent scalar per-world reference; and
- comparison with VeriEQL on a compatible query subset.

The direction should be stopped or substantially reframed if joins and
intermediate tuple universes make even small scopes impractical, if the SIMD
implementation provides little benefit over a scalar word-parallel engine, or
if SMT consistently finds the same small counterexamples faster. Bags, NULLs,
constraints, and aggregation should be attempted only after this first result.

## Research question

> Can a transposed, bit-parallel relational representation make exhaustive
> bounded evaluation of useful SQL fragments fast enough to improve optimizer
> validation and DBMS testing over solver-only and random-testing approaches?

That question is falsifiable, database-specific, and enabled rather than
merely decorated by TSL.
