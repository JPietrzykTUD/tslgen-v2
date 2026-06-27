# TSLc ARM SVE Random-Access Runtime-Length Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE `conflict` / `conflict_free` checkpoint closed its focused
runtime-length gap:

- focused SVE `conflict,conflict_free` coverage now reports both primitives at
  `24/24 emitted`;
- focused SVE C++ qemu generated `936` specializations and passed CTest;
- full SVE C++ coverage now reports `4361 emitted / 4495 attempted`;
- full SVE C++ qemu generated `4361` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Target the remaining SVE C++ random-access runtime-length coverage gaps. Start
with focused coverage and inspect the exact skipped slots before editing
source.

Current broad signal:

- full SVE coverage reports `expand_load 20/30 emitted, 10 skipped`;
- full SVE coverage reports `gather 20/30 emitted, 10 skipped`;
- full SVE coverage reports `scatter 18/28 emitted, 10 skipped`;
- these direct skips currently report unresolved
  `value<generation>(vector::length)`;
- `extract_value 20/30 emitted, 10 skipped` is currently pruned behind the same
  random-access dependency area.

Work from source data first:

- inspect `tsldata/primitives/load_store/rnd_access.tsl`;
- prefer SVE1-valid scalable bodies using runtime lane counts, ACLE
  predication, and runtime buffers when needed;
- do not use SVE2-only intrinsics under `requires [sve]`;
- do not introduce renderer or lane-model changes;
- leave a slot skipped with an honest diagnostic if it cannot be expressed
  correctly under SVE1.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives expand_load,gather,scatter,extract_value \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-random-access-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives expand_load,gather,scatter,extract_value \
  --output-root ./tslctmp/sve-random-access-checkpoint \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl
```

Full SVE coverage and qemu:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-full-coverage

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

Standard hygiene:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

## Guardrails

- No renderer/lane-model redesign.
- No Rust SVE attempts.
- No primitive, extension, or intrinsic name branches in `tslc/src`.
- Keep fixes source-owned in `tsldata` unless a tiny typed support boundary is
  genuinely required.
- Do not claim SVE coverage parity until every remaining gap is closed and the
  full SVE qemu command passes afterward.
