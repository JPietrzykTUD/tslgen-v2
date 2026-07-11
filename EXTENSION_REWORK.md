# Extension Rework Plan

## Purpose

Clarify how `tslc` models extension availability before adding target families
such as WASM SIMD, oneAPI FPGA, and compiler-builtin SIMD paths.

The current `lscpu_flags` name suggests "minimum CPU features required by an
extension", but that is not what the selector uses it for. The rework should
make the existing behavior explicit, preserve per-implementation feature
gating, and avoid introducing broad hardware/toolchain taxonomies until a real
validation decision needs them.

## Current Model

The relevant current pieces are:

- `tsldata/extensions/extension.tsl` defines extension records, inheritance,
  backend metadata, and `lscpu_flags`.
- `supplementary/buildsystem/machine_profiles.json` defines named generation
  profiles and their available `features`.
- `tslc/src/tslc/catalog/machine_profiles.py` promotes those profiles into
  `MachineProfile.features`.
- `tslc/src/tslc/select/selector.py` selects implementations whose body
  `requires [...]` are a subset of the profile features.
- The selector also uses `Extension.lscpu_flags` only to activate inherited
  extension variants such as `avx2_vl` and `sse_vl`.
- `BackendExtensionMetadata.generation_support` is currently descriptive
  metadata. It is promoted into the catalog but is not a selector/lowering
  contract.

That means body-level `requires` are the real feature gate for emitted
implementations. `lscpu_flags` is currently a variant activation hook, not a
complete extension requirement.

## Problems To Fix

1. `lscpu_flags` is misleading.

   It sounds like all CPU features required by an extension. In practice it is
   used only to decide whether a derived extension variant should become an
   emitted candidate.

2. Extension-level "minimum CPU features" is the wrong primary model.

   Some extensions contain bodies with different requirements. For example, an
   `avx2` substrate can contain floating-point operations that only require
   `avx`, while integer operations require `avx2`. The exact requirement
   belongs on the implementation body.

3. `inherits` currently carries too much implied behavior.

   For variants such as `avx2_vl`, inheritance means "reuse the parent bodies"
   and, once active, "replace/supersede the parent extension". Those are related
   but distinct concepts.

4. Profile `features` are too CPU-flavored in naming and documentation.

   The set should be understood as target features available to compilation and
   selection. Those target features may be x86 ISA features, AArch64 features,
   WASM features such as `simd128`, or other compile-time target capabilities.

5. Toolchain and runtime contracts are not modeled yet.

   That is acceptable for the current compiler, but oneAPI FPGA and
   compiler-builtin SIMD will eventually need abstract build/runtime
   requirements. Those should not be forced into `lscpu_flags`.

## Settled Vocabulary

Use the following mental model:

- **Extension**: a SIMD substrate or implementation family. It owns facts such
  as vector shape, mask policy, intrinsic style, backend imports, inheritance,
  and variant activation.
- **Implementation `requires`**: the exact target features required by one
  implementation body.
- **Profile features**: the target capabilities available for one generated
  profile. These are not limited to physical CPU flags.
- **Activation**: the condition under which an extension variant becomes a
  candidate extension for a profile.
- **Supersession**: the explicit statement that an active variant replaces one
  or more other extensions in emitted output.
- **Toolchain/run contract**: a future abstract requirement on compiler,
  backend, runtime, or device availability. Actual executable paths remain in
  build verifier configuration, CLI configuration, devcontainer setup, or CI.

## Target Design

### Extension Activation

Replace the `lscpu_flags` concept with an activation condition:

```text
Extension:
  active_when:
    target_features [...]
  inherits ...
  supersedes [...]
```

`active_when.target_features` means:

> This extension variant may participate in selection when the active profile
> has these target features.

This is not a replacement for implementation `requires`. It only decides whether
the extension itself is a candidate. Individual implementation bodies still
select through their own `requires`.

### Supersession

Make supersession explicit:

```text
Extension:
  supersedes ["avx2"]
```

For example, `avx2_vl` should not merely rely on `inherits "avx2"` to imply
that it replaces `avx2` when active. It should say that directly.

This keeps three facts separate:

- `inherits`: where fallback bodies or metadata are reused from.
- `active_when`: when this extension variant exists for a profile.
- `supersedes`: which extensions should be hidden or replaced when this variant
  is active.

### Implementation Requirements

Keep implementation body requirements as the precise feature gate:

```text
implementation:
  requires [avx2]
```

For now, keep `requires [...]` as shorthand for target features. Do not add
`cpu.` prefixes or structured feature namespaces until there is a concrete
collision or validation decision that needs them.

If a future structured form becomes necessary, prefer an additive shape such as:

