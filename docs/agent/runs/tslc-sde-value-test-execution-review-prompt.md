# TSLc SDE Value-Test Execution Review Prompt

## Goal

Review the SDE-backed value-test execution slice for all SDE-annotated x86
machine profiles. The slice should prove that generated value tests can be
built and run for both C++ and Rust without requiring native host ISA support.

## Scope

Files to inspect:

- `supplementary/buildsystem/machine_profiles.json`
- `tslc/src/tslc/catalog/machine_profiles.py`
- `tslc/src/tslc/output/verify.py`
- `tslc/src/tslc/api.py`
- `tslc/src/tslc/cli.py`
- `tslc/src/tslc/render/cpp_project.py`
- `tslc/src/tslc/render/rust_project.py`
- `tslc/src/tslc/value_tests/_pattern_core.py`
- `tslc/src/tslc/value_tests/render_rust.py`
- `tslc/tests/test_build_verify_config.py`
- `tslc/tests/test_catalog_validation.py`
- `tslc/tests/test_cli.py`
- `tslc/tests/test_value_test_planning.py`
- `tsldata/primitives/bitwise/bit_ops.tsl`
- `tsldata/primitives/conversion/repr_change.tsl`
- `tsldata/primitives/load_store/load.tsl`
- `tsldata/primitives/load_store/pack_expand.tsl`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`
- `docs/agent/tslc-vector-query-handoff.md`

## Expected Design

- SDE execution belongs to the after-write verifier, not selection, lowering,
  value-test planning, or rendering.
- Machine profile `sde` aliases are typed profile metadata, validated at the
  profile-loading boundary and passed through render data to verification.
- `--sde` is explicit CLI opt-in. Normal generation and verification must not
  require host autodetection or an emulator.
- C++ and Rust consume the same profile metadata. C++ may wrap `ctest` through
  SDE; Rust should build test binaries first and run the binaries through SDE.
- Missing emulator paths and missing Rust test binaries must surface as
  structured diagnostics.
- Source metadata corrections exposed by SDE should remain source-owned
  feature/profile facts, not verifier exceptions or primitive-name branches.
- The verifier must not special-case primitive names, profile names, or value
  test case families beyond typed profile metadata and backend command shape.
- Existing C++/Rust AVX2 parity behavior must remain intact.

## Validation Already Run

Focused tests:

```bash
python -m compileall -q tslc/src/tslc
python -m pytest -q tslc/tests/test_value_test_planning.py tslc/tests/test_build_verify_config.py tslc/tests/test_catalog_validation.py::test_machine_profile_sde_metadata_is_validated tslc/tests/test_cli.py
```

Result: `30 passed`.

Full repository gate:

```bash
./verify.sh
```

Result: passed all targeted validations, including 220 non-build tests and 53
generated-build tests.

Real SDE both-backend sweep:

```text
sse, sse2, sse3, avx, avx2, knl, kml, skylake, cannonlake,
cascadelake, cooperlake, icelake-rockerlake, tigerlake, zen4,
sapphirerapids, zen5
```

Result: every profile generated, wrote artifacts, and verified C++ plus Rust
value tests through `/opt/intel-sde/sde64` with zero diagnostics.

## Review Questions

1. Does SDE stay cleanly contained in the verifier side-effect boundary?
2. Are the C++ and Rust execution paths symmetric at the profile metadata
   level, with Rust differences limited to Cargo's test-binary workflow?
3. Are SDE and source-feature diagnostics structured and actionable?
4. Did any primitive-, extension-, or profile-specific exception logic leak
   into renderers, planning, or value-test case classification?
5. Are the KNL/KML profile and `.tsl` requirement corrections legitimate
   source metadata fixes, and are they covered by generated-build or SDE
   evidence?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
- `Reject`

For any non-`Accept` verdict, include concrete findings with file/line
references and the smallest recommended next action.
