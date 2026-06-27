# TSLc ARM SVE Convert-Down Scalable Narrowing Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest representation-change checkpoint closed the SVE `convert_up`
runtime-length gaps:

- focused SVE `convert_up,convert_down` coverage now reports
  `convert_up 135/135 emitted`;
- focused SVE C++ qemu generated `1166` specializations and passed CTest;
- full SVE C++ coverage now reports `4169 emitted / 4469 attempted`;
- full SVE C++ qemu generated `4169` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Improve SVE C++ representation-change coverage one primitive or small related
family at a time. Start with the remaining `convert_down` scalable narrowing
gaps.

Current known focused gap:

- `convert_down` still has `13` SVE skipped slots, all due to
  `could not resolve value<generation>(vector::length)`.
- The skipped slots cover signed/unsigned integer narrowing windows and one
  `f64` path.

Important SVE constraint:

- Do not use SVE2-only narrowing intrinsics under `requires [sve]`.
- Evidence from the current environment shows `svqxtn*` is guarded by SVE2
  or SME in `/opt/zig/lib/include/arm_sve.h`, so it is not valid for the
  current SVE profile unless requirements are explicitly split.
- Prefer a correct scalable-valid SVE1 body or leave the slot unselected with
  an honest diagnostic. Do not approximate saturating or narrowing semantics.

Secondary known gap:

- Full SVE coverage has one remaining `generic::length(OutVec)` skip in
  `load_convert_up<f32>`. Treat that as a follow-up unless it becomes the
  smallest safe continuation after `convert_down`.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives convert_down \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-convert-down-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives convert_down \
  --output-root ./tslctmp/sve-convert-down-checkpoint \
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
