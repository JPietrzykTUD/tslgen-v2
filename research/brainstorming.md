# What `tslc` and `tsldata` may really be worth

Assessment date: 2026-07-29

## Executive judgment

The project is worthwhile, conditionally. Its value is not that the world lacks another SIMD wrapper library. Mature portable libraries, standard interfaces, compiler IRs, and vendor intrinsics already cover much of that surface.

The more distinctive opportunity is this:

> `tslc` can make a low-level primitive catalog executable: one semantic contract plus a portfolio of implementations becomes a verified, explainable, machine-specific library in multiple languages.

That makes the project closer to a **semantic product-line compiler for optimized libraries** than to an ordinary code generator.

This interpretation is supported by the active architecture. `tsldata/` owns primitive contracts, implementations, tests, benchmark semantics, extensions, and type facts. `tslc` promotes them into typed catalog and lowered values, selects and closes concrete implementation graphs, projects those facts into C++ and Rust, and plans verification and variant policies. The raw-text/typed-region boundary is explicit in [`tslc/CHARTER.md`](../tslc/CHARTER.md) and [`tslc/DESCRIPTION.md`](../tslc/DESCRIPTION.md); the generated variant workflow is documented in [`docs/variant-benchmarking.md`](../docs/variant-benchmarking.md).

The project becomes scientifically and practically valuable when it is used to expose and measure facts that ordinary SIMD libraries hide. If it remains primarily an increasingly comprehensive generator and authoring environment, it risks becoming overbuilt and scientifically inward-looking.

## What the project could enable

### 1. A bridge to new hardware and language paradigms before ecosystems mature

New ISAs, scalable-vector models, compiler-vector types, custom accelerators, and language ecosystems often appear before portable standards and mature libraries support them uniformly. `tslc` could let a hardware vendor or systems team describe a new target once and derive:

- native C++ and Rust APIs;
- feature, type, representation, and safety constraints;
- generated correctness and differential tests;
- native, composed, fallback, and unsupported realizations;
- benchmark candidates and compile-time policies;
- explicit coverage gaps rather than implied completeness.

This shortens the path from “intrinsics exist” to “a usable and tested library exists.” It is particularly valuable where requiring users to adopt a new compiler IR or nightly language feature is impractical.

The research question is not whether a generator can emit another intrinsic table. It is whether integration effort is governed mainly by genuinely new semantic obligations—such as mask representation, scalable lane behavior, safety, or type projection—rather than by the full primitive × type × ISA × language product.

### 2. An observatory for semantic capability, not just API availability

Most portable libraries answer a coarse question: “Is operation X available for target Y?”

The typed selection and dependency machinery in `tslc` could answer a richer question:

> Is this operation native, composed through which dependency chain, served by a generic fallback, unsupported, or only attractive under a particular measured implementation policy?

That provenance could support:

- explainable database-operator selection;
- identification of expensive semantic gaps in an ISA;
- quantitative comparison of fixed and scalable vector architectures;
- prioritization of primitives that eliminate long fallback chains;
- instruction-set and accelerator co-design;
- analysis of which hardware features matter to real workloads.

This may be a stronger research direction than publishing the generator itself. `tslc` becomes the experimental instrument used to discover the marginal value of an instruction or representation for database and systems workloads.

The crucial constraint is ownership: such an observatory should consume compiler-owned typed selection, lowering, dependency, feature, and implementation-state facts. It must not infer semantics by parsing opaque C++ or Rust fragments.

### 3. Cross-language compiler and tuning experiments

Corresponding generated C++ and Rust implementations create experiments that a single-language library cannot conduct cleanly:

- Do implementation rankings transfer between C++ and Rust?
- Does the same authored strategy produce equivalent machine code?
- Which compiler or language boundaries reverse the winning implementation?
- What performance regret results from reusing one language's policy in the other?
- Which semantic contracts expose differences in masks, shifts, floating-point behavior, safety, or calling conventions?
- Can capability information reduce the number of candidates that must be calibrated without discarding the oracle winner?

The current correctness-gated measure-and-select workflow is strong engineering, not a new autotuning algorithm. Scientific value requires a result beyond ordinary winner selection, such as:

