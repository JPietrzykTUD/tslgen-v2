# Adding An Extension To `tsldata`

This guide is the human checklist for adding a target extension or target
profile to TSL. It is written from the `wasm128` WebAssembly SIMD slice, but the
steps are general.

The design goal is simple: a new extension should be mostly source data plus
focused typed compiler support when the current compiler vocabulary is missing a
real concept. Avoid extension-name branches in templates or primitive lowering.

## 1. Name The Target Contract

Before editing, write down the target contract in plain language.

- What is the extension name, for example `wasm128`, `neon`, or `avx2`?
- Which extension family owns it, for example `wasm`, `arm`, or `x86`?
- Which machine profile selects it, for example `wasm32-simd128`?
- Which feature tokens must an implementation require, such as `simd128`?
- Is the vector width fixed, scalable, inherited, or derived from another
  extension?
- Which C++ and Rust targets, flags, headers, architecture modules, and runtime
  execution runners are needed?
- Which primitive and type slice is small enough to prove the vertical path?

For WebAssembly SIMD, the first contract was: fixed-width `wasm128`, selected by
profile `wasm32-simd128`, gated by feature `simd128`, compiled through the
existing C++ and Rust backends to `wasm32-wasip1`, and run through Wasmtime.

## 2. Add The Target Family

Start in `tsldata/detail/target_families.tsl`.

Add the extension family to `known_extension_families`:

```tsl
known_extension_families [scalar, generic_like, x86, arm, cuda, wasm]
```

Then add or update the profile family:

```tsl
profile_families:
  wasm32:
    extension_families [wasm]
    runner_kinds [wasmtime]
    sort_order 30
    cpp_feature_flags true
    cpp_target "wasm32-wasip1"
    rust_target_features true
    rust_target "wasm32-wasip1"
```

Keep this file about routing and capabilities. Do not put primitive selection
rules, intrinsic spellings, or build-system commands here.

## 3. Add The Machine Profile

Update `supplementary/buildsystem/machine_profiles.json`.

For WebAssembly SIMD, the profile is:

```json
"wasm32": [
  {
    "name": "wasm32-simd128",
    "target_features": "simd128",
    "cpp_flags": [],
    "runner": {"kind": "wasmtime", "profile": "default"}
  }
]
```

`target_features` is the selector capability set. Implementation bodies with
`requires [simd128]` are usable only when this profile is selected.

Use profile features for compile/profile capabilities. Do not treat Wasm
`simd128` as host CPU probing.

## 4. Add Extension Metadata

Add the extension block in `tsldata/extensions/extension.tsl`.

For a fixed-width SIMD extension, define:

- `extension_name` and `family`;
- `intrinsic_style` when intrinsic spelling differs from existing dialects;
- vector width and sort order;
- backend support metadata;
- register type mappings for every supported scalar type;
- intrinsic composition prefix/suffix data;
- mask policy, even if mask primitives are not in the first slice.

The WebAssembly SIMD shape is:

```tsl
extension wasm128:
  vendor "webassembly"
  extension_name "wasm128"
  family "wasm"
  intrinsic_style "wasm"
  vector_bits 128
  native_sort_order 800
  autodetect false
  lscpu_flags []
  mask_repr "lane_bitmask"
  mask_width "lanes"
  mask_vector_loadable false
  runtime_lanes false
  default_test_target true
  cpp:
    supported true
    headers ["wasm_simd128.h"]
  rust:
    supported true
    type_name "Wasm128"
    arch_module "wasm32"
```

Then add explicit `vector_register_types`. For `wasm128`, each supported base
type uses `v128_t` in C++ and `core::arch::wasm32::v128` in Rust. Prefer
explicit mappings when native registration or render logic expects concrete
scalar tags.

## 5. Add Intrinsic Dialect Support Only If Needed

Most extensions can use existing intrinsic composition. If the target has a new
spelling rule, add a typed dialect path in compiler code.

WebAssembly SIMD is lane-shape-first:

```text
wasm_i32x4_add
core::arch::wasm32::i32x4_add
```

That differs from the existing operation-first shape:

```text
_mm256_add_epi32
```

The right boundary is `tslc/src/tslc/backend/translation_common.py`, keyed by
`intrinsic_style "wasm"` or an equivalent typed policy. Do not special-case
Wasm intrinsic names in templates, primitive lowering, or raw string rewrites.

Verify exact intrinsic names against toolchain headers or official target docs.
For `wasm128`, untyped memory intrinsics use names such as `wasm_v128_load` and
`wasm_v128_store` in C++.

## 6. Add The First Primitive Slice

Pick a small vertical slice that proves selection, lowering, rendering, build,
and value-test execution.

For `wasm128`, start with:

- `set_zero`
- `set1`
- `load`
- `store`
- `from_array`
- `to_array`
- `add`
- `sub`

