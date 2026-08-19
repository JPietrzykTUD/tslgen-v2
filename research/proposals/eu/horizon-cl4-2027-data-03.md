# RV-CONTINUUM: Open and Verifiable Near-Data Processing Across the Federated AI Compute Continuum

Topic: **HORIZON-CL4-2027-04-DATA-03 — New approaches for decentralised,
federated and sustainable AI data processing**

Action type: **Research and Innovation Action**

Status on 19 August 2026: **Forthcoming; scheduled to open 17 November 2026**

Deadline: **18 March 2027, 17:00 Brussels time**

Indicative funding: **EUR 35 million total; around EUR 17.5 million per project
and approximately two projects**

Recommendation: **Develop as a CHORYS-seeded consortium proposal, with the TSL
team leading a bounded semantic-portability and evidence work package**

RV-CONTINUUM is a working title subject to consortium and trademark checks.

## Proposal summary

RV-CONTINUUM will extend Europe's open RISC-V near-data accelerator work into a
federated, sustainable AI data-processing continuum. Building on CHORYS
results, the project will let data preparation, feature extraction,
compression, filtering, training support, and inference support move across
edge, cloud, and HPC sites without silently changing semantics.

TSL will provide typed kernel contracts and generated conformance evidence for
RISC-V Vector and complementary architectures. A federated control plane will
combine this evidence with data locality, privacy, security, latency, and
calibrated energy measurements when placing work. Architecture partners retain
native schedules and optimisation. Two vertical owners will validate the
system in different sectors and advance integrated prototypes from roughly
TRL 3 to TRL 6–7.

The result is not another RISC-V backend. It is an evidence-aware method and
platform for using heterogeneous open accelerators safely and efficiently
across sites.

## CHORYS baseline

CHORYS, grant **101189551**, runs from January 2025 through December 2028. Its
public objectives cover:

- open and programmable near-data accelerators;
- asynchronous data services in the cloud;
- performance, energy-efficiency, and cost improvements;
- European leadership in RISC-V accelerators;
- hardware/software co-design.

Its coordinator, academic systems groups, RISC-V IP company, programmable
accelerator company, and cloud provider form a strong consortium seed. The team
states that TSL is used for RISC-V integration, although this is not named in
public CORDIS metadata and must be supported from internal project records.

## New foreground and non-duplication

| CHORYS baseline | RV-CONTINUUM foreground |
| --- | --- |
| Open near-data accelerators | Cross-site placement of AI data-processing stages across edge, cloud, and HPC |
| RISC-V hardware/software co-design | Typed semantic contracts and portable evidence across RVV and complementary architectures |
| Accelerator performance/energy demonstrations | End-to-end attribution including transfer, storage, retries, idle, and orchestration |
| Cloud-facing demonstrators | Federated policy, lineage, privacy/security, and multi-sector validation |
| TSL/RVV work attributed by the team to CHORYS | New evidence interfaces, placement algorithms, capability model, and cross-architecture experiments |

For every reused artefact, record whether it is background or a CHORYS result,
its owner, licence, access right, maturity, and availability date. Every new
task must produce distinct foreground. If the CHORYS description of action
already funds the central federation or semantic-evidence questions, narrow or
abandon this concept.

## Research questions

The central question is:

> Can a federated AI control plane use typed kernel semantics and reproducible
> hardware evidence to move data-processing work across heterogeneous sites
> while preserving results and reducing end-to-end energy and data movement?

Hypotheses:

- **Semantic mobility:** a bounded contract and generated differential evidence
  preserve observable behaviour across RVV vector lengths and complementary
  targets.
- **Evidence-aware placement:** placement using semantic coverage, data
  locality, and measured energy outperforms hardware-label-only scheduling
  without violating latency, privacy, or equivalence constraints.
- **Small capability model:** vector length, predication, memory, permutation,
  and acceleration capabilities predict valid placements and major performance
  cliffs better than ISA names alone.

Negative findings about where portability fails are valid outcomes.

## Objectives

1. Orchestrate selected AI data-lifecycle stages across edge, cloud, and HPC.
2. Define typed, testable semantics for a bounded kernel set.
3. Make CHORYS-derived RISC-V near-data capability a first-class execution path.
4. Include tested semantics and provenance in placement decisions.
5. Attribute energy across compute, transfer, storage, retries, and
   coordination.
6. Maintain lineage, privacy, security, and reproducible evidence.
7. Demonstrate results in at least two genuinely different sectors.

## Technical concept

### Semantic execution contracts

Each selected kernel has a signature, observable semantics, capability
requirements, error behaviour, and generated test obligations. An execution
record binds a semantic version to the implementation, compiler and flags,
hardware profile, runtime vector length, dataset class, and evidence status.

TSL does not represent full AI graphs or replace existing frameworks. It covers
low-level recurring data kernels where drift affects the distributed pipeline.

### Federated evidence plane

Placement considers:

- data location, movement volume, and sovereignty;
- exact semantic/test coverage for an implementation and platform;
- latency, availability, and security policy;
- energy with declared boundaries and uncertainty;
- expected performance and staging/recompilation cost.

Experiments compare label-only scheduling, energy/data-aware scheduling, and
the full semantics/evidence-aware strategy.

