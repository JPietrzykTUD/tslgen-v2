# Overload Specification Implementation Plan

## Status and authority

This plan implements the source-owned overload specification settled in
`todo/overload-spec-plan.md`. That document is the product contract and remains
authoritative if this plan is ambiguous.

This feature is intentionally independent of the Rust API. It adds source data,
typed compiler semantics, validation, and editor support. It does not change
lowered specializations, emitted names, generated C++ or Rust APIs, facades,
templates, documentation for generated APIs, value tests, or benchmarks. A
later Rust-API slice may consume the typed catalog fact established here, but it
must not shape or duplicate this schema.

The settled facts are:

- a primitive `overload` block has exactly required `axis`, required `value`,
  and optional boolean `primary` (default `false`);
- the initial registry contains exactly
  `count_distribution={uniform, per_lane}` and
  `payload_extent={vector, scalar}`;
- immediate binding, mask policy, generic parameters, result targets, and
  implementation safety retain their existing typed owners;
- one source declaration marks the primary value for each primitive name and
  overload axis, and the compiler promotes that marker to every declaration of
  the same value;
- only `shift_left`, `shift_right`, and `store` are annotated in the current
  corpus.

## Pre-implementation design-review findings

### Blocking: registry syntax is still an explicit product decision

The ground-truth plan leaves the exact syntax and location of the source-owned
axis/value registry open. The recommended form is specified below. Because this
is a public corpus/schema decision, implementation must not silently choose a
different form.

The Rust suffix for `per_lane`, Rust name composition, result-target spelling,
and active-lane mask spelling are not blockers: they are outside this feature.

### High: wildcard expansion can create false duplicate-primary errors

`aligned=*` and `packed=*` expand one source declaration into multiple catalog
`Primitive` objects. `store` uses this mechanism. Counting `primary true` on the
expanded catalog would therefore report duplicates that do not exist in source.

Primary-marker cardinality must be checked by unique source declaration/source
span. The resolved primary value may then apply to every expanded typed variant.

### High: semantic overloads are not signature overload identity

`catalog/signature_kinds.py` and
`LoweredSpecialization.param_identity_tokens` already own target-language
parameter-type identity. They must not be renamed, repurposed, or extended to
mean `count_distribution` or `payload_extent`. The new semantic overload fact
ends at the catalog boundary in this feature.

### High: the editor must project compiler facts, not copy the registry

Primitive-field completion currently shares some schema constants, but closed
overload values, hover, navigation, and semantic tokens do not exist. Adding a
second editor vocabulary would drift. Completion, hover,
definitions/references, symbols/tokens, and diagnostics must consume the same
promoted registry and validated catalog used by batch `tslc check`.

### Medium: the current corpus must not become an inference table

It would be easy to recognize the last `s`, `sImm`, or `v` parameter of shifts,
or branch on the name `store`. That would make the next overload axis require
more compiler special cases. Compatibility must instead be checked from
source-declared registry rules and typed signature structure. Parameter names,
documentation prose, primitive names, and raw TSIL/target text are never
semantic inputs.

### Medium: no backend transport type is justified yet

Adding overload fields to selection or `LoweredSpecialization` before a backend
consumer exists would be speculative plumbing and would couple this feature to
the future Rust API. The typed `Catalog` is the handoff boundary for now. The
editor is the first compiler-owned projection and gives the new model immediate
behavioral value.

## Goal, scope, and non-goals

### Goal

After this work, TSL authors can declare and discover semantic overload axes in
source data. The compiler parses them into immutable catalog values, validates
the complete same-name family, resolves its primary value once, and exposes the
same facts through batch diagnostics and the editor. Invalid metadata produces
deterministic, source-located, actionable diagnostics.

### In scope

- a source-owned overload-axis registry under `tsldata/detail`;
- the exact three-key primitive `overload` block;
- typed catalog models and cross-declaration validation;
- annotations for all current `shift_left`, `shift_right`, and `store` forms;
- compiler-owned editor diagnostics, completion, hover, navigation,
  references, document symbols, and semantic tokens;
- VS Code integration coverage proving that the Python LSP projection reaches
  the editor without duplicating semantics in TypeScript;
