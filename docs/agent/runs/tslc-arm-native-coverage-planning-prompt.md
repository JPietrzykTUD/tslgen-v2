# Prompt: ARM Native Coverage Planning

Plan the next ARM coverage slice after fixed-width native NEON codegen,
native register metadata guardrails, and the first C++ NEON QEMU runtime gate.

## Context

The current state has:

- native fixed-width NEON C++ and Rust substrate rendering from typed
  `Extension.vector_register_types` metadata;
- Rust NEON value tests cross-built for `aarch64-unknown-linux-musl` and run
  through `qemu-aarch64`;
- C++ NEON `add` value tests cross-built with
  `/opt/zig/zig c++ -target aarch64-linux-musl` and run by CTest through
  `qemu-aarch64`;
- fixed-width non-x86 extensions without backend register metadata diagnosed at
  lowering;
- broad C++ host-build verification skipping C++ NEON cleanly when plain clang
  lacks an aarch64 C++ sysroot;
- broad all-backend verification currently blocked by Rust NEON native coverage
  gaps when every primitive is included by default;
- SVE still deferred because scalable-vector semantics need a separate design.

## Goal

Create a concrete, minimal plan for expanding ARM native coverage without
turning NEON/SVE names into compiler architecture.

## Questions To Answer

- Which NEON primitives currently emit native C++ and Rust tests under the
  `neon` profile?
- Which NEON selected primitives still fall back, skip, or fail coverage, and
  what typed blocker category explains each one?
- Which blockers are source-data implementation gaps versus compiler support
  gaps?
- Which Rust NEON intrinsic spelling mismatches are source-data issues, such as
  `vcvtqf32_s32` versus the Rust `core::arch::aarch64` spelling?
- Which Rust NEON const-generic shape mismatches are compiler/rendering issues,
  such as lane indices rendered as `usize` where Rust expects `i32`?
- What is the smallest next primitive family to make native and value-tested
  for both C++ and Rust under QEMU?
- Which SVE facts are already modeled, and what minimal scalable-vector design
  question must be answered before enabling SVE emission?

## Scope

- Use existing CLI/verifier knobs; do not add new toolchain plumbing unless the
  inventory proves the current surface is insufficient.
- Keep C++ and Rust parity as an explicit measurement, not an assumption.
- Keep SVE emission disabled unless the plan has a focused scalable-vector
  design slice.
- Do not special-case primitive names in compiler code; primitive-specific work
  belongs in `tsldata` source bodies/tests.

## Evidence To Collect

Run or adapt targeted commands such as:

```bash
PYTHONPATH=tslc/src ZIG_GLOBAL_CACHE_DIR=/tmp/zig-global-cache-tslc ZIG_LOCAL_CACHE_DIR=/tmp/zig-local-cache-tslc python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --profiles neon \
  --backends cpp,rust \
  --output-root /tmp/tslc-arm-neon-inventory \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64 \
  --cpp-compiler "/opt/zig/zig c++" \
  --cpp-target aarch64-linux-musl
```

If the full NEON run is too broad, narrow with `--primitives` and document the
reason.

## Expected Output

- A prioritized ARM coverage plan with one concrete next implementation slice.
- A blocker taxonomy for NEON coverage gaps.
- An explicit SVE/scalable-vector design follow-up if SVE remains out of scope.
- Validation commands for the chosen next slice.
