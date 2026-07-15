# TSL Editor Remaining-Work Plan

## Status And Purpose

The contributor-preview editor and its compiler-owned language server are
working. Implemented behavior is documented in `docs/tsl-editor.md`; the
compiler and authoring-service boundaries are documented in
`tslc/DESCRIPTION.md`. This file intentionally does not repeat finished CLI,
language-server, preview, doctor, contributor install/package,
grammar-generation, or primitive-scaffolding work.

The native TSLc explorer is now part of that working baseline. It provides
File/Corpus primitive discovery, profile/backend slot counts, an
unavailable-only view, selected-implementation navigation and preview, and
direct authored Calls/Called By relationships. Explicit concrete analysis adds
the compiler's final native/composed/fallback/unknown state and active lowered
dependency closure without changing those lookup-only paths.

Safe compiler-owned code actions are also part of the working baseline. Exact
metadata and schema repairs are source-located, document-version/digest checked,
returned as LSP `WorkspaceEdit` values, and undoable. Ambiguous diagnostics
offer help rather than guessed edits.

This is the execution plan for the remaining editor work. It should contain
only unfinished behavior. When a slice meets its exit criteria, remove that
slice rather than preserving a completion log here. Git history and tests are
the completion record.

Parsed outer-language context, catalog completion, descriptor-driven TSIL
region-shell completion, typed query-path completion, hierarchical symbols,
typed selector navigation, semantic highlighting, and safe source actions are
now part of the working baseline. A self-contained Marketplace distribution is
the remaining release gate and is deliberately separated from authoring
behavior.

## Target Outcome

A user should be able to install the public extension on a supported host and
use the compiler-backed editor without separately installing Python or
`tslc[editor]`, while contributors retain explicit external-runtime overrides.

## Fixed Boundaries

These constraints apply to every slice in this plan:

- Python compiler code owns syntax, catalog facts, validation, TSIL regions,
  selector rules, query semantics, and completion vocabulary. TypeScript owns
  VS Code presentation and command wiring only.
- Hover, completion, symbols, navigation, and semantic tokens query the latest
  successful in-memory catalog/index. They must not run a corpus check, select
  a specialization, lower TSIL, render code, or start a child process.
- Parsed syntax and source spans are the primary source of cursor context. A
  conservative lexical fallback may handle the currently incomplete line, but
  it must not become a second parser.
- Registered TSIL vocabulary must be derived from compiler registries,
  descriptors, validators, or typed query rules. Do not copy keyword or option
  lists into the extension.
- Ordinary editing requests do not write files, invoke toolchains, access the
  network, or analyze C++/Rust inside raw TSIL segments.
- Explicit commands may start cancellable child processes only where their
  existing command contract requires it.
- A formatter remains out of scope until the parser has a lossless concrete
  syntax representation for comments and exact source structure.
- The contributor preview may continue to use an external `tslc[editor]`
  installation. A polished public release must not silently assume a local
  Python installation.

## Remaining Gaps

| Area | Remaining behavior | Main owner |
| --- | --- | --- |
| Public distribution | Self-contained, platform-specific server runtime and release verification | Extension packaging and CI |

## Ordered Slices

The remaining slice is a separate release/distribution track. It builds on the
stable authoring protocol but does not change its compiler/editor ownership.

### Slice 1: Self-Contained Marketplace Runtime

**Goal:** make a public VS Code installation work without a separately managed
Python or `tslc[editor]` environment.

This is a release/distribution project, not a language-feature prerequisite.

**Work:**

- Choose and document a reproducible freezing/embedding approach that packages
  the same Python compiler and language-server sources tested in the repository.
- Build platform-specific server artifacts and VSIX packages for the supported
  operating-system and architecture matrix.
- Retain explicit server-command and external-runtime settings as contributor
  and debugging overrides.
- Ensure activation performs no download and verifies packaged executable
  presence with an actionable error.
- Test local, SSH, container, and WSL extension-host placement so the server
  executes where workspace files are visible.
- Add release provenance, checksums, license inventory, and a startup smoke test
  for every packaged platform artifact.

**Exit criteria:**

- A clean supported host with no Python, Node.js, or repository checkout can
  install its VSIX, open a `.tsl` workspace, receive diagnostics, hover, and
  completion, and run an explicit specialization command.
- The packaged compiler version is visible in logs and diagnostics and matches
  the release manifest.
- CI builds and smoke-tests every advertised platform package.
- Contributor override paths continue to work and are documented separately
  from the default user path.

## Deferred Work

The following items are not active slices:

- source formatting before a lossless concrete syntax tree exists;
- rename, call hierarchy, or target-language symbol analysis;
- automatic rendering on hover, cursor movement, save, or ordinary checking;
- speculative completion for raw C++/Rust expressions;
- unsaved-buffer specialization preview unless a future compiler command gains
  an explicit overlay contract;
- background build, test, benchmark, or toolchain execution.

Add one of these only when there is a concrete user workflow, a compiler-owned
semantic boundary, and focused acceptance tests.

## Validation Strategy

Each slice must add focused Python tests at the compiler/authoring boundary and
protocol tests at the LSP adapter boundary. Add TypeScript tests only for client
translation, command UI, or VS Code integration; do not duplicate compiler
semantic test matrices in TypeScript.

Representative validation from the repository root:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_authoring_tools.py \
  tslc/tests/test_authoring_completion.py \
  tslc/tests/test_lsp_workspace.py \
  tslc/tests/test_lsp_protocol.py
(cd tslc && python -m mypy)
(cd editors/vscode-tsl && npm test)
git diff --check
```

Use the actual focused test filenames present when a slice is implemented; add
new files when that makes ownership clearer. Run the full Python suite after a
slice changes shared parsing, catalog promotion, TSIL scanning, or diagnostic
models. Run the extension-host integration tests when protocol capabilities,
commands, workspace edits, or packaging change. The Marketplace slice also
requires clean-host tests of each built artifact.

## Performance Guardrails

Do not introduce incremental catalog architecture pre-emptively. Preserve the
current full-corpus semantics and measure after each authoring slice.

- language-server startup to first diagnostics: less than 2.5 seconds for the
  repository corpus on the reference development environment;
- edited-document diagnostics after debounce: p95 below 750 milliseconds;
- hover, completion, definition, references, symbols, and semantic tokens from
  a ready index: p95 below 100 milliseconds;
- explorer refresh for an unchanged catalog/profile/backend projection: p95
  below 100 milliseconds; selecting an uncached profile/backend projection:
  p95 below 750 milliseconds;
- explicit specialization preview/check/doctor result: normally below 5
  seconds, remaining cancellable and outside lookup requests;
- explicit explorer concrete analysis: normally below 5 seconds for one slot,
  remaining cancellable and never running as a refresh side effect.

Record the corpus size and measurement command when changing a threshold. If a
lookup exceeds its budget, profile context construction and index shape first.
If rebuild diagnostics exceed their budget, measure parse-cache misses and
catalog reconstruction before designing incremental promotion.

## Active Risks And Mitigations

- **Bundled Python multiplies platform and release risk.** Keep it isolated in
  this slice, use a declared support matrix, build reproducibly, and retain the
  external runtime only as an explicit override.
