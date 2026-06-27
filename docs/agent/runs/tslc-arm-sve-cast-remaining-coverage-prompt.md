# TSLc ARM SVE Cast Remaining Coverage Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE load-convert checkpoint closed the final `load_convert_up`
coverage gap:

- focused SVE `load_convert_up` coverage now reports `39/39 emitted`;
- focused SVE C++ qemu generated `801` specializations and passed CTest;
- full SVE C++ coverage now reports `4183 emitted / 4469 attempted`;
- full SVE C++ qemu generated `4183` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

## Next Task

Continue SVE C++ conversion-family closure by targeting the remaining `cast`
coverage gaps. Start with focused coverage and inspect the exact skipped slots
before editing source.

Current broad signal:

- focused SVE `cast` coverage reports `217/241 emitted`;
- full SVE coverage still reports `cast 217/241 emitted`;
- previous SVE conversion fixes were source-owned in `tsldata` and did not
  require renderer or lane-model changes.

Work from source data first:

- inspect `tsldata/primitives/conversion/cast.tsl`;
- prefer SVE1-valid direct ACLE conversions where the current profile supports
  them;
- when no direct SVE1 intrinsic is available, either compose existing typed
  primitives safely or leave the slot skipped with an honest diagnostic;
- do not use SVE2-only intrinsics under `requires [sve]`;
- do not introduce renderer or lane-model changes.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives cast \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-cast-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives cast \
  --output-root ./tslctmp/sve-cast-checkpoint \
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
