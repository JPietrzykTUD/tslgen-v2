---
name: add-tsl-extension
description: Add a target extension or machine-profile family through TSL source data, typed compiler capabilities, generated artifacts, verification, and tests. Use when asked to add a SIMD ISA or extension, fixed or scalable profile, compiler-vector overlay, target family, machine profile, feature or compile mode, or the first primitive slice for a new target.
---

# Add TSL Extension

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tsldata/AGENTS.md`,
   `tslc/AGENTS.md`, `tslc/CHARTER.md`, and `docs/add-extension.md` completely.
   Inspect the closest extension family, target family, and machine profiles.
2. Define the target contract before editing: extension/family names, vector
   width model, inheritance/superseding, supported backends, feature and compile
   modes, profile selection, target triples/flags, headers/modules, and runner.
3. Update only the source-owned surfaces required by the contract:
   `tsldata/detail/target_families.tsl` for family roles, accepted features,
   compiler spellings, and documentation facts;
   `tsldata/extensions/extension.tsl` for extension metadata; and
   `supplementary/buildsystem/machine_profiles.json` for profile instances or
   genuine profile overrides. A feature-, compile-mode-, or profile-only change
   need not edit all three. Do not branch on the new name in generic stages.
4. Add typed catalog/schema/backend support only for concepts the current model
   cannot express. Keep selection and lowering driven by source capabilities;
   keep target syntax and intrinsic composition backend-owned. Add backend
   query leaves through `query_value::<namespace>::<name>` translation data so
   lowering and authoring discover a namespace without generic resolver edits.
5. Prove one small primitive/type slice through selection, lowering, rendering,
   generated build, and value tests before broadening coverage. Use the
   primitive or primitive-implementation skill for that slice when applicable.
6. If the target needs a new compiler, cross-target path, runner, emulator, or
   preflight behavior, also use `extend-tslc-verification`. Keep tool paths
   injectable and unavailable hardware/toolchains skip-safe.
7. Test catalog promotion, capability validation, profile selection, lowering,
   backend spelling, additive query/authoring discovery, verifier configuration,
   and deterministic diagnostics. Use a synthetic next family, feature, or
   query namespace to prove generic consumers do not need name branches.
8. Run a focused smoke generation, inspect emitted target facts, then broaden
   to the full Python suite and generated gates justified by the slice.

## Checks

- The next similar extension should mostly add source data, profiles,
  implementations, and tests rather than new name classifiers.
- Unsupported backend/profile/type combinations must remain explicit.
- Templates must format typed decisions, not infer target semantics.
- Update coverage ratchets only after generated build/value behavior is stable
  and the task explicitly authorizes baseline changes.

## Useful Commands

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_catalog.py tslc/tests/test_catalog_validation.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_backend_target_capability.py tslc/tests/test_profile_rendering.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_select_and_lower*.py tslc/tests/test_build_verify_config.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_generation_conditionals.py tslc/tests/test_query_authoring.py
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
./dev.sh build --primitives add --profiles PROFILE --backends cpp,rust
./dev.sh test --primitives add --profiles PROFILE --backends cpp,rust
```
