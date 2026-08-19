# VLEN-Decode: Vector-Length-Aware Decoding of Standard Columnar Data

Programme: **DFG Research Grants Programme**

Proposed duration: **36 months**

Submission: **Proposals may be submitted at any time**

Recommendation: **Proceed to a real-hardware pilot and focused prior-art review**

## Proposal summary

Modern CPUs increasingly expose scalable vector instruction sets such as Arm
SVE and RISC-V Vector, where vector length is an implementation choice rather
than a compile-time constant. VLEN-Decode will determine whether one semantic
decomposition of standards-compliant columnar decoding can remain efficient
across vector lengths and architectures, or whether high performance requires
capability- and vector-length-conditioned stages.

The project will implement and compare universal, capability-conditioned, and
native-oracle decoders for selected Parquet encodings on real SVE, RVV, and
fixed-width SIMD systems. A scalar executable specification, generated
differential tests, and a reproducible benchmark corpus will separate semantic
correctness from scheduling choices. The result is knowledge about
scalable-vector algorithm design, not another format library.

## Scientific question

> Can a single vector-length-agnostic decomposition of standard columnar
> decoding remain competitive across SVE and RVV, and, where it cannot, what is
> the smallest capability model needed to recover performance without
> duplicating semantics?

Subquestions:

1. Which decoding stages are invariant under vector length?
2. Which stages depend on predicates, permutation, compaction, or memory
   capabilities?
3. How do data distributions, null density, encoded run length, vector length,
   and compiler interact to create performance cliffs?
4. Can a small strategy vocabulary approach native performance without native
   semantic duplication?
5. What is the portability cost in throughput, energy, source duplication, and
   change amplification?

## Hypotheses

- **H1:** semantic stages can be shared across fixed and scalable vectors while
  target scheduling remains isolated in a small number of typed strategies.
- **H2:** runtime vector length alone is insufficient; predicate, permute,
  compaction, and memory capabilities explain material performance variation.
- **H3:** capability-conditioned implementations reduce native-normalised
  regret without approaching the maintenance cost of independent native
  implementations.

The project remains scientifically useful if H1 fails, provided it produces a
controlled map of where portability breaks.

## Experimental design

Start with a narrow, standards-compliant slice: fixed-width integer data,
Parquet plain encoding, and one encoded path selected after the pilot, including
null handling and malformed-input behaviour. Add an encoding only when it tests
a distinct mechanism.

Compare three implementation levels:

- **U — universal:** one vector-length-agnostic formulation;
- **S — strategy-conditioned:** shared semantics with a small declared
  capability vocabulary;
- **N — native oracle:** expert implementation for every measured target.

All levels use one scalar reference and adversarial corpus. Measurements cover
real SVE and RVV systems, a fixed-width AVX-class baseline, several effective
vector lengths where hardware permits, and multiple toolchain versions where
practical. QEMU is functional evidence only.

Primary outcomes:

- native-normalised throughput and energy regret;
- tail latency and compiler sensitivity;
- semantic and source duplication;
- number of places changed when adding a target or encoding;
- prediction accuracy on a held-out machine or vector length.

The benchmark protocol will define warm-up, repetitions, clocks, flags,
measurement boundaries, uncertainty, and exclusion rules before the main
experiment.

## Work programme

### WP1 — Specification and pilot, months 1–6

- freeze selected Parquet semantics;
- implement the scalar executable specification;
- complete the Arrow/Parquet, database, compiler, SVE, and RVV prior-art matrix;
- establish adversarial/property-based inputs and real hardware access;
- preregister correctness and performance methodology.

Gate: demonstrate a non-trivial portability question on one SVE and one RVV
system.

### WP2 — Universal and strategy-conditioned decoders, months 5–16

- implement U;
- derive a minimal capability vocabulary from mechanisms rather than ISA names;
- implement S without duplicating semantic rules;
- generate differential and malformed-input tests.

Milestone: semantic equivalence across all supported vector lengths and inputs.

### WP3 — Native oracles and experiments, months 12–26

