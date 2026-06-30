# AGENTS.md

## Purpose

This repository contains `tslc`, a Python compiler for the TSL data language.
It reads `.tsl` source data, builds a validated catalog, selects primitive
implementations for explicit targets, lowers TSIL body regions, and generates
deterministic C++ and Rust library artifacts.

Optimize for a maintainable research compiler: typed models, clear ownership,
small modules, deterministic output, and diagnostics that help a TSL author fix
input data.

## Design Foundations

`tslc` is a compact compiler, not a framework. It should be easy for an
experienced Python developer to trace one primitive from source data to emitted
artifact without learning a private architecture vocabulary first.

The project design rests on these ideas:

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

## Project Map

```text
tslc/
  src/tslc/
    api.py                    Public generation API
    cli.py                    CLI entry point
    sources.py                Source-document loading
    syntax/                   TSL parser and parsed-source models
    catalog/                  Typed catalog model, builder, validation
    select/                   Target/profile implementation selection
    ir/                       Recursive TSIL body segments and region registry
    lower/                    Lowering from catalog + TSIL regions to typed output facts
    backend/                  Backend dialects, translation, emitted functions
    render/                   In-memory generated-project render models/artifacts
    output/                   Artifact writing and build/test verification
    value_tests/              Generated value-test planning and harness data
    maintenance/              Developer tools: explain, stage dump, coverage ratchet
  tests/                      Python test suite
  CHARTER.md                  Short design contract
  README.md                   User-facing overview and quick start
  DESCRIPTION.md              Longer architecture narrative

tsldata/
  detail/                     Type/language/backend detail data
  extensions/                 Extension and profile source data
  primitives/                 Primitive source corpus

supplementary/
  buildsystem/                C++/Rust build-system static files and templates
  ci/                         CI helper scripts
  docs/                       Active generated-documentation assets
  helpers/                    C++/Rust helper sources
  templates/                  C++/Rust render templates

coverage/
  baseline.json               Coverage ratchet baseline
  primitive-coverage-inventory.md
                              Maintenance-generated coverage inventory

.agents/
  skills/                     Repo-local Codex skills for repeated workflows

tslctmp/                      Local scratch/build/generated output; do not commit
```

## Common Commands

Run from the repository root unless noted.

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

Useful focused tests:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_tsil_scan.py tslc/tests/test_lower_text.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_output_format.py
```

Use `./dev.sh` for generated-project workflows:

```bash
./dev.sh generate --primitives add --profiles scalar --backends cpp,rust
./dev.sh build --primitives add --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives add --profiles avx2 --backends cpp
./dev.sh explain --primitive add --profile avx2 --type si32 --backend cpp
./dev.sh dump --stage lowered --primitive add --profile avx2 --type si32 --backend cpp
```

## Design Rules

- Use typed Python and keep boundaries mypy-friendly where practical.
- Prefer `@dataclass(frozen=True, slots=True)` for domain/value objects.
- Use object-oriented ownership for stateful concepts such as `Catalog`,
  selector/generator objects, backend dialects, diagnostic reporting, and
  artifact writing.
- Prefer pure functions for simple stateless transformations.
- Keep raw dictionaries at parser, configuration, or explicit metadata
  boundaries. Downstream compiler stages should consume typed objects.
- Keep filesystem reads in source/config loading and filesystem writes in
  artifact writing or explicit maintenance tools.
- Return structured diagnostics from pure logic. Do not call `SystemExit`
  outside CLI boundaries.
- Preserve source locations for diagnostics where practical.
- Keep iteration and emitted output deterministic.
- Split modules before they become catch-all files.

## TSIL And Backend Boundaries

- A TSIL body is a recursive sequence of `RawText` and recognized keyword
  `Region` segments, not a general C/C++/Rust AST.
- Recognize exact documented source forms. Diagnose malformed or unsupported
  nearby forms instead of silently repairing them.
- New shared semantics should become typed TSIL regions or typed lowering values
  rather than backend-specific raw string rewrites.
- Backend semantic decisions belong in typed lowering/translation/evaluator
  code, not templates.
- Templates format already-decided render values. They must not select
  implementations, parse TSIL, resolve types, choose intrinsics, gate features,
  repair source, or compute dependency closure.
- A backend with substantially different expression syntax should fail clearly
  until the needed raw forms have typed TSIL representations.

## Extensibility Rules

A dimension is extensible when a typical new feature mostly adds focused code
rather than modifying unrelated locations.

When adding a backend:

- register capabilities in the backend/support-policy boundary;
- add typed translation/render support and supplementary assets;
- validate unsupported capabilities before render/write;
- add focused tests proving the backend ID or capability is data-driven.

When adding a primitive or source-data shape:

- add or update `.tsl` data in `tsldata/`;
- keep parser output separate from catalog/domain promotion;
- validate schema and semantic constraints with actionable diagnostics;
- add selection/lowering/render tests proportional to the blast radius.

When adding a TSIL region:

- add it to the region descriptor/registry path;
- scan through the shared recursive segment boundary;
- add shell validation and lowering support as separate concerns;
- test valid, malformed, unsupported, and nested forms.

## Scratch And Generated Output

Use workspace-local scratch paths. This repo is commonly used in a WSL
container where `/tmp` lives on an overlay that only grows.

- Use `./tslctmp/...` for generated trees, build directories, and test scratch.
- Keep tool caches under `./tslctmp` when configurable.
- Do not commit generated scratch output.
- Do not delete or rewrite committed baselines unless the task explicitly calls
  for it.
- `supplementary/docs/` is an active asset tree; keep it.

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
- Follow existing local style before introducing new patterns.
- Do not revert unrelated user changes.
- Do not add hidden network, hardware, or host-specific test dependencies.
- Hardware/toolchain detection must be injectable, skippable, or clearly gated.
- Update `AGENTS.md`, `PLANS.md`, or `tslc/*.md` only when behavior, workflow,
  or architecture guidance changes.
- Final responses should state what changed, what validation ran, and any
  meaningful follow-up.
