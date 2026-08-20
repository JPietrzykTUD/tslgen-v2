# DFG funding landscape for `tslc` and `tsldata`

Assessment date: **19 August 2026**

These are research concepts, not submission-ready applications. The DFG is the
German Research Foundation, and the routes below are research or infrastructure
programmes rather than procurement tenders. Eligibility, host commitments,
budgets, and the state of the art must be checked for a named PI.

## Shortlist

| Priority | Concept | Programme | Submission | Assessment |
| --- | --- | --- | --- | --- |
| 1 | [VLEN-Decode](research-grant-vlen-decode.md) | Research Grants Programme | Any time | Strongest near-term scientific and organisational fit |
| 2 | [One Bit, One Database](koselleck-one-bit-one-database.md) | Reinhart Koselleck Projects | Any time | High-risk route only for an outstanding professorial-level PI |
| 3 | [Kernel Evidence Observatory](kofi-kernel-evidence-observatory.md) | KoFI: coordinated Research Grant and Research Software Infrastructures proposals | Contact DFG first | Conditional on documented national demand and an infrastructure partner |

CHORYS materially strengthens VLEN-Decode. The public EU record confirms an
active RISC-V near-data accelerator RIA with TU Dresden as a beneficiary, and
the team identifies TSL/RISC-V integration as part of that work. CHORYS
engineering and platform results can be preliminary evidence, while the DFG
proposal asks a distinct scientific question about standards-compliant
decoding, vector length, and capability-conditioned algorithms.

A grant-record and double-funding review is mandatory because CHORYS remains
active until 31 December 2028.

## Why this can be research

`tslc` is a typed research compiler and `tsldata` is its declarative corpus
of primitive semantics, target extensions, tests, and benchmark metadata.
“Extend the SIMD library” is not a sufficient research question. The proposed
projects use this infrastructure to test falsifiable hypotheses about:

- vector-length-aware algorithm design;
- semantic versus performance portability;
- exhaustive relational semantics at small domains;
- reproducible, community-owned kernel evidence.

The current repository records 111 primitive names, typed RVV source data, and
generated build/test machinery. Its coverage inventory does not itself prove
full RVV performance or scientific novelty.

## Programme gates

### Research Grants Programme

The programme is bottom-up and accepts proposals at any time. An initial
project can normally run for up to three years. The named applicant must satisfy
the DFG eligibility and host rules. Software may be funded when it is necessary
to answer the research question; maintaining a compiler is not the project
objective.

### Reinhart Koselleck Projects

Koselleck funding supports exceptionally innovative, higher-risk work that
cannot be pursued adequately through ordinary instruments. It provides
EUR 500,000 to EUR 1.25 million for five years. The PI must be eligible to hold
a professorship and have an outstanding scientific record. It is not simply a
larger software grant.

### KoFI and Research Software Infrastructures

KoFI coordinates a scientific Research Grant with a separate LIS infrastructure
proposal. The scientific and infrastructure work programmes remain distinct.
Prospective applicants should contact the DFG before submission.

A Research Software Infrastructures proposal must serve communities across
sites with durable technical, organisational, governance, and skills
structures. It cannot merely finance the roadmap of one repository. The
June 2026 KoFI announcement says that the two coordinated proposals may be
submitted at any time. Do not infer a KoFI deadline from the generic recurring
LIS deadline rule; confirm the current forms, portal procedure, and review
timetable with the DFG before planning submission.

## Opportunities screened out at this stage

- No directly matching thematic DFG call or Priority Programme was identified
  in the 2026 screening. A new Priority Programme would require a substantially
  broader German research community and is not an immediate route.
- A standalone Research Software Infrastructures proposal whose real purpose
  is to maintain or extend `tslc` falls outside the programme logic.
- Instrumentation programmes do not fit unless a separate, justified hardware
  facility is itself required by the research.

## Recommendations

1. Run a real-hardware RVV/SVE decoding pilot and focused prior-art review.
2. Name a DFG-eligible PI and document scalable-vector hardware access.
3. Map every CHORYS task/result against every proposed DFG task, person, cost,
   and output.
4. Treat the Koselleck concept as a separate high-risk decision and run its kill
   experiment first.
5. Approach KoFI only after interviews/workshops demonstrate cross-institution
   demand and a durable infrastructure operator is committed.

## Sources

- [CHORYS project record](https://cordis.europa.eu/project/id/101189551)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [Research Grant guidelines](https://www.dfg.de/resource/blob/168072/50-01-en.pdf)
- [DFG eligibility](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [Reinhart Koselleck Projects](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/reinhart-koselleck-projects)
- [Research Software Infrastructures](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/infrastructure/lis/funding-opportunities/research-software-infrastructures)
- [Research Software Infrastructures guidelines](https://www.dfg.de/resource/blob/333366/12-22-en.pdf)
- [Research-software support options](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [KoFI announcement](https://www.dfg.de/en/news/news-topics/announcements-proposals/2026/ifr-26-39)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
