# EU funding landscape for `tslc` and `tsldata`

Assessment date: **19 August 2026**

This directory contains proposal concepts based on official EU sources and the
current repository. They are not submission-ready applications. Dates,
eligibility, budgets, security conditions, and templates must be rechecked in
the Funding & Tenders Portal before submission.

## Recommended routes

| Priority | Concept | Instrument | Deadline | Recommended role |
| --- | --- | --- | --- | --- |
| 1 | [RVV-READY](chorys-proof-of-market-rvv-ready.md) | HORIZON-CL4-2027-01-MAT-PROD-49, Proof of Market IA | 2 February 2027 | CHORYS business/SME lead; TSL team supplies the result and evidence |
| 2 | [RV-CONTINUUM](horizon-cl4-2027-data-03.md) | HORIZON-CL4-2027-04-DATA-03 RIA | 18 March 2027 | TSL/RISC-V work-package lead in a large CHORYS-seeded consortium |
| 3 | [PORTABILITY FRONTIER](erc-portability-frontier.md) | ERC Starting or Consolidator Grant | Starting: 14 October 2026; Consolidator: 12 January 2027 | Eligible PI and host |
| 4 | [VLEN-PORT](msca-postdoctoral-vlen-port.md) | MSCA Postdoctoral Fellowships 2026 | 9 September 2026 | Named eligible fellow plus host; viable only if already paired |
| 5 | [VECTRA-DN](msca-doctoral-network-vectra.md) | MSCA Doctoral Networks 2026 | 24 November 2026 | Beneficiary or coordinator in an established network |

The MSCA overview pages currently mark the 2026 dates and budgets as
indicative/TBC. The dates above are planning dates, not a substitute for the
live Funding & Tenders topic and published call documents.

The ranking answers which route can build most directly on CHORYS. It does not
rank scientific prestige. RVV-READY is the most literal continuation because
the call funds market validation of achieved Cluster 4 results. RV-CONTINUUM is
the strongest large research opportunity, but it needs substantial new
foreground and a much broader consortium.

## CHORYS starting point

The official CORDIS record identifies CHORYS, grant **101189551**, as a Cluster
4 RIA running from **1 January 2025 to 31 December 2028**. It develops open and
programmable accelerators for near-data processing and asynchronous cloud data
services. Its stated goals include performance, energy-efficiency, cost, and
European leadership in RISC-V accelerators and hardware/software co-design.

CORDIS lists the University of Copenhagen as coordinator and TU Dresden,
Menta, Politecnico di Milano, TU Darmstadt, Codasip, Cyso, and INESC-ID as
beneficiaries. This provides a credible consortium and exploitation seed.

The team states that TSL-to-RISC-V integration is CHORYS work. Public CORDIS
metadata does not name TSL or this repository as a deliverable. Any proposal
must therefore trace the exact TSL/RVV asset through CHORYS tasks, deliverables,
result records, owners, licences, and access rights.

## Technical baseline

The current repository supports a credible preliminary-work claim:

- `tsldata` declares RVV as a scalable C++ extension with runtime lane counts;
- target-family data defines a RISC-V cross-compilation and QEMU route;
- machine profiles use RV64 vector flags and an RVV 1.0 QEMU configuration;
- the source corpus contains 111 primitive names;
- `tslc` separates typed semantics, selection, lowering, backend rendering,
  and generated verification.

Important limits:

- the tracked coverage inventory probes generic/x86 profiles, not the full RVV
  matrix;
- QEMU establishes functional evidence, not real-board performance or energy;
- RVV is C++ only in the declared extension;
- the repository does not itself provide a federated AI platform, data
  governance system, or production GPU/FPGA stack;
- market demand and commercialisation rights are not software test results.

## Route-specific gates

### RVV-READY: Proof of Market

The topic explicitly accepts achieved results from ongoing or completed Cluster
4 RIAs/IAs. It expects small consortia, especially startups and SMEs, to test
commercial potential. The proposal must name the source project, establish
ownership or an owner commitment to negotiate access, include a business
partner, and define a credible path to market.

