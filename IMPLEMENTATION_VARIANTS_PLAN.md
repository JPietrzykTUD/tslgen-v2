# Implementation Variants Plan

## Goal

Add a typed source-data feature for alternative implementation bodies of the
same selected primitive specialization.

An implementation variant is an authored, semantically equivalent body for one
already-selected implementation leaf. Variants let TSL authors keep multiple
ways to express the same primitive behavior, compile them, inspect generated
code, and later benchmark or select between them without turning `tslc` into a
hardware-tuning framework.

## Settled Design

### Ownership

Variants live inside the implementation leaf that already owns `requires`,
`safety`, and `implementation`.

```tsl
requires [avx2]
safety:
  internal_unsafe true
  caller_unsafe false
  reasons [intrinsic]
implementation:
  tsil "..."
variants:
  scalar_loop:
    tsil "..."
  intrinsic_composition:
    tsil "..."
```

The leaf owns availability and safety. Variants are body alternatives for that
same leaf.

### Contract

`impls` answers:

```text
Can this primitive specialization be emitted for this extension/type/profile?
```

`variants` answers:

```text
Which equivalent body shapes exist for that already-emittable specialization?
```

Therefore a variant must not change:

- primitive name;
- signature;
- parameter or result kinds;
- type or extension axes;
- requirements;
- public caller-safety;
- semantic contract.

If a body needs a different requirements set, it is not a variant. It belongs in
a separate existing `impls` branch.

Internal safety may differ. For example, a scalar-loop default body may only
need `raw_pointer`, while an intrinsic-composition variant may additionally
need `intrinsic`. That is allowed because it is an implementation detail, not a
public API contract.

### Requirements

Variants inherit the exact requirements set from their implementation leaf.

Variants must not add, weaken, or override requirements. If variant lowering or
dependency propagation discovers that a variant body needs requirements beyond
the leaf contract, that is a diagnostic. The author should move that body to a
separate implementation branch with the proper `requires` data.

### Safety

Caller safety remains on the implementation leaf.

Variants may contribute internal safety facts. The effective emitted
specialization safety is the conservative union of:

- the default implementation body's internal safety and reasons;
- every variant body's internal safety and reasons;
- the leaf's fixed public caller-safety.

Variants must not change public caller-safety. A variant cannot make a safe
public Rust wrapper unsafe to call, or make an unsafe public wrapper safe.

Proposed first-slice shape:

```tsl
safety:
  internal_unsafe true
  caller_unsafe true
  reasons [raw_pointer]
implementation:
  tsil "..."
variants:
  intrinsic_composition:
    safety:
      internal_unsafe true
      reasons [intrinsic]
    tsil "..."
```

The leaf caller contract is still `caller_unsafe true`. The effective internal
reason set becomes `[intrinsic, raw_pointer]`.

Variant `safety` blocks should be optional. If omitted, the variant contributes
no extra internal safety facts beyond what can be propagated from its body. If
present, the first slice should accept only:

- `internal_unsafe`;
- `reasons`.

Reject `caller_unsafe` under variants.

### Variant IDs

Variant names are authored stable identifiers, not a closed enum.

Good examples:

```tsl
variants:
  scalar_loop:
    tsil "..."
  intrinsic_composition:
    tsil "..."
  table_lookup:
    tsil "..."
```

The compiler should validate identifier-like names so they are safe for:

- generated function names;
- diagnostics;
- CLI/debug selection;
- documentation;
- future benchmark tooling.

The names are free-form in meaning, but not arbitrary prose. A later slice may
add optional `description` text if human prose is useful.

### Emission

All valid variants are emitted by default.

Reasons:

- authored variants should not silently rot;
- generated code can be inspected without a special mode;
- future benchmark and assembler-inspection tools have concrete symbols to use;
- compilation proves each variant remains viable for the same leaf contract.

The public wrapper still calls exactly one selected body. In the first slice,
that body is the default `implementation`.

Example generated shape:

```cpp
namespace tsl::detail::primitives {

template <class Vec>
struct gather_narrow_partial_impl {
  static auto apply(...) { ... default body ... }
};

template <class Vec>
struct gather_narrow_partial_impl_intrinsic_composition {
  static auto apply(...) { ... variant body ... }
};

} // namespace tsl::detail::primitives
```

The public wrapper initially remains simple:

```cpp
return detail::primitives::gather_narrow_partial_impl<Vec>::apply(...);
```

Rust should mirror the same concept in the Rust detail namespace/module shape.

## Non-Goals For The First Slice

- No benchmarking framework.
- No automatic variant selection.
- No assembler inspection integration.
- No profile-specific variant choice.
- No per-variant requirements.
- No per-variant public caller-safety.
- No new plugin registry or strategy DSL.
- No global rewrite of implementation selection.

## Future Selection Direction

After variants exist and compile, add a second slice for compile-time selection.
The source model should already make this possible without changing `tsldata`
again.

Possible C++ direction:

```cpp
#if defined(TSL_USE_VARIANT_gather_narrow_partial_intrinsic_composition)
  return detail::primitives::gather_narrow_partial_impl_intrinsic_composition<Vec>::apply(...);
#else
  return detail::primitives::gather_narrow_partial_impl<Vec>::apply(...);
#endif
```

Possible Rust direction:

- feature-gated variant selection;
- cfg-based detail dispatch;
- or generated const configuration if that fits the existing Rust API.

The important boundary: selection should consume typed variant metadata. It
should not rediscover semantics by parsing function names or body text.

## Data Model

Add a typed catalog value, probably near the existing implementation body model:

```python
@dataclass(frozen=True, slots=True)
class ImplementationVariant:
    name: str
    body: ImplementationBody
```

Then implementation leaves can carry:

