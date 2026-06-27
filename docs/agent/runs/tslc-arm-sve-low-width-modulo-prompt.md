# TSLc ARM SVE Low-Width Modulo Coverage Prompt

## Context

Continue the active ARM per-primitive coverage goal. The previous checkpoint
closed the SVE C++ float `shift_left` and `shift_right` dependency prunes in
`tsldata/primitives/bitwise/shifts.tsl`.

Current SVE C++ coverage baseline:

```text
4445 emitted / 4505 attempted
```

The remaining full-SVE dependency prunes are concentrated in `mod`, `mod_imm`,
and `to_ostream`, plus the known unsupported scalable signatures for
`from_array`, `to_array`, and `set`.

The sampled explains show that `mod_imm` prunes only because it composes through
missing low-width `mod` callees:

- `mod<sve, si8>`
- `mod<sve, si16>`
- `mod<sve, ui8>`
- `mod<sve, ui16>`

The prior arithmetic checkpoint already confirmed with an ACLE probe that direct
`svdiv_f32_x` exists, while direct `svdiv_s8_x` and `svdiv_s16_x` do not exist
in the installed toolchain. Do not add invalid SVE intrinsic spellings just to
increase coverage.

## Goal

Close the SVE C++ low-width modulo coverage gap for `mod` and the dependent
`mod_imm` forms without changing `tslc/src` architecture and without enabling
Rust SVE.

## Scope

Allowed:

- Edit `tsldata/primitives/arithmetic/complex.tsl`.
- Add SVE1-valid source-owned implementations for low-width integer modulo.
- Use runtime-buffer fallback bodies if no direct SVE1 intrinsic composition is
  valid.
- Use direct SVE2-only intrinsics only if they are guarded by explicit SVE2
  requirements and the profile/coverage result is understood.
- Update handoff docs and create the next concrete prompt.

Out of scope:

- Rust SVE support.
- Renderer, lane-model, planner, or value-test framework changes.
- Treating SVE names as special in `tslc/src`.
- Adding broad modulo DSL machinery.
- Fixing `to_ostream`, `from_array`, `to_array`, or `set` signatures in this
  slice.

## Required Investigation

Start with:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive mod \
  --type si8

PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive mod_imm \
  --type si8
```

Then inspect the selected `mod` and `mod_imm` bodies in
`tsldata/primitives/arithmetic/complex.tsl`.

## Validation

Run at least:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives mod,mod_imm \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-low-width-modulo-coverage

PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives mod,mod_imm \
  --output-root ./tslctmp/sve-low-width-modulo-checkpoint \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl

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

python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

The fast non-build gate currently has one known baseline failure:

```text
test_primitive_corpus_safety_covers_direct_unsafe_facts
```

Do not treat that as introduced by this slice unless the failure set changes.

## Completion

Commit one verified milestone with the usual co-author trailer. Do not mark the
overall goal complete unless SVE C++ coverage and the broader ARM parity goal
are actually complete.
