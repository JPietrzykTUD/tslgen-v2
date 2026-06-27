# TSLc ARM SVE Compress Runtime-Length Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE cast/reinterpret checkpoint closed the focused `cast` gap:

- focused SVE `cast` coverage now reports `241/241 emitted`;
- focused SVE C++ qemu generated `1039` specializations and passed CTest;
- full SVE C++ coverage now reports `4337 emitted / 4495 attempted`;
- full SVE C++ qemu generated `4337` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Target the remaining SVE C++ `compress` / `compress_store` runtime-length
coverage gaps. Start with focused coverage and inspect the exact skipped slots
before editing source.

Current broad signal:

- full SVE coverage reports `compress 26/30 emitted, 4 skipped`;
- full SVE coverage reports `compress_store 26/30 emitted, 4 skipped`;
- both skipped groups currently report unresolved
  `value<generation>(vector::length)`.

Work from source data first:

- inspect `tsldata/primitives/misc/compress.tsl`;
- prefer SVE1-valid scalable bodies using runtime lane counts or ACLE
  predication;
- do not use SVE2-only intrinsics under `requires [sve]`;
- if a compact/pack operation truly cannot be expressed for a type under SVE1,
  leave the slot skipped with an honest diagnostic rather than adding a
  fixed-lane workaround;
- do not introduce renderer or lane-model changes.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives compress,compress_store \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-compress-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives compress,compress_store \
  --output-root ./tslctmp/sve-compress-checkpoint \
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