- focused parser/catalog/authoring/LSP tests and architecture documentation.

### Out of scope

- any Rust or C++ API, naming, facade, lowering, render, or generated-project
  change;
- propagation into `LoweredSpecialization` in this feature. It is a required
  follow-up for the Rust-API integration described below;
- generated API documentation, executable value tests, or benchmarks;
- overload annotations for any other current primitive family;
- treating `sImm`, `mask`, `generic_params`, or `return_type` as overload
  values;
- public API decisions for active-lane reductions or result-target families;
- primitive implementation-body changes or target-language parsing;
- editor code actions that guess an axis, value, or primary declaration;
- opportunistically refactoring existing name-specific facade logic.

## Recommended source contract — decision gate A

Add one top-level declaration in `tsldata/detail/overload_axes.tsl`:

```text
overload_axes:
  count_distribution:
    values:
      uniform:
        operand_kinds [s, sImm]
      per_lane:
        operand_kinds [v]
  payload_extent:
    values:
      vector:
        operand_kinds [v]
      scalar:
        operand_kinds [s]
```

The semantic registry still contains exactly the four settled axis/value pairs.
`operand_kinds` is registry validation data, not another primitive-overload
field and not a target-language spelling. It expresses facts already required
by the settled validation rules:

- uniform counts accept runtime scalar or compile-time scalar-immediate kinds;
- per-lane counts accept a vector kind;
- vector payloads accept a vector kind;
- scalar payloads accept a scalar kind.

This is preferable to a bare `axis [values]` list because a bare list would
force the compatibility rules into Python branches keyed by axis/value. It is
also preferable to an operand name in every primitive: the settled primitive
block has exactly three keys, and the distinguishing operand can be located
structurally within the typed family.

The initial registry rule language stops at `operand_kinds`. Do not design a
general constraint framework. If a future proven axis cannot be validated by
one discriminating operand, add the next semantic registry concept in a
separate slice.

The primitive annotations are exactly those from the ground-truth plan:

- `shift_left` runtime scalar: `count_distribution=uniform`, `primary true`;
- `shift_left` immediate and masked immediate: `count_distribution=uniform`;
- `shift_left` vector count: `count_distribution=per_lane`;
- all three `shift_right` declarations: runtime scalar is the one primary
  uniform declaration, immediate is uniform, vector count is per-lane;
- `store(ptr, v)`: `payload_extent=vector`, `primary true`;
- masked `store(mask, ptr, v)`: `payload_extent=vector`;
- `store(ptr, s)`: `payload_extent=scalar`.

Do not annotate `permute_lanes`, reductions, masked arithmetic, or result-target
families merely to exercise the feature.

## Typed ownership

```text
tsldata/detail/overload_axes.tsl + primitive overload blocks
                              |
                              v
              generic outer parsed fields
                              |
                              v
       OverloadRegistry + PrimitiveOverload in Catalog
                              |
                    family validation
                              |
                              v
             ResolvedPrimitiveOverload
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
        batch diagnostics              editor/LSP projections
```

The focused domain types belong in
`tslc/src/tslc/catalog/overloads.py`, not in support policy, authoring, or a
backend:

- `OverloadValueSpec`: value name, accepted operand signature kinds, and source
  span;
- `OverloadAxisSpec`: axis name, immutable value mapping, and source span;
- `OverloadRegistry`: immutable sorted axis mapping plus lookup and
  compatibility behavior;
- `PrimitiveOverload`: one source declaration's axis, value,
  `declares_primary` marker, and relevant source spans;
- `ResolvedPrimitiveOverload`: axis, value, and `is_primary_value` after family
  validation/resolution.

All are frozen and slotted. If implementation shows that either spec type is
only a wrapper with no invariant or useful behavior, collapse it rather than
creating plumbing. Plain dictionaries are acceptable while promoting parsed
fields; catalog and editor logic consume typed immutable objects.

Add `Primitive.overload: PrimitiveOverload | None` and
`Catalog.overload_registry: OverloadRegistry`. The catalog builds a private,
deterministic primary-value index keyed by `(primitive_name, axis)`, using
unique source markers, and exposes one method that resolves a primitive's
authored value to `ResolvedPrimitiveOverload`. Validation and editor consumers
must not rescan sibling declarations independently.

