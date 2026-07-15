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

The next product milestone is **authoring depth**: complete, context-accurate
hover and completion, followed by deeper navigation, semantic highlighting,
and safe source actions. A self-contained Marketplace distribution is a later
release gate and is deliberately separated from authoring behavior.

## Target Outcome

An author editing an incomplete `.tsl` document should be able to discover the
language without memorizing compiler internals:

- hover exposes the useful typed facts already known by the catalog;
- completion proposes fields and values that are valid at the cursor, not just
  values that happen to be nearby in the file;
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
| Hover | Primitive parameter names and declaration location; extension backend and activation facts; author-facing TSIL region forms and purpose; concise documentation links | Compiler catalog index and TSIL descriptors |
| Outer/catalog completion | Top-level declarations, nested block fields, broad enum/boolean/backend values, duplicate-field suppression, and precise nested selector context | Compiler authoring context and vocabulary |
| TSIL shell completion | Region-boundary awareness plus selector terms and named option bags for all registered regions | TSIL registry/descriptors and authoring vocabulary |
| TSIL expression completion | Type/value query roots and continuations, primitive parameters, generic parameters, and named axes | Typed TSIL query rules and primitive scope |
| Symbols/navigation/tokens | More declaration kinds, nested branches, list selectors, target axes, field/parameter/query token classes | Catalog index and LSP feature adapters |
| Explorer analysis | Explicit, cancellable lowering verdicts, transitive dependencies, and final implementation state cached by concrete context | Lowering/dependency closure and explorer command boundary |
| Safe actions | Convert exact compiler suggestions into version-checked `WorkspaceEdit` actions | Diagnostics/audit API and LSP code actions |
| Public distribution | Self-contained, platform-specific server runtime and release verification | Extension packaging and CI |

## Shared Authoring Model

The completion and navigation slices need one compiler-owned view of the
cursor. Add the smallest typed model that can be reused by those features; do
not expose parser dictionaries to the LSP layer.

### `AuthoringCursorContext`

The context should describe facts such as:

- source path, offset, line, indentation, and replacement range;
- enclosing declaration and typed catalog entity when promotion succeeded;
- enclosing block path, for example `primitive.extension.type.safety`;
- whether the cursor is in a field name, scalar value, list value, selector,
  TSIL region boundary, TSIL region shell, or raw target text;
- fields already present in the enclosing mapping;
- active primitive parameters, generic parameters, selector axes, extension,
  and type facts when known;
- a confidence/source marker distinguishing parsed context from the
  incomplete-line fallback.

The parser/source-map layer should construct this context. Completion
providers consume it; they should not rediscover structure with independent
regular expressions.

### `AuthoringCompletion`

Extend the current label-oriented result only as required to carry:

- label and completion kind;
- replacement range;
- concise detail or documentation;
- plain insertion text or an LSP snippet;
- deterministic sort group;
- optional commit characters where they materially improve selector/query
  completion.

The compiler returns semantic completion records. The LSP adapter translates
them to protocol objects, and the VS Code client remains unaware of compiler
rules.

### TSIL authoring descriptors

Region hover and completion need author-facing metadata, not validator function
names. Enrich the existing region descriptor boundary, or add one adjacent
compiler-owned authoring descriptor, with:

- a short purpose statement;
- accepted outer forms;
- selector keys and closed selector values, when applicable;
- named option-bag keys and closed option values, when applicable;
- whether expressions, nested regions, or raw body text are accepted.

The descriptor must be close enough to registration and validation that a new
region cannot silently omit editor vocabulary. Descriptor consistency tests
should fail during compiler testing and extension packaging.

## Ordered Slices

The slices are ordered by authoring dependency. Slice 1 is independent. Slice 2
creates the context foundation required by Slices 3 through 5. Slice 6 is the
direct follow-up to the delivered catalog explorer and may proceed independently
once its lowering-provenance vocabulary is defined. Slice 7 should wait until
source-span behavior is stable. Slice 8 is a separate release track and must not
block the authoring-depth milestone.

### Slice 1: Complete Typed Hover

**Goal:** every supported hover target presents concise author-facing facts
already available from the latest successful catalog index.

**Work:**

- Include primitive parameter names alongside the signature and brief
  description.
