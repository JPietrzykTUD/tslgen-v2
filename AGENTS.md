# AGENTS.md

## Scope And Instruction Ownership

This file applies to the entire repository. A nested `AGENTS.md` adds
instructions for its subtree; it does not replace this root contract. Read this
file and every applicable nested instruction file before changing files.

The active guidance is split by responsibility:

- `CHARTER.md` states the repository-wide product and design contract.
- `PLANS.md` defines how to scope, execute, validate, and report a change.
- `tslc/AGENTS.md` owns compiler-implementation rules and focused validation.
- `tsldata/AGENTS.md` owns authored TSL source-data rules.
- `tslc/CHARTER.md` and `tslc/DESCRIPTION.md` define the compiler contract and
  describe the current architecture.
- `.agents/skills/` contains task-specific playbooks. Keep detailed feature
  procedures there instead of duplicating them in instruction files.

## Purpose

This repository contains `tslc`, a Python compiler for the TSL data language,
plus the authored source corpus, reusable inputs, tests, coverage evidence, and
CI needed to generate deterministic C++ and Rust SIMD library artifacts.

Optimize for a maintainable research compiler: typed models, clear ownership,
small modules, deterministic output, and diagnostics that help a TSL author fix
input data.

## Repository Design Foundations

`tslc` is a compact compiler, not a framework. It should be easy for an
experienced Python developer to trace one primitive from source data to emitted
artifact without learning a private architecture vocabulary first.

The repository design rests on these ideas:

- **Compiler pipeline**: `.tsl` sources become parsed syntax, a typed catalog,
  selected implementations, scanned TSIL segments, lowered specializations,
  backend output, rendered artifacts, and optional verification.
- **KISS**: choose the simplest design that preserves the compiler boundary and
  makes the next similar feature understandable. Keep vertical slices small,
  names literal, control flow direct, and abstractions justified by behavior.
- **DRY with judgment**: remove duplicated compiler knowledge, diagnostics,
  selection rules, lowering behavior, backend rules, and render decisions.
  Tolerate small local repetition when it keeps unlike concepts independent or
  avoids premature generalization.
- **Domain vocabulary over plumbing**: add real concepts such as `Primitive`,
  `Extension`, `Region`, `BackendDialect`, or `LoweredSpecialization` when they
  carry behavior or invariants. Avoid request/result/handoff wrapper families
  whose only job is passing another object along.
- **Typed objects after parsing**: plain dictionaries are acceptable at I/O,
  parser, or metadata boundaries. Domain, selection, lowering, backend, and
  render logic should consume frozen dataclasses, enums, protocols, or other
  explicit typed values.
- **Object-oriented ownership where useful**: stateful concepts should own their
  invariants and behavior. Use small classes or protocols for catalogs,
  selectors, generators, backend dialects, diagnostic reporters, and artifact
  writers. Use pure functions for simple stateless transformations.
- **TSIL is not a target-language AST**: implementation bodies are recursive
  sequences of raw target text plus recognized TSIL keyword regions. Add typed
  regions for shared semantics; do not grow ad-hoc C/C++/Rust parsers or raw
  string rewrite ladders.
- **Backends format decided semantics**: backend code translates typed lowered
  values. Templates format render models. They must not decide primitive
  selection, feature gating, type resolution, dependency closure, or source
  repair.
- **Coverage, not fantasy completeness**: unsupported source forms should
  produce clear skips or diagnostics. Progress is measured by which primitive,
  extension, type, and backend combinations compile and verify.
- **Extensibility means additive change**: adding a primitive, TSIL region, or
  backend capability should mostly add focused source data, typed handlers,
  backend rules, assets, and tests rather than modify unrelated stages.
- **Diagnostics are part of the product**: errors and skips should be
  structured, deterministic, source-located where practical, and written for the
  TSL author who needs to fix the input.
- **Vertical slices cross directories**: a backend, primitive, source shape, or
  TSIL feature may touch `tsldata/`, `tslc/`, `supplementary/`, and tests.
  Directory boundaries express ownership; they do not define the whole feature.

## Project Map

