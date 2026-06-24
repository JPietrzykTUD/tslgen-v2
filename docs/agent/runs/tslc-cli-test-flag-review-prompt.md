# TSLc CLI `--test` Flag Review Prompt

## Goal

Review the focused CLI slice that adds `--test` for generated value-test
execution.

## Scope

Files to inspect:

- `tslc/src/tslc/cli.py`
- `tslc/tests/test_cli.py`
- `tslc/README.md`
- `docs/redesign/design-decisions.md`
- `docs/agent/current-redesign-state.md`

## Expected Design

- `--test` is a command-line convenience only.
- It reuses existing generation and verification contracts:
  - generation gets `test_harness=True`;
  - value-test planning warnings are enabled;
  - after-write verification runs with `run_value_tests=True`.
- It requires `--output-root` because build/test verification operates on
  written generated artifacts.
- It should print clear user-facing feedback before running value-test
  verification, print captured `ctest` / value-enabled `cargo test`
  stdout/stderr from verifier `test` steps, and report a build/test
  verification result afterward.
- It should keep configure/build command output quiet unless those commands
  fail through existing diagnostics.
- It must not introduce a new pipeline stage, generation mode, public API
  wrapper, verifier command path, renderer-side semantic inference, or source
  test semantics.
- `--verify` should keep its compile-only behavior unless `--test` is also
  present.

## Validation Already Run

```bash
python -B -m compileall -q tslc/src/tslc tslc/tests/test_cli.py
python -m pytest -q tslc/tests/test_cli.py
```

Result: both passed; the pytest run reported `2 passed`.

## Review Questions

1. Does the CLI mapping stay thin, or did it add avoidable plumbing/machinery?
2. Is the `--output-root` requirement clear and enforced before side effects?
3. Does the CLI make it visually clear that value tests are actually run,
   including `ctest` / `cargo test` output?
4. Are existing value-test integration tests still the owner of build/run
   semantics, with CLI tests limited to option mapping?
5. Do README and ADR-090 accurately describe the behavior without overstating
   architecture?

## Expected Verdict

Return one of:

- `Accept`
- `Accept With Follow-Ups`
- `Needs Revision`
- `Return To Planner`
