# Publication assessment of `tslc` and `tsldata`

Assessment date: 2026-07-29

## 1. Executive verdict

Primary verdict: **Potentially publishable, but probably below top-tier**.

The workspace contains a substantial and unusually disciplined implementation: a typed, deterministic compiler (`tslc`) consumes a large declarative SIMD corpus (`tsldata`) and emits C++ and Rust libraries, build projects, tests, diagnostics, coverage reports, and editor-facing information. The integrated compiler and corpus contain a plausible candidate for peer-reviewed publication, but that candidate has not yet been isolated or empirically defended.

The publication-status correction is material. **“Designing and Implementing a Generator Framework for a SIMD Abstraction Library” is an arXiv/CoRR preprint, not a refereed publication.** DBLP records it only as CoRR ([DBLP record](https://dblp.org/rec/journals/corr/abs-2407-18728)). Current SIGMOD policy explicitly permits an existing arXiv version and defines prior publication as refereed proceedings or journal work ([SIGMOD 2027 policy](https://2027.sigmod.org/calls_papers_sigmod_research.shtml)); PVLDB uses the same refereed-publication distinction ([PVLDB 2027 guidelines](https://www.vldb.org/2027/submission-guidelines.html)). The preprint therefore does **not** consume the project's opportunity for a first peer-reviewed paper. It is best treated as the authors' earlier manuscript and evidence of the intended thesis, not as an independent publication that defeats novelty.

The project is still not publication-ready for a top-tier database or systems venue. Three facts dominate the corrected assessment:

1. The central generative approach remains eligible for publication. A source-driven SIMD-library compiler may be a publishable domain-specific systems architecture even though its components use known compiler techniques. The strongest candidate insight is narrower than “we generate a library”: it is the **minimal semantic lift** needed to preserve hand-authored intrinsic control while retargeting a large corpus across languages and fixed/scalable-vector ISAs.
2. That insight is presently implicit. Typed post-parse models, rule-based selection, semantic regions, backend dialects, dependency closure, templates, generated tests, and deterministic diagnostics are sound engineering. The repository does not yet formalize why this particular raw-text/typed-region boundary is new or superior, quantify it, or show that it produces a generalizable outcome.
3. The repository contains extensive test and benchmark *infrastructure*, but not the measurements needed for a research claim. Static inspection found no committed evaluation showing generated-code performance, performance portability, compile-time cost, code size, database workload performance, developer productivity, or defect-detection effectiveness against credible baselines. The checked-in benchmark inventories mainly record shape coverage and gaps, not runtime results.

The three proposed selling points should not be presented as three equal novelties. **One authored corpus producing multiple languages** is an important result to measure, but multi-backend generation is established. **Fast integration of new paradigms** is the strongest central research hypothesis when restated as bounded change amplification: integration effort should track genuinely new semantic obligations rather than the full corpus-product size. **Autotuning** is careful and useful engineering in its current measure-and-select form; it becomes scientific only if the project demonstrates a new result such as safe capability-constrained pruning or transferable variant rankings across generated languages.

The database motivation is plausible but weakly realized. Database-oriented helper examples cover masks, predicates, selection vectors, aggregation, and consumption, and `todo/db-operators.md` explicitly frames TSL as a database-engineering research prototype. However, no integration with a database management system or query compiler, no representative analytical workload, and no end-to-end database measurements were found. The separate `test-sort` prototype has a more recognizably database-oriented algorithmic subject, but it is not evidence for the current `tslc`/`tsldata` compiler: its default build consumes a released TSL package rather than the workspace revision, and its recorded measurements are narrow and preliminary.

| Dimension | Assessment |
|---|---|
| Importance of the general problem | High: SIMD portability, scalable-vector support, and maintainable architecture-specific code matter to systems and databases. |
| Scientific novelty currently demonstrated | Plausible but unproven. The arXiv manuscript does not count as formal prior publication; the real novelty risks are established generative techniques, portable SIMD libraries, TVL, vector IRs, and hardware-adaptive database work. |
| Engineering novelty and difficulty | Moderate to high. The breadth, typed ownership, deterministic diagnostics, dual-language output, and verification planning are impressive. |
| Empirical readiness | Low. Infrastructure is broad; research measurements and comparisons are absent. |
| Current database-research fit | Weak. There are operator-shaped examples but no DBMS integration or data-management evaluation. |
| Best present publication unit | The integration of `tslc` and `tsldata` as research software, not either component alone. |
| Most credible present venue level | A focused generative-programming/compiler paper after moderate research work, or an artifact/software publication. A database demonstration or workshop paper becomes credible after a concrete integration. |
| Top-tier path | Possible after substantial work. It does not require abandoning the generator thesis, but it does require turning one implicit design choice into a falsifiable insight and evaluating it against strong systems. |

Confidence is **moderately high (approximately 0.78)**. The principal uncertainty is not publication eligibility but whether the hybrid TSIL boundary, or a capability-closure projection built from it, remains novel after a deeper focused literature review. The evidence most likely to improve the verdict is a small pilot showing either (a) that a compact semantic-region set measurably enables cross-language reuse that templates and a full IR do not, or (b) that transitive native/composed/fallback facts cause database operator choices that coarse ISA labels miss.

## 2. Scope and limitations of the assessment

This was a strict static inspection. In accordance with the requested safety constraints:

- No project code, Python module, script, generator, build, test, linter, package manager, notebook, or benchmark was executed.
- No dependency, cache, build tree, Git state, external service, or file other than this report was changed.
- Test files and CI definitions were inspected as evidence of intended validation, not as evidence that checks currently pass.
- Checked-in coverage and planning reports were treated as repository claims. Their numbers were not regenerated or independently verified.
- Recorded benchmark observations were assessed only where they already existed in documentation. No performance result was reproduced.

The local evidence reviewed included the repository and compiler charters, architecture description, plans, source-data instructions, compiler pipeline and models, selector and lowering code, backend interfaces, representative `.tsl` sources, test definitions, CI configurations, coverage inventories, benchmark documentation, examples, and the adjacent multi-column sort prototype. Particularly important evidence includes:

- `CHARTER.md`, `PLANS.md`, `tslc/CHARTER.md`, and `tslc/DESCRIPTION.md`;
- `tslc/src/tslc/pipeline.py`, `catalog/model.py`, `select/selector.py`, `ir/segments.py`, `ir/scan.py`, `lower/lowerer.py`, `lower/raw_text.py`, and `backend/translation.py`;
- `tsldata/extensions/extension.tsl`, `tsldata/detail/target_families.tsl`, and representative primitive sources such as `tsldata/primitives/arithmetic/fundamental.tsl`;
- `tslc/tests/test_build_verify.py`, `tslc/tests/test_value_tests.py`, and the remaining static test suite;
- `coverage/primitive-coverage-inventory.md`, `coverage/benchmark-shape-inventory.md`, and `coverage/benchmark-rust-shape-inventory.md`;
- `docs/variant-benchmarking.md`, `todo/db-operators.md`, and the C++ and Rust examples;
- `test-sort/docs/multi-column-sort.md`, `test-sort/docs/multi-column-sort-plan.md`, `test-sort/benchmarks/benchmark_multicolumn_gbench.cpp`, and `test-sort/CMakeLists.txt`.

The related-work search covered the direct TSL lineage, portable SIMD libraries and standards, database execution and query compilation, vector IRs, generative/autotuning systems, and compiler-testing work. It prioritized papers and official project or venue sources. It was not a formal systematic literature review, citation-network study, patent search, or exhaustive code-hosting search. Therefore, “no novelty found” means that no defensible novelty emerged against the strong nearby work inspected; it is not proof that every related publication has been enumerated.

External adoption was not exhaustively audited. The repository did not supply an external-user study, dependency census, or case-study evidence. Absence of such evidence in this assessment should not be read as proof that no external users exist.

Venue names and scopes were checked against current public calls or official pages available in July 2026. Venue deadlines, track names, and policies can change before submission.

## 3. Project and architecture summary

### 3.1 Problem, users, and outputs

`tslc` addresses a real engineering problem: manually maintaining SIMD primitives across instruction-set extensions, element types, feature combinations, and target languages creates duplication and semantic drift. `tsldata` supplies the source corpus and target facts; `tslc` parses those inputs, selects applicable implementations, lowers recognized semantics, and emits usable projects.

The intended users supported by repository evidence are:

- authors who define or maintain SIMD primitives and target-extension data;
- maintainers of a generated SIMD abstraction library;
- C++ and Rust consumers who want a uniform primitive interface;
- compiler/tooling users who need diagnostics, explanations, previews, coverage, or editor services;
- downstream systems developers, including database-oriented consumers illustrated by the examples.

The architecture can be summarized as:

```text
`.tsl` source data
    -> parsing and source locations
    -> frozen typed catalog
    -> profile/type/feature specialization selection
    -> recursive scan of raw text plus recognized TSIL regions
    -> typed lowering and dependency discovery
    -> profile-scoped closure, pruning, and finalization
    -> C++ or Rust backend dialect
    -> rendered libraries, projects, tests, reports, and editor facts
```

This flow is documented in `tslc/DESCRIPTION.md` and implemented principally in `tslc/src/tslc/pipeline.py`. `GenerationRequest` and `GenerationResult` are explicit boundary objects, while `_GenerationSession.run` and `_generate_profile` coordinate catalog loading, profile selection, dependency worklists, lowering, pruning, coverage, and rendering.

### 3.2 Relationship between `tslc` and `tsldata`

| Component | Owned responsibility | Concrete evidence |
|---|---|---|
| `tsldata` | Declarative primitive definitions, extension/profile facts, feature relationships, type groups, semantic contracts, implementation bodies, authored test cases, and language translation data | `tsldata/extensions/extension.tsl`; `tsldata/detail/target_families.tsl`; `tsldata/detail/lang/`; `tsldata/primitives/` |
| `tslc` | Parsing, validation, typed domain representation, selection, TSIL scanning, lowering, closure, backend translation, rendering, diagnostics, authoring tools, generated verification, and artifact writing | `tslc/src/tslc/`; architecture in `tslc/DESCRIPTION.md` |
| Integration boundary | Source data describes facts and bodies; the compiler owns interpretation and artifact generation | Repository and subtree `AGENTS.md` files; `tslc/CHARTER.md` |

The separation is scientifically sensible: corpus facts are data, while semantic interpretation belongs to the compiler. It also makes the integrated artifact more valuable than either tree alone. `tsldata` without the compiler is a code corpus in a project-specific schema; `tslc` without the corpus is a compiler framework with little demonstrated application breadth.

### 3.3 Main abstractions

The implementation follows the repository's “typed objects after parsing” rule. `tslc/src/tslc/catalog/model.py` defines frozen domain objects including `Implementation`, `PrimitiveBenchmarkSpec`, `Primitive`, `Extension`, and `Catalog`. Semantic contracts are split into focused modules for memory, conversions, shifts, overloads, and other domains. This is strong ownership and maintainability, but frozen dataclasses and typed domain models are established compiler practice rather than a research result.

Specialization selection in `tslc/src/tslc/select/selector.py` is deterministic and explicit. Candidate ordering combines extension-chain distance, type-group specificity, feature-flag count, and source order. `evaluate_candidates` applies compatibility checks and sorts candidates; ambiguity diagnostics expose ties whose final distinction would otherwise be source order. This is a useful and auditable rule system. It is not an optimization algorithm or learned cost model.

TSIL is deliberately an island language, not a target-language AST. `tslc/src/tslc/ir/segments.py` represents a body as recursive `RawText` and recognized `Region` values. `ir/scan.py` lexically protects comments and string literals while locating nested regions, and `lower/region_handlers/registry.py` dispatches regions for operations such as intrinsics, helpers, variables, masks, memory, lane access, control flow, types, values, and completion. `lower/lowerer.py` translates these regions into backend-aware lowered specializations and dependencies.

The limit of that abstraction is important. `tslc/src/tslc/lower/raw_text.py` returns literal raw text unchanged, and `tslc/CHARTER.md` explicitly rejects parsing general C++ or Rust expressions. Raw fragments therefore have to remain valid for the selected backend family, or authors must isolate differing semantics in regions. This design is pragmatic and keeps the compiler small, but it weakens any claim that TSIL is a fully language-neutral IR.

`tslc/src/tslc/backend/translation.py` defines the `BackendDialect` protocol. Backends translate already-decided semantics and render models, rather than selecting primitives. Generated outputs include CMake-oriented C++ projects and Cargo-oriented Rust projects, build/value-test sources, coverage and benchmark plans, and editor/authoring projections.

### 3.4 Source breadth

Static inspection found 23 extension declarations in `tsldata/extensions/extension.tsl`, spanning scalar and generic forms, x86 families and compiler-vector overlays, ARM NEON/SVE and fixed-width SVE profiles, RISC-V RVV, WebAssembly SIMD, CUDA, and oneAPI FPGA families. This declaration breadth should not be confused with equally mature implementation or runtime validation.

The checked-in `coverage/primitive-coverage-inventory.md` reports:

- 104 distinct primitive names;
- 160 source declarations, 172 variants, 146 name/signature pairs, and 3,315 implementation leaves;
- 157,584 emitted specializations under the inventory's probe;
- 96 primitives labeled build-verified, eight that lower cleanly but were not build-verified, and no partially lowering or non-lowering primitive in that particular probe.

The same report warns that emission is not a compile guarantee, checks only ten scalar types, probes a limited group of scalar and x86 profiles, and does not show exact C++/Rust parity. Its emitted-extension summary is much narrower than the 23 declared extension families. These caveats make the inventory good artifact-health evidence but poor evidence for cross-architecture performance portability.

The corpus itself is semantically richer than a bag of intrinsic strings. For example, `tsldata/primitives/arithmetic/fundamental.tsl` defines `add` with an arithmetic semantic contract, authored tests, and implementations for scalar/generic/compiler-vector, x86, NEON, WebAssembly, SVE, and RVV families. This supports the claim that the source format can express broad specialization. It does not establish correctness or performance on those targets.

### 3.5 Testing, verification, and benchmark infrastructure

Static search found 1,354 Python test functions across 105 `test_*.py` files. The suite includes parser, catalog, selection, lowering, diagnostics, backend, authoring/LSP, build-project, and generated-value-test concerns. This is notable engineering investment, but none of those tests was run for this assessment.

`tslc/tests/test_build_verify.py` defines focused generated-project build gates. `tslc/tests/test_value_tests.py` explicitly separates substrate compilation from executable value testing and includes definitions for C++ and Rust, AVX2 and SSE differential cases, NEON/QEMU cases, and broader corpus gates. The CI configurations describe SDE, QEMU, and Wasmtime runners. These files establish intended methodology and some target coverage; they do not establish that the current revision passes, that all declared architectures are exercised, or that the tests are statistically or semantically sufficient.

Variant benchmarking is carefully designed in `docs/variant-benchmarking.md`: generated candidates must pass a correctness gate before timing, scenario data can be authored through typed benchmark specifications, and policies can select variants. Nevertheless, the checked-in inventories show that this facility is incomplete:

- `coverage/benchmark-shape-inventory.md` reports 28 C++ profiles, seven benchmarked signature shapes, 53 not-applicable shapes, seven coverage gaps, and 6,590 strict issues.
- `coverage/benchmark-rust-shape-inventory.md` reports 28 profiles, 106 reports, zero benchmarked shapes, 53 not-applicable shapes, 14 gaps, and 4,763 issues; nearly all reports are report-only rather than policy-mapped.

No committed generated-code timing dataset was found for the central compiler/library claims. `tslc/src/tslc/maintenance/performance_benchmark.py` is a compiler self-performance harness, but its tests exercise harness behavior rather than supplying a research evaluation. The word “benchmark” in this workspace therefore often denotes benchmark *generation, coverage, or planning*, not demonstrated performance.

### 3.6 Database relevance and the adjacent sort prototype

`todo/db-operators.md` says that TSL is a research prototype from database engineering and enumerates column-oriented transformation, predicate, selection, count, aggregation, and consumption patterns. The C++ and Rust examples implement many of these patterns, including dense and masked transforms, predicates, mask layouts, selection-vector production/refinement/consumption, and aggregation. These examples show API utility and dual-language reach.

They are not a database system. The example READMEs describe them as generated-library consumers rather than compiler tests, and the repository contains no inspected query optimizer, execution engine, storage manager, transaction system, or integration patch for an external DBMS. There are no TPC-H, TPC-DS, SSB, ClickBench, or comparable results.

The `test-sort` subtree implements a homogeneous lexicographic multi-column co-sort prototype with per-column directions, payload permutation, equal-run discovery, serial and parallel variants, incremental three-way variants, and a bitonic leaf. `multi-column-sort-plan.md` records a small set of local observations, including close results between two-way network and post-sort three-way variants and less than one percent scan reduction for one incremental variant. Those observations are useful negative engineering results, not a paper evaluation: hardware and toolchain detail, variance, repeated-trial statistics, broad baselines, and database workloads are missing.

More importantly, `test-sort/CMakeLists.txt` defaults to fetching a generated TSL release (`v0.2.5`) and only optionally accepts a local source directory. Its results therefore cannot be attributed to the current compiler revision without an explicitly recorded local configuration. The sort work should be assessed as a separate potential publication unit, not used to inflate the evidence for `tslc` or `tsldata`.

## 4. Candidate scientific contributions

This section deliberately separates an implemented mechanism from a defensible scientific claim. “Partially supported” means that the mechanism exists, not that novelty, superiority, or generality has been established.

### 4.1 Scientific-novelty candidate: single-corpus, multi-language, multi-paradigm generation

**Exact proposed claim.** One authored SIMD primitive corpus plus a compact vocabulary of typed semantic islands can generate C++ and stable Rust libraries across fixed- and scalable-vector models, while making the cost of a new language or vector paradigm depend mainly on genuinely new semantic concepts rather than on the full primitive × type × ISA × language product.

**Repository evidence.** `tsldata/` is one authored corpus. `tslc/src/tslc/ir/segments.py` defines `RawText` and `Region`; `ir/scan.py` handles nesting while protecting comments and literals; `lower/region_handlers/registry.py` registers semantic forms; `lower/lowerer.py` produces typed lowered specializations; and the C++ and Rust backend dialects consume shared lowered facts. `tslc/DESCRIPTION.md` documents fixed/scalable target families, backend-owned C++/Rust projections, and the rule that substantially different syntax requires additional typed TSIL rather than compiler-side raw-string rewriting.

The precise claim is **one source-of-truth corpus and shared semantic model**, not literally one undifferentiated codebase: the compiler necessarily contains backend-specific C++ and Rust projection and rendering code. Repository co-location alone is not evidence of semantic sharing.

**Potentially new element.** The potentially publishable result is a domain-specific sufficiency and extensibility result: a small, classifiable semantic surface may be enough to preserve hand-authored intrinsic control while crossing both a programming-language boundary and a fixed/scalable vector-model boundary. If integration effort demonstrably scales with new semantic obligations rather than corpus size, that would be more than a feature checklist.

**Established practice.** Multi-backend code generation, external DSLs, island grammars, staged/generative programming, typed compiler IRs, backend dialects, and preserving uninterpreted source fragments are established techniques. The project's 2024 preprint articulates the broad generator thesis, but it is not peer-reviewed and may legitimately be superseded. MLIR's Vector dialect is a much richer typed and retargetable vector IR.

**Prior-art risk.** “One source, several outputs” is routine compiler engineering, and “generators ease extension” is a generic motivation. The mechanism may only appear novel because the repository calls its regions “TSIL.” The claim survives only if the work identifies a stable minimal boundary, quantifies real cross-language reuse and change amplification, preserves code quality, and reports where the approach fails.

**Contribution type.** Architectural, methodological, and empirical; not currently algorithmic or formal.

**Generalization.** Plausible for low-level libraries whose bodies need exact target control but whose language/architecture differences concentrate at identifiable semantic pressure points. Generalization to unrelated languages remains constrained because raw fragments are preserved and the compiler charter explicitly describes a C-like-source backend family.

**Likely skeptical review.** “Multi-backend generators are old. C++ and Rust are similar enough that sharing text is unsurprising, and adding targets through data files only shows competent architecture. Where is the measured reduction in change amplification, the fair counterfactual, the generated-code parity, and the evidence that a third paradigm does not break the abstraction?”

**Current support level.** One corpus, two backend families, and fixed/scalable machinery are implemented. Effective semantic sharing, bounded integration effort, superiority, and generality are unmeasured.

### 4.2 Scientific-novelty candidate: deterministic source-driven specialization and closure

**Exact proposed claim.** Declarative extension, type, and feature facts can drive deterministic selection and dependency closure for a portable SIMD library across many profiles.

**Repository evidence.** `catalog/model.py` defines typed catalog entities; `select/selector.py` ranks candidates by extension distance, type specificity, feature count, and source order; `_GenerationSession._generate_profile` in `pipeline.py` computes a profile-scoped worklist, lowers selected bodies, discovers dependencies, prunes unresolved specializations, and finalizes the result. Diagnostics expose ambiguity and missing coverage.

**Potentially new element.** The precise fact model and diagnostic presentation may be useful and unusually complete for SIMD-library generation.

**Established practice.** Applicability predicates, overload resolution, deterministic rule priority, dependency-graph closure, and reachability pruning are standard compiler and build-system techniques. The ranking is a literal tuple order, not a new search, constraint-solving, or optimization method.

**Prior-art risk.** The earlier project manuscript uses external source data, selection, and generation stages, so the current paper should explain the evolution rather than pretend the idea appeared only in this repository. This is not a prior-publication bar. The scientific risk comes from comparable compilers using target-feature predicates, overload selection, and dependency closure under established terminology.

**Contribution type.** Architectural and artifact-oriented.

**Generalization.** The pattern generalizes, but the particular facts and order are project policy. No evidence shows that the policy is optimal or broadly reusable.

**Likely skeptical review.** “This is conventional compiler plumbing made explicit and typed. Determinism and good diagnostics are software quality, not a scientific contribution.”

**Current support level.** Supported as engineering; likely unpublishable as a standalone scientific claim.

### 4.3 Scientific-novelty candidate: catalog-derived cross-backend verification

**Exact proposed claim.** Primitive contracts and authored cases can generate compile, value, golden, and differential tests across languages, profiles, and runners, reducing semantic drift in an architecture-specific SIMD library.

**Repository evidence.** Semantic contracts and authored tests appear in primitive data; the compiler owns value-test planning and rendering; `test_value_tests.py` defines golden and differential gates for C++ and Rust; `test_build_verify.py` covers generated builds; CI configuration describes native and emulated runners. Coverage reports distinguish planned, emitted, build, and value-test states.

**Potentially new element.** A single catalog-derived plan spanning primitive semantics, target profiles, C++/Rust generation, and emulator-aware execution could support a useful empirical testing methodology.

**Established practice.** Test generation, property-based testing, metamorphic testing, differential testing, cross-compiler testing, mutation analysis, and translation validation are mature areas. Csmith demonstrated large-scale differential compiler testing, while Alive2 demonstrates the much stronger bar of an explicit semantics and bounded translation validation.

**Prior-art risk.** The existing system appears to instantiate known testing patterns; no new oracle construction, case-generation algorithm, coverage criterion, or fault model was found.

**Contribution type.** Potentially methodological and empirical; currently an engineering infrastructure contribution.

**Generalization.** More plausible than the selector claim. The test planner could inform other generated low-level libraries if its contracts and oracle assumptions were specified independently of TSL.

**Likely skeptical review.** “There is extensive testing code, but where are the bugs found, mutation score, comparison to handwritten suites, oracle independence, false-positive analysis, and cost? A large test suite is not a testing research result.”

**Current support level.** Infrastructure is supported. Effectiveness and novelty are unsupported.

### 4.4 Scientific-novelty candidate: correctness-gated variant selection

**Exact proposed claim.** The generator can benchmark several valid primitive implementations, reject incorrect variants, and choose a target-specific policy without embedding the choice in source code.

**Repository evidence.** `docs/variant-benchmarking.md` specifies correctness-before-timing, typed benchmark scenarios, report generation, and policy selection. `PrimitiveBenchmarkSpec` exists in `catalog/model.py`; benchmark maintenance and rendering modules implement the workflow.

**Potentially new element.** The current measure-and-select workflow is not new, but the generated cross-language candidate space creates two testable opportunities: (1) whether variant rankings and policies transfer between corresponding C++ and Rust specializations, and (2) whether typed transitive capability/provenance facts can prune calibration safely without excluding an oracle winner.

**Established practice.** Empirical algorithm selection and autotuning are foundational to FFTW, ATLAS, SPIRAL, Halide/auto-scheduling, TVM, and many compiler systems. Correctness-gating candidates is necessary methodology, not a novel optimization.

**Prior-art risk.** Very high for the current feature. Without a new pruning/search method, transfer result, robustness method, or insight about SIMD variants, this is an integration of known techniques. A cross-language study must also be broad enough to teach more than “different compilers sometimes produce different code.”

**Contribution type.** Engineering today; potentially algorithmic for safe capability-constrained pruning or empirical for cross-language policy transfer.

**Generalization.** The workflow could generalize to generated low-level libraries, but the checked-in coverage is incomplete and the Rust inventory records no benchmarked shapes. No portability or policy-transfer result exists yet.

**Likely skeptical review.** “This is a careful benchmark harness and policy file, not a new autotuner. Exhaustive measurement plus winner selection is established, and there are no committed results showing useful pruning, robust choices, or cross-language transfer.”

**Current support level.** Correctness-gated candidate planning, measurement, reduction, and policy consumption are substantially implemented, although coverage is incomplete. A new tuning method or general empirical result is unsupported.

### 4.5 Domain-specific candidate: performance-portable database operator substrate

**Exact proposed claim.** A generated primitive corpus can serve as a language- and architecture-portable substrate for vectorized database operators using masks and selection vectors.

**Repository evidence.** `todo/db-operators.md` defines database-shaped helper categories. C++ and Rust examples exercise dense and masked transformations, predicates, selection-vector production and refinement, count, aggregation, and consumption. The primitive and extension corpus supplies the lower-level operations.

**Potentially new element.** Stable-Rust generation from the same source corpus and uniform support for fixed- and scalable-vector targets could be valuable if demonstrated in a database engine. Non-obvious findings about mask representation, vector length, fallback behavior, or cross-language code generation could become research contributions.

**Established practice.** Vectorized database execution, selection vectors, mask-based processing, hardware-oblivious SIMD abstraction, and generated query code are well established. The Template Vector Library, Voodoo, Weld, and VOILA are directly relevant.

**Prior-art risk.** Very high. The same research lineage did publish the Template Vector Library specifically for in-memory column stores. The unrefereed TSLGen preprint also contains a database-style range-count experiment, which a new submission may extend or replace but cannot present as newly performed if it reuses the same result.

**Contribution type.** Domain adaptation and potential systems/empirical contribution.

**Generalization.** It could generalize to analytical engines, but the current evidence stops at small library-consumer examples.

**Likely skeptical review.** “This is a SIMD library with database-flavored examples. There is no optimizer, execution engine, workload, end-to-end result, or demonstrated database insight.”

**Current support level.** API feasibility is supported; performance portability, database impact, and scientific novelty are unsupported.

### 4.6 Adjacent algorithmic candidate: multi-column co-sort

**Exact proposed claim.** Equal-run discovery and incremental multi-way refinement can accelerate lexicographic multi-column sorting while preserving payload permutation and parallelism.

**Repository evidence.** `test-sort/docs/multi-column-sort.md` documents serial/parallel and incremental variants; `benchmark_multicolumn_gbench.cpp` defines a broad intended benchmark matrix over types, lane widths, data distributions, directions, cache-relative sizes, and threading; `multi-column-sort-plan.md` records implementation status and a few local measurements.

**Potentially new element.** There may be an algorithmic or data-dependent scheduling insight in deciding when to refine equal runs, scan boundaries, or replay payloads.

**Established practice and uncertainty.** Lexicographic sorting, segmented/equal-run refinement, radix and comparison sorting, permutation vectors, SIMD sorting networks, and parallel quicksort are heavily studied. A focused related-work search for this exact sort design was not completed because it is outside the requested `tslc`/`tsldata` center of gravity.

**Contribution type.** Potentially algorithmic and empirical, but separate from the compiler.

**Generalization.** Potentially relevant to columnar engines if integrated and evaluated.

**Likely skeptical review.** “The current results are a handful of local timings, include outcomes below one percent, lack strong database and sorting baselines, and may not exercise the workspace compiler at all.”

**Current support level.** Prototype support only. No novelty claim is presently defensible, and it must not be counted as evidence for `tslc` or `tsldata`.

## 5. Engineering and artifact contributions

### 5.1 Engineering novelty

The following work is difficult and comparatively polished even though it is not, by itself, scientific novelty:

- **Typed compiler ownership.** Frozen catalog, selection, lowering, backend, render, verification, and authoring models prevent raw source dictionaries from leaking through the compiler. The module boundaries in `tslc/src/tslc/` are unusually explicit for a research prototype.
- **Traceable specialization decisions.** The selector exposes applicability and deterministic priority, and the authoring commands can explain or preview selected specializations. This is valuable for debugging a combinatorial corpus.
- **Safe semantic-island scanning.** Nested regions are recognized without naively rewriting strings or comments. This is a non-trivial implementation detail and a defensible design compromise.
- **Dependency-aware lowering.** Profile-scoped worklists, dependency discovery, pruning, and diagnostics turn scattered primitive bodies into a coherent generated library rather than isolated snippets.
- **Dual-language generation.** C++ and Rust outputs, including build/value-test projects, increase artifact usefulness. Stable Rust is a practically interesting target given that the official `portable_simd` API remains experimental ([Rust `portable-simd`](https://github.com/rust-lang/portable-simd), [`core::simd` documentation](https://doc.rust-lang.org/core/simd/struct.Simd.html)).
- **Correctness-gated variant policies.** The generated benchmark path preserves candidate identity, validates correctness before timing, detects stale or foreign policies, and keeps ordinary builds on the authored default. This is unusually careful systems engineering even though measure-and-select autotuning is established.
- **Authoring and maintenance surfaces.** Check, explain, preview, dump, coverage, diagnostics, LSP/editor support, and explicit maintenance commands make the corpus more sustainable.
- **Verification orchestration.** Build and value-test planning across compilers, profiles, languages, and emulators is a meaningful engineering achievement.

These qualities make the repository potentially useful to other researchers. They do not establish that the underlying research problem has a new solution.

### 5.2 Artifact value

The integrated artifact has substantial potential value:

- a non-trivial authored corpus rather than toy examples;
- explicit target-family and toolchain facts;
- fixed- and scalable-vector extension declarations;
- reusable C++ and Rust generated consumers;
- deterministic generation and source-oriented diagnostics;
- a large static test suite and CI designs for native and emulated execution;
- coverage inventories that expose missing support rather than implying fantasy completeness;
- architecture documentation detailed enough to support independent inspection.

The artifact could be valuable as:

- a benchmark corpus for SIMD code generation and testing;
- a substrate for database operator experiments;
- a case study in rebuilding a research generator with typed compiler boundaries;
- an educational or comparative artifact for cross-language low-level generation.

### 5.3 Artifact weaknesses

The strongest artifact claims are still qualified:

- The package version is `0.1.0a1` in `tslc/pyproject.toml`, signaling pre-alpha maturity.
- Declared architecture breadth is much larger than the checked-in build/value evidence. The principal primitive coverage inventory is x86-centric.
- C++ and Rust parity is explicitly incomplete.
- The Rust benchmark inventory reports no benchmarked shapes.
- CI and test definitions were not executed in this assessment, so current reproducibility is unknown.
- No stable public dataset of generated-code performance results was found.
- No external adoption, independent reproduction, or downstream case study was evidenced in the repository.
- The raw-text boundary makes the corpus less backend-neutral than a typed IR claim might imply.
- The adjacent sort experiment defaults to an external generated release and uses unpinned network fetches in its default CMake setup, which is not yet a self-contained research reproduction package.

### 5.4 Incremental or non-novel work

The following should not be promoted into paper contributions without new evidence:

- moving from untyped dictionaries to frozen dataclasses;
- use of a parser generator, visitor-style handlers, protocols, and templates;
- CMake/Cargo project generation;
- configuration discovery and command-line interfaces;
- an LSP and editor integration backed by compiler facts;
- deterministic sorting and diagnostics;
- adding another ISA declaration or intrinsic mapping;
- adding Rust syntax translation to an existing generator architecture without demonstrating corpus-level semantic sharing, bounded integration effort, or a general cross-language result;
- build matrices, coverage markdown, and benchmark manifests;
- convenience helpers for masks or selection vectors;
- refactoring the earlier generator into smaller modules.

These are all useful. Treating them as research novelty would invite the “just a library” or “just code generation” rejection.

## 6. Closest related work

### 6.1 Status and proper role of the 2024 TSLGen manuscript

**“Designing and Implementing a Generator Framework for a SIMD Abstraction Library”** is a project-authored arXiv manuscript ([Pietrzyk et al., 2024](https://arxiv.org/abs/2407.18728)). Its abstract presents TSLGen as an end-to-end generator for the Template SIMD Library, motivated by maintainability and extensibility, and reports framework evaluation and comparable performance. The manuscript describes external source specifications, implementation selection, code generation, validation/build support, and a database-style range-count use case.

The local `tslc/README.md` calls `tslc` a clean restart of the earlier `tslgen` generator, so the manuscript is highly relevant to understanding the project's intended research thesis. It is **not**, however, a refereed publication. DBLP classifies it only as CoRR, and no proceedings or journal version was found in the literature search. SIGMOD and PVLDB explicitly distinguish preprints from prior refereed publications and allow work available on arXiv to be submitted.

The correct consequences are:

- the broad generator thesis remains eligible for a first peer-reviewed publication;
- a submission may subsume and substantially revise the 2024 manuscript rather than invent a wholly different central idea;
- the manuscript should be disclosed or cited according to the target venue's anonymity policy and the paper should explain how the current system and evidence supersede it;
- its claims cannot be treated as peer-validated evidence, and its old experiments cannot silently be relabeled as new results;
- type safety, Rust output, semantic regions, diagnostics, and verification breadth become scientific contributions only if the paper connects them to a general claim and evidence.

The manuscript is therefore a project baseline and statement of intent, not the most damaging external novelty comparison.

### 6.2 Same-lineage database and hardware work

The **Template Vector Library** paper, “Hardware-Oblivious SIMD Parallelism for In-Memory Column-Stores,” already argues for a single-source SIMD abstraction that allows database developers to write hardware-oblivious column-store operators and map them efficiently across extensions ([CIDR 2020 page](https://vldb.org/cidrdb/2020/hardware-oblivious-simd-parallelism-for-in-memory-column-stores.html)). This is the most damaging comparison to a database-facing abstraction claim.

“Program your (custom) SIMD instruction set on FPGA in C++” extends the same general line toward treating FPGA hardware as a SIMD target with a consistent programming surface ([CIDR 2024 page](https://vldb.org/cidrdb/2024/program-your-custom-simd-instruction-set-on-fpga-in-c.html)). Consequently, `tsldata` declarations for oneAPI FPGA targets are not, without new mechanisms and results, a first demonstration of that idea.

Any credible paper must explain whether `tslc`/`tsldata` supersede, reproduce, or materially extend these systems. Omitting this lineage would be fatal in review.

### 6.3 Portable SIMD libraries and standards

| Work | What it already provides | Possible `tslc`/`tsldata` delta | Novelty consequence |
|---|---|---|---|
| [Google Highway](https://github.com/google/highway) | A mature performance-portable, length-agnostic C++ SIMD interface, runtime dispatch, and broad fixed/scalable target support | Source-generated library, catalog diagnostics, and Rust output | Mostly implementation architecture unless measured benefits or new semantics are shown |
| [xsimd](https://github.com/xtensor-stack/xsimd) | Unified C++ wrappers over x86, ARM, WebAssembly, Power, and RISC-V families with substantial ecosystem use | Declarative generation, semantic contracts, authoring tools, Rust | Artifact differentiation, not first portable SIMD abstraction |
| [IBM Generic SIMD Library](https://research.ibm.com/publications/simple-portable-and-fast-simd-intrinsic-programming-generic-simd-library) | Portable mappings with comparable performance and source-code reduction | More generated tooling and corpus management | Weakens performance-portability and productivity novelty |
| [Vc](https://onlinelibrary.wiley.com/doi/abs/10.1002/spe.1149) and [Sierra](https://sierra-lang.github.io/) | Earlier portable vector types and compiler-supported portable vector programming | Different generation and compatibility choices | Establishes a long history of this abstraction class |
| C++ `std::simd` | A standardized portable data-parallel type; the official WG21 record shows the proposal merged into the working paper ([WG21 N5002](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2024/n5002.html)) | Greater control over target mappings and generated projects | Raises the practical-significance bar: why is a separate library needed? |
| Rust `core::arch` and `portable_simd` | Official architecture intrinsics are explicitly target-specific ([`core::arch`](https://doc.rust-lang.org/beta/core/arch/index.html)); portable SIMD remains an experimental nightly project ([repository](https://github.com/rust-lang/portable-simd)) | A generated stable-Rust surface could be useful now | A time-sensitive artifact advantage, not necessarily a durable research contribution |

The required comparison is not simply feature count. A research paper would need to show a meaningful outcome—performance portability, fewer unsupported combinations, lower porting effort, fewer semantic defects, or a capability unavailable through these alternatives.

### 6.4 Vector IRs, DSLs, and generative systems

The [MLIR Vector dialect](https://mlir.llvm.org/docs/Dialects/Vector/) models fixed and scalable vectors, provides typed vector operations, and supports progressive lowering from virtual vector abstractions to target hardware. It is a more semantically complete answer to retargetable vector IR than raw text plus semantic islands. `tslc` may be much lighter and better suited to preserving hand-authored intrinsics, but that is a design trade-off, not demonstrated novelty.

Generative and autotuning precedents are extensive:

- [Halide](https://people.csail.mit.edu/jrk/halide12/) separates algorithm from schedule for high-performance image code.
- [SPIRAL](https://www.spiral.net/) generates and searches platform-tuned implementations from mathematical structure.
- [FFTW](https://www.fftw.org/) combines generated codelets and runtime planning.
- [TVM](https://www.usenix.org/conference/osdi18/presentation/chen) uses a compiler stack and learned cost models to optimize tensor programs across hardware.

Against these systems, `tslc` does not currently offer a new scheduling language, search algorithm, cost model, formal algebra, or optimizer. Its variant benchmarking is a useful integration, but the nearest established systems go much further scientifically.

### 6.5 Database execution and query compilation

Several database systems papers already occupy the conceptual space around vector abstraction and generated execution:

- [Voodoo, PVLDB 2016](https://www.vldb.org/pvldb/vol9/p1707-pirk.pdf) presents a declarative vector algebra intended to abstract SIMD, caches, and heterogeneous hardware, with a MonetDB backend and empirical evaluation.
- [Weld](https://dawn.cs.stanford.edu/publications/weld) introduces a common IR and runtime for cross-library optimization in data-intensive applications ([CIDR paper](https://people.eecs.berkeley.edu/~matei/papers/2017/cidr_weld.pdf)).
- [VOILA, PVLDB 2021](https://www.vldb.org/pvldb/vol14/p1067-gubner.pdf) generates execution-engine flavors across the scalar/vectorized design space and evaluates database workloads against compiled and vectorized engines.
- Kersten et al., [“Everything You Always Wanted to Know About Compiled and Vectorized Queries But Were Afraid to Ask,” PVLDB 2018](https://www.vldb.org/pvldb/vol11/p2209-kersten.pdf), provides the sort of systematic query-workload and microarchitectural comparison expected of a database execution paper.
- Rosenfeld et al., [“The Operator Variant Selection Problem on Heterogeneous Hardware,” ADMS@VLDB 2015](https://www.viktor-rosenfeld.com/assets/publications/Rosenfeld_2015_The-Operator/Rosenfeld_2015_The-Operator.pdf), already generate thousands of selection and aggregation variants and show that the best variant is device-dependent. This is the most damaging comparison to a simple “hardware-aware operator selection” idea.

These works already provide IRs, execution models, optimizer integration, or database-system evaluation. `tslc` currently provides a lower-level primitive library. That can be a valuable substrate, but a substrate is not automatically a database research contribution.

A database paper based on `tslc` must go beyond ordinary variant selection. The plausible distinction is that `tslc` exposes the **transitive semantic capability closure** of a plan—native, composed, fallback, unsupported, required features, dependencies, and benchmark-attested variants—rather than only a device label or a set of measured operator implementations. Whether that distinction changes useful plan decisions is an open empirical question, not an existing result.

### 6.6 Verification and testing precedents

If generated verification becomes the central story, the evaluation bar comes from mature compiler-testing research:

- [Csmith, PLDI 2011](https://users.cs.utah.edu/~regehr/papers/pldi11-preprint.pdf) combines random well-defined C generation with differential testing and substantiates effectiveness through hundreds of real compiler bugs.
- [Alive2, PLDI 2021](https://pldi21.sigplan.org/details/pldi-2021-papers/5/Alive2-Bounded-Translation-Validation-for-LLVM) defines explicit IR semantics, bounded translation validation, and a deployed evaluation that found dozens of previously unknown LLVM bugs.

`tslc` need not match formal translation validation to be publishable, but it would need a new fault model or oracle, real or seeded defects, comparative detection results, and a cost analysis. Merely generating many tests is far below this bar.

### 6.7 Related work that any credible paper must include

At minimum:

1. the 2024 TSLGen arXiv manuscript as the earlier version of this project, not as a refereed external baseline;
2. the Template Vector Library and its database evaluation;
3. Highway, xsimd, C++ `std::simd`, and Rust portable SIMD;
4. MLIR Vector for typed vector semantics and lowering;
5. Voodoo, VOILA/Kersten et al., and Rosenfeld et al.'s operator-variant selection work for database execution context;
6. SPIRAL/FFTW/TVM if variant selection or autotuning is claimed;
7. Csmith/Alive2 and more focused differential/property-testing work if verification is claimed.

The strongest peer-reviewed novelty comparisons are TVL for hardware-oblivious database SIMD, MLIR Vector and generative systems for semantic lowering, and Rosenfeld et al. for hardware-dependent operator selection. The TSLGen preprint is important for continuity and research integrity, but it does not itself consume the peer-reviewed publication opportunity.

## 7. Novelty assessment

### 7.1 Scientific novelty

No strong scientific novelty is currently *demonstrated*, but there is a credible candidate for a first peer-reviewed publication.

The proposed three-part framing has the following scientific hierarchy:

- **One source corpus, multiple generated languages:** a meaningful supporting claim and artifact result, but weak novelty by itself. The paper must measure effective semantic sharing, not merely count files in one repository.
- **Autotuning:** established in its current correctness-gated measure-and-select form. A new pruning method, cross-language transfer result, or robust multi-scenario policy could become scientific; none is demonstrated yet.
- **Generator-driven integration of new paradigms:** the strongest research seed, provided “fast” is replaced by a falsifiable change-amplification claim and “paradigm” means a structurally different language or vector model rather than one more intrinsic table.

The most plausible concept is the **typed semantic-island boundary**: it seeks a middle ground between opaque intrinsic templates and a full vector IR. The research question is not whether regions and raw text exist, but **how much semantics must be lifted** to retarget a large, hand-optimized SIMD corpus without losing target-specific control. That could support a publishable design insight if the boundary were formalized, compared to templates and fuller IRs, and quantified over the corpus. The repository currently provides implementation evidence only. It does not define a formal boundary, measure semantic lift or duplicated target text, prove preservation, or perform the necessary ablations.

The selector and dependency closure are clear but conventional. The generated verification machinery is broad but uses established testing patterns. The variant policy system is a limited form of a long-established autotuning idea. The database helpers adapt known vectorized-execution patterns.

### 7.2 Engineering novelty

Engineering novelty is considerably stronger:

- the repository treats a SIMD corpus as compiler input rather than scattering template logic;
- it has unusually explicit typed ownership and diagnostics;
- it combines semantic islands, dependency closure, dual-language rendering, verification planning, and authoring/LSP tools;
- it maintains a large corpus and exposes unsupported coverage explicitly.

This is credible software contribution language. It should not be rewritten as “a novel compiler architecture” unless a genuinely new architectural principle and comparative evidence can be isolated.

### 7.3 Artifact value

Artifact value is moderate to high, subject to reproducibility checks. The source corpus, cross-language generator, tests, profiles, examples, and reports are useful ingredients for independent research. A polished, versioned, reproducible release could merit a software publication even if the scientific idea remains incremental.

### 7.4 Domain-specific contribution

The database-oriented adaptation is currently modest. Masks, selection vectors, predicates, and column-wise aggregation are expected mechanisms in vectorized execution. The work becomes more interesting if fixed versus scalable vectors, C++ versus Rust, or fallback/dependency choices produce a new database-system insight. No such result is presently recorded.

### 7.5 Overall claim classification

| Proposed claim | Current classification | Why |
|---|---|---|
| A declarative generator architecture for portable SIMD libraries | Plausible but unproven | The project's arXiv manuscript is not prior formal publication, and no identical peer-reviewed system was found; established generative techniques and portable libraries still make a broad “first” claim risky |
| One authored corpus produces C++ and Rust | Plausible supporting claim | Both backends exist, but effective semantic sharing, backend-specific duplication, parity, and generated-code quality are unmeasured; multi-backend generation itself is established |
| New language or vector paradigms have bounded change amplification | Strongest future claim | The additive architecture and fixed/scalable plus C++/Rust pressure points exist; no retrospective or controlled integration-cost study establishes the claimed scaling behavior |
| New language-neutral SIMD IR | Not defensible | Raw target text is preserved; semantic regions are partial islands |
| New specialization algorithm | Not defensible | Deterministic tuple ranking and graph closure are standard |
| Existing correctness-gated measure-and-select autotuner is scientifically new | Not defensible | Correctness, calibrated measurement, and policy identity are rigorous engineering, but no new search/cost model is present and coverage/results are incomplete |
| Capability-constrained tuning or cross-language policy transfer | Plausible future claim | The typed candidate, provenance, and dual-language infrastructure exists; no pruning guarantee, oracle comparison, rank-transfer result, or robustness study exists |
| New correctness method | Not yet defensible | Infrastructure exists, but no new oracle/fault model or comparative study |
| New database execution architecture | Not defensible | No database engine exists in the inspected project |
| Capability-closure-aware database operator planning | Plausible future claim | `tslc` already owns native/composed/fallback and dependency facts, but no planner or experiment currently consumes them |
| High-quality research software for generated SIMD libraries | Defensible with qualification | Strong static artifact evidence, though current execution/reproducibility was not verified |
| Minimal-semantic-lift methodology for cross-language SIMD corpus maintenance | Strongest future claim | The implementation boundary exists; the metric, formalization, counterfactuals, and empirical evidence do not |

The corrected conclusion is that the project has a legitimate first peer-reviewed publication opportunity, but its potentially distinctive implementation choices have not yet been converted into a falsifiable claim that survives the peer-reviewed nearest work.

## 8. Significance and impact assessment

### 8.1 Importance of the underlying problem

The underlying problem is important. SIMD fragmentation imposes real costs on database engines, analytics libraries, compilers, and scientific software. Scalable-vector ISAs complicate assumptions about lane counts, masks, and loop structure. Maintaining C++ and Rust surfaces from one semantic corpus could have practical value. A reusable generator could let researchers explore new instruction families without repeatedly rebuilding library plumbing.

### 8.2 Why present significance is unproven

Importance of the area does not establish significance of this solution. The repository does not yet answer:

- whether generated code matches or exceeds hand-written intrinsics or mature portable libraries;
- whether the same source genuinely remains portable across fixed and scalable vectors;
- whether generated Rust is competitive with C++ and with Rust's evolving standard SIMD direction;
- whether dependency fallback creates material overhead;
- whether database operators or queries benefit;
- whether authors add or repair primitives faster and with fewer defects;
- whether generated testing catches bugs that existing suites miss;
- whether users outside the project can adopt the artifact.

Feature breadth is not a substitute for these outcomes. Likewise, 157,584 reported emitted specializations measure the Cartesian reach of a probe, not scientific impact, semantic correctness, or runtime quality.

### 8.3 Likely reviewer perception

A top-tier database reviewer is likely to see:

- no database system;
- no query-execution or optimization innovation;
- a library generator whose architecture is described in an unrefereed manuscript and whose individual mechanisms resemble known compiler techniques;
- micro-level helper examples without workload results;
- extensive implementation but no falsifiable systems claim.

A top-tier compiler reviewer is likely to see:

- no formal IR semantics;
- no new lowering, optimization, synthesis, or cost-model algorithm;
- a partial island grammar preserving raw C-like text;
- no generated-code comparison to compiler and library baselines.

A top-tier software-engineering reviewer is likely to see:

- a potentially interesting testing and maintenance artifact;
- no empirical study of defects, productivity, mutation score, or maintenance tasks.

The “just a library,” “just code generation,” and “engineering framework” risks are therefore high and justified, not superficial reviewer misunderstandings.

### 8.4 Potential impact if the missing research is done

The artifact could become significant if it enables one of two outcomes:

1. a database study that reveals a general and surprising rule about performance-portable vectorized execution across fixed/scalable ISAs and languages; or
2. a software-methodology study showing that catalog-derived semantic tests materially improve correctness or maintenance of low-level portable libraries.

In both cases the contribution would be the discovered and validated insight, with `tslc`/`tsldata` as the enabling artifact. The repository itself should not be mistaken for that insight.

## 9. Publication-readiness gaps

### 9.1 Research framing

No inspected document states a paper-ready set of research questions or falsifiable hypotheses. The repository charters state product and architecture contracts, which are valuable for engineering, but not a scientific problem definition.

Missing:

- an explicit statement that the submission supersedes the 2024 TSLGen preprint, together with a novelty comparison against peer-reviewed systems rather than against the project itself;
- one central research question, rather than a list of generator features;
- a precise definition of “one source”: one authored primitive corpus and shared semantic facts, not an absence of backend-specific compiler code;
- a falsifiable hypothesis that paradigm-integration cost tracks newly introduced semantic obligations rather than the primitive × type × target × language product;
- if autotuning is claimed scientifically, a separate hypothesis about safe pruning, policy transfer, or robustness that improves on exhaustive measure-and-select;
- a definition of “performance portability,” “maintainability,” or “semantic equivalence” appropriate to the chosen claim;
- a scope statement identifying which target families and primitive shapes are scientifically relevant.

### 9.2 Formal and technical depth

Present:

- typed semantic contracts;
- explicit selection order;
- typed region and lowering objects;
- deterministic diagnostics;
- implementation-level invariants in charters and tests.

Missing:

- a formal source and target semantics for TSIL regions;
- a correctness argument for region lowering or dependency pruning;
- an oracle-independence argument for differential tests;
- a complexity or convergence analysis where relevant;
- a new optimization/search/selection algorithm;
- a formal model of fixed versus scalable-vector portability;
- a precise statement of what raw text may assume across backends.

A formal proof is not mandatory for a database systems paper, but the absence of both formal novelty and empirical novelty leaves no strong scientific center.

### 9.3 Baselines and comparisons

No central evaluation against the strongest alternatives was found. Required baselines depend on the claim but would include:

- the previous TSLGen implementation;
- Template Vector Library;
- Google Highway;
- xsimd and/or another mature C++ SIMD library;
- C++ `std::simd`;
- Rust `core::arch` hand intrinsics and the current portable-SIMD direction;
- compiler auto-vectorization;
- hand-tuned intrinsic kernels;
- native operator implementations from a real database engine;
- Voodoo/VOILA-style generated or vectorized execution where comparison is technically meaningful;
- compile-only, handwritten, property-based, differential, and mutation-testing baselines for a verification paper.

Comparing only against scalar code would not meet a top-tier bar.

### 9.4 Workloads, datasets, and integrations

Present:

- primitive-level authored cases;
- generated example programs;
- an intended multi-column sort benchmark matrix;
- a few preliminary sort timing observations.

Missing:

- a real DBMS or query-engine integration;
- representative analytical queries;
- standard datasets or documented synthetic distributions;
- end-to-end and operator-level workloads;
- application-level case studies outside the repository;
- an evaluation showing which primitives dominate real workloads;
- a traceable connection between the current compiler revision and any measured downstream binary.

### 9.5 Architecture coverage

Present:

- declarations for many fixed and scalable target families;
- static build/value-test definitions;
- runner configurations for native and emulated targets;
- x86-heavy checked-in coverage.

Missing:

- runtime results on representative x86 generations;
- native ARM NEON and SVE results;
- meaningful RVV hardware or carefully qualified emulation results;
- WebAssembly runtime comparisons;
- evidence for CUDA or FPGA targets commensurate with their declarations;
- cross-architecture confidence intervals and failure accounting;
- an explicit distinction between declared, selected, emitted, compiled, value-tested, and performance-tested support in the paper dataset.

### 9.6 Performance and cost evidence

No central recorded evaluation was found for:

- runtime throughput or latency;
- generated code quality and instruction selection;
- performance portability;
- runtime dispatch or fallback overhead;
- compiler/generator time;
- downstream compile time;
- binary size and template/code expansion;
- memory use;
- scalability with primitive count, profile count, threads, or data size;
- sensitivity to vector length, selectivity, distribution, alignment, and cache regime;
- energy or hardware-counter behavior;
- autotuning stability and measurement noise;
- tuning regret against an exhaustive oracle, calibration cost, candidate-pruning safety, and C++/Rust ranking or winner agreement.

The benchmark shape inventories are useful readiness reports but do not answer these questions.

### 9.7 Ablation and causal evidence

Missing ablations include:

- typed regions versus raw per-backend bodies;
- one shared corpus versus separately maintained C++ and Rust implementations;
- exact specialization versus generic fallback;
- dependency closure/pruning versus eager inclusion;
- benchmark-selected versus statically selected variants;
- capability-constrained pruning versus exhaustive candidate timing;
- per-language tuning versus a transferred C++↔Rust policy;
- fixed-width versus scalable-vector formulations;
- generated tests with and without semantic contracts;
- golden versus differential versus property-based cases;
- individual database helper abstractions and mask representations.

Without ablations, even favorable performance would not show which design decision caused it.

### 9.8 Developer productivity and maintainability

Maintainability is a core motivation but is not measured. Missing evidence includes:

- controlled extension tasks;
- time and edit counts to add an ISA, primitive, backend, or semantic shape;
- the number of genuinely new semantic owners/handlers versus corpus entries and unrelated compiler stages touched;
- defect rates and review effort;
- comparison with the old TSLGen codebase and at least one mature library;
- longitudinal or reconstructed evidence for the Rust and scalable-vector integrations using a pre-defined change-amplification metric;
- independent developer tasks or qualitative study;
- sensitivity to author expertise.

Lines of code alone would be weak evidence and should not be the primary metric.

### 9.9 Correctness and reliability evidence

Present:

- many test definitions;
- authored contracts and cases;
- build/value separation;
- golden and differential strategies;
- planned emulated execution.

Missing:

- an independently run current test result;
- a stated semantic oracle for every case class;
- mutation testing;
- a corpus of historical or newly discovered defects;
- comparison with handwritten test suites;
- false-positive/false-negative analysis;
- emulator-versus-native validation;
- coverage over undefined, implementation-defined, overflow, mask, and floating-point behavior;
- a proof or validation that the generic reference is sufficiently independent of specialized implementations.

### 9.10 Reproducibility, maturity, and adoption

Positive signs include explicit configuration, deterministic output goals, generated project layouts, CI files, and checked-in coverage reports.

Remaining gaps:

- a versioned research artifact tied to a paper commit;
- documented hardware, OS, compiler, flags, runner versions, and seeds;
- raw result data and analysis scripts with outputs;
- a one-command or clearly staged reproduction that has been independently tested;
- stable dependency pinning for all downstream experiments;
- external users, citations, or independently reproduced case studies;
- a feature-complete release appropriate to software-publication review.

Because execution was prohibited, the present assessment cannot certify even the existing reproduction paths.

## 10. Storyline 1: minimal semantic lift for retargetable SIMD libraries

This is the closest-to-current-code and lowest-risk research direction. It turns the repository's most unusual design boundary into a question that can be measured and falsified. It is not yet an established result.

### Elevator pitch

- **Problem:** Portable SIMD libraries must absorb new languages, ISAs, and vector models without multiplying hand-maintained implementations or allowing their semantics to drift.
- **Observation:** Intrinsic bodies need exact target control, but only a limited set of pressure points—types, lanes, masks, memory, control, safety, and dependencies—appear to require shared compiler semantics.
- **Idea:** Author one primitive corpus, keep target-specific text opaque, and lift only those pressure points into typed semantic islands that backend dialects project into C++ and stable Rust.
- **Core hypothesis:** Adding a genuinely new language or vector paradigm costs work proportional to its new semantic obligations, not to the full primitive × type × ISA × language product.
- **Evidence required:** Measure effective corpus sharing, change amplification, C++/Rust and fixed/scalable parity, generated-code quality, and the approach's explicit failure envelope against raw-template and fuller-IR counterfactuals.
- **Autotuning role:** Generated, correctness-gated variants strengthen the system story, but autotuning becomes a research result only if capability facts safely reduce calibration or policies/rankings transfer across generated languages.
- **Payoff if true:** A practical middle point between duplicated intrinsic libraries and a full vector IR, with a reusable rule for integrating future low-level execution paradigms.

### Central thesis

A single authored corpus plus a small, explicitly typed set of semantic islands is sufficient to retarget hand-optimized SIMD primitives across C++ and stable Rust and across fixed- and scalable-vector ISAs, with integration effort governed mainly by newly introduced semantic concepts rather than corpus-product size, while preserving raw target control and generated-code quality.

### Research problem

Hand-written portable SIMD libraries face a tension. Pure templates and per-ISA bodies retain exact intrinsic control but duplicate semantics and are difficult to retarget. A full vector IR enables principled lowering but requires the compiler to model and optimize much more of each body. `tslc` occupies a deliberate middle point: raw target text stays opaque, while only shared semantic pressure points become typed TSIL regions.

The research problem is to determine whether that middle point has a reproducible structure rather than being an ad hoc implementation. The paper must identify which semantics actually need lifting, what remains safely raw, how the boundary changes when adding a backend or scalable-vector family, and where the approach fails. A database system is not required for this compiler/generative-programming story, although database operator kernels can provide an application case.

### Proposed novelty

The proposed novelty is a **minimal-semantic-lift methodology**, consisting of:

- a precise model of bodies as opaque target fragments plus typed semantic islands;
- a taxonomy of why semantics must be lifted: target spelling, type/lane relations, mask representation, memory behavior, control, safety, or dependency closure;
- measurable quantities such as lifted-semantic coverage, backend-specific raw duplication, unsupported slots, and change amplification;
- a counterfactual evaluation against a template/raw-body design and a fuller typed-IR design or representative MLIR formulation;
- evidence that the boundary remains stable when crossing both a language boundary (C++ to Rust) and a vector-model boundary (fixed width to scalable).

The novelty is not the existence of an island grammar. Island grammars and retargetable code generation are established. The claim is that a small, classifiable semantic surface is sufficient for this difficult low-level domain and that its costs and failure envelope can be measured.

### How the three proposed ideas fit

- **Central claim — fast integration of new paradigms:** restate “fast” as bounded change amplification and test it on structurally difficult additions such as stable Rust and scalable vectors.
- **Primary supporting result — one corpus, multiple languages:** quantify how much primitive semantics and implementation content is genuinely shared, how much is backend-specific, and whether the outputs remain semantically and performance competitive.
- **Secondary or separate result — autotuning:** use the existing correctness-gated machinery as infrastructure. Claim scientific novelty only for a demonstrated cross-language policy-transfer result, safe capability-constrained pruning method, or other reproducible tuning insight.

The paper should not advertise these as three unrelated features. The first two form one coherent generative-programming thesis; the third is optional unless it produces an independently strong result.

### Candidate contributions

1. **A formalized hybrid body model and taxonomy of lifted SIMD semantics.**  
   Status: **partially supported**. `RawText`, recursive `Region` values, typed contracts, handlers, and lowering exist; the research model and taxonomy do not.

2. **A corpus-scale result quantifying how one authored source of truth is shared across C++/Rust and fixed/scalable outputs.**  
   Status: **partially supported as a mechanism**. Both backends and vector models exist, but semantic sharing, backend-specific duplication, shared availability, and parity have not been measured.

3. **A bounded-change-amplification result for integrating new languages and vector paradigms.**  
   Status: **currently unsupported**. The architecture is explicitly additive, but no retrospective or controlled study shows that effort tracks new semantic concepts rather than corpus size.

4. **Cross-language and cross-vector-model semantic and generated-code parity, together with a documented failure envelope.**  
   Status: **partially supported as infrastructure**. Backends, value-test planners, structured skips, and diagnostics exist; parity, code quality, and failures have not been analyzed as paper results.

5. **A correctness-gated generated variant space plus either a cross-language tuning-transfer result or safe capability-constrained reduction.**  
   Status: **partially supported as infrastructure and currently unsupported as science**. Candidate planning, timing, reduction, and policies exist; the transfer/pruning result does not.

### Required evidence

- Define the unit of “lifted semantics.” Count region occurrences alone only measures syntax; the study should map each region family to the semantic obligation it owns and identify which raw fragments remain backend-constrained.
- Build a compiler-owned census from the existing `Segment`, region registry, lowered contracts, implementation origins, and coverage facts. It must not parse or classify raw C++/Rust text beyond the compiler's current scanner boundary.
- Measure, for the complete corpus and a stratified primitive subset, region-family usage, backend-specific source duplication, C++/Rust shared availability, fixed/scalable reuse, structured skips, and transitive fallback/composition.
- Define two counterfactuals on a representative slice: a raw/template-only form and a more fully typed form. Measure authoring changes, unsupported cases, diagnostics, generated code, compile cost, and runtime code quality.
- Establish C++/Rust semantic parity over a predeclared operation/type/profile matrix using independent golden oracles where the generic implementation is not independent.
- Define change amplification before measuring it: count newly introduced semantic concepts and owners, corpus entries changed, backend-only exceptions, unrelated compiler stages touched, diagnostics encountered, and review effort. Lines of code alone are insufficient.
- Reconstruct the already implemented Rust and scalable-vector integrations from version history where the history is clean enough, then perform additive maintenance tasks—one new primitive shape and one backend/vector-model pressure case—under the same metric. Independent participants would strengthen the result but are not essential for a first pilot.
- If autotuning is retained as a contribution, choose one precise experiment: either compare corresponding C++/Rust variant rankings, winner agreement, and transferred-policy regret, or prove and evaluate capability-based candidate pruning against an exhaustive oracle. Merely reporting different winners is insufficient.
- Report the failure envelope: bodies that cannot be shared, regions that merely rename syntax, target-language assumptions left in raw text, and combinations that only work through generic fallback.
- Publish exact sources, generated artifacts, profiles, toolchains, raw measurements, and analysis tied to the assessed revision.

### Low-effort wins and an early kill test

The following are genuinely low effort relative to a DBMS integration because they reuse existing typed facts and test infrastructure:

1. **Semantic-lift and effective-sharing census.** Add a read-only research analysis outside the production compiler path that consumes existing segment/region, lowering, implementation-origin, and coverage facts. Report region families, shared versus backend-specific bodies, C++/Rust shared availability, fixed/scalable reuse, fallback, and unsupported slots. This is the cheapest test of whether “one source” is substantive.
2. **Retrospective change-amplification table.** Reconstruct the Rust backend and one scalable-vector integration from clean commits or design records. For each, count new semantic concepts, corpus entries changed, backend-local additions, unrelated stages touched, and post-integration gaps. This is imperfect causal evidence but a useful low-cost gate before a controlled study.
3. **Small parity slice.** Predeclare arithmetic, comparison/masks, conversion, memory, and lane-sensitive operations. Run the designed C++/Rust golden and differential tests and inspect generated code on that slice, reporting every unsupported slot.
4. **Two counterfactual authoring tasks.** Re-express representative bodies as backend-specific raw/template code and as fully typed pseudocode or an MLIR Vector sketch. Record what must be duplicated or modeled. A small transparent comparison is more credible than repository-wide LOC claims.
5. **Cross-language tuning pilot.** For the currently supported corresponding variant shapes, measure C++/Rust rank correlation, winner agreement, and regret from transferring each language's policy to the other. Compare with authored defaults and independently tuned exhaustive oracles. If too few shapes are currently shared, record that as a coverage failure rather than expanding the claim.
6. **One additive pressure test.** Choose a semantics-heavy operation crossing language and vector-model boundaries. Measure whether existing vocabulary handles it additively or forces unrelated compiler/corpus changes.
7. **Paper claim matrix.** Mark every result in the 2024 preprint as retained, replaced, or dropped, while treating the new submission as the peer-review target rather than as an extension of a prior publication.

These tasks can validate the idea before a broad hardware campaign. **Kill the central storyline** if the census shows little genuine semantic sharing, if change amplification still scales with corpus-product size, if a small region set does not explain sharing, or if the counterfactuals are no worse than TSIL. **Drop autotuning from this paper**—without killing the central storyline—if cross-language rankings do not transfer and no new safe pruning or robustness result emerges.

### Strongest baselines

- **The 2024 TSLGen preprint and prototype:** an evolution/continuity baseline, not a prior-publication obstacle. The new paper should supersede its evidence cleanly.
- **Island-grammar and embedded-DSL work:** required to show that the claim is about the measured semantic boundary, not inventing island grammars. One relevant example is the island-grammar approach to embedded concrete syntax ([Erdweg et al.](https://www.sciencedirect.com/science/article/pii/S0167642312002134)).
- **MLIR Vector:** the fuller typed-IR comparison and the strongest challenge to the need for raw semantic islands.
- **Highway and xsimd:** mature hand-maintained portable-library baselines for authoring structure, coverage, and generated-code quality.
- **C++ `std::simd`:** the standards-based portability baseline.
- **Rust hand intrinsics and current portable SIMD:** required for the stable-Rust claim.
- **Hand-written intrinsics and compiler auto-vectorization:** generated-code-quality baselines for the representative slice.
- **For any autotuning subclaim:** authored defaults, independent exhaustive C++ and Rust oracles, and ordinary per-language tuning. Cross-language policy reuse must be evaluated by regret, not only winner agreement.

The required outcome is not universal victory. A publishable result could identify a robust boundary: a compact semantic surface suffices for defined primitive classes, fails predictably for others, and reduces language/ISA change amplification without degrading code quality. The result must teach that boundary, not merely report feature counts.

### Likely reviewer objections

1. **“The arXiv manuscript is not peer-reviewed, but generating a library from data is still an obvious application of known techniques.”**
2. **“Semantic islands are an engineering compromise, not a scientific result.”**
3. **“Island grammars and retargetable generators are old ideas.”**
4. **“Highway, xsimd, TVL, and `std::simd` already solve portability.”**
5. **“The evaluation cherry-picks architectures and operators.”**
6. **“Rust is a temporary ecosystem gap rather than durable research novelty.”**
7. **“Maintainability claims are subjective and measured by the authors on their own code.”**
8. **“Raw target text undermines semantic equivalence and backend generality.”**
9. **“C++ and Rust are both C-like enough that the language-retargeting result is weak.”**
10. **“The artifact is broad but pre-alpha and not independently used.”**
11. **“Autotuning is old and distracts from the semantic-lift contribution.”**

### Response to reviewer objections

1. Treat the preprint as the manuscript being matured and make minimal semantic lift—not generic generation—the paper's testable contribution. If the literature review finds this exact method, the novelty claim fails.
2. Formalize and measure the compromise. If the measurements do not reveal a stable boundary or useful trade-off, the objection stands.
3. Cite the prior techniques and claim only the domain-specific sufficiency/failure result over a large low-level corpus.
4. It requires strong comparative results and a precise capability gap. Feature checklists are not enough.
5. It requires a pre-declared matrix, transparent exclusions, sensitivity analysis, and failure reporting.
6. Stable Rust can support significance, but the durable claim must concern cross-language semantics or maintenance rather than current API stabilization.
7. It requires independent tasks/participants or carefully designed longitudinal evidence. This is feasible but expensive.
8. It requires explicit raw-text obligations and possibly reducing the raw surface. If general retargetability requires replacing most raw text with a richer IR, that would materially change the project.
9. Add a third syntax pressure case or show why the fixed/scalable vector-model boundary is independently demanding. Do not claim arbitrary-language retargetability.
10. It requires a stable release and external reproduction; this is addressable engineering work.
11. Agree for the current measure-and-select feature. Keep it as artifact infrastructure unless cross-language transfer or capability-constrained pruning produces a separable result; otherwise omit it from the contribution list rather than overselling it.

The story succeeds only if it changes the central sentence from “we built a better generator” to “we discovered and validated a stable minimal semantic boundary for retargeting low-level SIMD libraries.”

### Suitable venues

- **GPCE:** the most realistic research venue if the paper contributes a measured generative-programming method rather than only an artifact. GPCE explicitly focuses on code generation, language implementation, model-driven engineering, and product-line development ([GPCE 2026](https://2026.ecoop.org/home/gpce-2026)).
- **Compiler Construction or PACT:** plausible with a stronger formalization and rigorous cross-target quantitative study. PACT explicitly covers compilation techniques, performance portability, and cross-layer evaluation ([PACT 2026](https://pact2026.github.io/)).
- **CGO:** aspirational if the boundary becomes a genuine code-generation technique with strong code-quality and maintenance evidence ([CGO 2027](https://conf.researchr.org/home/cgo-2027)).
- **PLDI:** still unlikely without a deeper semantic or language result. The current official scope expects novel systems, thorough empirical work, or well-motivated theory ([PLDI 2026](https://pldi26.sigplan.org/track/pldi-2026-papers)).
- **Database venues:** not the natural target for this storyline unless a database integration supplies the motivating problem and major evaluation.

### Publication gap

**Moderate research effort.**

The core mechanism and corpus already exist, and the preprint may be superseded by a peer-reviewed submission. The missing work is a precise model, effective-sharing census, change-amplification evidence, counterfactuals, parity/code-quality measurements, and a failure envelope. The autotuning subclaim additionally needs a transfer or pruning result and can be dropped if its pilot is negative. Merely completing benchmark coverage is insufficient.

## 11. Storyline 2: capability-closure-aware database operator planning

This is the higher-upside database-systems direction. It consumes `tslc` as a one-way downstream source of typed facts rather than turning the database planner into a compiler stage. It has a cheap feasibility pilot, but a credible top-tier paper requires a real DBMS integration and is a major project.

### Central thesis

A physical database optimizer that uses the transitive SIMD capability closure of each operator plan—native, composed, fallback, unsupported, required features, and benchmark-attested variants—makes more robust cross-hardware choices than ISA-name dispatch or unconstrained empirical operator tuning.

### Research problem

Database engines commonly dispatch on an ISA or machine family and then choose among operator variants using rules or measured costs. That abstraction is coarse. An operator requiring gather, mask conversion, compress/selection-vector production, or a lane-sensitive reduction may be native on one profile, composed from several primitives on another, silently routed through generic fallback on a third, and unavailable on a fourth. The transitive implementation path can matter as much as the advertised ISA.

Hardware-dependent operator variant selection is not new: Rosenfeld et al. already showed that thousands of variants can have device-dependent winners. TVL and Voodoo already pursue hardware-oblivious database execution. The proposed distinction is narrower: use compiler-owned semantic dependency and implementation-provenance facts to define the *feasible and explainable plan space before or alongside timing*, instead of treating every generated variant as an opaque benchmark candidate.

The repository contains relevant facts in `LoweredSpecialization`, profile-scoped dependency closure, propagated native/composed/fallback/unknown state, machine profiles, `tslc analyze`, coverage, and benchmark plans. It does not contain an operator-requirement model, database optimizer, cost model, or evaluation.

### Proposed novelty

Potential novelty would consist of:

- an operator requirement graph expressed in language-neutral primitive semantics and contracts;
- a join between that graph and a machine-profile-specific emitted closure, preserving native/composed/fallback/unsupported provenance and required features;
- safe pruning of infeasible or fallback-dominated physical variants before expensive calibration;
- a small, explainable cost layer that combines provenance with benchmark evidence rather than replacing semantics with a black-box tuner;
- an empirical result identifying when capability closure changes database plans and when it does not.

Simply exporting a feature matrix or selecting the fastest benchmark is not novel. The paper needs to show that transitive semantic capability is a missing planning variable with measurable predictive or pruning value.

### Candidate contributions

1. **A formal operator-requirement and profile-capability model based on transitive primitive semantics.**  
   Status: **partially supported**. Compiler-owned primitive contracts and closure facts exist; operator requirements and the join do not.

2. **A deterministic, explainable planner that distinguishes native, composed, fallback, and unsupported operator realizations.**  
   Status: **currently unsupported**. `tslc analyze` exposes ingredients, not a database planning algorithm.

3. **A pruning or ranking method that adds information beyond ISA labels and ordinary measured variant selection.**  
   Status: **currently unsupported** and the key novelty risk.

4. **A real analytical-engine integration with capability-driven physical choices.**  
   Status: **currently unsupported**.

5. **A multi-architecture evaluation showing plan quality, robustness, calibration cost, and end-to-end impact.**  
   Status: **currently unsupported**.

### Required evidence

- Define operator requirements using existing language-neutral operation, operand-role, memory, conversion, shift, mask, and dependency facts. Do not infer semantics from primitive names or raw target text.
- Define the profile capability join and its ordering or algebra: native, composed, fallback, unsupported, feature requirements, path depth, benchmark attestation, and uncertainty.
- Show sound feasibility pruning: a rejected plan must genuinely lack a required emitted closure, while a retained plan must not be claimed fast merely because it is native.
- Select workload-driven physical choice points, such as bitmask versus selection-vector production, native compress versus composed packing, gather-dependent versus scan-based access, and reduction strategies. The exact set should come from a real engine or query trace.
- Integrate the planner into at least one analytical engine, keeping it downstream of public typed compiler facts in accordance with the repository's one-way dependency rule.
- Compare against static engine defaults, ISA-name dispatch, Rosenfeld-style empirical variant selection, a benchmark oracle, and the engine's native kernels.
- Evaluate operator microbenchmarks and end-to-end workloads such as TPC-H, SSB, or ClickBench across meaningfully different x86 and ARM/scalable-vector profiles; emulation may establish correctness but not performance.
- Measure plan accuracy, variants pruned, calibration time, optimization overhead, runtime, compile time, code size, robustness to selectivity/skew/cache regime, and failure cases.
- Ablate feasibility only, provenance depth, primitive benchmark evidence, and the full capability-aware model.
- Release capability snapshots, operator requirement graphs, raw timings, optimizer decisions, exact generated artifacts, and revision/toolchain identities.

### Low-effort wins and an early kill test

There is no low-effort route to a top-tier DB paper, but there is a low-effort route to deciding whether this idea deserves one:

1. **Offline capability snapshots.** For a small set of existing profiles, project the exact emitted primitive closure, implementation state, dependencies, and feature requirements already exposed by generation/analysis. Keep this as a downstream research artifact; do not duplicate selection rules.
2. **Three operator requirement graphs.** Express three existing database-helper patterns—filter-to-mask, selection-vector production/refinement, and aggregation/consume—as semantic primitive requirements. No full query engine is needed for this pilot.
3. **Decision-divergence table.** Ask whether two profiles with superficially similar “SIMD available” labels produce different feasible/native/composed plan sets. This static table is the first novelty gate.
4. **Tiny policy comparison.** On two genuinely different native machines if available, compare a fixed default, an ISA-tag rule, a simple capability-closure score, and exhaustive microbenchmark oracle for those three operators. The score should be intentionally simple; the purpose is to test whether closure facts add signal.
5. **Planning-overhead and pruning measurement.** Report how many candidate variants are eliminated before timing and whether any eliminated candidate would have won. A single unsound prune invalidates the method.

**Kill the storyline** if capability closures do not differ at operator-relevant points, if closure/provenance does not improve prediction or pruning over ISA tags, or if exhaustive timing is cheap enough that semantic pruning adds no practical value. A positive pilot justifies the expensive DBMS integration; it does not itself justify a top-tier claim.

### Strongest baselines

- **Rosenfeld et al.'s operator variant selection:** the mandatory baseline; it already establishes device-dependent variant winners and heuristic selection.
- **Template Vector Library/MorphStore:** the same-lineage hardware-oblivious database baseline.
- **Voodoo and VOILA:** relevant semantic/generated execution baselines.
- **The integrated engine's existing physical optimizer and kernels:** required practical baseline.
- **ISA-name dispatch and exhaustive timing oracle:** necessary ablations that isolate the value of capability closure.
- **Highway, xsimd, or `std::simd`:** useful substrate baselines where the same operator can be expressed fairly.

To support the claim, capability closure must either prune materially without excluding winners, improve plan-choice robustness at lower calibration cost, or explain reproducible performance cliffs missed by ordinary device labels. Merely producing a richer capability report is not enough.

### Likely reviewer objections

1. **“Operator variant selection on heterogeneous hardware was already published.”**
2. **“Native/composed/fallback is a poor proxy for runtime cost.”**
3. **“ISA names plus microbenchmarks are sufficient.”**
4. **“The work is still a library because no real optimizer consumes it.”**
5. **“The requirement graph simply restates the generated call graph.”**
6. **“Primitive microbenchmarks do not compose into operator or query costs.”**
7. **“The method prunes a rare but fast composed implementation.”**
8. **“Architecture coverage is too incomplete and emulator-heavy.”**
9. **“The result is specific to one engine and one authored corpus.”**
10. **“Maintaining capability snapshots adds more complexity than benchmarking all variants.”**

### Response to reviewer objections

1. Explicitly position semantic feasibility/provenance as complementary to empirical variant selection and show an outcome Rosenfeld-style tuning does not provide. If no such outcome exists, the idea is not novel.
2. Do not claim provenance alone predicts cost. Combine it with sparse benchmark evidence and evaluate each component separately.
3. Use ISA-tag and exhaustive-timing baselines; the proposed method must reduce cost or improve robustness.
4. A real DBMS integration is mandatory for the full paper. Standalone examples support only the pilot.
5. Operator requirements are an independent physical-plan contract; demonstrate choice points where several primitive graphs implement the same relational operation.
6. Evaluate operator and end-to-end query outcomes and report where primitive costs fail to compose.
7. Prove feasibility pruning separately from heuristic ranking and compare every prune against the oracle.
8. Central performance claims need native hardware. Use emulators only for correctness and disclose untested declarations.
9. Replicate the capability projection on a second operator family or engine component; a full second DBMS is desirable but may not be necessary if the abstraction is public and independently checked.
10. Generate snapshots deterministically from compiler-owned facts and measure their production/calibration overhead. If exhaustive timing remains simpler and cheap, concede the point.

### Suitable venues

- **SIGMOD/PACMMOD or PVLDB/VLDB:** aspirational only after a real optimizer integration, workload-driven choices, strong baselines, and native multi-architecture results. Their current calls require a principled data-management contribution and evaluation in a data-management context ([SIGMOD 2027](https://2027.sigmod.org/calls_papers_sigmod_research.shtml), [PVLDB 2027](https://www.vldb.org/2027/submission-guidelines.html)).
- **ICDE:** similarly aspirational after a complete database study ([ICDE 2027](https://icde2027.github.io/)).
- **CIDR:** realistic for an early architecture paper after a positive pilot and a convincing prototype, because CIDR welcomes risky systems ideas and systems-building insight ([CIDR 2027](https://www.cidrdb.org/cidr2027/)).
- **A data-management-on-modern-hardware or compiler/database workshop:** realistic for the capability snapshots, three-operator pilot, and negative results.
- **CGO or PACT:** possible if the main result is cross-layer compiler capability modeling rather than query optimization, but a strong quantitative evaluation remains necessary.

No top-tier venue is justified by the current compiler facts alone.

### Publication gap

**Major research project.**

The compiler already supplies unusually rich inputs, so the low-effort feasibility pilot is real. The operator model, ranking method, DBMS integration, hardware campaign, and end-to-end evaluation still have to be created. This is the most plausible top-tier database path, but not the fastest publication path.

## 12. Alternative publication formats

| Publication unit or format | Assessment |
|---|---|
| `tslc` alone | Weak scientific unit. It is a well-structured compiler implementation, but the corpus supplies most of the demonstrated scale and domain value. |
| `tsldata` alone | Primarily a corpus/artifact. No independent formal semantics, dataset methodology, or empirical study currently makes it a research paper. |
| Integrated `tslc` + `tsldata` | The coherent unit for Storyline 1 and also the strongest artifact unit. The compiler supplies the mechanism and `tsldata` supplies the one authored corpus needed to test real C++/Rust sharing, fixed/scalable reuse, and bounded paradigm-integration cost. |
| Broader methodology demonstrated by both | Potentially publishable as “minimal semantic lift with bounded change amplification” only if the region taxonomy, effective-sharing census, integration studies, counterfactuals, code-quality evidence, and failure envelope support a general result. Without those, it remains an architecture description. |
| Database-system integration built on both | The coherent unit for Storyline 2, but the publishable object would be the capability-aware planning method and database result—not the generator itself. This is a new systems research project. |
| Empirical study enabled by both | Plausible if it establishes a general result about semantic lift, cross-language tuning transfer, performance portability, or capability-aware plan selection under a rigorous protocol. The insight, not the tool, must be central. |
| Adjacent multi-column sort | Potentially a separate algorithm/DB paper unit. It presently lacks novelty analysis, strong baselines, and adequate results, and should not be bundled merely to make the compiler paper look more database-like. |
| Demonstration | Plausible after a compelling database-facing interactive scenario. A SIGMOD demonstration must still show significant R&D, a real application, and intellectual contribution ([SIGMOD 2027 demo call](https://2027.sigmod.org/calls_sigmod_demos.shtml)). |
| Artifact track | Useful only in support of a paper accepted through another contribution path. An artifact badge is not a substitute for scientific novelty. |
| Software paper | The most credible near-term direction after a stable release, independent reproduction, documented research use, and clearer impact. [JOSS](https://joss.theoj.org/about) is a possible example, but it expects feature-complete, research-relevant, maintainable open software; the current pre-alpha status and lack of evidenced external impact are material gaps. |
| Workshop/experience paper | Realistic if framed around one focused lesson, including negative results and a transparent account of which claims from the arXiv manuscript are retained, revised, or rejected. |

Splitting the current work into separate `tslc` and `tsldata` papers would fragment one integrated artifact into two weaker units. There is not enough independent scientific content in each component to justify that split. The two conditional research storylines above could eventually become distinct papers because they ask different questions and require different evidence, but attempting both now would diffuse effort before either has a validated thesis.

## 13. Final recommendation

Primary verdict: **Potentially publishable, but probably below top-tier**.

- **Strongest defensible contribution:** the integrated compiler and corpus contain a plausible research thesis not yet peer-reviewed: one authored primitive source of truth plus a deliberately small set of typed semantic islands may retarget C++/Rust and fixed/scalable vectors with change amplification governed by genuinely new semantic concepts rather than corpus-product size.
- **Principal novelty risk:** multi-backend generators, island grammars, portable SIMD interfaces, dependency closure, vector IRs, architecture-specific specialization, and autotuning are all established. The paper must demonstrate a stable minimal boundary and bounded integration result, not merely multiple outputs and a benchmark-selected policy. The arXiv manuscript is an earlier disclosure to supersede transparently, not a peer-reviewed novelty blocker.
- **Principal significance risk:** the compiler story may be valuable but niche, while the repository currently demonstrates no effect on a real database engine, query optimizer, workload, or external user.
- **Most important missing evidence:** for the closest-to-code path, an effective-sharing census, a precise semantic-lift model, retrospective and controlled change-amplification evidence, counterfactual authoring comparisons, generated-code/parity results, and a failure envelope. The autotuning claim additionally needs cross-language transfer or safe-pruning evidence. For the database path, a capability-divergence pilot must precede a real optimizer integration and native multi-architecture evaluation.
- **Most promising publication storyline:** Storyline 1 is the fastest defensible route: show that one corpus and minimal semantic lift bound the cost of adding languages and vector paradigms. Treat autotuning as optional supporting infrastructure unless its pilot yields a separate result. Storyline 2 has the best top-tier database upside: use transitive capability closure as an optimizer input—but only if the cheap pilot first shows information beyond ISA tags and ordinary empirical variant selection.
- **Most credible venue level:** after moderate research work, a focused generative-programming/compiler venue such as GPCE is realistic; CC or PACT is plausible with a strong result, while CGO is aspirational. A top-tier database venue becomes credible only after the major Storyline 2 systems project. A software/artifact paper remains a fallback, not the only opportunity.
- **Confidence:** moderately high, approximately 0.78. Static inspection supports the mechanisms and the absence of current evaluation, but cannot establish generated-code quality, performance, or the outcome of either proposed pilot.
- **Evidence most likely to change the verdict:** a positive effective-sharing census plus change-amplification study showing that a small stable region vocabulary explains reuse and makes Rust/scalable-vector integration additive; secondarily, a tuning pilot showing low-regret C++↔Rust policy transfer or safe material pruning. For the DB storyline, capability-aware choices must beat ISA dispatch or ordinary empirical selection. Negative kill tests should lower only the affected claim.

The publication-status correction matters: the core generator thesis can still be submitted for its first peer review. It does not remove the need for a scientific claim and comparative evidence. Finishing mappings, benchmarks, or documentation alone would still be engineering completion. The low-effort wins below are useful because they cheaply test the proposed ideas; they are not, by themselves, a finished paper.

## 14. Prioritized next research steps

### Immediate low-effort decision gates

1. **Create a preprint-to-submission claim matrix.** Mark each claim and result in the 2024 arXiv manuscript as retained, strengthened, replaced, or dropped. Cite it as an earlier version and make the peer-reviewed submission self-contained. This is a framing and integrity task, not a novelty veto.
2. **Produce an effective-sharing census.** From existing typed compiler facts, count shared versus backend-specific implementations, raw-only and region-using bodies, C++/Rust shared availability, fixed/scalable reuse, composition, fallback, and unsupported slots. Do not parse raw C++ or Rust to manufacture semantic facts. This is the cheapest decisive test of the “one source” claim.
3. **Reconstruct change amplification.** Use clean history or design records for the Rust backend and one scalable-vector integration. Count new semantic concepts/owners, corpus edits, backend-local additions, unrelated stages touched, and residual gaps. If integration effort visibly scales with corpus size or scattered edits, weaken the central claim before doing a controlled study.
4. **Run a small cross-language tuning-transfer pilot.** On the currently common benchmarkable variants, compare C++ and Rust rank correlation, winner agreement, transferred-policy regret, authored defaults, and separate exhaustive oracles. If common coverage is too small or transfer is poor, keep autotuning as engineering infrastructure rather than a paper contribution.
5. **Retain the database kill test separately.** Specify three operator requirement graphs and compute a profile-by-plan feasibility/provenance table from typed facts. Pursue Storyline 2 only if capability closure changes feasible choices beyond ISA labels and ordinary tuning.
6. **Use existing evidence as an inventory, not as results.** Map tests, coverage reports, benchmark definitions, and artifacts to each hypothesis and mark measurements that do not exist.
7. **Choose one central storyline after the gates.** Storyline 1 is the lower-cost publication attempt; Storyline 2 is the higher-risk database bet. A successful autotuning pilot may strengthen Storyline 1 or become a separate empirical result, but it should not blur the thesis.

### Work required to establish novelty

1. **For Storyline 1, formalize the semantic-lift and change-amplification claims.** Define raw segments, typed regions, contracts, composition, backend obligations, unsupported cases, effective sharing, the unit of a new semantic concept, and what “bounded” or “sufficient” means. The model must predict observable outcomes rather than redescribe classes.
2. **For an autotuning subclaim, choose exactly one novelty axis.** Formalize either cross-language policy transfer and regret, capability-constrained safe pruning, or robust multi-scenario selection. Do not relabel exhaustive timing plus winner selection as a new algorithm.
3. **For Storyline 2, formalize the operator-capability join.** Define operator requirements independently of primitive names; define native/composed/fallback/unsupported provenance, feature requirements, uncertainty, and sound feasibility pruning. Do not claim that provenance alone is a cost model.
4. **Complete focused related-work searches before implementation.** Storyline 1 needs island grammars, staged/generative programming, portable SIMD, vector IRs, multi-backend DSLs, and autotuning/transfer work if retained. Storyline 2 needs operator variant selection, learned/empirical physical design, hardware-oblivious execution, and cross-layer capability models.
5. **State kill criteria in advance.** Reject Storyline 1 if the small region set does not explain meaningful reuse, change amplification is not bounded, or counterfactuals are no worse. Drop the tuning subclaim if it adds no result beyond independent exhaustive policies. Reject Storyline 2 if closure adds no decision signal beyond ISA tags/timing or cannot prune safely.
6. **Do not claim ordinary deltas as novelty.** Typed Python architecture, Rust emission, more profiles, more tests, a capability matrix, deterministic generation, or measure-and-select tuning may support the artifact but are not central scientific contributions on their own.

### Work required to establish significance

1. **Storyline 1: show that the middle point solves a real retargeting problem.** Use representative changes across C++/Rust and fixed/scalable vectors; quantify duplicated target logic, authoring effort, generated-code quality, and unsupported cases relative to credible alternatives.
2. **Storyline 2: integrate with a real analytical engine.** Derive choice points from query traces or engine code, not convenient primitive examples, and demonstrate a measurable planning or calibration problem.
3. **Show an actual limitation of current alternatives.** Compare with TVL, Highway/xsimd/`std::simd`, MLIR-style lowering where appropriate, Rosenfeld-style variant selection, and native engine strategies. A contrived weakness is not enough.
4. **Demonstrate external relevance.** Obtain an independent user/reproduction or apply the model to an external primitive library, operator family, or second system component.
5. **Keep the multi-column sort separate unless it tests the chosen thesis.** It needs its own novelty review and baselines; adjacency to SIMD generation does not make it supporting evidence.

### Work required for empirical validation

1. **Predeclare a storyline-specific evaluation matrix.** Specify hardware, ISAs, native versus emulated execution, compilers, languages, operations, types, workloads, seeds, exclusions, and primary outcomes before collecting headline results.
2. **Use the strongest relevant baselines.** Storyline 1 needs the earlier TSLGen implementation/manuscript as a historical baseline, mature portable libraries, standards APIs, hand intrinsics, auto-vectorization, and an IR-based point of comparison. Storyline 2 needs static defaults, ISA dispatch, Rosenfeld-style empirical selection, an exhaustive oracle, and native engine kernels.
3. **Measure costs as well as benefits.** Include runtime, generation/compile time, code size, fallback cost, portability failures, calibration/optimization overhead, and the human effort or change amplification claimed by the paper.
4. **Add ablations and sensitivity analyses.** Isolate region kinds, composition/fallback, shared cross-language source, capability provenance, sparse benchmark evidence, selectivity, skew, cache regime, and vector-length assumptions as appropriate.
5. **Use native hardware for performance claims.** Emulation and cross-compilation can establish coverage or correctness, not performance portability. Report repetitions, uncertainty, exclusions, and negative results.
6. **Create a paper-tied reproduction package later.** Preserve raw results, analysis code, generated artifacts, capability snapshots, requirement graphs, exact toolchains, and a revision-to-binary chain; obtain an independent reproduction before submission.

### Work required for venue fit

1. **Route Storyline 1 to the compiler/generative audience.** GPCE is realistic after the moderate study; CC or PACT requires a stronger technical and empirical result; CGO is aspirational. A database venue is a poor fit without a database result.
2. **Route Storyline 2 according to prototype depth.** A positive three-operator pilot may support CIDR or a hardware-conscious data-management workshop. SIGMOD/PACMMOD, PVLDB, or ICDE requires the full engine integration, strong query evaluation, and multi-architecture evidence.
3. **Match a negative pilot honestly.** If the proposed insight fails but the software matures and gains research users, pursue a software paper or artifact accompanying another paper. Do not stretch feature breadth into a research claim.
4. **Mature and freeze the evaluated artifact.** Delimit backend parity, unsupported targets, external dependencies, generated manifests, and reproducibility commands before submission.
5. **Write around the result.** The repository architecture explains how the result was produced; it is not itself the result.

The highest-priority actions are the **effective-sharing census** and the **retrospective change-amplification table** because they directly test the combined multi-language/new-paradigm thesis with existing facts. The **cross-language tuning-transfer pilot** is the next cheapest way to decide whether autotuning belongs in the paper. The separate **three-operator capability-divergence table** remains the gate for the more expensive database storyline.
