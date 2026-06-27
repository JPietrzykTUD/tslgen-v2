# TSLc ARM SVE Conversion/Extract Gap Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE shift cleanup is verified:

- old SVE shift selector-template spellings such as `svlsl_n_{{ ?i? }}_x`,
  `svlsr_n_{{ ?i? }}_x`, `svasr_n_{{ ?i? }}_x`, `svdup_n_{{ ui? }}`,
  `svlsr_{{ ?i? }}_x`, and `svasr_{{ ?i? }}_x` are gone from
  `tsldata/primitives/bitwise/shifts.tsl`;
- focused SVE `shift_left,shift_right` qemu generated `902` specializations
  and passed CTest;
- full SVE C++ qemu generated `4138` specializations and passed CTest;
- current SVE coverage still reports `4138 emitted / 4469 attempted`, but the
  explicit stale-intrinsic skip reasons are gone.

## Next Task

Improve SVE C++ coverage one primitive or small related family at a time.
Start with the remaining conversion/extract runtime-length gaps:

- `cast`, `convert_up`, `convert_down`, `extract`, or `extract_value` paths
  that still report unresolved `generic::runtime_length(ToType)` or
  `generic::length(OutVec)`.
- Keep fixes corpus-driven and typed. Prefer scalable-valid direct SVE bodies
  or already-supported typed queries. Do not add renderer/lane-model behavior.
- If a path is inherently fixed-window/cross-lane and not scalable-valid, mark
  or leave it unselected rather than mistiling SVE.

Use focused coverage first to confirm the exact primitive/family being worked.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives CURRENT_ACTIVE_PRIMITIVE \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-CURRENT_ACTIVE_PRIMITIVE-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives CURRENT_ACTIVE_PRIMITIVE \
  --output-root ./tslctmp/sve-CURRENT_ACTIVE_PRIMITIVE-checkpoint \
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
- Fix through `tsldata` plus thin typed support only.
- Do not claim SVE coverage parity until the remaining gaps are actually closed
  and the full SVE qemu command passes afterward.
