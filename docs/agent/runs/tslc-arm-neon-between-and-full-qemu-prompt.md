# TSLc ARM NEON Between/Full QEMU Runtime Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
The value-test renderer architecture is finalized; do not redesign it. Work
through `tsldata` plus thin typed support only.

Recent checkpoints:

- NEON direct comparisons plus `to_integral` now generate, build, and pass
  value tests for C++ and Rust under qemu.
- Full NEON coverage now emits `9000 / 9020` attempted slots. The only 20 skips
  are expected Rust/SVE dependency skips: `extension 'sve' is not supported on rust`.
- Fast gate baseline is currently `1 failed, 263 passed, 82 deselected`; the
  only failure is the known safety-contract WIP
  `test_primitive_corpus_safety_covers_direct_unsafe_facts`.

## Next Task

Prove the next runtime slice. Start with the `between_*` comparison family,
because an earlier broad run exposed a Rust
`between_inclusive_f32_between_inclusive_mask_basic` value-test failure before
the C++ `to_integral` blocker was fixed.

Run:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --primitives between_exclusive,between_inclusive,between_left_inclusive,between_right_inclusive \
  --output-root ./tslctmp/neon-between-checkpoint \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl \
  --rust-target aarch64-unknown-linux-musl \
  --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
```

If that fails, inspect generated source and fix the corpus/body/test data
without changing renderer/lane-model architecture. If it passes, run the full
NEON all-primitive C++/Rust qemu gate:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --output-root ./tslctmp/neon-full-qemu \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl \
  --rust-target aarch64-unknown-linux-musl \
  --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
```

## Required Validation

- Targeted generation/build/value tests under qemu for C++ and Rust.
- `python -m compileall -q tslc/src/tslc`
- `PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests`
- `git diff --check`

Do not claim full NEON parity until the full all-primitive command actually
builds and runs successfully.

## Guardrails

- No renderer/lane-model redesign.
- No primitive, extension, or intrinsic name branches in `tslc/src`.
- Mark genuinely cross-lane primitives with `cross_lane true`; elementwise
  primitives need no marker.
- Keep the fast gate at the current baseline. A new failure is a regression.
- Commit the verified runtime slice with the standard trailer.
