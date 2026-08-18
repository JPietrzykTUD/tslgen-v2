# VECTRA-DN: Verified, Energy-Aware, Cross-Architecture Data Systems

Instrument: **Marie Skłodowska-Curie Actions Doctoral Networks 2026**

Proposed form: **Standard Doctoral Network with strong industrial participation**

Status on 8 August 2026: **Open**

Deadline: **24 November 2026, 17:00 CET**

Call budget: **EUR 593.034 million**

Recommendation: **Develop only with an existing European training consortium and named recruiting beneficiaries**

The MSCA overview marks the timeline and budget as indicative/TBC. The live
Funding & Tenders topic is the controlling source and should be checked again
before submission.

## Proposal in one paragraph

VECTRA-DN will train a European cohort of researchers to make data-processing
software correct, efficient, and energy-aware across rapidly changing CPUs,
GPUs, and reconfigurable accelerators. The network's shared scientific question
is how typed semantic contracts, target-owned schedules, generated differential
tests, and calibrated measurements can replace the fragile choice between one
slow portable implementation and many unverified native versions. Interlocking
doctoral projects will cover scalable-vector algorithms, GPU/FPGA scheduling,
cross-language verification, energy evidence, standards-based columnar
decoding, and reproducible heterogeneous experimentation. Universities,
research centres, hardware/compiler organisations, data-engine companies, and
infrastructure providers will co-supervise and exchange candidates. `tslc` and
`tsldata` are one common teaching and experimentation platform, not the network's
product or mandatory architecture.

## Training need and scientific theme

New doctoral researchers in performance-critical data systems are often
trained in only one layer: algorithm, compiler, architecture, verification, or
application. Heterogeneous portability fails at the boundaries among those
layers. VECTRA-DN will train researchers to state semantic invariants, expose
target mechanisms, design fair native baselines, measure energy and
performance, and publish reproducible evidence.

The unifying research question is:

> How can a data-processing operation preserve one testable meaning across
> architecture classes while making scheduling, memory, and energy trade-offs
> explicit and empirically accountable?

This theme is broad enough for distinct doctorates but narrow enough for shared
methods, artefacts, datasets, and secondments.

## Research objectives

1. Create typed semantic contracts for selected data-processing operations and
   define where target strategy begins.
2. Develop scalable-vector, SIMT, and spatial implementations with independently
   reviewed native oracles.
3. Generate differential, metamorphic, and standards-conformance evidence
   across languages and targets.
4. Establish comparable performance and energy protocols from kernel through
   data movement and runtime.
5. Apply the methods to standards-based columnar processing and one AI/data
   pipeline domain.
6. Train candidates in open research software, reproducibility, responsible
   research, entrepreneurship, communication, and cross-sector collaboration.

## Illustrative doctoral projects

The final projects must be co-designed around the expertise and facilities of
actual beneficiaries. A coherent initial portfolio is:

| Project | Research focus | Natural secondment |
| --- | --- | --- |
| DC1 | Formal semantic contracts and compositional TSIL regions | Verification or language-tool partner |
| DC2 | Vector-length-agnostic algorithms for SVE and RVV | CPU/architecture vendor or HPC centre |
| DC3 | Generated differential and metamorphic tests across C++ and Rust | Compiler/toolchain organisation |
| DC4 | Semantics/schedule separation for SIMT data kernels | GPU or data-engine company |
| DC5 | Spatial scheduling and evidence for FPGA kernels | FPGA tool/vendor or applied lab |
| DC6 | Standards-compliant Parquet decoding across vector lengths | Database/analytics company |
| DC7 | End-to-end energy attribution for heterogeneous kernels | Measurement/LCA research group |
| DC8 | Reproducible hardware runners and citable evidence packages | Computing centre or research infrastructure |
| DC9 | Cost models for representation and target-strategy selection | Query-engine or compiler team |

This is an illustrative nine-project design, not a commitment. Every doctoral
project needs a distinct hypothesis, independent publication path, primary and
secondary supervision, dataset/hardware access, and concrete contribution to
at least one shared network demonstrator.

## Shared methodology and demonstrators

Candidates will use a common three-level experimental ladder:

- universal implementation;
- mechanism- or capability-conditioned implementation;
- expert native oracle.

They will share semantic references, adversarial datasets, measurement
protocols, and provenance requirements. Network demonstrators could include a
standard columnar decoding pipeline and a federated data-preparation pipeline,
chosen because they connect multiple doctoral projects without making every
thesis dependent on one codebase.

Primary research measures include correctness coverage, native-normalised
performance and energy regret, compiler/hardware sensitivity, target-specific
semantic duplication, and change amplification when a new operation or target
is added.

## Training programme

### Network schools

- semantics, type systems, and executable specifications;
- SIMD, scalable vectors, SIMT, FPGA pipelines, and memory systems;
- generated testing, formal and differential verification;
- experimental design, statistics, benchmarking, and energy measurement;
- databases, columnar formats, AI data pipelines, and standards;
- open science, FAIR research software, security, ethics, and reproducibility;
- project leadership, grant writing, innovation, IP/licensing, teaching, and
  public communication.

