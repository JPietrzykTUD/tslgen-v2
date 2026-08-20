# Fundamentals of relational truth-table execution

## Purpose and scope

This document defines the proposed execution model precisely enough to guide a
prototype and to distinguish its guarantees from ordinary query execution,
random testing, and symbolic equivalence checking. The accessible overview and
worked four-world example are in [`idea.md`](idea.md).

The initial system checks whether two relational expressions have equal results
over every database in a finite, explicitly declared universe. It returns one
of three outcomes:

```text
COUNTEREXAMPLE(D)       # D is legal and Q1(D) != Q2(D)
BOUNDED_EQUIVALENT(S)   # no difference exists in the complete bounded scope S
UNSUPPORTED(reason)     # the requested semantics are outside the implemented fragment
```

It must not collapse `BOUNDED_EQUIVALENT` into an unrestricted claim of query
equivalence.

## 1. Bounded database universe

### 1.1 Schema and finite domains

Let a relational schema be

```text
S = {R1(A11, ..., A1k), ..., Rm(Am1, ..., Aml)}.
```

For each attribute `A`, choose a finite typed domain `Dom(A)`. The first
prototype can derive a domain from:

- constants occurring in the query pair;
- constants required by constraints;
- a small number of canonical fresh values per type; and
- `NULL` when the selected semantic phase supports it.

For a set-valued relation `R(A1, ..., Ak)`, the possible ground tuples are:

```text
G_R = Dom(A1) x ... x Dom(Ak).
```

The bounded schema contains

```text
N = sum_R |G_R|
```

possible ground facts. Assign each fact a stable index from `0` to `N - 1`.
A database world is a Boolean assignment

```text
w in {0, 1}^N,
```

where bit `j` states whether ground fact `j` is present. The complete set-valued
universe therefore contains `2^N` database instances.

This ground-fact model is intentionally simple. A slot-based model can instead
bound rows without constructing the full domain product, but it introduces row
permutation symmetry and duplicate semantics. The initial implementation
should establish the ground-fact model before comparing alternatives.

### 1.2 World numbering

Worlds require a deterministic numbering because a set bit must be decoded
into a reproducible database. Under ordinary binary numbering, world `i`
contains fact `j` exactly when:

```text
(i >> j) & 1 == 1.
```

The input mask for fact `j` consequently alternates runs of zero and one of
length `2^j`. These masks can be generated directly for any contiguous tile of
world indices; they do not need to be stored for the whole universe.

Binary order does not guarantee the smallest counterexample by tuple count.
The system can obtain small explanations by one of the following explicit
strategies:

1. increase relation/domain bounds incrementally;
2. enumerate worlds by Hamming weight within a scope;
3. minimize a found world with a deterministic deletion pass; or
4. pass the found world to a dedicated counterexample minimizer.

The chosen policy and its minimality guarantee must be reported with the
result.

### 1.3 Legal worlds

Let `Gamma` be a set of integrity constraints. Define the validity truth table:

```text
V_Gamma[w] = 1 iff D_w satisfies Gamma.
```

Only worlds for which `V_Gamma` is one participate in equivalence. Primary-key,
unique, foreign-key, `NOT NULL`, and finite-domain `CHECK` constraints can be
compiled into bitwise predicates over input fact masks. More complex
constraints may initially be evaluated by a scalar world validator and packed
into `V_Gamma`.

Constraint handling is part of correctness, not an optimization. An invalid
world that differentiates two queries is not a valid counterexample under the
declared schema.

## 2. Transposed world representation

### 2.1 Tuple membership functions

For a relational expression `E` and a possible ground output tuple `t`, define:

```text
M_E(t)[w] = 1 iff t is in E(D_w).
```

`M_E(t)` is a Boolean function of the bounded input facts. The implementation
stores its truth table as a bitset. A conventional executor fixes `w` and
computes many tuples. The proposed executor fixes `t` and computes the tuple's
membership across many `w` simultaneously.

A world relation is therefore conceptually:

```text
WorldRelation = ordered map<GroundTuple, WorldMask>
```

where `WorldMask` contains one bit per world in the current tile. Tuple order is
canonical and derived from typed domain order so that comparison and artifact
generation are deterministic.

### 2.2 Physical world tiles

For a tile containing `T` worlds, a mask occupies `T / 8` bytes. `T` should be
a multiple of the target vector length except for the final tail. A physical
tile contains:

```text
WorldTile
  first_world_index
  world_count
  valid_world_mask
  generated base-fact masks
  query-local intermediate masks
```

