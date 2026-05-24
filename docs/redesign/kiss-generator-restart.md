# KISS Generator Restart Charter

Milestone 105 freezes the accepted M57-M104 lowering/request/result/worklist
chain as evidence, not as the default architecture for future product work.
The restart goal is deliberately direct:

```text
.tsl source data -> validated catalog -> selected implementations -> C++ and Rust library artifacts
```

The new generator should become useful by proving that path on tiny fixtures
before adding broad lowering machinery.

## Standing Rules

- Treat `docs/redesign/` as the product contract.
- Treat `frozen/` and `tslgenold/` as evidence only.
- Treat `tsldata/` as source corpus and fixture evidence, not generated output.
- Do not add clean restart product code outside an accepted product milestone;
  the old top-level `tslgen/` tree is quarantined under `tslgenold/`.
- Prefer small objects with obvious ownership over chains of milestone-shaped
  request/result wrappers.
- Add a new IR category, request/result family, inventory, worklist,
  provenance wrapper, registry, dispatcher, hidden backfeed, fixpoint
  mechanism, or pipeline stage only when at least two concrete accepted stages
  need the same concept.
- Keep file I/O in source loading, manifest loading, configuration adapters,
  and artifact writing. Parsing, catalog validation, selection, lowering,
  backend translation, and rendering stay pure where practical.
- Generated text must come from accepted typed values and backend emitters, not
  renderer-side semantic inference or raw source rewriting.

## Small Concept Set

`TslProject` owns the configured source set, diagnostics, target requests, and
artifact destination policy. It coordinates the run, but it should not hide
parser, catalog, backend, or writer behavior.

The source loader owns deterministic path resolution and returns source
documents with path, text, digest, kind, and source locations. It is the normal
filesystem-read boundary.

The parser owns syntax recognition and returns parse results with diagnostics
and spans. Parser-private dictionaries or syntax nodes do not become domain
objects.

The `Catalog` owns validated domain data: primitives, implementations,
types, lane sets, extensions, templates, backend metadata, tests, and rule
metadata needed by accepted slices. Downstream stages consume typed objects.

`Primitive` and `Implementation` represent source-authored behavior and
available implementation bodies. They preserve source locations for
diagnostics without requiring downstream stages to inspect raw parser data.

`Target` records explicit backend, extension, type, attribute, and feature
requirements. Host hardware detection, if used, is an adapter that produces
target data rather than a hidden selection dependency.

`Generator` coordinates catalog validation, selection, backend emission, and
artifact assembly for one run. It should be boring: orchestration over typed
objects, not a semantic dispatcher.

`Backend` is a narrow protocol for backend-specific capability checks and
artifact emission. The initial concrete emitters are C++ and Rust.

The C++ emitter and Rust emitter consume selected typed implementation data
and backend translation facts for the accepted slice. They return artifact
values and diagnostics; they do not read files or repair source bodies.

The diagnostic reporter accumulates structured diagnostics with code, severity,
message, source location, and notes. Pure logic reports diagnostics rather than
exiting the process.

The artifact set is an immutable collection of logical paths, content, digests,
and metadata. The artifact writer is the explicit filesystem-write boundary.

## First Restart Slices

Milestone 106 was structural, not product implementation: it moved the
pre-restart top-level `tslgen/` tree to `tslgenold/` as old-state evidence and
reserved a fresh top-level `tslgen/` path for the clean implementation. It did
not add parser, catalog, generator, backend, renderer, CLI, fixture, or
generated output code.

The first product slice after that layout reset should prove an end-to-end
path on a tiny `.tsl` fixture:

1. Load one explicit source document.
2. Parse the supported source form.
3. Build and validate a minimal catalog with one primitive and one
   implementation.
4. Select one implementation for explicit C++ and Rust targets.
5. Emit one deterministic C++ library artifact and one deterministic Rust
   library artifact through typed backend emitters.
6. Return an artifact set and write it only through the artifact writer.
7. Run the same pipeline twice and prove diagnostics and artifacts are stable.

That slice may leave broad TSIL semantics, dependency closure, backend maps,
hardware autodetection, CLI compatibility, generated tests, and corpus-wide
coverage out of scope.

## Evidence Policy

Accepted M57-M104 tests and modules remain valuable because they name exact
diagnostic boundaries, source-body integrity rules, deterministic ordering
risks, and places where renderer inference became tempting. They do not require
the restart to reuse the same class hierarchy, public imports, stage names, or
request/result/worklist chain.

Future restart milestones should cite old evidence only when it clarifies a
required behavior or negative boundary. They should not create a migration map
from old modules to new modules, import `frozen/` or `tslgenold/` at runtime,
or preserve old abstractions for convenience.

## Review Pressure Checks

Reviewers should ask:

- Does this slice move the source-to-artifact path forward?
- Could a contributor find the owner for a primitive, extension, backend rule,
  diagnostic, or artifact without reading the old implementation?
- Is every new object justified by current ownership or by reuse across at
  least two accepted stages?
- Are diagnostics explicit for malformed or unsupported input?
- Are artifact ordering, diagnostic ordering, and path handling deterministic?
- Did the change keep old evidence quarantined from clean runtime imports?
