# tslc charter

This is a one-page contract for how `tslc` is built. It exists because the
predecessor (`tslgen`) drowned in its own scaffolding: ~500 classes, 155 of them
`*Handoff/*Fragment/*Payload/*Inventory` plumbing wrappers, produced by a process
that rewarded adding a typed micro-slice every commit. `tslc` keeps the parts
that were genuinely good and changes the incentives that produced the rest.

## 1. It is a compiler

`tslc` is a compiler: DSL → typed model → lowering → codegen → verify. A rich
**vocabulary** of domain/IR types is expected and welcome — a `Primitive`, an
`Extension`, a TSIL `Region` kind per keyword. Growth happens by adding
vocabulary that represents something real.

## 2. Plumbing is budgeted; vocabulary is not

What stays minimal is **plumbing**: never a `Discovery → DiscoveryResult →
Handoff → HandoffResult` quartet for one concept. There is one body model
(`Segment`), one lowered form (`LoweredFunction`). Result objects carry only
`(value, diagnostics)`. If you are about to add a wrapper whose only job is to
carry another type between two functions, don't.

## 3. New types are gated on delivered behavior, not on "two stages need it"

A type earns its place when it lets a primitive **compile** that couldn't
before — not when a second call site references it. Progress is tracked by a
coverage table (primitive × extension × backend → compiles?), never by a
milestone number.

## 4. The body model is a segment sequence, not an AST

A TSIL body is an ordered `tuple[Segment, ...]` where each segment is either
`RawText` (semi-valid target code, passed through verbatim) or a `Region` (a
recognized TSIL keyword island whose inner spans are themselves a recursive
segment sequence). We do **not** parse C++/Rust expressions. We translate only
keyword islands.

This deliberately makes the current prototype a C-like-source backend family:
raw fragments must already be acceptable to each selected backend, and adding a
backend with substantially different expression syntax is not just a backend
module addition. Common operators, memory idioms, and control forms should be
promoted to typed TSIL regions before such a backend relies on them.

## 5. Hard rules carried over (these were right)

- Typed, immutable domain objects after the parser boundary. No dicts as domain
  objects.
- Diagnostics are structured values. Pure logic never calls `SystemExit`.
- File I/O lives only in source loading and artifact writing. Parsing, catalog
  building, selection, lowering, and rendering are pure.
- Deterministic ordering everywhere (sorted artifacts, stable iteration).
- Templates format already-decided values. No backend semantics in templates.

## 6. Scratch and output go in `./tslctmp`, never `/tmp`

This runs in a WSL devcontainer: `/` (and `/tmp`) is the container overlay,
backed by a VHDX that only ever grows. Generated trees, build dirs, and test
scratch go under `./tslctmp` (the workspace 9p host mount), which is
host-managed and cleanable. Likewise, durable project knowledge lives in the
repo (this file, `README.md`, code comments) — the agent memory under
`/root/.claude` is on the ephemeral overlay and is treated as a cache that
points back here, not as a source of truth.

## 7. Evidence, not architecture

`docs/redesign/` and `tsldata/` are requirements and evidence. `tslgen/`,
`tslgenold/`, and `frozen/` are read-only evidence. `tslc` never imports them at
runtime.
