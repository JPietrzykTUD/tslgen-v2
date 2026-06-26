# Prompt: C++ NEON Runtime Verification Planning

You are planning the next ARM verification slice after native fixed-width NEON
codegen and the native register metadata guardrail.

## Context

Rust NEON value tests already cross-build for `aarch64-unknown-linux-musl` and
run through `qemu-aarch64`. C++ NEON artifacts render native
`tsl::simd<T, tsl::neon>` substrates and `<arm_neon.h>`, but C++ runtime
verification is still blocked in this environment by the lack of a
clang-compatible aarch64 C++ sysroot/standard library.

## Goal

Produce a concrete, minimal plan for making C++ NEON generated value tests
cross-compile and run through QEMU without hiding sysroot/toolchain assumptions
inside lowering, rendering, or tests.

## Questions To Answer

- Which aarch64 C++ compiler/sysroot options are already available in the
  workspace?
- Can `clang++ --target=aarch64-linux-gnu` compile a trivial program including
  standard library headers such as `<array>`?
- If no sysroot is available, what exact package/container/setup requirement is
  needed?
- Should CLI/API expose a sysroot flag, compiler flag passthrough, or rely on
  environment/toolchain configuration?
- How should `BuildVerifierConfig` carry this without making profile metadata
  local-machine-specific?

## Scope

- Inspect current verifier and CMake cross-compile configuration.
- Propose the smallest typed config surface needed for a C++ aarch64 sysroot,
  if one is required.
- Keep Rust QEMU behavior unchanged.
- Keep native NEON codegen semantics unchanged.
- Keep SVE and broader ARM primitive coverage out of scope.

## Validation To Plan

The eventual implementation should prove:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --profiles neon \
  --primitives add \
  --backends cpp \
  --output-root /tmp/tslc-cpp-neon-qemu \
  --test \
  --value-test-warnings \
  --qemu-aarch64 /usr/bin/qemu-aarch64
```

The expected end state is C++ CTest running the generated aarch64 NEON test
binary through QEMU. If the sysroot is unavailable, the planning pass should
stop with an explicit environment requirement rather than adding speculative
plumbing.