No field is added to selection or lowering in this plan. This does not mean the
fact ends permanently at the catalog:

- `SelectedImplementation` already carries `primitive: Primitive`, so selection
  preserves `Primitive.overload` without another field;
- constructing `LoweredSpecialization` is the point where that catalog object
  is intentionally flattened and the overload fact would otherwise be lost;
- the later Rust-API integration must therefore resolve the selected
  primitive's overload through the catalog and add a backend-neutral
  `ResolvedPrimitiveOverload | None` field to `LoweredSpecialization` (or to an
  equally explicit typed pre-backend facade model if one exists by then);
- dependency closure, specialization replacement, emitted-name finalization,
  documentation, tests, and benchmarks must then preserve or consume that
  carried fact without reconstructing it from signatures or names.

That transport change belongs to the Rust-API vertical slice because this
feature has no lowering/backend consumer yet. Keeping it deferred avoids an
unused lowered field while fixing the catalog contract that the later slice
must consume.

### Required handoff to the future Rust-API slice

The Rust-API work starts from the validated catalog owner established here. Its
first semantic step is:

```text
SelectedImplementation.primitive.overload
                  + Catalog.resolve_primitive_overload(...)
                                  |
                                  v
         LoweredSpecialization.overload
                                  |
                                  v
              Rust facade/name planning
```

The future slice must verify uniform runtime, uniform immediate, masked
uniform, per-lane, vector-payload, and scalar-payload forms. It must not add a
second overload registry, infer roles from parameter kinds, or branch on
`shift_left`, `shift_right`, or `store`.

## Implementation slices

Each slice is independently reviewable. Do not combine schema, corpus, and
editor work into one large patch.

### Slice 1 — promote the source-owned registry

**Outcome:** the catalog contains the exact closed registry, but no primitive
uses it yet.

1. Add `tsldata/detail/overload_axes.tsl` after decision gate A is accepted.
2. Reuse the grammar's generic top-level field form. Do not add a Lark keyword
   or dedicated grammar production unless the existing form demonstrably
   cannot preserve the required spans.
3. Add a focused promoter such as
   `tslc/src/tslc/catalog/_builder_overloads.py`, following the existing
   `target_families` top-level-field pattern.
4. Add `overload_registry` to `Catalog` and freeze/sort its mappings at the
   model boundary.
5. Add a focused schema validator such as
   `catalog/validation/_schema_overloads.py` and route `overload_axes` from
   `schema_validation.py`.
6. Validate:
   - exactly one top-level registry declaration;
   - known registry keys (`values`, then `operand_kinds`);
   - non-empty axis and value names;
   - a non-empty values map for each axis;
   - non-empty `operand_kinds` lists;
   - every operand kind through `DEFAULT_SIGNATURE_KINDS`, not a duplicate
     string table;
   - duplicate axes, values, and kinds with related locations where useful.

**Tests:** extend `test_catalog.py` and `test_catalog_validation.py` with valid
promotion, immutability, duplicate/unknown field, missing value, bad
signature-kind, and stable diagnostic-order cases. Add a parser test only if a
parser change is actually needed.

**Acceptance:** the registry is source-owned, typed, immutable, and the four
valid pairs are not separately listed in production Python.

### Slice 2 — parse and promote primitive `overload` blocks

**Outcome:** any primitive declaration can carry the exact three-key block as a
typed value.

1. Add `overload` to `ParsedPrimitiveFieldKind` and the parser's known
   primitive-field map. Preserve unknown fields as today so normal schema
   diagnostics retain their source path.
2. Add `overload` to `KNOWN_PRIMITIVE_FIELDS`.
3. Validate the block locally in `_schema_primitives.py` or a focused helper:
   - only `axis`, `value`, and `primary` are accepted;
   - `axis` and `value` are required exactly once;
   - `primary` is optional, occurs at most once, and is `true` or `false`;
   - scalar values are required; lists/maps are rejected with source-located
     diagnostics.
