# TSL v1 generated-library user guide

TSL v1.0.0 is the generated C++/Rust SIMD library. The `tslc` compiler and the
VS Code extension are independently versioned tools and may remain on `0.x`
while generating the stable library product.

The machine-generated [support contract](tsl-v1-support.md) is authoritative
for the exact current backend/profile/type matrix, callable families, checked
companions, scalable-shape exclusions, and implementation-state meanings. This
guide explains how to consume that contract; it does not maintain a second
profile list.

## Choose a generated bundle

The release tarball contains standalone deployment bundles rather than one
monolithic all-profile project. Each C++ profile has its own bundle because a
C++ application selects one deployment profile. The Rust release profiles stay
together in one crate because Rust selects among them from compile-target
features. The root `.tsl-release-bundles.json` lists the exact bundle paths,
profiles, extracted sizes, and generated artifact-manifest digests; those rows
are derived from the machine-generated release contract rather than maintained
as another profile list.

The v1 contract provides C++ across every listed supported profile, including
runtime-scalable SVE, fixed SVE128/SVE256/SVE512, and baseline RV64 Vector 1.0.
Stable Rust is intentionally narrower and is limited to the six x86 profiles in
the generated contract. Stable Rust SVE and RVV, SVE2, optional RVV extensions,
and undeclared RVV LMULs are not part of v1.

Every matrix row supports the ten stable scalar element types. That does not
mean every callable accepts every type: a primitive's source-owned type group,
result-target constraints, and the reviewed exact exclusions still apply.

## Consume the release archive

The v1 generated-library tarball is a source package, not a system-prefix
installer. Verify it with the published `SHA256SUMS`, inspect the manifest, and
extract only the selected bundle. For example:

```bash
tar -xOf tsl-generated-v1.0.0.tar.gz \
  tsl-generated-1.0.0/.tsl-release-bundles.json | jq .
tar -xzf tsl-generated-v1.0.0.tar.gz \
  tsl-generated-1.0.0/bundles/cpp-avx2
```

Extracting every bundle is supported for auditing, but recreates the measured
all-profile stress footprint and is not the normal installation path.

For C++, point CMake `FetchContent` at the extracted `cpp/` directory and link
the stable `tsl::tsl` target:

```cmake
include(FetchContent)
set(TSL_PROFILE avx2 CACHE STRING "Generated TSL profile" FORCE)
set(TSL_BUILD_TESTS OFF CACHE BOOL "Generated TSL tests" FORCE)
FetchContent_Declare(
  tsl
  SOURCE_DIR "/path/to/tsl-generated-1.0.0/bundles/cpp-avx2/cpp"
)
FetchContent_MakeAvailable(tsl)
target_link_libraries(my_target PRIVATE tsl::tsl)
```

For Rust, use the extracted crate as a path dependency. Profile selection comes
from Rust compile-target features as described below; do not add a profile-named
Cargo feature.

```toml
[dependencies]
tsl = { path = "/path/to/tsl-generated-1.0.0/bundles/rust-release/rust" }
```

The release package workflow performs these steps from a fresh extraction and
builds/runs independent C++ and Rust consumers. Moving the extracted directory
after CMake configuration or Cargo resolution requires reconfiguration, as for
any source/path dependency.

## C++ consumption and profile selection

The stable C++ entry point is `#include <tsl.hpp>` and the stable namespace is
`tsl`. Link a generated CMake project through `tsl::tsl`; do not include a
physical `tsl_<profile>.hpp` header or depend on compiler-selection macros.
The checked-in [C++ examples](../examples/cpp/README.md) are compiled and run by
the generated-package CI workflow.

The generated headers require C++17. The supplied CMake project requires CMake
3.16 or newer. `TSL_PROFILE=auto` runtime-probes the generated, ungated profiles
when building natively. During cross-compilation it cannot execute a probe and
uses the generated fallback, so set `-DTSL_PROFILE=<profile>` explicitly. Gated
accelerator modes and their toolchain probes must also be selected explicitly.

The exact release profiles are warning-clean as ordinary includes under their
CI-assigned compilers. The locally reproduced representative matrix uses GCC
15.2 for scalar, AVX2, SVE, and RVV; Clang 21 for AVX2; and WASI Clang 22.1 for
WebAssembly. Windows MSVC and IntelLLVM/OneAPI coverage remains remote CI
evidence. These are verified release toolchains, not a promise that every older
compiler is supported; see the [C++ quality evidence](../supplementary/release/tsl-v1-cpp-consumer-quality.md).

