# Migrating pre-v1 generated consumers to TSL v1

TSL v1 stabilizes the generated library, not the Python compiler or editor
version. Regenerate from the v1 source/compiler pair, review the generated
`public-api.json`, and update the generated package version to `1.0.0`. Do not
derive the compiler or extension version from that library version.

## 1. Regenerate a deliberate support slice

Choose the exact C++/Rust profiles, primitive families, and scalar types the
application uses. Compare them with the generated
[v1 support contract](tsl-v1-support.md). Stable Rust supports only its listed
x86 profile set; C++ owns the v1 SVE and RVV surfaces. A pre-v1 configuration
that requested every backend/profile combination may now fail instead of
emitting an unusable or misleading combination.

## 2. Use stable entry points

For C++, include `tsl.hpp` and link `tsl::tsl`. Treat physical profile headers,
`detail` namespaces, compiler-selection macros, and implementation structs as
unstable. Select a generated profile with `TSL_PROFILE`; use an explicit value
for cross-compilation.

For Rust, migrate application code toward the opaque root `Simd`/`Mask` facade
or the selected `tsl::profile` surface. Do not select machine profiles with
Cargo features: compile-target `cfg(target_feature)` now selects the profile,
with a generated generic fallback. The optional `runtime-dispatch` feature is
independent.

## 3. Audit every catastrophic precondition

Unsuffixed functions are the direct expert path. They do not clamp indices,
replace divisors, resize ranges, repair alignment, or perform another hidden
sanitization step. This is a contract clarification as well as an API rule:
pre-v1 code that relied on unspecified defensive behavior must be corrected.

Where a complete runtime guard exists, choose the `*_checked` twin. In C++, a
value-producing checked call now has the shape `value = op_checked(..., error)`;
inspect `error` before using `value`, because the failure placeholder is only
initialized storage and has no operation-defined meaning. A void checked call
returns the error directly. No `checked_result<register_type>` aggregate is
introduced, so the API does not impose an aggregate return ABI on vector values.

In Rust, checked calls return `Result`. Unsuffixed functions with an outstanding
catastrophic caller obligation are now `unsafe fn`; either move the call into a
narrow, documented `unsafe` block or use the checked slice/reference form.
Internal `raw_memory` alone is not a public unsafe reason. The public marker
comes from `caller_unsafe`, such as raw-pointer validity or a typed catastrophic
precondition.

Do not mechanically invent a checked twin where none is generated. Mask-layout
loads/stores, deallocation, raw memory copy, and pointer-indexed narrow gather
currently need ownership/layout information that their bare-pointer signatures
cannot prove. Redesign the calling interface or retain a reviewed unsafe call.

## 4. Update algorithms

Range algorithms with cross-range, capacity, selected-index, mask-size, or
overlap obligations expose checked forms. C++ retains an unsuffixed unchecked
overload. Rust retains an unsuffixed unsafe raw-pointer kernel, with descriptive
`*_raw` compatibility aliases where documented, plus safe checked slice forms.
Single-slice total operations may remain safe and have no checked twin.

Use the checked-in [C++ range example](../examples/cpp/range_operator.cpp) and
[Rust range example](../examples/rust/src/bin/range_operator.rs) as the tested
migration patterns.

## 5. Recheck scalable assumptions

Replace uses of compile-time lane counts on runtime-scalable SVE/RVV with the
runtime lane query. Do not reinterpret SVE128/SVE256/SVE512 success as proof for
the scalable `sve` profile. Fixed-array and ordered-width operations listed in
the support contract are intentionally unavailable on runtime-scalable
profiles; select a fixed profile or redesign the data shape.

## 6. Treat implementation state as evidence, not dispatch semantics

If pre-v1 code inferred “native” from a profile or primitive name, switch to the
generated implementation-state query or `tslc analyze`. `composed` and
`fallback` can be semantically supported but have different structural and
performance implications. `unknown` means the compiler cannot prove a stronger
classification, not that the operation is unavailable.

## 7. Raise toolchain and documentation gates

C++ consumers must enable C++17 and use CMake 3.16 or newer when consuming the
generated project. Build the generated headers as ordinary includes with the
application's warning policy. Rust consumers must meet MSRV 1.89 and should run
warnings, Clippy correctness/suspicious, Rustdoc, doctests, and package-content
checks used by the release gate.

Finish migration by compiling and running the checked-in consumer examples,
reviewing every changed declaration in `public-api.json`, and confirming that
`tslc check --strict` and `tslc doctor` pass for the deployed profile.
