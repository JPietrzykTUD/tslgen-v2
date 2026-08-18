# DFG funding landscape for `tslc` and `tsldata`

Assessment date: **8 August 2026**

This folder contains proposal concepts, not submission-ready applications. The
DFG is the German Research Foundation (*Deutsche Forschungsgemeinschaft*), and
its programmes below are calls for research or infrastructure proposals rather
than procurement tenders. Eligibility, host commitments, budgets, ethics, data
management, and the state of the art still have to be checked for a named
principal investigator (PI) before submission.

## Result of the screening

Yes, there are plausible funding routes. The strongest near-term route is a
bottom-up DFG Research Grant on scalable-vector columnar decoding. Two more
ambitious routes are credible only under explicit conditions.

| Priority | Concept | Programme | Submission window | Assessment |
| --- | --- | --- | --- | --- |
| 1 | [VLEN-Decode](research-grant-vlen-decode.md) | Research Grants Programme | Any time | Best scientific and organisational fit; develop a hardware-access pilot first |
| 2 | [One Bit, One Database](koselleck-one-bit-one-database.md) | Reinhart Koselleck Projects | Any time | Excellent high-risk fit only for an outstanding, professorial-level PI |
| 3 | [Kernel Evidence Observatory](kofi-kernel-evidence-observatory.md) | KoFI: Research Grant plus Research Software Infrastructures | Contact DFG first; infrastructure deadlines occur in March and August | Conditional; do not submit before a national needs analysis and infrastructure partnership |

CHORYS materially strengthens the first route. The public EU record confirms an
active RISC-V near-data accelerator RIA with TU Dresden as a beneficiary, and
the team identifies TSL/RISC-V integration as part of that work. VLEN-Decode
therefore treats CHORYS engineering and platform results as preliminary
evidence, while reserving standards-compliant decoder algorithms, cross-ISA
experiments, and the causal vector-length/capability question for distinct DFG
work. A grant-record and double-funding check is a submission gate.

The next Research Software Infrastructures deadlines derived from the published
rule are **31 August 2026** (last Monday in August) and **1 March 2027** (first
Monday in March). The August date is not realistic for a new consortium unless
the required needs analysis, governance, and partner commitments already
exist. Recheck the current form and deadline with the DFG before planning a
submission.

## Why the project is fundable as research

`tslc` is a typed research compiler, and `tsldata` is its declarative corpus of
primitive semantics, target extensions, types, tests, and benchmark metadata.
The pipeline selects implementations, scans mixed raw text and typed TSIL
regions, lowers specialisations, renders C++ and Rust, and can generate build
and value-test evidence. This is a useful experimental instrument, but “extend
the SIMD library” is not a research question.

The tracked coverage inventory reports 111 primitive names and 171,442 emitted
specialisations for the probed profiles; it also records important limits.
Generated coverage is not by itself proof of compilation, performance, or
scientific novelty. The benchmark inventory likewise exposes substantial
coverage gaps. The proposals therefore use the compiler to test falsifiable
hypotheses about semantic portability, vector-length sensitivity, exhaustive
database semantics, or reproducible evidence—not as the proposal's end goal.

Relevant local evidence:

- [`tslc` architecture and scope](../../../tslc/DESCRIPTION.md)
- [Primitive coverage inventory](../../../coverage/primitive-coverage-inventory.md)
- [Benchmark-shape inventory](../../../coverage/benchmark-shape-inventory.md)
- [Database research assessment](../../database-research-meta-study.md)
- [Accelerator-portability frontier](../../accelerator-portability-frontier.md)
- [Relational truth-table pilot](../../query-eval/idea.md)

## Programme fit and eligibility gates

### Research Grants Programme

The programme is bottom-up: researchers may submit a clearly defined project
in any discipline at any time. An initial project can normally run for up to
three years. The ordinary eligibility route requires a doctorate and a German
research institution; the detailed DFG rules include institutional and
employment conditions that the named PI must verify. Research software needed
to answer the scientific question can be requested through the regular grant.

### Reinhart Koselleck Projects

This instrument supports exceptionally innovative, higher-risk work that
cannot be pursued adequately in another DFG programme or with institutional
funding. It provides EUR 500,000 to EUR 1.25 million for five years. The PI must
be eligible to hold a professorship and have an outstanding scientific record.
It is not a larger substitute for an ordinary software-engineering grant.

### KoFI and Research Software Infrastructures

Since 15 June 2026, a scientific Research Grant may be coordinated with a
separate proposal to a DFG Scientific Library Services and Information Systems
(LIS) programme. The work programmes remain distinct and are reviewed jointly.
The DFG asks prospective KoFI applicants to make contact before submission.

The Research Software Infrastructures programme is for cross-site,
community-oriented enabling structures at technical, organisational, and/or
skills levels. It is not a route for funding the feature roadmap of one
research code. A credible application needs representative users from more
than one community, an analysis of existing services, integration and
governance plans, and a sustainable operating institution.

## Opportunities screened out

- No directly matching active thematic DFG call or Priority Programme was
  identified in the 2026 call index. Creating a new Priority Programme would
  require a much broader German research community and is not an immediate
  route for this project.
- A standalone Research Software Infrastructures proposal whose actual purpose
  is merely to maintain or extend `tslc` would be outside the programme logic.
- Instrumentation programmes do not fit unless a separate, justified hardware
  facility is the research need.

## Recommended sequence

1. Run a small real-hardware SVE/RVV decoding pilot and a focused prior-art
   review; use the result to decide whether VLEN-Decode has a real performance
   and methods question.
2. Identify a DFG-eligible PI and obtain written access to the required
   scalable-vector hardware.
3. Treat One Bit, One Database as a separate high-risk programme. Run its
   bounded pilot before selecting Koselleck rather than an ordinary grant.
4. Approach KoFI only after interviews or workshops demonstrate demand across
   institutions and communities and an infrastructure provider is prepared to
   own long-term operation.

## Official sources

- [Official CORDIS record for CHORYS, grant 101189551](https://cordis.europa.eu/project/id/101189551)
- [DFG Research Grants Programme](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/research-grants)
- [DFG Research Grant guidelines (form 50.01)](https://www.dfg.de/resource/blob/168072/50-01-en.pdf)
- [DFG eligibility guidance](https://www.dfg.de/en/research-funding/proposal-funding-process/eligibility)
- [DFG Reinhart Koselleck Projects](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/individual/reinhart-koselleck-projects)
- [DFG Research Software Infrastructures](https://www.dfg.de/en/research-funding/funding-opportunities/programmes/infrastructure/lis/funding-opportunities/research-software-infrastructures)
- [Research Software Infrastructures guidelines (form 12.22)](https://www.dfg.de/resource/blob/333366/12-22-en.pdf)
- [DFG research-software support options](https://www.dfg.de/en/basics-topics/digital-topics/research-software/support-options)
- [DFG KoFI announcement, 15 June 2026](https://www.dfg.de/en/news/news-topics/announcements-proposals/2026/ifr-26-39)
- [DFG 2026 announcements and calls](https://www.dfg.de/en/news/news-topics/announcements-proposals/2026)