The evaluator reuses tile-local arenas after comparing the two query outputs.
Thus peak mask memory is approximately:

```text
O(T * number_of_live_ground_tuples / 8),
```

not `O(2^N * number_of_ground_tuples)` for a suitably streamed plan. Total work
remains exponential when a bounded-equivalence result requires all tiles.

### 2.3 Boolean circuit interpretation

Every output tuple defines a Boolean function over base-fact variables. A
positive relational query induces a monotone provenance function; difference,
negation, and SQL conditions add complement and richer logic. Relational
truth-table execution evaluates the complete truth table of these functions in
tiles rather than retaining a symbolic formula.

This observation connects the proposal to provenance and possible-world
semantics, but the physical objective differs: produce exhaustive bounded
semantic signatures and counterexamples at high throughput.

## 3. Set-relational operator semantics

The following definitions assume finite set semantics. They are compositional,
so a typed relational-algebra tree can be interpreted recursively or compiled
into a mask-operation DAG.

### 3.1 Base relation

For a base relation `R` and `t in G_R`, `M_R(t)` is the input truth-table
variable assigned to that ground fact. For a tile starting at world index `b`,
bit `k` of `M_R(t_j)` is:

```text
((b + k) >> j) & 1.
```

### 3.2 Selection

For a deterministic predicate `p` over ground tuple values:

```text
M_select_p(E)(t) = M_E(t)  if p(t) is TRUE
                 = 0       otherwise.
```

Once correlated expressions or world-dependent scalar subqueries are
supported, predicate evaluation itself produces a world mask. The general
form is:

```text
M_select_p(E)(t) = M_E(t) AND T_p(t),
```

where `T_p(t)` marks worlds in which the predicate evaluates to SQL `TRUE`.

### 3.3 Projection and duplicate elimination

For set projection onto attributes `A` and output tuple `u`:

```text
M_project_A(E)(u)
    = OR { M_E(t) | project_A(t) = u }.
```

The OR expresses alternative witnesses: the projected tuple is present if at
least one input tuple producing it is present.

### 3.4 Cartesian product and join

For compatible tuples `l` and `r` whose concatenation or merge is `u`:

```text
M_product(L, R)(u)
    = OR { M_L(l) AND M_R(r) | combine(l, r) = u }.
```

An equijoin or theta join retains only pairs satisfying the join predicate:

```text
M_join_p(L, R)(u)
    = OR { M_L(l) AND M_R(r)
           | combine(l, r) = u AND p(l, r) = TRUE }.
```

The implementation should index ground tuples by join keys rather than test
the full Cartesian product. Nevertheless, the number of possible intermediate
tuples is a central scaling risk and must be measured explicitly.

### 3.5 Set operations

For corresponding ground tuple `t`:

```text
M_union(L, R)(t)        = M_L(t) OR M_R(t)
M_intersection(L, R)(t) = M_L(t) AND M_R(t)
M_difference(L, R)(t)   = M_L(t) AND NOT M_R(t).
```

The final physical vector must clear tail bits that do not denote worlds in the
tile. Complement is always taken relative to the current tile's valid bit
range, never over uninitialized storage.

### 3.6 Rename

Rename changes tuple schema and identifiers but not world membership:

```text
M_rename(E)(rename(t)) = M_E(t).
```

### 3.7 Semijoin and antijoin

For left tuple `l`, first compute the existence of any qualifying right
witness:

```text
W(l) = OR { M_R(r) | p(l, r) = TRUE }.
```

Then:

```text
M_semijoin(l) = M_L(l) AND W(l)
M_antijoin(l) = M_L(l) AND NOT W(l).
```

SQL `NOT IN` is not equivalent to this antijoin in the presence of `NULL` and
must use the three-valued extension below.

## 4. Bounded equivalence as a relational miter

Assume `Q1` and `Q2` have compatible result schemas. Let `G_out` be the union
of their possible ground output tuples. Missing tuple masks are treated as
zero. Define the difference mask:

```text
Delta = OR over t in G_out of
        ((M_Q1(t) XOR M_Q2(t)) AND V_Gamma).
```

This is analogous to a miter in circuit equivalence checking: any set output
bit witnesses a semantic difference.

For each world tile:

```text
function check_tile(Q1, Q2, tile):
    base  = generate_base_masks(tile)
    valid = evaluate_constraints(base, tile)
    out1  = evaluate(Q1, base)
    out2  = evaluate(Q2, base)
    delta = compare_outputs(out1, out2) AND valid

    if any(delta):
        local_bit = first_set_bit(delta)
        world_id  = tile.first_world_index + local_bit
        return decode_world(world_id)

    return no_difference_in_tile
```

