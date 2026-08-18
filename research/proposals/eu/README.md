# EU funding landscape for `tslc` and `tsldata`

Assessment date: **8 August 2026**

This folder records a targeted screening of official European Commission and
European Research Council sources. It is not exhaustive legal or financial
advice, and the concepts are not submission-ready. Every deadline, budget, and
condition must be rechecked in the Funding & Tenders Portal for the exact topic
before submission.

## Result of the screening

There are credible EU routes at five different scales. The team's participation
in CHORYS makes two of them substantially more concrete: a small proof-of-market
action can valorise an achieved CHORYS result, while a large Cluster 4 RIA can
extend the research into the federated AI compute continuum. ERC and MSCA remain
independent bottom-up routes for frontier research and researcher training.

| Priority | Concept | Instrument and status on 8 August 2026 | Deadline | Realistic role |
| --- | --- | --- | --- | --- |
| 1 | [RVV-READY](chorys-proof-of-market-rvv-ready.md) | Cluster 4 Proof of Market 2027, forthcoming | Opens 22 Sep 2026; deadline 2 Feb 2027, 17:00 Brussels time | CHORYS SME/business lead with rights to the result; TSL team as technical/result-owner partner if appropriate |
| 2 | [RV-CONTINUUM](horizon-cl4-2027-data-03.md) | Horizon Cluster 4 DATA-03 RIA, forthcoming | Opens 17 Nov 2026; deadline 18 Mar 2027, 17:00 Brussels time | TSL/RISC-V work-package lead in a large consortium seeded by CHORYS |
| 3 | [PORTABILITY FRONTIER](erc-portability-frontier.md) | ERC Starting Grant 2027 open; Consolidator Grant 2027 forthcoming | Starting: 14 Oct 2026; Consolidator: 12 Jan 2027 | Lead PI, conditional on career window and record |
| 4 | [VLEN-PORT](msca-postdoctoral-vlen-port.md) | MSCA Postdoctoral Fellowships 2026 open | 9 Sep 2026, 17:00 CEST | Joint host and named fellow; 2026 is viable only if already paired |
| 5 | [VECTRA-DN](msca-doctoral-network-vectra.md) | MSCA Doctoral Networks 2026 open | 24 Nov 2026, 17:00 CET | Network coordinator or beneficiary with established European partners |

The ranking answers “what can build directly on CHORYS?”, not “which instrument
is scientifically most prestigious?” RVV-READY is the most direct bridge, but
only if the result is already achieved inside CHORYS, its commercialisation
rights are documented, and an eligible business-led consortium is ready.
RV-CONTINUUM is the stronger new research project, but it needs a large
consortium and a strict non-duplication boundary. The MSCA fellowship deadline
is closest, while PORTABILITY FRONTIER is the most ambitious
investigator-led science case.

## CHORYS starting position and evidence boundary

The public CORDIS record identifies CHORYS (grant **101189551**) as a Cluster 4
RIA running from **1 January 2025 to 31 December 2028**, coordinated by the
University of Copenhagen. It develops open and programmable accelerators for
near-data processing and asynchronous cloud data services, explicitly targets
RISC-V-based accelerator leadership, and names TU Dresden as a beneficiary. It
also lists Menta, Codasip, and Cyso as industrial participants alongside
Politecnico di Milano, TU Darmstadt, and INESC-ID.

The statement that the TSL/RISC-V integration is part of the team's CHORYS work
comes from the project team. The public CORDIS description does **not** name TSL
or this repository as a deliverable. The local repository independently shows a
credible technical baseline: a scalable RVV extension, runtime lane counts,
RISC-V cross-compilation and QEMU profiles, generated C++ support, and a
substantial July 2026 RVV implementation history. Before either CHORYS-derived
application is submitted, the team must map those assets to the grant's
background/results register, deliverables, owners, licences, and access rights.

## Shared technical assessment

`tslc` compiles declarative TSL sources through a typed catalogue, selection,
recursive TSIL scanning and lowering, backend rendering, and optional build and
value verification. `tsldata` supplies primitive, extension, type, test, and
benchmark source data. The repository is a useful reproducible experimental
platform:

- tracked coverage contains 111 primitive names and generated C++/Rust output
  over the profiles actually probed;
- machine-profile data includes fixed-width x86, Arm SVE, RISC-V Vector, Arm
  NEON, and WebAssembly routes;
- the RVV route is a typed scalable C++ target with RISC-V toolchain flags and
  functional QEMU profiles;
- generated tests and benchmark metadata can expose semantic and performance
  coverage rather than relying on hand-written examples.

The limitations matter just as much:

- coverage and emulation do not prove real-board performance, energy, or
  customer readiness;
- the current compiler does not provide a validated, production GPU/FPGA
  execution stack;
- CUDA is declared in source data but is not an active supported target-family
  path, and the oneAPI FPGA material is only a partial sized-vector/tool-gating
  slice without synthesis or board evidence;
- Rust does not currently support the scalable RVV extension;
- benchmark-shape coverage is incomplete.

The proposals therefore present TSL as preliminary apparatus and CHORYS as a
source of relevant project results and relationships. They do not claim that a
cross-accelerator commercial platform already exists.

Relevant local evidence:

- [`tslc` current architecture](../../../tslc/DESCRIPTION.md)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Target-family definition](../../../tsldata/detail/target_families.tsl)
- [RISC-V machine profile](../../../supplementary/buildsystem/machine_profiles.json)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
- [Accelerator-portability frontier](../../accelerator-portability-frontier.md)
- [Database research assessment](../../database-research-meta-study.md)

## Instrument-specific gates

### Cluster 4 Proof of Market

HORIZON-CL4-2027-01-MAT-PROD-49 explicitly seeks small consortia—particularly
spin-offs, startups, and SMEs—to explore the EU market potential of achieved
results from ongoing or completed Cluster 4 RIAs/IAs. The proposal must name
the source grant and acronym, show ownership or an owner commitment to negotiate fair, reasonable, and
non-discriminatory access to the relevant result and IPR, and
present a credible pathway to market with a business partner. The work
programme assigns EUR 5 million, estimates about EUR 0.20 million per project,
and expects about 25 projects.

This is an unusually literal fit for CHORYS, but it is not funding for more
open-ended compiler research. The bid needs a frozen product/result boundary,
customer discovery, user pilots, competitive and IP analysis, and a commercial
decision. Under the General Annex collaborative-action rule, plan for at least
three independent entities in three eligible countries unless the live portal
states an exception.

### Horizon Europe Cluster 4 DATA-03 as a CHORYS continuation

The 2027 RIA targets decentralised, federated, and sustainable AI data
processing across cloud, edge, HPC, and diverse hardware. It expects end-to-end
energy monitoring and at least two reproducible use cases in different domains,
progressing from approximately TRL 3 to TRL 6–7. The work programme allocates
EUR 35 million and expects about two projects at roughly EUR 17.5 million each.

CHORYS supplies a much better starting consortium and technology story than a
standalone compiler: open RISC-V near-data accelerators, a cloud deployment
route, hardware/software co-design, and the team's TSL portability layer.
RV-CONTINUUM must nevertheless create new foreground. Its new unit of work is
cross-site AI lifecycle federation, semantic evidence for placement across
RISC-V and other hardware, and end-to-end energy/data-movement optimisation in
two sectors. The TSL team can lead that bounded semantics-and-evidence work
package; it cannot substitute for the federated platform, security,
infrastructure, energy, and vertical partners required by the topic.

### ERC Starting or Consolidator Grant

ERC is bottom-up and uses scientific excellence as its sole evaluation
criterion. The 2027 Starting Grant window is 0–10 years from PhD defence and
the Consolidator window is 5–15 years, subject to the official extension rules.
A PI may submit only one proposal under the ERC 2027 work programme. The host
must be in an EU Member State or Associated Country. The choice between
Starting and Consolidator is determined by the named PI, not project size.

### MSCA Postdoctoral Fellowship

This is a joint researcher-host proposal built around mobility, training,
career development, and two-way knowledge transfer. The 2026 deadline is too
close for speculative matchmaking. A strong concept can instead be prepared
for the announced 2027 call if no mature pair exists now.

