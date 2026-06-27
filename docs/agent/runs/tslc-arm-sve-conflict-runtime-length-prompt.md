# TSLc ARM SVE Conflict Runtime-Length Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE `compress` / `compress_store` checkpoint closed the focused
low-width runtime-length gap:

- focused SVE `compress,compress_store` coverage now reports both primitives
  at `30/30 emitted`;
- focused SVE C++ qemu generated `1036` specializations and passed CTest;
- full SVE C++ coverage now reports `4345 emitted / 4495 attempted`;
- full SVE C++ qemu generated `4345` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Target the remaining SVE C++ `conflict` / `conflict_free` runtime-length
coverage gaps. Start with focused coverage and inspect the exact skipped slots
before editing source.

Current broad signal:

- full SVE coverage reports `conflict 16/24 emitted, 8 skipped`;
- full SVE coverage reports `conflict_free 16/24 emitted, 8 skipped`;
- skipped slots currently report unresolved
  `value<generation>(vector::length)`.

Work from source data first:

- inspect `tsldata/primitives/misc/conflict.tsl`;
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
  --primitives conflict,conflict_free \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-conflict-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives conflict,conflict_free \
  --output-root ./tslctmp/sve-conflict-checkpoint \
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
