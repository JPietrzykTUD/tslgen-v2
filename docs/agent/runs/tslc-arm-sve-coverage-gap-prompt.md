# TSLc ARM SVE Coverage Gap Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE C++ runtime slice is green:

- `cast` SVE C++ qemu checkpoint generated `975` specializations and passed
  CTest.
- `compress_store` SVE C++ qemu checkpoint generated `966` specializations and
  passed CTest.
- `test_imask,insert_imask,extract_imask,shift_right_imask` SVE C++ qemu
  checkpoint generated `842` specializations and passed CTest after SVE was
  removed from the integer-mask bit-position helper implementations.
- Full SVE C++ qemu generated `4138` specializations, built, and passed CTest.
- Current SVE coverage inventory reports `4138 emitted / 4469 attempted`.

## Next Task

Improve SVE C++ coverage one primitive or small related family at a time. Start
from the largest explicit source gaps in the current inventory:

- `shift_left` / `shift_right`: old selector templates such as
  `svlsl_n_{{ ?i? }}_x`, `svlsr_n_{{ ?i? }}_x`, and `svdup_n_{{ ui? }}` still
  need unified `intrin<..., build[...]>` source forms or a scalable-safe
  fallback.
- `cast` / extraction families: unresolved `generic::runtime_length(ToType)`
  and `generic::length(OutVec)` queries still block some scalable conversion
  and extraction slots.
- `from_array`, `to_array`, `set`, `gather`, `scatter`, and related array/list
  signatures still have unsupported shape gaps; address only if the slice can
  stay corpus-driven and typed.

For each primitive/family, run focused coverage and qemu build/test before
retrying full SVE.

## Required Commands

Focused SVE C++ qemu template:

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

Full SVE coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-full-coverage
```

Full SVE qemu:

```bash
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
- For native-predicate SVE, do not force integer-mask bit operations onto
  `svbool_t`; leave non-scalable integer-mask helper shapes unselected unless
  there is a real typed scalable contract.
- Do not claim full SVE coverage parity until the coverage gaps are actually
  closed and the full SVE qemu command passes afterward.