If every tile has zero `Delta`, the expressions are equivalent for the exact
finite domains, relation semantics, row/multiplicity bounds, constraints, and
SQL feature contract recorded in the scope manifest.

### Counterexample replay

A decoded world is converted into deterministic DDL/DML or a structured
database artifact:

```text
schema
semantic mode and dialect
integrity constraints
ordered INSERT statements
Q1 and Q2
expected differing outputs
bound and world identifier
```

The artifact should be executed against an independent reference DBMS. A
replay mismatch can reveal a bug in the model checker, a dialect mismatch, or a
bug in the DBMS. It is not automatically evidence of the last case.

## 5. Extending the model toward SQL

### 5.1 Three-valued logic and `NULL`

For each predicate `p`, store two disjoint masks:

```text
T_p = worlds in which p is TRUE
U_p = worlds in which p is UNKNOWN
F_p = active_worlds AND NOT (T_p OR U_p).
```

SQL's three-valued connectives can then be evaluated with bitwise formulas.
For example:

```text
T_(p AND q) = T_p AND T_q
F_(p AND q) = F_p OR F_q
U_(p AND q) = active AND NOT (T_(p AND q) OR F_(p AND q))

T_(NOT p) = F_p
F_(NOT p) = T_p
U_(NOT p) = U_p.
```

A `WHERE` clause retains only `T_p`. Join conditions, `CASE`, `IN`, `NOT IN`,
and outer joins must use their declared SQL semantics rather than treating
unknown as ordinary false at every stage.

`NULL` can be included as a distinguished member of each nullable finite
domain. The ground-tuple universe and constraint masks then capture null
placement exhaustively.

### 5.2 Bag multiplicities

SQL relations are generally bags. A Boolean membership mask cannot distinguish
one copy from several. Bag support therefore changes both the world universe
and the value stored for each intermediate tuple.

Let each of the `N` possible base tuples have an input multiplicity in
`{0, ..., B_base}`. The complete bounded bag universe contains:

```text
W_bag = (B_base + 1)^N
```

worlds, rather than `2^N`. A deterministic mixed-radix numbering can decode
the multiplicity of base tuple `j` in world `w` as:

```text
mult(w, j) = floor(w / (B_base + 1)^j) mod (B_base + 1).
```

These input multiplicities can again be generated directly for a world tile.
The scope manifest must state `B_base`; calling the input decisions Boolean or
reporting `2^N` worlds once bags are enabled would be incorrect.

For every base or intermediate ground tuple `t`, represent its per-world
multiplicity with bit planes:

```text
C_E(t) = [C0(t), C1(t), ..., Ck(t)]
```

where bit `w` across the planes encodes the binary multiplicity in world `w`.
Bit-sliced full adders, subtractors, comparisons, and multipliers then implement
bag operations across all worlds:

- `UNION ALL`: bounded addition;
- projection: addition of witness multiplicities;
- join: multiplication of left and right multiplicities followed by addition
  across witnesses;
- `DISTINCT`: nonzero test producing Boolean membership;
- `EXCEPT ALL`: saturating subtraction; and
- `INTERSECT ALL`: per-world minimum.

Intermediate multiplicities can exceed `B_base`, especially after joins and
projection. Each plan node therefore needs either a sound derived counter
width or an explicit configured bound. Overflow behavior is part of the
semantic scope: it must produce `UNSUPPORTED` or an explicit overflow mask,
never silently wrap and certify the wrong semantics. Output equivalence
compares every multiplicity plane, not merely the nonzero membership mask.

An alternative is to enumerate row slots and quotient permutations through
symmetry breaking. Both representations should be compared only after the set
prototype works; bag support is a major research milestone, not a minor
engineering task.

### 5.3 Aggregation

`COUNT`, bounded integer `SUM`, `MIN`, and `MAX` can in principle be expressed
with bit-sliced arithmetic and per-group truth tables. Aggregation introduces
three sources of growth:

1. group keys define additional output-tuple universes;
2. aggregate values require a bounded result domain; and
3. SQL empty-input, null-elimination, overflow, and type-promotion rules must
   match the target dialect.

The first publication does not require all aggregates. `COUNT` over a small
domain is the preferred first case because it exercises multiplicities without
immediately requiring general arithmetic.

### 5.4 Ordering and limits

