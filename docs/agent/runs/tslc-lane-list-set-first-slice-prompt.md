# TSLc Lane-List `set` First Slice

## Accepted State

The active implementation line is `tslc/`. The prior `tslgen/` milestone
history is retained only as history. Read before planning or executing:

- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/redesign/design-decisions.md` ADR-079
- `docs/redesign/behavioral-spec.md`
- `docs/agent/review-checklist.md`

## Goal

Start replacing the variadic `set` source shape with a first-class lane-list
shape without implementing the entire migration at once.

Current source shape:

```tsl
prim<v:=s...>[arg_count(args)=return_vector_length] set(args...):
```

Target source shape:

```tsl
prim<v:=(lanes<s>)> set(values):
```

Accepted semantic mechanisms:

```tsl
lanes<at>(values, N)
loop<generation>(i, start, end, step) { ... }
```

## First-Slice Scope

Implement the smallest end-to-end slice that makes the new lane-list concept
real while preserving current generated behavior:

- Parse and model `lanes<s>` as a structured signature parameter term.
- Validate only parameter-position `lanes<s>` for now.
- Reject malformed lane-list forms such as `lanes<>`, `lanes<v>`, nested
  `lanes<...>`, and result-position lane lists.
- Lower a named lane-list parameter as a typed fact carrying element kind `s`
  and the selected lane count.
- Add `lanes<at>(values, N)` for literal generation-time indexes.
- Migrate only the scalar `set` implementation, or one similarly tiny concrete
  `set` path, far enough to prove the end-to-end shape.
- Add focused unit tests for parsing/validation/lowering and one generated
  value or build verification test for the migrated path.

## Explicitly Out Of Scope

- Do not implement full SIMD `set` migration in this first slice.
- Do not add `lanes<expand>` or `lanes<expand_reverse>`.
- Do not remove `s...`, `arg_count(args)=return_vector_length`,
  `pack<expand>`, or `pack<first>` until no selected source path needs them.
- Do not change `loop<range>` semantics; it remains an emitted target-language
  loop.
- Do not implement broad generation-time expression parsing beyond what the
  selected `lanes<at>` literal-index slice needs.

## Follow-Up Slice

After the first slice is accepted:

- Add `loop<generation>(i, start, end, step) { ... }` with generation-time
  integer bounds.
- Allow `lanes<at>(values, i)` when `i` is bound by `loop<generation>`.
- Migrate the full SIMD `set` body and preserve current reverse construction
  explicitly in source.
- Add value-test planning for `v:=(lanes<s>)`.
- Remove or quarantine old variadic-pack behavior.

## Required Validation

At minimum, run:

```bash
python -m compileall -q tslc/src/tslc tslc/tests
python -m pytest -q tslc/tests/test_support_policy.py
python -m pytest -q tslc/tests/test_select_and_lower.py
python -m pytest -q tslc/tests/test_masks_and_calls.py
python -m pytest -q tslc/tests/test_build_verify.py::test_set_builds
git diff --check
```

If `test_set_builds` remains too broad for the first slice, add and run a
narrower focused build/value test that proves the migrated path, and document
why full `set` migration remains in the follow-up.

## Expected Output

Produce a focused implementation plus tests and documentation updates. Keep the
surface small and explicit; do not turn lane lists into a general collection or
macro system.

## Stop Rule

Stop after the first lane-list slice is implemented and verified. Prepare the
next prompt for `loop<generation>` and full SIMD `set` migration rather than
continuing into it.