The work programme indicates EUR 5 million total, around EUR 0.20 million per
project, and about 25 projects. This scale supports customer discovery,
productisation, rights work, and a few external pilots—not a general compiler
roadmap.

### RV-CONTINUUM: DATA-03

DATA-03 targets decentralised, federated, sustainable AI data processing across
cloud, edge, HPC, and diverse hardware. It expects end-to-end energy monitoring,
data consistency, privacy and security, and at least two reproducible use cases
in different domains. The expected progression is roughly TRL 3 to TRL 6–7.

The work programme indicates EUR 35 million total, around EUR 17.5 million per
project, and two projects. CHORYS supplies open RISC-V near-data assets and
relationships; the new project must add multi-site federation,
semantics-aware placement, energy attribution, security, and vertical
demonstrations.

### ERC and MSCA

ERC is bottom-up frontier research selected on excellence. It depends on a
specific PI's eligibility window and record. MSCA Postdoctoral Fellowships
depend on a named researcher-host pair and mobility eligibility. Doctoral
Networks require an integrated European training programme, recruited doctoral
candidates, secondments, supervision, and durable academic/industrial
relationships.

## Opportunities screened out or deferred

- **EIC Pathfinder Open 2026** closed on 12 May 2026; reassess a 2027 route
  only after the official work programme is published.
- **HORIZON-CL4-2027-05-DATA-09** targets whole data-centre resource
  management at high TRL; the present project is too narrow and immature to
  anchor it.
- **HORIZON-CL4-2027-04-DATA-08** is at most a technology-provider route if a
  deployment-ready component and vertical-led telco-cloud-edge consortium
  exist; its TRL 6–8 and large pilot scope make it weaker than DATA-03.
- **HORIZON-CL4-2027-01-MAT-PROD-61** follows specified industrial research
  agendas that do not naturally fit TSL/RISC-V.
- Monitor the 2027 Chips JU work programme instead of inventing a match to a
  closed or restricted topic.

## Double-funding boundary

CHORYS remains active until the end of 2028. For every successor proposal,
record:

1. whether an asset is pre-existing background, a CHORYS result, or new
   proposal foreground;
2. its owner, licence, access right, maturity, and availability date;
3. which staff effort, equipment, costs, and deliverables are funded by each
   grant;
4. how the new scientific question or market-validation task differs from the
   CHORYS description of action.

No new proposal should charge the same work twice or rebadge a CHORYS
deliverable as new foreground.

## Immediate sequence

1. Hold a CHORYS result/IP workshop with the technical, exploitation, legal,
   and grants leads.
2. Ask Menta, Codasip, and Cyso whether one will own the RVV-READY business case
   and provide access to external customers.
3. Give the CHORYS coordinator a two-page RV-CONTINUUM baseline/foreground
   matrix.
4. Secure real RVV hardware and collect correctness, integration-time,
   performance, and defensible energy evidence.
5. Recruit the missing DATA-03 capabilities: federated AI orchestration,
   security/data governance, energy methodology, and two vertical owners.
6. Recheck the live topic and General Annexes before submission.

## Official and local sources

- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [Proof of Market topic](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-01-MAT-PROD-49)
- [DATA-03 topic](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-04-DATA-03/en)
- [Cluster 4 work programme](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-7-digital-industry-and-space_horizon-2026-2027_en.pdf)
- [Horizon Europe General Annexes](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-15-general-annexes_horizon-2026-2027_en.pdf)
- [Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/)
- [ERC Starting Grant](https://erc.europa.eu/apply-grant/starting-grant)
- [ERC Consolidator Grant](https://erc.europa.eu/apply-grant/consolidator-grant)
- [MSCA Postdoctoral Fellowships 2026](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026)
- [MSCA Doctoral Networks 2026](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-doctoral-networks-2026)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Target-family definition](../../../tsldata/detail/target_families.tsl)
- [Machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
