# Repository Charter

This charter defines the repository-wide contract for `tslgen-v99`. The
compiler-specific contract in [`tslc/CHARTER.md`](tslc/CHARTER.md) refines it;
neither document is a substitute for current source data, tests, or generated
artifact evidence.

## 1. This Repository Delivers A Source-Driven Compiler

The compiler product is the whole path from authored `.tsl` data through
`tslc` to deterministic, compilable, testable C++ and Rust artifacts. Compiler
code, source data, normal testing and benchmarking, reusable inputs, and
coverage evidence are parts of one coordinated system rather than independent
projects. Separately packaged downstream tools may live in this repository,
but are not compiler stages, backends, `tslc` commands, or compiler-product
guarantees.

## 2. Current Evidence Is The Source Of Truth

Active behavior is justified by `tsldata/`, `supplementary/`, compiler code,
tests, package documentation, and generated artifacts that build and run.
Historical plans, local caches, and undocumented assumptions do not override
that evidence.

## 3. Changes Are Coherent Vertical Slices

A backend, primitive, source shape, TSIL feature, diagnostic, or verification
improvement may cross top-level directories. Keep one observable behavior per
slice, with tests at the boundaries it changes. Directory layout expresses
ownership; it must not force partial features or duplicate policy.

## 4. Maintainability Is A Product Requirement

A maintainer should be able to understand, debug, and safely change one
behavior by following a small number of clearly owned modules. Prefer direct
control flow, literal names, typed domain vocabulary, and small extension
points. Avoid handoff wrappers, compatibility layers, scattered string
classifiers, and speculative frameworks that do not deliver compiler behavior.

Shared knowledge should have one owner. Small local repetition is acceptable
when it keeps unlike concepts independent and clearer than a premature
abstraction.

## 5. Extensibility Means Additive, Honest Change

The next similar backend, primitive, or TSIL region should mostly add focused
data, handlers, capabilities, assets, and tests. If it repeatedly requires
editing unrelated stages, strengthen the missing boundary rather than adding
another special case.

Unsupported combinations remain explicit through structured diagnostics or
deterministic coverage skips. Progress is measured by supported combinations
that compile and verify, not by claims of completeness.

## 6. Output And Diagnostics Are Reproducible

Source discovery, selection, diagnostics, artifacts, manifests, generated
tests, and maintenance reports use stable ordering. Diagnostics are written for
the TSL author or maintainer who can act on them and preserve source locations
where practical.

Generated trees, build directories, test scratch, and configurable caches live
under `./tslctmp`. Source-controlled documentation and baselines are durable
project evidence; scratch output is not.

## 7. Documentation Has Clear Ownership

Root documentation explains the repository and cross-tree workflow.
`tslc/` documentation owns the compiler contract, architecture, and quick
start. Top-level `docs/` contains human-authored maintainer guides.
`supplementary/docs/` contains inputs used to build generated TSL
documentation. Each independently packaged tool owns its contract, instructions,
and user documentation below its directory in `tools/`. Keep these roles
distinct.

## 8. Compiler-Owned Projections Reuse Compiler Semantics

Interactive diagnostics, catalog discovery, navigation, hover, completion, and
preview are projections of compiler-owned parsed documents, typed catalogs,
registries, selection, and lowering. Batch analysis commands, maintenance
reports, documentation generators, and other compiler-owned projections
likewise consume public typed compiler facts. They may filter and format their
own output, but selection, capabilities, target spellings, dependency closure,
and source validation remain owned by their compiler stages. Opaque target text
remains opaque to these projections.

Editor clients may own transport and UI, but must not grow a second TSL parser
or TSIL vocabulary. Ordinary live features read the latest successful source
index and never render projects or invoke generated-code toolchains. Concrete
specialization preview is an explicit, cancellable saved-file action outside
the language-server process.

## 9. Downstream Tools Own Their Separate Interpretation

An independently packaged tool under `tools/` is a downstream consumer, not a
compiler-owned semantic projection. Dependencies point from the tool to
`tslc`, never from `tslc` or `tsldata` to the tool. Installing or importing the
compiler must not register the tool, change compiler defaults, or alter normal
generated artifacts.

A downstream tool may apply a bounded, tool-specific interpretation to target
text under its own documented contract. It owns the resulting semantics,
diagnostics, compatibility, coverage, verification, and output, and must not
present local inference as a compiler guarantee. It reuses compiler-owned
catalog, selection, capability, type-spelling, dependency, validation, and
ordinary lowering facts where available rather than duplicating them.

A tool need alone does not justify changing `tslc`, `tsldata`, normal TSIL
semantics, or generated behavior. Any such change requires a separate,
projection-neutral compiler or source-data justification. Root governance,
maintainability, determinism, diagnostics, testing, and review rules still
apply to the downstream tool.
