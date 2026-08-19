# One Bit, One Database: Exhaustive Relational Semantics at Machine-Word Scale

Assessment date: **19 August 2026**

Programme: **DFG Reinhart Koselleck Projects**

Proposed duration: **5 years**

Indicative programme range: **EUR 500,000–1.25 million**

Submission status: **Draft high-risk concept; proposals may be submitted at any time**

Recommendation: **Apply only with an outstanding eligible PI and a successful bounded pilot**

## Proposal in one paragraph

One Bit, One Database asks whether the exponentially large space of small
database instances can be treated as data parallelism rather than enumerated
one world at a time. In the proposed representation, each bit position denotes
one complete bounded database world; bitwise relational operators then evaluate
a query simultaneously over thousands of worlds. If viable, this could create
a new computational basis for exhaustive query testing, bounded equivalence,
counterexample generation, and semantic exploration. The approach may also
fail: joins, bag semantics, nulls, and integrity constraints may destroy its
structural advantage. The project therefore combines formal semantics,
bit-parallel algorithms, comparison against scalar enumeration and SAT/SMT
methods, and explicit stop gates. `tslc` supplies portable bitset experiments;
the research object is the new relational representation.

## The high-risk scientific idea

Database testing and bounded verification repeatedly evaluate the same query
over many possible small instances. Conventional methods enumerate instances,
encode the problem into a solver, or generate selected counterexamples. This
project inverts the representation:

- fix a finite relational universe and enumerate its possible database worlds;
- assign one bit position to each world;
- represent the truth of a fact, tuple, or intermediate relation over all
  worlds as a bit vector;
- implement relational operators as transformations over those vectors.

Thousands of independent worlds can then be advanced by a handful of vector or
machine-word instructions. This is not merely bit-packing tuples inside one
database. The bit dimension is the model space itself.

The potential gain is radical, but so is the scaling risk. A finite universe
with `n` optional facts has `2^n` worlds. Useful structure, constraints, and
partitioning must compensate before that exponential dominates.

## Research questions

1. Which fragment of relational algebra admits compact, compositional
   truth-table execution over bounded database worlds?
2. Can joins and projection reuse enough structure to outperform scalar world
   enumeration or solver encodings at useful bounds?
3. How should integrity constraints prune, quotient, or compress the world
   space without making every operator solver-dependent?
4. Where is the crossover among bit-parallel execution, scalar enumeration,
   BDD/SAT/SMT techniques, and specialised query-equivalence tools?
5. Can the representation produce minimal, interpretable counterexamples for
   query-engine testing and semantic-difference analysis?

## High-risk/high-gain hypotheses

- **H1:** For bounded set semantics, selection, projection, union, difference,
  and a useful class of joins can be composed directly over bit-parallel world
  representations.
- **H2:** Constraint-aware factoring creates reusable subspaces that delay the
  exponential limit enough to make exhaustive testing practical beyond toy
  examples.
- **H3:** Different operators have distinct best representations; a small typed
  algebra can select among dense words, compressed bitsets, and factored
  subspaces without changing query semantics.
- **H4:** Exhaustive world-parallel execution finds semantic corner cases that
  random generation misses and can return them faster than general solvers for
  at least one well-defined query fragment.

A negative answer—an experimentally and formally characterised boundary beyond
which the representation loses—is an intended scientific outcome.

## Five-year work programme

### WP1 — Core model and kill experiment (months 1–9)

- Formalise finite integer domains, set semantics, and a small relational
  algebra.
- Implement a scalar world enumerator as the executable oracle.
- Implement selection, projection, join, union, and difference for a bounded
  universe of roughly 16–24 optional facts.
- Compare dense bit-parallel execution with scalar words and representative
  solver-based tools.

Gate: discontinue the central architecture if joins explode before useful
bounds or if bit-parallel execution has no reproducible advantage over simple
scalar-word batching.

### WP2 — Algebra, structure, and constraints (months 7–24)

- Derive compositional laws and cost models for intermediate representations.
- Add keys, foreign keys, domain constraints, and symmetry reduction.
- Explore factoring, partitioning, compressed bitsets, and incremental
  evaluation.
- Prove equivalence to the reference semantics for the supported fragment.

### WP3 — Semantic expansion (months 19–38)

- Study duplicates, SQL three-valued logic, nulls, aggregation, and correlated
  constructs one mechanism at a time.
