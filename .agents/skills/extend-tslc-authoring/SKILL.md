---
name: extend-tslc-authoring
description: Add or change compiler-owned authoring and LSP capabilities in tslc. Use when asked to implement or repair diagnostics, hover, navigation, references, completion, semantic tokens, code actions, workspace snapshots or caches, primitive explorer or scaffolding, specialization context, LSP protocol records, or thin editor presentation backed by those facts.
---

# Extend TSLC Authoring

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, the authoring section of `tslc/DESCRIPTION.md`, and the
   relevant `tslc/src/tslc/authoring*.py`, `catalog_index*.py`, and `lsp/`
   paths. Read `editors/vscode-tsl/AGENTS.md` before changing the client.
2. Classify the feature before editing: ordinary live snapshot projection,
   explicit saved-corpus child action, editor-neutral protocol adaptation, or
   client-only presentation. Do not move an expensive or stateful action into
   the live language-server path for convenience.
3. Identify the canonical typed compiler owner for every displayed or returned
   fact. Reuse public catalog, selector, region/query registry, lowering, or
   diagnostic projections; extend the owner when a fact is missing instead of
   recreating it in authoring or TypeScript code.
4. Keep ordinary live features pure and snapshot-based. They may parse and
   validate overlays but must not load render assets, lower specializations,
   write projects, or invoke toolchains. Profile-aware views consume the
   workspace's immutable configured profiles rather than reloading them per
   request. Preserve stale result suppression, immutable snapshots, and the last
   valid index/context when an edited document is temporarily invalid.
5. Preserve exact source spans and document identity. Convert positions to
   UTF-16 only at the LSP adapter. Bind edits to version, digest, range, and
   expected text so stale actions fail safely.
6. Make explorer, specialization, scaffold, and query views consume the real
   catalog, `Selector`, selector-path projection, registered TSIL descriptors,
   and backend query data. Add a synthetic next backend, namespace, selector
   shape, or region test when the feature crosses one of those extension points.
7. Keep the TypeScript client limited to transport, cancellation, caching,
   presentation, and applying server-provided edits. Generate shared keyword
   inventories from compiler registries; never copy compiler semantics into the
   client.
8. Add focused tests at the compiler projection, workspace snapshot, LSP
   protocol, and client boundary touched by the change. Prove deterministic
   ordering, malformed-overlay behavior, stale-request handling, and that
   ordinary live features reuse rather than reimplement selection and do not
   lower specializations, render projects, or invoke toolchains.

## Checks

- A new compiler fact has one typed owner and every authoring surface projects
  that owner rather than maintaining a parallel table or classifier.
- Initially invalid and temporarily invalid documents retain honest diagnostics
  without replacing the last successful catalog/index with partial state.
- Explicit preview or analysis remains cancellable, saved-corpus-only, and
  outside the language-server process.
- The editor client contains no TSL parsing, selector rules, backend knowledge,
  or TSIL vocabulary.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_authoring_check.py tslc/tests/test_authoring_completion.py tslc/tests/test_authoring_fixes.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_index_authoring.py tslc/tests/test_query_authoring.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_lsp_*.py tslc/tests/test_authoring_tools.py
(cd editors/vscode-tsl && npm test)
(cd editors/vscode-tsl && xvfb-run -a npm run test:integration)
git diff --check
```
