# VLEN-Decode: Vector-Length-Aware Decoding of Standard Columnar Data

Programme: **DFG Research Grants Programme**

Proposed duration: **36 months**

Submission status: **Draft concept; proposals may be submitted at any time**

Recommendation: **Proceed to a real-hardware pilot and full prior-art review**

## Proposal in one paragraph

Modern CPUs increasingly expose scalable vector instruction sets such as Arm
SVE and RISC-V Vector, where vector length is an implementation choice rather
than a compile-time constant. VLEN-Decode will determine whether one semantic
decomposition of standards-compliant columnar decoding can remain efficient
across vector lengths and architectures, or whether high performance
fundamentally requires capability- and vector-length-conditioned stages. It
will implement and compare universal, capability-conditioned, and native-oracle
decoders for carefully selected Parquet encodings on real SVE, RVV, and
fixed-width SIMD systems. A scalar executable specification, generated
differential tests, and a reproducible benchmark corpus will separate semantic
correctness from scheduling choices. The project aims to produce empirical and
methodological knowledge about scalable-vector algorithm design, not another
format library.

## Scientific problem

Most vectorized decoders are designed around a fixed lane count and a familiar
set of shuffle, mask, gather, compress, and memory operations. Scalable-vector
ISAs replace that assumption with predication and a runtime vector length.
Source-level portability is possible, but it is not known when the resulting
algorithm remains close to a target-specific oracle or where it develops
systematic performance cliffs.

The central question is:

> Can a single vector-length-agnostic decomposition of standard columnar
> decoding remain competitive across SVE and RVV, and, where it cannot, what is
> the smallest capability model needed to recover performance without
> duplicating semantics?

Subquestions are:

1. Which decoding stages are invariant under vector length, and which depend on
   lane topology, predicate operations, or memory capabilities?
2. How do data distribution, selectivity, null density, encoded run length,
   vector length, and compiler interact to create performance cliffs?
3. Is a small, explicit strategy vocabulary sufficient, or are native
   per-target algorithms unavoidable?
4. What is the cost of portability in throughput, latency, energy, source
   duplication, and change amplification?

## Hypotheses and falsification

- **H1:** The semantic stages of selected standard decoders can be shared
  across fixed and scalable vectors while target-specific scheduling remains
  isolated in a small number of typed strategies.
- **H2:** Runtime vector length alone is not a sufficient selection feature;
  predicate, permute, compaction, and memory capabilities explain a material
  portion of the observed performance variation.
- **H3:** Capability-conditioned implementations reduce native-normalized
  performance regret without approaching the maintenance cost of independent
  native implementations.

The project succeeds scientifically even if H1 fails: a well-controlled map of
where semantic portability breaks is a useful negative result. It should stop
or be redesigned if the pilot finds no stable standards-compliant kernel, no
measurable difference among the three implementation levels, or prior work
already answers the same question on comparable hardware.

## Experimental design

The initial format slice should remain narrow. A defensible starting point is
fixed-width integer data using Parquet's plain and one encoded path selected
after the pilot, including null handling and malformed-input cases required by
the standard. Additional encodings are admitted only when they test a distinct
algorithmic mechanism.

Each kernel will have three levels:

- **U — universal:** one vector-length-agnostic formulation;
- **S — strategy-conditioned:** shared semantics with a small declared set of
  capability-dependent stages;
- **N — native oracle:** an expert implementation for each measured target.

All levels will be checked against a scalar reference and shared adversarial
test corpus. Measurements will cover multiple real SVE and RVV vector lengths,
a fixed-width AVX-class baseline, at least two toolchain versions where
practical, and controlled datasets spanning the relevant distributions. QEMU
may be used for functional coverage, never as performance evidence.

Primary outcomes are native-normalized throughput and energy regret,
tail-latency distributions, code and semantic duplication, and the number of
places changed when adding a target or encoding rule. The statistical protocol,
warm-up, repetitions, clock controls, compiler flags, and exclusion rules will
be preregistered after the pilot.

## Work programme

### WP1 — Specification, prior art, and baselines (months 1–6)

- Freeze the selected Parquet semantics and construct the scalar executable
  specification.
- Complete a systematic comparison with current Arrow/Parquet, database,
  compiler, SVE, and RVV decoding work.
- Establish adversarial and property-based inputs, fixed-width baselines, and
  access to reproducible SVE/RVV systems.
- Pre-register the performance and correctness protocol.

Milestone: a reproducible pilot showing a non-trivial portability question on
at least one SVE and one RVV machine.

### WP2 — Universal and strategy-conditioned decoders (months 5–16)

- Express shared decoder semantics and the U implementation.
- Add only the typed operations and test shapes needed for the selected
  semantics.
- Derive the minimal candidate strategy vocabulary from observed mechanisms,
  not from ISA names.
- Generate differential and malformed-input tests across target profiles.

Milestone: semantic equivalence across all supported vector lengths and input
classes.

### WP3 — Native oracles and controlled experiments (months 12–26)

- Implement or adapt expert N baselines for every measured target.
- Measure throughput, latency, energy, code size, compiler sensitivity, and
  performance counters.
- Use factorial and ablation experiments to distinguish vector-length effects
  from individual capabilities and implementation choices.

Milestone: a public evidence package sufficient to reproduce every reported
comparison.

### WP4 — Portability model and transfer (months 23–36)

- Test whether the inferred capability model predicts unseen vector lengths or
  a held-out machine.
- Quantify the maintenance cost and change amplification of U, S, and N.
- Validate transfer on one additional decoding stage only if it probes the same
  theory.
