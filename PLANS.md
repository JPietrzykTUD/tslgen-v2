# Planning And Execution Guide

This is the repository-wide planning protocol for active `tslc` work. It keeps
changes small, reviewable, and directed at working compiler behavior without
requiring milestone logs or ceremonial plan documents.

## What Counts As A Slice

A slice is one coherent change that a reviewer can understand and validate
without reconstructing a larger historical plan. Good slices usually do one of
these:

- make one source-data form parse, validate, lower, render, or verify;
- add one backend or backend capability boundary;
- add one primitive or primitive-shape family to `tsldata/` and generation;
- improve one diagnostic family;
- remove one obsolete dependency or simplify one boundary;
- strengthen one extension point with focused tests.

A vertical slice may cross parser, catalog, lowering, backend, rendering, and
source-data directories when those edits deliver one behavior. Avoid mixing
unrelated feature work, documentation cleanup, and refactoring. If the result
is hard to name in one sentence, split it.

## Before Editing

Read the root `AGENTS.md`, this file, `CHARTER.md`, and every applicable nested
`AGENTS.md`. For compiler design work, also read `tslc/CHARTER.md` and the
relevant part of `tslc/DESCRIPTION.md`. Use an applicable task skill when one is
available.

Before substantial implementation, write down or hold in working memory:

- **Goal**: the user-visible behavior or cleanup result.
- **Scope**: the source, compiler, assets, tests, and docs likely to change.
- **Out of scope**: adjacent work to leave alone.
- **Boundary**: the stages that own the behavior.
- **Data model**: domain objects or typed records involved.
- **Extension point**: what future backend/primitive/region becomes easier.
- **Projection**: for a tool or derived view, the typed owner of every consumed
  fact and the decisions, if any, that legitimately remain local.
- **Validation**: exact tests and commands to run.
- **Risk**: likely regressions, nondeterminism, diagnostic gaps, or unavailable
  toolchains.

For tiny mechanical changes, this may remain a mental checklist. State the plan
before editing when a change crosses boundaries, changes a contract, or could
expand into a broad rewrite.

## Execution Loop

1. Inspect current code, source data, tests, and documentation before deciding
   the design.
2. Make the smallest change that completes the named slice.
3. Add or update tests at the same boundary as the behavior.
4. Run the smallest focused validation that can fail for the intended reason.
5. Broaden validation when the change crosses stages or affects generated
   artifacts.
6. Re-read the diff for scope, ownership, diagnostics, and determinism.
7. For a new semantic projection or shared registry with no exact task skill,
   run `design-review` again after focused tests and before calling the slice
   complete.
8. Update guidance when behavior, workflow, ownership, or canonical validation
   commands changed. Update every affected task skill in the same slice.
9. Report the result, validation, limitations, and meaningful follow-ups.

The charters and applicable `AGENTS.md` files own architecture invariants. Task
skills own detailed feature procedures and command lists. Do not reproduce
those documents in a plan.

## Choosing Validation

Use the command matrix in the applicable nested `AGENTS.md` or task skill.
Select validation proportionally:

- Documentation-only changes: check links and paths, run focused documentation
  tests when generated-documentation behavior or tooling is involved, and run
  `git diff --check`.
- Source-data changes: run catalog validation plus the selection/lowering or
  generated checks for the affected behavior.
- Compiler logic changes: run `compileall` and focused pytest at the owning
  boundary; run mypy when typed models, protocols, or public signatures change.
- Cross-stage compiler changes: broaden to the full Python suite.
- New semantic projections or shared registries without an exact task skill:
  add an owner-equivalence test and an additive probe using the next plausible
  backend, family, namespace, region, or case kind. If raw target text is in
  scope, prove that it remains opaque or that unsupported semantics are rejected
  without rewriting it.
- Generated layout, backend codegen, verification, or executable value-test
  changes: run the opt-in generated build/value gates for the smallest useful
  primitive/profile/backend matrix.
- Hardware-specific checks: use injectable runners or explicit skips when the
  required hardware or emulator is unavailable.

Always run `git diff --check`. Treat a skipped generated case as an explicit
verification gap to report, not as proof of success.

## Review Packet

For a non-trivial change, the final report should make review cheap:

- what changed and why it belongs in the slice;
- files or ownership boundaries touched;
- tests added or changed;
- commands run and results;
- known limitations or skipped verification;
- follow-ups intentionally excluded from the slice.

## Stop Conditions

Stop and ask or report a blocker when:

- required behavior conflicts across active source/data evidence;
- a backend contract cannot be inferred from typed data or current assets;
- a proposed abstraction depends mostly on guessed future needs;
- a test would require unavailable hardware without an injectable substitute;
- the slice is turning into a broad rewrite without a clear delivered behavior;
- completion requires deleting the only active evidence or baseline for current
  behavior;
- completion requires a product, public-corpus, or compatibility decision that
  the user has not authorized.