### MSCA Doctoral Network

At least three independent legal entities in three EU Member States or Horizon
Europe Associated Countries are required, including at least one in an EU
Member State. Every beneficiary recruits at least one doctoral candidate. A
competitive network needs an integrated research and training programme,
secondments, supervision, transferable skills, and durable academic/industrial
relationships—not several unrelated compiler PhDs under one title.

## Opportunities screened out or deferred

- **EIC Pathfinder Open 2026** closed on 12 May 2026. A 2027 call should not be
  planned against invented dates; reassess when the official 2027 EIC work
  programme is published.
- **HORIZON-CL4-2027-05-DATA-09**, on AI data-centre resource management, is an
  Innovation Action at high technology readiness focused on whole data-centre
  cooling, power, scheduling, and operations. The present project is too narrow
  and immature to anchor that proposal.
- **HORIZON-CL4-2027-04-DATA-08**, on demand-side 3C pilots, is a possible
  technology-provider route only if CHORYS has a deployment-ready component
  and a vertical-led telco-cloud-edge consortium. Its TRL 6–8, mandatory
  mobility pilot, and roughly EUR 19 million project scale make it weaker than
  DATA-03 today.
- **HORIZON-CL4-2027-01-MAT-PROD-61**, the Fast Track to Research and
  Innovation topic, is bounded by specified industrial partnership research
  agendas. TSL/RISC-V does not naturally fit those agendas and should not be
  forced into that call.
- No currently open Chips JU call was found that matches a general TSL/RISC-V
  continuation. Monitor the 2027 Chips JU work programme rather than relying on
  a closed automotive RISC-V topic or a restricted EuroHPC framework action.

## Recommended preparation sequence

1. Run a CHORYS result/IP workshop: identify the exact achieved TSL/RVV result,
   its owner, source-grant accounting, open-source and background licences, and
   who may commercialise it.
2. Ask the CHORYS industrial partners whether one will lead RVV-READY and which
   external customer problem it will test. Stop if there is no buyer hypothesis
   or rights path.
3. Give the CHORYS coordinator a two-page RV-CONTINUUM continuation note that
   marks every item as CHORYS baseline, reused background/result, or genuinely
   new DATA-03 foreground.
4. Recruit the missing DATA-03 capabilities: federated AI/cloud-edge-HPC
   coordination, end-to-end energy measurement, security/data governance, and
   two committed vertical owners.
5. Produce real-board RVV correctness, integration-time, performance, and
   energy evidence. QEMU remains a correctness tool, not market or performance
   evidence.
6. In parallel, identify the actual ERC PI or MSCA fellow and apply career and
   mobility rules before investing in those narratives.
7. Recheck live portal conditions, amendments, budgets, country/control
   restrictions, and forms immediately before submission.

## Official sources

- [Official CORDIS record for CHORYS, grant 101189551](https://cordis.europa.eu/project/id/101189551)
- [Official CORDIS record for the 2027 Proof of Market topic](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-01-MAT-PROD-49)
- [ERC Starting Grant](https://erc.europa.eu/apply-grant/starting-grant)
- [ERC Consolidator Grant](https://erc.europa.eu/apply-grant/consolidator-grant)
- [ERC 2027 application changes](https://erc.europa.eu/news-events/news/applying-erc-grant-2027-competitions-what-you-need-know)
- [MSCA Postdoctoral Fellowships 2026](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026)
- [MSCA Doctoral Networks 2026](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-doctoral-networks-2026)
- [Horizon Europe 2026–2027 Cluster 4 work programme](https://research-and-innovation.ec.europa.eu/document/download/87a8c19b-2643-49ec-8d07-37781ceb516e_en)
- [Official CORDIS record for HORIZON-CL4-2027-04-DATA-03](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-04-DATA-03/en)
- [Horizon Europe 2026–2027 General Annexes](https://research-and-innovation.ec.europa.eu/document/download/7318fc15-13a4-484b-a74e-7c403f88fee2_en)
- [Horizon Europe work-programme index](https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe/horizon-europe-work-programmes_en)
- [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/)
