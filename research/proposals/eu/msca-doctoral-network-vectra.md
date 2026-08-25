# VECTRA-DN: Verified, Energy-Aware, Cross-Architecture Data Systems

Instrument: **Marie Skłodowska-Curie Actions Doctoral Networks 2026**

Proposed form: **Standard Doctoral Network with strong industrial participation**

Status on 19 August 2026: **Open**

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
| DC1 | Capability model for RVV/SVE kernel portability | RISC-V IP or Arm/HPC partner |
| DC2 | Standards-compliant columnar decoding across vector lengths | Database/analytics company |
| DC3 | Generated semantic, differential, and metamorphic verification | Formal-methods or compiler group |
| DC4 | Evidence-aware compiler selection and lowering | Toolchain or vendor partner |
| DC5 | Near-data processing on open RISC-V accelerators | CHORYS hardware partner |
| DC6 | GPU/accelerator native-oracle comparison | Accelerator vendor or laboratory |
| DC7 | End-to-end energy attribution for data kernels | Measurement or HPC centre |
| DC8 | Workload and dataset representativeness | Cloud or vertical owner |
| DC9 | Sustainable research-software and evidence governance | Infrastructure or RSE partner |

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

## Showcase experiment: blind cross-site portability relay

The network needs evidence that a shared methodology transfers between people
and institutions, not only that one expert can tune several targets. The relay
therefore combines a technical portability test with a reproducibility and
training test.

### Relay task

The originating doctoral project publishes a typed semantic contract, generator
input, build manifest, oracle, and evidence schema—but no implementation for the
three hidden receiver targets—for a nullable analytics kernel:

`range filter -> compact qualifying row IDs -> gather float measure -> sum`

The public training corpus spans 1%, 10%, 50%, and 90% selectivity, 0% and 10%
nulls, clustered and random matches, and all vector-tail lengths. A coordinator
retains additional edge cases and distributes AVX-512, SVE, and RVV targets
among three receiving sites. Each site produces (S) a specialization through
the shared TSL method and (N) an independently reviewed native baseline. In a
second round, sites receive a semantic change—the gathered measure becomes
independently nullable and its nulls must be excluded from the sum while the
selected row IDs are preserved—and exchange targets. Assignment order is
balanced so the result is not just an order or familiarity effect.

All runs use containerized toolchains, pinned inputs, randomized variant order,
warm-up, repeated measurements, bitwise result hashes, and a replay by a second
site. If person-level observations are retained as research data, participation,
consent, and reporting are handled under the host institutions' ethics rules;
otherwise only aggregate artifact/process measures are kept.

### Measurements and decision rule

Record time and engineer-hours to first hidden-test pass, number of support
interventions, undocumented assumptions found, semantic and target-specific
lines changed, replay success, rows/s, joules/row, and S's regret relative to N.
The network lever is present if all three sites pass the hidden corpus from the
same semantic contract, a second site reproduces each result within the
pre-declared confidence interval, S stays within 20% of N in at least 75% of
benchmark cells, and the change request does not create semantic forks. It is
absent if success depends on the originating expert, evidence cannot be replayed,
or each target requires an independent semantic implementation. Thresholds are
pilot gates and negative results become training material rather than being
discarded.

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

## CHORYS connection and boundary

CHORYS can seed RISC-V platforms, use cases, supervisors, and industrial and
academic relationships. It does not make existing beneficiaries committed to
this network, and it cannot fund the same doctoral work. Before submission,
build a matrix of CHORYS background/results, new doctoral foreground,
supervisors, secondments, equipment, staff effort, costs, and outputs.

Each doctorate must retain an independent hypothesis and publication path;
the network may use CHORYS assets without turning its work plan into a
continuation of the CHORYS engineering backlog.

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
| CHORYS work and doctoral foreground overlap | Maintain the boundary matrix and remove any duplicate task, effort, cost, or output |

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
- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [Local accelerator-portability frontier](../../accelerator-portability-frontier.md)
- [Local compiler description](../../../tslc/DESCRIPTION.md)
- [Local coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Local benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
