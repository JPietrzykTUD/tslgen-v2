# TSL v1 Rust surface and quality evidence

Date: 2026-09-09

## Result

The stable Rust v1 surface is the generated opaque facade, root re-exports, and
profile callables for `sse`, `sse2`, `sse3`, `avx`, `avx2`, and `knl`. The
semantic public-API baseline freezes 7,201 exact declaration records for those
six profiles and their shared fallback scope. The profile set is read from the
release policy by CI rather than repeated in workflow code.

Stable Rust SVE and RVV are explicitly unsupported in v1. Their release target
scopes are C++-only, the Rust release profile selection contains neither
family, and the release contract names `stable Rust SVE` and `stable Rust RVV`
among its exclusions. This avoids a
facade that appears portable but depends on private LLVM intrinsics or local
inline assembly.

## API and safety boundary

The exact declaration manifest records typed callable identities instead of
hashing rendered Rust. The stable root surface remains the opaque `Simd` and
`Mask` facade plus its reviewed re-exports; implementation traits and physical
profile modules remain implementation detail.

Unchecked functions are `unsafe fn` only when the caller owns a catastrophic
validity obligation. Raw memory inside an implementation is not sufficient to
make a public function unsafe. Raw pointers, unchecked lane indices, invalid
integer division operands, and analogous caller obligations can require
`unsafe`; a complete compiler-owned guard additionally produces the safe,
idiomatic `Result<_, PreconditionError>` `*_checked` twin.

Checked admission is decided for the complete Rust callable group. During this
slice, the full KNL build exposed a `mod` trait that declared a delegated
precondition hook although its i8/i16 implementations could not provide the
required `equal` dependency. The planner now carries one typed checked-condition
fact across policy selection and rendering. Consequently, the group emits
neither the hook nor `mod_checked` unless every specialization can implement the
guard; it does not advertise a checked function that fails to compile.

## Toolchain and quality gates

The generated manifest declares `rust-version = "1.89"`. CI installs and runs
both Rust 1.89.0 and the current stable toolchain over the exact release-profile
set. Each profile is checked with:

- compiler warnings denied, including `invalid-value`, `private-interfaces`,
  and `private-bounds`;
- Clippy `correctness` and `suspicious` groups denied;
- Rustdoc warnings, missing public documentation, broken intra-doc links, and
  bare URLs denied;
- generated compile-failure contracts and build/value tests; and
- Cargo package-content listing.

Rustdoc examples are profile-neutral. The verifier builds documentation for
every profile and executes doctests once with the least demanding host-capable
profile (`sse` for the SDE-backed x86 release set). It schedules no host doctest
for a pure cross-target profile.

Local full-corpus runs generated 41,874 specializations and 126 artifacts. Both
Rust 1.89.0 and current stable 1.98.0 completed the 93-command six-profile
build/lint/Rustdoc/value matrix with no failed command. The full Rust 1.89 run
used Intel SDE 10.8.0 and passed all generated suites, including 2,367 AVX,
2,543 AVX2, 2,706 KNL, and 2,240 value cases for each of SSE, SSE2, and SSE3.

The full generated facade's doctest gate succeeded on each toolchain: two
complete crate examples executed. At the time, 3,524 context-free API call
fragments were also labeled as ignored examples even though they only
illustrated parameterized call syntax. Slice 12 relabels those fragments as
non-executable `Call form` text, so ignored snippets no longer masquerade as
tested examples. After the final compatibility fixes, focused current-stable
and Rust 1.89 runs each passed all 13 scheduled commands and 412 SSE generated
value cases, including the doctest command.

Two MSRV defects were removed rather than suppressed globally:

- Rust 1.89 treats `__cpuid` as unsafe while current stable treats it as safe.
  The internal CPU-identity asset uses one documented compatibility block with
  a statement-local `allow(unused_unsafe)`.
- Rust 1.89 Clippy rejected target-feature helpers that repeated a generic bound
  inline and in a `where` clause. Typed generic rendering now places those
  bounds in exactly one `where` clause.

## Packaging and downstream consumption

An external Cargo project successfully consumed the generated crate as a path
dependency and exercised the facade, checked/unchecked arithmetic, masks,
memory, conversions, operators, and runtime dispatch. `cargo package` produced
one `.crate`; a second clean project consumed the unpacked archive successfully.

Cargo's package-owned file listing is identical before and after a local
documentation artifact is added under the generated crate. The standalone
consumer script applies the same before/after check, removes its exact probe on
success or failure, and passed together with all generated C++/Rust examples.
The crate contains `Cargo.toml`, `README.md`, the root/facade sources, and the
declared generated sources; it does not capture compiler sources or local docs.

## Reproduction

```bash
./dev.sh test \
  --backends rust \
  --profiles sse,sse2,sse3,avx,avx2,knl \
  --quality \
  --no-format \
  --output-root ./tslctmp/rust-release-stable

RUSTUP_TOOLCHAIN=1.89.0 ./dev.sh test \
  --backends rust \
  --profiles sse,sse2,sse3,avx,avx2,knl \
  --quality \
  --no-format \
  --output-root ./tslctmp/rust-release-msrv

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  -k 'rust_path_dependency_consumer_builds or rust_warning_gates'
```