```python
implementation: ImplementationBody
variants: tuple[ImplementationVariant, ...] = ()
```

Use immutable tuples and deterministic ordering. Preserve source locations for
diagnostics where the parsed model currently supports them.

## Parser, Builder, And Validation

Parser/schema work:

- accept `variants:` only at implementation leaves;
- accept variant IDs as stable identifier-like keys;
- accept the same body shape as `implementation` for each variant;
- accept optional variant `safety` blocks with only `internal_unsafe` and
  `reasons`;
- reject unknown fields under a variant in the first slice;
- reject duplicate variant IDs deterministically;
- reject `requires` under a variant;
- reject `caller_unsafe` under a variant;
- reject a variant without a body.

Builder work:

- promote parsed variant blocks into typed `ImplementationVariant` values;
- keep dictionaries confined to parser/builder boundaries;
- keep ordering stable by source order or deterministic sorted order, whichever
  matches nearby catalog behavior.

Validation diagnostics should be source-located where practical.

## Selection And Dependency Closure

Selection should not treat variants as separate implementation candidates.

The selected implementation leaf remains the same leaf selected today. Variants
are attached to the selected lowered specialization after that leaf has been
chosen.

Dependency and requirement propagation must account for every emitted body:

- default `implementation`;
- each variant body.

If a variant calls a primitive that is unavailable under the leaf requirements,
that should be diagnosed as a variant contract violation. It should not be
silently dropped, because variants are emitted by default.

Safety propagation must also account for every emitted body. Variant internal
safety and propagated internal safety reasons contribute to the effective
specialization safety. Propagated caller-safety must still match the leaf's
public caller-safety contract.

## Lowering

Lowering should produce typed lowered variant bodies rather than backend
renderers scanning catalog data.

Possible lowered shape:

```python
@dataclass(frozen=True, slots=True)
class LoweredImplementationVariant:
    name: str
    body: RenderText
```

`LoweredSpecialization` can then carry:

```python
variant_bodies: tuple[LoweredImplementationVariant, ...] = ()
```

The default body remains the existing body field.

Lowering diagnostics should include the variant ID when a variant body fails:

```text
primitive gather_narrow_partial variant intrinsic_composition: ...
```

## Rendering

Renderers consume lowered variant bodies only.

They may:

- spell generated variant function names;
- place variant functions in detail namespaces/modules;
- format backend syntax;
- keep public wrappers calling the default body in the first slice.

They must not:

- inspect the catalog for variant semantics;
- decide whether a variant is valid;
- infer requirements or safety from body text;
- parse TSIL.

Generated names should be deterministic and derived from the default
implementation symbol plus the variant ID.

## Value Tests

First slice:

- existing public value tests continue to exercise the public wrapper and
  default implementation;
- variant bodies are compile-checked because they are emitted;
- no generated value-test matrix explosion.

Later slice:

- add an opt-in variant value-test mode that calls each variant detail symbol
  directly;
- compare variant results against the public/default path;
- expose variant coverage in value-test planning output.

## Documentation

First slice:

- generated API docs may mention available variant IDs if this can be done
  without broad documentation refactoring;
- otherwise leave docs unchanged except for compiler/source-shape
  documentation.

Later slice:

- add optional variant descriptions;
- include emitted variant symbol names and strategy notes in specialization
  docs;
- link variant entries to benchmark or assembly reports if those tools exist.

## Suggested Implementation Slices

### Slice 1: Source Model And Validation

- Extend parser/schema acceptance for `variants:`.
- Add typed `ImplementationVariant`.
- Add typed optional variant internal safety facts.
- Promote variants in the catalog builder.
- Validate malformed variant blocks.
- Add focused parser/catalog/validation tests.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
python -m compileall -q tslc/src/tslc
git diff --check
```

### Slice 2: Lowering And Rendering

- Attach variants to selected/lowered specializations.
- Lower default and variant bodies through the same TSIL path.
- Render C++ and Rust detail variant symbols.
- Keep wrappers calling the default implementation.
- Add renderer/lowering tests proving variants are emitted and wrapper dispatch
  remains unchanged.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
./dev.sh build --primitives gather_narrow_partial --profiles scalar,avx2 --backends cpp,rust
```

### Slice 3: Dependency And Requirement Contract

- Ensure dependency closure sees variant calls.
- Diagnose variants that require dependencies unavailable for the leaf.
- Union default and variant internal safety/reasons.
- Reject or diagnose propagated variant caller-safety that conflicts with the
  leaf caller-safety contract.
- Add regression tests with a tiny fake primitive fixture.

Validation:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_build_verify_config.py
```

### Slice 4: Corpus Trial

- Add one real variant to `gather_narrow_partial`.
- Use the existing scalar-loop-like body as the default.
- Add an intrinsic-composition variant under the same requirements where that is
  expressible. The variant may add internal `intrinsic` safety reason, but it
  must keep the same caller-safety contract.
- Build C++ and Rust for representative profiles.

Validation:

```bash
./dev.sh build --primitives gather_narrow_partial --profiles scalar,avx2 --backends cpp,rust
./dev.sh test --primitives gather_narrow_partial --profiles scalar --backends cpp,rust
```

## Design Checks

This feature stays aligned with the project design if:

- `tslc` remains primitive- and extension-agnostic;
- variants are typed catalog/lowered data, not renderer-side string guesses;
- requirements remain owned by implementation leaves;
- safety remains owned by implementation leaves;
- emitted variant ordering is deterministic;
- malformed variants produce diagnostics;
- adding the next variant mostly edits `tsldata`, not compiler classifiers;
- renderers format already-lowered variant bodies.

If implementation starts requiring scattered primitive-name branches, renderer
catalog inspection, or per-variant requirement selection, stop and redesign the
boundary before continuing.
