# PIPCost Prototype Instructions

## Scope

These instructions apply to `research/pipcost-src/`. The repository root
`AGENTS.md`, `CHARTER.md`, and `PLANS.md` also apply.

PIPCost is an independently packaged downstream research prototype. It is not
a `tslc` stage, backend, projection, or source-data extension. Dependencies
point from PIPCost to the public `tslc` API and generated C++ product only.
Prototype work does not authorize changes to `tslc/` or `tsldata/`.

## Ownership

PIPCost owns the fixed query, physical-plan identities, synthetic data,
measurement methodology, experiment records, summaries, oracle decisions, and
cost model. It must not present these facts as compiler guarantees.

Do not parse or rewrite generated C++ or TSIL. Disassembly may be captured as
build-specific experimental evidence only.

All generated projects, builds, tests, measurements, models, and caches must
remain below `tslctmp/pipcost/`. Importing `pipcost` must not write files,
register compiler behavior, or alter compiler defaults.

## Validation

Run from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pytest -q -p no:cacheprovider \
  --basetemp=tslctmp/pipcost/pytest \
  research/pipcost-src/tests

PYTHONPYCACHEPREFIX=tslctmp/pipcost/pycache \
  python -m compileall -q research/pipcost-src/src/pipcost

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost doctor --profile avx2

PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=tslc/src:research/pipcost-src/src \
  python -m pipcost check --profile avx2 --compiler c++

git diff --check
```

Hardware-dependent measurements are always explicit. A skipped native build or
run is a verification gap, not evidence of performance.