4. Promote it in `_builder_primitives.py` to `PrimitiveOverload`, retaining
   axis/value/primary spans. Omitted `primary` becomes `False`.
5. Do not validate registry membership in the parser or promoter; that requires
   the complete catalog and belongs to catalog invariants.

**Tests:** valid block, omitted/false/true primary, missing axis, missing value,
duplicate key, unknown key, non-boolean primary, and malformed scalar shape.

**Acceptance:** catalog consumers see `PrimitiveOverload | None`, never a raw
map, and primitives without the block behave identically.

### Slice 3 — validate and resolve overload families

**Outcome:** the catalog proves the settled cross-declaration invariants once
and exposes a resolved primary value.

Add a focused invariant entry point from
`catalog/validation/invariants.py` and call it from `validate_catalog`.
Validation operates on unique source declaration spans so wildcard expansion
does not change declaration cardinality.

For the initial one-axis model, once any declaration of a primitive name has an
`overload` block, all declarations of that name are members of the family and
must declare the same axis. This matches every current annotated family and
makes omissions diagnosable. A future need for multiple independent overload
axes under one name requires an explicit schema extension, not inference.

Validate in this order to avoid cascading diagnostics:

1. **Registry membership:** the axis exists and the value belongs to that exact
   axis.
2. **Family completeness:** no unannotated same-name declaration and no mixed
   axes within the family.
3. **Primary marker:** exactly one unique source declaration has
   `primary true`; missing or duplicate markers include related locations.
4. **Primary promotion:** the marker's value becomes the family's primary
   value; all declarations of that value, including immediate/masked siblings
   and wildcard expansions, resolve `is_primary_value=True`.
5. **Canonical signature alignment:** parse every signature with the existing
   signature model. Remove a leading control mask only when the declaration has
   an explicit `mask` policy. Do not remove an ordinary `m` parameter from an
   active-lane or mask-algebra primitive. Remaining family members must align
   in result and arity.
6. **Discriminating operand:** exactly one aligned parameter position may carry
   the union of registry `operand_kinds` for the family's values. Each
   declaration's kind at that position must be accepted for its value. Other
   positions retain their normal typed identity.
7. **Composite uniqueness:** reject duplicate declarations using overload value
   plus existing typed facts: normalized signature/binding time, mask policy and
   other semantic attributes, generic parameters, and result-target dimension.
   Do not copy those facts into the overload model. Existing duplicate-primitive
   diagnostics remain active and cannot be bypassed by changing metadata.

Use stable `TSL-CATALOG-OVERLOAD-*` codes, with distinct diagnostics for unknown
axis, invalid value, missing member metadata, mixed axis, missing primary,
duplicate primary, shape mismatch, and duplicate composite identity. Messages
name the primitive, axis/value, observed signature kind, and accepted
values/kinds.

**Required negative fixtures:**

- `count_distribution=scalar` and `payload_extent=uniform`;
- swapped `uniform`/`per_lane` operand kinds;
- unknown axis/value;
- one missing block in an otherwise annotated family;
- two primary markers for the same value and for different values;
- no primary marker;
- an explicit-policy masked sibling that aligns after its leading mask is
  removed;
- an ordinary leading-mask reduction that is not normalized as policy masking;
- wildcard-expanded `store` with one source primary marker and no false
  duplicate;
- duplicate-header result-target declarations that remain distinguished by
  `return_type`.

**Acceptance:** every valid annotated family has one resolved primary value,
and no consumer needs to interpret primitive names or raw signatures.

### Slice 4 — annotate the current corpus

**Outcome:** the settled current families are the first production users.

1. Edit only:
   - `tsldata/primitives/bitwise/shifts.tsl`;
   - `tsldata/primitives/load_store/store.tsl`.
2. Add the exact `shift_left`, `shift_right`, and `store` blocks enumerated in
   the ground-truth plan and above.
3. Do not edit implementation bodies, authored tests, benchmarks, attributes,
   `generic_params`, or signatures.
4. Add inventory assertions that the authored declaration count remains 160
   and wildcard-expanded primitive count remains 172. If unrelated concurrent
   work legitimately changes the corpus, review and update the inventory rather
   than blindly changing expected numbers.