- Include the declaration source path and position as a navigable Markdown
  link where the client supports it.
- Include an extension's supported backend IDs and required target features or
  compile modes, omitting empty sections.
- Replace internal TSIL validator names with the region purpose and accepted
  forms from the authoring descriptor.
- Add one concise link to the declaration or relevant maintained guide instead
  of copying long documentation into the hover.
- Keep existing type-group member hover as regression-covered behavior.

**Exit criteria:**

- Exact Markdown tests cover primitives, extensions, type groups, and every
  registered TSIL region.
- Missing optional facts produce clean omission, not placeholders or `None`.
- Hover output is deterministic and contains no internal callable names.
- A test proves hover uses only the supplied index and starts no check,
  selection, lowering, rendering, or subprocess path.

### Slice 2: Parsed Cursor Context And Catalog Completion

**Goal:** outer-language completion is driven by the syntactic role at the
cursor, including incomplete documents.

**Work:**

- Introduce `AuthoringCursorContext` at the parser/source-map boundary and
  migrate existing indentation/regular-expression context checks to it.
- Add top-level declaration keywords with minimal snippets for the declaration
  header only.
- Complete known fields for all authored nested blocks, including safety,
  implementation leaves, variants, activation conditions, size parameters,
  generic parameters, backend blocks, and test metadata represented by the
  current schema.
- Complete closed booleans, enum values, backend IDs, feature IDs, shapes, and
  other typed scalar/list values from their owning schema or registry.
- Make nested implementation selectors aware of extension, type group,
  `ToBase`, `ToExtension`, and `where` axes.
- Suppress singleton fields already present in the current block. Preserve
  repeatable fields where the grammar permits repetition.
- Return typed completion records with replacement ranges, detail, and snippets
  where a snippet saves meaningful typing.
- Preserve current primitive-name completion in `call` selectors and current
  common extension/type-group completion as regression behavior.

**Exit criteria:**

- A table-driven context matrix covers empty files, declaration headers,
  extension/type levels, each nested block family, scalar/list values, and
  malformed current lines.
- `requires` completes activation features, while type positions complete
  datatypes; tests explicitly guard this distinction.
- At `extension.type` mapping scope the provider proposes mapping keys, not
  types.
- Results contain no duplicates, are deterministically ordered, and do not
  suggest fields invalid for the current block.
- The incomplete-line fallback is conservative and cannot reinterpret a
  successfully parsed surrounding block.

### Slice 3: Complete TSIL Region-Shell Completion

**Goal:** completion inside a TSIL body understands registered region
boundaries and each region's accepted shell.

**Work:**

- Use the TSIL scanner and cursor spans to distinguish a valid region boundary,
  an active region shell, nested body content, and raw target text.
- Offer registered region keywords only at valid boundaries.
- Offer selector keys, selector values, named option-bag keys, and closed option
  values from the region authoring descriptors.
- Migrate any existing `cast` and `var` special cases to the shared descriptor
  path; do not retain duplicate hard-coded vocabulary.
- Keep primitive-name completion inside `call<primitive=...>` and make its
  replacement range precise.
- Degrade safely for an unfinished or malformed shell: offer only facts valid
  before the parse error and never guess raw target-language identifiers.

**Exit criteria:**

- Every registered region has positive completion tests for its supported
  shell and negative tests for invalid positions.
- Adding a registered region without the required authoring metadata fails a
  focused consistency test.
- Nested regions and adjacent raw text do not leak completions into each other.
- Generated TextMate keyword checks and semantic completion derive from the
  same registered region inventory.

### Slice 4: TSIL Queries And Primitive Scope

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

### Slice 5: Symbols, Navigation, And Semantic-Token Depth

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

### Slice 6: Explorer Concrete Analysis

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

### Slice 7: Safe Compiler-Owned Code Actions

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

### Slice 8: Self-Contained Marketplace Runtime

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

The authoring-depth milestone is complete when Slices 1 through 7 satisfy their
exit criteria and all of the following hold:

- hover exposes complete concise facts without triggering compiler work;
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
8 and must not be claimed merely because contributor installation works.

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
  Slice 8, use a declared support matrix, build reproducibly, and retain the
  external runtime only as an explicit override.