- low-regret cross-language policy transfer under identifiable conditions;
- a taxonomy explaining when rankings diverge;
- sound capability-constrained pruning with materially lower calibration cost;
- a robust multi-scenario policy that improves on independent per-machine exhaustive tuning.

A sufficiently broad study could also uncover compiler bugs, intrinsic inconsistencies, or undocumented optimization differences. Such discoveries would be more persuasive than feature-count arguments.

### 4. Workload-specific low-level library synthesis

A database engine, runtime, embedded system, or accelerator application may require only a narrow subset of primitives, types, profiles, mask policies, and safety modes. Instead of depending on a large generic package, `tslc` can potentially produce a focused product with:

- exactly the requested primitive dependency closure;
- a concrete machine or deployment profile;
- auditable generated artifacts and manifests;
- workload-relevant implementation variants;
- compile-time policy selection rather than mandatory runtime dispatch;
- generated tests covering the selected product rather than an abstract global API.

This may provide practical advantages in static deployment, reproducible builds, accelerator SDKs, database kernels, and tightly controlled software supply chains. Its value would need to be demonstrated through a real consumer; configurability alone is not a research result.

### 5. A laboratory for the maintainability of low-level software

The project can test a general hypothesis about retargetable low-level libraries:

> With semantics lifted only at true cross-target pressure points, integration effort grows with the number of new semantic concepts rather than with the size of the existing implementation corpus.

This hypothesis is falsifiable. Relevant measurements include:

- new semantic concepts, descriptors, contracts, and handlers introduced;
- existing primitive implementations left untouched;
- backend-specific exceptions and duplicated bodies;
- unrelated compiler stages touched;
- unsupported combinations before and after the integration;
- diagnostics, defects, review effort, and generated-code regressions;
- change amplification for a new language, fixed/scalable vector model, and ordinary ISA extension.

If supported, the result teaches a reusable design principle. If false, the failure boundary is still informative: it identifies when partial semantics stop scaling and a fuller IR or separate implementation family becomes necessary.

### 6. A testbed for instruction-set economics

The combination of semantic primitive contracts, implementation dependency closure, workload traces, and variant measurements could support a different kind of study:

> Which proposed hardware operation removes the most expensive composed or fallback paths for an actual workload?

For example, a proposed mask conversion, compression, gather, reduction, or lane operation could be modeled as newly native. The resulting closure changes could be joined with operator traces and measured costs. This could quantify the marginal workload value of an instruction rather than evaluating an ISA through isolated microbenchmarks.

This direction could fit architecture or database venues, but only after real workload integration and native measurements. Static closure deltas are a useful pilot, not a performance conclusion.

## Where other approaches choose different design points

The alternatives do not generally fail; they solve different problems. The potential `tslc` gap lies in the combination of source ownership, semantic provenance, native-source generation, verification, and implementation portfolios.

| Approach | What it does well | Gap that `tslc` may occupy |
|---|---|---|
| Mature portable SIMD libraries and standard APIs | Stable user-facing abstraction, performance, ecosystem maturity | Usually expose a predetermined abstraction rather than an author-owned compiler for custom target families, languages, policies, tests, and semantic provenance |
| Handwritten intrinsics and templates | Exact implementation control and predictable target recipes | Duplicate semantics, difficult multi-language maintenance, weak machine-readable contracts, and limited explanation of native/composed/fallback realization |
| LLVM/MLIR-style vector IRs | Rich semantics, transformation, optimization, and progressive lowering | Require a larger semantic and toolchain commitment; may be less suitable when exact hand-selected recipes must be preserved and delivered as ordinary source libraries |
| Compiler auto-vectorization | Low author effort for suitable loops | Unpredictable support for irregular operations, explicit masks, gather/compress, precise fallback, and selectable implementation portfolios |
| Bindings and C FFI | Reuse one native implementation in several languages | Lose idiomatic native APIs, some inlining and type integration, shared compile-time policies, and language-specific verification |
| Traditional autotuners | Select fast algorithms or implementations | Often do not derive candidates, semantic contracts, correctness cases, dependency provenance, and several language realizations from one catalog |
| Vendor intrinsic APIs | Immediate access to hardware features | Fragment semantics and packaging across vendors, architectures, languages, and compiler versions |