- Publish algorithms, negative results, corpus, and reproducibility artefacts.

## Role of `tslc` and `tsldata`

The repository is experimental apparatus:

- `tsldata` can hold typed primitive semantics, extension capabilities, tests,
  and benchmark metadata.
- `tslc` can select and lower specialisations, generate C++ and Rust artefacts,
  and produce deterministic correctness evidence.
- Existing machine profiles already describe fixed-width x86, SVE, and RVV
  environments, including emulated correctness routes.

The starting point must not be overstated. The repository now has a broad RVV
source and build-evidence path, but scalable-vector performance still needs
real-hardware evidence; Rust does not currently cover SVE or RVV, and
benchmark-shape coverage is incomplete. Any compiler changes must remain
general semantic capabilities rather than Parquet-specific string rewrites.

## Relationship to CHORYS and the double-funding boundary

CHORYS (grant **101189551**) materially strengthens the feasibility case. Its
public scope covers open and programmable near-data accelerators, RISC-V ISA
extensions, data-intensive applications, and hardware/software co-design. The
project team states that TSL is used for its RISC-V integration, and the local
repository shows a scalable RVV target, toolchain and QEMU profiles, and a
focused implementation history.

That evidence should enter VLEN-Decode as preliminary work, but the public
CORDIS description does not name TSL and the EU project remains active through
31 December 2028. The DFG proposal must therefore obtain the relevant CHORYS
grant records and draw an explicit boundary:

| CHORYS contribution or result | New DFG research |
| --- | --- |
| Engineering integration of RISC-V through TSL, to the extent recorded in the CHORYS description of action and results | Causal study of how runtime vector length and capabilities affect standards-compliant columnar decoding |
| Open RISC-V near-data accelerator and cloud demonstrator context | Controlled cross-ISA comparison of RVV, SVE, and fixed-width systems on real hardware |
| Existing primitive implementations, build tests, and platform access | New Parquet reference semantics, adversarial corpus, U/S/N algorithms, preregistered experiments, and held-out-machine tests |
| CHORYS-funded staff effort, equipment, tasks, and deliverables | Separately costed DFG personnel, experiments, outputs, and publications |

The DFG project may reuse background and CHORYS results with the correct rights
and acknowledgement; it may not charge the same work twice. Before submission,
the PI, CHORYS coordinator, and both institutions' grants offices should review
a task/personnel/cost/result matrix. If CHORYS already funds the Parquet
decoder experiments or the same central hypotheses, VLEN-Decode must be
reframed or not submitted.

## Why this fits the DFG Research Grants Programme

| DFG characteristic | Project fit |
| --- | --- |
| Knowledge-driven project in any discipline | The proposal asks a general computer-architecture and data-systems question about scalable-vector algorithms |
| Clearly defined topic and duration | One standards-based decoder family, three implementation levels, controlled hardware matrix, 36 months |
| Research quality and originality | Falsifiable comparison of universal, capability-conditioned, and native designs with a held-out-target test |
| Applicant's preliminary work | The typed compiler, source corpus, generated tests, and coverage inventories reduce apparatus risk without predetermining the result |
| Feasibility | A six-month pilot milestone and bounded format slice prevent an open-ended backend project |

The DFG explicitly allows research software to be funded as part of a regular
research project when it is required to address the scientific question. That
is the appropriate framing here; maintaining the compiler as infrastructure is
not the primary objective.

## Team and resources to secure

A plausible core is a DFG-eligible PI, one doctoral or postdoctoral researcher
with low-level systems expertise, and student support for corpus and experiment
automation. The proposal should request or document:

- scheduled access to at least one real SVE and one real RVV platform, with a
  plan for vector-length diversity;
- independent expertise in Parquet conformance and database execution;
- energy measurement that is comparable across machines, or a narrower claim
  if such measurement cannot be calibrated;
- archiving, open-access, travel, and reproducibility costs under the
  appropriate DFG modules.

Exact staffing and costs must be developed under the current Basic Module rules
for the host institution.

## Main risks and mitigations

| Risk | Mitigation or decision gate |
| --- | --- |
| Hardware availability is too narrow | Obtain written access before submission; do not use emulation for performance claims |
| Format work overwhelms the research | Freeze one narrow, standards-compliant slice and reuse established parsers around the measured kernels |
| “Universal” is a weak baseline | Require expert-reviewed native oracles and publish absolute as well as normalized results |
| Compiler engineering dominates | Admit a compiler feature only when it expresses reusable semantics needed by an experiment |
| Prior art has answered the question | Complete the focused review and pilot before committing to a full proposal |

## Immediate preparation tasks

1. Name the PI and verify DFG eligibility with the host research office.
2. Secure SVE/RVV hardware access and select exact CPU implementations and
   toolchains.
3. Implement the smallest plain-decoding U/N pilot and measure whether a
   meaningful gap exists.
4. Complete a standards and prior-art matrix, including current Arrow/Parquet
   implementations and scalable-vector publications.
5. Ask the DFG programme contact whether any planned staffing or equipment
   creates a module-specific issue.

## Official and local sources

- [Official CORDIS record for CHORYS, grant 101189551](https://cordis.europa.eu/project/id/101189551)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [DFG Research Grant guidelines (form 50.01)](https://www.dfg.de/resource/blob/168072/50-01-en.pdf)
- [DFG eligibility guidance](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [DFG support options for research software](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [Local database research assessment](../../database-research-meta-study.md)
- [Local benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
- [Local machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
