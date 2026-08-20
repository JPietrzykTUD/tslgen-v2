# VLEN-PORT: Portable Columnar Decoding Across Scalable Vector Lengths

Instrument: **Marie Skłodowska-Curie Actions Postdoctoral Fellowships 2026**

Proposed form: **European Postdoctoral Fellowship, 24 months**

Status on 19 August 2026: **Open**

Deadline: **9 September 2026, 17:00 CEST**

Recommendation: **Submit in 2026 only if an eligible fellow and host are already paired; otherwise prepare for 2027**

The MSCA overview marks its timeline and budget as indicative/TBC. The live
Funding & Tenders topic is the controlling source and should be checked again
before submission.

## Proposal in one paragraph

VLEN-PORT will train a postdoctoral researcher at the intersection of database
systems, compiler semantics, and scalable-vector architecture while answering a
focused research question: can one standards-compliant Parquet integer decoder
remain efficient across runtime vector lengths on Arm SVE and RISC-V Vector, or
does it need a small set of capability-conditioned stages? The fellow will
construct a scalar executable specification, implement universal and
target-oracle variants, generate cross-profile differential tests, and measure
performance and energy on real hardware. A short external secondment with a
data-engine, compiler, or architecture partner will test transfer beyond the
host. The host contributes typed compilation, reproducibility, and
high-performance systems methods; the fellow must bring complementary expertise
such as columnar formats, scalable-vector programming, or experimental data
systems. The output is both new portability evidence and a researcher able to
bridge semantics, architectures, and open research software.

## Research question and objectives

Scalable-vector ISAs make lane count a runtime property. This helps binary
portability but leaves an algorithm-design question: which decoder stages can
remain vector-length agnostic, and which depend on predicate, permute,
compaction, or memory capabilities?

VLEN-PORT has four objectives:

1. define a narrow, standards-compliant Parquet integer-decoding slice and
   executable scalar oracle;
2. implement universal, capability-conditioned, and native-oracle variants for
   SVE, RVV, and a fixed-width SIMD baseline;
3. explain performance cliffs across vector lengths, compilers, and data
   distributions using controlled real-hardware experiments;
4. release reusable semantic cases, differential tests, benchmark protocols,
   and research artefacts while building the fellow's independent profile.

## Method and work plan

### WP1 — Semantics, state of the art, and individual development plan (months 1–4)

- Complete the format/algorithm prior-art review with host and external mentor.
- Freeze the selected encoding, null, tail, and malformed-input semantics.
- Build the scalar oracle and adversarial/property-based corpus.
- Agree a career-development plan, training objectives, open-science protocol,
  and hardware-access schedule.

### WP2 — Scalable-vector implementations and verification (months 3–11)

- Develop one vector-length-agnostic decoder and expert-reviewed target
  baselines.
- Introduce only reusable typed semantics needed by the experiment.
- Generate differential value tests over vector lengths and input classes.
- Use emulation only to widen functional coverage; obtain performance data on
  physical SVE and RVV systems.

### WP3 — Performance, energy, and explanatory model (months 9–18)

- Measure throughput, latency distributions, energy, code size, and relevant
  hardware counters across controlled datasets and toolchains.
- Separate vector-length effects from individual capability and compiler
  effects through ablations.
- Test whether a small capability-conditioned strategy reduces
  native-normalised regret on a held-out configuration.

### WP4 — Transfer, secondment, and dissemination (months 16–24)

- Validate the method with an external data-engine, compiler-vendor, or
  architecture partner.
- Publish the positive or negative portability result and open evidence package.
- Deliver a tutorial on reproducible scalable-vector experiments and a plan for
  the fellow's next independent funding step.

## Training and two-way knowledge transfer

MSCA evaluates researcher development, mobility, supervision, and impact as
well as scientific quality. The exact transfer depends on the named fellow.
A credible pairing would look like this:

| Host contributes | Fellow contributes |
| --- | --- |
| Typed compiler pipelines and semantic lowering | Standards-based columnar processing or scalable-vector expertise |
| Generated correctness/value testing | Independent native implementations and domain datasets |
| Reproducible benchmark and coverage methods | New research network and application perspective |
| C++/Rust and multi-profile generation | Complementary toolchain, database, or architecture practice |
| Research software governance and open artefacts | Training material and external transfer route |