```text
CHARTER.md                  Repository-wide design contract
PLANS.md                    Planning and execution protocol
docs/                       Human-authored maintainer guides
examples/                   Checked-in C++ and Rust consumer examples

tslc/
  AGENTS.md                 Compiler-local instructions
  src/tslc/                 Compiler package
  tests/                    Python test suite
  CHARTER.md                Compiler-specific design contract
  DESCRIPTION.md            Current architecture narrative
  README.md                 Compiler quick start

tsldata/
  AGENTS.md                 Source-data-local instructions
  detail/                   Type, language, and backend detail data
  extensions/               Extension source data
  primitives/               Primitive source corpus

supplementary/
  buildsystem/              Machine-profile configuration
  ci/                       Reusable CI helper scripts
  docs/                     Inputs for generated TSL documentation

coverage/                   Coverage and benchmark ratchet evidence
.agents/skills/             Task-specific agent playbooks
.github/                    GitHub Actions workflows and actions
tslctmp/                    Local scratch and generated output; do not commit
```

## Cross-Tree Feature Routing

These workflows are task-specific rather than directory-specific:

- Adding a backend or backend capability: use
  `.agents/skills/add-tslc-backend/SKILL.md`.
- Adding a primitive or source-data shape: use
  `.agents/skills/add-tsl-primitive/SKILL.md`.
- Adding or completing an implementation of an existing primitive: use
  `.agents/skills/add-tsl-primitive-implementation/SKILL.md`.
- Adding a TSIL keyword region: use
  `.agents/skills/add-tsil-region/SKILL.md`.
- Reviewing architecture or extensibility: use
  `.agents/skills/design-review/SKILL.md`.

Read the root instructions and the instructions for every subtree touched by a
workflow. Keep the essential cross-tree contract visible here; keep detailed
paths, checks, and commands in the applicable skill.

## Common Commands

Run from the repository root unless noted.

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
(cd tslc && python -m mypy)
git diff --check
```

The default pytest run skips generated C++/Rust build/value gates. Run them
explicitly when the slice touches generated project layout, backend codegen,
verification, or executable value tests:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

Use `./dev.sh` for generated-project workflows:

```bash
./dev.sh generate --primitives add --profiles scalar --backends cpp,rust
./dev.sh build --primitives add --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives add --profiles avx2 --backends cpp
./dev.sh explain --primitive add --profile avx2 --type si32 --backend cpp
./dev.sh dump --stage lowered --primitive add --profile avx2 --type si32 --backend cpp
```

## Scratch And Generated Output

Use workspace-local scratch paths. This repo is commonly used in a WSL
container where `/tmp` lives on an overlay that only grows.

- Use `./tslctmp/...` for generated trees, build directories, and test scratch.
- Keep tool caches under `./tslctmp` when configurable.
- Do not commit generated scratch output.
- Do not delete or rewrite committed baselines unless the task explicitly calls
  for it.
- `supplementary/docs/` contains assets used only for generated-TSL
  documentation; keep it.
- Use top-level `docs/` for human-authored maintainer guides, not generated
  documentation inputs or agent workflow machinery.

## Review Expectations

When asked for a review, lead with findings ordered by severity and include
file/line references. Prioritize:

- boundary violations;
- extension-point weaknesses;
- raw dictionaries leaking into domain logic;
- unclear or missing diagnostics;
- nondeterminism;
- missing tests;
- maintainability risks.

If there are no blocking findings, say so clearly and mention any residual risk
or test gaps.

## Working Rules

- Keep each change scoped to one coherent slice.
- Read `PLANS.md` before substantial planning, implementation, review, or
  revision work. Tiny documentation or typo-only edits may use it as a
  mental checklist rather than a formal plan.
- Read every `AGENTS.md` that applies to the files being changed.
- Inspect current code, source data, tests, and local documentation before
  deciding the design.
- Follow existing local style before introducing new patterns.
- Do not revert unrelated user changes.
- Do not add hidden network, hardware, or host-specific test dependencies.
- Hardware/toolchain detection must be injectable, skippable, or clearly gated.
- Keep filesystem writes in artifact writing, explicit maintenance tools, or
  clearly owned configuration/update commands.
- Update instruction files, plans, charters, architecture docs, or READMEs only
  when their documented behavior, workflow, ownership, or navigation changes.
- Final responses should state what changed, what validation ran, and any
  meaningful follow-up.
