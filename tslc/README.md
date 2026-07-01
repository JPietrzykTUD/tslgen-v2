# tslc — the TSL compiler

`tslc` compiles the TSL data language (`tsldata/**.tsl`) into deterministic,
compilable C++ and Rust SIMD library artifacts.

It is a clean restart of the earlier `tslgen` generator. The architecture is a
small compiler pipeline:

```
sources -> parse -> catalog -> select -> scan body -> lower -> emit -> render -> write -> verify
```

- **`sources`** reads `.tsl` files (the only filesystem-read boundary).
- **`syntax`** parses outer declarations + TSIL body envelopes (Lark, ported).
- **`catalog`** promotes the parse tree into a typed, immutable domain model.
- **`select`** chooses an implementation for an explicit `Target`
  (backend × extension × type), expanding type groups and extension fallbacks.
- **`ir`** models a TSIL body as a recursive sequence of `[raw text | region]`
  segments — *not* an abstract syntax tree. Raw target-language text passes
  through verbatim; only recognized TSIL keyword islands are lowered.
- **`lower`** walks the segment sequence, resolving type/value queries and
  composing intrinsic names into a backend-ready `LoweredFunction`.
- **`backend`** emits C++ and Rust function text from lowered functions.
- **`render`/`output`** assemble and write the `generated/{cpp,rust}/...` tree,
  then build-verify it with the local toolchains.

See [CHARTER.md](CHARTER.md) for the design rules this project holds itself to.

## Quick start

```bash
cd tslc
python -m pytest -q
# Generated C++/Rust build/value gates are opt-in:
python -m pytest -q --run-generated-builds tests/test_build_verify.py tests/test_value_tests.py
# Write scratch/output under the workspace (./tslctmp), not /tmp: on WSL the
# container overlay (which backs /tmp) only grows the VHDX and never shrinks.
python -m tslc.cli --sources ../tsldata \
  --machine-profiles ../supplementary/buildsystem/machine_profiles.json \
  --primitives add,sub --profiles scalar,avx2 \
  --output-root ./tslctmp/generated --verify

# Build and run generated value tests.
# The CLI prints captured ctest/cargo test output for the test steps.
python -m tslc.cli --sources ../tsldata \
  --machine-profiles ../supplementary/buildsystem/machine_profiles.json \
  --primitives add,sub --profiles avx2 --backends cpp \
  --output-root ./tslctmp/value-tests --test
```
