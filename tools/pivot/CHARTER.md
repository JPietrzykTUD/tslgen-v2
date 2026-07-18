# PIVOT Downstream-Tool Charter

This charter refines the repository [CHARTER.md](../../CHARTER.md) for the
independently packaged PIVOT exporter. It does not relax the compiler contract
in [`tslc/CHARTER.md`](../../tslc/CHARTER.md).

## 1. PIVOT Is Downstream Of The Compiler

PIVOT is a separately packaged consumer of `tslc`, not a compiler stage,
backend, installed `tslc` subcommand, or compiler-owned semantic projection.
Dependencies point from PIVOT to `tslc`; neither `tslc` nor `tsldata` imports,
registers, or changes behavior for PIVOT.

## 2. The Output Is Completely Flattened Straight-Line Dataflow

PIVOT emits deterministic language mappings from TSL primitives and abstract
vector operations to concrete C++ or Rust instruction lists. Every `direct`
list is completely flattened. Runtime branches, loops, and other control flow
that cannot become a plain sequential instruction list are unsupported.

## 3. Compiler Facts Stay Compiler-Owned

Source validation, catalogs, machine profiles, implementation selection, call
dependency identity, target capabilities, intrinsic and type spellings, and
ordinary TSIL scan/lowering semantics remain owned by `tslc`. PIVOT reuses
those facts and does not maintain competing selection, capability, source, or
backend policies.

## 4. PIVOT Owns Its Interpretation

PIVOT owns profile-cover policy used only for export, admissibility, residual
target-text interpretation, binding identity, local allocation, recursive
flattening, cycle reporting, YAML schema and paths, diagnostics, skips, and
coverage evidence.

PIVOT may parse and transform lowered C++ and Rust text inside its package. Its
interpretation is a PIVOT fact, not a compiler guarantee. Parsing is bounded,
typed where semantics matter, and fail-closed: unsupported or ambiguous text
produces a structured skip rather than guessed output or context-blind repair.

## 5. Isolation Is A Hard Requirement

PIVOT may instantiate and configure compiler objects but never monkey-patches
compiler classes, mutates registries or defaults, or feeds its interpretation
back into compiler semantics. The initial package may import compiler internals
as an explicit lockstep dependency on this repository revision; it owns the
resulting compatibility burden.

A PIVOT need alone does not justify edits to `tsldata`, normal TSIL semantics,
compiler lowering, backend generation, generated tests, or benchmarks. A useful
projection-neutral compiler change requires a separately justified slice.

## 6. Coverage And Reproducibility Are Product Requirements

Every entry in the canonical full-corpus PIVOT baseline remains emitted.
Coverage may increase, but an entry or a pre-existing nominal-identity
multiplicity may not disappear merely because an aggregate count stays
unchanged. Definition identities, relevant content hashes, collision groups,
skips, diagnostics, artifact paths, and YAML content are deterministic. Silent
corruption is never an acceptable way to preserve coverage.

## 7. PIVOT Owns Its Evidence

The tool owns package-isolation, parser, inliner, schema, golden or differential,
determinism, compatibility, and full-export ratchet tests. Core compiler tests
prove compiler behavior; they are not substitutes for PIVOT consumer evidence.