### Architecture-owned optimisation

RISC-V, CPU, GPU, and selected emerging-hardware partners own native
scheduling, memory movement, and expert baselines. For selected kernels, compare
a universal formulation, a capability-conditioned implementation, and an
architecture-native oracle.

### Sustainability and trust

Energy partners define calibration and system boundaries. Security and
data-governance partners define threat models, identity, policy enforcement,
privacy, and provenance. Optimisation may not trade away correctness,
security, privacy, or latency silently.

## Illustrative work packages

| WP | Lead profile | Output |
| --- | --- | --- |
| WP1: architecture and CHORYS handover | Coordinator/systems architect | Architecture, baseline/foreground register, KPIs, integration plan |
| WP2: federated control plane | Distributed AI/cloud-edge-HPC partner | Orchestration, lineage, policy, placement, consistency |
| WP3: typed kernels and evidence | **TSL team** | Contracts, capability model, target adapters, tests, evidence API |
| WP4: heterogeneous execution | RISC-V and architecture partners | Real-hardware integration, native schedules, expert baselines |
| WP5: energy | Measurement/LCA/HPC partner | Calibrated telemetry, attribution, uncertainty |
| WP6: trust | Security/data-governance partners | Threat model, controls, privacy-preserving flows |
| WP7: demonstrators | Two vertical owners | Integrated TRL 6–7 demonstrations |
| WP8: exploitation and standards | Industry/community partners | Adoption, standards, open-source and business plans |

These are role profiles, not commitments by named CHORYS partners.

## Candidate demonstrators

### Industrial condition monitoring

Factories keep high-rate sensor streams locally. Edge and near-data RISC-V
systems filter, compress, and extract features; cloud/HPC sites perform fleet
analysis and selected training. Evaluate connectivity, response time, movement,
semantic equivalence, and end-to-end energy.

### Privacy-sensitive life-science analytics

Institutions retain sensitive datasets while quality control, feature
extraction, and selected inference/training stages move among trusted sites.
Evaluate policy, lineage, privacy, reproducibility, movement, and semantic
equivalence. This requires specialist domain, legal, ethics, and security
partners.

The final domains must be selected by committed owners with data and deployment
sites.

## TSL readiness and limits

Existing assets:

- scalable RVV extension and runtime lane counts;
- RISC-V C++ cross-toolchain and QEMU profiles;
- typed compiler pipeline and generated tests;
- a corpus of 111 primitive names.

Limits:

- the tracked inventory does not probe the full RVV matrix;
- QEMU cannot establish real-hardware performance or energy;
- RVV is C++ only in source data;
- no compiler-owned federated runtime, energy model, or governance system;
- no production GPU/FPGA execution stack;
- generated coverage does not prove performance portability.

The TSL team should lead semantics, RVV evidence, and integration interfaces,
not the entire federation.

## Tender fit

| Expected element | Response |
| --- | --- |
| Cloud-edge-HPC decentralisation | Cross-site control plane covers the full continuum |
| Diverse hardware | CHORYS-seeded RVV plus complementary architectures |
| End-to-end sustainability | Compute, transfer, storage, retry, idle, and orchestration accounting |
| Quality, consistency, privacy, security, latency | Lineage/policy plane and dedicated trust work |
| Two domains | Two committed cross-sector demonstrators |
| Reproducibility | Versioned semantic, toolchain, hardware, dataset, and energy evidence |
| TRL progression | Existing prototypes integrated into operationally relevant demonstrations |

## Consortium gaps

Beyond the CHORYS seed, recruit:

- an experienced coordinator for a roughly EUR 17.5 million RIA;
- a mature federated AI/cloud-edge-HPC platform;
- complementary architecture and framework expertise;
- calibrated energy/LCA expertise;
- security, privacy, data governance, and responsible-AI expertise;
- two vertical owners with data, sites, prototypes, and adoption authority;
- standards, exploitation, and research-software ecosystem capability.

Check all country and control restrictions in the live topic and General
Annexes.

## No-go conditions

Do not bid without:

- a written CHORYS/new-foreground separation;
- an experienced coordinator;
- a mature federated platform;
- a defensible end-to-end energy method;
- two real vertical owners;
- real-board RVV evidence and access;
- sufficient new research beyond additional RVV primitives.

## Immediate actions

1. Discuss a DATA-03 successor with the CHORYS coordinator and exploitation
   lead.
2. Build the baseline/foreground and ownership matrix.
3. Draft a two-page TSL/RISC-V work-package offer with interfaces and KPIs.
4. Inventory consortium gaps and recruit them.
5. Ask verticals which kernels dominate movement, energy, or latency.
6. Run a real-board RVV pilot before the main writing phase.
7. Recheck topic amendments and restrictions when the call opens.

## Sources

- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [DATA-03 topic](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-04-DATA-03/en)
- [Cluster 4 work programme](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-7-digital-industry-and-space_horizon-2026-2027_en.pdf)
- [Horizon Europe General Annexes](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-15-general-annexes_horizon-2026-2027_en.pdf)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Target-family definition](../../../tsldata/detail/target_families.tsl)
- [Machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