- Record impossibility or complexity results where compositional execution
  breaks.
- Build representation-selection policies from mechanism-level evidence rather
  than hand-written query lists.

### WP4 — Applications and competitors (months 30–50)

- Integrate the engine with differential database testing and bounded
  query-equivalence workflows.
- Compare fairly with scalar enumeration, BDDs, SAT/SMT, and established
  database-verification systems.
- Evaluate counterexample latency, attainable universe size, memory, energy,
  and diagnostic usefulness.

### WP5 — General theory and open artefacts (months 43–60)

- State the tractable frontier and representation-selection principles.
- Release semantics, proofs or checked models, datasets, implementations, and
  reproducibility packages.
- Validate the ideas with an external database engine or verification group.

## Role of `tslc` and `tsldata`

`tslc` is a supporting apparatus for experimenting with word-, fixed-vector-,
and potentially scalable-vector bitset primitives across targets. Its typed
selection, lowering, generated value tests, and C++/Rust outputs can reduce
implementation drift between experimental variants. `tsldata` can record the
shared primitive semantics and test cases.

Neither repository currently implements a database truth-table engine, SQL
semantics, a solver, or a proof system. Those are new research components and
should live in an appropriately isolated experimental package. Compiler changes
are justified only by reusable bitset semantics, not by embedding a SQL parser
or database-specific raw-text rewrites into TSIL.

## Why this fits Reinhart Koselleck funding

| Programme characteristic | Project fit |
| --- | --- |
| Exceptionally innovative research | The database-world dimension, rather than tuples within one world, becomes the unit of bit parallelism |
| High scientific risk | Exponential state growth or join intermediates may invalidate the method despite a sound core idea |
| Potentially transformative gain | A successful representation would open a new execution basis for exhaustive testing and bounded semantic analysis |
| Five years of flexible funding | Formalisation, representation research, competitive implementation, and high-risk semantic expansion need iterative freedom |
| Not adequately served by ordinary funding | This claim is credible only if the proposal makes the early failure probability and need for flexible redirection explicit |

The instrument is PI-specific. The official programme requires an outstanding
scientific record and eligibility to hold a professorship. Without that record,
or if the pilot reduces the idea to a predictable implementation project, an
ordinary Research Grant is the appropriate route instead.

## Team and environment

The project needs a senior PI able to bridge database semantics and systems,
plus expertise in formal methods, high-performance bitset algorithms, and
experimental database evaluation. A credible environment would include:

- doctoral/postdoctoral researchers spanning semantics and systems;
- a database-verification collaborator who can audit comparisons;
- access to representative CPUs and performance/energy measurement;
- independent statistical and reproducibility review;
- a software architecture that keeps the experimental database engine one-way
  dependent on the compiler rather than coupling database semantics into it.

## Main risks and decision gates

| Risk | Gate or mitigation |
| --- | --- |
| Exponential universe dominates immediately | The month-9 kill experiment is mandatory; publish the boundary if the core hypothesis fails |
| Comparison with solvers is unfair | Use expert-reviewed encodings, report modelling time and end-to-end latency, and include multiple competitor families |
| SQL semantics make the model ad hoc | Begin with a formally precise relational fragment and add one semantic mechanism per experiment |
| A simple scalar implementation wins | Treat it as falsification, not a reason to add opaque compiler complexity |
| The idea overlaps existing bounded-verification work | Complete a deep prior-art audit before choosing the programme |

## Immediate preparation tasks

1. Verify the PI's Koselleck eligibility and publication record with the host
   research office and DFG contact.
2. Complete a structured prior-art map covering VeriEQL-style equivalence,
   SQLancer-style testing, BDD/bitset model checking, lifted databases, and
   possible-world semantics.
3. Run the bounded set-semantics pilot described in WP1 and publish the scalar
   oracle and crossover plots.
4. Obtain external reviews from one database-semantics and one formal-methods
   researcher before committing to the five-year framing.

## Official and local sources

- [DFG Reinhart Koselleck Projects](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/reinhart-koselleck-projects)
- [DFG eligibility guidance](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [Local One Bit, One Database pilot](../../query-eval/idea.md)
- [Local publication assessment](../../publication_assessment.md)
- [Local compiler charter](../../../tslc/CHARTER.md)