## Rust consumption and profile selection

The generated crate uses Rust edition 2021 and declares Rust 1.89 as its MSRV.
Its stable surface is the opaque root `Simd`/`Mask` facade, reviewed root
re-exports, and the selected `profile` primitive surface. The public
`tsl_core`/`tsl_algorithm` substrate remains reachable for generated signatures
but is not a representation-stable ABI.

Normal builds select the strongest generated profile using compile-target
`cfg(target_feature)` conditions and fall back to the generated generic
implementation. Machine profiles are not Cargo features. The optional
`runtime-dispatch` feature is a separate `std`-based choice. The checked-in
[Rust examples](../examples/rust/README.md) are compiled and run in package CI;
generated crate examples are executable doctests. See the
[Rust quality evidence](../supplementary/release/tsl-v1-rust-quality.md) for the
MSRV/current-stable matrix.

## Ordinary and checked calls

An unsuffixed operation performs the requested work without hidden validation,
clamping, substitution, or fallback values. The caller must uphold documented
preconditions. A `*_checked` twin exists only when TSL can validate every
catastrophic runtime precondition before the ordinary operation and its side
effects.

For C++ value operations, the checked call returns the ordinary value type and
writes a final `tsl::precondition_error&`. A failure does not invoke the
ordinary operation. Its returned object is initialized but has no TSL-defined
semantic value; inspect the error before consuming it. Void checked operations
return `precondition_error` directly. C++ expresses remaining object-lifetime,
provenance, range, alignment, and concurrency obligations in documentation.

Rust uses `Result<T, PreconditionError>` or `Result<(), PreconditionError>` for
checked calls. An unsuffixed call is `unsafe fn` only when the caller owns an
outstanding catastrophic obligation. Internal raw-memory staging does not make
a public function unsafe by itself. Raw-pointer validity, an unchecked dynamic
index, invalid integer division input, or another typed caller obligation can.

Some pointer APIs intentionally have no checked twin. A bare pointer cannot
prove allocation provenance, object lifetime, layout, capacity, overlap, or
concurrency. The generated reference and checked-API census state each omission
rather than offering a partial check under a reassuring name.

## Scalable shapes

Runtime-scalable `sve` and `rvv` derive lane counts from the active vector type;
they do not invent a compile-time width. Fixed-shape callables whose public
contract requires `lanes<s>`, a fixed `s[]`, ordered fixed register widths, or a
fixed mask window are excluded when no truthful runtime-sized form exists.
SVE128/SVE256/SVE512 are separate fixed-width compatibility profiles and do not
prove vector-length-agnostic behavior. Each such compilation mode emits one
fixed-SVE width, so operations that require a distinct smaller or larger
same-family register have no applicable type pair in that profile. Base-width
integral-mask extraction/insertion remains available and rebuilds the native
predicate through reviewed semantic fallback code.

The exact excluded callable identities and edge scalar types are generated in
the [support contract](tsl-v1-support.md). QEMU multi-vector-length correctness
is recorded in the [scalable verification evidence](../supplementary/release/tsl-v1-scalable-verification.md);
native SVE and RVV/CHORYS attestations remain final-release gates.

## Implementation state

`native`, `composed`, `fallback`, and `unknown` describe implementation
structure, not semantic availability or a performance guarantee. Generated C++
and Rust expose the same final post-dependency-closure state; `tslc analyze` and
`tslc explain` report it for an exact specialization. Release gates reject
unknown state and unreviewed accelerated fallback where the support policy
requires stronger evidence.

Use state to inspect and qualify an implementation, then measure on the target
machine before making a performance decision. The exact meanings and query
surface are frozen in the
[implementation-awareness contract](../supplementary/release/tsl-v1-implementation-awareness.md).

## Unsupported combinations and diagnostics

An unsupported profile/backend pair, source type constraint, fixed-shape
request on a runtime-scalable vector, missing target compiler, or unavailable
checked guard is reported explicitly. It is not repaired by silently selecting
a different public operation. Use `tslc check --strict`, `tslc doctor`, and
`tslc explain` before packaging a generated slice; the
[command-line guide](tslc-cli.md) documents the exact commands.

The generated C++ Doxygen reference and Rustdoc are the declaration-level API
references. `public-api.json` in each generated backend tree is the scope-exact,
machine-readable declaration and reachability manifest.
