# tslc — what it is and how it works

A deep-orientation companion to [README.md](README.md) (quick start) and
[CHARTER.md](CHARTER.md) (the design rules). This file explains the *shape* of
the system: what it compiles, the pipeline, the two nested input languages, and
the design decisions that matter.

## What it is

`tslc` is a **compiler that generates a SIMD wrapper library**. It reads a
declarative data language (`.tsl` files under `tsldata/`) describing abstract
SIMD *primitives* (`add`, `sub`, `load`, `gather`, `blend`, …) and emits
deterministic, compilable **C++ and Rust** source implementing each primitive
across a matrix of:

- **hardware extensions** — `scalar`, `sse`, `avx2`, `avx512`, `neon`, `sve`, a
  portable `generic`, … (with inheritance/fallback chains);
- **scalar types** — `si8…si64`, `ui8…ui64`, `f32`, `f64`;
- **machine profiles** — skylake, icelake, etc. (a named CPU-feature set).

The architecture keeps a rich **vocabulary** of domain/IR types while
**budgeting plumbing tightly**: one body model (`Segment`), one lowered form
(`LoweredSpecialization`), and result objects that carry only `(value,
diagnostics)`. Progress is tracked by a coverage table
(*primitive × extension × backend → compiles?*) and by generated artifacts that
build, not by the number of internal abstractions.

## The pipeline

The compiler is a pure function once source data and static compiler assets are
loaded, orchestrated in [pipeline.py](src/tslc/pipeline.py):

```
sources + compiler assets → parse → catalog → select → scan body → lower → emit → render → write → verify
```

| Stage | Module | Role |
|---|---|---|
| **compiler assets** | [compiler_assets.py](src/tslc/compiler_assets.py) | Load the bundled grammar and render assets |
| **sources** | [sources.py](src/tslc/sources.py) | Read `.tsl` source files |
| **syntax** | [syntax/](src/tslc/syntax/) | Lark grammar → parse tree (outer declarations + TSIL body envelopes) |
| **catalog** | [catalog/](src/tslc/catalog/) | Promote parse tree → typed, immutable domain model (`Primitive`, `Extension`, `Catalog`) |
| **select** | [select/](src/tslc/select/) | For each `(backend, extension, type)` slot, pick the best implementation body |
| **ir / scan** | [ir/](src/tslc/ir/) | Turn a TSIL body into a recursive `tuple[Segment, ...]` — *not* an AST |
| **lower** | [lower/](src/tslc/lower/) | Walk segments, resolve queries/intrinsics → `LoweredSpecialization` |
| **backend** | [backend/](src/tslc/backend/) | Emit C++/Rust function text from lowered specs |
| **render** | [render/](src/tslc/render/) | Assemble a per-profile project (headers/modules, dispatch, CMake/Cargo) |
| **output** | [output/](src/tslc/output/) | Write the file tree; build-verify with real toolchains (incl. SDE/QEMU emulation) |

Entry points: [cli.py](src/tslc/cli.py) (`python -m tslc.cli`) and
[api.py](src/tslc/api.py).

## The input language (two nested languages)

### 1. The outer TSL data language

