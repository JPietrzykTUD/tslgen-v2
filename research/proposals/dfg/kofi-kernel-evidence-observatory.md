# KoFI concept: Kernel Evidence Observatory plus VLEN-Decode

Programmes: **DFG KoFI combination of an Individual Research Grant and Research
Software Infrastructures**

Proposed duration: **Two coordinated three-year projects**

Submission status: **Conditional concept; contact DFG before submission**

Recommendation: **Do not submit until community demand and an operating partner are demonstrated**

## Proposal in one paragraph

This KoFI concept separates a scientific project from a community service while
making their interaction explicit. The research project, VLEN-Decode, studies
when standards-based columnar decoding remains efficient across scalable-vector
architectures. The infrastructure project establishes a Kernel Evidence
Observatory (KEO): a cross-site service through which research groups can
publish executable kernel semantics, build and correctness results, benchmark
protocols, hardware/toolchain provenance, and citable evidence packages. The
research project is an early demanding user, but KEO is governed and designed
for multiple compiler, systems, database, and HPC communities and remains
useful independently of VLEN-Decode or `tslc`. The concept fits KoFI only if a
national needs analysis shows that existing services do not already meet this
need and a credible infrastructure institution commits to long-term operation.

## Why two proposals are necessary

The DFG distinguishes knowledge-driven research from information
infrastructure. Combining them does not erase that boundary.

### Scientific work programme: VLEN-Decode

The Research Grant asks a falsifiable question about scalable-vector decoding.
It owns algorithms, native comparisons, hypotheses, papers, and the scientific
interpretation of experiments. Its detailed concept is in
[research-grant-vlen-decode.md](research-grant-vlen-decode.md).

### Infrastructure work programme: Kernel Evidence Observatory

The LIS proposal owns general enabling services:

- a versioned metadata model for semantic cases, generated artefacts,
  toolchains, target capabilities, runners, energy measurements, and results;
- validation and ingestion of evidence packages from more than one research
  software ecosystem;
- distributed execution-provider interfaces for institutional hardware, with
  explicit trust and reproducibility levels;
- discovery, comparison, citation, and export services;
- governance, contributor onboarding, training, preservation, security, and a
  sustainable operating model.

KEO must not own the scientific conclusion that one decoder design is better,
and VLEN-Decode must not quietly fund a general service. Each budget, milestone,
output, and staff role should be traceable to one side.

## Intended users and unmet need

The hypothesis behind KEO is that low-level research software commonly reports
performance without a durable link among semantic intent, exact generated
source, compiler and flags, hardware capabilities, correctness results, and
measurement protocol. Conventional source repositories, CI services, benchmark
dashboards, and archival repositories each preserve part of that chain.

That hypothesis is not yet evidence of national demand. Before proposal work,
the applicants should interview or workshop at least:

- compiler and programming-language researchers;
- database and data-processing systems groups;
- HPC and computer-architecture groups;
- institutional research software engineers and computing centres;
- relevant NFDI, EOSC, benchmark, artefact-evaluation, and software-heritage
  initiatives.

The needs analysis must identify current workflows, failed hand-offs, candidate
contributors, usage volumes, interoperability requirements, and existing
services that should be integrated rather than duplicated. Representative
users from more than one scientific community must test the prototype.

## Infrastructure phases and work programme

### WP-I1 — Needs, landscape, governance, and service design

- Publish the needs and environment analysis.
- Define user groups, governance, access rules, licences, data retention, and
  service-level expectations.
- Agree responsibilities between scientific users and the operating
  information-infrastructure institution.
- Specify interoperability with established software and data services.

Gate: stop if demand is local to the `tslc` team, if an existing service can
meet the need through a modest integration, or if no institution accepts
post-grant responsibility.

### WP-I2 — Technical prototype

- Implement the evidence-package schema and validation service.
- Connect at least two independent kernel/software ecosystems and multiple
  execution providers.
- Preserve immutable inputs and results while allowing corrected superseding
  records.
- Test discovery, citation, access control, and reproducible replay.

The service may reuse compiler-generated evidence, but compiler feature
development for VLEN-Decode belongs to the Research Grant.

### WP-I3 — Community operation and skills

