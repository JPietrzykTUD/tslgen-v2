# RVV-READY: Proof of Market for a Portable RISC-V Data-Kernel SDK

Topic: **HORIZON-CL4-2027-01-MAT-PROD-49 — Proof of market to improve
valorisation and commercialisation of Horizon-generated R&I results**

Action type: **Innovation Action**

Source project: **CHORYS, grant 101189551**

Status on 19 August 2026: **Forthcoming; scheduled to open 22 September 2026**

Deadline: **2 February 2027, 17:00 Brussels time**

Indicative funding: **EUR 5 million total; around EUR 0.20 million per project**

Recommendation: **Prepare only if the result, rights, business lead, and
customer access can be documented**

## Proposal summary

RVV-READY will test whether the TSL-to-RISC-V work developed in CHORYS can
become a customer-ready development and qualification package for European
RISC-V data-processing platforms. The package will let a processor-IP vendor,
near-data accelerator integrator, or cloud operator select a bounded set of
data-intensive kernels from typed semantics, generate RVV C++
implementations, and attach reproducible compiler, vector-length, correctness,
and performance evidence.

A small business-led consortium will freeze the exploitable result and its
rights, interview prospective buyers, package one market-specific kernel set,
and run two external design-partner pilots on real RISC-V hardware. The project
will make a go, pivot, or stop decision based on integration effort,
performance, energy, support cost, willingness to pay, and adoption evidence.
It is a proof of market, not a request for another open-ended compiler roadmap.

## Why CHORYS qualifies as the source

CORDIS describes CHORYS as an ongoing Cluster 4 RIA that develops open and
programmable near-data accelerators and promotes European RISC-V capability.
The project team states that its TSL/RISC-V integration belongs to this work.

The application must go beyond that public evidence and identify:

- the achieved result and the CHORYS task, milestone, deliverable, or report in
  which it is recorded;
- which components are project background and which are CHORYS results;
- owners and contributors to code, source data, documentation, tests, and
  know-how;
- third-party and open-source licences;
- who has commercialisation rights for the proposed action;
- either an applicant that owns/holds the relevant rights or the result owner's
  commitment to negotiate fair, reasonable, and non-discriminatory access.

If the TSL/RVV asset is only planned future work at submission time, this topic
does not fit it.

## Product candidate

The candidate product is deliberately narrower than the whole compiler:

1. a selected semantic catalogue of high-value data-processing kernels;
2. an RVV C++ generation profile for a declared compiler and platform envelope;
3. generated build, value, provenance, and compatibility evidence;
4. reference integration for one beachhead such as storage, networking,
   database/analytics, or near-data cloud processing;
5. installation, documentation, SBOM/licence material, and support procedures.

The local repository supplies useful apparatus: scalable runtime lane counts,
RVV intrinsic composition, RISC-V cross-compilation, QEMU functional execution,
and generated verification. It does not yet prove buyer demand or real-board
performance.

## Commercial hypotheses

| Element | Hypothesis to test |
| --- | --- |
| Initial customer | European RISC-V IP/platform vendors and near-data integrators |
| Pain | Hand-written RVV enablement is slow to integrate and qualify across compilers, vector lengths, and platform revisions |
| Offer | Supported kernel pack plus generation, conformance, provenance, and integration service |
| Buyer value | Shorter time to a qualified workload and lower regression/maintenance cost |
| Differentiation | Typed source semantics and generated evidence while retaining native optimisation |
| Revenue options | SDK/support subscription, platform integration contract, or licensing to an IP/tool provider |

Open-source use does not automatically create revenue. The project must test
who pays, what remains open, and which assurance, maintenance, or integration
service is scarce.

## Showcase experiment: 48-hour RVV integration challenge

This experiment tests the commercial lever directly: whether the product reduces
the effort and risk of adopting RVV, rather than merely generating code that is
fast in an internal benchmark.

### Workload and comparison

Two design partners receive the same hidden acceptance corpus for a nullable
`int32` pipeline: load at least 64 Mi values, apply a one-sided threshold predicate,
compact the qualifying values, and return a 64-bit count and checksum. The
corpus spans selectivities of 1%, 10%, 50%, and 90%; average value and null run
lengths of 1, 16, and 256; 0% and 10% nulls; and every tail length up to one
vector. The working set must exceed four times the target's last-level cache.

Each partner integrates two matched predicate variants in randomized order:

- the RVV-READY package generated from one TSL semantic source, including the
  build recipe, correctness tests, target manifest, and evidence report;
- the partner's normal route, using scalar/autovectorized code or hand-written
  RVV intrinsics and its usual qualification procedure.

After first acceptance, both routes receive the same change request: replace a
one-sided predicate with the inclusive range predicate and qualify a new
compiler minor version. Runs use the same board, compiler flags, clock policy,
input bytes, and output checks. A scalar implementation is the correctness and
performance floor; an expert RVV implementation is the native-performance
reference. TSL developers may answer documented support questions but may not
write integration code for the partner.

