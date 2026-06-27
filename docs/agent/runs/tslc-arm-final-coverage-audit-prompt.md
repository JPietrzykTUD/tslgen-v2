# TSLc ARM Final Coverage Audit Prompt

## Context

Continue the active ARM per-primitive coverage goal. The SVE C++ residual
fixed-lane signatures are now typed as policy-deferred:

- `from_array`: `v:=s[]`
- `to_array`: `s[]:=v`
- `set`: `v:=(lanes<s>)`

Full SVE C++ coverage currently reports:

```text
4479 emitted / 4479 attempted, 30 policy-deferred slots
```

Rust SVE remains source-declared unsupported and out of scope.

## Goal

Run a completion audit for the ARM goal without redefining success.

Prove or disprove:

1. NEON C++ generates, builds, and runs value tests under qemu for the full
   supported primitive corpus.
2. NEON Rust generates, builds, and runs value tests under qemu for the full
   supported primitive corpus.
3. SVE C++ generates, builds, and runs value tests under qemu for all emitted
   supported primitives.
4. SVE C++ has no true skipped coverage gaps; only the three fixed-lane
   scalable signatures above may remain as `policy_deferred`.
5. The fast non-build gate remains at the known safety-contract baseline, with
   no new failures.

If every item is proven by current command output, mark the active goal
complete. If any item is not proven, keep the goal active and create the next
focused prompt.

## Required Commands

Run SVE C++ full generation/build/value tests:

```bash
PATH=/opt/zig:$PATH PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --output-root ./tslctmp/sve-final-qemu \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "zig c++" \
  --cpp-target aarch64-linux-musl
```

Run NEON C++ and Rust full generation/build/value tests. Use the same
cross-build/qemu configuration already established in the ARM handoff. If the
exact Rust linker/target flags are not obvious, locate them from the current
handoff or build-verifier tests before running.

Run coverage checks:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp \
  --profiles sve \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/sve-final-coverage

PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --backends cpp,rust \
  --profiles neon \
  --coverage \
  --value-test-warnings \
  --output-root ./tslctmp/neon-final-coverage
```

Run the fast gate:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q -p no:cacheprovider -k 'not build' tslc/tests
git diff --check
```

The known baseline failure is:

```text
test_primitive_corpus_safety_covers_direct_unsafe_facts
```

Do not treat it as introduced unless the failure set changes.

## Audit Rules

- Do not claim completion from old chat memory; use current command output.
- Do not count `policy_deferred` SVE fixed-lane signatures as emitted support.
- Do not count true `coverage_gap` skips as complete.
- Do not attempt Rust SVE.
- Do not change renderer/lane-model/value-test architecture during the audit.

## Completion

If all required evidence is green, call `update_goal(status="complete")` and
report the exact validation commands and counts.

If not complete, update `docs/agent/current-redesign-state.md`,
`docs/agent/tslc-vector-query-handoff.md`, and create one focused next prompt
for the remaining blocker.
