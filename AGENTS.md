# AGENTS.md

## Scope And Instruction Ownership

This file applies repository-wide. A nested `AGENTS.md` adds instructions for
its subtree; read this file and every applicable nested instruction file.

The active guidance is split by responsibility:

- `CHARTER.md` states the product/design contract; `PLANS.md` defines how to
  scope, execute, validate, and report changes.
- `tslc/AGENTS.md` owns compiler rules; `tsldata/AGENTS.md` owns source-data
  rules.
- `tslc/CHARTER.md` and `tslc/DESCRIPTION.md` define the compiler contract and
  describe the current architecture.
- `.agents/skills/` contains task playbooks; `.claude/skills/` exposes those
  canonical playbooks through directory symlinks.
- Root and nested `CLAUDE.md` files are import-only bridges to the applicable
  `AGENTS.md` files. Edit canonical instructions and skills, not their bridges.

## Purpose

This repository contains `tslc`, a Python compiler for TSL data, plus its source
corpus, reusable inputs, tests, coverage evidence, and CI for deterministic C++
and Rust SIMD library generation.

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

See the [README project map and navigation](README.md). Instruction and skill
ownership remains defined above.

## Cross-Tree Feature Routing

- Backend/capability: `.agents/skills/add-tslc-backend/SKILL.md`.
- Target extension/profile: `.agents/skills/add-tsl-extension/SKILL.md`.
- Primitive/source shape: `.agents/skills/add-tsl-primitive/SKILL.md`.
- Existing implementation: `.agents/skills/add-tsl-primitive-implementation/SKILL.md`.
- TSIL keyword region: `.agents/skills/add-tsil-region/SKILL.md`.
- Generated value-test shape: `.agents/skills/add-value-test-shape/SKILL.md`.
- Toolchain/runner verification: `.agents/skills/extend-tslc-verification/SKILL.md`.
- Architecture/extensibility review: `.agents/skills/design-review/SKILL.md`.

Read instructions for every subtree touched. Keep detailed paths, checks, and
commands in the applicable skill. Claude exposes the same skill names through
`.claude/skills/`.

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

Use workspace-local scratch paths; in common WSL setups, `/tmp` lives on an
overlay that only grows.

- Use `./tslctmp/...` for generated trees, builds, test scratch, and configurable
  tool caches. Do not commit it.
- Do not delete or rewrite committed baselines unless the task explicitly calls
  for it.
- Keep generated-documentation inputs in `supplementary/docs/`; use top-level
  `docs/` for human-authored maintainer guides.

## Review Expectations

Lead reviews with findings ordered by severity and include file/line references.
Prioritize boundary violations, weak extension points, raw dictionaries leaking
into domain logic, unclear diagnostics, nondeterminism, missing tests, and
maintainability risks. If none block the change, say so and note residual risks
or test gaps.

## Critical Judgment

- Evaluate non-trivial implementation requests before acting: confirm that the
  approach solves the stated goal, fits existing invariants and architecture,
  and is not needlessly complex or risky.
- Push back before implementation when a concern is material. State the concern
  and preferred alternative briefly; request direction only when the choice
  materially changes scope, behavior, or accepted risk.
- Do not push back on trivial edits, harmless preferences, or approaches with no
  substantive objection.
- Do not withdraw a technical conclusion merely to agree. Revise it when new
  facts or arguments justify doing so. If the user knowingly chooses the
  original safe, in-scope approach, proceed without claiming the concern is
  resolved.

## Communication And Code Style

- Be brief by default: lead with the outcome, then include only material
  rationale, risks, validation, and follow-up.
- For edits, change files directly and summarize the result with file links.
  Show patches or full file contents only when requested.
- Use a short plan for architectural uncertainty, multiple dependent steps, or
  meaningful cross-file coordination. Skip it for straightforward local or
  mechanical changes.
- Keep comments sparse and useful to future maintainers; explain non-obvious
  constraints or intent, not edit history.
- Do not leave commented-out code or speculative TODOs. Add a TODO only for
  intentionally deferred necessary work with a clear condition for removal.

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
