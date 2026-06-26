# Prompt: ARM NEON Rust Intrinsic Spelling Coverage

Plan and execute the next small ARM native coverage slice after the Rust
lane-index const-generic fix for `extract_value`.

## Context

Current ARM native coverage evidence:

- native fixed-width NEON register substrates are rendered from typed
  `Extension.vector_register_types` metadata;
- C++ and Rust NEON value tests can cross-build and run through QEMU;
- focused C++/Rust NEON QEMU value-test coverage passes for `add`, `sub`,
  `mul`, `binary_and`, and `extract_value`;
- Rust `generic_params {kind int}` now render as `i32`, so
  `vgetq_lane_*::<Index>` receives the lane type Rust stdarch expects;
- SVE remains out of scope until scalable-vector semantics are designed.

Broad all-backend verification still reaches Rust NEON native coverage gaps
when every primitive is included. The remaining representative blocker is
native Rust NEON intrinsic spelling mismatch, especially conversion-style
functions whose C++ spelling does not match `core::arch::aarch64`.

## Goal

Raise native ARM coverage by making the next smallest failing NEON primitive
family compile and pass C++/Rust value tests through QEMU, without turning NEON
or primitive names into compiler architecture.

## Questions To Answer

- Which currently failing NEON primitive family is the smallest next spelling
  blocker after `extract_value`?
- Is the mismatch a source-data backend spelling problem, a typed intrinsic
  composition rule gap, or an unsupported Rust stdarch intrinsic?
- Can the fix live in `tsldata` backend spelling/source bodies, or does it need
  a small typed compiler rule?
- Does the fix preserve C++ behavior and existing x86/Rust generated-build
  coverage?
- Which focused C++/Rust QEMU value-test command proves the new primitive
  family is now covered?

## Scope

- Work primitive-by-primitive.
- Keep SVE disabled/deferred.
- Do not add primitive-name classifier branches to production compiler code.
- Do not add local Rust intrinsic spelling tables in renderers.
- Prefer source-owned backend spelling data and existing typed TSIL mechanisms.
- Use existing verifier knobs: `--qemu-aarch64`, `--cpp-compiler`, and
  `--cpp-target`.

## Evidence To Collect

Start from targeted probes, for example:

```bash
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --profiles neon \
  --primitives CURRENT_ACTIVE_PRIMITIVE \
  --backends cpp,rust \
  --output-root /tmp/tslc-arm-neon-CURRENT_ACTIVE_PRIMITIVE \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "/opt/zig/zig c++" \
  --cpp-target aarch64-linux-musl
```

Also run the focused regression gate after extending it if the new primitive is
stable enough for a persistent test.

## Expected Output

- One additional native NEON primitive family covered for both C++ and Rust.
- A short blocker taxonomy entry for the next remaining ARM gap.
- Focused validation commands and results.
- Updated handoff/current-state docs and, if a typed design decision changes,
  an ADR entry.
