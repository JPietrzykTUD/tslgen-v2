# RVV-READY: Proof of Market for a Portable RISC-V Data-Kernel SDK

Topic: **HORIZON-CL4-2027-01-MAT-PROD-49 — “Proof of market” to improve
valorisation and commercialisation of Horizon generated R&I results**

Action type: **Horizon Europe Innovation Action (IA)**

Source project: **CHORYS, grant agreement 101189551**

Status on 8 August 2026: **Forthcoming; scheduled to open 22 September 2026**

Deadline: **2 February 2027, 17:00 Brussels time**

Topic budget: **EUR 5 million; around EUR 0.20 million per project and about 25
projects expected**

Recommendation: **Prepare immediately, conditional on an achieved CHORYS result,
documented commercialisation rights, an SME/business lead, and real customer
access**

## Proposal in one paragraph

RVV-READY will test whether the TSL-to-RISC-V work developed in CHORYS can become
a customer-ready software development and qualification package for European
RISC-V data-processing platforms. The package will let a processor-IP vendor,
near-data accelerator integrator, or cloud operator select a bounded set of
data-intensive kernels from typed semantics, generate RVV C++ implementations,
and attach reproducible compiler, vector-length, correctness, and performance
evidence. A small business-led consortium will freeze the exploitable result and
its rights, interview prospective buyers, package one market-specific kernel
set, and run two external design-partner pilots on real RISC-V hardware. The
project will decide—using adoption, integration-effort, performance, energy,
support-cost, and willingness-to-pay evidence—whether to launch a supported
SDK/service, license an integration and qualification layer, or stop. It is a
proof of market, not a request to fund another open-ended compiler roadmap.

## Why CHORYS is a direct source project

The official CORDIS record describes CHORYS as an ongoing Cluster 4 RIA from
January 2025 through December 2028. Its public objectives include open and
programmable accelerators, near-data processing, asynchronous cloud data
services, improved performance/energy/cost, and European leadership in RISC-V
accelerators. TU Dresden is a beneficiary; Menta, Codasip, and Cyso are among
the industrial participants.

The project team states that its TSL/RISC-V integration is CHORYS work. The
public project description does not identify TSL or this repository by name, so
the application must establish the link from the grant's own records. Before
writing the bid, identify:

- the achieved result and the CHORYS task, milestone, deliverable, or periodic
  report in which it is recorded;
- which part is pre-existing background, which part is a CHORYS result, and
  which code, data, documentation, and know-how form the product candidate;
- every owner and contributor, including rights in third-party and open-source
  dependencies;
- who has the right to commercialise the complete package for the proposed
  project's duration;
- whether a result owner will join the proposal or provide the required
  commitment to negotiate fair, reasonable, and non-discriminatory access.

If the TSL/RVV package cannot be evidenced as an achieved CHORYS result by the
submission date, this topic is not the right route for it. A merely planned
future CHORYS result is insufficient.

## Result to be valorised

The candidate result is not “the whole compiler.” It is a frozen,
market-specific package assembled from four assets:

1. **Semantic kernel catalogue:** a selected set of high-value data-processing
   primitives with typed signatures, capabilities, and correctness cases.
2. **RVV generation profile:** scalable-vector C++ generation, runtime lane
   handling, toolchain settings, and integration headers for a declared RISC-V
   platform envelope.
3. **Qualification evidence:** generated build and value tests, toolchain and
   vector-length provenance, benchmark protocols, and a machine-readable
   compatibility report.
4. **Integration know-how:** documentation, examples, support procedures, and
   reference adapters for one beachhead application such as storage/network
   near-data processing or cloud analytics.

The repository provides credible preliminary apparatus: `tsldata` declares a
scalable RVV extension with runtime lane counts; the target-family and machine
profiles define RISC-V C++ cross-compilation and QEMU execution; and the corpus
contains 111 primitive names overall. These facts establish an engineering
starting point, not market demand. QEMU evidence is useful for correctness but
cannot replace real-board integration, performance, or energy measurements.

## Commercial hypothesis

The proposal should test one beachhead rather than market “portable SIMD” to
everyone.

