# TSL v1 Rust surface and quality evidence

Date: 2026-09-13

## Result

The stable Rust v1 surface is the generated opaque facade, root re-exports, and
profile callables for the scalar fallback and every ungated Rust-capable
machine profile: 16 x86 profiles from `sse` through `zen5`, plus `neon` and
`wasm32-simd128`. The semantic public-API baseline freezes 12,951 exact
declaration records for those 19 profiles and their shared target fallback.
The profile set is read from the release policy by CI rather than repeated in
workflow code, and a release ratchet fails when any eligible profile is omitted.

Stable Rust SVE and RVV are explicitly unsupported in v1. Their release target
scopes are C++-only, the Rust release profile selection contains neither
family, and the release contract names `stable Rust SVE` and `stable Rust RVV`
among its exclusions. This avoids a
facade that appears portable but depends on private LLVM intrinsics or local
inline assembly.

## Compile-time profile selection

Every machine profile remains a separate generated Rust module. The crate root
guards each module declaration and its `profile` re-export with mutually
exclusive `#[cfg(...)]` predicates; there is no runtime branch and no
`build.rs` selector. Strict target-feature supersets precede their subsets.
When two feature sets are incomparable, the planner uses the reviewed
`backend_selection_priority.rust` value from the machine-profile data. Every
consumer of profile order reuses this one typed plan.

Input order is not selection policy: reversing the requested profiles produces
the same plan and artifact digests. Generated tests cover exact Cannon Lake,
exact Cascade Lake, their artificial feature union, stronger Ice Lake, the
fallback, AArch64 Neon, and Wasm. Equal target predicates remain an error;
auto-detect-gated normal/OneAPI pairs therefore stay in separate generated CI
scopes rather than using priority to make one unreachable.

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

Local full-corpus runs generated 162,830 specializations and 550 artifacts.
Both Rust 1.89.0 and current stable 1.98.0 completed the same 284-command
19-profile build/lint/Rustdoc/value matrix with no failed command, verifier
diagnostic, or skip. Each run included 19 warning-denied checks, 19 Rustdoc
builds, 19 Clippy checks, 114 expected-failure contracts, all generated value
suites through Intel SDE 10.8.0, QEMU AArch64 10.2.1, and Wasmtime 45.0.2, one
doctest command, and one Cargo package-content listing.

The value-test planner still reports four explicit
`TSL-VALUE-TEST-UNSUPPORTED-CASE` shapes for AVX-512 integral-mask insertion
and extraction on applicable profiles. Those authored cases are not silently
counted as executed; closing that typed test-shape gap remains separate from
the profile-selection and release-scope change.

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
memory, conversions, operators, and runtime dispatch. For the expanded release,
both Cargo 1.89.0 and 1.98.0 packaged the combined crate successfully with
`--no-verify`: 437 files, 924.6 MiB uncompressed and 18.3 MiB compressed.

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
  --profiles scalar,sse,sse2,sse3,avx,avx2,knl,kml,skylake,cannonlake,cascadelake,cooperlake,icelake_rockerlake,tigerlake,zen4,sapphire_emerald_granite_rapids,zen5,neon,wasm32-simd128 \
  --quality \
  --no-format \
  --output-root ./tslctmp/rust-release-stable

RUSTUP_TOOLCHAIN=1.89.0 ./dev.sh test \
  --backends rust \
  --profiles scalar,sse,sse2,sse3,avx,avx2,knl,kml,skylake,cannonlake,cascadelake,cooperlake,icelake_rockerlake,tigerlake,zen4,sapphire_emerald_granite_rapids,zen5,neon,wasm32-simd128 \
  --quality \
  --no-format \
  --output-root ./tslctmp/rust-release-msrv

PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds \
  tslc/tests/test_build_verify.py \
  -k 'rust_path_dependency_consumer_builds or rust_warning_gates'
```
