# TSLc ARM SVE Representation-Change Runtime-Length Gap Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE cast coverage checkpoint is verified:

- SVE `cast` no longer uses the unresolved
  `value<generation>(generic::runtime_length(ToType))` query;
- focused SVE `cast` coverage improved from `213/241` to `217/241`;
- full SVE C++ coverage improved from `4138 emitted / 4469 attempted` to
  `4142 emitted / 4469 attempted`;
- focused SVE `cast` qemu generated `979` specializations and passed CTest;
- full SVE C++ qemu generated `4142` specializations and passed CTest;
- the fast gate remains at `1 failed, 263 passed, 82 deselected`, with only
  the known safety-contract WIP failure.

## Next Task

Improve SVE C++ conversion/extract coverage one primitive or small related
family at a time. Start with the remaining representation-change runtime-length
gaps:

- `convert_up` and `convert_down` still report unresolved
  `generic::length(OutVec)` and generation-time conditions that depend on it.
- Prefer scalable-valid direct SVE bodies or already-supported typed queries.
- Do not add renderer/lane-model behavior.
- If a path is inherently fixed-window/cross-lane and not scalable-valid,
  leave it unselected or mark it honestly rather than mistiling SVE.

Use focused coverage first to confirm the exact primitive/family being worked.

## Required Commands

Focused SVE C++ coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives convert_up,convert_down \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-repr-change-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives convert_up,convert_down \
  --output-root ./tslctmp/sve-repr-change-checkpoint \
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