| Element | Testable hypothesis |
| --- | --- |
| Initial customer | European RISC-V IP/platform vendors and near-data system integrators that need software enablement for data-intensive workloads |
| Pain | Hand-written RVV kernel enablement is slow to qualify across compilers, changing hardware profiles, and vector lengths |
| Offer | Supported kernel pack plus generation, conformance, provenance, and integration service for a declared platform envelope |
| Buyer value | Shorter time to a qualified workload, lower maintenance and regression cost, and auditable portability evidence |
| Differentiation | Typed source semantics and generated evidence across vector lengths, while native target optimisation remains possible |
| Revenue options to test | Annual SDK/support subscription, per-platform integration and qualification contract, or licensing to an IP/tool vendor |

The project should not assume that open-source adoption becomes revenue. It
must test who pays, what remains open, which assurance or integration service is
scarce, and whether the addressable market supports continued maintenance.

## Proposed activities

### WP1 — Result, rights, and product boundary

- Record the source result as **CHORYS, grant 101189551** and trace it to the
  grant's technical and ownership records.
- Freeze the kernel pack, supported RVV/toolchain/platform envelope, licences,
  third-party notices, and contribution history.
- Obtain owner confirmation or the required access commitment before
  submission; resolve consortium and exploitation-agreement conflicts early.
- Define the supportable product and explicit non-features.

Decision gate: no bid without a complete rights chain and a result that is
already achieved.

### WP2 — Market and competition evidence

- Interview qualified buyers across RISC-V IP, accelerator, storage/network,
  database/analytics, and cloud-platform segments.
- Compare native intrinsics, compiler auto-vectorisation, established SIMD
  libraries, vendor SDKs, and other code-generation approaches on buyer-relevant
  criteria.
- Select one beachhead use case and document buyer, user, procurement, support,
  certification, and integration requirements.
- Test pricing and route-to-market assumptions rather than only asking whether
  the technology is interesting.

### WP3 — Productised demonstrator

- Package reproducible installation, examples, toolchain/container metadata,
  SBOM and licence material, generated tests, and evidence reports.
- Close only the defects and usability gaps that block the selected customer
  journey.
- Establish a real-hardware reference and retain at least two RVV vector-length
  correctness checks; use emulation only for functional breadth.
- Measure integration time, correctness failures, throughput, energy where
  calibrated, binary/code size, and maintenance effort against an agreed native
  baseline.

### WP4 — External customer pilots

- Run two design-partner pilots with prospective users outside the core
  development team.
- Require each pilot to integrate a real workload and report adoption blockers,
  not merely execute a supplied benchmark.
- Capture evidence suitable for a purchase, paid follow-on, licence, or a
  documented no-buy decision.

### WP5 — Commercialisation decision

- Select and cost the product, service, licensing, support, and maintenance
  model.
- Consolidate IP, standards, compliance, security, export/control, and supply
  dependencies relevant to the chosen market.
- Produce a go/pivot/stop decision, exploitation agreement, financing plan, and
  post-project owner for the product.

## Why the concept fits the topic

| Topic requirement or expected outcome | RVV-READY response |
| --- | --- |
| Achieved result from an ongoing/completed Cluster 4 RIA or IA | The candidate result is the TSL/RVV package achieved in CHORYS; grant 101189551 is named and must be evidenced internally |
| Explore commercial potential of Horizon results | Customer discovery, competition analysis, pricing tests, two pilots, and a go/pivot/stop decision |
| Involve startups and SMEs in valorisation | A CHORYS industrial SME or another eligible business leads the market path; academic participation remains bounded |
| Demonstration, testing, assessment, certification or standards | Productised real-hardware demonstrator, native comparison, qualification evidence, and relevant standards/compliance review |
| Ownership/access to knowledge assets | Result register, ownership map, commercialisation rights, and owner confirmation or FRAND-access commitment |
| Clear pathway to market and business partner | Named buyer segment, offer, revenue hypotheses, pilot customers, and a post-project commercial owner |

The fit is unusually strong **if** the rights and achieved-result tests pass. It
is weak if the bid asks to add speculative backends, primitives, or research
features without a customer decision attached.

## Consortium shape and eligibility

The work programme calls for a small consortium, especially spin-offs,
startups, and SMEs. Because the topic refers to the ordinary General Annex B
eligibility conditions and states no collaborative-consortium derogation,
prepare for the standard minimum of three independent legal entities in three
different eligible countries, including one Member State entity and two others
from different Member States or Associated Countries. Recheck the live portal.

