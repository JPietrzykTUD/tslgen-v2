# TSLc ARM NEON Next Primitive Coverage Prompt

Continue the active ARM per-primitive coverage goal from branch `claude`.

Context:

- Renderer and lane-model architecture are settled; do not redesign them.
- Add coverage through `tsldata` plus narrow, typed planner/source support only.
- NEON C++ and Rust must both generate, build, and run under qemu for each
  targeted primitive or small related batch.
- Rust NEON execution is proven with target `aarch64-unknown-linux-musl`, the
  zig linker wrapper under `tslctmp/zig-aarch64-linux-musl-cc`, and qemu.
- SVE remains Phase 2 and C++ only.

Completed checkpoint before this prompt:

- Fixed fixed-width masked mask-result value-test planning for signatures shaped
  like `m:=(m,v,v)`.
- Reordered authored masked comparison tests so mask inputs match the source
  signature for `equal`, `nequal`, `less_than`, `greater_than`,
  `less_than_or_equal`, and `greater_than_or_equal`.
- Corrected the `nequal` masked float NaN/inf edge expected lane for an active
  `INFINITY != 0.0` lane.
- Verified the masked comparison batch with:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --primitives equal,nequal,less_than,greater_than,less_than_or_equal,greater_than_or_equal \
  --output-root ./tslctmp/neon-mask-comparison-checkpoint \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl \
  --rust-target aarch64-unknown-linux-musl \
  --rust-linker /workspaces/tslgen-v99/tslctmp/zig-aarch64-linux-musl-cc
```

Result: generated `2556` specializations, C++ CTest passed, Rust qemu value
tests passed with `420 passed`, and `build/test-verified 12 commands`.

Fast gate after this checkpoint:

```bash
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
```

Result: `1 failed, 263 passed, 82 deselected`. The remaining failure is the
known safety-contract WIP:

- `tslc/tests/test_safety_contract.py::test_primitive_corpus_safety_covers_direct_unsafe_facts`

The two previous AVX2 value-test WIP failures now pass because the masked
comparison source-shape fix removed their authored-unplanned diagnostics. Do
not reintroduce those failures to preserve the old count.

Next action:

1. Pick the next NEON primitive or small related batch with missing/generated
   value-test coverage.
2. Run generation first with `--coverage --value-test-warnings` for that
   primitive/batch.
3. Fix source data or narrow typed support only where the evidence points.
4. Run the full NEON C++/Rust qemu command for the targeted primitive/batch.
5. Re-run the fast gate and preserve the improved baseline shape: only the
   safety-contract WIP should fail.
6. Commit the checkpoint with an honest message and the standard
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
   trailer when the targeted primitive/batch is verified.
