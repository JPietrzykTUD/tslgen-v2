# TSLc ARM SVE Residual Scalable Signatures Prompt

## Context

Continue the active ARM per-primitive coverage goal. The previous checkpoint
closed the SVE C++ `to_ostream` dependency prune by adding a source-owned
runtime-buffer formatter body.

Current SVE C++ coverage baseline:

```text
4479 emitted / 4509 attempted
```

There are no remaining dependency-prune buckets in the full SVE C++ coverage
summary. The only skipped buckets are the explicit unsupported scalable
signatures:

- `from_array`: `v:=s[]`
- `to_array`: `s[]:=v`
- `set`: `v:=(lanes<s>)`

These are the places most likely to intersect the scalable-vector/lane-list
boundary. Do not quietly redesign the renderer or lane model to make the number
go up.

## Goal

Decide and implement the smallest correct next step for the residual SVE C++
scalable signatures.

Acceptable outcomes:

1. A source-owned implementation is possible for a primitive without changing
   `tslc/src`; implement and verify it.
2. The primitive is genuinely not meaningful for scalable SVE as currently
   declared; mark or model the source data so coverage no longer treats it as a
   missing generated primitive, if such a source-owned mechanism already exists.
3. The right fix requires a `tslc/src` architecture change; stop and report the
   exact required change instead of making it ad hoc.

## Scope

Allowed:

- Inspect `tsldata/primitives/load_store/array.tsl` and
  `tsldata/primitives/load_store/construct.tsl`.
- Inspect selection/support policy only to understand why these signatures are
  skipped.
- Edit `tsldata` if a source-owned fix is possible.
- Update handoff docs and create the next concrete prompt.

Out of scope:

- Rust SVE support.
- Renderer, value-test planner, or broad lane-model redesign.
- Adding primitive, extension, or intrinsic-name branches in `tslc/src`.
- Treating a skipped unsupported signature as green without documenting the
  typed reason.

## Required Investigation

Start with:

```bash
PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive from_array \
  --type si32

PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive to_array \
  --type si32

PYTHONPATH=tslc/src python -m tslc.maintenance.explain \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backend cpp \
  --profile sve \
  --extension sve \
  --primitive set \
  --type si32
```

Also run focused coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives from_array,to_array,set \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-residual-signatures-coverage
```

## Validation

If code/data changes are made, run the focused gate for the affected primitive
set and then the full SVE gates:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --primitives from_array,to_array,set \
  --output-root ./tslctmp/sve-residual-signatures-checkpoint \
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

Commit one verified milestone if a source-owned implementation or source-owned
coverage modeling change is made. If the correct answer requires architecture
work, stop with a concise explanation and do not fake coverage.