### Measurements and decision rule

Record engineer-hours to first correct run and to qualified release, hidden-test
failures, support interventions, change-turnaround time, rows/s, joules/row,
binary size, and performance relative to the expert RVV reference. Report
per-partner results as well as the paired aggregate so that one unusually strong
engineer cannot hide a failed integration.

The commercial lever is present if both partners complete without TSL-team code
changes, the packaged route at least halves median qualification effort, has no
semantic mismatches, and reaches at least 85% of native throughput throughout
the declared support envelope. It is absent if adoption still requires custom
RVV work, the evidence package does not shorten qualification, or performance
falls below the partner's acceptance floor. These are pre-registered pilot
screening thresholds, not promised tender outcomes; failed cells remain part of
the product decision.

## Work plan

### WP1 — Result and rights

- trace the source result to CHORYS records;
- freeze the product boundary and supported platform envelope;
- complete ownership, licence, and contribution maps;
- obtain owner participation or the required access commitment;
- separate all work and costs from the ongoing CHORYS grant.

Decision gate: no bid without a complete rights chain and a result that is
already achieved.

### WP2 — Market evidence

- conduct structured interviews with qualified buyers and users;
- compare native intrinsics, auto-vectorisation, SIMD libraries, vendor SDKs,
  and competing generators;
- choose one beachhead and document buyer, procurement, certification, and
  support requirements;
- test pricing and route-to-market assumptions.

One beachhead is mandatory. Internal benchmark results cannot replace
external customer workloads, integration experience, or buying-process
evidence.

### WP3 — Productised demonstrator

- package reproducible installation and evidence reports;
- close only customer-journey blockers;
- validate on real RISC-V hardware and multiple functional vector-length
  configurations;
- compare against an agreed native baseline for correctness, integration time,
  throughput, energy where defensible, and maintenance effort.

### WP4 — External pilots and decision

- run two external real-workload design-partner pilots;
- record adoption blockers and buying-process evidence;
- select and cost the product, service, licensing, and maintenance model;
- produce a go, pivot, or stop decision and name the post-project owner.

## Fit to the tender

| Topic expectation | RVV-READY response |
| --- | --- |
| Achieved Cluster 4 RIA/IA result | TSL/RVV package traced to CHORYS grant 101189551 |
| Explore commercial potential | Customer discovery, pricing tests, competition analysis, and pilots |
| Startup/SME involvement | CHORYS SME or another eligible business owns the market route |
| Demonstration and testing | Productised SDK evaluated on real hardware and real workloads |
| Knowledge-asset access | Ownership map plus rights confirmation or access commitment |
| Pathway to market | Defined buyer, offer, revenue options, pilots, and post-project owner |

The fit is strong only if the achieved-result and rights gates pass.

## Consortium

The public CHORYS consortium contains a plausible industrial seed: Menta
(France), Codasip GmbH (Germany), and Cyso (Netherlands). This is not an
assumption that they will participate. A credible small consortium needs:

- one business partner accountable for the offer and buyers;
- one RISC-V platform/IP partner accountable for reference integration;
- one workload, cloud, storage, or near-data partner accountable for a pilot;
- the TSL team supplying the result and technical evidence where justified.

Recheck the live portal for the collaborative-action minimum and country/control
restrictions. At roughly EUR 0.20 million, do not recreate the full CHORYS
consortium or distribute token research tasks.

## Success measures

Draft targets, to be agreed with the business lead:

- completed ownership/access package;
- at least 12 qualified buyer/user interviews;
- one frozen kernel/platform envelope;
- two external real-workload pilots on real RVV hardware;
- evidence for correctness, integration effort, performance, and calibrated
  energy where possible;
- at least two concrete post-project market signals;
- costed go/pivot/stop decision.

## No-go conditions

Do not submit if:

- the asset cannot be evidenced as an achieved CHORYS result;
- ownership or commercial access remains unresolved;
- no business partner owns the offer;
- no external customer will provide a workload and adoption feedback;
- the proposal mainly funds new primitives/backends rather than market tests;
- tasks, staff effort, costs, or deliverables duplicate CHORYS.

## Immediate actions

1. Convene the CHORYS technical lead, exploitation lead, coordinator, and
   TU Dresden legal/grants offices.
2. Write a one-page result sheet covering source record, owner, licence,
   supported platform, current evidence, and customer problem.
3. Ask the CHORYS industrial partners who will lead and bring external
   customers.
4. Run five discovery interviews before committing to a full proposal.
5. Secure real RVV board access.
6. Recheck the topic and application forms when the call opens.

## Sources

- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [Proof of Market topic](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-01-MAT-PROD-49)
- [Cluster 4 work programme](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-7-digital-industry-and-space_horizon-2026-2027_en.pdf)
- [Horizon Europe General Annexes](https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/horizon/wp-call/2026-2027/wp-15-general-annexes_horizon-2026-2027_en.pdf)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Target-family definition](../../../tsldata/detail/target_families.tsl)
- [Machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