`ORDER BY` alone does not change a bag of tuples, but `LIMIT`, `OFFSET`, window
functions, and order-sensitive aggregates do. Their model requires a bounded
sequence semantics rather than unordered tuple masks. They should remain out
of the initial scope unless the earlier gates succeed.

### 5.5 Correlation, subqueries, and recursion

Subqueries can be lowered to supported semijoin, antijoin, aggregation, and
dependent-evaluation constructs. Correlation may make predicate masks depend
on outer tuples. Recursive SQL requires fixpoint evaluation over each world
and is a separate research problem. Unsupported syntax must be diagnosed
before evaluation rather than approximated.

## 6. Controlling state-space growth

### 6.1 Tiling

Tiling is mandatory. It bounds memory, allows early termination, and exposes
parallel scheduling across CPU threads, GPUs, or FPGA streams. Tile size is an
experimental parameter because larger tiles amortize plan overhead while
increasing live intermediate memory.

### 6.2 Domain reduction

Many constants are indistinguishable to a query except for equality and order
relationships. A domain constructor can retain query constants and introduce
canonical representatives for relevant intervals or equivalence classes.
Such reduction is sound only under a proved abstraction for the supported
operators. Heuristic domain reduction may be used to find bugs but cannot
support a bounded-equivalence statement.

### 6.3 Symmetry breaking

Renaming fresh domain values or permuting indistinguishable row slots can
produce isomorphic databases. A canonicalization rule or additional validity
mask can eliminate duplicate worlds. Correctness requires that every omitted
world be isomorphic, under the query and constraint vocabulary, to one retained
world.

### 6.4 Constraint-aware generation

Masking illegal worlds after generation is simple but may waste most of the
work for strong key or foreign-key constraints. Later variants can enumerate
only legal structures or partition facts into dependent groups. The plain
validity-mask method remains the reference because its semantics are easy to
audit.

### 6.5 Output-universe pruning

The evaluator should derive possible intermediate tuples from typed operator
semantics and finite domains, then discard tuples whose masks are zero in the
current tile. Static key and predicate analysis can further reduce candidate
tuples, but it must not reimplement an unsound query optimizer inside the
checker.

### 6.6 Hybrid symbolic checking

A practical system need not choose exclusively between truth tables and SMT.
Possible hybrids include:

- exhaust small scopes before invoking a solver;
- use a found world as an SMT seed or minimization bound;
- use truth-table signatures to cluster candidate-equivalent subexpressions;
- send only unresolved output differences to a solver;
- use solver-derived constraints to construct a denser legal-world generator;
  and
- select the engine from query features and estimated state-space size.

The pure executor must be evaluated before a hybrid policy is trained or tuned,
otherwise the source of any improvement will be unclear.

## 7. Complexity and expected crossover

Let:

- `N` be the number of independent bounded input facts;
- `W = 2^N` be the number of worlds;
- `L` be machine bits processed per vector operation;
- `K_E` be the number of live possible tuples across the plan; and
- `C_E` be the number of mask operations required per vector block.

A simplified set-semantics cost is:

```text
time  = O((W / L) * C_E)
space = O((T / 8) * K_E)
```

for tile size `T`. This estimate hides tuple indexing, plan interpretation,
constraint generation, and memory hierarchy effects. It makes the central
trade-off explicit: vector width divides a brute-force state space but cannot
change its exponential asymptote.

Truth-table execution is expected to be strongest when:

- a counterexample exists at a small bound;
- intermediate tuple universes remain small;
- constraints do not make legal worlds extremely sparse;
- the query compiles to long, regular bitwise loops; and
- solver search would spend significant time discovering a simple model.

SMT or theorem proving is expected to dominate when:

- a large bound is required;
- arithmetic and strings create large domains;
- strong constraints describe a tiny fraction of all Boolean assignments;
- symbolic structure allows large regions to be pruned; or
- unrestricted equivalence can be proved for the query class.

Locating this crossover empirically is one of the intended scientific results.

## 8. System architecture and ownership

The prototype is an independently owned research consumer of generated TSL:

```text
query pair + bounded schema + constraints
                   |
                   v
          typed SQL/RA front end
                   |
                   v
       bounded ground-domain planner
                   |
                   v
       relational mask-operation DAG
                   |
          +--------+---------+
          |                  |
          v                  v
 scalar word backend     TSL SIMD backend
          |                  |
          +--------+---------+
                   v
          tiled world executor
                   |
          +--------+---------+
          |                  |
          v                  v
 counterexample decoder   bounded certificate/report
          |
          v
 independent DBMS replay
```

