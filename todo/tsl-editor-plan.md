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

This is the execution plan for the remaining editor work. It should contain
only unfinished behavior. When a slice meets its exit criteria, remove that
slice rather than preserving a completion log here. Git history and tests are
the completion record.

Parsed outer-language context, catalog completion, descriptor-driven TSIL
region-shell completion, typed query-path completion, hierarchical symbols,
typed selector navigation, and semantic highlighting are now part of the
working baseline. The next product milestone adds safe source actions.
A self-contained Marketplace distribution is a later release gate and is
deliberately separated from authoring behavior.

## Target Outcome

An author editing an incomplete `.tsl` document should be able to discover the
language without memorizing compiler internals:

- safe, source-located compiler suggestions can become explicit, undoable
  editor actions;
- ordinary lookup requests remain memory-only and fast.

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
| Safe actions | Convert exact compiler suggestions into version-checked `WorkspaceEdit` actions | Diagnostics/audit API and LSP code actions |
| Public distribution | Self-contained, platform-specific server runtime and release verification | Extension packaging and CI |

## Ordered Slices

The slices are ordered by product dependency. Slice 1 builds safe edits on the
now-stable source-span model. Slice 2 is a separate release track and must not
block the authoring-depth milestone.

### Slice 1: Safe Compiler-Owned Code Actions

**Goal:** expose exact, source-located compiler suggestions as deliberate,
undoable editor edits.

**Work:**

- Define a typed suggestion/fix record with diagnostic identity, document URI,
  expected document version or digest, replacement range, and replacement
  text.
- Convert metadata-audit suggestions only when the compiler can identify an
  exact safe insertion or replacement range.
- Add missing required-field actions only for schema cases with an unambiguous
  insertion point and canonical indentation.
- Add non-editing actions that open the relevant guide or inspect the owning
  declaration when automatic repair is not safe.
- Return LSP `WorkspaceEdit` objects; the server must not write source files
  directly.

**Exit criteria:**

- Every edit action has before/after tests, preserves surrounding text, and is
  rejected for a stale document version or digest.
- Ambiguous diagnostics expose explanation/help only, never a guessed edit.
- Multi-document edits are absent unless one atomic compiler suggestion truly
  owns every affected span.
- VS Code integration tests prove edits are previewable/undoable and ordinary
  diagnostics remain non-mutating.

### Slice 2: Self-Contained Marketplace Runtime

**Goal:** make a public VS Code installation work without a separately managed
Python or `tslc[editor]` environment.

This slice starts only after the authoring-depth slices are stable. It is a
release/distribution project, not a language-feature prerequisite.

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

## Authoring-Depth Milestone Acceptance

The authoring-depth milestone is complete when Slice 1 satisfies its
exit criteria and all of the following hold:

- completion is correct at top level, nested catalog blocks, TSIL boundaries,
  region shells, query paths, and primitive scope;
- completion remains useful but conservative on the incomplete line;
- all compiler-owned completion inventories have consistency/drift tests;
- symbols, navigation, references, and semantic tokens use the same typed
  declarations and source spans;
- explorer analysis distinguishes final lowering state from selector origin,
  exposes the active transitive dependency closure, and remains explicit and
  cancellable;
- every automatic edit is explicit, source-located, version-checked, and
  undoable;
- ordinary editing remains free of rendering, builds, tests, network access,
  and direct file writes;
- focused Python, LSP, extension, and performance checks pass.

Self-contained Marketplace distribution is accepted separately through Slice
2 and must not be claimed merely because contributor installation works.

## Active Risks And Mitigations

- **Incomplete buffers can defeat parsed context.** Keep the fallback limited
  to the current line, carry a confidence marker, and prefer omission over an
  invalid completion.
- **Schema and completion can drift.** Derive values from typed schemas and
  registries and add inventory tests that compare registered forms with
  authoring descriptors.
- **TSIL vocabulary can fragment across scanners, validators, and lowering.**
  Put author-facing metadata next to region registration and test every
  registered descriptor.
- **Raw TSIL text is intentionally ambiguous.** Stop semantic classification at
  raw-text boundaries; do not infer target-language names.
- **More feature detail can regress latency.** Precompute immutable index facts,
  keep request handlers lookup-only, and measure against the guardrails before
  adding caching layers.
- **Concrete explorer results can become stale or misleading.** Key them by the
  complete slot and corpus digest, label analyzed versus lookup facts, and
  invalidate rather than recompute implicitly after edits.
- **Bundled Python multiplies platform and release risk.** Keep it isolated in
  Slice 2, use a declared support matrix, build reproducibly, and retain the
  external runtime only as an explicit override.
