# Changelog

This changelog describes the generated TSL library. The `tslc` compiler and the
VS Code extension have independent version lines.

## 1.0.0 — release candidate

### Added

- Stable generated C++ and Rust public declaration/reachability manifests.
- Direct unsuffixed operations plus `*_checked` companions for complete,
  representable catastrophic runtime preconditions.
- C++ `precondition_error` output/status APIs and Rust
  `Result<_, PreconditionError>` checked APIs.
- Stable C++ runtime-scalable SVE, fixed SVE128/SVE256/SVE512, and baseline RV64
  Vector 1.0 profiles, with exact exclusions and multi-vector-length tests.
- Stable Rust support for the exact x86 profile set in the generated support
  contract, tested on Rust 1.89 and current stable.
- Coarse `native | composed | fallback | unknown` implementation-state queries
  in both generated languages and matching compiler/editor analysis.
- Complete generated C++ Doxygen and Rustdoc entry points, checked-in compiled
  consumer examples, and machine-generated backend/profile/type support docs.

### Changed

- The generated library package version is `1.0.0`; compiler and editor package
  versions remain independent `0.x` components.
- Release production is single-owner and draft-first, with normalized
  reproducible archives, exact checksums/manifests, and fail-closed native
  evidence requirements for the final tag.
- Unsuffixed calls have an explicit no-hidden-sanitization contract. C++ states
  caller obligations in documentation; Rust exposes an `unsafe fn` exactly when
  a catastrophic obligation remains with the caller.
- C++ checked value operations return the ordinary value type and write a final
  error reference. A failure placeholder must not be consumed.
- Rust profile selection uses compile-target features rather than per-profile
  Cargo features, with an exact generated generic fallback.
- Runtime-scalable vectors use runtime lane counts. Fixed-width compatibility
  profiles remain distinct products.
- The release archive provides one standalone project per C++ profile and one
  combined Rust crate, with a contract-bound bundle index. The monolithic
  all-profile tree remains only an internal documentation and stress reference.

### Explicitly unsupported in v1

- Stable Rust SVE and RVV.
- SVE2, undeclared optional RVV extensions, and RVV LMUL values outside the
  declared baseline profile.
- Fixed-shape callable identities on runtime-scalable profiles when no truthful
  runtime-sized signature exists.
- Checked twins for pointer contracts whose complete capacity, layout,
  provenance, lifetime, or overlap obligations are not representable.

See the [migration guide](docs/migrating-to-tsl-v1.md) and generated
[support contract](docs/tsl-v1-support.md) for the exact surface.