No individual row proves novelty. A composition of established ideas may be scientifically incremental while still having substantial product and research-infrastructure value.

## When the project is not worthwhile

Continued large investment is difficult to justify if most of the following become true:

- the intended deliverable is only another general-purpose C++ SIMD wrapper;
- most Rust output depends on brittle translation of C++-shaped raw text;
- backend-specific exceptions grow proportionally with corpus size;
- scalable and non-x86 targets mostly resolve through generic fallback;
- too few primitives have meaningful competing implementations for tuning to matter;
- generated performance or code quality is not competitive with mature alternatives;
- no external engine, hardware vendor, runtime, or researcher consumes the output;
- compiler, LSP, diagnostic, and maintenance infrastructure grows faster than verified primitive capability;
- each “new paradigm” requires scattered changes across unrelated compiler stages;
- generated tests mostly reproduce the same semantic assumptions as the implementations and find no real defects.

For one language and a small number of targets, a mature portable library or direct intrinsics will usually be cheaper. The architecture is justified only by a genuinely multi-dimensional product line or by experiments that require its semantic and provenance machinery.

## Strongest north-star research result

The most coherent near-term study would ask three connected questions:

1. How much primitive meaning and implementation content is genuinely shared across C++/Rust and fixed/scalable vectors?
2. Which new semantic obligations account for the integration cost of each paradigm?
3. Do generated implementation rankings and policies transfer across languages and machines, and can semantic capability reduce calibration cost?

A strong result could be stated as follows:

> Across a large low-level primitive corpus, a compact set of semantic obligations explains most cross-language and cross-vector reuse. New paradigms require changes proportional to those obligations rather than corpus size, while generated code remains competitive. Variant rankings transfer under identifiable conditions and fail predictably under others.

That would be a scientific result. `tslc` would be the unusually capable apparatus that made it possible.

The autotuning clause is optional. If the transfer/pruning pilot is negative, the paper should retain the single-corpus and bounded-change-amplification thesis and present tuning as artifact infrastructure. A failed tuning claim should not blur or invalidate the stronger generative-programming question.

## Immediate decision experiments

Before expanding the implementation further:

1. **Effective-sharing census:** measure shared versus backend-specific bodies, region use, C++/Rust shared availability, fixed/scalable reuse, composition, fallback, and unsupported combinations using existing typed compiler facts.
2. **Retrospective change-amplification study:** reconstruct the Rust and one scalable-vector integration from clean history or design records; count semantic concepts, corpus edits, backend-local additions, unrelated stages, and residual gaps.
3. **Cross-language tuning pilot:** for currently common benchmarkable variants, compare rank correlation, winner agreement, transferred-policy regret, authored defaults, and independent exhaustive oracles.
4. **Capability-value pilot:** join three database-operator requirement graphs with profile-specific native/composed/fallback closure and identify whether superficially similar SIMD targets permit different plans.
5. **External-consumer test:** integrate one generated slice into a real engine, runtime, or vendor-facing SDK and document what the consumer could not obtain as cleanly from a mature portable library.

These experiments have useful negative outcomes. Stop or narrow the relevant claim if sharing is superficial, change amplification follows corpus size, tuning transfer is poor, capability provenance does not affect decisions, or the external consumer gains no meaningful advantage.

## Final assessment

`tslc` and `tsldata` are worthwhile if they become a **semantic control plane and experimental platform for families of hand-optimized low-level libraries**. They can potentially connect one source of truth to multiple native languages, hardware paradigms, verification regimes, implementation portfolios, and explainable capability states in a way that existing point solutions generally do not attempt as one system.

They are not worthwhile merely because generation, Rust output, autotuning, diagnostics, or broad target declarations are individually impressive. The project's future value depends on demonstrating at least one external consequence: faster integration of a genuinely different paradigm, a new empirical insight, a real compiler or semantic defect, a materially better tuning decision, a useful instruction-set finding, or a downstream system that could not obtain the same result economically from established alternatives.