### Learning by mobility

Each candidate should have a secondment that supplies a capability unavailable
at the recruiting host: real hardware, a production data engine, compiler
internals, formal verification, calibrated energy measurement, or research
infrastructure operation. Exchanges must serve the individual research and
career plan rather than satisfy a mobility spreadsheet.

### Cohort integration

Cross-project replication pairs will reproduce another candidate's result on a
different target or toolchain. Annual “portability clinics” will invite external
users to bring a failing kernel and jointly classify whether the failure is
semantic, scheduling, toolchain, or measurement related. Candidates will also
maintain an evidence and negative-results catalogue.

## Role and limitations of `tslc`/`tsldata`

The repository provides an inspectable shared sandbox for typed primitives,
target profiles, recursive TSIL regions, deterministic C++/Rust generation,
generated tests, and coverage analysis. It is suitable for teaching how facts
move from source data to selected and lowered artefacts.

It must not become compulsory infrastructure for every thesis. GPU and FPGA
work currently exceeds the validated compiler product; those candidates need
expert partners and may use separate experimental adapters. The current source
corpus has incomplete backend and benchmark coverage. Those limitations are
valuable teaching material only when stated openly, not repackaged as completed
cross-architecture capability.

## Why this fits MSCA Doctoral Networks

| MSCA objective | VECTRA-DN response |
| --- | --- |
| High-quality doctoral training | Integrated technical, transferable-skill, open-science, and leadership curriculum |
| International, interdisciplinary, intersectoral mobility | Joint supervision and capability-driven secondments across universities, infrastructure, and industry |
| Excellent individual research | Distinct, falsifiable projects connected by a common methodology rather than a software backlog |
| Sustainable collaboration | Shared schools, demonstrators, evidence practices, supervision, and future curricula |
| Researcher employability | Training spans formal reasoning, performance engineering, data systems, hardware, reproducibility, and communication |

The network should remain a standard DN unless actual partners support the
additional Industrial or Joint Doctorate rules. In particular, an Industrial
Doctorate requires joint academic/non-academic supervision and candidates to
spend at least half their fellowship in the non-academic sector.

## Consortium and eligibility gates

The official 2026 preparation guidance requires at least three independent
legal entities in three different EU Member States or Horizon Europe Associated
Countries, with at least one beneficiary in an EU Member State. All
beneficiaries must recruit at least one doctoral candidate. Recruited
researchers must not hold a PhD at recruitment, may be of any nationality, must
be enrolled in a doctoral programme, and normally may not have resided or
carried out their main activity in the recruiting country for more than 12 of
the previous 36 months. Standard appointments may run 3–36 months.

A merely eligible consortium is not competitive. A plausible network needs:

- several academic beneficiaries with complementary supervision;
- at least two meaningful non-academic partners in compiler/hardware/data
  systems or research infrastructure;
- committed real CPU/GPU/FPGA access;
- a professional network manager and experienced MSCA coordinator;
- balanced candidate distribution, recruitment strategy, and contingency
  plans;
- explicit inclusion, supervision-quality, mental-health, open-science, ethics,
  IP, and career-development practices.

## Risks and no-go conditions

| Risk | Mitigation / gate |
| --- | --- |
| Projects are one compiler roadmap split nine ways | Require an independent hypothesis and external method/partner for every doctorate |
| Training is an afterthought | Co-design curriculum, supervision, secondments, and career plans before freezing research tasks |
| Hardware claims are aspirational | Obtain named facilities, access conditions, and expert supervisors in the proposal |
| Network is too technically homogeneous | Add database, verification, energy, infrastructure, and industry partners with real ownership |
| Coordination capacity is missing | Do not coordinate without experienced EU project support; join another DN as beneficiary instead |

## Immediate next steps

1. Circulate a two-page network concept to potential beneficiaries in at least
   three eligible countries.
2. Replace the illustrative DC table with projects co-authored by the proposed
   primary and secondary supervisors.
3. Map every candidate to recruitment host, doctoral enrolment, secondment,
   hardware/data, training outcomes, and contingency supervisor.
4. Name an experienced coordinator and begin the implementation, impact,
   recruitment, and supervision sections in parallel with the science.
5. Stop the 2026 attempt if core beneficiaries are not committed early enough
   for institutional and budget review.

## Official and local sources

- [MSCA Doctoral Networks 2026 call](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-doctoral-networks-2026)
- [MSCA announcement that the 2026 call opened](https://marie-sklodowska-curie-actions.ec.europa.eu/whats-new/news/doctoral-networks-2026-call-opens-for-submission)
- [Six steps to prepare an MSCA Doctoral Network](https://marie-sklodowska-curie-actions.ec.europa.eu/actions/doctoral-networks/6-steps-to-prepare-your-application-doctoral-networks-call)
- [Local accelerator-portability frontier](../../accelerator-portability-frontier.md)
- [Local compiler description](../../../tslc/DESCRIPTION.md)
- [Local coverage inventory](../../../coverage/primitive-coverage-inventory.md)
