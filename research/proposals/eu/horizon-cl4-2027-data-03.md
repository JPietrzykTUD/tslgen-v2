# RV-CONTINUUM: Open and Verifiable Near-Data Processing Across the Federated AI Compute Continuum

Topic: **HORIZON-CL4-2027-04-DATA-03 — New approaches for decentralized,
federated and sustainable AI data processing**

Action type: **Horizon Europe Research and Innovation Action (RIA)**

Status on 8 August 2026: **Forthcoming; scheduled to open 17 November 2026**

Deadline: **18 March 2027, 17:00 Brussels time**

Topic budget: **EUR 35 million; approximately two projects at EUR 17.5 million
each expected**

Recommendation: **Develop as a CHORYS-seeded consortium proposal, with the
TSL/RISC-V team leading a bounded semantic-portability and evidence work
package; do not coordinate from the compiler alone**

The acronym is a working title and requires consortium, availability, and
trademark checks.

## Proposal in one paragraph

RV-CONTINUUM will extend Europe's emerging open RISC-V near-data accelerator
stack into a federated, sustainable AI data-processing continuum. Building on
the open accelerator, cloud, and hardware/software co-design results of CHORYS,
the project will let data preparation, feature extraction, compression,
filtering, training support, and inference support move across edge, cloud, and
HPC sites without silently changing their semantics. TSL will provide typed
kernel contracts and generated conformance evidence for RISC-V Vector and other
hardware, while a federated control plane combines that evidence with data
locality, privacy, latency, and calibrated energy measurements when placing
work. Architecture partners will retain native schedules and optimisation. Two
committed vertical owners will validate the system in different sectors and
advance integrated prototypes from approximately TRL 3 to TRL 6–7. The result
is not another RISC-V backend: it is an evidence-aware method and platform for
using open heterogeneous accelerators safely and efficiently across sites.

## Why CHORYS changes the starting point

The official CORDIS record describes CHORYS (grant **101189551**) as a Cluster 4
RIA running from **1 January 2025 to 31 December 2028**. Its public objective is
to develop and demonstrate open, programmable accelerators for near-data
processing and asynchronous cloud data services, improving performance,
energy-efficiency, and cost. It explicitly aims to strengthen European
leadership in RISC-V accelerators and hardware/software co-design.

CORDIS names the University of Copenhagen as coordinator and TU Dresden,
Menta, Politecnico di Milano, TU Darmstadt, Codasip, Cyso, and INESC-ID as
beneficiaries. This is a much stronger technology and relationship base than a
standalone TSL proposal:

- an existing open-accelerator and near-data-processing research programme;
- RISC-V IP and accelerator expertise;
- programmable storage/controller and cloud-demonstration routes;
- academic hardware/software co-design and systems expertise;
- a team-supplied account that TSL is being used for RISC-V integration.

The last point is not stated on the public CORDIS page. The proposal must cite
the relevant CHORYS grant records and deliverables rather than infer that this
repository is an official project result from public metadata alone.

## Non-duplication and new scientific contribution

CHORYS remains active through the end of 2028, so a successor proposal may
overlap in calendar time. It cannot charge the same people, tasks, equipment,
integration, or deliverables twice. The consortium should maintain a
result-by-result table like this from the first concept note:

| CHORYS public baseline | New RV-CONTINUUM foreground |
| --- | --- |
| Open and programmable accelerators for near-data processing | Cross-site placement of AI data-processing stages over edge, cloud, and HPC |
| RISC-V accelerator and hardware/software co-design capability | Typed semantic contracts and evidence-aware execution across RISC-V and complementary architectures |
| Performance, energy-efficiency, and cost demonstrations | Calibrated end-to-end energy attribution including data transfer, storage, retries, and orchestration |
| Cloud-facing accelerator demonstrators | Federated multi-site control, data lineage, privacy/security policy, and reproducible cross-sector validation |
| TSL/RVV integration work attributed by the team to CHORYS, subject to confirmation in the grant records | New runtime evidence interfaces, federated placement methods, multi-architecture validation, and research hypotheses not in CHORYS |

Every reused artefact must be labelled as pre-existing background or a CHORYS
result, with owner, licence, access right, maturity, and the date it becomes
available. Every RV-CONTINUUM task must produce distinct foreground. If the
CHORYS description of action already funds the central federation and semantic
evidence questions below, this concept must be narrowed or abandoned.

