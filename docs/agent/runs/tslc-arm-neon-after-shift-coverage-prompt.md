# TSLc ARM NEON Coverage Prompt After Shift Checkpoint

Continue the active ARM per-primitive coverage goal from branch `claude`.

Current verified checkpoints on this branch:

- `19e1ba0 value-tests: cover NEON masked comparisons`
- Follow-up working-tree checkpoint: NEON `shift_left` and `shift_right` are
  verified for C++ and Rust under qemu.

Shift checkpoint details:

- Migrated NEON shift intrinsic selector spellings in
  `tsldata/primitives/bitwise/shifts.tsl` from old
  `intrin<vshlq_{{ ... }}>` forms to unified
  `intrin<name, build[suffix=...]>` forms.
- Replaced NEON immediate right-shift `_n` intrinsics with the vector-shift
  formulation using a negative signed shift vector, because `vshrq_n_*` rejects
  immediate shift `0` while the generated smoke surface instantiates zero-shift
  wrappers.
- Rewrote signed negation as signed subtraction from zero so generated Rust
  casts before negating.

Verified command:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --primitives shift_left,shift_right \
  --output-root ./tslctmp/neon-shift-checkpoint \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl \
  --rust-target aarch64-unknown-linux-musl \
  --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
```

Result: generated `2076` specializations; C++ CTest passed; Rust qemu smoke
passed; Rust qemu value tests passed with `258 passed`; `build/test-verified
12 commands`.

Fast gate after the shift checkpoint:

```bash
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
```

Result: `1 failed, 263 passed, 82 deselected`. The only remaining failure is
the known safety-contract WIP:

- `tslc/tests/test_safety_contract.py::test_primitive_corpus_safety_covers_direct_unsafe_facts`

Next action:

1. Run full NEON coverage discovery again:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/neon-all-coverage-discovery
```

2. Pick the next concrete primitive or small related batch from remaining
   NEON skips.
3. Fix only source data or narrow typed support; do not reopen renderer or
   lane-model architecture.
4. Verify generation, build, and qemu value tests for both C++ and Rust.
5. Re-run the fast gate and preserve the improved one-failure baseline.
6. Commit the checkpoint with the standard co-author trailer.
