# tslgen-v99

[![Python Logic](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/python.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/python.yml)
[![Generated Build](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-build.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-build.yml)
[![Generated Value Tests](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-values.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-values.yml)
[![Generated Package](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-package.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/generated-package.yml)
[![Coverage Ratchet](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/coverage-ratchet.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/coverage-ratchet.yml)
[![Docs](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/docs.yml/badge.svg?branch=main)](https://github.com/JPietrzykTUD/tslgen-v99/actions/workflows/docs.yml)

This repository contains `tslc`, a Python compiler for the TSL data language,
plus the source data, templates, helper assets, coverage baselines, and CI
workflows used to generate deterministic C++ and Rust SIMD library artifacts.

`tslc` reads `.tsl` source data, builds a validated catalog, selects primitive
implementations for explicit targets, lowers TSIL body regions, renders
generated projects, and optionally verifies them with real toolchains.

## Project Map

```text
tslc/          Python compiler package, tests, charter, and architecture docs
tsldata/       TSL extension/profile/type/primitive source corpus
.github/      GitHub Actions workflows, actions, and workflow-only scripts
supplementary/ Build-system templates, helper sources, docs assets, reusable CI helpers
coverage/      Coverage ratchet baseline and generated coverage inventory
tslctmp/       Local generated output and scratch space; do not commit
```

## Quick Start

Run from the repository root unless noted.

```bash
python -m compileall -q tslc/src/tslc
PYTHONPATH=tslc/src python -m pytest -q tslc/tests
git diff --check
```

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
- Design contract: [tslc/CHARTER.md](tslc/CHARTER.md)
- Architecture narrative: [tslc/DESCRIPTION.md](tslc/DESCRIPTION.md)
- Active planning guide: [PLANS.md](PLANS.md)
- Contributor/agent instructions: [AGENTS.md](AGENTS.md)
