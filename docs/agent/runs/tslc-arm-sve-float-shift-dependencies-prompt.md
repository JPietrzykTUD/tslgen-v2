# TSLc ARM SVE Float Shift Dependencies Prompt

## Context

Continue the active ARM NEON/SVE per-primitive bring-up on branch `claude`.
Phase 1 NEON is runtime-green for C++ and Rust. Phase 2 SVE is C++ only;
Rust SVE is declared unsupported and must not be attempted.

The latest SVE arithmetic dependency checkpoint improved the arithmetic
cluster:

- focused SVE coverage for `mod,mod_imm,mul_imm` improved from
  `1072 emitted / 1126 attempted` to `1096 emitted / 1136 attempted`;
- `mul` and `mul_imm` now report `90/90`;
- `mod` improved to `78/86`, with only `si8/si16/ui8/ui16` masked forms
  still pruned;
- `mod_imm` improved to `78/90`, with only `si8/si16/ui8/ui16` runtime and
  masked forms still pruned;
- focused SVE C++ qemu generated `1326` specializations and passed CTest;
- full SVE C++ coverage now reports `4431 emitted / 4505 attempted`;
- full SVE C++ qemu generated `4431` specializations and passed CTest;
- the fast non-build gate remains at `1 failed, 263 passed, 82 deselected`,
  with only the known safety-contract WIP failure.

An ACLE compile probe confirmed `svdiv_f32_x` exists, but `svdiv_s8_x` and
`svdiv_s16_x` do not. Do not close the remaining small-width integer modulo
prunes by pretending direct 8/16-bit SVE division exists; they need a real
widening/narrowing design or an explicit deferred-support decision.

Remaining full SVE C++ skips are now:

- `44` pruned dependency slots:
  - `mod`: `8` skipped (`si8`, `si16`, `ui8`, `ui16`, two forms each);
  - `mod_imm`: `12` skipped (`si8`, `si16`, `ui8`, `ui16`, three forms each);
  - `shift_left`: `8` skipped (`f32`, `f64`, four forms each);
  - `shift_right`: `6` skipped (`f32`, `f64`, three forms each);
  - `to_ostream`: `10` skipped;
- unsupported signature kinds for `to_array` (`s[]:=v`), `from_array`
  (`v:=s[]`), and `set` (`v:=(lanes<s>)`), `10` each.

## Next Task

Target the SVE float shift dependency cluster:

- `shift_left` SVE `f32` and `f64` skipped forms;
- `shift_right` SVE `f32` and `f64` skipped forms.

Work from source data first:

- inspect `tsldata/primitives/bitwise/shifts.tsl`;
- use `tslc.maintenance.explain` on representative skipped slots before
  editing;
- prefer SVE1-valid direct bodies over the current generic
  `from_array`/`to_array` bounce;
- for float bit shifts, preserve bitwise semantics by reinterpreting through a
  same-width unsigned vector where appropriate, following existing source-owned
  SVE idioms;
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
  --primitives shift_left,shift_right \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-float-shift-coverage
```

Focused SVE C++ qemu:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives shift_left,shift_right \
  --output-root ./tslctmp/sve-float-shift-checkpoint \
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