## Central research question and hypotheses

The central question is:

> Can a federated AI control plane use typed kernel semantics and reproducible
> hardware evidence to move data-processing work across heterogeneous sites
> while preserving results and reducing end-to-end energy and data movement?

Three falsifiable hypotheses give the TSL/RISC-V work scientific content:

- **H1 — semantic mobility:** a bounded typed contract and generated
  differential evidence can preserve the observable behaviour of selected
  kernels across RVV vector lengths and complementary CPU/GPU targets.
- **H2 — evidence-aware placement:** placement that considers semantic
  coverage, data locality, and measured energy outperforms hardware-label-only
  scheduling on energy and transfer cost without violating latency, privacy, or
  result-equivalence constraints.
- **H3 — small capability model:** a compact vocabulary for vector length,
  predication, memory, permutation, and acceleration capabilities predicts
  valid placements and major performance cliffs better than ISA names alone.

A negative result is still useful if it identifies where semantic portability
or evidence transfer fails. The project must publish those limits rather than
hide them behind aggregate benchmark scores.

## Project objectives

1. **Federated AI data lifecycle:** orchestrate selected preprocessing,
   training-support, inference-support, and feedback stages across edge, cloud,
   and HPC while respecting locality, sovereignty, latency, and availability.
2. **Semantic kernel contracts:** define typed, testable meanings for a bounded
   set of data-intensive kernels independently of target scheduling and memory
   policy.
3. **Open RISC-V integration:** turn CHORYS-derived RISC-V near-data capability
   into a first-class execution and evidence path, then compare it with
   complementary conventional and emerging hardware.
4. **Evidence-aware placement:** include tested semantic coverage, toolchain and
   hardware provenance, performance uncertainty, and energy confidence in
   placement decisions.
5. **End-to-end sustainability:** attribute energy and relevant resource use to
   computation, data transfer, storage, retries, and lifecycle stages.
6. **Trustworthy federation:** maintain data/model/version lineage, privacy and
   security policy, and reproducible evidence across sites.
7. **Cross-sector validation:** demonstrate measurable benefits in at least two
   domains with distinct data, privacy, latency, and hardware constraints.

## Technical concept

### Semantic execution contract

For a bounded set of high-impact data kernels, the TSL work package will define
signatures, observable semantics, capability requirements, error behaviour,
and generated test obligations. An execution record will bind a kernel version
to its source semantics, selected implementation, compiler and flags, hardware
profile, runtime vector length, dataset class, and evidence status.

TSL will not represent full AI graphs or replace established frameworks. Its
scope is recurring low-level data work where silent semantic or performance
drift affects the distributed pipeline.

### Federated control and evidence plane

The consortium platform will describe datasets, models, policies, sites,
devices, telemetry, and kernel evidence. A placement decision will consider:

- data location, movement volume, and sovereignty constraints;
- semantic and test coverage for the exact implementation and platform;
- latency, availability, and security policy;
- measured energy with declared system boundaries and uncertainty;
- expected performance and the cost of staging or recompilation.

The research comparison will include a conventional scheduler that sees only
resource labels, an energy/data-locality scheduler, and the full
semantics-and-evidence-aware strategy.

### Architecture-owned execution

RISC-V, CPU, GPU, and any selected emerging-hardware partners will own native
scheduling, memory movement, and expert baselines. TSL supplies common semantics
and evidence interfaces, not one allegedly optimal implementation for every
device. Selected kernels will compare:

- a universal semantic formulation;
- a capability-conditioned implementation;
- an architecture-native oracle.

This makes “portable” measurable in correctness, performance regret,
integration effort, and change amplification rather than equivalent to
“compiles.”

### End-to-end energy, trust, and reproducibility

Energy partners will define calibrated measurement boundaries and uncertainty
protocols across device, host, network, storage, idle, and coordination costs.
Security and data-governance partners will define threat models, identity,
policy enforcement, provenance, and privacy-preserving data/model flows.

Evidence packages will be versioned and reproducible. Optimisation remains
multi-objective: an energy reduction cannot silently violate accuracy,
semantics, privacy, security, or latency.

## Illustrative work packages

