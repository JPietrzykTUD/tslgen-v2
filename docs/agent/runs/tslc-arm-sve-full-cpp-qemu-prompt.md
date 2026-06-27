# TSLc ARM SVE Full C++ QEMU Runtime Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is now runtime-green for C++ and Rust:

- full NEON coverage emitted `9000 / 9020` slots, with only Rust/SVE dependency
  skips;
- full all-primitive NEON C++/Rust qemu gate generated `9000`
  specializations;
- C++ CTest passed;
- Rust qemu value tests passed with `1144 passed`.

SVE remains Phase 2 and is C++ only. Rust SVE is declared unsupported and must
not be attempted.

The current fast gate baseline is `1 failed, 263 passed, 82 deselected`; the
only known failure is
`test_primitive_corpus_safety_covers_direct_unsafe_facts`.

## Next Task

Run the full SVE C++ coverage inventory first:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-full-coverage
```

Then run the full SVE C++ qemu gate:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --output-root ./tslctmp/sve-full-qemu \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl
```

If the full SVE run fails, narrow to the failing primitive or small family,
fix via `tsldata` plus thin typed support only, then rerun the focused SVE
C++ qemu gate before retrying the full gate.

## Required Validation

- SVE C++ coverage inventory.
- SVE C++ qemu generation/build/value-test run for the target slice.
- `python -m compileall -q tslc/src/tslc`
- `PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests`
- `git diff --check`

## Guardrails

- No renderer/lane-model redesign.
- No Rust SVE attempts; SVE Rust is `supported false`.
- No primitive, extension, or intrinsic name branches in `tslc/src`.
- Cross-lane scalable operations must be truly scalable-valid or explicitly
  `cross_lane true` so they are skipped rather than mistiled.
- Do not claim SVE full parity until the full SVE C++ qemu command actually
  passes.
- Commit the verified SVE runtime slice with the standard trailer.
