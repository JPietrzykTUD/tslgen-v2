# tslgen-v2

[![Python Logic](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/python.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/python.yml)
[![Generated Build](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-build.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-build.yml)
[![Generated Value Tests](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-values.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-values.yml)
[![Generated Package](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-package.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/generated-package.yml)
[![Coverage Ratchet](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/coverage-ratchet.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/coverage-ratchet.yml)
[![Docs](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v2/actions/workflows/docs.yml)

This repository contains `tslc`, a Python compiler for the TSL data language,
plus the authored source data, packaged compiler assets, generated-documentation
inputs, coverage baselines, examples, and CI workflows used to generate
deterministic C++ and Rust SIMD library artifacts.

`tslc` reads `.tsl` source data, builds a validated catalog, selects primitive
implementations for explicit targets, lowers TSIL body regions, renders
generated projects, and optionally verifies them with real toolchains.

## Project Map

```text
CHARTER.md    Repository-wide design contract
tslc/         Python compiler package, tests, compiler charter, and architecture docs
tsldata/      TSL type/language/extension/primitive source corpus
editors/      Editor clients; compiler semantics remain in tslc
docs/         Human-authored maintainer guides
examples/     Checked-in C++ and Rust generated-library consumers
.github/      GitHub Actions workflows, actions, and workflow-only scripts
supplementary/ Machine profiles, generated-doc inputs, and reusable CI helpers
coverage/     Coverage and benchmark ratchet evidence
tslctmp/      Local generated output and scratch space; do not commit
```

## Quick Start

Run from the repository root unless noted.

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

Install the unified command locally, or use its module equivalent:

```bash
python -m pip install -e ./tslc
tslc check
tslc list primitives
tslc doctor --profile scalar
```

The checked-in `tslc.toml` supplies corpus, profile, backend, and scratch-output
defaults. See the [command-line tools guide](docs/tslc-cli.md) for validation,
discovery, generation, inspection, audit, coverage, and configuration commands.
For unsaved diagnostics, navigation, completion, and explicit specialization
preview, see the [TSL editor guide](docs/tsl-editor.md).

Generate and verify a small C++/Rust project:

```bash
./dev.sh build --primitives add --profiles scalar,avx2 --backends cpp,rust
```

Build and run generated value tests:

```bash
./dev.sh test --primitives add --profiles avx2 --backends cpp
```

Use `./tslctmp/...` for generated trees, build directories, and scratch output.
This matters in the devcontainer/WSL setup because `/tmp` lives on the container
overlay.

## Where To Look

- Package quick start: [tslc/README.md](tslc/README.md)
- Command-line tools: [docs/tslc-cli.md](docs/tslc-cli.md)
- Editor setup and architecture: [docs/tsl-editor.md](docs/tsl-editor.md)
- Repository charter: [CHARTER.md](CHARTER.md)
- Compiler charter: [tslc/CHARTER.md](tslc/CHARTER.md)
- Architecture narrative: [tslc/DESCRIPTION.md](tslc/DESCRIPTION.md)
- Active planning guide: [PLANS.md](PLANS.md)
- Repository instructions: [AGENTS.md](AGENTS.md)
- Claude Code import bridge: [CLAUDE.md](CLAUDE.md)
- Compiler instructions: [tslc/AGENTS.md](tslc/AGENTS.md)
- TSL source-data instructions: [tsldata/AGENTS.md](tsldata/AGENTS.md)
- Shared task skills: `.agents/skills/`, exposed to Claude Code through
  `.claude/skills/`

## License

This repository is licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE) and [NOTICE](NOTICE). The `tslc` Python package and the VS
Code extension include their own Apache-2.0 `LICENSE` and `NOTICE` files for
standalone distribution.
