# TSL v1 support-file compile-cost evidence

Capture date: 2026-09-11T10:58:13+00:00

Status: final Slice 13 measurement; informational and non-gating

## Scope and method

The repository-local, non-networked measurement script is
[`supplementary/benchmarks/measure_support_compile_cost.py`](../supplementary/benchmarks/measure_support_compile_cost.py).
It compares the frozen Slice 0 scalar/AVX2 project with a freshly
generated scalar/AVX2 project. Baseline and candidate clean builds are
interleaved; every C++ object and Cargo target directory is removed
before its sample. Wall and child CPU times are recorded for every
sample; tables report medians over 3 repetitions.
Cargo is forced offline and incremental compilation is disabled.

Absolute timings are not release gates: this host is not a stable
runner and no cross-host noise band has been established. The observed
spread is the larger within-revision min/max span for the paired run.
A classification outside that spread is a review signal, not an
automatic performance claim.

## Provenance

- Baseline revision: `34e8980b`
- Candidate revision: `3dbd51ac7afc5aea4bc3073b9d73d2e227df0656`
- Baseline manifest SHA-256: `afe13562db7a9c8e50b4c03b25930d34c0879a9754bf96464c74cb5f3b31d740`
- Candidate manifest SHA-256: `2caa588ffb9551fe9321a2a28f2edf664ce1ad324ca1d596dbee4f6597b2b281`
- Host: `Linux-6.8.0-60-generic-x86_64-with-glibc2.43`; `x86_64`; 24 logical CPUs
- Python: `3.14.4`

Tool versions:

- clang: `Ubuntu clang version 21.1.8 (6ubuntu1)`
- gcc: `g++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`
- Rust msrv: `rustc 1.89.0 (29483883e 2025-08-04)`; `cargo 1.89.0 (c24e10642 2025-06-23)`
- Rust stable: `rustc 1.98.0 (88d9e12ae 2026-08-18)`; `cargo 1.98.0 (797e8a9bc 2026-08-05)`

## C++ preprocessing volume

Each workload is a no-op translation unit. `core` includes
`tsl_core.hpp`; `primitives` includes the selected profile header;
`algorithms` adds `tsl_algorithm.hpp`. Bytes and lines are each
compiler's `-E -P` output. Token records come from Clang's own
`-dump-tokens` output; the script does not implement a C++ lexer.

| Revision | Compiler | Profile | Workload | Preprocessed bytes | Lines | Clang token records |
| --- | --- | --- | --- | ---: | ---: | ---: |
| baseline | gcc | scalar | core | 2656196 | 73795 | 510846 |
| baseline | clang | scalar | core | 2827739 | 58456 | 510846 |
| candidate | gcc | scalar | core | 2545044 | 70081 | 490221 |
| candidate | clang | scalar | core | 2715685 | 55041 | 490221 |
| baseline | gcc | scalar | primitives | 5264934 | 121154 | 1106197 |
| baseline | clang | scalar | primitives | 5436454 | 105813 | 1106197 |
| candidate | gcc | scalar | primitives | 5451247 | 132993 | 1085572 |
| candidate | clang | scalar | primitives | 5621865 | 117951 | 1085572 |
| baseline | gcc | scalar | algorithms | 5587058 | 130628 | 1167394 |
| baseline | clang | scalar | algorithms | 5758890 | 115236 | 1167394 |
| candidate | gcc | scalar | algorithms | 5785778 | 140826 | 1146904 |
| candidate | clang | scalar | algorithms | 5956597 | 125720 | 1146904 |
| baseline | gcc | avx2 | core | 2655350 | 73762 | 510846 |
| baseline | clang | avx2 | core | 2827739 | 58456 | 510846 |
| candidate | gcc | avx2 | core | 2544198 | 70048 | 490221 |
| candidate | clang | avx2 | core | 2715685 | 55041 | 490221 |
| baseline | gcc | avx2 | primitives | 9158961 | 200572 | 2059449 |
| baseline | clang | avx2 | primitives | 9331963 | 185262 | 2059449 |
| candidate | gcc | avx2 | primitives | 9887585 | 231479 | 2038824 |
| candidate | clang | avx2 | primitives | 10059689 | 216472 | 2038824 |
| baseline | gcc | avx2 | algorithms | 9481085 | 210046 | 2120646 |
| baseline | clang | avx2 | algorithms | 9654399 | 194685 | 2120646 |
| candidate | gcc | avx2 | algorithms | 10222116 | 239312 | 2100156 |
| candidate | clang | avx2 | algorithms | 10394421 | 224241 | 2100156 |

## C++ clean compile timing

