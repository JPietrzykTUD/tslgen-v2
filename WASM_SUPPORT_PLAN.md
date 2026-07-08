# WASM SIMD Support Plan

This plan captures the agreed path for adding WebAssembly SIMD support to
`tslc`/`tsldata`.

The intended design is **not** a direct WAT backend. `tslc` should keep emitting
C++ and Rust source, and those generated projects should be compiled to
WebAssembly by Clang/WASI SDK or Rust. WAT is only an optional inspection format
after a `.wasm` binary has been produced.

## Settled Decisions

- Add WebAssembly SIMD as a target/profile/extension capability for the existing
  C++ and Rust backends.
- Do not make `tslc` emit WAT in the first implementation.
- Use WASI for value-test executables, because it gives normal process-style
  behavior: `_start`, stdout/stderr, arguments, and exit status.
- Use `wasm32-wasip1` for Rust value tests.
- Use WASI SDK `clang++` for C++ value tests.
- Use `wasmtime` as the initial runtime for executing generated `.wasm` value
  test binaries.
- Treat missing Wasm toolchains/runtimes as skip-safe verifier conditions, like
  missing SDE or QEMU today.
- Model SIMD availability with profile `features`, not with host `lscpu`
  detection.

## Non-Goals

- No direct WebAssembly text/binary backend in this slice.
- No browser or JavaScript harness in the first slice.
- No `wasm32-unknown-unknown` value-test runner in the first slice.

## Current Model Notes

`MachineProfile.features` is the real capability set used by selection and
build rendering. An implementation body is usable only when its applicable
`requires [...]` flags are a subset of the selected profile's features.

Extension variants use `active_when.target_features` and explicit `supersedes`
for profile-level activation. Base extensions such as `wasm128` do not need
`active_when`; they self-gate through implementation `requires` clauses.

For Wasm SIMD:

- Add a profile feature token named `simd128`.
- Put `requires [simd128]` on Wasm SIMD implementation bodies.
- Do not interpret `simd128` as runtime CPU probing. It is a compile/profile
  capability token.

## Why This Is Not A Big Architecture Change

Wasm SIMD is fixed-width 128-bit SIMD, much like NEON from the compiler model's
point of view. The fixed width is not the hard part.

The direct-WAT path would be architectural because TSIL bodies are currently a
recursive sequence of raw target-language text plus typed TSIL regions. Raw
fragments are C++/Rust-like source and are passed through, not parsed as a full
target-language AST. WAT has a substantially different stack-machine syntax, so
direct WAT output would require promoting much more expression, statement,
memory, local, and control-flow syntax into typed TSIL.

The C++/Rust-to-Wasm path avoids that problem. The required work is ordinary
target capability, intrinsic spelling, build configuration, and value-test
runner support.

## Data Changes

### Target Families

Update `tsldata/detail/target_families.tsl`.

Add a Wasm extension family:

```tsl
known_extension_families [scalar, generic_like, x86, arm, cuda, wasm]
```

Add a profile family. Exact field names may need to evolve during
implementation, but the intended facts are:

```tsl
profile_families:
  wasm32:
    extension_families [wasm]
    runner_kinds [wasmtime]
    sort_order 30
    cpp_feature_flags true
    rust_target_features true
    rust_target "wasm32-wasip1"
```

Notes:

- `cpp_feature_flags true` is useful because profile feature `simd128` naturally
  becomes `-msimd128`.
- `rust_target_features true` is useful because profile feature `simd128`
  naturally becomes `+simd128`.
- The verifier vocabulary uses `runner_kinds` because Wasmtime is a runtime, not
  a CPU emulator.
- Existing C++ cross-target verifier code has a hardcoded aarch64/Linux branch.
  Do not reuse that as-is for Wasm. Add a Wasm/WASI-specific CMake/toolchain
  path.

### Machine Profile

Update `supplementary/buildsystem/machine_profiles.json`.

Add:

```json
{
  "wasm32": [
    {
      "name": "wasm32-simd128",
      "target_features": "simd128",
      "cpp_flags": [],
      "runner": {"kind": "wasmtime", "profile": "default"}
    }
  ]
}
```

The `profile` value is not semantically important for Wasmtime. It exists only
because the current runner model keeps one shape for SDE, QEMU, and Wasmtime.

### Extension

Update `tsldata/extensions/extension.tsl`.

Add a fixed-width extension similar in shape to NEON:

```tsl
extension wasm128:
  vendor "webassembly"
  extension_name "wasm128"
  family "wasm"
  intrinsic_style "wasm"
  vector_bits 128
  native_sort_order 800
  autodetect false
  mask_repr "lane_bitmask"
  mask_width "lanes"
  mask_vector_loadable false
  runtime_lanes false
  default_test_target true
  cpp:
    supported true
    headers ["wasm_simd128.h"]
    test_suite_name "TslWasm128"
    test_support_header "tests/scalar_support.hpp"
  rust:
    supported true
    type_name "Wasm128"
    arch_module "wasm32"
    generation_support []
  vector_register_types:
    ?i?:
      cpp "v128_t"
      rust "core::arch::wasm32::v128"
    f32:
      cpp "v128_t"
      rust "core::arch::wasm32::v128"
    f64:
      cpp "v128_t"
      rust "core::arch::wasm32::v128"
  intrinsic_compose:
    prefix:
      cpp "wasm_"
      rust "core::arch::wasm32::"
    suffix:
      by_type:
        f32 "f32x4"
        f64 "f64x2"
        si8 "i8x16"
        ui8 "i8x16"
        si16 "i16x8"
        ui16 "i16x8"
        si32 "i32x4"
        ui32 "i32x4"
        si64 "i64x2"
        ui64 "i64x2"
  mask_type_policy:
    kind "lane_bitmask"
    width "lanes"
  integral_mask_type_policy:
    kind "lane_bitmask"
    width "lanes"
```

The exact `mask_repr`/policy may need adjustment once comparison and mask logic
are implemented. For the first vertical slice, focus on value vectors,
load/store, and arithmetic.

## Intrinsic Translation

Existing x86/NEON composition mostly renders:

```text
prefix + operation + "_" + suffix
```

Examples:

- `_mm256_add_epi32`
- `vaddq_s32`

Wasm SIMD is lane-shape-first:

```text
prefix + lane_shape + "_" + operation
```

Examples:

- C++: `wasm_i32x4_add`
- Rust: `core::arch::wasm32::i32x4_add`

Add a typed intrinsic composition path keyed by `intrinsic_style "wasm"` or an
equivalent explicit composition policy. Do not special-case raw strings in
templates.

The first implementation can reuse `intrinsic_compose.suffix.by_type` as the
lane shape, but the backend dialect must place it before the operation.

Also account for untyped `v128` operations:

- C++ examples: `wasm_v128_load`, `wasm_v128_store`
- Rust examples: verify exact names in `core::arch::wasm32` during
  implementation.

Do not guess names while implementing. Verify each C++ and Rust intrinsic name
against the toolchain headers/docs.

## Initial Primitive Slice

Start with a small vertical slice. The goal is not broad coverage; it is to make
one Wasm SIMD profile compile, lower, render, build, and run value tests.

Suggested first primitive set:

- `set_zero`
- `set1`
- `load`
- `store`
- `from_array`
- `to_array`
- `add`
- `sub`

Suggested first type set:

- `si32`
- `ui32`
- `f32`

Then expand to:

- `si8`, `ui8`, `si16`, `ui16`
- `si64`, `ui64`
- `f64`
- comparisons and masks
- shifts
- conversions
- min/max and other arithmetic

Every Wasm implementation body should use:

```tsl
requires [simd128]
```

Prefer typed TSIL regions such as `intrin<...>`, `call<primitive=...>`,
`complete(...)`, and existing memory/value helpers. Avoid adding raw string
rewrites.

## Backend And Render Changes

Expected implementation areas:

- `tslc/src/tslc/backend/translation_common.py`
- `tslc/src/tslc/backend/cpp_translation.py`
- `tslc/src/tslc/backend/rust_translation.py`
- `tslc/src/tslc/backend/target_capability.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/render/rust_project.py`
- `tslc/src/tslc/support_policy.py` and support-policy views if needed

Add support for:

- `wasm` extension family routing.
- Rust arch module `wasm32`.
- C++ header inclusion for `wasm_simd128.h`.
- Rust imports from `core::arch::wasm32`.
- C++ profile flags including `-msimd128`.
- Rust target features including `+simd128`.
- Rust target `wasm32-wasip1`.
- Wasm fixed 128-bit register registration for all supported scalar types.

Keep the existing global devcontainer `CC="zig cc"` and `CXX="zig c++"` behavior
for native/cross workflows. The Wasm verifier should explicitly select
`/opt/wasi-sdk/bin/clang++` or accept it through build-verifier config.

## C++ WASI Build Support

The current C++ verifier can cross-compile aarch64 by setting:

- `CMAKE_SYSTEM_NAME=Linux`
- `CMAKE_SYSTEM_PROCESSOR=aarch64`
- `CMAKE_CXX_COMPILER_TARGET=...`

That path is not correct for Wasm/WASI.

Add a WASI-specific CMake path. Viable options:

1. Use `/opt/wasi-sdk/bin/clang++` as `CXX`, with `-msimd128`, and set CMake
   cross-compiling behavior so configure does not try to execute Wasm binaries
   natively.
2. Use the WASI SDK CMake toolchain file, e.g.
   `/opt/wasi-sdk/share/cmake/wasi-sdk-p1.cmake`, if present in the installed
   SDK version.

Either way, the generated verifier should build `.wasm` executables and run
value tests through Wasmtime.

## Rust WASI Build Support

Use:

```text
--target wasm32-wasip1
RUSTFLAGS="-C target-feature=+simd128"
```

The existing Rust verifier already has a follow-up flow for cross-target tests:
build test binaries with `--no-run --message-format=json`, discover the produced
executables, then run them through a runner prefix. Extend this to support
Wasmtime as the runner.

Avoid `wasm32-unknown-unknown` initially. Rust's own documentation recommends
`wasm32-wasip1` for test-like compatibility because `unknown-unknown` lacks a
normal host interface for stdout, filesystem, process exit, and many `std`
operations.

## Value Test Runner

Add Wasmtime as a configured runtime.

Minimal model:

- Add `wasmtime_path` to `BuildVerifierConfig`.
- Accept `VerifyRunner(kind="wasmtime", profile="default")`.
- Add `wasmtime` to configured runner kinds when `wasmtime_path` is set.
- Make `runner_prefix(...)` return `(wasmtime_path,)` for Wasmtime.
- Make C++ CTest/CMake use Wasmtime for cross-running `.wasm` tests.
- Make Rust follow-up test commands run `wasmtime <test_binary.wasm>`.

Value-test code should keep `v128` values inside the Wasm module. Tests should
materialize vectors from scalar arrays, call generated TSL functions, convert or
store results back to scalar arrays inside the module, compare internally, and
return a normal process exit code.

## Devcontainer Toolchain

The active Dockerfile is `.devcontainer/Dockerfile`.

Add these args near the existing Zig args:

```dockerfile
ARG WASI_SDK_VERSION=33
ARG WASMTIME_VERSION=45.0.2
```

Add WASI SDK after the Zig install block:

```dockerfile
# Install WASI SDK: clang/clang++ for C/C++ -> wasm32-wasip1.
RUN set -eux; \
    curl -L "https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-${WASI_SDK_VERSION}/wasi-sdk-${WASI_SDK_VERSION}.0-x86_64-linux.tar.gz" \
      -o /tmp/wasi-sdk.tar.gz; \
    mkdir -p /opt; \
    tar -xzf /tmp/wasi-sdk.tar.gz -C /opt; \
    mv "/opt/wasi-sdk-${WASI_SDK_VERSION}.0-x86_64-linux" /opt/wasi-sdk; \
    rm /tmp/wasi-sdk.tar.gz; \
    /opt/wasi-sdk/bin/clang++ --version
```

Change the existing PATH setup to include WASI SDK:

```dockerfile
ENV WASI_SDK_PATH=/opt/wasi-sdk
ENV PATH="/opt/venv/bin:/opt/zig:/opt/wasi-sdk/bin:${CARGO_HOME}/bin:${PATH}"
```

Add `wasm32-wasip1` to the existing Rust target list:

```dockerfile
    rustup target add \
      x86_64-unknown-linux-gnu \
      aarch64-unknown-linux-gnu \
      x86_64-unknown-linux-musl \
      aarch64-unknown-linux-musl \
      wasm32-wasip1; \
```

Add Wasmtime after the Rust install block:

```dockerfile
# Install Wasmtime runtime for executing generated .wasm value-test binaries.
RUN set -eux; \
    curl -L "https://github.com/bytecodealliance/wasmtime/releases/download/v${WASMTIME_VERSION}/wasmtime-v${WASMTIME_VERSION}-x86_64-linux.tar.xz" \
      -o /tmp/wasmtime.tar.xz; \
    tar -xJf /tmp/wasmtime.tar.xz -C /tmp; \
    install -m 0755 "/tmp/wasmtime-v${WASMTIME_VERSION}-x86_64-linux/wasmtime" /usr/local/bin/wasmtime; \
    rm -rf "/tmp/wasmtime-v${WASMTIME_VERSION}-x86_64-linux" /tmp/wasmtime.tar.xz; \
    wasmtime --version
```

