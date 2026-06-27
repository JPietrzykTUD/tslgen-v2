# Prompt: C++ SVE Scalable-Vector Substrate Slice

Implement the first native SVE coverage slice after the broad fixed-width NEON
C++/Rust QEMU pass and the SVE planning decision in ADR-103.

## Context

Current evidence:

- SVE source data exists in `tsldata/extensions/extension.tsl` with
  `vector_bits "scalable"`, C++ register spellings (`svint32_t`, etc.),
  `svbool_t` mask metadata, and `rust supported false`;
- `./dev.sh explain --primitive add --profile neon --type si32 --backend cpp
  --extension sve` reports SVE is not emitted for the NEON profile;
- `./dev.sh explain --primitive add --profile sve --type si32 --backend cpp`
  reports no `sve` machine profile exists;
- `./dev.sh dump --stage catalog --primitive add --format text` shows SVE
  `add` bodies already exist in source data;
- C++ SVE probes compile with `/opt/zig/zig c++ -target aarch64-linux-musl`
  using SVE-capable CPUs such as `-mcpu=a64fx` or `-mcpu=neoverse_v1`;
- a tiny C++ SVE `svcntw()` binary runs under `/usr/bin/qemu-aarch64`;
- Rust SVE remains unsupported in this environment because stable stdarch does
  not expose SVE symbols such as `svbool_t`, `svint32_t`, or `svadd_s32_x`.

## Goal

Enable the smallest C++-only SVE scalable-vector substrate that can select,
lower, render, build, and preferably run one primitive family, starting with
`add<sve, si32>`, without treating SVE as a fixed-width vector and without
adding primitive-name or extension-name renderer branches.

## Scope

- Add an SVE machine profile with profile-owned C++ flags and QEMU metadata.
- Add explicit support-policy capability for C++ scalable extensions.
- Keep Rust SVE unsupported for this slice.
- Register C++ `simd<T, sve>` from source-owned SVE register/mask metadata.
- Avoid fixed-lane assumptions for SVE registration, masks, arrays, alignment,
  and `vector::length`.
- Start with `add` and only broaden if the substrate boundary is proven by that
  primitive.

## Out Of Scope

- Rust SVE code generation.
- Broad SVE primitive coverage.
- General scalable-vector DSL machinery.
- Renderer-side primitive or extension classifiers.
- Pretending SVE value tests have the same fixed lane model as NEON.

## Implementation Questions

- What typed lowered/render fact distinguishes fixed native vectors, sized
  generic vectors, and scalable native vectors?
- How should C++ `simd<T, sve>::array_type` or test helper array projection be
  represented if no fixed lane count exists?
- Does the first slice build-only/smoke-compile SVE, or can it run value tests
  using one concrete QEMU vector length?
- Where should SVE C++ flags live in `machine_profiles.json`, and which QEMU
  CPU profile should be used?
- Which diagnostics should fire if a scalable-vector primitive asks for an
  unsupported fixed-lane query?

## Evidence Commands

Start with pure evidence:

```bash
./dev.sh explain --primitive add --profile neon --type si32 --backend cpp --extension sve
./dev.sh dump --stage catalog --primitive add --format text
./dev.sh ratchet
```

After implementation, prove the narrow slice with commands shaped like:

```bash
./dev.sh explain --primitive add --profile sve --type si32 --backend cpp --extension sve
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh generate --profiles sve --primitives add
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh build --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
```

If value tests are supported in the same slice, add:

```bash
TSLC_BACKENDS=cpp TSLC_OUTPUT_ROOT=/tmp/tslc-sve-add ./dev.sh test --profiles sve --primitives add --cpp-compiler "/opt/zig/zig c++" --cpp-target aarch64-linux-musl
```

Also run focused Python tests and `git diff --check`.

## Expected Output

- A C++ SVE `add` slice that either build-verifies or has an explicit
  diagnostic explaining the remaining value-test blocker.
- Updated tests for SVE profile/support-policy/render behavior.
- Updated handoff/current-state docs and a next prompt.
- No regression in the ratchet baseline.
