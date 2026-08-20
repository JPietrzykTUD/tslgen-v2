# Draft paper introduction: one bit, one database

Query optimization depends on semantic substitution. A database system parses
a declarative query, derives alternative relational expressions, and selects a
physical plan expected to execute efficiently. This process is safe only when
each transformation preserves the query result for every legal database
instance. A faulty transformation may silently omit tuples, introduce
duplicates, mishandle `NULL`, or change an aggregate. Such errors are difficult
to expose because the responsible database state is often much smaller and
stranger than a production benchmark: a particular duplicate, a missing join
partner, or one unknown predicate value can be sufficient.

Existing validation techniques occupy two complementary points in the design
space. Automated DBMS testing systems such as
[SQLancer](https://github.com/sqlancer/sqlancer) generate concrete database
states and use metamorphic or differential test oracles. They have found
hundreds of bugs in mature systems, but a finite random campaign provides no
coverage statement over the untested states. Formal equivalence systems reason
about all databases in a logical fragment. Recent work such as
[VeriEQL](https://arxiv.org/abs/2403.03193) supports bounded reasoning about
complex SQL and integrity constraints by encoding symbolic tuples into an SMT
problem. Solver-based reasoning is expressive, but its cost depends on query
structure, theories, and search heuristics; obtaining a small counterexample
can still take seconds or time out.

This paper investigates a third point: exhaustive execution over a small
database universe. At first sight, exhaustive evaluation appears untenable. If
a bounded schema admits `n` independent ground facts, their presence bits
define `2^n` database instances. The central observation is that these instances
need not be executed sequentially. By transposing the state space, one machine
bit can represent one complete database instance, and a machine vector can
carry the membership of a tuple across hundreds of databases. Relational
operators then become bulk operations over truth tables: join witnesses use
bitwise conjunction, alternative derivations use disjunction, and set
difference uses conjunction with complement.

We call this organization **relational truth-table execution**. For a fixed
finite domain, the system constructs a bitset for every possible input tuple.
Bit `i` states whether that tuple occurs in database `Di`. Evaluating a query
produces corresponding bitsets for every possible output tuple. Two expressions
are bounded-equivalent exactly when all their output bitsets agree after
masking database instances that violate the declared integrity constraints. If
an XOR exposes a difference, the index of a set bit is decoded into the base
tuples of a concrete counterexample database. The same computation therefore
acts both as an exhaustive checker and as a counterexample generator.

This representation changes where the exponential cost is paid. It does not
remove the `2^n` state space, nor does it establish unbounded equivalence.
Instead, it removes per-database query interpretation, allocation, and control
flow, replacing them with dense Boolean operations over tiled world masks.
That trade-off is plausible because many software faults have small witnesses,
an observation commonly described as the
[small-scope hypothesis](https://alloytools.org/tutorials/online/maintext-FS-1.html).
It is also uncertain: join output universes may grow rapidly, legal instances
may be sparse, and SQL bags, `NULL`, arithmetic, and aggregation require richer
bit-sliced state. Determining the useful boundary is a primary result of the
work rather than an assumption.

The proposal draws on, but is distinct from, several established lines of
research. Possible-world databases and provenance give semantics to alternate
instances and tuple derivations. [SIMD-PAC-DB](https://arxiv.org/abs/2603.15023)
recently demonstrated that bits can encode membership in 128 stochastic
database subsamples and that arbitrary rewritten SQL can exploit those masks.
Its goal is efficient privacy computation over sampled subdatabases, not
exhaustion of a bounded database universe or equivalence counterexample
generation. Conversely, bit-parallel simulation is established in hardware
verification; for example,
[EQUIPE](https://doi.org/10.1109/ICCD.2010.5647645) uses GPU parallelism for
combinational equivalence checking. The research question here is whether a
truth-table execution model can be made into a useful relational system with
SQL semantics, integrity constraints, counterexample reconstruction, and a
measured crossover against SMT and random testing.

Portable explicit SIMD is important to this investigation. The core execution
path consists of long bitwise kernels, but useful implementations also require
tail masking, first-difference extraction, population counts, bit-sliced
arithmetic, and layout decisions that differ between fixed- and
scalable-vector machines. We use TSL and `tslc` to instantiate one semantic
implementation across AVX2, AVX-512, NEON, SVE, and RVV where supported. This
does not make TSL the subject of the database claim. It provides controlled
implementations with which to determine whether the reachable verification
scope depends on vector width, predicate facilities, memory bandwidth, or
another architectural capability.

The intended system first targets set-valued select-project-join-union-
difference expressions over finite domains. It evaluates the database universe
in bounded tiles, filters illegal worlds with constraint masks, compares two
query plans, and either returns a replayable counterexample or a precisely
scoped bounded-equivalence result. Subsequent stages add SQL three-valued logic,
bag multiplicities represented by bit-sliced counters, and selected
aggregations. A separate scalar executor and replay against a real DBMS provide
independent correctness oracles.

The study is organized around the following proposed contributions:

1. **A world-parallel relational representation.** We define truth-table
   semantics for a useful relational fragment, including tiled execution,
   integrity-constraint masks, and deterministic counterexample decoding.
2. **A data-parallel bounded checker.** We implement the semantics as portable
   explicit-SIMD kernels and characterize the effects of query structure,
   domain size, legal-world density, and vector architecture.
3. **A comparison with symbolic and randomized validation.** We compare time
   to counterexample, bounded-state coverage, memory, and supported semantics
   against VeriEQL and concrete randomized testing on synthetic transformations,
   published query pairs, and optimizer regressions.
4. **An empirical boundary for exhaustive SQL checking.** We identify the
   fragments and scopes for which dense exhaustive execution is advantageous,
   those for which SMT remains superior, and whether a hybrid checker improves
   either approach.

The resulting thesis is deliberately falsifiable. Relational truth-table
execution is valuable only if small exhaustive scopes include practically
relevant errors and the bit-parallel algebra reaches them faster or more
reliably than existing approaches. A finding that join expansion, bag
semantics, or solver performance eliminates this region would reject the main
hypothesis and establish a useful limit on brute-force data-parallel
verification.
