# PORTABILITY FRONTIER: Where Portable Data-Processing Semantics End

Instrument: **ERC Starting Grant 2027 or ERC Consolidator Grant 2027**

Proposed duration: **5 years**

Indicative maximum core grant: **EUR 1.5 million (Starting) or EUR 2 million
(Consolidator), with additional funding subject to ERC rules**

Assessment date: **19 August 2026**

Starting Grant deadline: **14 October 2026**

Consolidator Grant deadline: **12 January 2027**

Recommendation: **Strong frontier-science concept, conditional on the PI and preliminary evidence**

## Proposal in one paragraph

PORTABILITY FRONTIER will discover the point at which data-processing semantics
can no longer be shared across SIMD CPUs, SIMT GPUs, and spatial FPGA pipelines
without unacceptable performance or energy loss. Rather than assume that one
program maps everywhere, the project will separate semantic invariants from
target scheduling and compare three levels for representative kernels: a
universal formulation, a strategy-conditioned formulation, and an expert
native oracle. Experiments on a regular fused scan, standards-based columnar
decoding, and an irregular hash probe will measure native-normalised performance
and energy regret, semantic duplication, and change amplification on real
hardware. The project seeks a general theory and empirical map of the minimum
semantic lift required for heterogeneous portability. `tslc` and `tsldata`
provide a typed, test-generating CPU starting point; GPU and FPGA execution are
research to be built and validated, not existing capabilities.

## Frontier question

Portable programming systems tend to collapse two different goals: saying what
a data operation means and choosing how a target should schedule it. CPUs group
lanes into vectors, GPUs organise SIMT threads and memory hierarchies, and FPGAs
construct spatial pipelines. A universal abstraction may preserve meaning but
erase the target's advantage; native implementations may recover performance
but duplicate semantics and verification.

The central question is:

> What is the smallest shared semantic interface that preserves correctness
> across vector, SIMT, and spatial execution while allowing each architecture
> to retain its essential scheduling structure?

The project treats “the portability tax” as a measurable scientific object. It
will not equate source-code reuse with portability.

## Core hypotheses

- **H1 — semantic core:** A small typed semantic core can be shared across all
  three architecture classes for regular and decode-heavy data processing,
  while scheduling remains target-owned.
- **H2 — structured middle:** A strategy-conditioned middle layer achieves
  substantially lower native-normalised regret than a universal layer with far
  less semantic duplication than fully native implementations.
- **H3 — mechanism frontier:** Portability fails at identifiable mechanisms
  such as irregular communication, stateful compaction, or architecture-shaped
  memory coordination, rather than at arbitrary application boundaries.
- **H4 — maintainability trade-off:** Semantic sharing and performance can be
  analysed jointly using change amplification and verification obligations;
  line-count reuse alone predicts neither.

Falsification is central. If the strategy layer merely accumulates target-name
conditionals, or if native code wins everywhere without a stable semantic core,
the proposed abstraction has failed. If universal code matches all native
oracles, the presumed scheduling frontier is itself rejected.

## Experimental ladder

Every kernel/target pair will be implemented at three controlled levels:

- **U — universal:** the same high-level algorithm and scheduling assumptions;
- **S — strategy-conditioned:** common semantics with explicitly typed,
  mechanism-level choices;
- **N — native oracle:** an expert implementation designed for that target.

The ladder will be applied to three kernels selected to stress different
boundaries:

1. **Regular fused scan:** selection, transformation, and aggregation with
   predictable memory access.
2. **Standard columnar decode:** a narrowly defined, conformant Parquet integer
   decoding path with control and compaction pressure.
3. **Irregular hash probe:** data-dependent access and coordination that may
   resist shared scheduling.

The hardware matrix will include multiple SIMD widths, scalable-vector CPUs,
at least two GPU architectures, and at least one FPGA platform. Emulators and
simulators may extend correctness coverage but will not substitute for real
performance and energy measurements.

## Evaluation model

The primary quantitative measure is **native-normalised regret**: how far U and
S fall behind the best defensible N implementation on the same hardware.
Absolute throughput, latency, energy, compilation cost, code size, and resource
utilisation will also be published.

Portability cost will include:

- duplicated semantic rules and tests;
- number and locality of edits when a new target or semantic case is added;
- number of target-specific escape hatches;
- correctness obligations and unsupported combinations;
- sensitivity to compiler, data distribution, and hardware generation.

Native oracles will be independently reviewed, and all results will report
absolute values to prevent a weak oracle from making portable code look good.

## Five-year work programme

### WP1 — Theory, vocabulary, and preregistered evidence (months 1–12)

- Formalise semantics/schedule separation and native-normalised regret.
- Select exact kernel slices, hardware, toolchains, datasets, and native
  baselines after a focused state-of-the-art review.
- Define the typed strategy vocabulary and rules that prevent it from becoming
  an ISA-conditional catalogue.
- Publish experimental and negative-result protocols.

### WP2 — Cross-target experimental apparatus (months 6–24)

- Stabilise the CPU semantic and verification path.
- Build independent GPU and FPGA execution adapters with target experts.
- Create scalar/specification oracles, differential tests, provenance records,
  and reproducible hardware runners.
- Demonstrate end-to-end correctness on the regular scan before admitting more
  kernels.

### WP3 — Kernel frontier experiments (months 18–39)

- Complete the U/S/N ladder for all admitted target/kernel pairs.
- Run mechanism-level ablations and held-out-hardware tests.
- Measure performance, energy, resource use, semantic duplication, and change
  amplification under controlled toolchain and data variations.

### WP4 — Explanatory portability model (months 32–49)