5. Assert every declaration of those three names is annotated and no other
   current name is annotated.

**Validation:** run `PYTHONPATH=tslc/src python -m tslc check`, then focused
catalog/validation tests.

**Acceptance:** the entire corpus validates and exact inventory assertions make
an omitted family member visible.

### Slice 5 — adapt compiler-owned authoring and indexing

**Outcome:** editor features expose the complete schema without a parallel
vocabulary.

#### Completion

1. Add `overload_axes` to top-level completion.
2. Add `overload` to primitive-field completion.
3. Inside `overload`, offer exactly `axis`, `value`, and `primary`, excluding
   keys already present.
4. Complete `axis` from `Catalog.overload_registry`.
5. Complete `value` only from the declaration's selected axis. Never offer the
   union of values from all axes.
6. Complete `primary` from the shared boolean vocabulary.
7. Complete registry fields, axes, values, and `operand_kinds` from the same
   typed/parser owners used by validation.

If axis-dependent value completion needs the sibling `axis` from an in-progress
mapping, extend `AuthoringCursorContext` with one small parsed sibling-scalar
fact. Do not reparse slices of editor text in `authoring_completion.py`, and do
not add an overload-specific mini-parser.

#### Hover and navigation

1. Add scoped overload-axis and overload-value occurrences to
   `catalog_index.py`. A value is keyed by `(axis, value)` because identical
   value words may be legal on different future axes.
2. Index registry axes/values as definitions and primitive `axis`/`value`
   fields as references.
3. Go-to-definition on an axis or value resolves to
   `tsldata/detail/overload_axes.tsl`.
4. Find-references on a registry value returns every annotated declaration with
   that exact axis/value and optionally its definition according to the existing
   LSP flag.
5. Axis hover lists registered values. Value hover states its axis and accepted
   operand kinds. On a primitive declaration, hover may additionally state
   whether the resolved value is primary for that primitive family.
6. Format hover from `OverloadRegistry` and the catalog resolver; do not keep a
   prose lookup table.

#### Symbols and semantic tokens

1. Extend `catalog_authoring_index.py` with editor-neutral symbol/token facts
   for the top-level registry, its axes, and its values.
2. Use existing token kinds: registry axes as properties/classes and values as
   enum members. Do not add an LSP token type for one schema feature.
3. Include the primitive overload block in document symbols only if it improves
   the existing hierarchy; generic field symbols are sufficient if a dedicated
   node would add noise.
4. Tokenize primitive axis/value references consistently with their registry
   definitions.

#### Diagnostics and fixes

1. The workspace publishes the same catalog diagnostics as batch `tslc check`;
   do not add LSP-only validators.
2. Confirm that related locations survive LSP conversion for duplicate primary
   and mixed-axis errors.
3. Do not add initial code actions for missing/invalid values or primary
   markers: choosing them is a semantic author decision. Completion and precise
   diagnostics are the safe first UX.

**Owner-equivalence test:** for every axis, compare schema acceptance,
completion labels, hover facts, definitions, and semantic-token classification
against the same `OverloadRegistry` instance. The test must fail if an
authoring-only axis/value table is introduced.

**Focused tests:** extend:

- `tslc/tests/test_authoring_completion.py`;
- `tslc/tests/test_catalog_hover.py`;
- `tslc/tests/test_catalog_index_authoring.py`;
- `tslc/tests/test_lsp_workspace.py`;
- `tslc/tests/test_lsp_protocol.py` only if standard capability wiring changes.

Cover valid and incomplete blocks, unknown axes, axis-dependent value
completion, hover/definition/reference round trips, semantic tokens, document
symbols, related diagnostics, and latest-successful-catalog behavior after a
broken edit.

**Acceptance:** ordinary live features remain pure projections of the latest
successful typed catalog/index and perform no selection, lowering, rendering,
filesystem writes, or toolchain work.

### Slice 6 — prove VS Code presentation end to end

**Outcome:** the installed editor exposes the compiler features without owning
TSL overload semantics.

1. No TypeScript client source change is expected: completion, hover,
   definitions/references, diagnostics, document symbols, and semantic tokens
   already use standard LSP wiring.
