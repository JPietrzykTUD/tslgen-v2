# TSLc Lane-List `set` Generation-Loop Migration

## Accepted State

The first lane-list slice is implemented in `tslc/`:

- `SignatureShape` carries structured `SignatureTerm` values.
- `lanes<s>` is accepted as a parameter-position signature term.
- malformed lane-list signature terms and result-position lane lists are
  catalog-validation errors.
- lowering records named `LaneListParameter` facts.
- `lanes<at>(values, N)` lowers for non-negative literal indexes.
- C++ and Rust render `lanes<s>` as the existing array-like lane storage ABI.

Read before executing:

- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md` ADR-079
- `docs/redesign/behavioral-spec.md`
- `docs/agent/review-checklist.md`

## Goal

Complete the lane-list migration for `set` by adding generation-time loop
expansion and then moving the source corpus from:

```tsl
prim<v:=s...>[arg_count(args)=return_vector_length] set(args...):
```

to:

```tsl
prim<v:=(lanes<s>)> set(values):
```

The current reverse-lane behavior expected by value tests must remain explicit
in source, not hidden in backend renderers or the signature.

## Scope

- Implement `loop<generation>(i, start, end, step) { ... }`.
- Reuse the existing four-argument `loop<range>` shape.
- Require generation-time integer bounds; malformed, non-integer, and zero-step
  loops must produce diagnostics.
- Bind the loop variable as a generation-time integer for the expanded body.
- Extend `lanes<at>(values, i)` to accept loop-bound generation-time symbols.
- Support the minimal generation-time arithmetic needed by migrated `set`,
  including `value<generation>(vector::length) - 1 - i`, without turning TSIL
  into a general expression parser.
- Migrate the real corpus `set` signature and bodies from `s...`/`pack<...>` to
  `lanes<s>`/`lanes<at>`.
- Preserve current generated behavior and value-test expectations for `set`.
- Add value-test planning/render coverage for `v:=(lanes<s>)`.
- Remove or quarantine transition-only variadic `set` rendering paths only after
  the migrated corpus no longer needs them.

## Out Of Scope

- Do not add `lanes<expand>` or `lanes<expand_reverse>`.
- Do not change `loop<range>` semantics; it remains an emitted target-language
  loop.
- Do not introduce a broad macro system or collection DSL.
- Do not rewrite unrelated primitive bodies.
- Do not remove old variadic support until all selected source paths and tests
  prove it is unused.

## Validation

At minimum, run:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_lane_lists.py
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_value_tests.py
python -m pytest -q tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

If full `test_set_builds` fails because the migration exposes a real remaining
behavioral gap, stop with diagnostics/evidence and retarget the prompt rather
than papering over it.

## Stop Rule

Stop once `set` is authored with `v:=(lanes<s>)`, generation-time loops/indexes
are implemented only to the accepted scope, value tests cover the new shape, and
the targeted validation above passes. Prepare a cleanup/review prompt for
removing any remaining unused variadic-pack code.
