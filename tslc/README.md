# tslc — the TSL compiler

`tslc` compiles the TSL data language (`tsldata/**.tsl`) into deterministic,
compilable C++ and Rust SIMD library artifacts.

It is a clean restart of the earlier `tslgen` generator. The architecture is a
small compiler pipeline:

```
sources -> parse -> catalog -> select -> scan body -> lower -> finalize/validate/plan -> render -> write -> verify
```

- **`sources`** owns `.tsl` source-document reads; compiler assets and explicit
  configuration have their own loading boundaries.
- **`syntax`** parses outer declarations + TSIL body envelopes (Lark, ported).
- **`catalog`** promotes the parse tree into a typed, immutable domain model.
- **`select`** chooses implementations for one machine profile and registered backend,
  producing explicit extension × type slots while expanding type groups and fallbacks.
- **`ir`** models a TSIL body as a recursive sequence of `[raw text | region]`
  segments — *not* an abstract syntax tree. Raw target-language text passes
  through verbatim; only recognized TSIL keyword islands are lowered.
- **`lower`** walks the segment sequence, resolving type/value queries and
  composing intrinsic names into a backend-ready `LoweredSpecialization`.
- **`backend`** owns target-language type projection, helper requirements,
  emitted profiles, pre-render validation, and C++/Rust function emission.
- **`value_tests`** plans executable cases from finalized emitted names.
- **`benchmark`** plans optional typed variant measurements and policy data.
- **`render`/`output`** assemble and write the `generated/{cpp,rust}/...` tree,
  consuming already-decided semantics, then build-verify it with local toolchains.

See the repository [charter](../CHARTER.md) and compiler
[charter](CHARTER.md) for the design rules this project holds itself to.

## Quick start

```bash
# Run from the repository root.
python -m compileall -q tslc/src/tslc
(cd tslc && python -m mypy)
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
# Generated C++/Rust build/value gates are opt-in:
PYTHONPATH=tslc/src python -m pytest -q --run-generated-builds tslc/tests/test_build_verify.py tslc/tests/test_value_tests.py
# Write scratch/output under the workspace (./tslctmp), not /tmp: on WSL the
# container overlay (which backs /tmp) only grows the VHDX and never shrinks.
python -m pip install -e ./tslc
tslc check
tslc list primitives
tslc generate --primitives add,sub --profiles scalar,avx2
tslc build --primitives add,sub --profiles scalar,avx2
tslc preview --primitive add --profile avx2 --type si32 --backend cpp
tslc export pivot --primitives add --profiles avx2 --types si32 \
  --language cpp,rust \
  --output-root ./tslctmp/pivot

# Build and run generated value tests.
# The CLI prints captured ctest/cargo test output for the test steps.
tslc test --primitives add,sub --profiles avx2 --backends cpp
```

The repository `tslc.toml` supplies source, machine-profile, backend, and
workspace-output defaults. `PYTHONPATH=tslc/src python -m tslc ...` exposes the
same commands without installation. See the full
[command-line tools guide](../docs/tslc-cli.md) for `check --watch`, JSON
diagnostics, catalog discovery, `doctor`, inspection, audits, and exit codes.

PIVOT YAML is an explicit corpus export, not a registered compiler backend.
`tslc export pivot` has its own subset planner, lowering policy, renderer, and
output root. Its required language selection writes YAML below `cpp/` and/or
`rust/`; invoking it does not enter or modify ordinary C++/Rust generation.

Install the optional editor server without the repository-wide requirements:

```bash
python -m pip install -e './tslc[editor]'
tslc lsp --help
```

The Python server remains compiler-owned under `src/tslc/lsp/`; the TypeScript
VS Code client is under `../editors/vscode-tsl/`. See the
[TSL editor guide](../docs/tsl-editor.md) for setup, explicit saved-file
preview, extension development, performance evidence, limitations, and how to
refresh editable versus non-editable installations.

Contributor instructions for compiler changes live in
[`AGENTS.md`](AGENTS.md), in addition to the repository instructions.

## License

`tslc` is licensed under the Apache License, Version 2.0. See
[`LICENSE`](LICENSE).