An indentation-sensitive, YAML-ish DSL. A primitive declares a signature, docs,
authored test cases, and a tree of implementations keyed by
`extension → type-group`. Abbreviated from
[`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl):

```
prim<v:=(v,v)> add(left, right):
  tests:
    - {tags [basic], type "si32", case {inputs [[1,2,...],[8,7,...]], expected [9,9,...]}}
  impls:
    avx2:
      ?i?:                         # type-group wildcard: any integer width
        requires [avx, avx2]
        implementation:
          tsil "complete(intrin<add, build[suffix=base::signed_of(base::in)]>(left, right));"
```

- **Signatures** (`v:=(v,v)`): `v` vector, `m` mask, `s` scalar, `ptr`/`usize`
  (presence makes it a free function), `lanes<s>` a lane list.
- **Type-group keys**: `?i?` (any int), `f?` (any float), `arith` (all), plus
  concrete tags. Ranked by **specificity** — `si32` beats `?i?` beats `arith`.
- **Extension fallback**: extensions form `inherits` chains (e.g. `avx512_vl →
  avx512`); a *derived* extension supersedes its base only when the profile's
  CPU flags activate it.
- **Mask policies**: `[mask=zero]` (zeroing) and `[mask=pass_through]` (merge).
- `requires`, `safety` (internal/caller unsafe), and boolean attribute wildcards
  (e.g. `[aligned=*]`, expanded at catalog-build time).

### 2. The inner TSIL body language — the key design decision

A function body is **semi-valid target-language code sprinkled with TSIL keyword
islands**. Per the charter: *we do not parse C++/Rust expressions; we translate
only keyword islands.* [ir/scan.py](src/tslc/ir/scan.py) scans a body into a
recursive `tuple[Segment, ...]`:

- **`RawText`** — target source, passed through verbatim;
- **`Region`** — a recognized keyword island whose `<...>` selector is kept raw
  and whose `(...)` payload is recursively scanned.

The keyword set ([scan.py](src/tslc/ir/scan.py), `KEYWORDS`) is the *entire*
extension surface — `complete`, `intrin`, `op`, `call`, `value`, `type`, `cast`,
`var`, `let`, `mask`, `mem`, `lanes`, `io`, `if`, `loop`, `switch`,
`assume_aligned`. **Growth happens by adding a keyword here (and a handler),
never by adding wrapper families.**

So `intrin<add, build[suffix=base::signed_of(base::in)]>(left, right)` becomes
`_mm256_add_epi32(...)` for AVX2/si32, and
`call<primitive=mov, attrs[mask=zero]>(...)` resolves to another generated
primitive. Generation-time queries (`base::in`, `vector::length`,
`is_same(...)`) and control (`if<generation>`, `loop<generation>`,
`switch<compile>`) are evaluated *at compile time* against the concrete
type/extension being specialized.

## Lowering & assembly

The [Lowerer](src/tslc/lower/lowerer.py) walks the segments for one
`(primitive, extension, type, backend)` slot → a `LoweredSpecialization`
(concrete type spellings, register type, body text, mask policy, safety,
required CPU features). Region handlers
([lower/region_handlers/](src/tslc/lower/region_handlers/)) translate each
keyword; a query evaluator ([lower/queries.py](src/tslc/lower/queries.py))
resolves the `<...>` selectors.

The pipeline then runs a **profile-scoped dependency closure**: from the
requested primitives it follows `call<...>` edges
([lower/dependencies.py](src/tslc/lower/dependencies.py)), lowers callees, and
**prunes to a fixpoint** any specialization whose callees aren't themselves
emitted for the same `simd<type,ext>` (else the generated call wouldn't link).
It also **propagates bottom-up** unsafe-ness and required CPU feature flags
through the live call graph
([pipeline.py](src/tslc/pipeline.py), `_propagate_transitive_call_facts`).

Backends differ idiomatically (a `BackendDialect`,
[backend/translation.py](src/tslc/backend/translation.py), abstracts type
spellings, intrinsic composition, and call syntax):

- **C++** — `*_impl<Vec>` struct partial-specializations + wrapper function
  templates ([backend/cpp.py](src/tslc/backend/cpp.py)).
- **Rust** — traits + impls + turbofish wrappers, explicit `unsafe {}` framing,
  `core::arch` intrinsic qualification ([backend/rust.py](src/tslc/backend/rust.py)).

A static substrate ships as assets
([backend/assets/tsl_core.hpp](src/tslc/backend/assets/tsl_core.hpp),
[tsl_core.rs](src/tslc/backend/assets/tsl_core.rs)) defining `simd<T,Ext>` /
`SimdVector` and helpers; [render/](src/tslc/render/) fills `.tmpl` templates
into a per-profile project with a top-level dispatch header/module.

## Differential value tests

Authored `tests:` blocks (input lanes → expected lanes) drive the
[value_tests/](src/tslc/value_tests/) subsystem, which generates **executable**
C++/Rust tests: build a SIMD register from a lane array, run the generated
primitive, read the result back, compare to `expected`. The array↔register
round-trip uses auto-discovered "harness primitives" (`from_array`, `to_array`,
`to_integral`, found by signature shape in
[value_tests/harness.py](src/tslc/value_tests/harness.py)). A **differential**
mode cross-checks each hardware implementation against the portable `generic`
one. [output/verify.py](src/tslc/output/verify.py) then actually compiles and
runs them — optionally under **Intel SDE** or **qemu-aarch64** so
AVX-512/NEON/SVE code runs on hardware that lacks it.

## State / outcome

- **Coverage-not-completeness**: in `partial` mode a primitive whose body can't
  be lowered yet is *recorded as a skip*, not a failure; `strict` mode promotes
  skips to errors. [coverage.py](src/tslc/coverage.py) and
  [maintenance/](src/tslc/maintenance/) (e.g. `coverage_inventory`)
  operationalize the charter's coverage-not-completeness rule.
- **Honest edges**: [support_policy.py](src/tslc/support_policy.py) centralizes
  what the compiler can emit today; some keyword forms are *recognized so a
  body skips cleanly* rather than leaking through as raw text.
- **Tests**: the pure-logic suite is green. The build-verify tests
  (`test_build_verify.py`, full-corpus `test_value_tests.py`) compile/run real
  C++/Rust and make the full run exceed ~5 min. Run the suite from the **repo
  root**, not from `tslc/` — `tests/test_value_test_planning.py` reads source via
  repo-root-relative paths and otherwise reports false failures.

## Where to look first

- Big picture / rules: [README.md](README.md), [CHARTER.md](CHARTER.md).
- The body model: [ir/segments.py](src/tslc/ir/segments.py),
  [ir/scan.py](src/tslc/ir/scan.py).
- Orchestration: [pipeline.py](src/tslc/pipeline.py).
- A real primitive with all the moving parts:
  [`tsldata/primitives/arithmetic/fundamental.tsl`](../tsldata/primitives/arithmetic/fundamental.tsl).
