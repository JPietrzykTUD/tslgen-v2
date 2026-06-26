# TSLc ARM Emulator Verification Review Prompt

You are reviewing the ARM/QEMU value-test verification slice for `tslc`.

## Scope

Review the changes that generalize value-test emulator metadata from the
previous SDE-only path to typed verifier metadata that can represent both Intel
SDE and `qemu-aarch64`.

Primary files:

- `supplementary/buildsystem/machine_profiles.json`
- `tslc/src/tslc/catalog/machine_profiles.py`
- `tslc/src/tslc/output/verify.py`
- `tslc/src/tslc/api.py`
- `tslc/src/tslc/cli.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/render/rust_project.py`
- `tslc/tests/test_build_verify_config.py`
- `tslc/tests/test_catalog_validation.py`
- `tslc/tests/test_cli.py`
- `tslc/tests/test_profile_rendering.py`
- `docs/redesign/design-decisions.md`
- `docs/agent/tslc-vector-query-handoff.md`
- `docs/agent/current-redesign-state.md`

## Design Invariants To Check

- Emulator executable paths must remain verifier/CLI configuration, not machine
  profile data.
- Profile/render metadata should be typed (`MachineProfileEmulator`,
  `VerifyEmulator`) and deterministic.
- SDE and QEMU should share the same metadata concept without pretending they
  have the same command shape.
- C++ QEMU should use CMake cross-emulator configuration so host `ctest` is not
  run under QEMU.
- Rust QEMU should build tests with `cargo test --no-run --message-format=json`
  and run produced test binaries through QEMU.
- Renderers should only report already-decided verifier metadata; they should
  not perform primitive selection or emulator executable lookup.
- Native ARM extension emission should remain clearly deferred; do not confuse
  the NEON-profile QEMU proof with full `Simd<_, Neon>` support.

## Commands Already Run

```bash
python -m compileall -q tslc/src/tslc
```

Result: passed.

```bash
python -m pytest -q tslc/tests/test_build_verify_config.py tslc/tests/test_catalog_validation.py::test_machine_profile_emulator_metadata_is_validated tslc/tests/test_cli.py tslc/tests/test_profile_rendering.py
```

Result: `27 passed`.

```bash
./verify.sh
```

Result: passed all targeted validations: `238` non-build tests collected, `5`
value-test build/run checks run serially, and `53` generated-build tests
passed across the generated-build shards.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends rust --output-root ./tslctmp/ARM_RUST_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: Rust cross-built aarch64 musl test binaries with `rust-lld`, ran them
through `qemu-aarch64 -cpu cortex-a76`, and passed `150` generated value tests.

```bash
PYTHONPATH=tslc/src python -m tslc.cli --sources tsldata --machine-profiles supplementary/buildsystem/machine_profiles.json --primitives add --profiles neon --backends cpp --output-root ./tslctmp/ARM_CPP_QEMU --test --value-test-warnings --qemu-aarch64 /usr/bin/qemu-aarch64
```

Result: QEMU/CMake wiring was exercised, but clang failed because the host lacks
an aarch64 C++ sysroot/standard library (`fatal error: 'array' file not found`).

## Review Questions

1. Does the emulator abstraction stay small, typed, and verifier-owned?
2. Does the QEMU command path avoid the SDE-shaped mistake of wrapping host
   commands that QEMU cannot execute?
3. Are CLI/API additions narrow and optional?
4. Are diagnostics/skips honest when a configured emulator is missing or a
   profile requires a different emulator kind?
5. Does the documentation clearly distinguish ARM/QEMU verifier support from
   native ARM extension codegen support?

## Expected Verdict Format

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`

Lead with findings, ordered by severity, with file/line references. If there
are no blocking findings, say so and note any follow-ups.