- Run onboarding cohorts, consultations, and reproducibility clinics.
- Document how to contribute a new software ecosystem or execution site.
- Track adoption, successful independent replays, time-to-onboard, and user
  satisfaction rather than repository activity alone.
- Establish a transparent maintenance and financing plan.

### WP-I4 — Establishment and transfer

- Harden security, reliability, scaling, and preservation.
- Integrate metadata and identifiers with national and European services where
  justified.
- Transfer operational ownership and publish the post-funding roadmap.

## How `tslc` contributes without capturing the infrastructure

`tslc`/`tsldata` provides one well-instrumented starting ecosystem: typed
primitive and target facts, deterministic generation, C++/Rust artefacts,
generated tests, machine profiles, and explicit coverage reports. VLEN-Decode
provides a demanding first scientific user across real SVE and RVV hardware.

KEO cannot simply expose `tslc` internals as a hosted dashboard. Its public
evidence model must be neutral enough for a second and third software ecosystem
to contribute without adopting TSIL, TSL source formats, or compiler-specific
vocabulary. Conversely, compiler and source-data code must not import or
special-case the observatory.

## Fit to KoFI and Research Software Infrastructures

| Programme requirement | Proposed response |
| --- | --- |
| Closely linked research and information infrastructure | VLEN-Decode creates demanding evidence; KEO preserves and serves it alongside independent ecosystems |
| Separate, coordinated applications | Scientific hypotheses and infrastructure service milestones have distinct work programmes and budgets |
| Cross-location, community benefit | Multiple German institutions, execution sites, and research communities co-design and test the service |
| Technical, organisational, and skills tiers | Evidence services; governance and operations; training and onboarding |
| Needs and environment analysis | A mandatory pre-proposal workstream determines whether KEO should exist |
| Sustainability and integration | An infrastructure provider owns operation and integrates rather than duplicating established services |

The official Research Software Infrastructures guidance does not support a
proposal whose real objective is to develop or advance one research software
package. This concept is viable only when the general service and its users are
the infrastructure objective.

## Required consortium

At minimum, the preparation team needs:

- a DFG-eligible research PI for VLEN-Decode;
- a non-profit German computing centre, library, research data centre, or
  comparable information-infrastructure organisation willing to operate KEO;
- several independent compiler/systems/HPC/database user groups;
- providers of heterogeneous execution resources;
- expertise in metadata, software preservation, service security, training,
  and long-term governance;
- links to relevant national infrastructure initiatives.

Letters that merely promise future interest are weaker than documented current
workflows, contributed pilot data, and named operational responsibilities.

## Timing and no-go conditions

The Research Software Infrastructures rules set recurring deadlines on the
first Monday in March and last Monday in August. As assessed on 8 August 2026,
the next dates are 31 August 2026 and 1 March 2027. The DFG requires prior
contact for KoFI proposals. The August submission should be ruled out unless
the entire community and governance foundation already exists.

Do not submit if any of the following remains true:

- the only committed user is the `tslc` project;
- no independent infrastructure operator owns sustainability;
- the needs analysis cannot distinguish KEO from existing CI, archival, or
  benchmark services;
- infrastructure staff are actually budgeted to answer VLEN-Decode's research
  questions;
- no second software ecosystem can create and replay an evidence package.

## Preparation sequence

1. Send a two-page separation-of-work note to the DFG KoFI and LIS contacts.
2. Run a documented national needs and service-landscape workshop.
3. Recruit the operating institution and independent pilot ecosystems.
4. Prototype the neutral evidence package outside the compiler boundary.
5. Develop separate impact, sustainability, budget, and risk cases for the two
   proposals, then cross-reference only their real dependencies.

## Official and local sources

- [DFG KoFI announcement, 15 June 2026](https://www.dfg.de/en/news/news-topics/announcements-proposals/2026/ifr-26-39)
- [DFG research-software support options](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [DFG Research Software Infrastructures](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/infrastructure/lis/funding-opportunities/research-software-infrastructures)
- [Research Software Infrastructures guidelines (form 12.22)](https://www.dfg.de/resource/blob/333366/12-22-en.pdf)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [VLEN-Decode concept](research-grant-vlen-decode.md)
- [Local compiler description](../../../tslc/DESCRIPTION.md)
- [Local primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
