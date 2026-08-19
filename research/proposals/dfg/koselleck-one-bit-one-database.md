# One Bit, One Database: Exhaustive Relational Semantics at Machine-Word Scale

Programme: **DFG Reinhart Koselleck Projects**

Proposed duration: **60 months**

Indicative funding range: **EUR 500,000 to EUR 1.25 million**

Recommendation: **Consider only for an outstanding eligible PI after a decisive
kill experiment**

## Proposal summary

One Bit, One Database asks whether a complete relational system over very small
finite domains can be compiled into machine-word algebra whose semantic state
space is exhaustively testable. Instead of treating vector instructions merely
as a faster loop mechanism, relations, truth values, nullability, provenance,
and selected query states become packed logical objects. The project will seek
a formal correspondence between relational semantics and bit-parallel
execution, build verified query operators, and determine when the approach
outperforms conventional vectorised and compiled databases.

The gain would be a new bridge among database theory, exhaustive verification,
and hardware-aware execution. The risk is fundamental: SQL semantics,
state-space growth, or memory movement may prevent useful scaling.

## High-risk question

> Can a non-trivial, standards-defined relational fragment be represented as
> exhaustively checkable finite-state bit algebra while retaining useful
> performance and a principled path to larger domains?

This is not “put database values into SIMD registers.” It tests whether
semantic completeness at small domains reveals new query algorithms and
verification methods.

## Hypotheses

- a bounded relational fragment admits a compact algebra with mechanically
  checkable equivalence to a reference semantics;
- nullability and three-valued logic can be represented without a combinatorial
  explosion that destroys usefulness;
- hardware word and vector operations can evaluate complete sets of possible
  tuples or states efficiently;
- learned structural rules transfer from exhaustive small domains to selective
  larger-domain algorithms;
- counterexamples and impossibility boundaries are themselves valuable theory.

## Five-year programme

### WP1 — Core model and kill experiment

Define the smallest relational fragment, reference semantics, packed
representation, and equivalence checker. Compare selection, projection, and
one join family with scalar and vectorised baselines.

Kill or radically redesign the project if the representation cannot express
null/duplicate semantics cleanly, exhaustive checks do not add insight, or
memory/translation costs dominate before any non-trivial query.

### WP2 — Algebra and constraints

Study algebraic structure, canonicalisation, constraints, equivalence classes,
and query rewrites. Prove or falsify closure and complexity claims. Develop
machine-checkable laws and counterexample generation.

### WP3 — Semantic expansion

Add aggregation, selected outer/anti/semi joins, nulls, duplicate semantics,
and provenance one mechanism at a time. Each extension must preserve an
executable reference and exhaustive test regime for bounded domains.

### WP4 — Applications and competitors

Compare with interpreted, compiled, vectorised, bit-sliced, and GPU/accelerator
database techniques. Test uses in query optimisation, differential testing,
small-domain analytics, and verification.

### WP5 — General theory

Characterise what transfers beyond exhaustive domains, publish negative
boundaries, and release specifications, corpora, proofs, algorithms, and
reproducible experiments.

## Role of TSL

TSL can provide typed primitive semantics, target selection, generated
implementations, and cross-target evidence. It is experimental infrastructure,
not the central contribution. The project must keep database semantics in an
appropriate typed model rather than teaching the compiler to parse arbitrary
SQL or target-language strings.

The repository's current cost-model and intermediate-representation research
can inform baselines, but the Koselleck project must establish a substantially
more ambitious theoretical contribution.

## Why Koselleck

| Koselleck characteristic | Fit |
| --- | --- |
| Exceptional innovation | Treats whole bounded relational semantics as a machine-word algebra |
| High risk | The representation may fail on SQL semantics or scaling |
| High gain | New database algorithms plus exhaustive semantic guarantees |
| Five-year flexibility | Allows theory, systems, verification, and negative-result work to co-evolve |
| PI requirement | Requires a professorially eligible PI with an outstanding record |

An ordinary Research Grant is preferable if the proposal is mainly an
implementation and benchmark programme.

## Team and environment

The project needs:

- an outstanding eligible PI spanning data systems and low-level execution;
- database theory/semantics expertise;
- formal methods or exhaustive verification expertise;
- compiler/SIMD expertise;
- experimental database systems and hardware measurement capability.

## Risks

| Risk | Decision |
| --- | --- |
| SQL semantics explode the state | Preserve a principled fragment and publish the boundary |
| Exhaustive domains are toy-only | Require transfer predictions and competitive applications |
| Performance claims use weak baselines | Include expert conventional and bit-sliced competitors |
| Compiler work consumes the project | Keep TSL an apparatus with bounded extensions |
| Idea is not exceptional enough | Use an ordinary Research Grant instead |

## Preparation

1. Name the PI and verify Koselleck eligibility.
2. Write the formal semantic fragment before the funding narrative.
3. Implement the bounded kill experiment.
4. Compare with current bit-sliced, finite-model, query-verification, and
   compiled-database work.
5. Obtain independent reviews from database theory, systems, and formal-methods
   experts.

## Sources

- [Reinhart Koselleck Projects](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/reinhart-koselleck-projects)
- [DFG eligibility](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [Pipeline cost-model idea](../../pipeline-cost-model-idea.md)
- [Intermediate-representation plan](../../intermediate-repr-src/PLAN.md)
- [Publication assessment](../../publication_assessment.md)