2. Do not add axis/value arrays, validation, or parsing to
   `editors/vscode-tsl`.
3. Do not edit the TextMate keyword inventory merely to recognize `overload` or
   `overload_axes`; the structural grammar already handles ordinary field keys.
   Change the template only if an integration test proves structural coloring
   is wrong, then regenerate rather than editing generated JSON.
4. Add an integration fixture/test in
   `editors/vscode-tsl/test/integration/extension.test.ts` that opens a TSL
   document and proves at least:
   - `axis` completion comes from the source registry;
   - `value` completion is axis-scoped;
   - hover on a value contains registry-derived facts;
   - go-to-definition reaches the registry declaration;
   - an invalid pair appears with its compiler diagnostic code.
5. Keep assertions on semantic behavior and stable codes, not UI timing or
   internal Python object names.

If the existing integration harness cannot inspect one LSP feature without new
client code, first add a test-only helper around the standard VS Code command.
Do not add production command wiring for a feature already supplied by LSP.

**Validation:** run `(cd editors/vscode-tsl && npm test)` and
`(cd editors/vscode-tsl && xvfb-run -a npm run test:integration)`. Packaging is
not required unless client or extension-manifest files changed. If they did,
also run `npm run package`.

**Acceptance:** the VS Code client remains a thin transport/presentation layer,
and the end-to-end test proves the feature is visible to an editor user.

### Slice 7 — architecture documentation and final review

**Outcome:** active design documentation and evidence match the implemented
owner.

1. Update `tslc/DESCRIPTION.md` with the source registry, primitive catalog
   fact, cross-family validation, and authoring/index projection. Do not copy
   this plan or the complete registry into the architecture description.
2. Update author-facing source-schema documentation only if an existing guide
   already documents primitive fields. Do not create a second enum registry in
   prose.
3. Explicitly state that backend/API consumption is deferred and no
   `LoweredSpecialization` contract changed.
4. Run the validation matrix and mandatory post-implementation design review.

## Validation matrix

Run from the repository root, starting focused and broadening only after the
owning slice passes.

### Schema, catalog, and corpus

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog.py \
  tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m tslc check
```

### Authoring and LSP

```bash
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_authoring_completion.py \
  tslc/tests/test_catalog_hover.py \
  tslc/tests/test_catalog_index_authoring.py \
  tslc/tests/test_lsp_workspace.py \
  tslc/tests/test_lsp_protocol.py
```

### VS Code client/integration

```bash
(cd editors/vscode-tsl && npm test)
(cd editors/vscode-tsl && xvfb-run -a npm run test:integration)
```

Run `(cd editors/vscode-tsl && npm run package)` only if client or extension
packaging inputs changed.

### Repository-wide checks

```bash
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

Generated build/value gates are not required because this feature deliberately
does not change selection, lowering, render models, or generated artifacts. If
the implementation unexpectedly requires such a change, stop: the slice has
crossed into API/backend work and needs a separate approved plan.

## Design-review guardrails during implementation

Apply these at the end of every slice, not only during final review.

### Source of truth and ownership

- There is one source registry and one typed promoted owner.
- No axis/value list appears in authoring, LSP, support policy, lowering, a
  backend, template, or renderer.
- No new compiler branch names `shift_left`, `shift_right`, or `store`.
- No behavior is inferred from parameter names, comments, docs, or raw target
  text.
- Existing `sImm`, `mask`, `generic_params`, `return_type`, attributes, safety,
  and signature identity are referenced rather than copied.

### Pipeline and separation

- Parsing accepts structure; the catalog owns semantics and family invariants.
- The feature stops at the typed catalog and compiler-owned authoring/index
  projection.
- Selection, lowering, closure, emitted names, facade planning, render models,
  and generated assets have no overload-spec changes.
- The editor reads the latest successful catalog/index and never generates a
  project or invokes a toolchain.
- The VS Code client owns transport and presentation only.

### KISS and DRY

- Do not create a generic constraint framework around `operand_kinds`.
- Do not add request/result/handoff wrappers for one registry value.
- Prefer one focused catalog module and direct pure functions over an overload
  manager hierarchy.
- Extend existing scoped-symbol/index patterns rather than inventing a second
  authoring index.
