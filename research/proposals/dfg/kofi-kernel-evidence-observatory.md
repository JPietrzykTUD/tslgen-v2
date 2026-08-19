# KoFI concept: Kernel Evidence Observatory plus VLEN-Decode

Programmes: **DFG Research Grants Programme plus Research Software
Infrastructures under KoFI**

Recommendation: **Conditional; contact the DFG before submission and first
demonstrate cross-institution demand**

## Proposal summary

This concept coordinates two legally and scientifically distinct proposals.

The Research Grant funds VLEN-Decode: a focused study of scalable-vector
columnar-decoding algorithms. The Research Software Infrastructures proposal
establishes a community-owned Kernel Evidence Observatory that preserves
machine-readable semantic, build, correctness, performance, energy, toolchain,
and hardware evidence for reusable data-processing kernels.

The observatory is not a hosted copy of `tslc`. It accepts evidence from
multiple generators, libraries, compilers, architectures, and research groups;
defines common metadata and quality levels; supports reproducible comparison;
and establishes governance, curation, training, and sustainability.

## Why two proposals are necessary

| Scientific Research Grant | Infrastructure proposal |
| --- | --- |
| Asks hypotheses about scalable-vector decoding | Provides durable services for multiple research communities |
| Owns algorithms, experiments, and publications | Owns schemas, ingestion, curation, access, governance, and training |
| May produce evidence records | Must not predetermine scientific conclusions |
| Has a bounded three-year research question | Must establish broader and durable community value |

Shared personnel, tasks, and costs must be separable and justified. The
observatory cannot exist merely to support the companion project.

## Community need to establish

Before submission, interview and workshop representatives from:

- database and data-processing systems;
- compiler and performance engineering;
- SIMD/RISC-V/Arm architecture research;
- research software engineering and reproducibility;
- hardware and toolchain providers;
- repositories or infrastructures that might host or integrate the service.

The needs analysis must show that existing benchmark repositories, artefact
archives, CI systems, and performance databases do not already provide the
required combination. It must record current workflows, failed hand-offs,
candidate contributors, plausible usage volumes, interoperability
requirements, and services that should be integrated instead of duplicated.
Representative users from more than one scientific community must test the
prototype.

## Service concept

The observatory would manage:

1. typed kernel identity and observable semantics;
2. implementation and generator provenance;
3. compiler, flags, target, runtime, and hardware metadata;
4. build and correctness evidence with explicit coverage;
5. benchmark protocols, datasets, repetitions, uncertainty, and exclusions;
6. energy boundaries and sensor/calibration metadata;
7. comparable quality levels rather than one misleading score;
8. versioned, citable evidence packages;
9. governance, contribution review, retention, and withdrawal processes.

TSL is one producer and early design partner. It must not define the
infrastructure's private ontology or control admissibility.

## Infrastructure work programme

### Phase I — Needs, landscape, and governance

- conduct interviews and workshops;
- inventory existing services and standards;
- define users, use cases, gaps, and success criteria;
- establish independent governance and an advisory structure;
- choose a durable host/operator.

Gate: stop if demand is local to the TSL team, if an existing service can meet
the need through modest integration, or if no institution accepts post-grant
operational responsibility.

### Phase II — Technical prototype

- define open schemas and APIs;
- ingest evidence from TSL and at least two independent producers;
- support validation, versioning, citation, search, and export;
- demonstrate deterministic records and explicit uncertainty;
- implement access, security, and preservation policies.

### Phase III — Community operation and skills

- run contribution calls and onboarding;
- provide training and reusable workflows;
- measure adoption, successful independent replays, time-to-onboard,
  interoperability, curation cost, and user satisfaction;
- establish cross-site maintainer and reviewer roles.

### Phase IV — Establishment and transfer

- migrate to the long-term operator;
- formalise governance, funding, and service levels;
- integrate with relevant repositories/infrastructures;
- publish sustainability and decommissioning plans.

## Scientific companion: VLEN-Decode

The companion Research Grant supplies one demanding early use case but retains
its own hypotheses, methods, staffing, and publications. Its outputs can test
whether the observatory represents vector lengths, capabilities, semantic
coverage, native baselines, and energy uncertainty without customising the
service around one project.

## Fit to the programmes

| Requirement | Response |
| --- | --- |
| Coordinated research and infrastructure | Two distinct proposals with explicit interfaces |
| Cross-site community benefit | Multiple producer/consumer communities and institutions |
| Existing landscape considered | Formal service and gap inventory |
| Technical/organisational/skills dimensions | Open schemas/APIs, governance/operation, and training |
| Sustainability | Named operator, service model, governance, and exit plan |
| No single-project capture | Multiple independent evidence producers and governing stakeholders |

## Required consortium

At minimum, preparation requires:

- a DFG-eligible research PI for VLEN-Decode;
- a non-profit German computing centre, library, research data centre, or
  comparable information-infrastructure organisation willing to operate the
  observatory;
- several independent compiler, systems, HPC, and database user groups;
- providers of heterogeneous execution resources;
- expertise in metadata, software preservation, service security, training,
  and long-term governance;
- links to relevant national infrastructure initiatives.

Documented workflows, contributed pilot data, and named operational
responsibilities are stronger evidence than generic letters of interest.

## No-go conditions

Do not submit if:

- prospective users cannot articulate needs beyond the TSL team;
- no long-term host will own operations;
- existing infrastructure already covers the need;
- only aggregate benchmark numbers can be contributed;
- governance remains controlled by one project;
- the scientific and infrastructure personnel/costs cannot be separated;
- the DFG programme contact advises a different route.

## Preparation sequence

1. Contact the DFG KoFI and LIS programme contacts.
2. Run a national needs workshop and structured interviews.
3. Produce an existing-services and standards matrix.
4. Recruit a durable infrastructure operator and independent governance.
5. Prototype ingestion from TSL and two unrelated producers.
6. Define interfaces to VLEN-Decode without coupling review outcomes.
7. Choose a realistic deadline only after these gates pass.

## Sources

- [KoFI announcement](https://www.dfg.de/en/news/news-topics/announcements-proposals/2026/ifr-26-39)
- [Research Software Infrastructures](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/infrastructure/lis/funding-opportunities/research-software-infrastructures)
- [Research Software Infrastructures guidelines](https://www.dfg.de/resource/blob/333366/12-22-en.pdf)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [Research-software support options](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [VLEN-Decode concept](research-grant-vlen-decode.md)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
