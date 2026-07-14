# tslc Compiler Charter

This is the compiler-specific refinement of the repository
[`CHARTER.md`](../CHARTER.md). `tslc` is a compact compiler, not a framework for
compiler-shaped ceremony: it should grow by adding clear domain vocabulary and
behavior while keeping plumbing and handoff objects rare.

## 1. It is a compiler

`tslc` is a compiler: DSL → typed model → lowering → codegen → verify. A rich
**vocabulary** of domain/IR types is expected and welcome — a `Primitive`, an
`Extension`, a TSIL `Region` kind per keyword. Growth happens by adding
vocabulary that represents something real.

## 2. Plumbing is budgeted; vocabulary is not

What stays minimal is **plumbing**: never a `Discovery → DiscoveryResult →
Handoff → HandoffResult` quartet for one concept. There is one body model
(`Segment`) and one lowered specialization model (`LoweredSpecialization`).
Boundary results carry their substantive stage outputs and diagnostics directly.
If you are about to add a wrapper whose only job is to carry another type
between two functions, don't.

## 3. New types are gated on delivered behavior

A type earns its place when it lets a primitive **compile** that couldn't
before — not when a second call site references it. Progress is tracked by a
coverage table (primitive × extension × backend → compiles?), not by the number
of internal abstractions.

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

## 5. Hard rules

- Typed, immutable domain objects after the parser boundary. No dicts as domain
  objects.
- Diagnostics are structured values. Pure logic never calls `SystemExit`.
- File I/O lives in source/config/static-asset loading, artifact writing,
  verification, or explicit maintenance tools. Parsing, catalog building,
  selection, lowering, and rendering consume loaded inputs and are pure.
- Deterministic ordering everywhere (sorted artifacts, stable iteration).
- Selection closure, emitted-name finalization, backend validation, and test
  planning finish before project rendering begins.
- Templates format already-decided values. No backend semantics in templates.

## 6. Scratch and output go in repository `./tslctmp`, never `/tmp`

This runs in a WSL devcontainer: `/` (and `/tmp`) is the container overlay,
backed by a VHDX that only ever grows. Generated trees, build dirs, and test
scratch go under `./tslctmp` (the workspace 9p host mount), which is
host-managed and cleanable. Likewise, durable project knowledge lives in
source-controlled docs, tests, and code comments, not in local tool caches.

## 7. Current sources of truth

`tsldata/`, `supplementary/`, tests, and the `tslc` package docs are the project
requirements and evidence. Active compiler behavior should be justified by
these sources and by passing generated artifacts, not by undocumented
assumptions or speculative architecture.
