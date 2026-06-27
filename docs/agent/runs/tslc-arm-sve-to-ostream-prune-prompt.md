# TSLc ARM SVE To-Ostream Coverage Prompt

## Context

Continue the active ARM per-primitive coverage goal. The previous checkpoint
closed the SVE C++ low-width `mod` callees and the dependent `mod_imm` forms.

Current SVE C++ coverage baseline:

```text
4469 emitted / 4509 attempted
```

At this point the only full-SVE dependency prune in the coverage summary is
`to_ostream`; the other skipped buckets are the known unsupported scalable
signatures for `from_array`, `to_array`, and `set`.

Sampled explain output shows that `to_ostream<sve, si32>` and
`to_ostream<sve, f32>` select the common body in
`tsldata/primitives/io/out.tsl`, lower successfully, and then prune only because
they call `to_array[Vec]`, which is intentionally unsupported for scalable SVE
vectors.

## Goal

Close the SVE C++ `to_ostream` dependency prune without changing `tslc/src`
architecture and without enabling Rust SVE.

## Scope

Allowed:

- Edit `tsldata/primitives/io/out.tsl`.
- Add a source-owned SVE C++ implementation that writes scalable vector lanes
  without using `to_array[Vec]`.
- Use the same runtime-buffer pattern already used by other SVE bodies if that
  is the simplest valid shape.
- Update handoff docs and create the next concrete prompt.

Out of scope:

- Rust SVE support.
- Renderer, lane-model, planner, or value-test framework changes.
- Adding a general scalable `to_array` implementation.
- Fixing unsupported scalable signatures for `from_array`, `to_array`, or
  `set`.
- Treating primitive, extension, or intrinsic names as special in `tslc/src`.

## Required Investigation

Start with:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive to_ostream \
  --type si32

PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive to_ostream \
  --type f32
```

Then inspect `tsldata/primitives/io/out.tsl` and the C++ helper surface for
`io<format>`. Prefer preserving the existing `io<format>` lowering if it can be
fed a runtime buffer or array-like value cleanly from source.

## Validation

Run at least:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives to_ostream \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-to-ostream-coverage

PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives to_ostream \
  --output-root ./tslctmp/sve-to-ostream-checkpoint \
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