The public CHORYS consortium already contains a plausible three-country
industrial seed: Menta in France, Codasip GmbH in Germany, and Cyso in the
Netherlands. That is an observation, not an assumption that any partner will
participate or lead. A credible role pattern would be:

- one industrial partner owns the customer problem and commercial offer;
- one RISC-V platform/IP partner owns the reference integration;
- one cloud, near-data, or workload partner owns an external-facing pilot;
- the TSL team supplies the result, evidence pipeline, and technical support as
  a beneficiary or through another grant-compliant arrangement justified by
  the rights and budget.

At roughly EUR 0.20 million EU contribution, a university-heavy consortium or
large research plan is not credible. Preserve money for customer pilots,
productisation, market work, and exploitation rather than distributing token
research tasks among the full CHORYS consortium. The topic also excludes
entities directly or indirectly controlled by China; perform the required
control check for every participant.

## Evidence targets

Final targets should be negotiated with the business lead, but a credible
proposal would include:

- a signed result-ownership/access package before grant signature;
- at least 12 structured interviews with qualified prospective buyers/users;
- one frozen supported kernel/platform envelope with reproducible installation
  and qualification evidence;
- two external real-workload pilots on real RISC-V hardware;
- comparative evidence for integration effort, correctness, performance, and
  energy where measurement is defensible;
- at least two concrete post-project signals, such as a paid-pilot proposal,
  licence negotiation, letter of intent, or documented procurement path;
- a costed go/pivot/stop decision and named post-project product owner.

These are draft management targets, not call requirements.

## Main risks and no-go conditions

| Risk | Mitigation or no-go rule |
| --- | --- |
| TSL/RVV is background or planned work, not an achieved CHORYS result | Trace the exact result through CHORYS records; do not submit if the source-result condition fails |
| Ownership or commercial rights are fragmented | Complete the rights map and obtain owner participation or the required access commitment before writing |
| The same engineering is charged to CHORYS and RVV-READY | Separate work packages, staff effort, costs, deliverables, and results; obtain coordinator and grants-office review |
| Consortium is academic or technology-push led | Require an accountable business lead and external customer access |
| QEMU success is presented as product evidence | Use QEMU for functional coverage and real boards/customer workloads for market evidence |
| Scope exceeds a EUR 0.20 million action | Freeze one beachhead, one platform envelope, and one kernel pack; reject a general backend roadmap |
| No customer will share a workload or buying process | Stop rather than replace external evidence with internal benchmarks |

## Immediate next steps

1. Convene TU Dresden's CHORYS technical lead, exploitation lead, legal/IP
   office, and the project coordinator for a result-and-rights review.
2. Ask Menta, Codasip, and Cyso separately whether they see a sellable result,
   will lead or join, and can bring an external design customer.
3. Write a one-page result sheet: source task/deliverable, owner, licence,
   supported kernel/platform envelope, current evidence, customer problem, and
   unresolved rights.
4. Run five discovery interviews before committing to a proposal; use them to
   choose the beachhead and two pilot profiles.
5. Obtain real RVV board access and reproduce a versioned correctness and
   performance baseline.
6. Recheck the Funding & Tenders topic, templates, funding model, security and
   control conditions, and any work-programme amendment when the call opens.

## Official and local sources

- [Official CORDIS record for CHORYS, grant 101189551](https://cordis.europa.eu/project/id/101189551)
- [Official CORDIS record for HORIZON-CL4-2027-01-MAT-PROD-49](https://cordis.europa.eu/programme/id/HORIZON_HORIZON-CL4-2027-01-MAT-PROD-49)
- [Horizon Europe 2026–2027 Cluster 4 work programme](https://research-and-innovation.ec.europa.eu/document/download/87a8c19b-2643-49ec-8d07-37781ceb516e_en)
- [Horizon Europe 2026–2027 General Annexes](https://research-and-innovation.ec.europa.eu/document/download/7318fc15-13a4-484b-a74e-7c403f88fee2_en)
- [EU Funding & Tenders Portal](https://ec.europa.eu/info/funding-tenders/opportunities/portal/)
- [Local RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Local target-family definition](../../../tsldata/detail/target_families.tsl)
- [Local RISC-V machine profile](../../../supplementary/buildsystem/machine_profiles.json)
- [Local primitive-coverage inventory](../../../coverage/primitive-coverage-inventory.md)
