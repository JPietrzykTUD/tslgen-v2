# PORTABILITY FRONTIER: Where Portable Data-Processing Semantics End

Instrument: **ERC Starting Grant 2027 or Consolidator Grant 2027**

Duration: **Up to five years**

Starting Grant deadline: **14 October 2026**

Consolidator Grant deadline: **12 January 2027**

Recommendation: **Strong frontier-science route only for a PI with the correct
eligibility window, record, host support, and real accelerator access**

## Proposal summary

PORTABILITY FRONTIER will establish the scientific limits of portable
data-processing semantics across CPUs and accelerators. It asks which facts
about an algorithm can remain target-independent, which must be conditioned on
capabilities, and where architecture-native methods are irreducible.

The project will create matched implementations of selected database and
data-processing kernels at three levels: universal semantics, a small
capability-conditioned strategy vocabulary, and expert native oracles.
Generated differential tests will establish semantic equivalence; real hardware
experiments will measure performance, energy, integration effort, source
duplication, and change amplification. The goal is a predictive theory of
portability boundaries, not a library claiming one implementation is optimal
everywhere.

## Frontier question

> Is there a compact, target-independent semantic layer that preserves both
> meaning and most attainable efficiency across fundamentally different
> execution mechanisms, and can its failure points be predicted before an
> implementation is built?

Subquestions:

1. Which kernel structures transfer across fixed-width SIMD, scalable vectors,
   GPUs, and reconfigurable or near-data systems?
2. Which capability facts explain portability cliffs better than ISA or device
   names?
3. Can native-normalised performance regret be predicted from semantic and
   hardware features?
4. How should correctness, performance, energy, and maintenance costs be traded
   without collapsing into one arbitrary score?
5. What negative boundaries prove that native algorithms are unavoidable?

## Hypotheses

- semantic decompositions transfer farther than schedules and memory movement;
- a small capability vocabulary explains a large share of performance
  variation;
- strategy-conditioned implementations substantially reduce regret relative to
  universal ones while preserving most semantic sharing;
- generated evidence can make portability claims falsifiable and reproducible;
- some kernel/architecture pairs exhibit irreducible native structure, which
  the model can identify.

## Experimental ladder

Select kernels that expose different mechanisms:

- scans, filters, and predicate handling;
- compression/expansion and sparse materialisation;
- columnar decoding;
- gather/scatter and irregular memory;
- aggregation or hash-table building;
- one near-data or accelerator-specific workflow.

For each kernel, implement:

- **U:** universal semantic form;
- **S:** shared semantics plus declared capability strategies;
- **N:** expert architecture-native oracle.

Targets must include fixed-width SIMD and scalable RVV/SVE. GPU, FPGA, or
near-data targets enter only with committed expertise and real hardware.

## Evidence model

Measure:

- correctness over shared adversarial corpora;
- throughput, latency, and native-normalised regret;
- energy with declared system boundaries and uncertainty;
- compilation/toolchain sensitivity;
- code size and integration effort;
- semantic/source duplication and change amplification;
- ability to predict held-out targets, vector lengths, or kernels.

QEMU and simulators support correctness and mechanism exploration, never
unqualified performance claims.

## Work programme

1. **Theory and vocabulary:** define observable semantics, capability features,
   evidence quality, and preregistered metrics.
2. **Experimental apparatus:** build reference semantics, generated tests,
   target integrations, native-oracle review, and reproducible measurement.
3. **Kernel experiments:** execute controlled U/S/N comparisons and ablations.
4. **Predictive model:** explain and predict portability boundaries on held-out
   hardware or mechanisms.
5. **Synthesis:** publish theory, counterexamples, algorithms, corpora, and open
   evidence packages.

## Role of TSL and CHORYS

TSL provides typed source semantics, selection/lowering, generated output, and
verification apparatus. CHORYS provides a credible RISC-V near-data and
hardware/software co-design context. Neither is the ERC contribution itself.

The ERC project must be PI-driven and scientifically broader and deeper than
CHORYS deliverables. It must separate all CHORYS background/results from new
ERC foreground and avoid duplicate funding. The public CHORYS page does not
name TSL, so internal project records are required.

## Readiness gaps

- real RVV/SVE and accelerator access;
- expert native baselines;
- a narrow but mechanism-diverse kernel selection;
- calibrated cross-platform energy methodology;
- proof that the PI owns a coherent frontier vision rather than a software
  roadmap;
- preliminary evidence of a non-obvious portability boundary.

## ERC fit

ERC evaluates the PI and project on excellence. The concept is bottom-up,
high-risk/high-gain, and potentially field-shaping if it produces a predictive
theory rather than an implementation catalogue.

Starting Grant eligibility is generally 0–10 years from PhD defence;
Consolidator Grant eligibility is generally 5–15 years, subject to official
extension rules. The named PI must determine the instrument. Starting Grants
may provide up to EUR 1.5 million for five years and Consolidator Grants up to
EUR 2 million, with possible justified additional funding under the call rules.

## No-go conditions

Do not submit if:

- no eligible PI with a competitive track record is identified;
- the project is mainly compiler engineering;
- native oracles and real target access are missing;
- the selected mechanisms are too similar to support a general theory;
- CHORYS and ERC work cannot be separated;
- the pilot shows only unsurprising compile-time portability differences.

## Immediate actions

1. Apply the exact ERC eligibility rules to the candidate PI.
2. Choose the panel and obtain panel-aware external reviews.
3. Run one U/S/N real-hardware pilot across RVV, SVE, and fixed-width SIMD.
4. Complete a systematic prior-art and funded-project landscape.
5. Secure target experts and hardware.
6. Build a CHORYS/background/new-foreground matrix.

## Sources

- [ERC Starting Grant](https://erc.europa.eu/apply-grant/starting-grant)
- [ERC Consolidator Grant](https://erc.europa.eu/apply-grant/consolidator-grant)
- [ERC 2027 application changes](https://erc.europa.eu/news-events/news/applying-erc-grant-2027-competitions-what-you-need-know)
- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