```text
requires:
  target_features [avx2, avx512vl]
```

Do not model PCI, devices, runtimes, or local compiler executables inside
implementation `requires`.

### Profile Features

Treat profile `features` as target features, not as `lscpu` output.

Examples:

- x86: `sse`, `sse2`, `avx`, `avx2`, `avx512f`, `avx512vl`
- AArch64: `neon`
- WASM: `simd128`

The current field may remain named `features` in data for compatibility, but
documentation, diagnostics, and new code should call them target features where
possible.

### Toolchain And Runtime Contracts

Do not add a broad taxonomy yet.

Avoid adding general-purpose fields such as:

- `compiler_features`
- `compiler_kinds`
- `runtime_kinds`
- `device_kinds`
- `interconnect_kinds`
- `pci_features`

Add a new contract only when a compiler stage or verifier must make a concrete
decision from it.

Expected future triggers:

- **oneAPI FPGA**: likely needs a C++ compiler contract such as `icpx` or a
  oneAPI FPGA compile capability, because ordinary `g++` cannot build it.
- **compiler-builtin SIMD**: may need a compiler capability such as GNU vector
  extensions or Clang `ext_vector_type`, but only once selection/build
  validation needs to distinguish compilers.
- **WASM value tests**: need a runner/runtime path such as Wasmtime, but this
  belongs in verifier/build configuration rather than extension activation.

Actual executable locations such as `icpx`, `clang++`, `rustc`, WASI SDK paths,
or `wasmtime` paths should stay in build configuration, devcontainer setup, CI,
or CLI/runtime configuration.

## Source Ownership

`tsldata/extensions/extension.tsl` should own:

- extension identity and family;
- inheritance;
- variant activation;
- variant supersession;
- backend metadata;
- future abstract extension-owned compile/run contracts, once needed.

Primitive implementation data should own:

- exact body-level `requires [...]`;
- body text and TSIL regions;
- per-backend implementation availability.

Machine/profile data should own:

- named generation profiles;
- target family;
- available target features;
- compile flags/triples/default backend settings for that profile.

Target-family data should own:

- which extension families are valid for which target families;
- target-specific build flag policy;
- future target-family defaults such as WASM target triples or runner kind, if
  those become part of compiler configuration.

Verifier, devcontainer, CI, and CLI configuration should own:

- concrete compiler executable paths;
- concrete runtime executable paths;
- local installation details;
- optional skip/gate behavior for unavailable tools.

## Migration Slices

### 1. Rename The Concept

Introduce an `active_when.target_features` model in the catalog domain.

During migration, either:

- accept old `lscpu_flags` as an input alias and promote it to
  `active_when.target_features`; or
- migrate all source data in one change and remove `lscpu_flags` immediately.

The lower-risk path is to support the alias temporarily and emit a validation
warning or maintenance diagnostic if old data remains.

### 2. Make Supersession Explicit

Add `supersedes [...]` to derived variants that currently rely on selector
behavior implied by `inherits` plus `lscpu_flags`.

Initial expected cases:

- `avx2_vl` supersedes `avx2` when active.
- `sse_vl` supersedes `sse` or the relevant scalar-width SSE variant according
  to current emitted behavior.

Confirm the exact superseded IDs against current selector output before editing
data.

### 3. Update Selector Semantics

Adjust extension emission so it:

1. starts from extensions allowed by the profile/target-family support policy;
2. activates variants whose `active_when.target_features` are satisfied;
3. applies explicit `supersedes`;
4. continues selecting implementation bodies through body-level `requires`.

Base extensions should not need `active_when`. They remain available through the
existing target-family/profile support policy, and their bodies are selected by
`requires`.

### 4. Update Diagnostics And Explainers

Use "target features" in messages and maintenance output where the compiler is
talking about profile capabilities or implementation requirements.

Avoid presenting activation requirements as "minimum CPU features for an
extension".

Useful wording:

- "required target features"
- "profile target features"
- "extension activation features"
- "implementation requirements"

### 5. Audit `generation_support`

Do not use `generation_support` as part of this rework unless its behavior is
defined.

Choose one of these follow-up outcomes:

- remove it if it is obsolete descriptive metadata;
- keep it explicitly documented as inert metadata;
- rename and wire it to a real behavior, such as
  `requires_generated_extensions`, if a backend genuinely needs helper
  extension artifacts emitted.

This should be a separate slice from activation/supersession unless tests show
the two are already coupled.

## WASM SIMD Implications

WASM SIMD does not require `lscpu_flags`.

The first WASM SIMD slice should use:

- a WASM target family/profile;
- profile target feature `simd128`;
- C++ and/or Rust implementations whose bodies use `requires [simd128]`;
- backend/build configuration that compiles to `wasm32` with SIMD enabled;
- Wasmtime/WASI-based value-test execution.

Do not emit WAT as part of this plan. The generated C++/Rust code should compile
to WebAssembly through Clang/WASI SDK or Rust `wasm32-wasip1`.

Base WASM SIMD extensions do not need `active_when` initially. Body-level
`requires [simd128]` is sufficient unless a later selector/explain use case
needs extension-level candidate pruning.

## oneAPI FPGA Implications

oneAPI FPGA should not be represented as CPU features.

The first oneAPI FPGA support slice should decide whether the compiler or build
verifier must reject ordinary compilers such as `g++`. If yes, add the smallest
abstract contract that supports that decision.

Possible future shape:

```text
Extension:
  compile_when:
    cpp:
      compiler_kind icpx
```

or:

```text
Extension:
  compile_requires:
    cpp_capabilities [oneapi_fpga]
```

Do not add this until the build verifier or selector consumes it. Actual `icpx`
paths stay outside `extension.tsl`.

Runtime/device availability for FPGA boards, PCIe devices, simulators, or
emulators should be modeled as run/verification requirements only if generated
tests need to make that decision.

## Compiler-Builtin SIMD Implementation

The first compiler-builtin SIMD slice is implemented as three C++-only Clang
overlays: `clang_v128`, `clang_v256`, and `clang_v512`.

These are not machine profiles and do not supersede hardware extensions. They
are routed through the universal `compiler_builtin` extension family, selected
alongside the ordinary profile extensions, and emitted into a dedicated
`tsl_<profile>_clang.hpp` header. Generated CMake exposes
`tsl::<profile>_clang` only for Clang/AppleClang and defines
`TSL_ENABLE_CLANG`; the ordinary `tsl::<profile>` target and profile header stay
compiler-independent.

The smallest consumed backend facts are:

```text
cpp:
  header_group "clang"
  compiler_ids [Clang, AppleClang]
  dataparallel_inference false
  compile_guards:
    clang_compiler:
      macro "__clang__"
      equals 1
```

`header_group` owns opt-in artifact separation, while `compiler_ids` gates the
generated CMake target. `compile_guards` provides the header-level diagnostic.
`dataparallel_inference false` is essential: Clang
overlays must never become `dataparallel::native` or
`dataparallel::simd_for_t<fixed<N>, T>`, because the latter is their escape
hatch to the hardware-backed profile extension.

Primitive bodies use `vector::fixed` when a compiler-vector operation needs a
hardware fallback. Selection resolves that query to the best emitted concrete
extension of the same width so dependency closure can prove the callee exists;
the C++ backend renders the public facade:

```cpp
tsl::dataparallel::simd_for_t<
    tsl::dataparallel::fixed<N>, DataType>
```

Bodies explicitly `bit_cast` between the Clang register and the facade's
register before calling the ordinary primitive. If the profile has no emitted
fixed-width implementation at that width, lowering records a coverage skip
instead of generating an incomplete facade use. Mask fallback remains outside
this first slice because equal-sized mask objects do not imply equal mask
semantics.

This delivers the compiler decision without introducing general-purpose
`compiler_features`, runtime, device, or executable-path taxonomies.

## Test Plan

Add focused tests for the rework:

- catalog parsing/promotion accepts `active_when.target_features`;
- old `lscpu_flags` data is rejected, warned, or aliased according to the
  chosen migration path;
- selector activates `avx2_vl` only when the profile has `avx2`, `avx512f`, and
  `avx512vl`;
- ordinary `avx2` profiles do not emit `avx2_vl`;
- supersession hides/replaces the intended parent extension only when the
  variant is active;
- implementation body `requires` still gate selected bodies independently of
  extension activation;
- base extensions without `active_when` remain available through existing
  target-family/profile support;
- diagnostics and explain/dump output use target-feature terminology.

Useful existing test areas:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_render_model.py tslc/tests/test_generation_conditionals.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_output_format.py
```

Run the full Python suite once the migration is complete:

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

Run generated build/value gates only for slices that touch generated project
layout, backend codegen, verifier behavior, or value-test execution:

```bash
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
```

## Non-Goals

- Do not implement WASM SIMD in this rework.
- Do not add a direct WAT backend.
- Do not replace implementation body `requires` with extension-level feature
  gates.
- Do not add CPU/PCI/compiler/runtime/device namespaces until a concrete
  validation decision needs them.
- Do not make local tool paths part of `extension.tsl`.
- Do not couple `generation_support` cleanup to activation unless its behavior
  is first defined.
