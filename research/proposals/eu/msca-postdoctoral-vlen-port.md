# VLEN-PORT: Portable Columnar Decoding Across Scalable Vector Lengths

Instrument: **MSCA Postdoctoral Fellowships 2026**

Deadline: **9 September 2026, 17:00 Brussels time**

Proposed fellowship: **European Postdoctoral Fellowship, normally 12–24 months**

Recommendation: **Submit in 2026 only if a named eligible fellow and host are
already working together; otherwise prepare for the 2027 call**

## Proposal summary

VLEN-PORT will train a postdoctoral researcher at the intersection of data
systems, RISC-V/Arm scalable vectors, research compilers, and reproducible
performance engineering. The fellow will develop and evaluate a
vector-length-agnostic decoder for a narrow standards-compliant columnar format
slice, compare it with capability-conditioned and native implementations on
real RVV and SVE hardware, and publish semantic, performance, and energy
evidence.

The host contributes TSL, generated verification, and CHORYS-linked RISC-V
expertise. The fellow contributes a clearly identified complementary skill—for
example columnar-format semantics, formal testing, performance modelling, or
scalable-vector optimisation. A secondment with an industrial RISC-V,
database, cloud, or accelerator partner connects the scientific work to career
development and transfer.

## Research question

Can one standards-compliant decoding decomposition remain semantically stable
and efficient across runtime vector lengths, and which explicit capabilities
are required when it cannot?

Objectives:

1. build a scalar executable specification and adversarial corpus;
2. implement universal, capability-conditioned, and native decoder variants;
3. validate correctness across RVV/SVE vector lengths;
4. measure performance and energy on real hardware;
5. derive an explanatory portability model;
6. transfer methods between fellow, host, and secondment partner.

## Work plan

### WP1 — Semantics and development plan

Freeze the decoder slice, prior art, reference semantics, training objectives,
supervision plan, and open-science/data-management approach.

### WP2 — Implementations and verification

Develop U/S/N variants, reusable typed capabilities, differential tests, and
reproducible toolchain/platform records.

### WP3 — Experiments and model

Measure real RVV/SVE/fixed-width systems; perform ablations; explain
vector-length and capability effects; validate on a held-out configuration.

### WP4 — Transfer and dissemination

Complete the secondment, release artefacts, deliver tutorials, submit
publications, and execute the fellow's career-development plan.

## Training and two-way transfer

The proposal must be designed around the named fellow. Candidate training:

- RVV/SVE programming and computer-architecture measurement;
- typed compiler/source-data methods;
- database/columnar semantics;
- property-based and differential testing;
- energy methodology and statistics;
- open-source governance and research-software leadership;
- grant writing, supervision, teaching, and industry communication.

The fellow must bring expertise that the host genuinely lacks. A proposal where
the researcher merely implements the host's backlog is not competitive.

## CHORYS connection

CHORYS supplies a credible RISC-V near-data context, consortium relationships,
and the team's stated TSL/RISC-V work. VLEN-PORT must define its own research,
training, secondment, staff effort, and outputs. Internal grant records should
establish what is CHORYS background/result and what becomes fellowship
foreground.

## MSCA fit

| Evaluation dimension | Response |
| --- | --- |
| Excellence | Focused, falsifiable scalable-vector research question |
| Researcher-host match | Explicit complementary expertise and two-way transfer |
| Impact | Career development, open evidence, industry secondment, European RISC-V skills |
| Implementation | Bounded 24-month plan, real hardware, milestones, risk gates |
| Mobility and internationality | Must be demonstrated for the named researcher |

## Eligibility and timing gates

The fellowship is a joint researcher-host application. Apply the official
doctoral-degree, research-experience, nationality/residence, and mobility rules
to the specific person. The 2026 deadline is too close for speculative
matchmaking as of 19 August 2026.

Do not submit in 2026 without:

- a named eligible fellow;
- completed mobility screening;
- committed host and supervisor;
- hardware and secondment access;
- a mature first draft and institutional submission schedule.

## Immediate actions

1. Decide whether a mature fellow-host pair already exists.
2. Run eligibility and mobility checks with the research office.
3. Define the fellow's unique expertise and two-way transfer.
4. Obtain a secondment commitment and real hardware access.
5. Run a minimal decoding pilot.
6. If these are not already advanced, target the announced 2027 call.

## Sources

- [MSCA Postdoctoral Fellowships 2026](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026)
- [MSCA Postdoctoral Fellowships 2027](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2027)
- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
