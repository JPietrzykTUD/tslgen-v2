# TSLc ARM SVE Scalable Signature Design Prompt

## Context

Continue the active ARM per-primitive coverage goal from the residual SVE
signature audit.

Current SVE C++ coverage baseline:

```text
4479 emitted / 4509 attempted
```

There are no remaining full SVE C++ dependency-prune buckets. The only skipped
slots are selected specializations with fixed-lane array or lane-list
signatures:

- `from_array`: `v:=s[]`
- `to_array`: `s[]:=v`
- `set`: `v:=(lanes<s>)`

The previous audit confirmed these are rejected before body lowering by
`SupportPolicy.unsupported_signature_kinds_for_extension(...)`. C++ `s[]`
currently maps to `array_for<Vec>`, which derives its length from
`sizeof(Vec::register_type)`. SVE register types are sizeless, and `lanes<s>`
is a finite authored list while SVE has a runtime lane count.

ADR-114 records the boundary.

## Goal

Design the smallest typed treatment for scalable fixed-lane signatures before
any implementation work.

The outcome should be one of:

1. Keep `s[]` and `lanes<s>` fixed-lane-only, and add explicit typed coverage
   modeling so SVE skips are intentional rather than reported as missing
   support.
2. Introduce a separate scalable runtime-buffer/span contract for array-like
   vector materialization, with clear source syntax, type spelling, lowering,
   value-test, and renderer boundaries.
3. Introduce a different scalable constructor primitive for the role currently
   served by `set(v:=(lanes<s>))`, leaving finite `lanes<s>` fixed-lane-only.
4. Return to planner if the right design is broader than one maintainable slice.

## Scope

Allowed:

- Inspect `tslc/src/tslc/support_policy.py`, `tslc/src/tslc/backend/cpp.py`,
  `tslc/src/tslc/backend/assets/tsl_core.hpp`, and the residual source
  primitives.
- Inspect value-test patterns/renderers only to understand current fixed vs
  scalable assumptions.
- Update redesign docs with a concrete design and implementation plan.
- Implement only if the design is narrow, typed, and source-owned enough to fit
  one slice.

Out of scope:

- Rust SVE support.
- General scalable-vector DSL machinery.
- Primitive-name or extension-name classifier branches in production code.
- Treating `array_for<simd<T, sve>>` as valid.
- Hiding residual skips without a typed status or source contract.

## Required Evidence

Run or cite the focused residual coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives from_array,to_array,set \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-residual-signatures-coverage
```

Expected current result:

```text
588 emitted / 618 attempted
from_array 20/30 emitted, 10 skipped
to_array   20/30 emitted, 10 skipped
set        20/30 emitted, 10 skipped
```

## Design Questions

- Is `s[]` semantically an owned fixed-lane array, or a general vector
  materialization role that should gain a scalable runtime-buffer variant?
- Should scalable array conversion be represented by existing pointer
  primitives (`load`/`store`) rather than by `from_array`/`to_array`?
- Is `set(v:=(lanes<s>))` meaningful for scalable vectors at all, given that
  the source argument list is finite but the runtime lane count is not?
- What should coverage call an intentionally unsupported scalable signature:
  source-declared unsupported, policy-deferred, backend-unsupported, or another
  typed status?
- Which diagnostics should distinguish malformed source from deliberate
  unsupported scalable shape?

## Validation

For a design-only slice:

```bash
git diff --check
```

For an implementation slice, add focused tests for the new typed boundary and
run at minimum:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-full-coverage
git diff --check
```

The fast non-build gate currently has one known baseline failure:

```text
test_primitive_corpus_safety_covers_direct_unsafe_facts
```

Do not treat that as introduced unless the failure set changes.

## Completion

Update `docs/agent/current-redesign-state.md` and the active handoff with the
chosen design or planner verdict. Commit a verified milestone only if a concrete
design or implementation artifact is produced.