| WP | Lead profile | Main output |
| --- | --- | --- |
| WP1: requirements, architecture, and CHORYS result handover | Experienced coordinator / systems architect | Reference architecture, baseline/foreground register, KPIs, ethics and integration plan |
| WP2: federated AI data-processing control plane | Cloud-edge-HPC and distributed-AI partners | Cross-site orchestration, lineage, policy, placement, and consistency services |
| WP3: typed kernels and generated evidence | **TSL/compiler team** | Semantic contracts, capability model, target adapters, differential tests, and evidence API |
| WP4: RISC-V near-data and heterogeneous execution | RISC-V/CHORYS technology partners plus other architecture experts | Real-hardware integrations, native schedules, and expert baselines |
| WP5: end-to-end energy measurement and optimisation | Energy/HPC/LCA measurement partner | Calibrated telemetry, attribution, uncertainty, and optimisation interface |
| WP6: privacy, security, and trustworthy federation | Cybersecurity and data-governance partners | Threat model, controls, provenance, and privacy-preserving flows |
| WP7: two cross-sector demonstrators | Vertical owners | Integrated TRL 6–7 demonstrations and reproducible evaluation |
| WP8: exploitation, standards, and open ecosystem | Industry/community partners | Adoption, interoperability, standardisation, open-source, and business plans |

The work packages are an architecture for discussion, not a claim that the
named CHORYS organisations have agreed to these roles.

## Illustrative use cases

Final use cases must be selected by committed data and deployment owners. They
must use the proposed federation and create genuinely different constraints.

### Federated industrial condition monitoring

Factories retain high-rate sensor streams locally. Edge and near-data RISC-V
systems filter, compress, and extract features; selected model training and
fleet analysis use cloud/HPC sites. Evaluation covers intermittent
connectivity, heterogeneous installed hardware, response time, data movement,
semantic equivalence, and end-to-end energy.

### Privacy-sensitive life-science analytics

Multiple institutions keep sensitive datasets under local control while
quality control, feature extraction, and selected inference or training stages
move between trusted edge, cloud, and HPC resources. Evaluation covers policy,
lineage, privacy, reproducibility, transfer volume, and semantic equivalence.
This route requires specialist legal, ethics, security, and domain partners; the
compiler team cannot own those claims.

A lower-regulatory second domain can replace life sciences if suitable partners
are unavailable, but the pair must remain complementary and in different
sectors.

## Role and readiness of `tslc` and `tsldata`

The local repository supports a credible WP3 baseline:

- `tsldata` declares RVV as a scalable extension with runtime lane counts and
  C++ RISC-V intrinsic composition;
- the target-family catalogue defines a RISC-V C++ toolchain and QEMU runner;
- machine profiles carry RV64 vector flags and a VLEN-128 QEMU profile;
- the corpus contains 111 primitive names overall, with generated build and
  value-evidence machinery;
- the compiler already separates typed semantics, selection, lowering,
  backend rendering, and verification.

The July 2026 history also records a focused RVV implementation and coverage
series. A submission baseline should rerun and archive the exact supported
primitive/type/profile matrix rather than relying on commit titles.

Current limitations define the new work and claims:

- no real-board RVV performance or energy campaign is recorded in the
  repository;
- QEMU supports correctness, not market, performance, or energy claims;
- RVV is currently C++ only and uses one declared LMUL/type family envelope;
- there is no compiler-owned federated runtime, energy model, data-governance
  system, or production GPU/FPGA stack;
- generated coverage does not prove native-normalised performance portability;
- benchmark-shape coverage is incomplete.

Accordingly, the TSL team should lead the semantic portability, RVV evidence,
and interfaces—not the whole federation or every accelerator backend.

## Why the concept fits DATA-03

| Expected topic element | RV-CONTINUUM response |
| --- | --- |
| Decentralised AI processing across cloud, edge, and HPC | Federated control plane places data-lifecycle stages across all three |
| Diverse hardware and new processing approaches | CHORYS-seeded RISC-V near-data execution plus conventional and selected complementary architectures |
| Sustainability and end-to-end energy | Calibrated attribution includes compute, transfer, storage, retries, idle, and orchestration |
| Data quality, consistency, privacy, security, and latency | Versioned lineage/policy plane plus dedicated security and governance work |
| At least two complementary domains | Industrial monitoring and life-science analytics, subject to committed owners |
| Reproducible results | Versioned semantic, toolchain, hardware, dataset, performance, and energy evidence packages |
| TRL 3 to TRL 6–7 | CHORYS and partner prototypes become integrated, multi-site demonstrations with new foreground |
| European open technology capacity | Open RISC-V accelerator and TSL assets are connected to a reusable European compute-continuum stack |