| Compiler | Profile | Workload | Baseline/final median wall (s) | Wall delta | Baseline/final median CPU (s) | CPU delta | Observed wall spread (s) | Classification |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| gcc | scalar | core | 0.446 / 0.432 | -3.2% | 0.446 / 0.431 | -3.4% | 0.011 | improvement_outside_observed_spread |
| gcc | scalar | primitives | 0.671 / 0.651 | -2.9% | 0.671 / 0.651 | -3.0% | 0.012 | improvement_outside_observed_spread |
| gcc | scalar | algorithms | 0.697 / 0.678 | -2.9% | 0.697 / 0.677 | -2.9% | 0.017 | improvement_outside_observed_spread |
| gcc | avx2 | core | 0.433 / 0.420 | -2.9% | 0.432 / 0.420 | -2.9% | 0.003 | improvement_outside_observed_spread |
| gcc | avx2 | primitives | 1.222 / 1.215 | -0.6% | 1.222 / 1.214 | -0.6% | 0.021 | within_observed_spread |
| gcc | avx2 | algorithms | 1.254 / 1.250 | -0.3% | 1.254 / 1.250 | -0.3% | 0.016 | within_observed_spread |
| clang | scalar | core | 0.381 / 0.363 | -4.6% | 0.381 / 0.363 | -4.6% | 0.008 | improvement_outside_observed_spread |
| clang | scalar | primitives | 0.779 / 0.762 | -2.2% | 0.779 / 0.762 | -2.2% | 0.003 | improvement_outside_observed_spread |
| clang | scalar | algorithms | 0.820 / 0.804 | -1.9% | 0.819 / 0.804 | -1.9% | 0.011 | improvement_outside_observed_spread |
| clang | avx2 | core | 0.382 / 0.364 | -4.7% | 0.382 / 0.364 | -4.7% | 0.007 | improvement_outside_observed_spread |
| clang | avx2 | primitives | 1.641 / 1.624 | -1.1% | 1.640 / 1.623 | -1.0% | 0.023 | within_observed_spread |
| clang | avx2 | algorithms | 1.693 / 1.688 | -0.3% | 1.692 / 1.688 | -0.3% | 0.007 | within_observed_spread |

## Rust clean build timing

`check`, release build, Rustdoc, and a minimal path-dependent
consumer each start from an empty target directory. The consumer
imports one public error type; Cargo still compiles the generated
library module graph, so this is packaging evidence rather than a
claim about selective Rust imports.

| Toolchain | Task | Baseline/final median wall (s) | Wall delta | Baseline/final median CPU (s) | CPU delta | Observed wall spread (s) | Classification |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| msrv | check | 5.671 / 5.554 | -2.1% | 5.849 / 5.729 | -2.1% | 0.182 | within_observed_spread |
| msrv | release_build | 9.810 / 9.981 | +1.7% | 11.905 / 12.148 | +2.0% | 0.327 | within_observed_spread |
| msrv | rustdoc | 4.640 / 4.645 | +0.1% | 4.888 / 4.885 | -0.1% | 0.173 | within_observed_spread |
| msrv | downstream_consumer | 6.648 / 6.722 | +1.1% | 7.808 / 7.802 | -0.1% | 0.082 | within_observed_spread |
| stable | check | 5.086 / 5.054 | -0.6% | 5.292 / 5.260 | -0.6% | 0.156 | within_observed_spread |
| stable | release_build | 9.321 / 9.455 | +1.4% | 11.465 / 11.646 | +1.6% | 0.153 | within_observed_spread |
| stable | rustdoc | 4.362 / 4.471 | +2.5% | 4.658 / 4.767 | +2.3% | 0.039 | regression_outside_observed_spread |
| stable | downstream_consumer | 6.072 / 6.088 | +0.3% | 7.188 / 7.232 | +0.6% | 0.029 | within_observed_spread |

## Review conclusion

No material compile-cost regression was observed. All twelve C++ wall and CPU
medians were flat or lower. Seven of eight Rust tasks were within their paired
observed wall-time spread. Current-stable Rustdoc was the sole outside-spread
signal at 0.109 seconds (+2.5% wall, +2.3% CPU), which is not material on this
non-stable host and was not reproduced by MSRV Rustdoc.

Preprocessed byte and line volume increased for the scalar and AVX2 primitive
and algorithm workloads, while Clang's token records fell for every workload
and both compilers' clean compile medians did not regress. This is direct
evidence that support-file bytes alone were an unreliable compile-cost proxy.
The results do not justify selective C++ include contracts, Rust Cargo
features, or another public packaging decision.

## Reproduction

From the repository root, retain or regenerate the Slice 0 project
at the recorded baseline revision, then run:

```bash
python supplementary/benchmarks/measure_support_compile_cost.py \
  --baseline-root ./tslctmp/support-file-baseline-snapshot/generated \
  --markdown-output research/tsl-v1-support-file-compile-cost.md
```

The complete per-repetition JSON remains under
`./tslctmp/support-file-compile-cost/results.json`; it is scratch
evidence and is not committed. Regeneration replaces the measured
tables; review the new signals and update the human conclusion
before committing the report.