Start with a small type set:

- `si32`
- `ui32`
- `f32`

Every implementation body for the extension should declare the profile feature
requirements:

```tsl
requires [simd128]
```

Prefer typed TSIL regions:

- `intrin<...>`
- `call<primitive=...>(...)`
- `complete(...)`
- `cast<...>(...)`
- existing memory/value helpers

Avoid backend-specific raw string ladders. If a source form cannot be expressed,
add the missing typed TSIL concept instead of hiding behavior in templates.

## 7. Add Verifier And Runner Support

If the extension needs a non-native target or runtime, keep verifier support
skip-safe and injectable.

For WebAssembly SIMD:

- add `wasmtime_path` to verifier configuration;
- allow machine-profile runner kind `wasmtime`;
- route C++ CTest execution through Wasmtime for `.wasm` binaries;
- use a WASI CMake/cross-target path for C++;
- use Rust target `wasm32-wasip1`;
- set Rust target features with `RUSTFLAGS="-C target-feature=+simd128"`;
- skip cleanly when WASI SDK, the Rust target, or Wasmtime is missing.

The default devcontainer toolchain installs WASI SDK and Wasmtime, but verifier
config should still accept explicit paths for local and CI setups.

## 8. Add Focused Tests

Test the new extension in layers.

Catalog and selection tests should prove:

- the machine profile loads with the expected family, features, and runner;
- the target family routes only intended extension families plus universal
  families;
- `requires [...]` selects the new bodies only for capable profiles.

Backend tests should prove:

- C++ headers and Rust architecture module metadata are promoted correctly;
- register type spelling is correct;
- intrinsic composition produces representative target names.

Lowering tests should prove:

- each primitive in the first slice lowers for C++ and Rust;
- memory and unsafe intrinsics keep the correct safety shape;
- helper calls such as `from_array` and `to_array` compose through existing
  primitives.

Verifier tests should prove:

- C++ cross-target configuration uses the right CMake target settings;
- Rust uses the right target and target features;
- value tests run through the configured runner;
- missing runner/toolchain paths become deterministic diagnostics or skips.

## 9. Generate A Smoke Project

Generate a small project before broadening coverage:

```bash
PYTHONPATH=tslc/src python -m tslc.cli \
  --sources tsldata \
  --machine-profiles supplementary/buildsystem/machine_profiles.json \
  --primitives add,sub,set1,set_zero,load,store,from_array,to_array \
  --profiles wasm32-simd128 \
  --types si32,ui32,f32 \
  --backends cpp,rust \
  --output-root ./tslctmp/wasm-simd-smoke \
  --no-format
```

Inspect the generated output for the new target facts:

- C++ includes the extension header, for example `wasm_simd128.h`;
- C++ compile flags include target features, for example `-msimd128`;
- Rust uses the expected target feature attribute;
- generated profile headers register the new native SIMD type;
- intrinsic names match the target dialect.

When the toolchain is installed, run generated builds and value tests through
the verifier with the appropriate runner configured.

## 10. Update Tooling And Documentation

If the target needs toolchain setup, update `.devcontainer/Dockerfile` or CI
helpers in the same slice.

For WebAssembly SIMD, the container needs:

- WASI SDK for C++ `wasm32-wasip1` builds;
- Rust target `wasm32-wasip1`;
- Wasmtime for executing generated `.wasm` value-test binaries.

Do not make tests depend unconditionally on host-specific hardware, installed
runtimes, or network access. Hardware and runner detection must be injectable,
skippable, or clearly gated.

## 11. Verify In Layers

Run focused Python checks first:

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q \
  tslc/tests/test_catalog.py \
  tslc/tests/test_backend_target_capability.py \
  tslc/tests/test_select_and_lower.py \
  tslc/tests/test_build_verify_config.py
git diff --check
```

Then run the full logic suite:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
```

Use `./tslctmp/...` for normal generated output. If that path is not writable,
create or choose another workspace-local scratch path, for example
`./tslc-wasm-smoke`, and avoid committing generated output.

## 12. Expand Coverage Deliberately

After the first vertical slice is stable, add more types and primitive families.

For `wasm128`, the next natural expansions are:

- `si8`, `ui8`, `si16`, `ui16`;
- `si64`, `ui64`, `f64`;
- comparisons and masks;
- shifts;
- conversions;
- min/max and other arithmetic.

Only update coverage ratchets or baselines once generated behavior is stable and
the build/value-test path is reliable.

Before finishing, check:

- Could the next similar extension be added mostly through `tsldata`?
- Did any Python code branch on an extension name instead of a typed capability?
- Are unsupported cases represented as diagnostics or explicit deferred support?
- Are templates only formatting already-decided render values?
- Are generated outputs deterministic across runs?
- Does the extension have source data, profile data, tests, toolchain support,
  and a smoke-generation command?