- implement or adapt expert N baselines;
- measure throughput, latency, energy, code size, and compiler sensitivity;
- use factorial and ablation experiments to separate vector-length and
  capability effects;
- publish reproducible evidence packages.

### WP4 — Model and transfer, months 23–36

- predict a held-out vector length or machine;
- quantify maintenance cost and change amplification for U, S, and N;
- validate transfer on one additional stage only if it tests the same theory;
- publish algorithms, negative results, corpus, and artefacts.

## Role of TSL

`tsldata` can hold typed semantics, capabilities, tests, and benchmark
metadata. `tslc` can select/lower specialisations and produce deterministic
C++/Rust artefacts and correctness evidence. The local repository also declares
scalable RVV, a RISC-V C++ toolchain, and QEMU execution.

Limits:

- the tracked coverage inventory does not probe the full RVV matrix;
- scalable-vector performance needs real hardware;
- Rust does not support the declared RVV extension;
- benchmark-shape coverage is incomplete;
- compiler changes must express reusable semantics, not Parquet-specific string
  rewrites.

## Relationship to CHORYS

CHORYS strengthens feasibility through open RISC-V near-data accelerator work,
hardware/software co-design, and the team's TSL/RISC-V integration. Public
CORDIS metadata does not name TSL, and CHORYS remains active through 2028.

| CHORYS contribution/result | Distinct DFG research |
| --- | --- |
| TSL/RISC-V engineering integration, as confirmed in grant records | Causal study of runtime vector length and capabilities in columnar decoding |
| Open RISC-V near-data platform context | Controlled RVV/SVE/fixed-width comparison on real hardware |
| Existing primitives, tests, and access | New Parquet semantics, adversarial corpus, U/S/N algorithms, and preregistered experiments |
| EU-funded staff, equipment, tasks, and deliverables | Separately costed DFG people, experiments, outputs, and publications |

The PI, CHORYS coordinator, and grants offices should approve a
task/personnel/cost/result matrix. Do not submit if CHORYS already funds the
same decoder experiments or central hypotheses.

## Fit to the DFG programme

| Programme characteristic | Fit |
| --- | --- |
| Bottom-up knowledge-driven research | General computer-architecture and data-systems question |
| Defined duration and scope | One decoder family, three implementation levels, 36 months |
| Originality | Falsifiable portability comparison and held-out-target test |
| Preliminary work | Typed compiler, RVV source data, tests, and corpus reduce apparatus risk |
| Feasibility | Six-month pilot and narrow standards slice |
| Research software | Compiler is necessary apparatus, not the research objective |

## Resources and team

A plausible team is one eligible PI, one doctoral or postdoctoral researcher
with low-level systems expertise, and student assistance. Secure:

- scheduled real SVE and RVV access;
- Parquet/database conformance expertise;
- calibrated energy measurement or a narrower energy claim;
- archiving, open-access, travel, and reproducibility resources.

## Risks and decision gates

| Risk | Response |
| --- | --- |
| Hardware access is too narrow | Obtain commitments before submission |
| Format work dominates | Freeze one bounded standards slice |
| Universal baseline is weak | Use expert-reviewed native oracles |
| Compiler engineering dominates | Add only reusable semantic capabilities required by experiments |
| Prior art answers the question | Complete review and pilot before full proposal |
| Double funding | Maintain an approved CHORYS/DFG boundary matrix |

## Immediate actions

1. Name the PI and verify eligibility.
2. Obtain written SVE/RVV hardware access.
3. Implement a minimal plain-decoding U/N pilot.
4. Complete the standards and prior-art matrix.
5. Review overlap with CHORYS and consult the host research office.
6. Discuss module-specific staffing/equipment questions with the DFG contact.

## Sources

- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [Research Grant guidelines](https://www.dfg.de/resource/blob/168072/50-01-en.pdf)
- [DFG eligibility](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [Research-software support options](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Target-family definition](../../../tsldata/detail/target_families.tsl)
- [Machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