- Refactor an existing module only when required for this owner or projection.

### Diagnostics and determinism

- Every invalid source form has a structured code and best available source
  span.
- Cross-declaration conflicts include related locations.
- Diagnostics, registry mappings, completion items, references, and symbols use
  deterministic ordering.
- Unknown future pairs fail closed and never become arbitrary identifiers.

### Compatibility

- Unannotated primitive families remain behaviorally unchanged.
- Generated C++ and Rust artifacts remain unchanged because backends never see
  this new fact.
- The 160 authored declarations and 172 expanded catalog primitives remain
  representable.
- `permute_lanes`, active reductions, and result-target duplicate headers retain
  their current typed distinctions without overload annotations.

## Additive and equivalence probes

This feature introduces a shared registry with no exact pre-existing task
skill, so two probes are mandatory.

### Owner-equivalence probe

Build a test catalog from a small source registry and assert that:

- catalog lookup accepts exactly its pairs;
- invalid-pair diagnostics name the same allowed values;
- completion offers the same axes and axis-scoped values;
- hover reports the same operand kinds;
- definition/reference indexing resolves to the same source spans.

The test imports no authoring-owned enum table because none should exist.

### Additive next-axis probe

In a test-only source fixture, add a plausible new axis with two values and
`operand_kinds`, then add a two-declaration primitive family. It must parse,
promote, validate, resolve primary status, complete, hover, and navigate without
editing parser dispatch, validation branches, or editor logic. Only source
fixture data should name the synthetic axis/values.

The probe ends at catalog/editor behavior. It does not require a Rust or C++
spelling and must not generate code.

## Mandatory post-implementation design review

After focused tests pass and before the full suite, review the actual diff
against the repository and compiler charters. Report findings by severity with
file/line references. The review must explicitly answer:

1. **Typed owner:** Can every validation and editor fact be traced to
   `OverloadRegistry`, `PrimitiveOverload`, or the catalog resolver?
2. **No re-derivation:** Does any consumer inspect a primitive name, parameter
   name, raw signature string, or target text to rediscover semantics?
3. **Existing-owner composition:** Are immediate, mask, generic, target, safety,
   and signature-identity facts still owned where they were before?
4. **API separation:** Is there truly no selection, lowering, backend, emitted
   name, render, generated documentation, value-test, or benchmark change?
5. **Editor equivalence:** Do diagnostics, completion, hover, navigation,
   references, symbols, and tokens use the same registry/catalog owner?
6. **Thin client:** Did TypeScript remain free of TSL parsing, semantic enums,
   and validation?
7. **Additive extension:** Does the synthetic next-axis fixture require only
   source data?
8. **Diagnostics:** Are all cross-file errors deterministic, source-located,
   and actionable?
9. **Scope:** Did the work avoid active-mask, result-target, body-rewrite, and
   Rust-API decisions?

Any blocking/high failure reopens the owning slice. A medium finding may be
deferred only with a concrete reason and removal condition; do not leave a
speculative TODO in production code.

## Definition of done

The overload specification feature is complete when all of the following hold:

- decision gate A is recorded and the source registry contains exactly the four
  settled pairs with their compatibility facts;
- every current shift/store participant has the exact settled annotation and no
  other primitive is opportunistically annotated;
- malformed blocks, unregistered pairs, inconsistent shapes, missing members,
  and primary-marker errors have tested source-located diagnostics;
- primary status is resolved once per source family and wildcard expansion does
  not create false duplicates;
- completion, hover, definitions/references, symbols/tokens, and diagnostics use
  the typed registry/catalog owner;
- the VS Code integration test proves the editor-visible workflow while the
  client contains no overload semantics;
- owner-equivalence and additive next-axis probes pass;
- focused, full Python, mypy, corpus, editor unit/integration, and diff checks
  pass, or an unavailable GUI test environment is explicitly reported;
- selection/lowering/backends/generated artifacts have no changes;
- the mandatory post-implementation design review has no unresolved blocking or
  high-severity finding.

A future Rust API plan may begin from this validated catalog fact. It must be a
separate feature with its own public-spelling decisions and verification.
