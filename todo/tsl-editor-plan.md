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
direct authored Calls/Called By relationships. Those lookup features remain
separate from the unfinished concrete-analysis work below: `available` and
`authored` do not yet imply a final native/composed/fallback verdict.

This is the execution plan for the remaining editor work. It should contain
only unfinished behavior. When a slice meets its exit criteria, remove that
slice rather than preserving a completion log here. Git history and tests are
the completion record.

Parsed outer-language context, catalog completion, and descriptor-driven TSIL
region-shell completion are now part of the working baseline. The next product
milestone continues **authoring depth** with query-aware TSIL completion,
deeper navigation, semantic highlighting, and safe source actions.
A self-contained Marketplace distribution is a later release gate and is
deliberately separated from authoring behavior.

## Target Outcome

An author editing an incomplete `.tsl` document should be able to discover the
language without memorizing compiler internals:

- TSIL completion understands region shells, queries, and the current
  primitive's scope without interpreting raw target-language text;
- symbols, definitions, references, and semantic tokens cover the same typed
  declarations and selectors;
- an explicit explorer analysis can explain the lowered implementation state
  and active transitive dependency closure for one concrete slot without
  slowing ordinary explorer refreshes;
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
| TSIL expression completion | Type/value query roots and continuations, primitive parameters, generic parameters, and named axes | Typed TSIL query rules and primitive scope |
| Symbols/navigation/tokens | More declaration kinds, nested branches, list selectors, target axes, field/parameter/query token classes | Catalog index and LSP feature adapters |
| Explorer analysis | Explicit, cancellable lowering verdicts, transitive dependencies, and final implementation state cached by concrete context | Lowering/dependency closure and explorer command boundary |
| Safe actions | Convert exact compiler suggestions into version-checked `WorkspaceEdit` actions | Diagnostics/audit API and LSP code actions |
| Public distribution | Self-contained, platform-specific server runtime and release verification | Extension packaging and CI |

## Ordered Slices

The slices are ordered by authoring dependency. Slices 1 and 2 build on the
delivered parsed cursor and TSIL region context. Slice 3 is the direct follow-up
to the catalog explorer and may proceed independently once its
lowering-provenance vocabulary is defined. Slice 4 should wait until
source-span behavior is stable. Slice 5 is a separate release track and must
not block the authoring-depth milestone.

### Slice 1: TSIL Queries And Primitive Scope

**Goal:** expression completion exposes compiler-known query paths and names in
the current primitive without attempting target-language analysis.

**Work:**

- Complete supported query roots such as type, value, base, vector, scalar, and
  generic concepts from the typed query model actually accepted by lowering.
- After each root/segment, offer only valid continuations and close the
  completion path when the query is terminal.
- Complete current primitive parameters, generic parameters, and named
  selector axes where their role is unambiguous.
- Attach concise type/role detail so same-named values can be distinguished.
- Reuse lowering/query descriptors rather than encoding accepted paths in the
  LSP adapter.

**Exit criteria:**

- Tests cover each supported root, valid continuation, terminal path, and
  representative invalid continuation.
- Parameter completion changes with the enclosing primitive and is absent when
  no reliable primitive scope exists.
- Raw C++/Rust identifiers are never offered or classified by this feature.
- Completion remains a pure lookup against precomputed catalog/query facts.

### Slice 2: Symbols, Navigation, And Semantic-Token Depth

**Goal:** structural browsing and highlighting cover the same declarations and
references recognized by the authoring model.

**Work:**

- Add document symbols for all parsed top-level declaration kinds and useful
  nested declaration nodes, including implementation branches, variants,
  generic parameters, and test cases where named.
- Index individual elements of list-valued selectors instead of treating the
  complete list as one reference.
- Add definitions and references for nested target axes and other typed
  selectors once their ownership is unambiguous.
- Add semantic token classes for declaration keywords, known field names,
  parameters, selector keys/values, query roots, and closed enum values.
- Use `AuthoringCursorContext` and catalog/source spans for classification; do
  not introduce a TextMate-derived semantic parser.

**Exit criteria:**

- Symbol hierarchy tests cover every supported declaration and nested symbol
  kind with stable names and ranges.
- Definition/reference tests cover single and list selectors, including
  unresolved and ambiguous cases.
- Semantic token snapshots cover complete and incomplete documents and never
  classify raw target code as TSL semantics.
- Existing primitive-call and extension navigation remains regression covered.

### Slice 3: Explorer Concrete Analysis

**Goal:** enrich the catalog explorer with authoritative lowering and transitive
dependency facts behind an explicit, cached analysis boundary.

**Work:**

- Define compiler-owned typed provenance for native, composed, fallback, and
  unknown outcomes. Derive it from selection, lowering, and dependency
  propagation; never infer it by scanning raw implementation text in the
  extension.
- Add an explicit **Analyze Concrete Specialization** action on a slot. Reuse
  the explorer's primitive/profile/backend/extension/type context, show
  cancellable progress, and require no redundant prompts when the context is
  already complete.
- Report the active transitive call closure for that lowered specialization,
  including unresolved or failed dependencies with a concise reason. Keep it
  distinct from the existing direct authored Calls/Called By graph, which may
  include branches inactive for the selected slot.
- Present the verdict and dependency tree in an analyzed-result node or detail
  view. Include textual labels and tooltips in addition to icons, and make each
  resolved dependency navigable to its selected implementation.
- Cache results by corpus/input digest, primitive, profile, backend, extension,
  and type. Reuse a valid result across view refreshes and mark it stale, rather
  than silently recomputing it, after a relevant edit or configuration change.
- Keep the existing slot-origin and direct Calls/Called By views independent of
  concrete lowering.

**Exit criteria:**

- Concrete state is labelled `analyzed` and never confused with authored
  selector origin or selected availability; tests cover all four verdicts.
- The dependency tree represents only the active lowered specialization,
  detects cycles deterministically, and preserves actionable unresolved-edge
  diagnostics.
- The command uses the slot already selected in the explorer and never asks for
  profile, backend, extension, or type again.
- Repeating an unchanged analysis is served from the complete-context cache;
  changing any cache dimension cannot reuse the old verdict.
- Cancelling or failing analysis leaves the last valid catalog explorer usable.
- No automatic edit, hover, selection, or refresh triggers concrete analysis.

### Slice 4: Safe Compiler-Owned Code Actions

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

### Slice 5: Self-Contained Marketplace Runtime

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

The authoring-depth milestone is complete when Slices 1 through 4 satisfy their
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
6 and must not be claimed merely because contributor installation works.

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
  Slice 5, use a declared support matrix, build reproducibly, and retain the
  external runtime only as an explicit override.