The fit is strong at consortium level. It becomes weak if the proposal is
reduced to “fund more RVV primitives,” because that addresses only a small
fraction of the topic.

## Consortium starting point and gaps

The public CHORYS consortium is a valuable seed, not a complete DATA-03
consortium and not a set of presumed commitments. Its coordinator, academic
systems groups, RISC-V IP company, programmable accelerator company, and cloud
provider can cover several starting roles.

The proposal still needs:

- an experienced coordinator able to manage a roughly EUR 17.5 million
  cross-sector RIA, whether from CHORYS or elsewhere;
- a mature federated AI/cloud-edge-HPC platform and integration team;
- complementary architecture and framework expertise beyond RVV;
- calibrated energy measurement and sustainability/LCA capability;
- data governance, cybersecurity, privacy, and responsible-AI expertise;
- two independent vertical owners with data, sites, starting prototypes, and
  post-project adoption authority;
- interoperability, standards, exploitation, and research-software community
  capacity.

Ordinary Horizon collaborative eligibility requires at least three independent
entities in three different countries, including one in a Member State and two
others in different Member States or Associated Countries. This proposal will
be much larger. DATA-03 also carries topic-specific country and control
restrictions for parts of the action; every beneficiary and associated partner
must be checked against the live portal and General Annexes.

## Main risks and no-go conditions

| Risk | Mitigation or no-go rule |
| --- | --- |
| Double funding or rebadging CHORYS | Maintain task, effort, cost, deliverable, and result separation reviewed by both coordinators and grants offices |
| The new project is RISC-V-led rather than outcome-led | Make federation, energy, trust, and cross-sector outcomes primary; treat RVV as an enabling architecture |
| Existing CHORYS consortium lacks a federated platform or verticals | Add proven partners before proposal writing; do not use nominal advisory partners |
| Hardware diversity becomes a device list | Select mechanisms and devices tied to use-case needs and native expert baselines |
| Energy claims compare incompatible sensors or boundaries | Use one calibration, boundary, uncertainty, and reporting protocol |
| Two demonstrators are nominal | Require data owners, starting prototypes, sites, KPIs, and adoption authority |
| Semantic layer duplicates ML frameworks | Limit it to high-value data kernels and integrate through stable adapters |
| TRL progression is implausible | Admit only components with documented starting maturity and integration plans |

Do not bid if there is no experienced coordinator, no mature federated
platform, no end-to-end energy partner, no two vertical owners, or no defensible
CHORYS/foreground separation.

## Immediate next steps

1. Ask the CHORYS coordinator and exploitation lead whether a DATA-03 successor
   is strategically desirable and compatible with the description of action.
2. Create a one-page baseline/foreground matrix for every proposed TSL/RVV and
   accelerator result, including owner, licence, maturity, and availability.
3. Draft a two-page WP3/WP4 offer with tasks, interfaces, person-month range,
   real-hardware contribution, risks, and measurable KPIs.
4. Inventory the CHORYS consortium against the missing roles above; recruit
   gaps rather than automatically copying the existing consortium.
5. Ask candidate verticals which data kernels dominate movement, energy,
   latency, or portability risk and obtain access to representative workloads.
6. Produce a real-board RVV pilot with semantic, performance, integration-time,
   and calibrated energy evidence before the main writing phase.
7. Recheck topic wording, amendments, country/control restrictions, forms, and
   budgets when the call opens.

## Official and local sources

- [Official CORDIS record for CHORYS, grant 101189551](https://cordis.europa.eu/project/id/101189551)
- [Horizon Europe 2026–2027 Cluster 4 work programme, topic DATA-03](https://research-and-innovation.ec.europa.eu/document/download/87a8c19b-2643-49ec-8d07-37781ceb516e_en)
- [Official CORDIS topic record for HORIZON-CL4-2027-04-DATA-03](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-04-DATA-03/en)
- [Horizon Europe 2026–2027 General Annexes](https://research-and-innovation.ec.europa.eu/document/download/7318fc15-13a4-484b-a74e-7c403f88fee2_en)
- [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/)
- [Local RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Local target-family definition](../../../tsldata/detail/target_families.tsl)
- [Local RISC-V machine profile](../../../supplementary/buildsystem/machine_profiles.json)
- [Local primitive-coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Local benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
- [Local accelerator-portability assessment](../../accelerator-portability-frontier.md)
