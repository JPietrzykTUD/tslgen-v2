# TSLc Rust Warning Hygiene Review Prompt

## Goal

Review the focused Rust compiler-warning cleanup slice.

## Scope

Files to inspect:

- `tslc/src/tslc/lower/region_handlers/control.py`
- `tslc/src/tslc/lower/region_handlers/declarations.py`
- `tslc/src/tslc/backend/rust.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/tests/test_generation_conditionals.py`
- `tslc/tests/test_specialization.py`
- `tsldata/detail/lang/translate_c17.tsl`
- `tsldata/detail/lang/translate_cpp.tsl`
- `tsldata/detail/lang/translate_rust.tsl`
- `tsldata/primitives/arithmetic/horizontal.tsl`
- `tsldata/primitives/bitwise/horizontal.tsl`
- `tsldata/primitives/conversion/cast.tsl`
- `tsldata/primitives/conversion/mask_specific.tsl`
- `tsldata/primitives/load_store/array.tsl`
- `tsldata/primitives/load_store/construct.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/rnd_access.tsl`
- `tsldata/primitives/load_store/store.tsl`
- `tsldata/primitives/misc/conflict.tsl`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Expected Design

- Runtime `if` condition spelling is backend-owned through translation
  templates. C++ keeps `if ({cond})`; Rust emits `if {cond}`.
- Rust cast spelling preserves precedence without wrapping the whole cast
  expression, using `({expr}) as {type}`.
- Rust pointer casts avoid an extra outer pair of parentheses.
- Source bodies own source-level constness:
  - non-mutated `var<infer>` and `var<typed>` declarations are converted to
    `var<const_infer>` / `var<const_typed>`;
  - declarations mutated through assignment, `mask<set>`, pointer writes, or
    `mem<copy>` destinations stay mutable.
- Source bodies parenthesize cast-before-shift only where the cast result is
  intentionally shifted.
- Rust `s[]` parameters are immutable by default; bodies that need `.data()`
  introduce their own mutable local copy in source.
- `var<const_init_register>` is used only for zero-register locals that are not
  mutated before completion; mutable `var<init_register>` remains available for
  bodies that write lanes.
- Renderers and templates format already-decided syntax; no primitive-name or
  extension-name behavior branches should be introduced.
- Remaining Rust warnings should be documented as out-of-scope for this slice:
  unnecessary `unsafe` wrappers.

## Validation Already Run

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends rust \
  --output-root ./tslctmp/TEST \
  --test \
  --value-test-warnings
```

Result: passed, including visible Rust value-test execution output.

```bash
cargo test --manifest-path tslctmp/TEST/rust/Cargo.toml \
  --no-default-features \
  --features scalar,sse2,avx,avx2,skylake,value_tests
```

Result: passed. The warning census reported zero
`unnecessary parentheses around ...` warnings and zero `unused_mut` warnings.
Remaining compiler warnings were `228` unnecessary `unsafe` blocks.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py tslc/tests/test_select_and_lower.py tslc/tests/test_masks_and_calls.py
```

Result: `48 passed`.

```bash
python -m pytest -q tslc/tests/test_generation_conditionals.py tslc/tests/test_specialization.py::test_cast_lowers_integer_reductions tslc/tests/test_build_verify.py::test_full_corpus_builds
```

Result: `22 passed`.

```bash
git diff --check
```

Result: passed.

```bash
./verify.sh
```

Result: passed, including 191 non-build tests and 53 generated-build tests.

## Review Questions

1. Does runtime `if` rendering now respect the backend translation boundary?
2. Is the Rust cast cleanup precedence-safe, especially for cast-before-shift
   source bodies?
3. Are the source constness edits conservative and semantically correct?
4. Does the new test cover the important regression without overfitting to a
   primitive-specific design?
5. Are remaining Rust warnings accurately documented as separate follow-ups?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