The research prototype owns SQL semantics, finite domains, world layout,
relational operators, constraints, reports, and corpus adapters. `tslc` and
`tsldata` continue to own TSL primitive semantics, target selection, lowering,
generated artifacts, and verification. The compiler must not gain SQL syntax,
world semantics, or query-checker defaults for this project.

### TSL kernel boundary

The TSL-facing layer should expose representation-neutral operations such as:

```text
world_and(dst, lhs, rhs, words)
world_or(dst, lhs, rhs, words)
world_xor_or(accumulator, lhs, rhs, words)
world_and_not(dst, lhs, rhs, words)
world_any(mask, words)
world_first_set(mask, words)
bitsliced_add(...)
```

The first four are readily vectorized over bitset storage. Reductions may use
vector comparisons followed by a scalar final step if that is the simplest
portable contract. Query planning and tuple matching remain outside the kernel.

## 9. Correctness obligations

The system is scientifically useful only if its semantic scope is explicit and
its positive and negative answers are trustworthy.

Required invariants include:

1. every world bit has one deterministic database interpretation;
2. every legal bounded database is represented exactly once, or omitted only
   by proved symmetry reduction;
3. operator masks equal independent per-world relational evaluation;
4. constraints retain exactly the declared legal worlds;
5. tail and padding bits can never become counterexamples;
6. output comparison observes set or bag semantics exactly as declared;
7. decoded counterexamples reproduce in the independent semantic oracle; and
8. unsupported or overflowing cases fail closed.

For small scopes, the complete bit-parallel result should be cross-checked
against explicit per-world enumeration. Property-based operator tests and
replay in a pinned DBMS supplement but do not replace that oracle.

## 10. Closest work and claim boundary

| Existing area | Established contribution | Difference required here |
| --- | --- | --- |
| [VeriEQL](https://arxiv.org/abs/2403.03193) | Bounded equivalence and counterexamples for complex SQL through SMT. | Evaluate the complete bounded database truth table through relational bitset execution and measure its crossover with SMT. |
| [SQLancer](https://github.com/sqlancer/sqlancer) | Concrete database generation and specialized test oracles for DBMS logic and performance bugs. | Exhaust every database in a declared small scope and report a coverage guarantee for that scope. |
| [Possible-world representations](https://arxiv.org/abs/cs/0606075) | Compact models and query semantics for uncertain databases. | Use world positions as the physical execution dimension for exhaustive semantic comparison, not uncertainty answering. |
| [SIMD-PAC-DB](https://arxiv.org/abs/2603.15023) | Bit masks encode 128 stochastic subdatabase memberships for efficient privacy computation. | Enumerate a complete bounded input universe, retain per-output truth tables, compare two plans, and decode counterexamples. |
| [Alloy bounded analysis](https://courses.csail.mit.edu/6.897/spring01/papers/composition/alloy-fse00.pdf) | Relational specifications are translated to Boolean formulas and solved within finite scopes. | Execute a SQL-oriented relational algebra directly over transposed world truth tables and study explicit SIMD as the model-checking engine. |
| [EQUIPE](https://doi.org/10.1109/ICCD.2010.5647645) and EDA simulation | Parallel signatures and simulation accelerate circuit equivalence. | Define and implement the database-specific tuple universe, SQL semantics, joins, bags, constraints, and counterexample database reconstruction. |

The preliminary claim is intentionally mechanism-specific. A serious novelty
audit may still uncover a collision, especially in database provenance,
finite-model finding, deductive databases, or unpublished optimizer tooling.
Discovery of an equivalent physical method is a stop condition.

## 11. Research questions

The proposal ultimately asks:

- **RQ1:** For which relational fragments and bounds is exhaustive
  truth-table execution faster than symbolic bounded checking?
- **RQ2:** How do join fanout, output-domain size, constraints, bags, and
  `NULL` determine the maximum practical scope?
- **RQ3:** Does exhaustive small-scope execution find optimizer and SQL bugs
  that equal-time randomized testing misses?
- **RQ4:** Which symmetry, tiling, and hybrid techniques extend the useful
  region without compromising bounded coverage?
- **RQ5:** Does one TSL semantic implementation retain useful performance
  across fixed- and scalable-vector architectures?

The implementation and measurement programs for answering these questions are
defined in [`plan-implementation.md`](plan-implementation.md) and
[`plan-evaluation.md`](plan-evaluation.md).
