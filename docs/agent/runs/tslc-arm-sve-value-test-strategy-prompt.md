# Prompt: C++ SVE Value-Test Strategy Slice

Plan and implement the next small C++ SVE slice after the scalable native
registration substrate.

## Context

Current state:

- the `sve` machine profile exists with profile-owned `-mcpu=a64fx` and
  `qemu-aarch64 -cpu a64fx` metadata;
- C++ `simd<T, sve>` registrations are rendered from source-owned `sv*`
  register metadata and `svbool_t` mask/imask metadata;
- `add<sve, si32>` selects, lowers, closes its `mask_true<sve, si32>`
  dependency, build-verifies with Zig for `aarch64-linux-musl`, and CTest runs
  through QEMU;
- scalable extensions defer `s[]` / lane-list signatures and leave
  `vector::length` unresolved instead of manufacturing a fixed lane count;
- Rust SVE remains unsupported because stable Rust stdarch does not expose the
  required SVE symbols in this environment.

Important caveat:

`TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh test --profiles
sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target
aarch64-linux-musl` passes, but the generated `values_sve.cpp` does not yet
contain true `tsl::simd<..., tsl::sve>` value cases. The SVE profile is
smoke/build/runtime verified, not value-complete.

## Goal

Define and implement the smallest honest C++ SVE value-test strategy for one
primitive family, starting with `add`, without pretending SVE has a compile-time
fixed lane count and without adding primitive-name or extension-name classifier
branches to production compiler code.

## Questions To Answer

- What typed fact should represent the concrete runtime lane count used by a
  generated SVE value test under QEMU?
- Can the C++ SVE value-test renderer initialize and inspect SVE registers
  through source-owned load/store primitives, `svcnt*`, or a tiny helper
  without enabling general `array_for<simd<T, sve>>`?
- Should SVE value tests be profile-owned by a test vector-length policy, by
  extension metadata, or by a verifier/runtime capability?
- Which currently emitted SVE primitives are safe to value-test first:
  `add`, masked `add`, `mask_true`, load/store helpers, or a smaller dependency
  pair?
- How should unsupported authored SVE value-test shapes be surfaced as typed
  coverage diagnostics rather than silent skips?

## Scope

- C++ only.
- Start with one primitive family and one profile (`sve`) unless the typed
  helper is naturally reusable.
- Keep Rust SVE unsupported.
- Keep fixed-width and sized-generic value-test behavior unchanged.
- Do not make `array_for<Vec>` depend on `sizeof(sv*)` or use `vector::length`
  for scalable vectors unless the value is a typed runtime fact.
- Do not special-case source primitive names in production compiler/render code.

## Evidence Commands

Start with the current substrate checks:

```bash
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'simd<[^>]+sve|svadd|svptrue' /tmp/tslc-sve-add/cpp/tests/values_sve.cpp
```

After implementation, prove that `values_sve.cpp` contains at least one true
SVE value case and that it runs through QEMU:

```bash
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add-values ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
rg -n 'simd<[^>]+sve|svadd|svptrue' /tmp/tslc-sve-add-values/cpp/tests/values_sve.cpp
./dev.sh ratchet
git diff --check
```

Also run focused Python tests for value-test planning/rendering and SVE
profile rendering.

## Expected Output

- One real C++ SVE value-test path for `add` or a narrower dependency primitive.
- Typed coverage/diagnostics for SVE cases still not value-testable.
- Updated tests and docs.
- A next prompt for broadening SVE primitive coverage or reviewing the
  scalable value-test design.