The individual plan should add training in scientific leadership, supervision,
grant writing, responsible research, intellectual property/open-source choices,
statistics, energy measurement, and public communication. An intersectoral
secondment is useful only when the partner provides real format, compiler, or
hardware expertise.

## Role and readiness of `tslc`/`tsldata`

The project can reuse typed primitives, extension facts, machine profiles,
generated value tests, and deterministic C++ output. Current SVE and RVV
profiles lower apparatus risk, while existing gaps create a focused training
and research opportunity.

The proposal should not claim current cross-language scalable-vector parity or
performance validation. Rust is not presently an active SVE/RVV route, QEMU is
not performance evidence, and benchmark-shape coverage remains incomplete.
The fellow should add only capabilities needed for the scientific decoder
slice, not promise general completion of every backend.

## Relationship to CHORYS

CHORYS supplies a credible RISC-V near-data context, consortium relationships,
and the team's stated TSL/RISC-V integration work. VLEN-PORT must define its
own fellow-led research, training, secondment, staff effort, costs, and
outputs. Internal grant records should establish which assets are
pre-existing background, which are CHORYS results, and which work becomes new
fellowship foreground. Do not submit if those tasks or costs overlap.

## Why this fits MSCA Postdoctoral Fellowships

| MSCA characteristic | VLEN-PORT response |
| --- | --- |
| Excellent individual research project | A bounded, falsifiable question with standards-based semantics and real-hardware evaluation |
| Mobility and knowledge transfer | A fellow brings complementary architecture/database expertise into the host and transfers typed verification back out |
| Training and career development | Cross-disciplinary technical, open-science, leadership, and grant-development programme |
| Intersectoral/international exposure | Targeted secondment and external hardware/data-engine collaboration |
| Wider impact and reusable outputs | Open decoder semantics, conformance corpus, measurements, and training material |

The fellowship narrative must be written around the named researcher. A
generic person profile inserted after the science is designed will be weak.

## Eligibility and timing gates

For the 2026 call, the official MSCA guidance requires the researcher to:

- hold a PhD by the call deadline (including a successfully defended thesis
  where the degree has not yet formally been awarded);
- normally have no more than eight years of full-time-equivalent research
  experience after the PhD, with the call's specified exclusions;
- satisfy the mobility rule—normally not having resided or carried out the main
  activity in the host country for more than 12 months in the 36 months before
  the deadline.

The researcher and host apply jointly. European Fellowships normally last
12–24 months. Exact nationality, long-term-residence, career-break, and Global
Fellowship rules must be checked for the named researcher.

With only three weeks remaining on the assessment date, the 2026 call is a
no-go unless the fellow, supervisor, host research office, hardware access, and
core preliminary work already exist. The official call calendar lists the next
Postdoctoral Fellowships call opening on 7 April 2027 and closing on 8 September
2027; recheck those dates when the call documents are published.

## Main risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Project reads as host software maintenance | Lead with the fellow's scientific question, training, mobility, and independent trajectory |
| Hardware access fails | Secure written SVE/RVV access before submission and narrow energy claims to measurable systems |
| Scope is too broad for 24 months | Freeze one encoding family and one held-out capability test |
| Host and fellow knowledge overlap completely | Choose a genuinely complementary fellow and specify bidirectional transfer |
| 2026 preparation is rushed | Move intact concept to 2027 instead of submitting an underdeveloped application |

## Immediate next steps

1. Name the fellow and host supervisor; run the official mobility and
   post-PhD-experience calculation with the research office.
2. Define what knowledge travels in each direction and who supplies SVE/RVV
   hardware.
3. Select the exact encoding and run one universal/native pilot.
4. Obtain an external secondment commitment only if its training contribution
   is concrete.
5. Make a hard 2026/2027 go/no-go decision immediately.

## Official and local sources

- [MSCA Postdoctoral Fellowships 2026 call](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026)
- [MSCA Postdoctoral Fellowships 2027 call](https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2027)
- [Six steps to prepare an MSCA Postdoctoral Fellowship](https://marie-sklodowska-curie-actions.ec.europa.eu/actions/postdoctoral-fellowships/6-steps-to-prepare-your-application-postdoctoral-fellowships-call)
- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [Local database research assessment](../../database-research-meta-study.md)
- [Local RVV extension definition](../../../tsldata/extensions/extension.tsl)
- [Local machine profiles](../../../supplementary/buildsystem/machine_profiles.json)
- [Local benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
