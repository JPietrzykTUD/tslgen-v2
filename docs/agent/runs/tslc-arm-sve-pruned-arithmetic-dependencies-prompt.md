# TSLc ARM SVE Pruned Arithmetic Dependencies Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE sequence/float checkpoint closed the last direct
`value<generation>(vector::length)` skips:

- focused SVE coverage reports `sequence 30/30`, `custom_sequence 30/30`,
  and `hand 30/30`;
- focused SVE C++ qemu generated `888` specializations and passed CTest;
- full SVE C++ coverage now reports `4407 emitted / 4495 attempted`;
- full SVE C++ qemu generated `4407` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

Remaining full SVE C++ skips are now:

- `58` pruned dependency slots:
  - `mod`: `12` skipped;
  - `mod_imm`: `18` skipped;
  - `mul_imm`: `4` skipped;
  - `shift_left`: `8` skipped;
  - `shift_right`: `6` skipped;
  - `to_ostream`: `10` skipped;
- unsupported signature kinds for `to_array` (`s[]:=v`), `from_array`
  (`v:=s[]`), and `set` (`v:=(lanes<s>)`), `10` each.

Representative explain output:

- `mod<sve, si8>` masked variants prune because they call `mod<sve, si8>`
  and that callee is not generated for the profile;
- `mul_imm<sve, f32>` masked variants prune because they call masked
  `mul<sve, f32>` forms that are not generated;
- `shift_left<sve, f32>` float variants still bounce through generic
  `from_array`/`to_array` and generic shift dependencies;
- `to_ostream<sve, f32>` prunes on `to_array<sve, f32>`.

## Next Task

Target the SVE arithmetic pruned-dependency cluster first:

- `mod` SVE skipped slots;
- `mod_imm` SVE skipped slots;
- `mul_imm` SVE skipped slots.

Work from source data first:

- inspect `tsldata/primitives/arithmetic/complex.tsl`;
- use `tslc.maintenance.explain` on representative skipped slots before
  editing;
- prefer SVE1-valid direct intrinsic bodies or composition through already
  generated SVE primitives;
- avoid generic `from_array` / `to_array` fallback bodies for SVE scalable
  vectors unless the signature support gap is intentionally addressed in a
  separate typed compiler slice;
- do not introduce renderer, lane-model, value-test planner, or Rust SVE
  changes;
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
  --primitives mod,mod_imm,mul_imm \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-arithmetic-pruned-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives mod,mod_imm,mul_imm \
  --output-root ./tslctmp/sve-arithmetic-pruned-checkpoint \
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