The verifier should use:

```text
C++ compiler: /opt/wasi-sdk/bin/clang++
C++ flags:    -msimd128
Rust target:  wasm32-wasip1
Rust flags:   -C target-feature=+simd128
Runner:       wasmtime
```

## Implementation Slices

### Slice 1: Toolchain Metadata And Selection

- Add `wasm` extension family and `wasm32` profile family.
- Add `wasm32-simd128` machine profile with feature `simd128`.
- Add `wasm128` extension metadata.
- Add tests proving the profile routes only Wasm extensions plus universal
  generic/scalar families as intended.
- Add tests proving `requires [simd128]` selects Wasm bodies only for
  `wasm32-simd128`.

### Slice 2: Intrinsic Dialect

- Add lane-shape-first intrinsic composition for `intrinsic_style "wasm"`.
- Add C++ and Rust translation tests for representative names:
  `wasm_i32x4_add`, `wasm_f32x4_add`, Rust `i32x4_add`, Rust `f32x4_add`.
- Add diagnostics for unsupported Wasm intrinsic composition cases.

### Slice 3: First Primitive Coverage

- Add Wasm implementation bodies for the initial primitive/type slice.
- Generate C++ and Rust for `wasm32-simd128`.
- Confirm no unrelated profiles regress.

### Slice 4: Build Verification

- Add Wasm/WASI C++ build support.
- Add Rust `wasm32-wasip1` target support if the existing target machinery is
  not enough.
- Add `wasmtime_path` or equivalent verifier config.
- Add skip-safe diagnostics for missing WASI SDK, Rust target, or Wasmtime.

### Slice 5: Value Tests

- Plan and render value tests for `wasm128`.
- Run generated C++ `.wasm` value tests through Wasmtime.
- Run generated Rust `.wasm` value tests through Wasmtime.
- Keep failures as warnings initially if following the existing
  report-then-promote pattern for generated value tests.

### Slice 6: Expand Coverage

- Add more primitive families and types.
- Add comparison and mask semantics once `wasm128` mask representation is proven.
- Add coverage ratchet updates only when behavior is stable.

## Validation Commands

Run focused Python checks first:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_support_policy.py tslc/tests/test_backend_target_capability.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_output_format.py
```

Run full Python logic checks before review:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

After the Wasm generation slice exists, use a small generated smoke set:

```bash
./dev.sh generate \
  --primitives add,set_zero,set1,load,store,from_array,to_array \
  --profiles wasm32-simd128 \
  --types si32,ui32,f32 \
  --backends cpp,rust \
  --output-root tslctmp/wasm-simd-smoke \
  --coverage \
  --no-format
```

After verifier support exists, add build/value-test commands that explicitly
use:

```text
cpp compiler = /opt/wasi-sdk/bin/clang++
wasm runtime = wasmtime
rust target  = wasm32-wasip1
```

The exact `dev.sh` flags should be added with the verifier implementation if
they do not already exist.

## Risks And Checks

- **C++ CMake cross-target handling:** current cross support is aarch64-shaped.
  Wasm needs its own path.
- **Intrinsic naming:** Wasm uses lane-shape-first names. Do not force it into
  the x86/NEON suffix-after-op model.
- **Masks:** Wasm comparisons produce vector masks, but TSL mask policies and
  integral-mask helpers need proof through focused tests before broad coverage.
- **Runtime availability:** Wasmtime is a runtime, not CPU emulation. Missing
  runtime should skip value execution cleanly.
- **Rust target behavior:** prefer `wasm32-wasip1`; avoid
  `wasm32-unknown-unknown` until there is a custom runner/harness.
- **Feature semantics:** a generated `.wasm` containing SIMD instructions
  requires a runtime that supports SIMD. There is no native-style CPU dispatch
  fallback inside one Wasm module.

## Useful References

- WebAssembly SIMD reference:
  <https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/SIMD>
- WebAssembly `v128` value type:
  <https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/Value_types/v128>
- Rust `core::arch::wasm32` intrinsics:
  <https://doc.rust-lang.org/core/arch/wasm32/>
- Rust `wasm32-wasip1` target:
  <https://doc.rust-lang.org/rustc/platform-support/wasm32-wasip1.html>
- Wasmtime CLI:
  <https://docs.wasmtime.dev/cli.html>
- WASI SDK:
  <https://github.com/WebAssembly/wasi-sdk>
