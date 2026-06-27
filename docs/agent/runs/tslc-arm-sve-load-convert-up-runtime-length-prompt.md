# TSLc ARM SVE Load-Convert-Up Runtime-Length Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE representation-change checkpoint closed the `convert_down`
runtime-length gaps:

- focused SVE `convert_down` coverage now reports `65/65 emitted`;
- focused SVE C++ qemu generated `827` specializations and passed CTest;
- full SVE C++ coverage now reports `4182 emitted / 4469 attempted`;
- full SVE C++ qemu generated `4182` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Close the remaining full-SVE `generic::length(OutVec)` skip. Start with
`load_convert_up`, which currently has one known SVE C++ coverage gap in the
`f32` path.

Work from the source data first:

- inspect `tsldata/primitives/load_store` and related conversion helpers;
- prefer a source-owned `tsldata` fix;
- keep the implementation SVE1-valid under the current `requires [sve]`
  profile;
- do not introduce renderer or lane-model changes.

The goal for this slice is narrow:

- focused `load_convert_up` SVE C++ generation exits 0;
- focused `load_convert_up` SVE C++ value tests build and pass under qemu;
- full SVE C++ coverage improves without regressing already closed
  `convert_up` / `convert_down` slots;
- full SVE C++ value tests still pass under qemu;
- the fast non-build gate remains at the known safety-contract WIP baseline.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives load_convert_up \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-load-convert-up-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives load_convert_up \
  --output-root ./tslctmp/sve-load-convert-up-checkpoint \
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
- Preserve the value-test helper boundary: `tsl_test_core.hpp` exposes generic
  adapter APIs only; SVE ACLE helper code belongs in `tsl_test_sve.hpp`.
- Do not claim SVE coverage parity until every remaining gap is closed and the
  full SVE qemu command passes afterward.
