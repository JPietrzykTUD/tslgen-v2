# Prompt: ARM SVE Scalable-Vector Coverage Planning

Plan the next ARM native coverage slice after the broad fixed-width NEON
C++/Rust QEMU value-test pass.

## Context

Current ARM-native evidence:

- native fixed-width NEON register substrates are rendered from typed
  `Extension.vector_register_types` metadata;
- C++ and Rust NEON value tests cross-build and run through QEMU;
- focused NEON C++/Rust coverage now includes `sub`, `mul`, `binary_and`,
  `extract_value`, and `cast`;
- the broad NEON C++/Rust gate generates `8076` specializations, formats
  generated C++/Rust artifacts, passes C++ CTest, passes Rust smoke, and runs
  `1087` Rust value tests through QEMU;
- SVE/scalable-vector emission is still intentionally deferred.

## Goal

Produce a concrete, reviewable plan for enabling the next smallest native ARM
SVE/scalable-vector slice without weakening the existing design principles.

## Questions To Answer

- Which typed facts are missing for scalable-vector support: lane count,
  predicate representation, vector length, register spelling, emulator CPU
  flags, value-test expectations, or something else?
- Which current support-policy checks defer SVE, and are they still the right
  boundary?
- Can an initial SVE slice be primitive-by-primitive like NEON, or does scalable
  vector semantics require a shared typed design first?
- What is the smallest first primitive/profile/backend combination that can be
  generated, built, and run through QEMU?
- Which machine-profile `cpp_flags`, Rust target features, and QEMU CPU flags
  are source/profile-owned rather than renderer-owned?
- How should value-test planning represent scalable lanes without pretending
  they are fixed-width NEON lanes?

## Scope

- Planning only unless the design is already fully determined from current
  typed data.
- Keep fixed-width NEON behavior unchanged.
- Do not enable SVE by adding extension-name branches to renderers.
- Do not invent a broad scalable-vector DSL; prefer one thin, testable slice.
- Do not make tests depend on host ARM hardware; use QEMU where execution is
  required.

## Evidence To Collect

- Inspect `tsldata/extensions` and machine profiles for existing SVE metadata.
- Inspect support-policy deferrals for scalable/vector-bit kinds.
- Probe available local toolchain/QEMU SVE support with tiny generated or hand
  probes only if needed.
- Compare C++ and Rust SVE intrinsic/header/target requirements.
- Identify the first primitive candidate and the exact validation command that
  would prove it.

## Expected Output

- A short implementation plan for the first SVE/scalable-vector slice.
- Any required typed-model or profile-data additions.
- The intended focused validation commands.
- Explicit out-of-scope items and stop conditions.
- Updated current-state/handoff docs, and an ADR if the planning creates a new
  architectural decision.