- Infer which semantic and scheduling mechanisms predict regret.
- Test predictions on an unseen hardware generation or held-out kernel stage.
- Derive constructive rules for when to share, parameterise, or specialise.

### WP5 — Synthesis and open research product (months 45–60)

- Publish the portability-frontier theory, negative cases, benchmark corpus,
  implementations, and evidence packages.
- Validate the rules with external compiler, database, and architecture groups.
- Separate durable experimental infrastructure from conclusions tied to the
  measured hardware.

## Role and current readiness of `tslc`/`tsldata`

The existing compiler offers an unusually inspectable starting point: typed
catalogue data, explicit selection, semantic TSIL regions embedded in raw target
text, C++/Rust rendering, deterministic specialisation naming, generated value
tests, machine profiles, and coverage reports. It can operationalise the U/S/N
ladder first on CPU vector targets.

The proposal must state the current frontier honestly:

- TSIL is a recursive sequence of raw target text and recognised semantic
  regions, not a full target-language AST;
- the active product is a CPU SIMD wrapper compiler, not a heterogeneous
  accelerator compiler;
- declared CUDA source data is not an active validated CUDA backend;
- the oneAPI FPGA slice has no complete synthesis, board, or value-evidence
  flow;
- C++/Rust parity is incomplete for scalable vectors;
- published performance and productivity evidence is preliminary.

GPU/FPGA apparatus should be added only in slices justified by the research
experiment. A separate experimental package may be preferable where target
scheduling would violate the compiler's semantic boundary.

## Relationship to CHORYS

CHORYS supplies a credible RISC-V near-data and hardware/software co-design
context, including the team's stated TSL/RISC-V integration work. It reduces
apparatus risk but is not the ERC contribution. The ERC project must be
PI-driven and scientifically broader than CHORYS deliverables.

Because CHORYS remains active through 2028, maintain a result-by-result matrix
that separates pre-existing background, CHORYS results, and new ERC
foreground, together with people, costs, equipment, and outputs. Public
CORDIS metadata does not name TSL, so internal grant records must establish
the claimed relationship. Do not submit if that boundary cannot be audited or
if the same work would be charged twice.

## Why this fits ERC

| ERC characteristic | Project fit |
| --- | --- |
| Bottom-up frontier research | The proposal asks a fundamental systems question rather than responding to a prescribed application topic |
| High risk / high gain | There may be no useful shared middle layer; success would change how heterogeneous portability is designed and evaluated |
| PI-led coherent vision | One scientific thesis connects semantics, architecture, experimental methodology, and maintainability |
| Excellence as sole criterion | Claims are falsifiable, native-controlled, and designed to yield useful boundary results even when abstractions fail |
| Five-year scale | Real multi-architecture apparatus and held-out validation cannot be credible as a short software work package |

The compiler itself is preliminary work, not the claimed breakthrough. The
proposal's novelty must survive if reviewers regard TSL as replaceable
apparatus.

## Eligibility and call choice

For the ERC 2027 calls, the official pages state:

- **Starting Grant:** PhD defence normally 0–10 years before the applicable
  reference date; call opened 22 July 2026 and closes **14 October 2026**;
  up to EUR 1.5 million over five years, with specified additional funding.
- **Consolidator Grant:** PhD defence normally 5–15 years before the applicable
  reference date; call opens 24 September 2026 and closes **12 January 2027**;
  up to EUR 2 million over five years, with specified additional funding.

Extensions and exact reference dates are governed by the work programme. The
PI may be of any nationality but must conduct the project at an eligible host
in an EU Member State or Associated Country. Only one ERC proposal may be
submitted under the 2027 work programme. A research office should calculate
eligibility before choosing the call.

## Team and environment required

A credible application needs more than the present codebase:

- a PI with a strong, independent publication record spanning systems,
  compilers, databases, or architecture;
- senior or embedded GPU and FPGA expertise capable of producing defensible
  native oracles;
- guaranteed access to heterogeneous real hardware and calibrated energy
  measurement;
- research software engineering and reproducibility support;
- external domain collaborators for Parquet semantics and hash-join baselines;
- preliminary data demonstrating at least one non-trivial U/S/N gap.

## No-go conditions and immediate next steps

Do not submit in the current call if the PI window or host is unresolved, real
GPU/FPGA access is aspirational, or no native-reviewed pilot exists. An ERC
proposal assembled mainly around a software roadmap will not meet the intended
scientific bar.

Preparation should begin with:

1. formal PI eligibility and host confirmation;
2. a state-of-the-art matrix against SYCL, Kokkos, Alpaka, MLIR-based systems,
   vendor libraries, FPGA DSLs, and portability studies;
3. one regular-scan U/S/N pilot on a SIMD CPU and GPU, adding FPGA only with a
   target expert;
4. external review of native baselines and the semantics/schedule thesis;
5. a go/no-go decision early enough to protect the PI's single 2027 ERC
   submission opportunity.

## Official and local sources

- [ERC Starting Grant 2027](https://erc.europa.eu/apply-grant/starting-grant)
- [ERC Consolidator Grant 2027](https://erc.europa.eu/apply-grant/consolidator-grant)
- [ERC 2027 application changes](https://erc.europa.eu/news-events/news/applying-erc-grant-2027-competitions-what-you-need-know)
- [ERC 2027 work-programme announcement](https://erc.europa.eu/news-events/news/new-erc-work-programme-sets-out-2027-funding-opportunities)
- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [Local accelerator-portability frontier](../../accelerator-portability-frontier.md)
- [Local brainstorming and research framing](../../brainstorming.md)
- [Local RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Local primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Local benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
