# TSLc Native NEON Codegen Planning Prompt

Plan the next ARM slice after the accepted emulator-verifier work.

## Context

The ARM/QEMU verifier slice is accepted with follow-ups. It added typed
emulator metadata, QEMU CLI/API wiring, Rust aarch64 musl execution through
`qemu-aarch64`, and C++ CMake cross-emulator wiring. The Rust proof exercised
the NEON machine profile, but native ARM extension emission is still deferred:
the support policy does not emit the `arm` extension family, and C++/Rust
renderers do not yet register `neon` as a native vector substrate.

## Goal

Create a concrete implementation plan for a narrow native NEON codegen
substrate slice.

## Design Principles To Preserve

- `tslc` must stay primitive- and extension-agnostic. Do not special-case
  primitive names such as `add`, or extension names beyond typed extension
  metadata needed to register a selected extension.
- Native register spellings must come from `tsldata/extensions/extension.tsl`
  `vector_register_types`, promoted into typed catalog metadata.
- Renderers may format already-decided extension/register facts; they must not
  rediscover semantic facts or inspect primitive bodies.
- Enable `arm` in support policy only after the typed NEON substrate can render
  valid C++ and Rust registrations.
- Keep SVE out of this slice unless planning proves a shared typed boundary is
  required for both NEON and SVE. NEON is fixed-width; SVE is scalable and likely
  needs its own design.

## Planning Questions

1. What typed catalog model should hold extension-owned vector register
   spellings for C++ and Rust?
2. How should C++ register `tsl::simd<T, tsl::neon>` using those spellings?
3. How should Rust register `Simd<T, Neon>` and import/use
   `core::arch::aarch64` support?
4. Which tiny primitive/profile proof should be first? Prefer `add` on
   `profiles=["neon"]`.
5. Which tests prove that native NEON emitted, rather than only fallback/generic
   coverage?
6. What should be skipped or documented until a clang-compatible aarch64 C++
   sysroot is available?

## Expected Output

Produce a plan with:

- scope and out-of-scope work;
- typed model/render/support-policy changes;
- test plan;
- validation commands;
- expected follow-ups;
- risks or design questions that should block implementation.
