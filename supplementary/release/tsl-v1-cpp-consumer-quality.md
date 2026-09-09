# TSL v1 C++ consumer-quality evidence

Date: 2026-09-09

## Result

The generated C++ product now has an ordinary-include quality target. It compiles
the full generated wrapper smoke translation unit and a downstream-shaped
`#include <tsl.hpp>` consumer without treating TSL as a system header. The
consumer exercises direct unchecked load/add/store and checked span-based
load/store calls.

The local representative gate passed 49 verifier commands for `scalar`, `avx2`,
runtime-scalable `sve`, `rvv`, and `wasm32-simd128`. AVX2 additionally passed
with Clang 21. The CI matrix applies the same quality gate to every C++ machine
profile with its declared/default compiler, to every non-OneAPI x86 profile with
Clang 21, and to every non-OneAPI x86 profile with MSVC on Windows. OneAPI
profiles use their compiler-role-selected IntelLLVM compiler. Remote MSVC and
full-matrix results remain CI evidence and are not claimed as local runs.

The strict options are:

- GCC, Clang, AppleClang, and IntelLLVM: `-Wall -Wextra -Werror`;
- MSVC: `/W4 /WX`;
- MSVC x86 profile selection: the cumulative `/arch:SSE2`, `/arch:SSE4.2`,
  `/arch:AVX`, `/arch:AVX2`, or `/arch:AVX512` option derived from the typed
  machine-profile features. The supported spellings follow the
  [Microsoft `/arch` reference](https://learn.microsoft.com/en-us/cpp/build/reference/arch-x64?view=msvc-170).

Compiler-vector overlay headers remain separately generated and tested. They
are not part of the stable normal-include contract: the v1 compatibility policy
already excludes physical profile headers and compiler-selection macros.
Consequently, their explicit wide compiler-vector ABI warnings are not hidden
with a system-header or warning-suppression flag and are not counted as this
gate passing.

## Defects removed

The full-header warning audit found and fixed these source or renderer defects:

- unused generated specialization parameters caused by a uniform internal
  `apply` ABI and scalar/target-specific degeneracy;
- unused placeholder locals in `conflict`, `sequence`, and `memory_cp`;
- unsigned `< 0` comparisons in byte-shift implementations;
- signed-only `sign_mask` declarations emitted for unsigned shift paths;
- scalar `set_undef` returning an indeterminate value that Clang diagnosed when
  instantiated; its unspecified value is now a deterministic zero;
- target-only representation types incorrectly participating in public
  `dataparallel::native`/`fixed<N>` inference, which made an AVX2 profile select
  AVX-512;
- a Wasm exception guard that recognized `__wasm__` but not the standard
  `__wasm32__`/`__wasm64__` target macros.

No warning category is suppressed in the stable quality target.

## Static chunk-index contract

Immediate metadata now distinguishes two meanings:

- `value_range` is a finite backend dispatch domain; values outside it may
  still be semantically valid;
- `valid_range` is a source-authored compile-time well-formedness constraint.

`convert_up` and `convert_down` declare
`0..conversion_chunk_count(data, ToBase)`. Lowering resolves that upper bound
from the source and target lane widths. C++ emits a `static_assert` and Rust an
inline const assertion with the stable
`TSL_CONVERSION_CHUNK_INDEX_OUT_OF_RANGE` marker. Authored negative compilation
tests prove an out-of-range index is rejected rather than clamped, wrapped, or
sent through a runtime checked overload.

This is intentionally separate from `*_checked`: the invalid value is a static
template/const-generic program error, not a runtime catastrophic precondition.

## External consumers

`supplementary/ci/verify_generated_consumers.sh` now compiles one identical
checked/unchecked consumer through normal `FetchContent` integration for these
stable architecture families:

| Family | Profile | Compiler used locally | Result |
| --- | --- | --- | --- |
| generic | `scalar` | GCC 15.2 | pass |
| x86 | `avx2` | GCC 15.2 | pass |
| AArch64 scalable | `sve` | AArch64 GCC 15.2 | pass |
| RISC-V vector | `rvv` | RISC-V GCC 15.2 | pass |
| WebAssembly | `wasm32-simd128` | WASI Clang 22.1 | pass |

Native profiles build executables. Cross profiles build object consumers: this
proves parsing, instantiation, and code generation without pretending a foreign
binary was linked or executed on the host. The complete consumer/example script
passed in 42.76 seconds on the local CI image.

## Exact public declarations

The v1 API ratchet no longer hard-codes scalar/AVX2. It derives its scope from
`supplementary/release/tsl-v1-policy.json` and freezes:

- 29 C++ release profiles with 8,015 exact declaration records;
- six Rust release profiles with 7,201 exact declaration records.

The baseline stays semantic and inspectable: it records typed declaration
fields and does not hash rendered C++ or Rust source. Its size is 27 MiB.

## Size and compile-time audit

The measurement used the complete 29-profile C++ release scope, all ten stable
scalar types, and the full primitive corpus in the local CI image.

| Measurement | Result |
| --- | ---: |
| Selected/lowered specializations | 656,395 |
| Generated artifacts | 400 |
| Generation and writing, formatting disabled | 155.87 s |
| Extracted C++ tree | 1,732,168,527 bytes |
| C++ headers | 1,431,175,750 bytes |
| gzip archive of the generated tree | 50,707,257 bytes |
| Full generation plus single-process `clang-format` | exceeded 10 minutes; audit run interrupted |

Clean representative consumer build times, run concurrently from already
configured build trees, were:

| Profile | Wall time |
| --- | ---: |
| `scalar` | 2.03 s |
| `avx2` | 2.65 s |
| `sve` | 2.25 s |
| `rvv` | 2.44 s |
| `wasm32-simd128` | 3.27 s |

The per-consumer compile cost and 50.7 MB compressed delivery are not v1 use or
download blockers. The 1.73 GB extracted all-profile tree and formatter cost are
material packaging risks, however. Slice 15 addresses them without changing
compiler architecture: the single release archive contains a standalone project
per C++ profile and one combined Rust crate, and consumers selectively extract
only their deployment bundle. The full reference tree remains an internal
documentation/stress artifact. A compiler-header deduplication refactor is not
justified for v1: it would change the generated architecture despite the
measured consumer translation units completing in roughly two to three seconds.

The complete Slice 15 package build generated and formatted all 30 deployment
bundles in approximately 29.5 minutes. The deterministic archive was 56,997,715
bytes; its aggregate audit extraction was 2,177,610,277 bytes because common
generated support is intentionally repeated across standalone projects. Normal
C++ extraction is bounded to one 53,080,305–78,546,574-byte profile bundle; the
combined six-profile Rust crate is 192,807,970 bytes. Two independently written
archives were byte-identical. Clean selectively extracted CMake/Cargo consumers
passed, and the packaged `cpp-sve`/`cpp-rvv` showcase passed all six QEMU vector-
length executions. This closes the distribution concern without presenting the
aggregate audit extraction as the installation path.

## Reproduction

```bash
./dev.sh build \
  --backends cpp \
  --profiles scalar,avx2,sve,rvv,wasm32-simd128 \
  --quality \
  --no-format \
  --output-root ./tslctmp/slice9-family-quality

bash supplementary/ci/verify_generated_consumers.sh \
  ./tslctmp/slice9-consumer-root \
  ./tslctmp/slice9-consumers

./dev.sh generate \
  --backends cpp \
  --no-format \
  --output-root ./tslctmp/slice9-audit-noformat
```
