# TSLc ARM SVE Sequence Float Runtime-Length Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE random-access checkpoint closed its focused runtime-length gap:

- focused SVE coverage reports `expand_load 30/30`, `gather 30/30`,
  `scatter 28/28`, and `extract_value 30/30`;
- focused SVE C++ qemu generated `916` specializations and passed CTest;
- full SVE C++ coverage now reports `4401 emitted / 4495 attempted`;
- full SVE C++ qemu generated `4401` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Target the remaining direct SVE C++ runtime-length skips:

- `sequence` SVE `f32` and `f64`;
- `custom_sequence` SVE `f32` and `f64`;
- unmasked `hand` SVE `f32` and `f64`.

Current broad skip signal:

- the only remaining direct `value<generation>(vector::length)` skips are the
  six slots above;
- other remaining skips are pruned dependency slots or unsupported signatures
  such as `s[]:=v`, `v:=s[]`, and `v:=(lanes<s>)`.

Work from source data first:

- inspect `tsldata/primitives/load_store/sequence.tsl`;
- inspect `tsldata/primitives/bitwise/horizontal.tsl`;
- prefer SVE1-valid scalable bodies using runtime lane counts and ACLE
  predication or existing typed primitive composition;
- do not use SVE2-only intrinsics under `requires [sve]`;
- do not introduce renderer, lane-model, or value-test planner changes;
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
  --primitives sequence,custom_sequence,hand \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-sequence-float-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives sequence,custom_sequence,hand \
  --output-root ./tslctmp/sve-sequence-float-checkpoint \
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
- Do not claim SVE coverage parity until the remaining gaps are actually
  closed and the full SVE qemu command passes afterward.
