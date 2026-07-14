---
name: extend-tslc-verification
description: Add or change generated build and value-test verification in tslc. Use when asked to support a compiler or toolchain command, target triple or linker, runner or emulator, compiler or target preflight, cross-compilation path, verifier backend driver, missing-tool skip, command report, or generated verification capability independent of adding a backend.
---

# Extend TSLC Verification

## Workflow

1. Read `AGENTS.md`, `CHARTER.md`, `PLANS.md`, `tslc/AGENTS.md`,
   `tslc/CHARTER.md`, the existing `tslc/src/tslc/output/` verifier model,
   drivers/configuration/runners, backend capability registration,
   `supplementary/buildsystem/machine_profiles.json`, `dev.sh`, and relevant CI
   helpers/tests. Read `docs/add-extension.md` when a target extension is in
   scope.
2. Classify the requested capability before editing: backend driver, compiler
   command, target/linker/environment projection, machine-profile runner,
   preflight, generated build/test command, or report/skip behavior.
3. Keep caller overrides in backend-keyed `BuildVerifierConfig`; keep target and
   runner requirements in typed emitted profiles derived from source/profile
   data; keep backend orchestration in the registered verifier driver. Avoid
   generic backend/profile name checks.
4. Add runner-kind command construction in the focused runner boundary and
   validate allowed kinds through target/profile capabilities. If another
   similar addition would extend scattered conditionals, consolidate the
   runner extension point before adding more branches.
5. Preflight compilers and targets before expensive generated builds. Preserve
   complete commands and deterministic diagnostics without leaking secrets or
   ambient host assumptions. Keep `tslc doctor` on the same typed profile
   projection, backend verifier driver, and `BuildVerifierConfig` path so its
   readiness report cannot drift from build/test verification.
6. Treat absent optional compilers, targets, runners, emulators, or hardware as
   explicit skips unless the requested gate requires them. Injectable
   configuration must override ambient discovery.
7. Keep all generated trees, preflight sources, build directories, and reports
   under the selected workspace output root. Do not introduce hidden network or
   host dependencies.
8. Update `dev.sh`, container setup, or CI only when the capability is part of
   the supported shared workflow; keep local-only tools optional.
9. Test command construction, override precedence, missing tools, runner
   prefixes, target/environment projection, skip/failure reporting, and backend
   driver dispatch. Run the smallest real generated build/value gate that can
   prove the new path.

## Checks

- Configuration, profile requirements, backend drivers, and subprocess
  execution each have one owner.
- A skipped profile states exactly which capability is unavailable.
- Native, cross-compiled, and emulated paths cannot silently select one
  another's compiler, target, or runner.
- Hardware/toolchain absence is reported as a validation gap, not hidden as
  success.

## Useful Commands

```bash
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify_config.py
PYTHONPATH=tslc/src python -m tslc doctor --profile scalar
PYTHONPATH=tslc/src python -m pytest -q tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
git diff --check
```
